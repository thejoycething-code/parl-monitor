"""Royal Assent verification top line: fresh assents render, stale ones don't."""

import datetime
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import run_weekly
from src import board, filter as filt

WATCHLIST = os.path.join(ROOT, "config", "watchlist.yaml")


def closure(bill_id, note):
    return board.BoardRow(bill_id, "An Act", None, "Unassigned", "Royal Assent",
                          "-", "closed", board.ROYAL_ASSENT, closed_note=note,
                          triggers=["acts_watch", "legislation_check"])


class AssentToplineTests(unittest.TestCase):
    def setUp(self):
        self.wl = filt.load_watchlist(WATCHLIST)

    def test_stale_assent_is_suppressed(self):
        # CPA (bill 3938) assent 2026-04-29 vs edition w/c 2026-08-03: old news.
        row = closure(3938, "Royal Assent 2026-04-29")
        line = run_weekly.assent_topline(None, self.wl, row, datetime.date(2026, 8, 3))
        self.assertIsNone(line)

    def test_fresh_assent_renders_with_verification(self):
        row = closure(3938, "Royal Assent 2026-07-27")  # within a week of edition
        status = mock.Mock(note="in force at royal assent")
        with mock.patch.object(run_weekly.legislation, "fetch_section_status", return_value=status):
            line = run_weekly.assent_topline(mock.Mock(), self.wl, row, datetime.date(2026, 8, 3))
        self.assertIsNotNone(line)
        self.assertIn("s.241 in force at royal assent", line.text)
        self.assertIn("s.242", line.text)

    def test_unwatched_act_produces_no_line(self):
        row = closure(9999, "Royal Assent 2026-08-01")
        self.assertIsNone(run_weekly.assent_topline(None, self.wl, row, datetime.date(2026, 8, 3)))


if __name__ == "__main__":
    unittest.main()
