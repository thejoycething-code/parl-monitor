"""The 11 September prep tool (2026-09-03).

The test that matters is the second one. The first version of the anchor
check derived each anchor's EXPECTED verdict from the same our_side as
the actual, so inverting our_side inverted both sides of the comparison
and the check passed a fully inverted verdict in silence -- a guard that
could not fail. Fed our_side=aye on the known Third Reading it printed a
cheerful "Anchors check out". The expectation is now fixed to the person.
"""

import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))


def _load():
    spec = importlib.util.spec_from_file_location(
        "prep_division", os.path.join(ROOT, "tools", "prep_division.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


prep = _load()


class V:
    def __init__(self, member_id, vote):
        self.member_id = member_id
        self.vote = vote


# The real 20 June 2025 pattern: Kruger no, Leadbeater aye, Edwards aye.
REAL = [V(4858, "no"), V(4923, "aye"), V(5298, "aye")]


class AnchorTests(unittest.TestCase):
    def test_the_true_verdict_passes(self):
        passed, rows = prep.anchor_test(REAL, "no")
        self.assertTrue(passed)
        self.assertTrue(all(r["ok"] for r in rows))

    def test_an_inverted_verdict_is_refused(self):
        """The regression: this returned True before the fix."""
        passed, rows = prep.anchor_test(REAL, "aye")
        self.assertFalse(passed)
        self.assertTrue(all(r["ok"] is False for r in rows))

    def test_silence_fails_closed(self):
        passed, rows = prep.anchor_test([V(4858, "no")], "no")
        self.assertFalse(passed, "one voting anchor cannot testify")
        self.assertEqual(sum(1 for r in rows if r["ok"] is None), 2)

    def test_expectations_are_fixed_to_the_person(self):
        # Structural: no expectation may be computed from our_side.
        src = open(os.path.join(ROOT, "tools", "prep_division.py"),
                   encoding="utf-8").read()
        self.assertIn('4858: ("Danny Kruger", "GOOD")', src)
        self.assertNotIn("verdict_for(known, our_side)", src)


class PickTests(unittest.TestCase):
    class D:
        def __init__(self, id, title):
            self.id, self.title = id, title
            self.number = 0
            self.aye_count = self.no_count = 0

    def test_stage_match_and_ambiguity(self):
        divs = [self.D(1, "TIA Bill: Second Reading"),
                self.D(2, "TIA Bill: Amendment 94"),
                self.D(3, "Something else: Second reading")]
        self.assertEqual([d.id for d in prep.pick(divs, "Second Reading")],
                         [1, 3])          # ambiguous: run() refuses
        self.assertEqual([d.id for d in prep.pick(divs, "Second Reading", 3)],
                         [3])             # explicit id wins


class QuestionTests(unittest.TestCase):
    def test_the_tool_never_invents_a_question(self):
        """The Commons API carries no motion text (null in all 40 archived
        payloads checked), so the tool prints the sources and leaves the
        question to a human."""
        src = open(os.path.join(ROOT, "tools", "prep_division.py"),
                   encoding="utf-8").read()
        self.assertIn("READ THE QUESTION", src)
        self.assertIn("hansard.parliament.uk", src)
        self.assertIn("paste from Hansard", src)
        self.assertIn("reasoned amendment INVERTS", src)


if __name__ == "__main__":
    unittest.main()
