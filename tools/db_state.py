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

Compressed since 11 October 2026. The store passed 1.7GB (from 1.0GB two
days earlier) against GitHub's 2 GiB limit PER RELEASE ASSET, so a push now
publishes it gzipped as parl-monitor.db.gz (stdlib gzip, level 4: a
quarter of the size, about 15 seconds at 1.76GB on Apple silicon). The sidecar still records
the UNCOMPRESSED sha256 and size, which is what a pull verifies after
decompressing, plus gz_sha256 and gz_bytes for the asset itself. A pull
takes the form the sidecar names and falls back to the other: the legacy
raw parl-monitor.db asset is read while it exists, and a compressed push
deletes it only once its own upload is verified against GitHub's digest.
Past 1.6GB uncompressed or 1.5GB compressed every push (and the daily
health summary) warns: the next step is splitting the store.

Auth. On Actions, `gh` is present and GITHUB_TOKEN authenticates it. Locally
`gh` is usually absent, so the REST API is used with `github_token` from
config/secrets.yaml -- a PAT with contents:write on this repo. Without one a
pull cannot reach a private repo's assets, and the tool says so plainly
rather than leaving a stale store in place.
"""

from __future__ import annotations

import datetime
import gzip
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
ASSET = "parl-monitor.db"   # the legacy, uncompressed asset (read during the switch)
PREV = ASSET + ".prev"    # the copy kept aside while a new one uploads
GZ_ASSET = ASSET + ".gz"  # what a push publishes since 11 October 2026
GZ_PREV = GZ_ASSET + ".prev"
STORE_ASSETS = (GZ_ASSET, ASSET)
API = "https://api.github.com"

# Level 4, measured on the laptop (11 October 2026). The real store of 9
# October (963MB): level 1 gives 3.6x in 6s, level 4 4.0x in 8s, level 6
# 4.3x in 17s. A generated 1.9GB store of high-entropy text (the worst
# case): level 1 2.5x in 14s, level 4 2.85x in 24s, level 6 2.9x in 103s.
# Level 4 keeps nearly all of level 6's saving at a quarter of its worst
# case; decompressing is about 2s a GB at any level.
GZ_LEVEL = 4
ASSET_LIMIT = 2 * 1024 ** 3          # GitHub's ceiling for one release asset
STORE_WARN_BYTES = 1_600_000_000     # uncompressed: time to plan the split
GZ_WARN_BYTES = 1_500_000_000        # compressed: the split is now urgent
CHUNK = 1 << 20


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


class _CountingWriter:
    """A file wrapper that hashes and counts what passes through it, so the
    compressed asset's sha and size come out of the same single pass."""

    def __init__(self, handle):
        self.handle, self.hash, self.bytes = handle, hashlib.sha256(), 0

    def write(self, data):
        self.hash.update(data)
        self.bytes += len(data)
        return self.handle.write(data)

    def flush(self):
        self.handle.flush()


def compress(src, dest, level=GZ_LEVEL):
    """gzip src into dest, streaming. -> (sha256, bytes) of the UNCOMPRESSED
    input and (gz_sha256, gz_bytes) of the output, all from one read."""
    raw, size = hashlib.sha256(), 0
    with open(src, "rb") as fin, open(dest, "wb") as fout:
        out = _CountingWriter(fout)
        # filename="" and mtime=0: the same store always compresses to the
        # same bytes, so its gz_sha256 means one thing.
        with gzip.GzipFile(filename="", mode="wb", fileobj=out,
                           compresslevel=level, mtime=0) as gz:
            for chunk in iter(lambda: fin.read(CHUNK), b""):
                raw.update(chunk)
                size += len(chunk)
                gz.write(chunk)
    return raw.hexdigest(), size, out.hash.hexdigest(), out.bytes


def decompress(src, dest):
    """gunzip src into dest, streaming. -> sha256 of what was written.
    Raises OSError/EOFError on a corrupt or truncated file."""
    h = hashlib.sha256()
    with gzip.open(src, "rb") as gz, open(dest, "wb") as fout:
        for chunk in iter(lambda: gz.read(CHUNK), b""):
            h.update(chunk)
            fout.write(chunk)
    return h.hexdigest()


