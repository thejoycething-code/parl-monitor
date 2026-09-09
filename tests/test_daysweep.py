"""Sitting-day sweeps (Christopher, 2026-09-09): sweep what is new, not the whole week.

The weekly pass re-searched ground it had already covered and still left the current day
unswept. This sweeps a day once, remembers it, and never re-checks a recess day.
"""

import datetime
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import daysweep, db, filter as filt  # noqa: E402

MON = datetime.date(2026, 9, 7)      # Monday, both Houses sat
TUE = datetime.date(2026, 9, 8)
SAT = datetime.date(2026, 9, 5)      # a Saturday


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return db.init_db(conn)


class WatermarkTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()

    def test_an_unswept_weekday_is_pending(self):
        self.assertEqual(daysweep.pending_days(self.conn, MON, MON), [MON])

    def test_weekends_are_never_pending_and_cost_no_call(self):
        self.assertEqual(daysweep.pending_days(self.conn, SAT, SAT), [])

    def test_a_recess_day_once_recorded_is_never_rechecked(self):
        for house in ("Commons", "Lords"):
            daysweep.record(self.conn, MON, house, sat=False)
        self.assertEqual(daysweep.pending_days(self.conn, MON, MON), [])

    def test_a_day_swept_long_ago_is_not_swept_again(self):
        old = datetime.date.today() - datetime.timedelta(days=30)
        while old.weekday() >= 5:
            old -= datetime.timedelta(days=1)
        for house in ("Commons", "Lords"):
            daysweep.record(self.conn, old, house, sat=True, found=12)
        self.assertEqual(daysweep.pending_days(self.conn, old, old), [])

    def test_a_day_swept_today_is_looked_at_again_because_hansard_revises_text(self):
        today = datetime.date.today()
        if today.weekday() >= 5:
            self.skipTest("weekend: the recheck window only applies to sitting weekdays")
        for house in ("Commons", "Lords"):
            daysweep.record(self.conn, today, house, sat=True, found=3)
        self.assertEqual(daysweep.pending_days(self.conn, today, today), [today])

    def test_summary_counts_sitting_days_rows_and_gaps(self):
        daysweep.record(self.conn, MON, "Commons", sat=True, found=20)
        daysweep.record(self.conn, MON, "Lords", sat=True, found=5, gaps=[("home education", "HTTP 500")])
        daysweep.record(self.conn, TUE, "Commons", sat=False)
        daysweep.record(self.conn, TUE, "Lords", sat=False)
        got = daysweep.summary(self.conn, MON, TUE)
        self.assertEqual((got["days_recorded"], got["sitting_days"], got["rows"]), (4, 2, 25))
        self.assertEqual(len(got["with_gaps"]), 1)

    def test_a_re_sweep_replaces_the_row_rather_than_adding_one(self):
        daysweep.record(self.conn, MON, "Commons", sat=True, found=3)
        daysweep.record(self.conn, MON, "Commons", sat=True, found=25)
        rows = self.conn.execute("SELECT found FROM sweep_log WHERE day=? AND house='Commons'",
                                 (MON.isoformat(),)).fetchall()
        self.assertEqual([r[0] for r in rows], [25])


class SittingTests(unittest.TestCase):
    def test_an_empty_sections_list_means_the_house_did_not_sit(self):
        class C:
            def get_json(self, url, feed, slug, **kw):
                return []
        self.assertFalse(daysweep.sat_that_day(C(), "Commons", SAT))

    def test_sections_mean_it_sat(self):
        class C:
            def get_json(self, url, feed, slug, **kw):
                return ["Debates", "WrittenStatements"]
        self.assertTrue(daysweep.sat_that_day(C(), "Commons", MON))

    def test_an_api_failure_is_unknown_not_a_recess(self):
        """Recording a failed check as 'did not sit' would bury the day for ever."""
        class C:
            def get_json(self, url, feed, slug, **kw):
                raise RuntimeError("HTTP 500")
        self.assertIsNone(daysweep.sat_that_day(C(), "Commons", MON))


class SweepDayTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        self.tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        self.wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

    def _client(self, sat=True, rows=()):
        text = ("I cannot support the change proposed by the petition. A parental order in a surrogacy "
                "arrangement cannot begin until six weeks after the birth of the child.")
        default = [{"ContributionExtId": "c%d" % i, "MemberId": 5000 + i,
                    "SittingDate": MON.isoformat() + "T00:00:00", "House": "Commons",
                    "DebateSection": "Surrogacy Law and Legal Parenthood", "DebateSectionExtId": "D1",
                    "ContributionText": text} for i in range(4)]

        class C:
            def __init__(self):
                self.calls = []

            def get_json(self, url, feed, slug, **kw):
                self.calls.append(url)
                if "sectionsforday" in url:
                    return ["Debates"] if sat else []
                return {"Results": list(rows) if rows else default}
        return C()

    def test_a_recess_day_records_both_houses_and_searches_nothing(self):
        client = self._client(sat=False)
        cands, written, gaps = daysweep.sweep_day(client, self.conn, MON, ["surrogacy"],
                                                  self.tax, self.wl, log=lambda *_a: None)
        self.assertEqual((cands, written, gaps), ([], 0, []))
        self.assertEqual(sum(1 for u in client.calls if "searchTerm" in u), 0)
        self.assertEqual(daysweep.summary(self.conn, MON, MON)["sitting_days"], 0)

    def test_a_sitting_day_ledgers_the_contributions_and_records_the_watermark(self):
        client = self._client(sat=True)
        cands, written, _gaps = daysweep.sweep_day(client, self.conn, MON, ["surrogacy"],
                                                   self.tax, self.wl, log=lambda *_a: None)
        self.assertEqual(len(cands), 1)
        self.assertEqual(written, 4)
        rows = self.conn.execute("SELECT ref, kind, line, areas FROM mp_events ORDER BY ref").fetchall()
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["kind"], "debate")
        self.assertTrue(rows[0]["ref"].startswith("hansard:"))
        self.assertIn("Surrogacy", rows[0]["line"])
        self.assertEqual(daysweep.summary(self.conn, MON, MON)["rows"], 4)

    def test_the_search_is_paid_for_once_for_both_houses(self):
        client = self._client(sat=True)
        daysweep.sweep_day(client, self.conn, MON, ["surrogacy", "abortion"], self.tax, self.wl, log=lambda *_a: None)
        searches = [u for u in client.calls if "searchTerm" in u]
        self.assertEqual(len(searches), 2)          # two terms, not four
        self.assertEqual(sum(1 for u in client.calls if "sectionsforday" in u), 2)   # one per House

    def test_re_sweeping_the_same_day_does_not_duplicate_ledger_rows(self):
        for _ in range(2):
            daysweep.sweep_day(self._client(sat=True), self.conn, MON, ["surrogacy"],
                               self.tax, self.wl, log=lambda *_a: None)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM mp_events").fetchone()[0], 4)

    def test_a_contribution_whose_member_cannot_be_resolved_is_skipped_not_guessed(self):
        client = self._client(sat=True)
        import src.members as members
        original = members.resolve
        members.resolve = lambda conn, cl, mid: None
        try:
            _c, written, _g = daysweep.sweep_day(client, self.conn, MON, ["surrogacy"],
                                                 self.tax, self.wl, log=lambda *_a: None)
        finally:
            members.resolve = original
        self.assertEqual(written, 0)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM mp_events").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
