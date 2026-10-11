"""The new countries' briefs and packs on Drive (src/country_drive.py), with a fake Drive."""
import datetime
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import country_drive as cd  # noqa: E402

TODAY = datetime.date(2026, 10, 11)
BRIEF_MD = "# Campaigns Brief (DRAFT): {0}\n\n> **NOT READY: awaiting sign-off.**\n"


class FakeDrive(cd.Drive):
    """Folders, sheets and files in dicts; records every write."""

    def __init__(self, dry=False):
        super().__init__("tok", None, "DRIVE", dry=dry, log=lambda *a: None)
        self.folders = {}          # (parent, name) -> id
        self.props = {}            # slug -> file id
        self.names = {}            # file id -> name
        self.stored = {}           # folder id -> {name: {"id", "md5Checksum"}}
        self.writes = []
        self.n = 0

    def _id(self, kind):
        self.n += 1
        return "{0}{1}".format(kind, self.n)

    def folder(self, parent, name):
        if parent is None:
            return None, False
        key = (parent, name)
        if key in self.folders:
            return self.folders[key], False
        if self.dry:
            return None, False
        self.folders[key] = self._id("F")
        self.writes.append(("folder", name))
        return self.folders[key], True

    def by_slug(self, slug):
        return self.props.get(slug)

    def tag(self, file_id, slug, name=None):
        self.props[slug] = file_id
        if name:
            self.names[file_id] = name
            self.writes.append(("rename", file_id, name))

    def files(self, folder_id):
        return dict(self.stored.get(folder_id, {}))

    def trash(self, file_id):
        self.writes.append(("trash", file_id))
        for files in self.stored.values():
            for name in [n for n, f in files.items() if f["id"] == file_id]:
                del files[name]

    def upload(self, folder_id, path, name):
        fid = self._id("U")
        self.stored.setdefault(folder_id, {})[name] = {"id": fid, "md5Checksum": cd.md5_of(path)}
        self.writes.append(("upload", name))
        return fid

    def fca_note(self, file_id, cc):
        self.writes.append(("fca_note", file_id))
        return True


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.briefs = os.path.join(self.tmp, "briefs")
        self.packs = os.path.join(self.tmp, "packs")
        os.makedirs(self.briefs)
        os.makedirs(self.packs)
        self.brief("pl-kodeks-karny-10-611", "Kodeks karny")
        self.brief("it-fine-vita-19-104", "Fine vita")
        self.brief("bill-a-uk-bill", "A UK bill")              # not a new country: left out
        self.pack("pl-2026-10-20-kodeks-karny", sample=False)
        self.pack("it-2026-10-14-sample", sample=True)
        self.calls = []

    def brief(self, slug, subject, ready=False):
        with open(os.path.join(self.briefs, slug + ".csv"), "w") as h:
            h.write("Campaign Name,Campaigner\nx,y\n")
        with open(os.path.join(self.briefs, slug + ".md"), "w") as h:
            h.write(BRIEF_MD.format(subject) if not ready else
                    "# Campaigns Brief (DRAFT): {0}\n\nREADY\n".format(subject))

    def pack(self, name, sample):
        folder = os.path.join(self.packs, name)
        os.makedirs(folder)
        cc, rest = name.split("-", 1)
        with open(os.path.join(folder, "pack.json"), "w") as h:
            json.dump({"cc": cc, "date": rest[:10], "title": "Kodeks karny", "sample": sample}, h)
        for f in ("README.md", "pack.md", "members.csv"):
            with open(os.path.join(folder, f), "w") as h:
                h.write(f)

    def publish_one(self, token, slug, subject, dry_run=False, into=None, parent=None, title=None):
        self.calls.append((slug, into, parent, title))
        return (into or "S-" + slug), "ok"

    def go(self, drive, ledger, **kw):
        b = cd.local_briefs(("pl", "it"), self.briefs)
        p = cd.local_packs(("pl", "it"), self.packs)
        return cd.run(drive, b, p, ledger, today=TODAY, publish_one=self.publish_one,
                      log=lambda *a: None, **kw)


class LocalTests(Fixture):
    def test_finds_country_briefs_and_real_packs_only(self):
        b = cd.local_briefs(("pl", "it"), self.briefs)
        self.assertEqual([x["slug"] for x in b], ["it-fine-vita-19-104", "pl-kodeks-karny-10-611"])
        self.assertEqual(b[1]["subject"], "Kodeks karny")
        self.assertFalse(b[1]["ready"])
        p = cd.local_packs(("pl", "it"), self.packs)
        self.assertEqual([x["dir"] for x in p], ["pl-2026-10-20-kodeks-karny"])
        self.assertNotIn("pack.json", [f for _p, f in p[0]["files"]])

    def test_title_says_not_ready(self):
        b = cd.local_briefs(("pl",), self.briefs)[0]
        self.assertEqual(cd.brief_title(b, "2026-10"),
                         "2026-10 PL Brief DRAFT (NOT READY): Kodeks karny")


