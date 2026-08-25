"""Ranking the meaning-line backlog by what it would actually buy.

A division with no line renders as evidence and places nobody. The gaps are
worth wildly different amounts -- some place sixty sitting members, some
three -- so the queue ranks by placement value rather than listing a chore.
"""

import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db
import meaning_line_queue as q


class HolyroodQueueTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(sqlite3.connect(":memory:"))
        self.conn.row_factory = sqlite3.Row
        now = "2026-08-24"
        for key, ref, tier in (("k1", "S6M-1", 1), ("k2", "S6M-2", 2)):
            self.conn.execute(
                "INSERT INTO sp_divisions (key, reference, title, dated, "
                "source, areas, tier, first_seen, last_seen) "
                "VALUES (?,?,?,?,'votesmotion','[2]',?,?,?)",
                (key, ref, "A division", "2026-01-01", tier, now, now))
        for pid, current in (("1", 1), ("2", 1), ("3", 0)):
            self.conn.execute(
                "INSERT INTO sp_members (person_id, name, is_current, "
                "first_seen, last_seen) VALUES (?,?,?,?,?)",
                (pid, "M" + pid, current, now, now))
            self.conn.execute(
                "INSERT INTO sp_votes (division_key, person_id, vote) "
                "VALUES ('k1',?,'Yes')", (pid,))

    def tearDown(self):
        self.conn.close()

    def test_only_SITTING_members_count(self):
        """A division whose voters have all left places nobody now, whatever
        it meant -- so it must not outrank a live one."""
        rows = q.holyrood(self.conn, entries={})
        by_ref = {r[2]: r[0] for r in rows}
        self.assertEqual(by_ref["S6M-1"], 2, "the departed member must not "
                                             "inflate the score")

    def test_tier_2_is_included_and_marked(self):
        """The monitor hides tier 2, but the 5CA places on any confirmed
        line whatever the tier -- excluding them would hide real
        opportunities behind a display rule."""
        rows = q.holyrood(self.conn, entries={})
        wheres = {r[2]: r[1] for r in rows}
        self.assertEqual(wheres["S6M-2"], "Holyrood t2")
        self.assertEqual(wheres["S6M-1"], "Holyrood")

    def test_a_division_that_already_has_a_line_drops_out(self):
        rows = q.holyrood(self.conn, entries={"S6M-1": {"aye": 1}})
        self.assertNotIn("S6M-1", [r[2] for r in rows])

    def test_hidden_areas_do_not_qualify_a_division(self):
        self.conn.execute("UPDATE sp_divisions SET areas='[11]'")
        self.assertEqual(q.holyrood(self.conn, entries={}), [])


if __name__ == "__main__":
    unittest.main()