def gunzip_sha(src):
    """sha256 of src's decompressed bytes, written nowhere."""
    h = hashlib.sha256()
    with gzip.open(src, "rb") as gz:
        for chunk in iter(lambda: gz.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def size_warnings(size, gz_size=None):
    """Lines to print when the store nears the per-asset limit. The split
    (several assets) is the next step; these raise it while there is time."""
    out = []
    if size and size >= STORE_WARN_BYTES:
        out.append("STORE SIZE: {0:.2f} GB uncompressed (warning at {1:.1f} GB). "
                   "Plan splitting the store before the compressed asset nears "
                   "GitHub's 2 GiB per-asset limit.".format(size / 1e9, STORE_WARN_BYTES / 1e9))
    if gz_size and gz_size >= GZ_WARN_BYTES:
        out.append("STORE SIZE: the compressed asset is {0:.2f} GB (warning at {1:.1f} GB; "
                   "the limit is {2:.2f} GB). Split the store now.".format(
                       gz_size / 1e9, GZ_WARN_BYTES / 1e9, ASSET_LIMIT / 1e9))
    return out


def warn(line, log=print):
    """A warning that also shows as an annotation on a GitHub run's summary."""
    log(("::warning::" if os.environ.get("GITHUB_ACTIONS") == "true" else "  [warn] ") + line)


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


def _request(path, tok, data=None, headers=None, method=None):
    req = urllib.request.Request(
        path if path.startswith("http") else API + path, data=data,
        method=method)
    req.add_header("Authorization", "Bearer " + tok)
    req.add_header("Accept", "application/vnd.github+json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    return req


def _api(path, tok, data=None, headers=None, method=None):
    # `data` may be an open file: with a Content-Length header urllib sends
    # it in blocks, so a store never has to fit in memory to be uploaded.
    with urllib.request.urlopen(_request(path, tok, data, headers, method),
                                timeout=600) as resp:
        return resp.read()


def _api_download(url, tok, dest):
    """Stream a release asset to dest (the token path; gh streams its own)."""
    req = _request(url, tok, headers={"Accept": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=600) as resp, open(dest, "wb") as out:
        shutil.copyfileobj(resp, out, CHUNK)


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


def prefers_gz(sidecar=None):
    """Which form the last publish wrote, from the pointer of record.

    A sidecar with gz_sha256 was written by a compressed push; one without
    was written by a raw push (before 11 October 2026, or by a run still on
    the old code during the switch), so its raw asset is the one it names.
    No sidecar at all: the current form.
    """
    try:
        with open(sidecar or SIDECAR, encoding="utf-8") as handle:
            side = json.load(handle) or {}
    except (OSError, ValueError):
        return True
    return bool(side.get("gz_sha256")) or not side.get("sha256")


def plan_pull(names, prefer_gz=True):
    """-> (asset to download, name to restore it to) from the release's asset
    names. The preferred form first, the other as the fallback; failing both,
    a .prev copy a push left aside part-way (2026-09-09), which the caller
    renames back. (None, None) when the release holds no store at all."""
    order = (GZ_ASSET, ASSET) if prefer_gz else (ASSET, GZ_ASSET)
    for name in order:
        if name in names:
            return name, None
    for name in order:
        if name + ".prev" in names:
            return name + ".prev", name
    return None, None


def pull():
    install_merge_driver()
    tok = token()
    # The download lands BESIDE the working store and replaces it only once
    # verified. 14 Sept 2026: a refused download had already overwritten the
    # working copy, and with it a live re-score that then had to be paid for
    # again. "Nothing was overwritten except the download itself" was the
    # working store.
    got_path = DB + ".download"
    if have_gh():
        # The REST tag endpoint lists the assets, so the form to fetch is
        # chosen before anything downloads.
        out = subprocess.run(["gh", "api", "/repos/{0}/releases/tags/{1}".format(REPO, TAG)],
                             capture_output=True, text=True)
        if out.returncode:
            err = (out.stderr or "").strip()
            if "not found" in err.lower() or "404" in err:
                return _no_asset_yet()
            print("gh could not read the release: {0}".format(err))
            return 1
        try:
            assets = {a["name"]: a for a in json.loads(out.stdout).get("assets") or []}
        except ValueError:
            print("gh could not read the release: not JSON")
            return 1
    elif tok:
        assets = {a["name"]: a for a in release(tok).get("assets") or []}
    else:
        print("CANNOT PULL: no gh and no github_token in config/secrets.yaml.\n"
              "  A private repo's release assets need auth. Add a PAT with\n"
              "  contents:write as `github_token:` in config/secrets.yaml, or\n"
              "  install gh. The working copy is left untouched -- it may be "
              "STALE.")
        return 1

    name, restore = plan_pull(assets, prefers_gz())
    if name is None:
        if have_gh():
            print("gh download failed: no store asset ({0} or {1}) on the release".format(
                GZ_ASSET, ASSET))
            return 1
        return _no_asset_yet()
    if restore:
        # A push that failed between renaming the old asset aside and
        # uploading the new one leaves only PREV. Recover from it rather
        # than failing every workflow: this is exactly the state that
        # broke the day-sweep run on 2026-09-09.
        print("  [warn] no {0} on the release, but {1} is there: a push failed "
              "part-way. Recovering from it.".format(restore, name))
    elif name == ASSET and GZ_ASSET not in assets:
        print("  no {0} on the release yet: taking the uncompressed {1}".format(GZ_ASSET, ASSET))

    compressed = name.startswith(GZ_ASSET)
    dest = got_path + ".gz" if compressed else got_path
    if have_gh():
        out = subprocess.run(
            ["gh", "release", "download", TAG, "--repo", REPO,
             "--pattern", name, "--output", dest, "--clobber"],
            capture_output=True, text=True)
        if out.returncode:
            print("gh download of {0} failed: {1}".format(name, out.stderr.strip()))
            return 1
        if restore:
            if _rename_asset(name, restore):
                print("  recovered: {0} is published again. The sidecar in the repo "
                      "may name a store that was never uploaded -- check it.".format(restore))
            else:
                print("  could not rename {0} back to {1}".format(name, restore))
                return 1
    else:
        _api_download(assets[name]["url"], tok, dest)

    if compressed:
        return install_compressed(dest, got_path)
    return install_download(got_path)


def install_compressed(gz_path, got_path, db=None, sidecar=None, pulled=None, log=print):
    """Decompress a downloaded .gz beside the working store, then verify and
    install it as install_download does. A corrupt or truncated file leaves
    the working store untouched."""
    gz_sha = sha256(gz_path)
    try:
        got = decompress(gz_path, got_path)
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        log("CORRUPT DOWNLOAD: {0} does not decompress ({1}).\n"
            "  The working copy is UNTOUCHED. Re-run; if it persists the release "
            "asset itself is damaged.".format(os.path.basename(gz_path), exc))
        return 1
    os.remove(gz_path)
    return install_download(got_path, db=db, sidecar=sidecar, pulled=pulled, log=log,
                            got_sha=got, also_held=(gz_sha,))


def install_download(got_path, db=None, sidecar=None, pulled=None, log=print,
                     got_sha=None, also_held=()):
    """Verify a downloaded store against the sidecar and, only then, make it the
    working store. A mismatch leaves the working store untouched and the
    download beside it for inspection. `also_held`: other shas this pull
    took (the compressed asset's), recorded first so the live-asset check
    knows the published bytes as ours."""
    db, sidecar, pulled = db or DB, sidecar or SIDECAR, pulled or PULLED
    if os.path.exists(sidecar):
        with open(sidecar, encoding="utf-8") as handle:
            want = json.load(handle)
        got = got_sha or sha256(got_path)
        if want.get("sha256") and want["sha256"] != got:
            log("SHA MISMATCH: sidecar says {0}, downloaded {1}.\n"
                "  Refusing to trust this store. The working copy is UNTOUCHED; the "
                "download is beside it as {2}. Re-run, and if it persists the release "
                "asset and the committed sidecar have diverged.".format(
                    want["sha256"][:12], got[:12], os.path.basename(got_path)))
            return 1
        os.replace(got_path, db)
        with open(pulled, "a", encoding="utf-8") as handle:
            # The store's own sha LAST: check_lineage reads the last line as
            # "this copy".
            for extra in also_held:
                handle.write(extra + "\n")
            handle.write(got + "\n")
        log("store pulled and verified ({0:.1f} MB, sha {1}).".format(
            os.path.getsize(db) / 1e6, got[:12]))
    else:
        os.replace(got_path, db)
        log("store pulled ({0:.1f} MB); no sidecar to verify against yet."
            .format(os.path.getsize(db) / 1e6))
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
    else:
        log("  table counts: {0} tables, none emptied since the last publish".format(len(now)))
    return True, now


def held_shas():
    """Every sha this working copy has held, pulled or published."""
    if not os.path.exists(PULLED):
        return []
    return [ln.strip() for ln in open(PULLED, encoding="utf-8") if ln.strip()]


def _release_assets():
    """[{name, digest}] on the release, or None if it cannot be read."""
    out = subprocess.run(["gh", "api", "/repos/{0}/releases/tags/{1}".format(REPO, TAG)],
                         capture_output=True, text=True)
    if out.returncode:
        return None
    try:
        return [{"name": a.get("name"), "digest": (a.get("digest") or "").replace("sha256:", ""),
                 "created_at": a.get("created_at")}
                for a in (json.loads(out.stdout).get("assets") or [])]
    except ValueError:
        return None


def live_store(assets):
    """The store asset a reader would call current: the NEWER of the
    compressed and the raw asset when both are there (by GitHub's created_at,
    which a rename keeps), else whichever exists, the compressed one first.
    Both exist only during the switch: a compressed push deletes the raw
    asset once its upload is verified, and a run still on the old code
    could upload a raw one after it."""
    found = [a for a in assets if a.get("name") in STORE_ASSETS]
    if not found:
        return None
    if len(found) > 1 and all(a.get("created_at") for a in found):
        return max(found, key=lambda a: a["created_at"])
    return sorted(found, key=lambda a: STORE_ASSETS.index(a["name"]))[0]


def live_asset_is_ours(held, assets=None):
    """The release itself, not just the pointer on main, must hold a store we have seen.

    TWO MACHINES, NO SHARED LOCK. The Mac Mini runner (tools/mini_run.sh)
    publishes the store while GitHub's writers still do, and they do not share
    the parl-monitor-state concurrency group. A push uploads the asset FIRST
    and commits the sidecar seconds later, so in that window origin/main's
    pointer still names the old store and check_lineage alone would let a
    second writer overwrite the first one's work. The asset's own digest has
    no such window. A PREV asset means a push is part-way through.
    """
    assets = _release_assets() if assets is None else assets
    if assets is None:
        print("  [warn] could not read the release, so the live asset is "
              "unchecked.")
        return True
    names = {a["name"]: a["digest"] for a in assets}
    for prev in (PREV, GZ_PREV):
        if prev in names:
            print("REFUSING TO PUBLISH: {0} is on the release, so another push "
                  "is part-way through (or failed part-way).\n  Fix: python3 "
                  "tools/db_state.py --pull, redo this run's work, push.".format(prev))
            return False
    # The compressed asset's digest is the gz sha, which a pull or push of
    # it records in .store-pulled beside the store's own sha.
    live = (live_store(assets) or {}).get("digest")
    if live and held and live not in held:
        print("THE STORE MOVED UNDER YOU. Refusing to publish.\n"
              "  the release holds {0}, never seen here: another run has "
              "uploaded it and has not committed its sidecar yet.\n"
              "  Fix: python3 tools/db_state.py --pull, redo this run's work "
              "on the current store, then push.".format(live[:12]))
        return False
    return True


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
        return live_asset_is_ours(held_shas())
    # EVERY sha this working copy has held, pulled or published -- not
    # just the last one. A push writes the new sha locally but the
    # sidecar reaches origin only when the commit lands, so comparing
    # against the single latest sha refused a perfectly ordinary
    # push-then-push-again. What matters is not whether origin differs,
    # but whether origin holds something WE HAVE NEVER SEEN: that is
    # someone else's work.
    held = held_shas()
    ours = held[-1] if held else None
    if theirs in held:
        return live_asset_is_ours(held)
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


def _asset_records(tok=None):
    """[{name, id, state, size}] on the release. `state` is GitHub's: "uploaded"
    for a finished asset, anything else for one still being written."""
    if tok:
        payload = release(tok)
    else:
        out = subprocess.run(["gh", "api", "/repos/{0}/releases/tags/{1}".format(REPO, TAG)],
                             capture_output=True, text=True)
        if out.returncode:
            return []
        try:
            payload = json.loads(out.stdout)
        except ValueError:
            return []
    return [{"name": a.get("name"), "id": a.get("id"), "state": a.get("state"), "size": a.get("size"),
             "digest": (a.get("digest") or "").replace("sha256:", "")}
            for a in (payload.get("assets") or [])]


def check_upload(name, gz_sha, gz_size, api_tok=None, log=print):
    """Is what the release now holds under `name` exactly what we uploaded?
    True: GitHub's own sha256 digest (or, where it gives none, the size)
    matches. False: it definitely does not. None: the release could not be
    read, so nothing is known either way."""
    rec = next((r for r in _asset_records(api_tok) if r["name"] == name), None)
    if rec is None:
        log("  [warn] could not read {0} back from the release to verify it".format(name))
        return None
    if rec.get("state") != "uploaded" or rec.get("size") != gz_size:
        log("UPLOAD DOES NOT MATCH: {0} is {1} bytes ({2}); we sent {3}.".format(
            name, rec.get("size"), rec.get("state"), gz_size))
        return False
    if rec.get("digest") and rec["digest"] != gz_sha:
        log("UPLOAD DOES NOT MATCH: GitHub's digest for {0} is {1}, ours {2}.".format(
            name, rec["digest"][:12], gz_sha[:12]))
        return False
    return True


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



def swap_in_asset(upload, api_tok=None, log=print, asset=ASSET, prev=PREV, verify=None):
    """Publish a new store without ever leaving the release without one.

    `gh release upload --clobber` DELETES the published asset and then uploads.
    On 2026-09-09 the upload failed ("http2: request body larger than specified
    content length") and the release was left with NO asset, so every workflow
    died at "Fetch the store: no assets to download" and the only copies left
    were a corrupt local file and a two-week-old store in git history.

    So: rename the published copy aside (instant -- no bytes move), upload, and
    drop the old one only once the new one is there. A failed upload puts the
    name back, and the store is still published.

    `asset`/`prev`: the names to swap (the compressed pair since 11 October
    2026). `verify`: called after a good upload; False (a definite mismatch
    with what we sent) takes the upload down and restores the old copy, as a
    failed upload does. Nobody else can hold the name between our upload and
    this check: GitHub refuses a second asset of the same name.
    """
    kept = _rename_asset(asset, prev, api_tok)
    if kept:
        log("  kept the published store aside as {0} while this one uploads".format(prev))
    try:
        upload()
    except Exception as exc:                                # noqa: BLE001
        log(str(exc))
        if kept:
            # 14 Sept 2026: a laptop push raced the Monday publish. The publish
            # uploaded its store while ours was in flight, ours got a 404, and
            # this path then DELETED the publish's fresh asset as "a partial
            # upload" and put the old copy back -- forty minutes of CI work
            # gone and the sidecar pointing at bytes that no longer existed.
            # A failed upload leaves no asset behind (GitHub creates it on
            # completion), so an ASSET that exists now is somebody else's
            # finished publish: leave it, and leave ours aside for a person.
            # So: try the restore FIRST (it fails on a name clash), and only
            # then look at what holds the name. A finished upload is a rival;
            # anything else is our own debris and can go.
            if _rename_asset(prev, asset, api_tok):
                log("  RESTORED the previously published store; the release is intact.")
                return False
            holder = [r for r in _asset_records(api_tok) if r["name"] == asset]
            if holder and holder[0].get("state") == "uploaded":
                log("  ANOTHER PUBLISH LANDED while this one was uploading: its store stands. "
                    "Ours is not published; the previous copy stays aside as {0}. "
                    "Pull, redo this run's work, push again.".format(prev))
                return False
            _delete_asset(asset, api_tok)                   # our partial upload
            if _rename_asset(prev, asset, api_tok):
                log("  RESTORED the previously published store; the release is intact.")
            else:
                log("  COULD NOT RESTORE: the store is present as {0}. Rename it back to "
                    "{1} in the release before any workflow runs.".format(prev, asset))
        return False
    if verify is not None and verify() is False:
        log("  taking the bad upload down")
        _delete_asset(asset, api_tok)
        if kept and not _rename_asset(prev, asset, api_tok):
            log("  COULD NOT RESTORE: the store is present as {0}. Rename it back to "
                "{1} in the release before any workflow runs.".format(prev, asset))
        elif kept:
            log("  RESTORED the previously published store; the release is intact.")
        return False
    if kept:
        _delete_asset(prev, api_tok)
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
    gz_path = DB + ".gz"
    try:
        return _publish(tok, counts, digest, size, gz_path)
    finally:
        if os.path.exists(gz_path):
            os.remove(gz_path)


def _publish(tok, counts, digest, size, gz_path):
    """Compress, check, upload, verify, retire the raw asset, write the sidecar."""
    import time
    started = time.time()
    raw_sha, raw_size, gz_digest, gz_size = compress(DB, gz_path)
    if (raw_sha, raw_size) != (digest, size):
        print("REFUSING TO PUBLISH: the store changed while it was being compressed "
              "(sha {0}, then {1}). Is another process writing it?".format(digest[:12], raw_sha[:12]))
        return 1
    # A gzip that does not give the store back would fail every pull, so it
    # is proved before it goes anywhere (about 4s at 1.7GB).
    if gunzip_sha(gz_path) != digest:
        print("REFUSING TO PUBLISH: the compressed copy does not decompress to the store.")
        return 1
    print("  compressed {0:.1f} MB to {1:.1f} MB ({2:.0f}%) in {3:.0f}s".format(
        size / 1e6, gz_size / 1e6, 100.0 * gz_size / size if size else 0, time.time() - started))
    for line in size_warnings(size, gz_size):
        warn(line)
    if gz_size >= ASSET_LIMIT:
        print("REFUSING TO PUBLISH: the compressed store is {0:.2f} GB, over GitHub's {1:.2f} GB "
              "per-asset limit; the upload would fail. The store must be split.".format(
                  gz_size / 1e9, ASSET_LIMIT / 1e9))
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
                ["gh", "release", "upload", TAG, gz_path + "#" + GZ_ASSET, "--repo", REPO],
                capture_output=True, text=True)
            if out.returncode:
                raise RuntimeError("gh upload failed: " + out.stderr.strip())
        else:
            rel = release(tok)
            with open(gz_path, "rb") as handle:
                _api(rel["upload_url"].split("{")[0] + "?name=" + GZ_ASSET, tok,
                     data=handle, method="POST",
                     headers={"Content-Type": "application/octet-stream",
                              "Content-Length": str(gz_size)})

    verified = []

    def _verify():
        verified.append(check_upload(GZ_ASSET, gz_digest, gz_size, api_tok))
        return verified[-1]

    if not swap_in_asset(_upload, api_tok, asset=GZ_ASSET, prev=GZ_PREV, verify=_verify):
        return 1

    # The switch: the raw asset now holds an older store. Delete it only once
    # the compressed one is verified as what we sent; unverified, it stays,
    # and the next verified push retires it.
    if any(n == ASSET for n, _i in _assets(api_tok)):
        if verified and verified[-1] is True:
            _delete_asset(ASSET, api_tok)
            print("  retired the uncompressed {0} asset: {1} is verified and current".format(
                ASSET, GZ_ASSET))
        else:
            print("  [warn] {0} not verified, so the old uncompressed {1} stays on the "
                  "release for now".format(GZ_ASSET, ASSET))

    with open(SIDECAR, "w", encoding="utf-8") as handle:
        json.dump({"asset": "{0} release {1}".format(REPO, TAG),
                   # The UNCOMPRESSED store: what a pull verifies after
                   # decompressing, and what check_lineage compares.
                   "bytes": size, "sha256": digest,
                   # The published asset itself (since 11 October 2026). Its
                   # presence also tells a pull the last publish was gzipped.
                   "asset_name": GZ_ASSET, "gz_bytes": gz_size, "gz_sha256": gz_digest,
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
                   "note": ("Derived state; the bytes live as a gzipped release "
                            "asset. See tools/db_state.py.")},
                  handle, indent=2, sort_keys=True)
        handle.write("\n")
    with open(PULLED, "a", encoding="utf-8") as handle:
        # What we just published is now ours: the asset's sha (the live-asset
        # check reads GitHub's digest of it), then the store's, last.
        handle.write(gz_digest + "\n" + digest + "\n")
    print("store published ({0:.1f} MB, {1:.1f} MB compressed, sha {2}); sidecar written -- "
          "COMMIT IT so the repo records this state.".format(size / 1e6, gz_size / 1e6,
                                                            digest[:12]))
    return 0


def main():
    if "--pull" in sys.argv:
        return pull()
    if "--push" in sys.argv:
        return push()
    if "--check" in sys.argv:
        ok, _counts = check_counts(accept_loss=False)
        if os.path.exists(DB):
            for line in size_warnings(os.path.getsize(DB)):
                warn(line)
        return 0 if ok else 1
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
