"""The raw archive as release assets (Christopher, 2026-09-07: "do 3")."""

import importlib.util
import json
import os
import re
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



def with_jobs(src):
    """A workflow's text followed by the jobs/ scripts it runs: a workflow that
    hands its work to a script shared with the Mac Mini runner publishes from
    that script, in the order the script does it."""
    for job in re.findall(r"jobs/[\w-]+\.sh", src):
        src += open(os.path.join(WORKFLOWS, "..", "..", job), encoding="utf-8").read()
    return src

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

    def test_a_published_folder_is_merged_in_even_when_it_has_not_moved(self):
        """3 October 2026: a laptop folder created under a date CI had already
        published never received CI's files (a pull fetches changed folders
        only), and pushing it REPLACED them -- 577 files of 2026-09-29. The
        push now merges the published copy before every upload."""
        raw = tempfile.mkdtemp()
        published = _folder({"ci-only.json.gz": b"ci"})
        tar = os.path.join(tempfile.mkdtemp(), "published.tar")
        rs.make_tar(published, tar)
        pub_digest = rs.folder_digest(published)[0]
        os.makedirs(os.path.join(raw, "2026-09-29"))
        with open(os.path.join(raw, "2026-09-29", "laptop-only.json.gz"), "wb") as fh:
            fh.write(b"laptop")
        uploaded = {}
        saved = {k: getattr(rs, k) for k in ("RAW", "ensure_release", "origin_sidecar", "load_sidecar",
                                             "write_sidecar", "_held", "_hold", "download_asset",
                                             "upload_asset", "local_folders")}
        try:
            rs.RAW = raw
            rs.ensure_release = lambda *a, **k: True
            side = {"folders": {"2026-09-29": {"sha256": pub_digest, "files": 1}}}
            rs.origin_sidecar = lambda *a, **k: {"2026-09-29": {"sha256": pub_digest}}
            rs.load_sidecar = lambda *a, **k: side
            rs.write_sidecar = lambda *a, **k: None
            rs._held = lambda *a, **k: {}
            rs._hold = lambda *a, **k: None
            rs.local_folders = lambda *a, **k: ["2026-09-29"]
            rs.download_asset = lambda folder, dest: shutil.copy(tar, dest) or True
            def up(folder, path):
                import tarfile
                with tarfile.open(path) as t:
                    uploaded[folder] = sorted(m.name.lstrip("./") for m in t.getmembers() if m.isfile())
            rs.upload_asset = up
            rs.push(log=lambda *a: None)
        finally:
            for k, v in saved.items():
                setattr(rs, k, v)
        self.assertEqual(uploaded["2026-09-29"], ["ci-only.json.gz", "laptop-only.json.gz"])

    def test_a_tar_over_the_asset_ceiling_is_never_uploaded(self):
        """2 October 2026: GitHub refuses a release asset of 2 GiB or more, and
        --clobber replaces the published copy. An oversized day is held back,
        its sidecar entry kept, and the push fails loudly."""
        raw = tempfile.mkdtemp()
        os.makedirs(os.path.join(raw, "2026-10-03"))
        with open(os.path.join(raw, "2026-10-03", "big.pdf.gz"), "wb") as fh:
            fh.write(b"x" * 4096)
        uploaded, lines = [], []
        side = {"folders": {}}
        saved = {k: getattr(rs, k) for k in ("RAW", "ensure_release", "origin_sidecar", "load_sidecar",
                                             "write_sidecar", "_held", "_hold", "upload_asset",
                                             "local_folders", "ASSET_LIMIT")}
        try:
            rs.RAW = raw
            rs.ASSET_LIMIT = 1024
            rs.ensure_release = lambda *a, **k: True
            rs.origin_sidecar = lambda *a, **k: {}
            rs.load_sidecar = lambda *a, **k: side
            rs.write_sidecar = lambda *a, **k: None
            rs._held = lambda *a, **k: {}
            rs._hold = lambda *a, **k: None
            rs.local_folders = lambda *a, **k: ["2026-10-03"]
            rs.upload_asset = lambda folder, path: uploaded.append(folder)
            rc = rs.push(log=lines.append)
        finally:
            for k, v in saved.items():
                setattr(rs, k, v)
        self.assertEqual(uploaded, [])
        self.assertEqual(rc, 1)
        self.assertNotIn("2026-10-03", side["folders"])
        self.assertTrue(any("NOT uploading" in l for l in lines))

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


class AssetVerificationTests(unittest.TestCase):
    def test_tar_digest_equals_folder_digest_of_its_contents(self):
        src = _folder({"a.gz": b"A", "d/b.gz": b"B"})
        tar = os.path.join(tempfile.mkdtemp(), "t.tar")
        rs.make_tar(src, tar)
        self.assertEqual(rs.tar_digest(tar), rs.folder_digest(src)[0])

    def test_a_local_variant_of_a_published_file_is_not_a_mismatch(self):
        """2026-09-07: a laptop held today's folder with a same-named payload
        whose gzip header differed; the pull called the asset corrupt."""
        published = _folder({"x.json.gz": b"published bytes"})
        tar = os.path.join(tempfile.mkdtemp(), "t.tar")
        rs.make_tar(published, tar)
        self.assertEqual(rs.tar_digest(tar), rs.folder_digest(published)[0])   # the asset is sound
        local = _folder({"x.json.gz": b"local bytes, same JSON inside"})
        rs.extract_union(tar, local)                                          # keeps the local version
        self.assertEqual(open(os.path.join(local, "x.json.gz"), "rb").read(), b"local bytes, same JSON inside")
        self.assertNotEqual(rs.folder_digest(local)[0], rs.tar_digest(tar))     # and that is fine


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
            src = with_jobs(open(path, encoding="utf-8").read())
            if "db_state.py --push" in src:
                self.assertIn("raw_state.py --push", src, os.path.basename(path))
                self.assertLess(src.index("raw_state.py --push"), src.index("db_state.py --push"),
                                os.path.basename(path) + ": publish the archive before the store")
            if "db_state.py --pull" in src and "coverage-watch" not in path:
                self.assertIn("raw_state.py --pull", src, os.path.basename(path))

    def test_the_archive_writers_without_a_store_publish_it(self):
        for name in ("division-watch.yml", "devolved-watch.yml", "deploy-tracker.yml"):
            src = with_jobs(open(os.path.join(WORKFLOWS, name), encoding="utf-8").read())
            self.assertIn("raw_state.py --push", src, name)

    def test_the_merge_driver_is_bound(self):
        attrs = open(os.path.join(ROOT, ".gitattributes"), encoding="utf-8").read()
        self.assertIn("data/raw.json merge=raw-sidecar", attrs)


if __name__ == "__main__":
    unittest.main()
