"""The EU swept per sitting day (17 September 2026).

Westminster has been swept per sitting day since 9 September; the EU ran weekly,
so a Tuesday plenary waited until Saturday. On 17 September the 15 September
sitting -- 87 roll calls on our ground -- sat uncollected for two days because
the weekly had also been cancelled. Nothing here touches the network.
"""

import datetime
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, daysweep, eudaysweep  # noqa: E402

D = datetime.date


class FakeClient:
    """Serves one year's meetings calendar; counts calls so caching is testable."""

    def __init__(self, dates, fail=False):
        self.dates, self.fail, self.calls = dates, fail, 0

    def get_json(self, url, feed, slug, timeout=None, archive=True):
        self.calls += 1
        if self.fail:
            raise RuntimeError("calendar down")
        return {"data": [{"activity_date": d} for d in self.dates]}


def store():
    conn = db.init_db(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    return conn


class CalendarTests(unittest.TestCase):
    def test_a_year_of_sitting_dates_costs_one_call_and_is_cached(self):
        c = FakeClient(["2026-09-15", "2026-09-16"])
        cache = {}
        self.assertEqual(eudaysweep.sitting_dates(c, 2026, cache), {"2026-09-15", "2026-09-16"})
        eudaysweep.sitting_dates(c, 2026, cache)
        self.assertEqual(c.calls, 1, "the second lookup must come from the cache")

    def test_a_broken_calendar_is_not_a_recess(self):
        """Returning an empty set would record every day as 'did not sit' for ever."""
        self.assertIsNone(eudaysweep.sitting_dates(FakeClient([], fail=True), 2026, {}))


class SweepTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()

    def tearDown(self):
        self.conn.close()

    def test_a_non_sitting_day_is_recorded_and_never_asked_about_again(self):
        c = FakeClient(["2026-09-15"])
        sat, m, o, g = eudaysweep.sweep_day(self.conn, c, D(2026, 9, 14), log=lambda *a: None, cache={})
        self.assertIs(sat, False)
        self.assertEqual((m, o, g), (0, 0, 0))
        self.assertEqual(eudaysweep.pending_days(self.conn, D(2026, 9, 14), D(2026, 9, 14),
                                                 recheck_days=0), [])

    def test_a_calendar_failure_leaves_the_day_pending(self):
        c = FakeClient([], fail=True)
        sat, _m, _o, gaps = eudaysweep.sweep_day(self.conn, c, D(2026, 9, 14), log=lambda *a: None, cache={})
        self.assertIsNone(sat)
        self.assertEqual(gaps, 1)
        self.assertEqual(eudaysweep.pending_days(self.conn, D(2026, 9, 14), D(2026, 9, 14)),
                         [D(2026, 9, 14)], "a failure must not be remembered as a recess")

    def test_a_swept_sitting_is_looked_at_again_only_while_it_is_recent(self):
        daysweep.record(self.conn, D(2026, 9, 15), eudaysweep.HOUSE, sat=True,
                        source=eudaysweep.SOURCE)
        self.assertEqual(eudaysweep.pending_days(self.conn, D(2026, 9, 15), D(2026, 9, 15),
                                                 recheck_days=0), [],
                         "settled: roll calls have published")
        today = datetime.date.today()
        daysweep.record(self.conn, today, eudaysweep.HOUSE, sat=True, source=eudaysweep.SOURCE)
        self.assertEqual(eudaysweep.pending_days(self.conn, today, today), [today],
                         "today's sitting is revisited: roll calls publish late")

    def test_weekends_are_not_skipped_by_the_clock(self):
        """Hansard's sweep skips Saturdays without a call. The Parliament's own
        calendar decides here, because its sittings do not follow a week."""
        sat_day = D(2026, 9, 19)                     # a Saturday
        c = FakeClient([sat_day.isoformat()])
        self.assertIn(sat_day, eudaysweep.pending_days(self.conn, sat_day, sat_day))
        self.assertEqual(eudaysweep.sitting_dates(c, 2026, {}), {sat_day.isoformat()})

    def test_the_log_is_shared_with_hansard_under_its_own_source(self):
        daysweep.record(self.conn, D(2026, 9, 15), eudaysweep.HOUSE, sat=True,
                        found=87, source=eudaysweep.SOURCE)
        daysweep.record(self.conn, D(2026, 9, 15), "Commons", sat=True, found=3)
        s = eudaysweep.summary(self.conn, D(2026, 9, 1), D(2026, 9, 30))
        self.assertEqual((s["sittings"], s["found"]), (1, 87), "Hansard's row must not be counted")


if __name__ == "__main__":
    unittest.main()
