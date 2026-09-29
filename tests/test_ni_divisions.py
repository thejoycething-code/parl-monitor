"""tools/ni_divisions.py: the 2011 backfill options (29 September 2026).

--since fetches a year per request, and --classified harvests member votes for
divisions the classifier put on our ground, which is the only way a motion
(not a bill) such as "Marriage Equality" gets its roll-call.
"""

import datetime
import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "ni_divisions", os.path.join(ROOT, "tools", "ni_divisions.py"))
nd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nd)

D = datetime.date


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return conn


class YearWindowTests(unittest.TestCase):
    def test_windows_cut_at_calendar_years_and_cover_every_day(self):
        w = nd.year_windows(D(2011, 3, 5), D(2013, 2, 1))
        self.assertEqual(w, [(D(2011, 3, 5), D(2011, 12, 31)),
                             (D(2012, 1, 1), D(2012, 12, 31)),
                             (D(2013, 1, 1), D(2013, 2, 1))])

    def test_a_window_inside_one_year_is_one_request(self):
        self.assertEqual(nd.year_windows(D(2026, 1, 2), D(2026, 9, 29)),
                         [(D(2026, 1, 2), D(2026, 9, 29))])


class ClassifiedIdsTests(unittest.TestCase):
    def _div(self, conn, doc_id, areas):
        conn.execute("INSERT INTO ni_divisions (doc_id, subject, dated, areas, "
                     "first_seen, last_seen) VALUES (?, 's', '2015-04-27', ?, "
                     "'d', 'd')", (doc_id, areas))

    def test_only_divisions_on_our_ground_and_never_a_struck_one(self):
        conn = store()
        self._div(conn, "1", '[9]')
        self._div(conn, "2", '[]')
        self._div(conn, "3", None)
        self._div(conn, "4", '[7]')
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "config"))
            with open(os.path.join(tmp, "config", "nia_votes.yaml"), "w") as fh:
                fh.write("divisions:\n  - key: '4'\n    not_ours: true\n")
            old, nd.ROOT = nd.ROOT, tmp
            try:
                self.assertEqual(nd.classified_ids(conn), {"1"})
            finally:
                nd.ROOT = old


if __name__ == "__main__":
    unittest.main()
