"""The raw archive is a build ARTIFACT, not source: fetch and publish it.

    python3 tools/raw_state.py --pull     # before work
    python3 tools/raw_state.py --push     # after work

Why. data/raw -- every API payload the collectors ever fetched, gzipped,
one folder per day -- was tracked in git so provenance was durable. By
2026-09-07 it was 287MB in 11,936 files across 31 folders and growing
every week, the same shape that forced the store out of the repo at 88MB
against GitHub's 100MB hard push limit. It is derived state, re-fetchable
in principle and reproducible from our own copy in practice, so it now
lives as GitHub Release assets (Christopher, 2026-09-07: "do 3").

Shape. One rolling release, `raw-archive`, holding one uncompressed tar per
day folder (`raw-2026-09-06.tar`; the files inside are already gzipped).
A day folder is the unit because it is what a run touches: a Sunday pull
adds a few MB to today's folder and nothing else, so a push uploads that
one tar rather than 287MB, and a pull downloads only the folders whose
content has changed since the working copy last matched.

Provenance is NOT lost. Every push writes data/raw.json -- per folder: the
sha256 of its content, file count, bytes, and the run and time that
published it -- and THAT is committed. A pull verifies each folder against
the sidecar and refuses a mismatch.

Two runs, one day. The weeklies serialise behind one concurrency group,
but a laptop can push while a workflow is queued, and both archive into
today's folder. So a push checks the sidecar on origin/main per folder:
if origin holds a digest this copy has never seen, the folder MOVED under
us, and instead of refusing (the store's rule) the push MERGES -- it
downloads origin's tar, unpacks it beneath the local files (never
overwriting one), and publishes the union. Raw payloads are write-once by
slug, so the union is always the right answer; nothing here needs a
--force.

Auth. As tools/db_state.py: `gh` on Actions and wherever it is installed,
else the REST API with `github_token` from config/secrets.yaml.
"""

from __future__ import annotations

import datetime
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
SIDECAR = os.path.join(ROOT, "data", "raw.json")
PULLED = os.path.join(ROOT, "data", ".raw-pulled")      # local: {folder: [digests held]}
REPO = "thejoycething-code/parl-monitor"
TAG = "raw-archive"
API = "https://api.github.com"


def asset_name(folder):
    return "raw-{0}.tar".format(folder)


def folder_digest(path):
    """sha256 over (relative path, file sha256) pairs, sorted: the content,
    not the tar bytes, so two tars of the same folder agree."""
    h = hashlib.sha256()
    n = size = 0
    for rel in sorted(_files(path)):
        fh = hashlib.sha256()
        full = os.path.join(path, rel)
        with open(full, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                fh.update(chunk)
        h.update(rel.encode("utf-8") + b"\0" + fh.hexdigest().encode() + b"\n")
        n += 1
        size += os.path.getsize(full)
    return h.hexdigest(), n, size


def _files(path):
    for root, _dirs, files in os.walk(path):
        for f in files:
            if f == ".DS_Store":
                continue
            yield os.path.relpath(os.path.join(root, f), path)


def local_folders(raw=RAW):
    if not os.path.isdir(raw):
        return []
    return sorted(d for d in os.listdir(raw)
                  if os.path.isdir(os.path.join(raw, d)) and not d.startswith("."))


def make_tar(folder_path, out_path):
    """Deterministic, uncompressed: sorted members, fixed mtime/owner."""
    with tarfile.open(out_path, "w") as tar:
        for rel in sorted(_files(folder_path)):
            full = os.path.join(folder_path, rel)
            info = tar.gettarinfo(full, arcname=rel)
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            with open(full, "rb") as handle:
                tar.addfile(info, handle)


def extract_union(tar_path, folder_path):
    """Unpack beneath the folder WITHOUT overwriting any local file: the
    merge for two runs that archived into the same day. Rejects members
    that would escape the folder."""
    os.makedirs(folder_path, exist_ok=True)
    added = 0
    with tarfile.open(tar_path, "r") as tar:
        for m in tar.getmembers():
            if not m.isfile():
                continue
            dest = os.path.normpath(os.path.join(folder_path, m.name))
            if not dest.startswith(os.path.abspath(folder_path) + os.sep) and dest != os.path.abspath(folder_path):
                raise ValueError("tar member escapes the folder: {0}".format(m.name))
            if os.path.exists(dest):
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            src = tar.extractfile(m)
            with open(dest, "wb") as handle:
                shutil.copyfileobj(src, handle)
            added += 1
    return added


# -- sidecar and lineage -------------------------------------------------------

def load_sidecar(path=SIDECAR):
    if not os.path.exists(path):
        return {"folders": {}}
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle) or {}
    data.setdefault("folders", {})
    return data


