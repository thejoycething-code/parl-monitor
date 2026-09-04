"""The store is a build ARTIFACT, not source: fetch and publish it.

    python3 tools/db_state.py --pull     # before work
    python3 tools/db_state.py --push     # after work

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


def pull():
    tok = token()
    if have_gh():
        cmd = ["gh", "release", "download", TAG, "--repo", REPO,
               "--pattern", ASSET, "--output", DB, "--clobber"]
        out = subprocess.run(cmd, capture_output=True, text=True)
        if out.returncode:
            if "release not found" in (out.stderr or "").lower():
                return _no_asset_yet()
            print("gh download failed: {0}".format(out.stderr.strip()))
            return 1
    elif tok:
        rel = release(tok)
        asset = next((a for a in rel.get("assets") or []
                      if a["name"] == ASSET), None)
        if not asset:
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


def push():
    if not os.path.exists(DB):
        print("no store to publish at {0}".format(DB))
        return 1
    if not check_lineage():
        return 1
    stamp_heartbeat()          # inside the bytes, before the sha is taken
    tok = token()
    digest, size = sha256(DB), os.path.getsize(DB)
    if have_gh():
        out = subprocess.run(
            ["gh", "release", "create", TAG, "--repo", REPO, "--prerelease",
             "--title", "Store state", "--notes",
             "Published by the weekly workflows. Derived state, not source."],
            capture_output=True, text=True)
        if out.returncode and "already exists" not in (out.stderr or ""):
            print("gh release create: {0}".format(out.stderr.strip()))
        out = subprocess.run(
            ["gh", "release", "upload", TAG, DB + "#" + ASSET, "--repo", REPO,
             "--clobber"], capture_output=True, text=True)
        if out.returncode:
            print("gh upload failed: {0}".format(out.stderr.strip()))
            return 1
    elif tok:
        rel = release(tok)
        for a in rel.get("assets") or []:
            if a["name"] == ASSET:
                _api("/repos/{0}/releases/assets/{1}".format(REPO, a["id"]),
                     tok, method="DELETE")
        with open(DB, "rb") as handle:
            _api(rel["upload_url"].split("{")[0] + "?name=" + ASSET, tok,
                 data=handle.read(), method="POST",
                 headers={"Content-Type": "application/octet-stream"})
    else:
        print("CANNOT PUSH: no gh and no github_token in config/secrets.yaml.")
        return 1

    with open(SIDECAR, "w", encoding="utf-8") as handle:
        json.dump({"asset": "{0} release {1}".format(REPO, TAG),
                   "bytes": size, "sha256": digest,
                   "published_at": os.environ.get("GITHUB_RUN_ID")
                   and "run " + os.environ["GITHUB_RUN_ID"] or "local",
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
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
