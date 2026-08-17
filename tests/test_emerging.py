"""Catching language nobody listed."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import emerging

# A corpus of how the UN normally talks about gender recognition.
CORPUS = [
    "Ensure legal gender recognition procedures are accessible.",
    "Adopt legal gender recognition based on self-identification.",
    "Provide legal gender recognition without medical requirements.",
    "Repeal requirements for sterilization in legal gender recognition.",
]


class NovelPhraseTests(unittest.TestCase):
    def setUp(self):
        self.baseline = emerging.build_baseline(CORPUS)

    def test_baseline_counts_documents_not_repeats(self):
        """A phrase forty times in one text is still one document's evidence."""
        repeated = emerging.build_baseline(["gender recognition " * 40])
        self.assertEqual(repeated["gender recognition"], 1)

    def test_established_language_is_not_novel(self):
        novel = emerging.novel_phrases(
            "Adopt legal gender recognition based on self-identification.",
            self.baseline)
        self.assertNotIn("legal gender recognition", novel)

    def test_a_new_framing_surfaces_without_being_listed(self):
        """The self-ID hypothetical: nobody wrote "self-defined gender" down."""
        found = emerging.longest_novel(
            "Recognizes the right of every person to their self-defined gender.",
            self.baseline)
        self.assertTrue(any("self-defined" in g for g in found),
                        "new phrasing should surface: %s" % found)

    def test_drafting_mechanics_are_furniture(self):
        """"In operative paragraph 13, delete" says how, not what about."""
        novel = emerging.novel_phrases(
            "In operative paragraph 13, delete the fourteenth preambular text.",
            self.baseline)
        self.assertFalse([g for g in novel if emerging._is_furniture(g)])

    def test_subject_words_survive_even_beside_mechanics(self):
        """"delete sexual and reproductive" IS the finding, not furniture."""
        found = emerging.longest_novel(
            "In operative paragraph 13, delete sexual and reproductive health.",
            self.baseline)
        self.assertTrue(any("sexual" in g for g in found), found)

    def test_variants_of_one_finding_collapse(self):
        """Four windows over the same phrase are one discovery."""
        found = emerging.longest_novel(
            "delete sexual and reproductive health in operative paragraphs "
            "27 and 43, delete sexual and reproductive", self.baseline, limit=6)
        sexual = [g for g in found if "sexual" in g]
        self.assertEqual(len(sexual), 1, found)


class RightsClaimTests(unittest.TestCase):
    TERMS = ["gender identity", "self-identification", "abortion"]

    def test_a_claim_beside_our_term_is_flagged(self):
        hits = emerging.rights_claims(
            "Recognizes the right to gender identity for all persons.", self.TERMS)
        self.assertEqual(len(hits), 1)
        self.assertIn("gender identity", hits[0][1])

    def test_a_claim_alone_is_not_flagged(self):
        self.assertEqual(
            emerging.rights_claims("Reaffirms the right to development.", self.TERMS), [])

    def test_our_term_alone_is_not_flagged(self):
        """Presence is not escalation; the monitor already matches presence."""
        self.assertEqual(
            emerging.rights_claims("Notes progress on gender identity data.",
                                   self.TERMS), [])

    def test_claim_and_term_must_share_a_sentence(self):
        """A text can assert a right in one paragraph and mention gender in
        another without the two being related."""
        text = ("Reaffirms the right to development. "
                "Separately, notes reports on gender identity.")
        self.assertEqual(emerging.rights_claims(text, self.TERMS), [])


if __name__ == "__main__":
    unittest.main()