def write_sidecar(data, path=SIDECAR):
    data["note"] = ("Derived state; the bytes live as release assets, one tar per "
                    "day folder. See tools/raw_state.py.")
    data["release"] = "{0} release {1}".format(REPO, TAG)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _held():
    if not os.path.exists(PULLED):
        return {}
    try:
        with open(PULLED, encoding="utf-8") as handle:
            return json.load(handle) or {}
    except ValueError:
        return {}


def _hold(folder, digest):
    held = _held()
    held.setdefault(folder, [])
    if digest not in held[folder]:
        held[folder].append(digest)
    with open(PULLED, "w", encoding="utf-8") as handle:
        json.dump(held, handle)


def origin_sidecar():
    """data/raw.json as origin/main has it, or None if git cannot say."""
    try:
        subprocess.run(["git", "fetch", "--quiet", "origin", "main"], cwd=ROOT,
                       capture_output=True, timeout=120)
        out = subprocess.run(["git", "show", "origin/main:data/raw.json"], cwd=ROOT,
                             capture_output=True, text=True, timeout=60)
        if out.returncode:
            return None
        return (json.loads(out.stdout) or {}).get("folders") or {}
    except Exception:
        return None


def install_merge_driver():
    try:
        subprocess.run(["git", "config", "--local", "merge.raw-sidecar.name",
                        "per-folder union of the raw archive pointer"], cwd=ROOT,
                       capture_output=True, timeout=30)
        subprocess.run(["git", "config", "--local", "merge.raw-sidecar.driver",
                        "python3 tools/merge_raw_sidecar.py %O %A %B"], cwd=ROOT,
                       capture_output=True, timeout=30)
    except Exception as exc:
        print("  [warn] could not install the raw sidecar merge driver: {0}".format(exc))


