"""English out of the EP's multilingual label fields (src/eulabel.py)."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import eulabel

# The 17 Sept 2026 shape at 01:08 UTC: French and "mul", no "en".
NIGHT = {"fr": "Impact des médias sociaux et de l'environnement en ligne sur les jeunes",
         "mul": "Impact des médias sociaux et de l'environnement en ligne sur les jeunes"
                " - Impact of social media and the online environment on young people"
                " - Auswirkungen sozialer Medien und des Online-Umfelds auf junge Menschen"}


class EnglishLabelTests(unittest.TestCase):
    def test_en_wins_and_is_not_provisional(self):
        self.assertEqual(eulabel.english_label({"en": "A", "mul": "X - B - Y"}), ("A", False))

    def test_the_english_segment_is_lifted_out_of_mul(self):
        self.assertEqual(eulabel.english_label(NIGHT),
                         ("Impact of social media and the online environment on young people", True))

    def test_a_weekly_collector_gets_nothing_rather_than_french(self):
        self.assertEqual(eulabel.english_label({"fr": "Seulement en français"}), ("", True))
        self.assertEqual(eulabel.english({"fr": "Seulement en français"}), "")

    def test_roll_calls_may_take_french_as_a_last_resort(self):
        self.assertEqual(eulabel.english_label({"fr": "Seulement en français"}, any_language=True),
                         ("Seulement en français", True))

    def test_empty_and_odd_shapes(self):
        self.assertEqual(eulabel.english_label({}), ("", True))
        self.assertEqual(eulabel.english_label(None), ("", True))
        self.assertEqual(eulabel.english_label("plain string"), ("plain string", False))

    def test_normalise_title_matches_a_vote_item_to_its_adopted_text(self):
        a = "Gender inequalities in health, specifically as regards gender-specific conditions"
        b = "Gender inequalities in health, specifically as regards gender-specific conditions (2025/2074(INI)) ***I"
        self.assertEqual(eulabel.normalise_title(a), eulabel.normalise_title(b))
        self.assertNotEqual(eulabel.normalise_title(a), eulabel.normalise_title("An EU cardiovascular diseases strategy"))


if __name__ == "__main__":
    unittest.main()
