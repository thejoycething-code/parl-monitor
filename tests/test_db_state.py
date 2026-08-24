"""The store as a release asset (Christopher's decision, 2026-08-24).

The store hit 88MB against GitHub's 100MB HARD push limit, growing ~15MB
per build sprint. It is derived state, so it moved out of git into a
release asset. These tests pin the properties that make that safe.
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import db_state

WORKFLOWS = os.path.join(ROOT, ".github", "workflows")


def workflow(name):
    with open(os.path.join(WORKFLOWS, name), encoding="utf-8") as fh:
        return fh.read()


class WorkflowWiringTests(unittest.TestCase):
    STATEFUL = ("ni-weekly.yml", "sp-weekly.yml", "sd-weekly.yml",
                "sunday-pull.yml", "monday-publish.yml", "upr-monthly.yml")

    def test_every_stateful_workflow_pulls_and_pushes(self):
        for name in self.STATEFUL:
            text = workflow(name)
            self.assertIn("db_state.py --pull", text, name + " must pull")
            self.assertIn("db_state.py --push", text, name + " must push")

    def test_pull_precedes_push(self):
        for name in self.STATEFUL:
            text = workflow(name)
            self.assertLess(text.index("--pull"), text.index("--push"), name)

    def test_no_workflow_stages_the_store_itself(self):
        """`git add data/` is fine once the store is ignored, but naming the
        file explicitly would re-track it. sp-weekly used to."""
        for name in self.STATEFUL:
            text = workflow(name)
            self.assertNotIn("git add data/parl-monitor.db\n", text, name)
            self.assertNotIn("data/parl-monitor.db data/raw", text, name)

    def test_one_writer_at_a_time_is_enforced_repo_wide(self):
        """The release asset has no locking of its own; the shared
        concurrency group IS the lock. Without it two weeklies could
        interleave pull/push and silently lose a week's work."""
        for name in self.STATEFUL:
            text = workflow(name)
            self.assertIn("group: parl-monitor-state", text, name)
            self.assertIn("cancel-in-progress: false", text, name)

    def test_the_stateless_workflow_is_left_alone(self):
        """un-calls-weekly reads a page and sends a message; it never opens
        the store, so wiring it in would be noise."""
        self.assertNotIn("db_state.py", workflow("un-calls-weekly.yml"))


class BootstrapGuardTests(unittest.TestCase):
    def test_no_asset_with_a_working_copy_is_a_bootstrap(self):
        self.assertEqual(db_state._no_asset_yet(), 0,
                         "the working copy exists, so the first run should "
                         "proceed and publish it")

    def test_no_asset_and_no_working_copy_is_fatal(self):
        real = db_state.DB
        try:
            db_state.DB = os.path.join(ROOT, "data", "does-not-exist.db")
            self.assertEqual(db_state._no_asset_yet(), 1,
                             "untracking before an asset exists must fail "
                             "loudly, never build an empty store")
        finally:
            db_state.DB = real


class SidecarTests(unittest.TestCase):
    """The sidecar is what keeps provenance after the bytes leave git."""

    def test_sidecar_records_size_and_digest_when_present(self):
        if not os.path.exists(db_state.SIDECAR):
            self.skipTest("no store published yet")
        with open(db_state.SIDECAR, encoding="utf-8") as fh:
            meta = json.load(fh)
        self.assertIn("sha256", meta)
        self.assertIn("bytes", meta)
        self.assertEqual(len(meta["sha256"]), 64)

    def test_sidecar_is_not_ignored(self):
        """Check the RULES, not the file text: .gitignore's comment names the
        sidecar precisely to say it must never be ignored, and a naive
        substring search reads that explanation as a violation."""
        with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as fh:
            rules = [l.strip() for l in fh
                     if l.strip() and not l.lstrip().startswith("#")]
        for rule in rules:
            self.assertNotIn("parl-monitor.db.json", rule,
                             "the sidecar is the provenance record and MUST "
                             "be committed")


if __name__ == "__main__":
    unittest.main()