class RunTests(Fixture):
    def test_first_run_makes_folders_sheets_and_uploads(self):
        drive, ledger = FakeDrive(), cd.load_ledger(os.path.join(self.tmp, "none.json"))
        n = self.go(drive, ledger)
        self.assertEqual(n["new"], 2)
        self.assertEqual(n["pack_up"], 3)
        names = [w[1] for w in drive.writes if w[0] == "folder"]
        for want in ("Country editions", "Poland", "Italy", "Campaign briefs", "Debate packs",
                     "2026-10-20 Kodeks karny"):
            self.assertIn(want, names)
        pl_call = [c for c in self.calls if c[0].startswith("pl-")][0]
        self.assertIsNone(pl_call[1])
        self.assertEqual(pl_call[3], "2026-10 PL Brief DRAFT (NOT READY): Kodeks karny")
        self.assertEqual(drive.folders[(drive.folders[(drive.folders[("DRIVE", "Country editions")],
                                                       "Poland")], "Campaign briefs")], pl_call[2])
        self.assertEqual(sum(1 for w in drive.writes if w[0] == "fca_note"), 2)
        self.assertIn("pl-kodeks-karny-10-611", ledger["briefs"])

    def test_rerun_publishes_nothing_twice(self):
        drive, ledger = FakeDrive(), {"briefs": {}, "packs": {}}
        self.go(drive, ledger)
        before = list(drive.writes)
        self.calls = []
        n = self.go(drive, ledger)
        self.assertEqual(drive.writes, before)
        self.assertEqual(self.calls, [])
        self.assertEqual((n["new"], n["unchanged"], n["pack_up"], n["pack_same"]), (0, 2, 0, 3))

    def test_a_lost_ledger_adopts_the_sheet(self):
        drive = FakeDrive()
        self.go(drive, {"briefs": {}, "packs": {}})
        self.calls = []
        n = self.go(drive, {"briefs": {}, "packs": {}})
        self.assertEqual(n["new"], 0)
        self.assertTrue(all(c[1] for c in self.calls))       # rewritten in place, never copied

    def test_a_refreshed_brief_is_rewritten_and_a_ready_one_renamed(self):
        drive, ledger = FakeDrive(), {"briefs": {}, "packs": {}}
        self.go(drive, ledger)
        self.calls = []
        self.brief("pl-kodeks-karny-10-611", "Kodeks karny", ready=True)
        with open(os.path.join(self.briefs, "pl-kodeks-karny-10-611.csv"), "a") as h:
            h.write("more\n")
        n = self.go(drive, ledger)
        self.assertEqual((n["rewritten"], n["renamed"], n["new"]), (1, 1, 0))
        self.assertEqual(self.calls[0][1], "S-pl-kodeks-karny-10-611")
        self.assertIn(("rename", "S-pl-kodeks-karny-10-611", "2026-10 PL Brief DRAFT: Kodeks karny"),
                      drive.writes)

    def test_a_changed_pack_file_is_replaced(self):
        drive, ledger = FakeDrive(), {"briefs": {}, "packs": {}}
        self.go(drive, ledger)
        with open(os.path.join(self.packs, "pl-2026-10-20-kodeks-karny", "pack.md"), "w") as h:
            h.write("new text")
        n = self.go(drive, ledger)
        self.assertEqual((n["pack_up"], n["pack_same"]), (1, 2))
        self.assertEqual(sum(1 for w in drive.writes if w[0] == "trash"), 1)

    def test_rejected_briefs_are_binned_and_never_made(self):
        drive, ledger = FakeDrive(), {"briefs": {}, "packs": {}}
        self.go(drive, ledger)
        n = self.go(drive, ledger, rejected={"pl-kodeks-karny-10-611"})
        self.assertEqual(n["binned"], 1)
        self.assertNotIn("pl-kodeks-karny-10-611", ledger["briefs"])
        drive2, ledger2 = FakeDrive(), {"briefs": {}, "packs": {}}
        self.go(drive2, ledger2, rejected={"pl-kodeks-karny-10-611"})
        self.assertNotIn("pl-kodeks-karny-10-611", ledger2["briefs"])

    def test_dry_run_writes_nothing(self):
        drive, ledger = FakeDrive(dry=True), {"briefs": {}, "packs": {}}
        n = self.go(drive, ledger)
        self.assertEqual(drive.writes, [])
        self.assertEqual(self.calls, [])
        self.assertEqual(ledger, {"briefs": {}, "packs": {}})
        self.assertEqual((n["new"], n["pack_up"]), (2, 3))
        n = self.go(None, ledger)                              # offline
        self.assertEqual((n["new"], n["pack_up"]), (2, 3))

    def test_max_new_and_ready_only(self):
        drive, ledger = FakeDrive(), {"briefs": {}, "packs": {}}
        n = self.go(drive, ledger, max_new=1)
        self.assertEqual((n["new"], n["waiting"]), (1, 1))
        n = self.go(FakeDrive(), {"briefs": {}, "packs": {}}, ready_only=True)
        self.assertEqual((n["new"], n["skipped"]), (0, 2))
        self.assertIn("wait for next week", cd.summary(dict(n, waiting=3), False))


if __name__ == "__main__":
    unittest.main()
