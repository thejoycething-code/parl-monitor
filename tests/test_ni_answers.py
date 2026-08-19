"""Ministerial answer shapes: where a Minister declined.

Every fixture below is trimmed from a real stored answer, because the point of
the module is that these phrasings recur in the wild -- 28 of 203 stored answers
carry one, measured 2026-08-19 -- and an invented phrasing would prove nothing
about that.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import ni_answers

# AQW 49924/22-27, Department of Health, on puberty blockers.
NOT_HELD = ("Drugs typically prescribed to suppress the release of sex hormones "
            "in individuals can be used for the treatment of a range of "
            "conditions and the HSC Business Services Organisation does not "
            "hold information on the indication for which drugs have been "
            "prescribed.")

# AQW 47706/22-27, Assembly Commission, on the EHRC single-sex guidance.
NOT_OUR_REMIT = ("The case referred is a judgment of the High Court of England "
                 "and Wales concerning guidance published by the Equality and "
                 "Human Rights Commission, a body which does not have "
                 "functions in Northern Ireland about legislation which does "
                 "not extend to Northern Ireland.")

# AQW 48064/22-27, Department of Health, on chaplaincy and safe access zones.
NOT_ISSUED = ("Safe Access Zone operator guidance was issued to Health and "
              "Social Care Trusts in September 2023. My Department has not "
              "issued standalone guidance for chaplaincy teams.")

# AQW 44143/22-27, Department of Health.
NO_POSITION = ("The report was commissioned to inform the development of "
               "Departmental policy. As the draft report contains developing "
               "analysis, options, and advice which do not represent the "
               "Department's settled position, it will not be published.")

SUBSTANTIVE = ("The Northern Ireland Prison Service informs the Home Office of "
               "all custodial sentences imposed on foreign national prisoners "
               "within 10 days of the sentence.")


class ShapeTests(unittest.TestCase):
    def test_each_real_refusal_is_named(self):
        self.assertEqual(ni_answers.shape(NOT_HELD), "data not held")
        self.assertEqual(ni_answers.shape(NOT_OUR_REMIT), "not our remit")
        self.assertEqual(ni_answers.shape(NOT_ISSUED), "no policy issued")
        self.assertEqual(ni_answers.shape(NO_POSITION), "no settled position")

    def test_a_substantive_answer_has_no_shape(self):
        """'' is a real result, not a failure: 175 of 203 answers decline
        nothing and must read as substantive rather than unclassified."""
        self.assertEqual(ni_answers.shape(SUBSTANTIVE), "")

    def test_empty_and_none(self):
        self.assertEqual(ni_answers.shape(""), "")
        self.assertEqual(ni_answers.shape(None), "")

    def test_responsibility_deflection_is_a_remit_refusal(self):
        """REGRESSION. This phrase was dropped when the patterns were rewritten
        from the measuring probe, silently costing 8 of 28 answers -- caught by
        comparing the stored shape count (14) against the probe's (28)."""
        self.assertEqual(
            ni_answers.shape("This is not a policy or legislative "
                             "responsibility of my Department."),
            "not our remit")

    def test_in_due_course_is_a_non_commitment(self):
        """REGRESSION, the other half of the same rewrite loss: 6 answers."""
        self.assertEqual(
            ni_answers.shape("A revised policy will be brought forward in due "
                             "course."),
            "no settled position")

    def test_remit_wins_over_data_when_both_appear(self):
        """Ordered most-specific first: declining the remit is the harder wall,
        so it is the more useful label when an answer does both."""
        both = ("This does not extend to Northern Ireland and the Department "
                "does not hold information on it.")
        self.assertEqual(ni_answers.shape(both), "not our remit")


class QuoteTests(unittest.TestCase):
    def test_the_quoted_sentence_is_the_one_that_declines(self):
        """An answer averages 980 characters. The sentence a campaigner would
        cite is the one carrying the refusal, not the opening pleasantry."""
        quoted = ni_answers.quote(NOT_ISSUED, "no policy issued")
        self.assertIn("has not issued standalone guidance", quoted)
        self.assertNotIn("September 2023", quoted,
                         "the first sentence is context, not the refusal")

    def test_a_substantive_answer_quotes_its_opening(self):
        quoted = ni_answers.quote(SUBSTANTIVE)
        self.assertTrue(quoted.startswith("The Northern Ireland Prison Service"))

    def test_long_quotes_are_trimmed_on_a_word_boundary(self):
        quoted = ni_answers.quote(NOT_OUR_REMIT, "not our remit", limit=60)
        self.assertLessEqual(len(quoted), 64)
        self.assertTrue(quoted.endswith("..."))
        self.assertNotIn("  ", quoted)

    def test_empty_answer_quotes_nothing(self):
        self.assertEqual(ni_answers.quote(""), "")
        self.assertEqual(ni_answers.quote(None), "")


class ClassifyTests(unittest.TestCase):
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def setUp(self):
        from src import filter as filt
        self.filt = filt
        self.tax = filt.load_taxonomy(
            os.path.join(self.ROOT, "config", "taxonomy.yaml"))
        self.wl = filt.load_watchlist(
            os.path.join(self.ROOT, "config", "watchlist.yaml"))

    def test_areas_terms_and_shape_together(self):
        areas, terms, shape = ni_answers.classify(
            self.tax, self.wl, NOT_ISSUED, self.filt.filter_item)
        self.assertIn(1, areas, "safe access zones are area 1")
        self.assertTrue(terms)
        self.assertEqual(shape, "no policy issued")

    def test_an_empty_answer_yields_nothing(self):
        self.assertEqual(
            ni_answers.classify(self.tax, self.wl, "", self.filt.filter_item),
            ([], [], ""))


class SeparationTests(unittest.TestCase):
    """An answer's areas are the GOVERNMENT'S ground, not the asker's."""

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_the_5ca_never_reads_answer_areas(self):
        """`areas` is the MLA's evidence and feeds the 5CA. Crediting a member
        with the areas of a Minister's reply would give them ground they never
        took -- the same conflation this codebase keeps designing out."""
        with open(os.path.join(self.ROOT, "tools", "ni_5ca.py"),
                  encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("answer_areas", source)
        self.assertNotIn("answer_shape", source)


if __name__ == "__main__":
    unittest.main()
