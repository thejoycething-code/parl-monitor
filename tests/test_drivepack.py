import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import drivepack  # noqa: E402

REAL_UPLOAD = drivepack.upload_resumable   # DrivePackTests stubs the module attribute


class FakeDrive(object):
    def __init__(self):
        self.calls, self.folders, self.files = [], {}, {}

    def api(self, token, url, payload=None, method=None):
        self.calls.append((url.split("?")[0], payload))
        if method == "PATCH" and payload == {"trashed": True}:
            fid = url.split("/files/")[1].split("?")[0]
            self.files = {n: f for n, f in self.files.items() if f["id"] != fid}
            self.binned = getattr(self, "binned", []) + [fid]
            return {"id": fid, "trashed": True}
        if "files?q=" in url or "files?" in url and payload is None:
            q = url.split("q=")[1].split("&")[0]
            import urllib.parse
            q = urllib.parse.unquote_plus(q)
            if "mimeType = 'application/vnd.google-apps.folder'" in q:
                name = q.split("name = '")[1].split("'")[0]
                fid = self.folders.get(name)
                return {"files": [{"id": fid, "name": name}] if fid else []}
            return {"files": list(self.files.values())}
        if payload and payload.get("mimeType") == "application/vnd.google-apps.folder":
            fid = "f-%d" % (len(self.folders) + 1); self.folders[payload["name"]] = fid
            return {"id": fid}
        return {}


class DrivePackTests(unittest.TestCase):
    def test_root_and_pack_folders_are_created_once_and_uploads_are_idempotent(self):
        tmp = tempfile.mkdtemp()
        json.dump({"date": "2026-09-11", "title": "A Bill"}, open(os.path.join(tmp, "pack.json"), "w"))
        os.makedirs(os.path.join(tmp, "clips", "final"))
        open(os.path.join(tmp, "clips", "final", "speech-01-x.mp4"), "wb").write(b"v" * 100)
        open(os.path.join(tmp, "clips", "final", "speech-01-x-clean.mp4"), "wb").write(b"v" * 100)   # never uploaded
        open(os.path.join(tmp, "report.md"), "w").write("r")
        fake = FakeDrive()
        uploaded = []
        drivepack.upload_resumable = lambda token, folder_id, path, name=None, opener=None, log=print: uploaded.append(name) or "id-" + name
        url, done = drivepack.publish(tmp, log=lambda *_a: None, api=fake.api, token="t", drive_id="D")
        self.assertEqual(fake.folders, {"Debate footage": "f-1", "2026-09-11 A Bill": "f-2"})
        self.assertEqual(url, "https://drive.google.com/drive/folders/f-2")
        self.assertEqual(uploaded, ["speech-01-x.mp4", "report.md"])
        self.assertEqual(json.load(open(os.path.join(tmp, "pack.json")))["drive"]["url"], url)
        # second run: folders found, files with the same size skipped
        fake.files = {"speech-01-x.mp4": {"id": "id-speech-01-x.mp4", "name": "speech-01-x.mp4", "size": "100"}}
        uploaded.clear()
        drivepack.publish(tmp, log=lambda *_a: None, api=fake.api, token="t", drive_id="D")
        self.assertEqual(fake.folders, {"Debate footage": "f-1", "2026-09-11 A Bill": "f-2"})
        self.assertEqual(uploaded, ["report.md"])

    def test_a_recut_replaces_its_clip_and_prune_bins_the_cutters_stale_ones_only(self):
        """12 Sept 2026: Bradley's merged clip kept its name at a new size, and her
        four other pre-merge clips left the pack; a hand-placed file stays."""
        tmp = tempfile.mkdtemp()
        json.dump({"date": "2026-09-11", "title": "A Bill"}, open(os.path.join(tmp, "pack.json"), "w"))
        os.makedirs(os.path.join(tmp, "clips", "final"))
        open(os.path.join(tmp, "clips", "final", "speech-02-b.mp4"), "wb").write(b"v" * 500)
        fake = FakeDrive()
        fake.folders = {"Debate footage": "f-1", "2026-09-11 A Bill": "f-2"}
        fake.files = {"speech-02-b.mp4": {"id": "old-02", "name": "speech-02-b.mp4", "size": "100"},
                      "speech-03-b.mp4": {"id": "old-03", "name": "speech-03-b.mp4", "size": "100"},
                      "notes-from-max.docx": {"id": "hand", "name": "notes-from-max.docx", "size": "7"}}
        uploaded = []
        drivepack.upload_resumable = lambda token, folder_id, path, name=None, opener=None, log=print: uploaded.append(name) or "id-" + name
        drivepack.publish(tmp, log=lambda *_a: None, api=fake.api, token="t", drive_id="D", prune=True)
        self.assertEqual(uploaded, ["speech-02-b.mp4"])
        self.assertEqual(sorted(fake.binned), ["old-02", "old-03"])
        self.assertIn("notes-from-max.docx", fake.files)
        # without prune the stale clip stays
        fake.files["speech-03-b.mp4"] = {"id": "old-03", "name": "speech-03-b.mp4", "size": "100"}; fake.binned = []
        drivepack.publish(tmp, log=lambda *_a: None, api=fake.api, token="t", drive_id="D")
        self.assertEqual(fake.binned, [])


if __name__ == "__main__":
    unittest.main()


class SessionOpenRetryTests(unittest.TestCase):
    """12 Sept 2026: the POST that opens a resumable session timed out on file 51
    of 59 and, sitting outside the chunk retry, killed the run. It retries now."""

    def test_session_open_survives_two_timeouts(self):
        import io
        import urllib.error

        class Resp(io.BytesIO):
            def __init__(self, body, headers):
                io.BytesIO.__init__(self, body); self.headers = headers
            def __enter__(self): return self
            def __exit__(self, *a): return False

        state = {"opens": 0}

        def opener(req, timeout=None):
            if req.get_method() == "POST":
                state["opens"] += 1
                if state["opens"] < 3:
                    raise urllib.error.URLError("Operation timed out")
                return Resp(b"", {"Location": "https://upload.example/session"})
            return Resp(json.dumps({"id": "file-1"}).encode(), {})

        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "clip.mp4"); open(p, "wb").write(b"x" * 10)
            import time as _t
            real_sleep = _t.sleep; _t.sleep = lambda s: None
            try:
                fid = REAL_UPLOAD("tok", "folder", p, opener=opener, log=lambda *a: None)
            finally:
                _t.sleep = real_sleep
        self.assertEqual(fid, "file-1")
        self.assertEqual(state["opens"], 3)
