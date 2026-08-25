"""The 5CA's Evaluate phase (Christopher, 2026-08-24).

Plan says where a member is thought to stand; Evaluate records how they
actually voted. Most of the design is in what counts as a MISS, so that is
most of what these tests pin -- a hit rate is a number people quote, and a
generous denominator would flatter it.
"""

import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, stance
import evaluate_5ca as ev


class DirectionTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(sqlite3.connect(":memory:"))
        self.conn.row_factory = sqlite3.Row
        stance.ensure_table(self.conn)

    def _score(self, ref, value):
        self.conn.execute(
            "INSERT INTO stance (ref, stance, why, scored_at) VALUES (?,?,?,?)",
            (ref, value, "", "2026-01-01"))

    def test_direction_comes_from_the_divisions_own_scored_stance(self):
        self._score("div:c1:aye", -2)
        self._score("div:c1:no", 2)
        self.assertEqual(ev.direction(self.conn, "div:c1"), -1,
                         "a NO is our side when an aye scores negative")

    def test_an_unscored_division_refuses_rather_than_guessing(self):
        self.assertIsNone(ev.direction(self.conn, "div:c9"))

    def test_a_procedural_division_scored_zero_has_no_direction(self):
        self._score("div:c2:aye", 0)
        self._score("div:c2:no", 0)
        self.assertIsNone(ev.direction(self.conn, "div:c2"))


class ScoringRuleTests(unittest.TestCase):
    """The rules that decide the denominator."""

    def setUp(self):
        self.conn = db.init_db(sqlite3.connect(":memory:"))
        self.conn.row_factory = sqlite3.Row
        stance.ensure_table(self.conn)
        for ref, val in (("div:c1:aye", -2), ("div:c1:no", 2)):
            self.conn.execute(
                "INSERT INTO stance (ref, stance, why, scored_at) "
                "VALUES (?,?,?,?)", (ref, val, "", "2026-01-01"))
        # four members: an ally who votes with us, an ally who defects,
        # someone with no evidence at all, and an ally who is absent.
        for mid, name in (("1", "Ally"), ("2", "Defector"),
                          ("3", "Unknown"), ("4", "Absent")):
            self.conn.execute(
                "INSERT INTO members (id, name, party, seat, house, "
                "current_mp) VALUES (?,?,?,?,?,1)",
                (mid, name, "P", "S", "Commons"))
        # prior evidence (BEFORE the division) for 1, 2 and 4 only
        for mid in ("1", "2", "4"):
            self.conn.execute(
                "INSERT INTO mp_events (member_id, date, kind, ref, line, "
                "areas) VALUES (?,?,?,?,?,?)",
                (mid, "2025-01-01", "debate", "h:" + mid, "Spoke", "[2]"))
            self.conn.execute(
                "INSERT INTO stance (ref, stance, why, scored_at) "
                "VALUES (?,?,?,?)", ("h:" + mid, 2, "", "2025-01-01"))
        # the division itself: 1 votes no (ours), 2 votes aye, 4 absent
        for mid, lobby in (("1", "no"), ("2", "aye"), ("3", "no")):
            self.conn.execute(
                "INSERT INTO mp_events (member_id, date, kind, ref, line, "
                "areas) VALUES (?,?,?,?,?,?)",
                (mid, "2026-01-01", "vote", "div:c1:" + lobby, "Voted", "[2]"))
        self.conn.commit()

    def _outcomes(self):
        results, meta = ev.evaluate(self.conn, "div:c1", 2)
        self.assertNotIn("error", meta)
        # member_id comes back with the column's own affinity (int),
        # so key on str to compare with the fixture ids.
        return {str(r["member_id"]): r["outcome"] for r in results}

    def test_an_ally_who_votes_with_us_is_a_hit(self):
        self.assertEqual(self._outcomes()["1"], "hit")

    def test_an_ally_who_votes_against_us_is_a_miss(self):
        self.assertEqual(self._outcomes()["2"], "miss")

    def test_a_member_with_no_evidence_is_NOT_a_miss(self):
        """Zero means 'no evidence', an honest absence of prediction.
        Counting it as wrong would punish the sheet for admitting what it
        does not know -- and would sink the hit rate on a 650-seat roster
        where most members never speak on an issue."""
        self.assertEqual(self._outcomes()["3"], "no-prediction")

    def test_an_absence_is_NOT_a_miss(self):
        """Paired, ill or abroad contradicts nothing."""
        self.assertEqual(self._outcomes()["4"], "no-vote")

    def test_the_prediction_ignores_the_vote_being_evaluated(self):
        """After the vote the vote itself is evidence; a sheet that counted
        it would be marking its own homework."""
        results, _meta = ev.evaluate(self.conn, "div:c1", 2)
        by_id = {str(r["member_id"]): r for r in results}
        self.assertEqual(by_id["3"]["predicted"], "0",
                         "member 3's only evidence IS the division")

    def test_an_unscored_division_reports_an_error_not_a_hit_rate(self):
        _results, meta = ev.evaluate(self.conn, "div:c99", 2)
        self.assertIn("error", meta)


if __name__ == "__main__":
    unittest.main()
