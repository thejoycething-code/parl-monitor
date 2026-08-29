"""The public MSP votes page (Christopher, 2026-08-29).

A SEPARATE page from the Westminster one, and for a structural reason: an
MSP is elected by constituency OR region, so a Scottish postcode returns one
constituency member and seven regional ones. "Find your MP" has one answer;
"find your MSP" has eight.
"""

import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import make_msp_votes as mvp

TEMPLATE = os.path.join(ROOT, "templates", "msp-votes.html")
PAGE = os.path.join(ROOT, "partner_site", "msp-votes.html")


def template():
    with open(TEMPLATE, encoding="utf-8") as fh:
        return fh.read()


def payload():
    if not os.path.exists(PAGE):
        return None
    with open(PAGE, encoding="utf-8") as fh:
        text = fh.read()
    return json.loads(re.search(r"const DATA = (\{.*?\});\n", text, re.S).group(1))


class NameTests(unittest.TestCase):
    def test_a_sort_key_becomes_a_name(self):
        """sp_members stores "Briggs, Miles" for sorting. Rendering that is
        addressing someone by their filing card."""
        self.assertEqual(mvp.display_name("Briggs, Miles", "Miles"), "Miles Briggs")

    def test_the_preferred_name_replaces_only_the_first(self):
        self.assertEqual(mvp.display_name("McAllan, Màiri", "Màiri"),
                         "Màiri McAllan")

    def test_a_name_without_a_comma_is_left_alone(self):
        self.assertEqual(mvp.display_name("Presiding Officer", ""), "Presiding Officer")


class NotYetAnMspTests(unittest.TestCase):
    """The Bill was decided in March 2026 and Scotland voted in May, so 65
    of the 129 sitting MSPs could not have voted on it.

    Rendering that as "no vote recorded" is the fault the Westminster page
    committed against peers this morning, in a second parliament.
    """

    def test_the_page_distinguishes_absence_from_ineligibility(self):
        html = template()
        self.assertIn("NOT YET AN MSP", html)
        self.assertIn("was not a member of the Scottish Parliament", html)

    def test_new_members_are_marked(self):
        data = payload()
        if data is None:
            self.skipTest("page not built")
        new = [m for m in data["members"] if not m["there"]]
        sat = [m for m in data["members"] if m["there"]]
        self.assertGreater(len(new), 50)
        self.assertGreater(len(sat), 50)
        for m in new:
            self.assertFalse(m["votes"], "{0} is marked new but has votes".format(m["name"]))

    def test_a_new_member_is_not_tallied_out_of_three(self):
        html = template()
        self.assertIn("Elected in <b>May 2026</b>", html)


class SwitcherTests(unittest.TestCase):
    """Twelve MSPs voted Yes to the general principles and No on passing.
    Every one moved that way; none moved the other. That is the Bill's
    defeat, and seven of the twelve are still sitting."""

    def test_switchers_are_found_and_named_on_their_page(self):
        data = payload()
        if data is None:
            self.skipTest("page not built")
        switched = [m for m in data["members"] if m["switched"]]
        self.assertGreaterEqual(len(switched), 5)
        for m in switched:
            self.assertEqual(m["switched"][0], "Yes")
            self.assertEqual(m["switched"][1], "No")

    def test_the_page_explains_what_a_switch_means(self):
        html = template()
        self.assertIn("changed position", html)
        self.assertIn("which is why the Bill fell", html)


class VoteReadingTests(unittest.TestCase):
    def test_an_abstention_is_not_read_as_opposition(self):
        """Holyrood records four states. Reading Abstain or Not Voted as
        opposition puts a view in a member's mouth."""
        html = template()
        self.assertIn("not read as opposition", html)
        self.assertIn('const POSITION = {Yes:"for", No:"against"}', html)

    def test_the_result_is_coloured_by_which_way_it_went_for_us(self):
        """Green must not mean "passed": Stage 1 carrying went AGAINST us,
        and the final vote failing went for us."""
        html = template()
        self.assertIn('d.result === "Defeated" && d.ours === "against"', html)

    def test_only_signed_off_divisions_carry_a_verdict(self):
        data = payload()
        if data is None:
            self.skipTest("page not built")
        for d in data["divisions"]:
            self.assertIn(d["ours"], ("for", "against", None))

    def test_the_motion_text_is_shown_verbatim(self):
        """What makes our_side checkable rather than asserted."""
        data = payload()
        if data is None:
            self.skipTest("page not built")
        for d in data["divisions"]:
            self.assertTrue(d["motion"], d["short"])


class LinkTests(unittest.TestCase):
    def test_the_two_pages_reference_each_other(self):
        """Context, not navigation: each answers "what happened in the
        other Parliament" without pretending to be one site."""
        self.assertIn("mp-votes.html", template())
