"""Senedd ingester tests against live-probed fixtures (2026-08-21)."""

import gzip
import glob
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.ingest import senedd


def load(slug):
    paths = sorted(glob.glob(os.path.join(ROOT, "data", "raw", "*",
                                          slug + ".json.gz")))
    with gzip.open(paths[-1], "rt", encoding="utf-8") as fh:
        return fh.read()


class ParseTests(unittest.TestCase):
    def test_answered_question_parses_whole(self):
        q = senedd.parse_question(load("senedd_wq-answered-fixture"), 95000)
        self.assertEqual(q.reference, "WQ95000")
        self.assertEqual(q.member_name, "Andrew R.T. Davies")
        self.assertEqual(q.constituency, "South Wales Central")
        self.assertEqual(q.dated, "2024-11-14")
        self.assertEqual(q.answered, "2024-11-21")
        self.assertIn("maternity", q.body)
        self.assertIn("service standards", q.answer)

    def test_pending_question_has_minister_but_no_answer(self):
        q = senedd.parse_question(load("senedd_wq-pending-fixture"), 100032)
        self.assertEqual(q.dated, "2026-08-19")
        self.assertIsNone(q.answered)
        self.assertIsNone(q.answer)
        self.assertIn("Health", q.answered_by)

    def test_the_miss_signature_is_no_tabled_line(self):
        """A nonexistent id serves the site shell WITHOUT 'Tabled on' -- the
        walker's stop condition. It must be None, never a garbage row."""
        self.assertIsNone(
            senedd.parse_question(load("senedd_wq-miss-fixture"), 100600))


class SeparationTests(unittest.TestCase):
    """Senedd must not be able to reach the published Slack digest."""

    def _source(self, name):
        with open(os.path.join(ROOT, "tools", name), encoding="utf-8") as fh:
            return fh.read()

    def test_sd_pull_writes_its_own_tables_only(self):
        source = self._source("sd_pull.py")
        self.assertIn("sd_items", source)
        for table in ("items", "mp_events"):
            for verb in ("INTO {0} ", "INTO {0}(", "UPDATE {0} "):
                self.assertNotIn(verb.format(table), source)

    def test_monitor_is_read_only(self):
        source = self._source("sd_monitor.py")
        for verb in ("INSERT", "UPDATE ", "DELETE"):
            self.assertNotIn(verb, source)

    def test_the_honest_user_agent_rule_is_stated(self):
        """business.senedd.wales rejects the CitizenGO UA; working around the
        WAF by impersonating a browser is a recorded decision point, not a
        quiet default. The ingester must keep saying so."""
        source = open(os.path.join(ROOT, "src", "ingest", "senedd.py"),
                      encoding="utf-8").read()
        self.assertIn("honest", source)
        self.assertIn("decision", source)


if __name__ == "__main__":
    unittest.main()


class WeeklyWorkflowTests(unittest.TestCase):
    def test_the_workflow_has_no_publish_step_and_can_push(self):
        """Copied from ni-weekly rather than written from memory -- the
        sp-weekly lesson (its day-one double miss was a missing permissions
        block and sunset action majors)."""
        path = os.path.join(ROOT, ".github", "workflows", "sd-weekly.yml")
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        source = "\n".join(l for l in raw.splitlines()
                           if not l.strip().startswith("#"))
        for banned in ("slack", "secrets.yaml", "post_", "publish",
                       "ANTHROPIC", "SLACK"):
            self.assertNotIn(banned, source, banned)
        self.assertIn("group: parl-monitor-state", source)
        self.assertIn("contents: write", source)
        self.assertIn("checkout@v7", source)
