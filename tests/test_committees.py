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
        # Assert against the payload's own endDate, never a hardcoded date --
        # the same lesson as the item count above. This test pinned 2026-09-07
        # and broke on 2026-08-20 when the committee EXTENDED submission period
        # id 3964 to 2026-09-21T16:00 (it read 2026-09-07T17:00 in the capture
        # two days earlier). The parser was right; the constant was stale.
        # Comparing to the payload still catches a parser reading the wrong
        # field (startDate) or mishandling the timestamp, and survives the
        # committee moving its own deadline again.
        payload = load_fixture("committee_accepting-evidence")
        item = next(i for i in payload["items"]
                    if "Online Safety Act" in str(i.get("name") or i.get("title")))
        expected = datetime.date.fromisoformat(
            item["openSubmissionPeriods"][0]["endDate"][:10])
        osa = next(c for c in self.calls if "Online Safety Act" in c.title)
        self.assertEqual(osa.deadline, expected)
        self.assertNotEqual(
            osa.deadline,
            datetime.date.fromisoformat(
                item["openSubmissionPeriods"][0]["startDate"][:10]),
            "the parser must read endDate, not startDate")
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