# -- transport ------------------------------------------------------------------

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
    req = urllib.request.Request(path if path.startswith("http") else API + path,
                                 data=data, method=method)
    req.add_header("Authorization", "Bearer " + tok)
    req.add_header("Accept", "application/vnd.github+json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=900) as resp:
        return resp.read()


def _release(tok):
    try:
        return json.loads(_api("/repos/{0}/releases/tags/{1}".format(REPO, TAG), tok))
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    body = json.dumps({"tag_name": TAG, "name": "Raw archive",
                       "body": "The collectors' raw payloads, one tar per day folder. "
                               "Derived state, not source: see tools/raw_state.py.",
                       "prerelease": True}).encode()
    return json.loads(_api("/repos/{0}/releases".format(REPO), tok, data=body, method="POST"))


def ensure_release():
    if have_gh():
        out = subprocess.run(["gh", "release", "create", TAG, "--repo", REPO, "--prerelease",
                              "--title", "Raw archive", "--notes",
                              "The collectors' raw payloads, one tar per day folder. Derived state."],
                             capture_output=True, text=True)
        if out.returncode and "already exists" not in (out.stderr or ""):
            print("gh release create: {0}".format(out.stderr.strip()))
        return True
    tok = token()
    if tok:
        _release(tok)
        return True
    return False


def download_asset(folder, dest):
    """-> True if the tar landed at dest, False if there is no such asset."""
    name = asset_name(folder)
    if have_gh():
        out = subprocess.run(["gh", "release", "download", TAG, "--repo", REPO, "--pattern", name,
                              "--output", dest, "--clobber"], capture_output=True, text=True)
        if out.returncode:
            err = (out.stderr or "").lower()
            if "no assets match" in err or "release not found" in err or "not found" in err:
                return False
            raise RuntimeError("gh download failed for {0}: {1}".format(name, out.stderr.strip()))
        return True
    tok = token()
    if not tok:
        raise RuntimeError("no gh and no github_token in config/secrets.yaml")
    rel = _release(tok)
    asset = next((a for a in rel.get("assets") or [] if a["name"] == name), None)
    if not asset:
        return False
    blob = _api(asset["url"], tok, headers={"Accept": "application/octet-stream"})
    with open(dest, "wb") as handle:
        handle.write(blob)
    return True


def upload_asset(folder, tar_path):
    name = asset_name(folder)
    if have_gh():
        out = subprocess.run(["gh", "release", "upload", TAG, tar_path + "#" + name, "--repo", REPO,
                              "--clobber"], capture_output=True, text=True)
        if out.returncode:
            raise RuntimeError("gh upload failed for {0}: {1}".format(name, out.stderr.strip()))
        return
    tok = token()
    rel = _release(tok)
    for a in rel.get("assets") or []:
        if a["name"] == name:
            _api("/repos/{0}/releases/assets/{1}".format(REPO, a["id"]), tok, method="DELETE")
    with open(tar_path, "rb") as handle:
        _api(rel["upload_url"].split("{")[0] + "?name=" + name, tok, data=handle.read(),
             method="POST", headers={"Content-Type": "application/octet-stream"})


# -- pull / push ------------------------------------------------------------------

def pull(log=print):
    install_merge_driver()
    side = load_sidecar()["folders"]
    if not side:
        log("no published raw archive yet ({0} local folder(s)); this run's push publishes "
            "the first assets.".format(len(local_folders())))
        return 0
    if not have_gh() and not token():
        log("CANNOT PULL: no gh and no github_token in config/secrets.yaml. The working copy "
            "of data/raw is left as it is -- it may be STALE.")
        return 1
    os.makedirs(RAW, exist_ok=True)
    fetched = kept = 0
    tmp = tempfile.mkdtemp(prefix="raw-pull-")
    try:
        for folder, meta in sorted(side.items()):
            path = os.path.join(RAW, folder)
            if os.path.isdir(path) and folder_digest(path)[0] == meta["sha256"]:
                kept += 1
                _hold(folder, meta["sha256"])
                continue
            dest = os.path.join(tmp, asset_name(folder))
            if not download_asset(folder, dest):
                log("  {0}: sidecar names it but the release has no asset -- left as is".format(folder))
                continue
            # The published tar is the union of everything anyone archived;
            # local files that are not in it (this run's own new payloads,
            # or a laptop's) stay, because nothing here deletes.
            extract_union(dest, path)
            got = folder_digest(path)[0]
            if got != meta["sha256"] and set(_files(path)) == set(_tar_names(dest)):
                log("SHA MISMATCH on {0}: sidecar {1}, asset {2}. Refusing to trust it."
                    .format(folder, meta["sha256"][:12], got[:12]))
                return 1
            _hold(folder, meta["sha256"])
            fetched += 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    log("raw archive pulled: {0} folder(s) fetched, {1} already current, {2} local folder(s)."
        .format(fetched, kept, len(local_folders())))
    return 0


def _tar_names(tar_path):
    with tarfile.open(tar_path, "r") as tar:
        return [m.name for m in tar.getmembers() if m.isfile()]


def push(log=print):
    folders = local_folders()
    if not folders:
        log("no raw folders to publish under {0}".format(RAW))
        return 0
    if not ensure_release():
        log("CANNOT PUSH: no gh and no github_token in config/secrets.yaml.")
        return 1
    side = load_sidecar()
    theirs = origin_sidecar()
    if theirs is None:
        log("  [warn] could not read origin/main's raw sidecar; publishing without the "
            "moved-under-you check.")
        theirs = {}
    held = _held()
    published = unchanged = merged = 0
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    run = os.environ.get("GITHUB_RUN_ID") and "run " + os.environ["GITHUB_RUN_ID"] or "local"
    tmp = tempfile.mkdtemp(prefix="raw-push-")
    try:
        for folder in folders:
            path = os.path.join(RAW, folder)
            digest, n, size = folder_digest(path)
            if n == 0:
                continue
            current = (side["folders"].get(folder) or {}).get("sha256")
            remote = (theirs.get(folder) or {}).get("sha256")
            if remote and remote != current and remote not in held.get(folder, []):
                # The folder moved under us: someone published it since we
                # pulled. Merge their tar beneath our files, then publish the
                # union -- never their loss, never ours.
                dest = os.path.join(tmp, asset_name(folder))
                if download_asset(folder, dest):
                    added = extract_union(dest, path)
                    log("  {0}: published by another run since our pull -- merged {1} of their "
                        "file(s) in".format(folder, added))
                    merged += 1
                    digest, n, size = folder_digest(path)
            if digest == current and digest == (remote or current):
                unchanged += 1
                continue
            tar_path = os.path.join(tmp, asset_name(folder))
            make_tar(path, tar_path)
            upload_asset(folder, tar_path)
            os.remove(tar_path)
            side["folders"][folder] = {"sha256": digest, "files": n, "bytes": size,
                                       "published_utc": now, "published_by": run}
            _hold(folder, digest)
            published += 1
            log("  {0}: published ({1} files, {2:.1f} MB)".format(folder, n, size / 1e6))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    write_sidecar(side)
    log("raw archive published: {0} folder(s) uploaded, {1} unchanged, {2} merged; sidecar "
        "written -- COMMIT IT so the repo records this state.".format(published, unchanged, merged))
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
