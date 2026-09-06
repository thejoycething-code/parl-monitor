"""The devolved judge runs in the Monday publish (Christopher, 2026-09-06).

Not in the three devolved weeklies, which carry no secrets by design.
Before the edition renders, isolated, and fenced by a wall-clock budget
because the Monday publish has 30 minutes for everything and a first
pass is ~79 API calls.
"""

import os
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import triage


def items(n):
    return [triage.TriageItem(id="t:%d" % i, title="x", text="x", tier=2,
                              issue_areas=[1], watchlist_hit=False)
            for i in range(n)]


class BudgetTests(unittest.TestCase):
    def test_the_slicer_stops_when_the_budget_is_spent_and_says_so(self):
        logged = []

        def slow(chunk, api_key, usage_sink=None):
            time.sleep(0.05)
            return [triage.TriageResult(id=i.id, score=1, areas=[1],
                                        why_it_matters="w") for i in chunk]
        orig = triage.score_live
        triage.score_live = slow
        try:
            out = triage.score_in_slices(items(12), "k", slice_size=4,
                                         log=logged.append, budget_seconds=0.06)
        finally:
            triage.score_live = orig
        self.assertLess(len(out), 12, "the budget did not stop it")
        self.assertTrue(any("[budget]" in l and "left unscored" in l for l in logged),
                        "stopping early must be reported")

    def test_no_budget_means_the_old_behaviour(self):
        orig = triage.score_live
        triage.score_live = lambda chunk, api_key, usage_sink=None: [
            triage.TriageResult(id=i.id, score=1, areas=[1], why_it_matters="w")
            for i in chunk]
        try:
            out = triage.score_in_slices(items(5), "k", slice_size=2,
                                         log=lambda *a: None)
        finally:
            triage.score_live = orig
        self.assertEqual(len(out), 5)


class WiringTests(unittest.TestCase):
    def setUp(self):
        self.src = open(os.path.join(ROOT, "run_monday.py"), encoding="utf-8").read()

    def test_the_judge_runs_before_the_edition_renders(self):
        """Its why-lines have to be IN the edition."""
        self.assertLess(self.src.index('"devolved_triage.py"'),
                        self.src.index("run_weekly.render_edition(week"))

    def test_it_is_fenced_twice(self):
        block = self.src[self.src.index('"devolved_triage.py"'):][:1500]
        self.assertIn('"--budget-seconds", "480"', block)
        self.assertIn("timeout=660", block)
        self.assertIn("TimeoutExpired", block)

    def test_it_can_never_take_the_publish_down(self):
        block = self.src[self.src.index("THE DEVOLVED JUDGE"):][:2500]
        self.assertIn("edition unaffected", block)

    def test_the_weeklies_still_carry_no_secrets(self):
        """The reason it lives in the Monday publish at all."""
        for wf in ("sd-weekly", "sp-weekly", "ni-weekly"):
            src = open(os.path.join(ROOT, ".github", "workflows", wf + ".yml"),
                       encoding="utf-8").read()
            self.assertNotIn("ANTHROPIC_API_KEY", src, wf)
            self.assertNotIn("devolved_triage", src, wf)

    def test_the_tool_honours_the_budget_flag(self):
        src = open(os.path.join(ROOT, "tools", "devolved_triage.py"),
                   encoding="utf-8").read()
        self.assertIn("--budget-seconds", src)
        self.assertIn("budget_seconds=budget", src)


if __name__ == "__main__":
    unittest.main()
