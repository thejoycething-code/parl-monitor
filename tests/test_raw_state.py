"""The raw archive as release assets (Christopher, 2026-09-07: "do 3")."""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rs = _load("raw_state")
mrg = _load("merge_raw_sidecar")
WORKFLOWS = os.path.join(ROOT, ".github", "workflows")


def _folder(files):
    d = tempfile.mkdtemp()
    for rel, content in files.items():
        full = os.path.join(d, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as fh:
            fh.write(content)
    return d


class DigestAndTarTests(unittest.TestCase):
    def test_digest_is_content_not_order_or_mtime(self):
        a = _folder({"x.json.gz": b"1", "sub/y.json.gz": b"22"})
        b = _folder({"sub/y.json.gz": b"22", "x.json.gz": b"1"})
        self.assertEqual(rs.folder_digest(a), rs.folder_digest(b))
        self.assertEqual(rs.folder_digest(a)[1:], (2, 3))
        c = _folder({"x.json.gz": b"1", "sub/y.json.gz": b"23"})
        self.assertNotEqual(rs.folder_digest(a)[0], rs.folder_digest(c)[0])

    def test_tar_round_trips_and_union_never_overwrites(self):
        src = _folder({"a.gz": b"A", "d/b.gz": b"B"})
        tar = os.path.join(tempfile.mkdtemp(), "t.tar")
        rs.make_tar(src, tar)
        dst = _folder({"a.gz": b"LOCAL", "c.gz": b"C"})
        added = rs.extract_union(tar, dst)
        self.assertEqual(added, 1)                                    # only d/b.gz was new
        self.assertEqual(open(os.path.join(dst, "a.gz"), "rb").read(), b"LOCAL")
        self.assertEqual(open(os.path.join(dst, "d", "b.gz"), "rb").read(), b"B")
        self.assertTrue(os.path.exists(os.path.join(dst, "c.gz")))     # nothing deleted

    def test_a_tar_member_that_escapes_is_refused(self):
        import tarfile, io
        tar = os.path.join(tempfile.mkdtemp(), "evil.tar")
        with tarfile.open(tar, "w") as t:
            info = tarfile.TarInfo("../escape.gz"); data = b"x"; info.size = len(data)
            t.addfile(info, io.BytesIO(data))
        with self.assertRaises(ValueError):
            rs.extract_union(tar, tempfile.mkdtemp())

    def test_asset_names_carry_the_folder(self):
        self.assertEqual(rs.asset_name("2026-09-06"), "raw-2026-09-06.tar")
        self.assertEqual(rs.asset_name("eu-probe-2026-09-01"), "raw-eu-probe-2026-09-01.tar")


class MergeDriverTests(unittest.TestCase):
    def test_union_of_folders_later_publish_wins(self):
        ours = {"folders": {"a": {"sha256": "o", "published_utc": "2026-09-07T10:00:00Z"},
                            "b": {"sha256": "ob", "published_utc": "2026-09-07T09:00:00Z"}}}
        theirs = {"folders": {"b": {"sha256": "tb", "published_utc": "2026-09-07T11:00:00Z"},
                              "c": {"sha256": "tc", "published_utc": "2026-09-07T08:00:00Z"}}}
        out = mrg.merge(ours, theirs)
        self.assertEqual(set(out["folders"]), {"a", "b", "c"})
        self.assertEqual(out["folders"]["b"]["sha256"], "tb")
        self.assertEqual(out["folders"]["a"]["sha256"], "o")


class RepoWiringTests(unittest.TestCase):
    """The archive leaves git the way the store did: ignored, pointed at."""

    def _rules(self):
        with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as fh:
            return [l.strip() for l in fh if l.strip() and not l.lstrip().startswith("#")]

    def test_raw_is_ignored_and_the_sidecar_is_not(self):
        rules = self._rules()
        self.assertIn("data/raw/", rules)
        for rule in rules:
            self.assertNotIn("raw.json", rule, "the raw sidecar is the provenance record")

    def test_no_workflow_stages_the_raw_archive(self):
        import glob
        for path in glob.glob(os.path.join(WORKFLOWS, "*.yml")):
            src = open(path, encoding="utf-8").read()
            import re
            self.assertIsNone(re.search(r"git add[^\n]*data/raw(?![\w./])", src), os.path.basename(path) +
                              ": data/raw is ignored; `git add` of it fails the commit step")

    def test_every_store_publisher_publishes_the_archive_too(self):
        """A workflow that writes the store writes payloads into data/raw on
        the way; publishing one without the other strands provenance."""
        import glob
        for path in glob.glob(os.path.join(WORKFLOWS, "*.yml")):
            src = open(path, encoding="utf-8").read()
            if "db_state.py --push" in src:
                self.assertIn("raw_state.py --push", src, os.path.basename(path))
                self.assertLess(src.index("raw_state.py --push"), src.index("db_state.py --push"),
                                os.path.basename(path) + ": publish the archive before the store")
            if "db_state.py --pull" in src and "coverage-watch" not in path:
                self.assertIn("raw_state.py --pull", src, os.path.basename(path))

    def test_the_archive_writers_without_a_store_publish_it(self):
        for name in ("division-watch.yml", "deploy-tracker.yml"):
            src = open(os.path.join(WORKFLOWS, name), encoding="utf-8").read()
            self.assertIn("raw_state.py --push", src, name)

    def test_the_merge_driver_is_bound(self):
        attrs = open(os.path.join(ROOT, ".gitattributes"), encoding="utf-8").read()
        self.assertIn("data/raw.json merge=raw-sidecar", attrs)


if __name__ == "__main__":
    unittest.main()
