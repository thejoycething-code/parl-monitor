"""5CA Evaluate phase: predictions snapshotted, real votes scored against them."""

import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import db, evaluate, intel


def fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return db.init_db(conn)


def prediction(mid, name, column, n_events=3):
    return {"member_id": mid, "decision_maker": name, "column": column,
            "n_events": n_events}


class SnapshotTests(unittest.TestCase):
    def test_prediction_is_kept_so_it_can_be_scored_later(self):
        conn = fresh_conn()
        n = evaluate.open_campaign(conn, "tia-3r", 2, "Assisted dying", "2026-09-01",
                                   [prediction(1, "Ally MP", "++"),
                                    prediction(2, "Opponent MP", "--")])
        self.assertEqual(n, 2)
        rows = conn.execute("SELECT member_id, placement FROM ca_predictions "
                            "ORDER BY member_id").fetchall()
        self.assertEqual([(r["member_id"], r["placement"]) for r in rows],
                         [(1, "++"), (2, "--")])

    def test_reopening_replaces_the_snapshot(self):
        conn = fresh_conn()
        evaluate.open_campaign(conn, "c", 2, "L", "2026-09-01", [prediction(1, "A", "++")])
        evaluate.open_campaign(conn, "c", 2, "L", "2026-09-08", [prediction(1, "A", "-")])
        row = conn.execute("SELECT placement FROM ca_predictions").fetchone()
        self.assertEqual(row["placement"], "-")

    def test_our_side_must_be_stated(self):
        conn = fresh_conn()
        with self.assertRaises(ValueError):
            evaluate.record_outcome(conn, "c", "div:c1", "T", "2026-09-01", "yes")


class ScorecardTests(unittest.TestCase):
    """The Terminally Ill Adults (End of Life) Bill shape: voting NO is our
    side, so a tool assuming Aye-is-good would call every ally a defector."""

    def setUp(self):
        self.conn = fresh_conn()
        evaluate.open_campaign(
            self.conn, "tia", 2, "Assisted dying", "2026-09-01",
            [prediction(1, "Held Ally", "++"), prediction(2, "Defecting Ally", "+"),
             prediction(3, "Held Opponent", "--"), prediction(4, "Converted Opponent", "-"),
             prediction(5, "Unknown Who Came", "0", n_events=0),
             prediction(6, "Unknown Who Did Not Vote", "0", n_events=0)])
        # our side is NO
        for mid, side in ((1, "no"), (2, "aye"), (3, "aye"), (4, "no"), (5, "no")):
            intel.record_event(self.conn, mid, "2026-09-10", "vote",
                               "div:c900:" + side, "Voted {0}: TIA Bill".format(side),
                               areas=[2])
        evaluate.record_outcome(self.conn, "tia", "div:c900",
                                "Terminally Ill Adults (End of Life) Bill: Third Reading",
                                "2026-09-10", "no")
        self.result = evaluate.evaluate(self.conn, "tia")

    def by_name(self, name):
        return next(r for r in self.result["rows"] if r["decision_maker"] == name)

    def test_alignment_respects_which_side_was_ours(self):
        self.assertEqual(self.by_name("Held Ally")["alignment"], "with us")
        self.assertEqual(self.by_name("Defecting Ally")["alignment"], "against us")
        self.assertEqual(self.by_name("Held Opponent")["alignment"], "against us")
        self.assertEqual(self.by_name("Converted Opponent")["alignment"], "with us")

    def test_literal_vote_stays_bill_relative_for_the_sheet(self):
        self.assertEqual(self.by_name("Held Ally")["vote"], "N")       # voted No
        self.assertEqual(self.by_name("Defecting Ally")["vote"], "Y")  # voted Aye
        self.assertEqual(self.by_name("Unknown Who Did Not Vote")["vote"], "0")

    def test_surprises_are_the_point(self):
        surprises = {r["decision_maker"]: r["surprise"]
                     for r in self.result["rows"] if r["surprise"]}
        self.assertEqual(set(surprises), {"Defecting Ally", "Converted Opponent",
                                          "Unknown Who Came"})
        self.assertIn("no prior record", surprises["Unknown Who Came"])

    def test_accuracy_counts_only_placements_a_vote_tested(self):
        s = self.result["summary"]
        # Four placed members voted; two held (Held Ally, Held Opponent).
        self.assertEqual(s["placement_tested"], 4)
        self.assertEqual(s["placement_held"], 2)
        self.assertEqual(s["accuracy"], 50)

    def test_absence_is_recorded_but_not_scored_as_a_position(self):
        row = self.by_name("Unknown Who Did Not Vote")
        self.assertEqual(row["alignment"], "no vote recorded")
        self.assertIsNone(row["surprise"])

    def test_no_outcome_yet_scores_nothing_rather_than_guessing(self):
        conn = fresh_conn()
        evaluate.open_campaign(conn, "later", 2, "L", "2026-09-01",
                               [prediction(1, "A", "++")])
        result = evaluate.evaluate(conn, "later")
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["outcomes"], [])

    def test_a_vote_after_the_snapshot_scores_as_a_real_forecast(self):
        # setUp opens on 2026-09-01 and the division is 2026-09-10.
        self.assertFalse(self.result["summary"]["circular"])

    def test_a_vote_before_the_snapshot_is_flagged_as_circular(self):
        """The first real run scored 100%, because the division it scored
        against was part of the evidence the placements came from. Alignment
        counts stay valid; the percentage must not be read as foresight."""
        conn = fresh_conn()
        intel.record_event(conn, 1, "2025-06-20", "vote", "div:c9:no",
                           "Voted No: TIA Bill", areas=[2])
        evaluate.open_campaign(conn, "hindsight", 2, "L", "2026-08-06",
                               [prediction(1, "A", "++")])
        evaluate.record_outcome(conn, "hindsight", "div:c9", "TIA", "2025-06-20", "no")
        summary = evaluate.evaluate(conn, "hindsight")["summary"]
        self.assertTrue(summary["circular"])
        self.assertEqual(summary["accuracy"], 100)   # true, and meaningless

    def test_unknown_campaign_returns_none(self):
        self.assertIsNone(evaluate.evaluate(self.conn, "nope"))


class MultiDivisionTests(unittest.TestCase):
    def test_split_voting_across_nominated_divisions_is_not_forced(self):
        conn = fresh_conn()
        evaluate.open_campaign(conn, "c", 2, "L", "2026-09-01", [prediction(1, "Split MP", "++")])
        intel.record_event(conn, 1, "2026-09-10", "vote", "div:c1:no", "Voted No: A", areas=[2])
        intel.record_event(conn, 1, "2026-09-11", "vote", "div:c2:aye", "Voted Aye: B", areas=[2])
        evaluate.record_outcome(conn, "c", "div:c1", "A", "2026-09-10", "no")
        evaluate.record_outcome(conn, "c", "div:c2", "B", "2026-09-11", "no")
        row = evaluate.evaluate(conn, "c")["rows"][0]
        self.assertEqual(row["alignment"], "split")
        self.assertEqual(row["vote"], "split")


if __name__ == "__main__":
    unittest.main()
