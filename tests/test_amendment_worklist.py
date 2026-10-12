"""The amendment reading worklist (tools/amendment_worklist.py; Chris, 12
October 2026). Small temporary stores and stance files; no network."""

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country5ca as c5  # noqa: E402
from tests.test_country_5ca import Base, QUIET, _load  # noqa: E402

wl = _load("amendment_worklist")


class SelectionTests(Base):
    def setUp(self):
        super().setUp()
        self.draft()

    def test_only_unread_amendment_votes_are_listed(self):
        items = wl.build(self.conn, ("pl",), self.cfg)
        self.assertEqual([i["key"] for i in items], ["pl-10-1-2"])
        it = items[0]
        self.assertEqual((it["question"], it["question_source"], it["bill_key"], it["bill_direction"]),
                         ("poprawka 1", "store", "10/2110", "against"))
        self.assertEqual(it["tally"], {"yes": 200, "no": 220, "abstain": None})
        self.assertEqual(it["identifiers"]["amendment_numbers"], ["1"])
        self.assertTrue(any(u["url"].startswith("https://api.sejm.gov.pl/sejm/term10/votings/1/2")
                            for u in it["urls"]))
        self.assertEqual(it["answer_with"]["key"], "pl-10-1-2")
        # Once read (with/against), it leaves the list.
        c5.apply_amendments([{"cc": "pl", "key": "pl-10-1-2", "direction": "with", "why": "x",
                              "source": "https://example.org/a"}], self.cfg, "2026-10-12", log=QUIET)
        self.assertEqual(wl.build(self.conn, ("pl",), self.cfg), [])

    def test_unclear_stays_listed_with_its_flag_and_no_store_falls_back(self):
        c5.apply_amendments([{"cc": "pl", "key": "pl-10-1-2", "direction": "unclear",
                              "flag": "Which version?"}], self.cfg, "2026-10-12", log=QUIET)
        items = wl.build(None, ("pl",), self.cfg)
        self.assertEqual(items[0]["amendment_flag"], "Which version?")
        self.assertTrue(items[0]["question_source"].startswith("stance file"))
        self.assertIsNone(items[0]["tally"])

    def test_collated_only_entries_are_left_out(self):
        orig = c5.excluded
        c5.excluded = lambda: {9}
        try:
            self.assertEqual(wl.build(self.conn, ("pl",), self.cfg), [])
        finally:
            c5.excluded = orig

    def test_the_tool_writes_the_file_and_the_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, summ = os.path.join(tmp, "w.json"), os.path.join(tmp, "s.txt")
            orig = c5.CONFIG
            c5.CONFIG = self.cfg
            try:
                wl.main(["--db", os.path.join(self.tmp.name, "store.db"), "--out", out,
                         "--summary", summ, "--cc", "pl"])
            finally:
                c5.CONFIG = orig
            with open(out, encoding="utf-8") as h:
                self.assertEqual(len(json.load(h)), 1)
            with open(summ, encoding="utf-8") as h:
                self.assertRegex(h.read(), r"pl\s+Poland\s+1\s+1\s+1")


class WordingTests(unittest.TestCase):
    def test_french_wording(self):
        got = wl.wording_ids("l'amendement n° 135 de Mme Lorho à l'article 2 de la proposition de loi "
                             "relative au droit à l'aide à mourir (deuxième lecture).")
        self.assertEqual(got, {"amendment_numbers": ["135"], "article": "2", "author": "Mme Lorho",
                               "reading_or_stage": "deuxième lecture"})

    def test_italian_and_assembly_urls(self):
        got = wl.wording_ids("Identici emendamenti 1.2 D'ORSO VALENTINA (M5S), 1.1001 GRIMALDI MARCO (AVS)")
        self.assertEqual(got["amendment_numbers"][:2], ["1.2", "1.1001"])
        self.assertEqual(got["author"], "D'ORSO VALENTINA (M5S)")
        urls = wl.urls_for("fr", "an-17-1773", {}, {}, {"amendment_numbers": ["3"]}, {})
        self.assertEqual(urls[0]["url"], "https://www.assemblee-nationale.fr/dyn/17/scrutins/1773")
        self.assertIn("/amendements/<texte>/AN/3", urls[1]["url"])
        self.assertFalse(urls[1]["sure"])


if __name__ == "__main__":
    unittest.main()
