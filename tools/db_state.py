"""The store is a build ARTIFACT, not source: fetch and publish it.

    python3 tools/db_state.py --pull     # before work
    python3 tools/db_state.py --push     # after work (refuses if a table emptied; --accept-loss overrides)
    python3 tools/db_state.py --check    # compare table counts with the last publish, publish nothing

Why. data/parl-monitor.db was tracked in git so workflow state was durable
and versioned. It worked until the file reached 88MB against GitHub's 100MB
HARD push limit, growing ~15MB per build sprint (73 -> 88MB over three days
in August 2026) -- one more sprint would have stopped all six workflows at
once. The db is derived state that can be rebuilt, so it now lives as a
GitHub Release asset: no LFS bandwidth, a 2GB ceiling, and zero git history
growth (Christopher's decision, 2026-08-24).

Provenance is NOT lost. Every push writes data/parl-monitor.db.json -- size,
sha256, timestamp, and the run that produced it -- and THAT is committed. The
repo still records exactly which store produced which edition; it just does
not carry the bytes. A pull verifies the sha256 and refuses a mismatch, so a
truncated download can never be mistaken for the store.

Auth. On Actions, `gh` is present and GITHUB_TOKEN authenticates it. Locally
`gh` is usually absent, so the REST API is used with `github_token` from
config/secrets.yaml -- a PAT with contents:write on this repo. Without one a
pull cannot reach a private repo's assets, and the tool says so plainly
rather than leaving a stale store in place.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "parl-monitor.db")
SIDECAR = DB + ".json"
REPO = "thejoycething-code/parl-monitor"
TAG = "db-state"          # one rolling release, not one per run
ASSET = "parl-monitor.db"
PREV = ASSET + ".prev"    # the copy kept aside while a new one uploads
API = "https://api.github.com"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def token():
    for var in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    path = os.path.join(ROOT, "config", "secrets.yaml")
    if os.path.exists(path):
        import yaml
        with open(path, encoding="utf-8") as handle:
            return (yaml.safe_load(handle) or {}).get("github_token")
    return None


def have_gh():
    return shutil.which("gh") is not None


def _api(path, tok, data=None, headers=None, method=None):
    req = urllib.request.Request(
        path if path.startswith("http") else API + path, data=data,
        method=method)
    req.add_header("Authorization", "Bearer " + tok)
    req.add_header("Accept", "application/vnd.github+json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=600) as resp:
        return resp.read()


def release(tok):
    """The rolling release, created on first use."""
    try:
        return json.loads(_api("/repos/{0}/releases/tags/{1}".format(REPO, TAG),
                               tok))
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    body = json.dumps({
        "tag_name": TAG, "name": "Store state",
        "body": ("The parl-monitor SQLite store, published by the weekly "
                 "workflows. Derived state, not source: see "
                 "tools/db_state.py."),
        "prerelease": True}).encode()
    return json.loads(_api("/repos/{0}/releases".format(REPO), tok, data=body,
                           method="POST"))


def _no_asset_yet():
    """No release asset. Fine on the FIRST run, fatal afterwards.

    A working copy means we are bootstrapping: the run proceeds and its
    push publishes the first asset. NO working copy means the store was
    untracked before an asset existed, and continuing would build an empty
    store and publish it over nothing -- so fail loudly instead.
    """
    if os.path.exists(DB):
        print("no published store yet -- bootstrapping from the working copy "
              "({0:.1f} MB); this run's push publishes the first asset."
              .format(os.path.getsize(DB) / 1e6))
        return 0
    print("FATAL: no release asset AND no working copy at {0}.\n"
          "  The store was untracked before an asset was published. Do NOT "
          "let a run continue from here: it would build an empty store and "
          "publish it. Restore the store from git history "
          "(git show <commit>:data/parl-monitor.db > data/parl-monitor.db) "
          "and push it once.".format(DB))
    return 1


# Where a pull records WHICH published store it took. Untracked and
# local: it describes this working copy, not the repo.
PULLED = os.path.join(os.path.dirname(SIDECAR), ".store-pulled")


def published_sha():
    """The sha the REPO currently says is published, from origin/main.

    The committed sidecar is the pointer of record, so origin's copy of
    it answers "has anyone published since I pulled?" for the cost of a
    fetch -- no 131MB download. Returns None if git cannot answer, and
    the caller then warns rather than blocks: a guard that fails closed
    on a network blip would stop every workflow.
    """
    try:
        subprocess.run(["git", "fetch", "--quiet", "origin", "main"],
                       cwd=ROOT, capture_output=True, timeout=120)
        out = subprocess.run(
            ["git", "show", "origin/main:data/parl-monitor.db.json"],
            cwd=ROOT, capture_output=True, text=True, timeout=60)
        if out.returncode:
            return None
        return (json.loads(out.stdout) or {}).get("sha256")
    except Exception:
        return None


def install_merge_driver():
    """Bind tools/merge_sidecar.py to the sidecar in THIS clone.

    .gitattributes (versioned) says the sidecar uses the db-sidecar merge
    driver; git only honours that if the driver is defined in local
    config, which is not versioned. Every workflow and every laptop runs
    --pull before touching the store, so this is where the definition
    lands -- idempotently, and never as a reason to fail a pull.
    """
    try:
        subprocess.run(["git", "config", "--local", "merge.db-sidecar.name",
                        "release-asset decides which sidecar is current"],
                       cwd=ROOT, capture_output=True, timeout=30)
        subprocess.run(["git", "config", "--local", "merge.db-sidecar.driver",
                        "python3 tools/merge_sidecar.py %O %A %B"],
                       cwd=ROOT, capture_output=True, timeout=30)
    except Exception as exc:
        print("  [warn] could not install the sidecar merge driver: {0}".format(exc))


def pull():
    install_merge_driver()
    tok = token()
    if have_gh():
        cmd = ["gh", "release", "download", TAG, "--repo", REPO,
               "--pattern", ASSET, "--output", DB, "--clobber"]
        out = subprocess.run(cmd, capture_output=True, text=True)
        if out.returncode:
            if "release not found" in (out.stderr or "").lower():
                return _no_asset_yet()
            # A push that failed between renaming the old asset aside and
            # uploading the new one leaves only PREV. Recover from it rather
            # than failing every workflow: this is exactly the state that
            # broke the day-sweep run on 2026-09-09.
            if any(n == PREV for n, _i in _assets()):
                print("  [warn] no {0} on the release, but {1} is there: a push failed "
                      "part-way. Recovering from it.".format(ASSET, PREV))
                out = subprocess.run(
                    ["gh", "release", "download", TAG, "--repo", REPO,
                     "--pattern", PREV, "--output", DB, "--clobber"],
                    capture_output=True, text=True)
                if not out.returncode and _rename_asset(PREV, ASSET):
                    print("  recovered: {0} is published again. The sidecar in the repo "
                          "may name a store that was never uploaded -- check it.".format(ASSET))
                else:
                    print("gh download of {0} failed: {1}".format(PREV, out.stderr.strip()))
                    return 1
            else:
                print("gh download failed: {0}".format(out.stderr.strip()))
                return 1
    elif tok:
        rel = release(tok)
        asset = next((a for a in rel.get("assets") or []
                      if a["name"] == ASSET), None)
        if not asset:
            asset = next((a for a in rel.get("assets") or []
                          if a["name"] == PREV), None)
            if asset:
                print("  [warn] no {0}, recovering from {1}: a push failed part-way.".format(ASSET, PREV))
            else:
                return _no_asset_yet()
        blob = _api(asset["url"], tok,
                    headers={"Accept": "application/octet-stream"})
        with open(DB + ".part", "wb") as handle:
            handle.write(blob)
        os.replace(DB + ".part", DB)
    else:
        print("CANNOT PULL: no gh and no github_token in config/secrets.yaml.\n"
              "  A private repo's release assets need auth. Add a PAT with\n"
              "  contents:write as `github_token:` in config/secrets.yaml, or\n"
              "  install gh. The working copy is left untouched -- it may be "
              "STALE.")
        return 1

    if os.path.exists(SIDECAR):
        with open(SIDECAR, encoding="utf-8") as handle:
            want = json.load(handle)
        got = sha256(DB)
        if want.get("sha256") and want["sha256"] != got:
            print("SHA MISMATCH: sidecar says {0}, downloaded {1}.\n"
                  "  Refusing to trust this store. Nothing was overwritten in "
                  "place except the download itself; re-run, and if it "
                  "persists the release asset and the committed sidecar have "
                  "diverged.".format(want["sha256"][:12], got[:12]))
            return 1
        with open(PULLED, "a", encoding="utf-8") as handle:
            handle.write(got + "\n")
        print("store pulled and verified ({0:.1f} MB, sha {1}).".format(
            os.path.getsize(DB) / 1e6, got[:12]))
    else:
        print("store pulled ({0:.1f} MB); no sidecar to verify against yet."
              .format(os.path.getsize(DB) / 1e6))
    return 0


def table_counts(path=None):
    """{table: rows} for every table in the store, not only db.TABLES: the
    campaign-alignment and Looker tables live here too and are as easy to lose."""
    import sqlite3
    conn = sqlite3.connect("file:{0}?mode=ro".format(path or DB), uri=True)
    try:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {n: conn.execute('SELECT count(*) FROM "{0}"'.format(n)).fetchone()[0] for n in names}
    finally:
        conn.close()


SHRINK_FLOOR = 20          # below this many rows a halving is noise, not a signal


def compare_counts(before, now):
    """(lost, shrunk) between two {table: rows} maps.

    lost: a table that had rows and now has none, or is gone. shrunk: a table
    of SHRINK_FLOOR rows or more that lost over half. New tables are nobody's
    business here. WHY: the store rebuilt on 2026-09-09 after a corruption came
    back with pq_link at 0 rows against 5,117 written questions, and the only
    thing that noticed was a display test, a day later, after the page shipped.
    A table at zero is the tell of a rebuild that missed something.
    """
    lost, shrunk = [], []
    for table, was in sorted((before or {}).items()):
        if not was:
            continue
        got = (now or {}).get(table, 0)
        if got == 0:
            lost.append((table, was))
        elif was >= SHRINK_FLOOR and got < was * 0.5:
            shrunk.append((table, was, got))
    return lost, shrunk


def check_counts(accept_loss=False, log=print):
    """Refuse to publish a store that emptied a table the last publish had rows
    in, unless the caller says --accept-loss and so takes responsibility."""
    try:
        with open(SIDECAR, encoding="utf-8") as handle:
            before = json.load(handle).get("tables")
    except (OSError, ValueError):
        before = None
    now = table_counts()
    if not before:
        log("  no table counts in the sidecar yet; recording {0} tables".format(len(now)))
        return True, now
    lost, shrunk = compare_counts(before, now)
    for table, was, got in shrunk:
        log("  [warn] {0}: {1} rows at the last publish, {2} now".format(table, was, got))
    if lost:
        log("TABLES EMPTIED SINCE THE LAST PUBLISH:")
        for table, was in lost:
            log("  {0}: had {1} rows, now none".format(table, was))
        if not accept_loss:
            log("Refusing to publish. If this is deliberate (a table retired or "
                "rebuilt from scratch), run again with --accept-loss.")
            return False, now
        log("  --accept-loss given: publishing anyway.")
    return True, now


def check_lineage():
    """Refuse to publish a store that did not come from the current one.

    ONE WRITER AT A TIME was a rule with nothing enforcing it. On
    2026-09-03 the UPR monthly harvested 1,218 new recommendations,
    published them, and committed its sidecar -- and three hours later a
    hand push from a laptop whose store predated that run overwrote the
    asset and the pointer. Both runs were green. The loss surfaced 24
    hours later only because someone measured how stale each source was.

    The check is cheap: the sidecar on origin/main is the pointer of
    record, so if it has moved since our pull, our store is missing
    whatever moved it. Pull, redo the work on the current store, push.
    """
    if "--force" in sys.argv:
        print("  [--force] publishing over whatever is there. This DISCARDS "
              "any run that published since this store was pulled.")
        return True
    theirs = published_sha()
    if theirs is None:
        print("  [warn] could not read origin/main's sidecar, so this push "
              "is unguarded: if another run published since this store was "
              "pulled, its work is about to be discarded.")
        return True
    # EVERY sha this working copy has held, pulled or published -- not
    # just the last one. A push writes the new sha locally but the
    # sidecar reaches origin only when the commit lands, so comparing
    # against the single latest sha refused a perfectly ordinary
    # push-then-push-again. What matters is not whether origin differs,
    # but whether origin holds something WE HAVE NEVER SEEN: that is
    # someone else's work.
    held = []
    if os.path.exists(PULLED):
        held = [ln.strip() for ln in open(PULLED, encoding="utf-8")
                if ln.strip()]
    ours = held[-1] if held else None
    if theirs in held:
        return True
    if ours is None:
        print("REFUSING TO PUBLISH: this working copy has no record of "
              "pulling a store, so there is no way to tell what it would "
              "overwrite.\n  Run --pull first (or --force if you truly mean "
              "to replace the published store).")
        return False
    print("THE STORE MOVED UNDER YOU. Refusing to publish.\n"
          "  this copy:  {0}\n  published:  {1}  (never seen here)\n"
          "  Another run has published since this copy was pulled, and "
          "publishing now would discard its work -- which is how 1,218 UPR "
          "recommendations were lost on 2026-09-03.\n"
          "  Fix: python3 tools/db_state.py --pull, redo this run's work on "
          "the current store, then push. --force overrides.".format(
              (ours or "?")[:12], (theirs or "?")[:12]))
    return False


def stamp_heartbeat():
    """Record WHICH pipeline is publishing, inside the store itself.

    Westminster's tables carry no captured_at, so no amount of reading
    the store could tell whether the Sunday pull had run in a month.
    Every workflow ends in --push, so stamping here covers all of them
    at once and needs no change to twenty collectors. Written BEFORE the
    sha is taken, so it travels with the bytes it describes.
    """
    source = os.environ.get("GITHUB_WORKFLOW") or "local"
    try:
        # src/db.py is the ONLY place that creates tables (tests pin it),
        # and init_db is idempotent, so this also brings an older store
        # up to the current schema before stamping.
        sys.path.insert(0, ROOT)
        from src import db as _db
        conn = _db.init_db(_db.connect(DB))
        conn.execute("INSERT OR REPLACE INTO source_runs (source, last_run, "
                     "run_id) VALUES (?,?,?)",
                     (source, datetime.date.today().isoformat(),
                      os.environ.get("GITHUB_RUN_ID")))
        conn.commit()
        conn.close()
    except Exception as exc:
        # A heartbeat must never be the reason a run cannot publish.
        print("  [warn] could not stamp the heartbeat: {0}".format(exc))


def _assets(tok=None):
    """[(name, id)] on the release, via gh or the API."""
    if tok:
        return [(a["name"], a["id"]) for a in (release(tok).get("assets") or [])]
    # The REST tag endpoint, NOT `gh release view --json assets`: that reports a
    # GraphQL node id ("RA_kwDO...") and PATCHing with it is a 404. The numeric
    # REST id is what the asset endpoints want (measured 2026-09-09).
    out = subprocess.run(["gh", "api", "/repos/{0}/releases/tags/{1}".format(REPO, TAG)],
                         capture_output=True, text=True)
    if out.returncode:
        return []
    try:
        payload = json.loads(out.stdout)
    except ValueError:
        return []
    return [(a["name"], a["id"]) for a in (payload.get("assets") or [])]


def _rename_asset(name_from, name_to, tok=None):
    """Rename a release asset in place. No bytes move, so this is instant even at 141MB."""
    ident = next((i for n, i in _assets(tok) if n == name_from), None)
    if ident is None:
        return False
    if tok:
        _api("/repos/{0}/releases/assets/{1}".format(REPO, ident), tok,
             data=json.dumps({"name": name_to}).encode("utf-8"), method="PATCH",
             headers={"Content-Type": "application/json"})
        return True
    out = subprocess.run(["gh", "api", "--method", "PATCH",
                          "/repos/{0}/releases/assets/{1}".format(REPO, ident),
                          "-f", "name=" + name_to], capture_output=True, text=True)
    if out.returncode:
        print("  [warn] could not rename {0} -> {1}: {2}".format(name_from, name_to, out.stderr.strip()[:120]))
        return False
    return True


def _delete_asset(name, tok=None):
    ident = next((i for n, i in _assets(tok) if n == name), None)
    if ident is None:
        return
    if tok:
        _api("/repos/{0}/releases/assets/{1}".format(REPO, ident), tok, method="DELETE")
    else:
        subprocess.run(["gh", "api", "--method", "DELETE",
                        "/repos/{0}/releases/assets/{1}".format(REPO, ident)],
                       capture_output=True, text=True)



def swap_in_asset(upload, api_tok=None, log=print):
    """Publish a new store without ever leaving the release without one.

    `gh release upload --clobber` DELETES the published asset and then uploads.
    On 2026-09-09 the upload failed ("http2: request body larger than specified
    content length") and the release was left with NO asset, so every workflow
    died at "Fetch the store: no assets to download" and the only copies left
    were a corrupt local file and a two-week-old store in git history.

    So: rename the published copy aside (instant -- no bytes move), upload, and
    drop the old one only once the new one is there. A failed upload puts the
    name back, and the store is still published.
    """
    kept = _rename_asset(ASSET, PREV, api_tok)
    if kept:
        log("  kept the published store aside as {0} while this one uploads".format(PREV))
    try:
        upload()
    except Exception as exc:                                # noqa: BLE001
        log(str(exc))
        if kept:
            _delete_asset(ASSET, api_tok)                   # drop a partial upload, if any
            if _rename_asset(PREV, ASSET, api_tok):
                log("  RESTORED the previously published store; the release is intact.")
            else:
                log("  COULD NOT RESTORE: the store is present as {0}. Rename it back to "
                    "{1} in the release before any workflow runs.".format(PREV, ASSET))
        return False
    if kept:
        _delete_asset(PREV, api_tok)
    return True


def push():
    if not os.path.exists(DB):
        print("no store to publish at {0}".format(DB))
        return 1
    if not check_lineage():
        return 1
    ok, counts = check_counts(accept_loss="--accept-loss" in sys.argv)
    if not ok:
        return 1
    stamp_heartbeat()          # inside the bytes, before the sha is taken
    tok = token()
    digest, size = sha256(DB), os.path.getsize(DB)
    if not have_gh() and not tok:
        print("CANNOT PUSH: no gh and no github_token in config/secrets.yaml.")
        return 1
    if have_gh():
        out = subprocess.run(
            ["gh", "release", "create", TAG, "--repo", REPO, "--prerelease",
             "--title", "Store state", "--notes",
             "Published by the weekly workflows. Derived state, not source."],
            capture_output=True, text=True)
        if out.returncode and "already exists" not in (out.stderr or ""):
            print("gh release create: {0}".format(out.stderr.strip()))

    api_tok = tok if not have_gh() else None

    def _upload():
        if have_gh():
            out = subprocess.run(
                ["gh", "release", "upload", TAG, DB + "#" + ASSET, "--repo", REPO],
                capture_output=True, text=True)
            if out.returncode:
                raise RuntimeError("gh upload failed: " + out.stderr.strip())
        else:
            rel = release(tok)
            with open(DB, "rb") as handle:
                _api(rel["upload_url"].split("{")[0] + "?name=" + ASSET, tok,
                     data=handle.read(), method="POST",
                     headers={"Content-Type": "application/octet-stream"})

    if not swap_in_asset(_upload, api_tok):
        return 1

    with open(SIDECAR, "w", encoding="utf-8") as handle:
        json.dump({"asset": "{0} release {1}".format(REPO, TAG),
                   "bytes": size, "sha256": digest,
                   # Per-table row counts, so the next push can tell a rebuild
                   # that came back missing a table (compare_counts).
                   "tables": counts,
                   "published_at": os.environ.get("GITHUB_RUN_ID")
                   and "run " + os.environ["GITHUB_RUN_ID"] or "local",
                   # When, in UTC, so tools/merge_sidecar.py can resolve a
                   # conflicting pointer when the release digest cannot be
                   # reached: a later publish is by construction the
                   # current asset, because check_lineage refuses any other.
                   "published_utc": datetime.datetime.utcnow().strftime(
                       "%Y-%m-%dT%H:%M:%SZ"),
                   "note": ("Derived state; the bytes live as a release "
                            "asset. See tools/db_state.py.")},
                  handle, indent=2, sort_keys=True)
        handle.write("\n")
    with open(PULLED, "a", encoding="utf-8") as handle:
        handle.write(digest + "\n")   # what we just published is now ours
    print("store published ({0:.1f} MB, sha {1}); sidecar written -- COMMIT "
          "IT so the repo records this state.".format(size / 1e6,
                                                      digest[:12]))
    return 0


def main():
    if "--pull" in sys.argv:
        return pull()
    if "--push" in sys.argv:
        return push()
    if "--check" in sys.argv:
        ok, _counts = check_counts(accept_loss=False)
        return 0 if ok else 1
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
