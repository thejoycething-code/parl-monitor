"""A debate pack's deliverables on Google Drive (Christopher, 12 Sept 2026: "files
should go to Drive and not live on Slack. Create a new root folder for these").

The service account's only foothold is the Automated Briefs Shared Drive, so the
root lives there: one folder "Debate footage" at the top of that drive, one
subfolder per pack ("2026-09-11 Terminally Ill Adults (End of Life) Bill"), and
inside it the reel, the full-speech clips with their .srt files, and the pack's
report, selection and cut logs. Uploads are resumable (a 260 MB clip in 8 MB
chunks) and idempotent: a file already in the folder with the same name and size
is left alone. The folder link goes into pack.json and from there into the canvas
and the DM, so Slack carries a link and never the bytes.
"""

import json
import os
import sys
import urllib.parse
import urllib.request

ROOT_NAME = "Debate footage"
CHUNK = 8 * 1024 * 1024
DELIVERABLES = ("report.md", "social.md", "selection.md", "social-cut.md", "speeches-cut.md", "sequence.md", "roundup.md")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))


def _token():
    import publish_briefs_to_drive as pbd
    token, why = pbd.load_credentials()
    if not token:
        raise SystemExit("Drive: " + why)
    return token, pbd.FOLDER_ID, pbd.api


def find_or_create_folder(api, token, parent_id, name, drive_id):
    q = urllib.parse.urlencode({
        "q": "name = '%s' and '%s' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false" % (name.replace("'", "\\'"), parent_id),
        "corpora": "drive", "driveId": drive_id, "includeItemsFromAllDrives": "true", "supportsAllDrives": "true",
        "fields": "files(id,name)"})
    got = api(token, "https://www.googleapis.com/drive/v3/files?" + q)
    if got.get("files"):
        return got["files"][0]["id"], False
    made = api(token, "https://www.googleapis.com/drive/v3/files?supportsAllDrives=true",
               {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]})
    return made["id"], True


def existing_files(api, token, folder_id, drive_id):
    q = urllib.parse.urlencode({"q": "'%s' in parents and trashed = false" % folder_id, "corpora": "drive", "driveId": drive_id,
                                "includeItemsFromAllDrives": "true", "supportsAllDrives": "true", "fields": "files(id,name,size)", "pageSize": "200"})
    return {f["name"]: f for f in api(token, "https://www.googleapis.com/drive/v3/files?" + q).get("files", [])}


def upload_resumable(token, folder_id, path, name=None, opener=None, log=print):
    """Resumable upload in CHUNK-sized PUTs. Returns the file id."""
    opener = opener or urllib.request.urlopen
    name = name or os.path.basename(path)
    size = os.path.getsize(path)
    mime = "video/mp4" if path.endswith(".mp4") else "text/plain"
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&supportsAllDrives=true",
        data=json.dumps({"name": name, "parents": [folder_id]}).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": mime, "X-Upload-Content-Length": str(size)})
    with opener(req, timeout=60) as r:
        session = r.headers.get("Location")
    sent = 0
    file_id = None
    with open(path, "rb") as fh:
        while sent < size:
            blob = fh.read(CHUNK)
            end = sent + len(blob) - 1
            put = urllib.request.Request(session, data=blob, method="PUT",
                                         headers={"Content-Length": str(len(blob)), "Content-Range": "bytes %d-%d/%d" % (sent, end, size)})
            try:
                with opener(put, timeout=600) as r:
                    body = r.read().decode("utf-8", "replace")
                    if body.strip():
                        file_id = json.loads(body).get("id")
            except urllib.error.HTTPError as exc:
                if exc.code not in (308,):
                    raise
            sent = end + 1
    return file_id


def deliverables(pack_dir):
    """[(path, drive name)] for everything worth putting on Drive."""
    out = []
    final = os.path.join(pack_dir, "clips", "final")
    if os.path.isdir(final):
        for f in sorted(os.listdir(final)):
            if f.endswith((".mp4", ".srt", ".jpg")) and not f.endswith("-clean.mp4"):
                out.append((os.path.join(final, f), f))
    for f in DELIVERABLES:
        p = os.path.join(pack_dir, f)
        if os.path.exists(p):
            out.append((p, f))
    return out


def publish(pack_dir, log=print, dry_run=False, api=None, token=None, drive_id=None, opener=None):
    state = json.load(open(os.path.join(pack_dir, "pack.json")))
    if api is None:
        token, drive_id, api = _token()
    root_id, made = find_or_create_folder(api, token, drive_id, ROOT_NAME, drive_id)
    if made:
        log("  created the root folder '%s' in the shared drive" % ROOT_NAME)
    sub = "%s %s" % (state.get("date"), state.get("title"))
    folder_id, made = find_or_create_folder(api, token, root_id, sub, drive_id)
    url = "https://drive.google.com/drive/folders/" + folder_id
    have = existing_files(api, token, folder_id, drive_id)
    done = []
    for path, name in deliverables(pack_dir):
        size = os.path.getsize(path)
        if name in have and int(have[name].get("size") or -1) == size:
            done.append({"name": name, "id": have[name]["id"], "bytes": size, "skipped": True}); continue
        if dry_run:
            log("  would upload %-55s %6.1f MB" % (name, size / 1e6)); continue
        fid = upload_resumable(token, folder_id, path, name, opener=opener, log=log)
        log("  uploaded %-55s %6.1f MB" % (name, size / 1e6))
        done.append({"name": name, "id": fid, "bytes": size})
    if not dry_run:
        state["drive"] = {"folder_id": folder_id, "url": url, "root": ROOT_NAME, "files": done}
        json.dump(state, open(os.path.join(pack_dir, "pack.json"), "w"), indent=1)
    return url, done
