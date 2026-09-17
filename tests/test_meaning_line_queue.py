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


class EuropeanQueueTests(unittest.TestCase):
    """The EU arm ranks differently on purpose: every MEP on the roster still
    sits, so turnout ranks nothing, and one report can generate dozens of
    splits (87 for the 15 Sept Democracy Shield report)."""

    def setUp(self):
        self.conn = db.init_db(sqlite3.connect(":memory:"))
        self.conn.row_factory = sqlite3.Row
        now = "2026-09-17"
        divs = [
            # vote_id, label, favor, against, abstention, voters
            ("SIGNED", "An old vote we already signed", 5, 1, 0, ["1", "2", "3"]),
            ("WHOLE", "Big report on free speech", 40, 10, 2, ["1", "2", "3", "4", "5"]),
            ("SPLIT", "Big report on free speech - Recital E", 20, 30, 1, ["4", "5"]),
            ("SMALL", "A narrow motion", 3, 2, 0, ["6"]),
        ]
        for vid, label, f, a, ab, voters in divs:
            self.conn.execute(
                "INSERT INTO eu_divisions (vote_id, sitting_id, date, label, "
                "favor, against, abstention, areas, matched_terms, tier, "
                "first_seen, last_seen) VALUES (?,'s','2026-09-15',?,?,?,?,"
                "'[7]','[]',1,?,?)", (vid, label, f, a, ab, now, now))
            for pid in voters:
                self.conn.execute("INSERT INTO eu_votes (vote_id, person_id, "
                                  "position) VALUES (?,?,'favor')", (vid, pid))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def _run(self, signed_yaml):
        import tempfile, yaml as y
        d = tempfile.mkdtemp()
        cfg = os.path.join(d, "eu_divisions.yaml")
        with open(cfg, "w") as fh:
            y.safe_dump({"divisions": signed_yaml}, fh)
        real = q.ROOT
        q.ROOT = d
        os.makedirs(os.path.join(d, "config"), exist_ok=True)
        os.rename(cfg, os.path.join(d, "config", "eu_divisions.yaml"))
        try:
            return q.european(self.conn)
        finally:
            q.ROOT = real

    def test_splits_of_one_report_are_grouped_behind_the_whole_text_vote(self):
        rows, total = self._run({})
        self.assertEqual(total, 4, "every unsigned roll call is counted")
        top = rows[0][0]
        self.assertEqual(top[2], "WHOLE", "the highest-turnout member of the family leads")
        self.assertEqual(rows[0][1], 1, "its one split is reported, not listed")

    def test_ranking_is_marginal_placement_not_turnout(self):
        """WHOLE signed places MEPs 1-5. Its own 50-vote split now reaches nobody
        new, while a five-vote motion reaching MEP 6 places one. The small one
        wins, which is the whole reason this does not rank on turnout."""
        rows, _ = self._run({"WHOLE": {"signed_off": True, "our_side": "favor"}})
        by_id = {r[0][2]: r[0][0] for r in rows}
        self.assertEqual(rows[0][0][2], "SMALL", [r[0][2] for r in rows])
        self.assertEqual(by_id["SMALL"], 1)
        self.assertEqual(by_id["SPLIT"], 0, "its voters are already placed")

    def test_a_signed_division_never_appears_in_the_queue(self):
        rows, total = self._run({"SIGNED": {"signed_off": True, "our_side": "favor"}})
        self.assertNotIn("SIGNED", [r[0][2] for r in rows])
        self.assertEqual(total, 3)

    def test_an_unsigned_entry_in_the_config_still_queues(self):
        rows, total = self._run({"WHOLE": {"signed_off": False, "our_side": None}})
        self.assertIn("WHOLE", [r[0][2] for r in rows])
        self.assertEqual(total, 4)
