"""The sidecar merge driver: the release decides (Christopher, 2026-09-07:
"Fix the sidecar merge friction").

Three hand-resolved conflicts on the pointer file in two days, each one
keystroke from pointing the repo at a store that is not there.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("ms", os.path.join(ROOT, "tools", "merge_sidecar.py"))
ms = importlib.util.module_from_spec(spec); spec.loader.exec_module(ms)

A = {"sha256": "a" * 64, "published_utc": "2026-09-07T03:00:00Z"}
B = {"sha256": "b" * 64, "published_utc": "2026-09-07T04:00:00Z"}


class ChooseTests(unittest.TestCase):
    def test_the_side_naming_the_published_asset_wins_whichever_it_is(self):
        self.assertEqual(ms.choose(A, B, "a" * 64)[0], "ours")
        self.assertEqual(ms.choose(A, B, "b" * 64)[0], "theirs")

    def test_a_later_publish_is_not_enough_if_the_release_says_otherwise(self):
        """Newest pointer is not the true pointer if someone published after it."""
        self.assertEqual(ms.choose(A, B, "a" * 64)[0], "ours")   # B is later, A is published

    def test_neither_matching_refuses_rather_than_guessing(self):
        side, reason = ms.choose(A, B, "c" * 64)
        self.assertIsNone(side); self.assertIn("NEITHER", reason)

    def test_without_a_digest_the_later_publish_wins(self):
        self.assertEqual(ms.choose(A, B, None)[0], "theirs")
        self.assertEqual(ms.choose(B, A, None)[0], "ours")

    def test_without_digest_or_timestamps_it_refuses(self):
        side, reason = ms.choose({"sha256": "a" * 64}, {"sha256": "b" * 64}, None)
        self.assertIsNone(side); self.assertIn("refusing", reason)


class GitIntegrationTests(unittest.TestCase):
    """A real repo, a real conflicting merge, the real driver."""

    def make_repo(self):
        d = tempfile.mkdtemp()
        def git(*a):
            return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t"] + list(a),
                                  cwd=d, capture_output=True, text=True)
        git("init", "-q", "-b", "main")
        os.makedirs(os.path.join(d, "data"))
        open(os.path.join(d, ".gitattributes"), "w").write("data/parl-monitor.db.json merge=db-sidecar\n")
        git("config", "merge.db-sidecar.driver",
            "python3 {0} %O %A %B".format(os.path.join(ROOT, "tools", "merge_sidecar.py")))
        def write(side):
            with open(os.path.join(d, "data", "parl-monitor.db.json"), "w") as fh:
                json.dump(side, fh, indent=2, sort_keys=True); fh.write("\n")
        write({"sha256": "0" * 64, "published_utc": "2026-09-07T01:00:00Z"})
        git("add", "-A"); git("commit", "-qm", "base")
        git("checkout", "-qb", "ci"); write(A); git("commit", "-qam", "ci publish")
        git("checkout", "-q", "main"); write(B); git("commit", "-qam", "laptop publish")
        return d, git

    def read(self, d):
        return json.load(open(os.path.join(d, "data", "parl-monitor.db.json")))

    def test_merge_takes_the_side_the_release_names(self):
        d, git = self.make_repo()
        env = dict(os.environ, SIDECAR_DIGEST="sha256:" + "a" * 64)
        out = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "merge", "-q", "ci"],
                             cwd=d, capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.read(d)["sha256"], "a" * 64, "the release named A; the merge kept B")

    def test_merge_stops_when_neither_side_is_published(self):
        d, git = self.make_repo()
        env = dict(os.environ, SIDECAR_DIGEST="sha256:" + "c" * 64)
        out = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "merge", "-q", "ci"],
                             cwd=d, capture_output=True, text=True, env=env)
        self.assertNotEqual(out.returncode, 0, "a guessing merge is worse than a stopped one")
        self.assertIn("NEITHER", out.stderr)


class WiringTests(unittest.TestCase):
    def test_gitattributes_binds_the_sidecar(self):
        src = open(os.path.join(ROOT, ".gitattributes"), encoding="utf-8").read()
        self.assertIn("data/parl-monitor.db.json merge=db-sidecar", src)

    def test_pull_installs_the_driver_and_push_stamps_the_time(self):
        src = open(os.path.join(ROOT, "tools", "db_state.py"), encoding="utf-8").read()
        self.assertIn("merge.db-sidecar.driver", src)
        self.assertLess(src.index("def pull():"), src.index("install_merge_driver()\n    tok = token()"))
        self.assertIn('"published_utc"', src)


if __name__ == "__main__":
    unittest.main()
