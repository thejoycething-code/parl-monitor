"""Decisions needed (Christopher, 2026-09-07: "Build the decisions block")."""

import datetime
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import decisions, digest  # noqa: E402

LOG = [{"id": "send", "decision": "Submit a SEND response?", "about": "SEND reform",
        "owner": None, "decide_by": "2026-09-14", "opened": "2026-09-07", "status": "open"},
       {"id": "late", "decision": "An overdue one", "about": "Weddings", "owner": "Christopher",
        "decide_by": "2026-09-01", "status": "open"},
       {"id": "done", "decision": "Respond to foster care standards?", "about": "foster care",
        "owner": "Caroline", "status": "decided", "decided_on": "2026-09-03", "outcome": "No response"},
       {"id": "old", "decision": "Ancient", "about": "x", "status": "decided", "decided_on": "2026-06-01",
        "outcome": "yes"}]


class CollectTests(unittest.TestCase):
    def test_open_rows_count_down_and_mark_overdue(self):
        rows = decisions.collect(LOG, [], "2026-09-07")
        by = {r["id"]: r for r in rows["open"]}
        self.assertEqual(by["send"]["days_left"], 7)
        self.assertFalse(by["send"]["overdue"])
        self.assertEqual(by["late"]["days_left"], -6)
        self.assertTrue(by["late"]["overdue"])
        self.assertEqual([r["id"] for r in rows["open"]], ["late", "send"])   # most urgent first

    def test_decided_shows_for_two_weeks_then_drops(self):
        rows = decisions.collect(LOG, [], "2026-09-07")
        self.assertEqual([r["id"] for r in rows["decided"]], ["done"])
        later = decisions.collect(LOG, [], "2026-09-28")
        self.assertEqual(later["decided"], [])

    def test_an_unlogged_open_decision_is_surfaced_and_a_logged_one_is_not(self):
        mentions = [("SEND reform: education otherwise than at school", "A supporter response is still an open decision."),
                    ("Tying the Knot: weddings law", "Campaign live; response push through recess."),
                    ("Improving help and child protection", "Whether to respond is undecided."),
                    ("Improving help and child protection", "Whether to respond is undecided.")]   # duplicate
        rows = decisions.collect(LOG, mentions, "2026-09-07")
        self.assertEqual([u["title"] for u in rows["unlogged"]], ["Improving help and child protection"])

    def test_the_real_log_loads_and_names_the_send_decision(self):
        log = decisions.load()
        self.assertTrue(any(d["id"] == "send-eotas-response" for d in log))
        for d in log:
            self.assertIn(d.get("status", "open"), ("open", "decided"))


class RenderTests(unittest.TestCase):
    def test_block_has_table_decided_list_and_unlogged_prompt(self):
        rows = decisions.collect(LOG, [("Improving help and child protection", "undecided")], "2026-09-07")
        md = decisions.render(rows)
        self.assertIn("## Decisions needed", md)
        self.assertIn("| Submit a SEND response? | *unassigned* | 2026-09-14 | 7 days left |", md)
        self.assertIn("| An overdue one | Christopher | 2026-09-01 | **OVERDUE by 6 days** |", md)
        self.assertIn("- Respond to foster care standards? — **No response** (2026-09-03, Caroline)", md)
        self.assertIn("not yet logged in config/decisions.yaml", md)
        self.assertIn("- Improving help and child protection", md)

    def test_nothing_to_decide_renders_nothing(self):
        self.assertIsNone(decisions.render({"open": [], "decided": [], "unlogged": []}))
        self.assertIsNone(decisions.render(None))

    def test_it_sits_directly_under_top_lines(self):
        e = digest.Edition(week_commencing="2026-09-07", number=6, mode="normal")
        e.board_rows = []
        e.top_lines = [digest.Line("Something urgent", 3)]
        e.decisions = decisions.collect(LOG, [], "2026-09-07")
        md = digest.render(e)
        self.assertLess(md.index("## Top lines"), md.index("## Decisions needed"))
        self.assertLess(md.index("## Decisions needed"), md.index("## Active bills board"))

    def test_the_weekly_wires_it(self):
        src = open(os.path.join(ROOT, "run_weekly.py"), encoding="utf-8").read()
        self.assertIn("edition.decisions = _decisions.collect(", src)
        self.assertIn("edition.deadlines if d.get(\"why\")", src)   # consultation why-lines are checked too


if __name__ == "__main__":
    unittest.main()
