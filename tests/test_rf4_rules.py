"""RF4 scoring-rule summaries in generated briefs.

Agreed with the UK team (October 2026): each Red Fox Four question carries the
rule it is scored by, so Plan and Evaluate use the same rule. Scores stay
blank (the campaigner's judgement), and the summaries carry nothing internal:
this repo is public.
"""

from __future__ import annotations

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import make_briefs as mb


class RF4RulesTest(unittest.TestCase):

    def test_every_question_has_a_rule(self):
        self.assertEqual([code for code, _ in mb.RF4], list(mb.RF4_RULES))

    def test_rules_follow_each_hint_in_order(self):
        got = mb.with_rules(["a", "b", "c", "d", "e"])
        for (code, _), hint, base in zip(mb.RF4, got, "abcde"):
            self.assertTrue(hint.startswith(base + " "))
            self.assertTrue(hint.endswith(mb.RF4_RULES[code]))

    def test_hints_beyond_the_five_questions_are_untouched(self):
        got = mb.with_rules(["a", "b", "c", "d", "e", "extra"])
        self.assertEqual(got[5], "extra")

    def test_agreed_rules_are_stated(self):
        r = mb.RF4_RULES
        self.assertIn("never negative", r["RF#1"])
        self.assertIn("85/15", r["RF#1"])
        self.assertIn("never lifts RF#2", r["RF#2"])
        self.assertIn("status quo (0)", r["RF#4/2"])

    def test_scores_stay_blank_in_the_csv(self):
        import csv
        import tempfile
        subject = {"title": "Example Bill", "slug": "example-bill",
                   "nation": None}
        fields = {"general": [], "plan": [], "prepare": [],
                  "urgency": "Non-Urgent"}
        hints = mb.with_rules(["", "", "", "", ""])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "b.csv")
            mb.write_csv(path, subject, fields, hints, [], [],
                         __import__("datetime").date(2026, 10, 10))
            with open(path, encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
        rf = [r for r in rows if r and r[0] in dict(mb.RF4)]
        self.assertEqual(len(rf), 5)
        for row in rf:
            self.assertEqual(row[2], "")   # Plan score blank
            self.assertEqual(row[4], "")   # Evaluate score blank
            self.assertIn("Scoring rule:", row[3])

    def test_nothing_internal_in_the_public_summaries(self):
        text = " ".join(mb.RF4_RULES.values())
        for pattern in (r"https?://", r"looker", r"asana", r"\bdashboards?/",
                        r"@citizengo", r"—"):
            self.assertIsNone(re.search(pattern, text, re.I), pattern)


if __name__ == "__main__":
    unittest.main()
