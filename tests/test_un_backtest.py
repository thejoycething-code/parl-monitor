"""Regression: the 12 October 2026 GA vote on the political declaration on
pandemic prevention, preparedness and response must surface BEFORE the vote.

The monitor missed it. The draft (A/81/L.6, 5 October), the PGA's letter (7
October, naming 12 October) and the plenary listing were all public. Since
13 October 2026 the draft's own text is out of reach (documents.un.org's
robots.txt), so the draft is caught from 7 October, by the letter that names
it (tools/un_backtest.py says why). This
replays the archived responses (tests/fixtures/un/, fetched 13 October 2026)
as each earlier day would have seen them, through tools/un_backtest.py,
which uses the same src/un_signals.py as the forward look and the DM.
"""

import datetime
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import un_backtest  # noqa: E402

D = datetime.date
VOTE = D(2026, 10, 12)
LETTER = "letter:letter-pandemic-prevention-declaration-7-october-2026"
PLENARY = "plenary:f0bd129c-9251-4047-b00c-cccb49848b30"
DRAFT = "draft:A/81/L.6"


class PandemicDeclarationBacktest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = un_backtest.load()

    def at(self, day):
        due, first = un_backtest.as_of(day, *self.data)
        return {s.id: s for s in due}, {s.id: s for s in first}

    def test_nothing_on_5_and_6_october_by_the_new_route(self):
        """13 October 2026: the draft's PDF (dated 5 October) is behind
        docs.un.org's redirect to documents.un.org/api/..., which
        robots.txt disallows, so the replay no longer reads it. Nothing
        readable named A/81/L.6 before the PGA letter of 7 October. An
        honest two-day loss, recorded rather than faked."""
        for day in (D(2026, 10, 5), D(2026, 10, 6)):
            due, first = self.at(day)
            self.assertNotIn(DRAFT, first)
            self.assertEqual(due, {})

    def test_the_draft_is_a_first_sign_on_7_october_named_by_the_letter(self):
        _due, first = self.at(D(2026, 10, 7))
        self.assertIn(DRAFT, first)
        self.assertEqual(first[DRAFT].sign_date, D(2026, 10, 7))
        self.assertEqual(first[DRAFT].areas, [7])
        self.assertIn("named by PGA letter", first[DRAFT].detail)

    def test_the_letter_names_the_date_on_7_october(self):
        due, first = self.at(D(2026, 10, 7))
        self.assertIn(LETTER, first)
        self.assertEqual(due[LETTER].due, VOTE)
        self.assertEqual(due[DRAFT].due, VOTE, "the draft inherits the letter's date")

    def test_the_plenary_listing_is_on_top_by_8_october(self):
        due, first = self.at(D(2026, 10, 8))
        self.assertIn(PLENARY, due)
        self.assertEqual(due[PLENARY].due, VOTE)
        self.assertIn("A/81/L.6", due[PLENARY].detail)
        self.assertIn(PLENARY, first)

    def test_all_three_lead_every_day_from_8_october_to_the_vote(self):
        day = D(2026, 10, 8)
        while day < VOTE:
            due, _first = self.at(day)
            for ident in (LETTER, PLENARY, DRAFT):
                self.assertIn(ident, due, "{0} missing on {1}".format(ident, day))
            day += datetime.timedelta(days=1)

    def test_every_sign_predates_the_vote(self):
        due, first = self.at(D(2026, 10, 11))
        for s in list(due.values()) + list(first.values()):
            if s.sign_date:
                self.assertLess(s.sign_date, VOTE)

    def test_the_plenary_listing_date_is_taken_from_its_own_notes(self):
        _letters, plenaries, _consultations = self.data
        p = [m for m in plenaries if m.id.startswith("f0bd129c")][0]
        self.assertEqual(un_backtest.listed_from(p), D(2026, 10, 8))


if __name__ == "__main__":
    unittest.main()
