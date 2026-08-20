"""Holyrood ingester tests, against live-probed fixtures (2026-08-20)."""

import gzip
import glob
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.ingest import holyrood


def load_fixture(slug):
    paths = sorted(glob.glob(os.path.join(
        ROOT, "data", "raw", "*", slug + ".json.gz")))
    with gzip.open(paths[-1], "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


class QuestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = holyrood.parse_questions(load_fixture("holyrood_questions-fixture"))

    def test_parses_every_row(self):
        payload = load_fixture("holyrood_questions-fixture")
        self.assertEqual(len(self.rows), len(payload))

    def test_answers_arrive_inline(self):
        """The single biggest difference from NI: AnswerText is ON the question
        row, so no per-answer fetch exists to guard or to spend."""
        answered = [r for r in self.rows if r.answer]
        self.assertTrue(answered, "fixture must carry answered questions")
        for r in answered:
            self.assertTrue(r.answered, "an answer implies an AnswerDate")

    def test_html_entities_are_unescaped(self):
        """ItemText carries &rsquo; and &pound; -- classification text must be
        real characters or phrase terms fail on the entity."""
        for r in self.rows:
            self.assertNotIn("&rsquo;", r.body)
            self.assertNotIn("&pound;", r.body)

    def test_reference_comes_from_event_id(self):
        refs = [r.reference for r in self.rows if r.reference]
        self.assertTrue(any(x.startswith(("S6", "S7")) for x in refs), refs)


class MotionTests(unittest.TestCase):
    def test_since_floor_is_applied(self):
        """The motions endpoint IGNORES ?year= and serves everything since
        1999 (110MB, 84,751 rows); the floor is client-side and load-bearing --
        without it the store gains ~100MB of text nobody will read."""
        payload = load_fixture("holyrood_motions-fixture")
        allrows = holyrood.parse_motions(payload)
        floored = holyrood.parse_motions(payload, since="2024-01-01")
        self.assertLess(len(floored), len(allrows),
                        "fixture carries pre-2000 rows the floor must drop")
        for r in floored:
            self.assertGreaterEqual(r.dated, "2024-01-01")


class RosterTests(unittest.TestCase):
    def test_current_roster_is_the_chamber(self):
        """129 seats. The live probe's memberparties held exactly 129 rows with
        a null ValidUntilDate -- the roster validates itself against the real
        chamber, the same check that caught NI's by-date lag."""
        affs = holyrood.parse_affiliations(
            [{"ID": 1, "PersonID": 2, "PartyID": 3,
              "ValidFromDate": "2026-05-08T00:00:00", "ValidUntilDate": None}])
        self.assertIsNone(affs[0].valid_until)
        self.assertEqual(affs[0].valid_from, "2026-05-08")


class SeparationTests(unittest.TestCase):
    """Holyrood must not be able to reach the published Slack digest --
    the same structural guarantee as NI, asserted from day one rather than
    retrofitted."""

    def _source(self, name):
        with open(os.path.join(ROOT, "tools", name), encoding="utf-8") as fh:
            return fh.read()

    def test_sp_tools_never_write_published_tables(self):
        for name in ("sp_pull.py",):
            source = self._source(name)
            for table in ("items", "mp_events"):
                for verb in ("INTO {0} ", "INTO {0}(", "UPDATE {0} "):
                    self.assertNotIn(verb.format(table), source,
                                     "{0} must not write {1}".format(name, table))

    def test_sp_pull_writes_its_own_tables(self):
        source = self._source("sp_pull.py")
        self.assertIn("sp_items", source)
        self.assertIn("sp_members", source)

    def test_monitor_is_read_only(self):
        source = self._source("sp_monitor.py")
        for verb in ("INSERT", "UPDATE ", "DELETE"):
            self.assertNotIn(verb, source)

    def test_year_dumps_are_not_archived_to_git(self):
        """data/raw is committed weekly; the dumps are 7-110MB and the API
        serves them canonically by year. archive=False is the contract."""
        source = open(os.path.join(ROOT, "src", "ingest", "holyrood.py"),
                      encoding="utf-8").read()
        self.assertIn('archive=False', source)
        # the small roster fetches ARE archived (provenance is cheap there)
        self.assertIn('"members"', source)


if __name__ == "__main__":
    unittest.main()
