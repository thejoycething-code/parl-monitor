"""tools/mini_run.sh, step 4 (commit state), run for real in a throwaway git
repo with a bare remote and a stub `fail`.

9 October 2026: the sk backfill pushed raw-2026-10-09.tar, then lost its store
upload to a concurrent publish. Step 4 stopped at "the job changed the store
but did not publish it" BEFORE committing anything, so the raw archive's new
sidecar never reached main and every later pull refused the folder (SHA
MISMATCH). Christopher: "Fix it here". Now the raw sidecar alone is committed
and pushed, and the store failure is reported after it.
"""

import os
import subprocess
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def commit_block():
    with open(os.path.join(ROOT, "tools", "mini_run.sh"), encoding="utf-8") as h:
        src = h.read()
    start = src.index('STAGE="commit state"')
    end = src.index("# 4b. Now the job's own failure")
    return src[start:end]


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


class CommitStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.remote = os.path.join(self.tmp, "remote.git")
        self.clone = os.path.join(self.tmp, "clone")
        git(self.tmp, "init", "-q", "--bare", "-b", "main", self.remote)
        git(self.tmp, "clone", "-q", self.remote, self.clone)
        os.makedirs(os.path.join(self.clone, "data"))
        for name, body in (("raw.json", '{"v": 1}\n'), ("parl-monitor.db.json", '{"sha": "old"}\n'),
                           ("note.txt", "x\n")):
            with open(os.path.join(self.clone, "data", name), "w") as h:
                h.write(body)
        os.makedirs(os.path.join(self.clone, "jobs"))
        open(os.path.join(self.clone, "jobs", "demo.sh"), "w").close()
        git(self.clone, "add", "-A")
        git(self.clone, "commit", "-q", "-m", "init")
        git(self.clone, "push", "-q", "origin", "HEAD:main")

    def run_block(self, store_changed, raw_changed, sidecar_changed=False):
        d = os.path.join(self.clone, "data")
        open(os.path.join(d, ".store-pulled"), "w").close()
        time.sleep(1.1)
        with open(os.path.join(d, "parl-monitor.db"), "w") as h:
            h.write("store" if store_changed else "")
        if not store_changed:
            os.utime(os.path.join(d, "parl-monitor.db"), (0, 0))
        if raw_changed:
            with open(os.path.join(d, "raw.json"), "w") as h:
                h.write('{"v": 2}\n')
        if sidecar_changed:
            with open(os.path.join(d, "parl-monitor.db.json"), "w") as h:
                h.write('{"sha": "new"}\n')
        with open(os.path.join(d, "note.txt"), "w") as h:
            h.write("changed by the job\n")
        script = ("set -u\nJOB=demo\nREF=main\njob_failed=\n"
                  'fail() { echo "FAILED: $*"; exit 7; }\n' + commit_block() + "\necho DONE\n")
        p = subprocess.run(["bash", "-c", script], cwd=self.clone, capture_output=True, text=True,
                           env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
        remote_files = subprocess.run(["git", "--git-dir", self.remote, "show", "--stat", "--format=%s", "main"],
                                      capture_output=True, text=True).stdout
        return p, remote_files

    def test_unpublished_store_still_commits_the_raw_sidecar_then_fails(self):
        p, remote = self.run_block(store_changed=True, raw_changed=True)
        self.assertEqual(p.returncode, 7, p.stdout + p.stderr)
        self.assertIn("did not publish it", p.stdout)
        self.assertIn("raw archive only", remote)
        self.assertIn("data/raw.json", remote)
        self.assertNotIn("note.txt", remote)      # nothing else rides along

    def test_unpublished_store_with_no_raw_change_commits_nothing(self):
        p, remote = self.run_block(store_changed=True, raw_changed=False)
        self.assertEqual(p.returncode, 7)
        self.assertEqual(remote.splitlines()[0], "init")

    def test_a_published_store_commits_all_of_data_as_before(self):
        p, remote = self.run_block(store_changed=True, raw_changed=True, sidecar_changed=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("DONE", p.stdout)
        for f in ("data/raw.json", "data/parl-monitor.db.json", "data/note.txt"):
            self.assertIn(f, remote)
        self.assertNotIn("raw archive only", remote)


if __name__ == "__main__":
    unittest.main()
