"""Recorded votes from HRC session reports.

Fixture text is shaped like the real extraction, including the page footer
that the PDF glues into a country list at a page break.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.ingest import un_votes

REPORT = """
90. The Council considered draft resolution A/HRC/58/L.6 at its 55th meeting.
92. A recorded vote was taken on the draft resolution. The voting was as follows:
In favour: Albania, Belgium, France, Netherlands (Kingdom of the), Republic of Korea
Against: Bolivia (Plurinational State of), China, Cuba
Abstaining: Algeria, Côte d'Ivoire, Qatar
95. The Council then turned to draft resolution A/HRC/58/L.30/Rev.1.
96. A recorded vote was taken. The voting was as follows:
In favour: Chile, Germany, Japan
Against: Ethiopia, Sudan
Abstaining: Benin, Brazil, Kenya A/HRC/58/2 GE.25-11364 was issued subsequently.
"""


class UnVotesTests(unittest.TestCase):
    def setUp(self):
        self.votes = un_votes.parse_votes(REPORT)

    def test_finds_each_vote_block(self):
        self.assertEqual(len(self.votes), 2)

    def test_anchors_to_the_nearest_preceding_draft_symbol(self):
        """The prose by the vote says only "the draft resolution"; the symbol
        earlier in the section is what identifies it."""
        self.assertEqual(self.votes[0].draft, "A/HRC/58/L.6")
        self.assertEqual(self.votes[1].draft, "A/HRC/58/L.30/Rev.1")

    def test_keeps_parenthesised_names_whole(self):
        """An early version truncated this to "Bolivia (Plurinational"."""
        self.assertIn("Bolivia (Plurinational State of)", self.votes[0].against)
        self.assertIn("Netherlands (Kingdom of the)", self.votes[0].favour)

    def test_page_furniture_is_not_a_state(self):
        """The PDF glues the running header and job number onto the last name
        in a list at a page break; no state name contains a digit."""
        names = self.votes[1].abstaining
        self.assertIn("Kenya", names)
        self.assertFalse([n for n in names if any(c.isdigit() for c in n)],
                         "no state name contains a digit")

    def test_tally_is_counted_from_the_lists(self):
        """The prose form varies between sections; the lists are the evidence."""
        self.assertEqual(self.votes[0].tally, (5, 3, 3))

    def test_position_lookup(self):
        v = self.votes[0]
        self.assertEqual(v.position("Cuba"), "against")
        self.assertEqual(v.position("France"), "for")
        self.assertEqual(v.position("Qatar"), "abstain")

    def test_a_state_that_did_not_vote_is_none_not_absent_string(self):
        """Absent and not-a-member are indistinguishable in the source, so the
        answer is None rather than a guess."""
        self.assertIsNone(self.votes[0].position("United Kingdom"))


if __name__ == "__main__":
    unittest.main()
