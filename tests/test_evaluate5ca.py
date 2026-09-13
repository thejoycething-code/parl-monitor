"""5CA Evaluate: the pre-vote sheet against the lobbies. Pure functions, no store."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import evaluate5ca as ev  # noqa: E402


def row(mid, col, **flags):
    r = {"member_id": mid, "decision_maker": "M%d" % mid, "column": col, "wavering": False, "conflict": False, "targeted": []}
    r.update(flags)
    return r


class EvaluateTests(unittest.TestCase):
    def test_columns_flags_misses_and_gains(self):
        rows = [row(1, "++"), row(2, "+"), row(3, "0"), row(4, "-", wavering=True), row(5, "--"), row(6, "--", conflict=True), row(7, "++")]
        votes = {1: "no", 2: "aye", 3: "no", 4: "no", 5: "aye", 6: "absent"}       # our side is NO; 7 did not vote
        rec = ev.evaluate(rows, votes, "no")
        self.assertEqual(rec["columns"]["++"], {"n": 2, "ours": 1, "against": 0, "abstained": 0, "silent": 1})
        self.assertEqual(rec["columns"]["+"], {"n": 1, "ours": 0, "against": 1, "abstained": 0, "silent": 0})
        self.assertEqual([e["member_id"] for e in rec["misses"]], [2])            # placed +, voted Aye
        self.assertEqual([e["member_id"] for e in rec["gains"]], [4])             # placed -, voted No, and was flagged wavering
        self.assertEqual(rec["gains"][0]["flags"], ["wavering"])
        # among those placed against us who voted or were absent: flagged (4 moved, 6 abstained) 2/2; unflagged (5 voted Aye) 0/1
        self.assertEqual(rec["moved_from_theirs"], {"flagged": [2, 2], "unflagged": [0, 1]})
        self.assertEqual(rec["missing_from_theirs"], {"flagged": [2, 2], "unflagged": [0, 1]})
        self.assertEqual(rec["flags"]["wavering"], {"n": 1, "ours": 1, "against": 0, "abstained": 0, "silent": 0})
        self.assertEqual(rec["flags"]["none"]["n"], 5)
        self.assertEqual((rec["voted"], rec["ours"], rec["voters_placed"]), (5, 3, 6))

    def test_staying_away_counts_as_movement_in_the_missing_measure(self):
        rows = [row(1, "--", wavering=True), row(2, "--"), row(3, "--")]
        rec = ev.evaluate(rows, {2: "aye"}, "no")           # 1 and 3 did not vote
        self.assertEqual(rec["moved_from_theirs"], {"flagged": [0, 0], "unflagged": [0, 1]})
        self.assertEqual(rec["missing_from_theirs"], {"flagged": [1, 1], "unflagged": [1, 2]})

    def test_both_lobbies_is_an_abstention_not_a_vote_either_way(self):
        rec = ev.evaluate([row(1, "--")], {1: "both"}, "no")
        self.assertEqual(rec["columns"]["--"]["abstained"], 1)
        self.assertEqual(rec["gains"], [])

    def test_render_reads_as_a_sheet(self):
        rec = ev.evaluate([row(1, "++"), row(2, "-")], {1: "no", 2: "no"}, "no")
        md = ev.render(rec, "Assisted suicide: Second Reading", "2026-09-11", 2428, "2026-09-10")
        self.assertIn("| ++ | 1 | 1 | 0 | 0 | 0 | 100% |", md)
        self.assertIn("## Gains: placed against us, voted our way (1)", md)
        self.assertIn("* M2 at -", md)


if __name__ == "__main__":
    unittest.main()
