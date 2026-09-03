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


class RealPolarityTests(unittest.TestCase):
    """The proof that the expectations track PEOPLE, not a fixed lobby.

    Amendment 12 (division 2068, 20 June 2025) is a RESTRICTING
    amendment, so our side is AYE -- the opposite polarity to the
    readings. On it Kruger really did vote aye and both sponsors voted
    no. The same anchor set must therefore pass with our_side=aye and
    be refused with our_side=no, on the same real data. Offline: the
    payload is archived (data/raw/2026-09-03/, from the 2026-09-03
    refusal-path session).
    """

    PAYLOAD = os.path.join(ROOT, "data", "raw", "2026-09-03",
                           "division_cdetail-2068.json.gz")

    def _voters(self):
        import gzip
        import json
        from src.ingest import divisions as di
        if not os.path.exists(self.PAYLOAD):
            self.skipTest("archived payload for division 2068 not present")
        payload = json.loads(gzip.open(self.PAYLOAD).read().decode())
        _, voters = di.parse_commons_breakdown(payload)
        return voters

    def test_a_restricting_amendment_passes_on_aye_and_fails_on_no(self):
        voters = self._voters()
        passed_aye, rows_aye = prep.anchor_test(voters, "aye")
        passed_no, _ = prep.anchor_test(voters, "no")
        self.assertTrue(passed_aye, "our side is aye on a restricting "
                                    "amendment")
        self.assertFalse(passed_no, "the same data must be refused with "
                                    "the polarity inverted")
        by_name = {r["name"]: r for r in rows_aye}
        self.assertEqual(by_name["Danny Kruger"]["lobby"], "aye")
        self.assertEqual(by_name["Kim Leadbeater"]["lobby"], "no")
        self.assertEqual(by_name["Lauren Edwards"]["lobby"], "no")


class RefusalPathTests(unittest.TestCase):
    """run()'s own refusals, with a fake client (no network)."""

    class D:
        def __init__(self, id, title):
            self.id, self.title = id, title
            self.number, self.aye_count, self.no_count = 1, 10, 5

    def _client(self, divs):
        outer = self

        class C:
            def get_json(self, url, feed, slug, **kw):
                return {"Divisions": []}
        # patch the fetch instead: run() calls div_ingest directly
        return C()

    def _run(self, divs, **kw):
        from src.ingest import divisions as di
        real = di.fetch_commons_divisions
        di.fetch_commons_divisions = lambda client, date: divs
        lines = []
        try:
            code = prep.run("2026-09-11", client=object(),
                            out=lines.append, **kw)
        finally:
            di.fetch_commons_divisions = real
        return code, "\n".join(lines)

    def test_no_divisions_points_at_the_nod_procedure(self):
        code, text = self._run([])
        self.assertEqual(code, 0)
        self.assertIn("talked out or passed on the nod", text)
        self.assertIn("nothing is signed", text)

    def test_a_stage_with_no_match_is_refused(self):
        code, text = self._run([self.D(1, "Some other Bill: Committee")],
                               our_side="no")
        self.assertEqual(code, 1)
        self.assertIn("matches stage", text)
        self.assertNotIn("--- sign-off message ---", text)

    def test_an_ambiguous_stage_is_refused_with_the_ids(self):
        code, text = self._run([self.D(1, "TIA: Second Reading"),
                                self.D(2, "Other: Second reading")],
                               our_side="no")
        self.assertEqual(code, 1)
        self.assertIn("divisions match", text)
        self.assertIn("--division", text)
        self.assertNotIn("--- sign-off message ---", text)

    def test_the_question_block_prints_before_any_verdict(self):
        code, text = self._run([self.D(1, "TIA: Second Reading")])
        self.assertIn("READ THE QUESTION", text)
        self.assertNotIn("--- sign-off message ---", text)


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
