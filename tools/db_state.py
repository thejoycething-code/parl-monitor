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
        print("store pulled and verified ({0:.1f} MB, sha {1}).".format(
            os.path.getsize(DB) / 1e6, got[:12]))
    else:
        print("store pulled ({0:.1f} MB); no sidecar to verify against yet."
              .format(os.path.getsize(DB) / 1e6))
    return 0


def push():
    if not os.path.exists(DB):
        print("no store to publish at {0}".format(DB))
        return 1
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
