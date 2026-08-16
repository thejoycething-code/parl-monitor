"""Committee calls-for-evidence tests against the live-probed fixtures."""

import datetime
import glob
import gzip
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import filter as filt
from src.ingest import committees

TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))


def load_fixture(slug):
    paths = sorted(glob.glob(os.path.join(ROOT, "data", "raw", "*", slug + ".json.gz")))
    with gzip.open(paths[-1], "rb") as handle:
        return json.loads(handle.read().decode("utf-8"))


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.calls = committees.parse_response(load_fixture("committee_accepting-evidence"))

    def test_parses_open_calls(self):
        # Assert against the payload's own item count, never a hardcoded one:
        # the fixture is the newest live capture, so a committee closing its
        # call for evidence turned 25 into 24 and failed a test about the
        # PARSER (2026-08-17). The parser's job is to lose nothing.
        payload = load_fixture("committee_accepting-evidence")
        self.assertEqual(len(self.calls), len(payload.get("items") or []))
        self.assertTrue(self.calls, "fixture carried no calls for evidence")
        self.assertTrue(all(c.id and c.title for c in self.calls))

    def test_deadline_from_submission_period(self):
        osa = next(c for c in self.calls if "Online Safety Act" in c.title)
        self.assertEqual(osa.deadline, datetime.date(2026, 9, 7))
        self.assertEqual(osa.url, "https://committees.parliament.uk/work/{0}/".format(osa.id))

    def test_rolling_calls_have_no_deadline(self):
        rolling = [c for c in self.calls if c.deadline is None]
        self.assertTrue(rolling)  # e.g. "Electronic voting", "Support for Jurors"

    def test_osa_call_matches_taxonomy_others_do_not(self):
        matched = [c for c in self.calls if filt.filter_item(TAX, WL, c.title or "").matched()]
        titles = [c.title for c in matched]
        self.assertTrue(any("Online Safety Act" in t for t in titles))
        # Whisky, Sahel, high streets etc. must not leak through.
        self.assertLessEqual(len(matched), 3)


class ResolveTests(unittest.TestCase):
    def test_committee_names_resolve_from_fixture(self):
        payload = load_fixture("committee_committees-for-9955")
        names = [(i.get("value") or i).get("name") for i in payload.get("items") or []]
        self.assertEqual(names, ["Communications and Digital Committee"])


if __name__ == "__main__":
    unittest.main()
