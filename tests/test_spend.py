"""API spend, recorded rather than remembered (Christopher, 2026-08-24).

The standing instruction is to be told when API funds are used. Until this
existed, the only source was recollection of historic rates -- the kind of
number that drifts without anyone noticing. The passes were already handed
a `usage` block on every reply and were discarding it.
"""

import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, spend, triage


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(sqlite3.connect(":memory:"))
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()

    def test_tokens_are_stored_per_pass_and_model(self):
        spend.record(self.conn, "triage", "claude-sonnet-5",
                     {"input_tokens": 1000, "output_tokens": 100},
                     dated="2026-08-24")
        rows, _notes, _total = spend.summary(self.conn)
        self.assertEqual(rows[0]["pass"], "triage")
        self.assertEqual(rows[0]["input"], 1000)
        self.assertEqual(rows[0]["calls"], 1)

    def test_an_unexpected_usage_shape_is_stored_as_zeros_not_dropped(self):
        """A call that happened must leave a trace even if the response
        surprised us -- silence would understate the bill."""
        spend.record(self.conn, "stance", "claude-sonnet-5", {},
                     dated="2026-08-24")
        rows, _n, _t = spend.summary(self.conn)
        self.assertEqual(rows[0]["calls"], 1)
        self.assertEqual(rows[0]["input"], 0)

    def test_an_unknown_model_records_tokens_but_estimates_no_cost(self):
        spend.record(self.conn, "triage", "some-future-model",
                     {"input_tokens": 5000, "output_tokens": 500},
                     dated="2026-08-24")
        rows, notes, total = spend.summary(self.conn)
        self.assertIsNone(rows[0]["usd"])
        self.assertEqual(total, 0.0)
        self.assertTrue(any("no rate held" in n for n in notes))


class RateTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(sqlite3.connect(":memory:"))
        self.conn.row_factory = sqlite3.Row

    def test_sonnet_5_is_two_and_ten_after_the_cancelled_rise(self):
        """Sonnet 5's scheduled rise to $3/$15 on 1 September 2026 was
        cancelled; $2/$10 became the standard price. This test used to pin
        $3.00 for September work -- the forecast, not the invoice."""
        spend.record(self.conn, "stance", "claude-sonnet-5",
                     {"input_tokens": 1_000_000, "output_tokens": 100_000},
                     dated="2026-09-07")
        _rows, notes, total = spend.summary(self.conn)
        self.assertAlmostEqual(total, 3.00, places=2)   # $2 input + $1 output
        self.assertFalse(any("INTRODUCTORY" in n for n in notes))

    def test_an_intro_rate_still_applies_before_it_lapses_and_says_so(self):
        """The mechanism stays for the next model launched on one."""
        saved = dict(spend.RATES)
        try:
            spend.RATES["some-intro-model"] = {"input": 3.00, "output": 15.00,
                                               "intro": {"until": "2026-08-31",
                                                         "input": 2.00, "output": 10.00}}
            spend.record(self.conn, "stance", "some-intro-model",
                         {"input_tokens": 1_000_000, "output_tokens": 0}, dated="2026-08-24")
            _rows, notes, total = spend.summary(self.conn)
            self.assertAlmostEqual(total, 2.00, places=2)
            self.assertTrue(any("INTRODUCTORY" in n for n in notes))
        finally:
            spend.RATES.clear()
            spend.RATES.update(saved)

    def test_a_pass_spanning_a_rate_change_is_priced_per_day(self):
        """It used to take the rate of the pass's LAST day for all of it."""
        saved = dict(spend.RATES)
        try:
            spend.RATES["some-intro-model"] = {"input": 3.00, "output": 15.00,
                                               "intro": {"until": "2026-08-31",
                                                         "input": 2.00, "output": 10.00}}
            for day in ("2026-08-30", "2026-09-02"):
                spend.record(self.conn, "stance", "some-intro-model",
                             {"input_tokens": 1_000_000, "output_tokens": 0}, dated=day)
            _rows, _notes, total = spend.summary(self.conn)
            self.assertAlmostEqual(total, 5.00, places=2, msg="$2 before + $3 after, not $6")
        finally:
            spend.RATES.clear()
            spend.RATES.update(saved)

    def test_no_currency_conversion_is_invented(self):
        """A stored FX rate goes stale silently. Dollars are what the
        invoice is in."""
        self.assertIsNone(spend.USD_PER_GBP)


class WiringTests(unittest.TestCase):
    def test_triage_hands_its_usage_to_the_sink(self):
        reply = {"content": [{"type": "text",
                              "text": '[{"id":"x","score":2,"areas":[1],'
                                      '"why_it_matters":"w"}]'}],
                 "model": "claude-sonnet-5",
                 "usage": {"input_tokens": 10, "output_tokens": 2}}

        class Item:
            id, title, text = "x", "t", "body"
            matched_terms, issue_areas, tier = [], [1], 1

        seen = []
        triage.score_live([Item()], api_key="k",
                          transport=lambda payload, key: reply,
                          usage_sink=lambda u, m: seen.append((u, m)))
        self.assertEqual(seen[0][1], "claude-sonnet-5")
        self.assertEqual(seen[0][0]["input_tokens"], 10)

    def test_the_monday_log_reports_spend(self):
        with open(os.path.join(ROOT, "run_monday.py"), encoding="utf-8") as fh:
            self.assertIn("spend.line(", fh.read())


if __name__ == "__main__":
    unittest.main()
