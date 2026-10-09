"""Every Mac Mini job that publishes the store names the pipeline its heartbeat
stamps (9 October 2026: Day sweep, EU day sweep and US weekly stamped "local",
so tools/coverage.py would have called them dead once GitHub's backup skipped)."""
import glob
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import coverage  # noqa: E402


class HeartbeatNameTests(unittest.TestCase):
    def test_every_store_publishing_job_names_a_watched_pipeline(self):
        jobs = glob.glob(os.path.join(ROOT, "jobs", "*.sh"))
        self.assertTrue(jobs)
        for path in jobs:
            src = open(path, encoding="utf-8").read()
            push = re.search(r"^[^#\n]*python3 tools/db_state\.py --push", src, re.M)
            if not push:
                continue
            m = re.search(r'GITHUB_WORKFLOW="\$\{GITHUB_WORKFLOW:-([^}]+)\}"', src)
            self.assertIsNotNone(m, os.path.basename(path) + " publishes the store but names no pipeline")
            self.assertIn(m.group(1), coverage.PIPELINES, os.path.basename(path))
            self.assertLess(m.start(), push.start(), path)


if __name__ == "__main__":
    unittest.main()
