"""English taxonomy v1.26 (16 October 2026): guarded "gender identity".

Bare "gender identity" stays rejected (v1.20: mostly anti-discrimination
boilerplate). Chris asked to keep what it brings in on our ground: gender
identity services and clinics, children and schools, single-sex spaces.
Two tier-2 forms, measured in docs/keyword-taxonomy.md (area 3 notes):
area 3 guarded by children/school/clinic company, area 5 by single-sex
company, both vetoed by SOGI lists and other boilerplate.
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
    return res.tier, res.issue_areas


class GuardedGenderIdentity(unittest.TestCase):
    def test_version(self):
        self.assertEqual(TAX.version, "1.26")

    def test_on_our_ground_gains_area_3_at_tier_2(self):
        for text in ("To ask the Scottish Government what plans it has to reduce average waiting times at "
                     "gender identity clinics.",
                     "her current position on gender identity education in primary schools",
                     "guidance on gender identity in schools must prioritise safeguarding",
                     "support for children under 16 who are uncertain about their gender identity",
                     "counseling related to gender identity to students under 18 years of age"):
            self.assertEqual(hit(text), (2, [3]), text)

    def test_single_sex_company_gains_area_5(self):
        tier, areas = hit("guidance on sleeping arrangements where the sex of a supervising adult differs "
                          "from their gender identity")
        self.assertEqual(tier, 2)
        self.assertIn(5, areas)
        self.assertEqual(hit("access to women-only refuges by gender identity"), (2, [5]))

    def test_boilerplate_is_vetoed(self):
        for text in ("no child shall be discriminated against on the basis of race, religion, sexual orientation, "
                     "gender identity or disability in any school",
                     "pupils bullied because of their sexual orientation or gender identity",
                     "schools may not discriminate on grounds of gender identity or expression",
                     "an inspirational ambassador to all young people regardless of gender identity",
                     "a hate crime against a child motivated by gender identity",
                     "ban conversion therapy for children aimed at changing gender identity"):
            areas = hit(text)[1]
            self.assertNotIn(3, areas, text)
            self.assertNotIn(5, areas, text)

    def test_bare_phrase_still_matches_nothing(self):
        self.assertEqual(hit("the Equality Bill and gender identity"), (None, []))

    def test_nhs_alone_is_not_company(self):
        self.assertEqual(hit("NHS data on gender identity"), (None, []))

    def test_survey_form_of_v119_unchanged(self):
        self.assertEqual(hit("no gender identity question on forms or surveys"), (2, [5]))


if __name__ == "__main__":
    unittest.main()
