import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import drivepack  # noqa: E402


class FakeDrive(object):
    def __init__(self):
        self.calls, self.folders, self.files = [], {}, {}

    def api(self, token, url, payload=None, method=None):
        self.calls.append((url.split("?")[0], payload))
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


if __name__ == "__main__":
    unittest.main()
