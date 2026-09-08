"""Cutting by words (Christopher, 2026-09-07: "there's extra text")."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import alignclip  # noqa: E402

TRANSCRIPT = ("um so as i was saying pregnant women are not factories and babies are not goods to be ordered "
              "i believe this is crossing an ethical line where human life is treated as a business transaction thank you").split()
WORDS = [(w, i * 0.4, i * 0.4 + 0.35) for i, w in enumerate(TRANSCRIPT)]


class AlignTests(unittest.TestCase):
    def test_exact_passage_is_found_at_its_first_and_last_word(self):
        a, b, ratio = alignclip.align(WORDS, "Pregnant women are not factories, and babies are not goods to be ordered.")
        self.assertEqual(a, WORDS[6][1])          # 'pregnant'
        self.assertEqual(b, WORDS[18][2])         # 'ordered'
        self.assertGreater(ratio, 0.95)

    def test_a_misheard_word_still_aligns(self):
        words = list(WORDS); words[8] = ("or", words[8][1], words[8][2])          # 'are' heard as 'or'
        a, b, ratio = alignclip.align(words, "Pregnant women are not factories, and babies are not goods to be ordered.")
        self.assertEqual(a, WORDS[6][1]); self.assertEqual(b, WORDS[18][2])
        self.assertGreater(ratio, 0.85)

    def test_an_absent_passage_is_not_forced(self):
        self.assertIsNone(alignclip.align(WORDS, "The Law Commission consultation called for a total ban on surrogacy in the UK."))

    def test_hansard_web_furniture_is_stripped_from_a_pasted_passage(self):
        self.assertEqual(alignclip.tokens("circumvent Toggle showing location ofColumn 224WHthe law"), ["circumvent", "the", "law"])

    def test_cuts_file_parses_headings_and_passages(self):
        cuts = alignclip.parse_cuts("# x\n\n## Jonathan Hinder\nPregnant women are not factories.\n\n## Tracy Gilbert\n\nThe Government must act.\n")
        self.assertEqual(cuts, [("Jonathan Hinder", "Pregnant women are not factories."), ("Tracy Gilbert", "The Government must act.")])

    def test_the_tool_offers_cut(self):
        src = open(os.path.join(ROOT, "tools", "debate_pack.py"), encoding="utf-8").read()
        self.assertIn("def cut_passages(args):", src)
        self.assertIn('"--cut"', src)


if __name__ == "__main__":
    unittest.main()
