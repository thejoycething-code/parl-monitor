"""English taxonomy v1.25 (13 October 2026): the unhyphenated "single sex" forms.

Area 5 carried "single-sex space*", "single-sex service*" and "single-sex
ward*" only with the hyphen, and no "facilities" form at all. The Health Bill's
New Clause 143 (division 2422, 8 September 2026) is headed "Single sex
facilities" and matched area 5 only at tier 2, on "changing room*", so the
clause-text path stored it but the ledger gate never saw a tier-1 term.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import filter as filt  # noqa: E402

TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def hit(text):
    res = filt.filter_item(TAX, WL, text, title="")
    return res.tier, res.issue_areas, res.matched_terms


class SingleSex(unittest.TestCase):
    def test_version(self):
        # 1.26 since 16 October 2026 (guarded "gender identity"): tests/test_v126_terms.py.
        self.assertIn(TAX.version, ("1.25", "1.26"))

    def test_unhyphenated_forms_match_like_the_hyphenated(self):
        for text, term in (("guidance on single sex spaces", "single sex space*"),
                           ("single sex services for victims", "single sex service*"),
                           ("patients on single sex wards", "single sex ward*"),
                           ("single sex facilities for NHS staff", "single sex facilit*"),
                           ("a single-sex facility in every hospital", "single-sex facilit*")):
            tier, areas, terms = hit(text)
            self.assertEqual((tier, areas), (1, [5]), text)
            self.assertIn(term, terms, text)

    def test_hyphenated_forms_unchanged(self):
        for text in ("single-sex spaces", "single-sex services", "single-sex wards"):
            self.assertEqual(hit(text)[:2], (1, [5]), text)

    def test_other_single_sex_phrases_stay_out(self):
        # A single-sex school is not a term; neither is bare "single sex".
        self.assertIsNone(hit("a single sex school in the borough")[0])
        self.assertIsNone(hit("single sex")[0])


if __name__ == "__main__":
    unittest.main()
