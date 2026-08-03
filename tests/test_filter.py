"""Taxonomy + watchlist filter tests (handoff sections 6, 7)."""

import gzip
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import filter as filt

TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
WATCHLIST = os.path.join(ROOT, "config", "watchlist.yaml")
RAW = os.path.join(ROOT, "data", "raw", "2026-08-01")


def load_json(slug):
    with gzip.open(os.path.join(RAW, slug + ".json.gz"), "rb") as h:
        return json.loads(h.read().decode("utf-8"))


class FilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tax = filt.load_taxonomy(TAXONOMY)
        cls.wl = filt.load_watchlist(WATCHLIST)

    def match(self, *fields):
        return filt.filter_item(self.tax, self.wl, *fields)

    # -- tiering -----------------------------------------------------------

    def test_tier1_phrase_auto_includes(self):
        r = self.match("Lords committee day on the assisted dying bill Thursday")
        self.assertIn(2, r.issue_areas)
        self.assertEqual(r.tier, 1)
        self.assertTrue(r.auto_include)
        self.assertFalse(r.to_triage)

    def test_tier2_only_goes_to_triage(self):
        r = self.match("A debate on palliative care funding")  # area 2 tier2
        self.assertEqual(r.tier, 2)
        self.assertTrue(r.to_triage)
        self.assertFalse(r.auto_include)

    # -- matching mechanics ------------------------------------------------

    def test_rse_word_boundary_does_not_match_nurse(self):
        self.assertFalse(self.match("A nurse spoke at length in the course").matched())
        self.assertIn(6, self.match("New RSE guidance published").issue_areas)

    def test_stem_wildcard(self):
        self.assertIn(3, self.match("Ban on puberty blockers upheld").issue_areas)

    def test_bare_exclusion_words_do_not_match(self):
        self.assertFalse(self.match("Gender pay gap reporting reform").matched())
        self.assertFalse(self.match("Termination of employment tribunal").matched())

    def test_v02_patches(self):
        self.assertIn(6, self.match("SEND reform: education otherwise than at school").issue_areas)
        self.assertIn(9, self.match("Tying the Knot: reforming weddings law").issue_areas)
        self.assertIn(7, self.match("anti-Muslim hostility definition consultation").issue_areas)

    def test_multi_area_term(self):
        areas = self.match("Silent prayer near a clinic").issue_areas
        self.assertIn(1, areas)
        self.assertIn(7, areas)

    # -- watchlist ---------------------------------------------------------

    def test_watchlist_entity_min_score_2_without_keyword(self):
        r = self.match("Kim Leadbeater made remarks about the weather")
        self.assertIn("Kim Leadbeater", r.watchlist_hits)
        self.assertEqual(r.min_score, 2)
        self.assertTrue(r.to_triage)

    def test_division_entity_match_with_smart_quote(self):  # acceptance 9.7 path
        title = "Draft Children’s Wellbeing and Schools Act 2026 (Establishment of Schools) Regulations"
        r = self.match(title)
        self.assertIn("Children's Wellbeing and Schools", r.watchlist_hits)
        self.assertIn(6, r.issue_areas)

    # -- integration on real fixtures --------------------------------------

    def test_si_fixture_matches_via_act_watch(self):
        name = (load_json("si_search-childrens-wellbeing")["items"][0]["value"]["name"])
        self.assertIn("Children's Wellbeing and Schools", self.match(name).watchlist_hits)

    def test_acronym_org_is_case_sensitive(self):
        # "CARE" the charity matches; "care" the word does not.
        self.assertIn("CARE", self.match("The charity CARE gave evidence").watchlist_hits)
        self.assertFalse(self.match("T Levels in sport and social care").matched())
        # "PATHWAYS" programme matches; "care pathways" does not.
        self.assertIn(3, self.match("The PATHWAYS gender pilot").issue_areas)
        self.assertFalse(self.match("Clinical care pathways review").matched())


    def test_v03_additions(self):
        # Vocabulary gaps closed 2026-08-03 (Christopher approved the set).
        self.assertIn(1, self.match("Decriminalisation of abortion: pardons scheme").issue_areas)
        self.assertIn(6, self.match("Support for home schooling families").issue_areas)
        self.assertIn(6, self.match("Homeschooling registration proposals").issue_areas)
        self.assertIn(8, self.match("A threat to religious liberty").issue_areas)
        self.assertIn(5, self.match("EHRC guidance on single-sex services").issue_areas)
        self.assertIn(3, self.match("Social transition of pupils in schools").issue_areas)
        self.assertIn(5, self.match("The gender reassignment protected characteristic").issue_areas)
        self.assertIn(2, self.match("Lessons from MAiD in Canada").issue_areas)
        self.assertIn(10, self.match("Polygenic screening of embryos").issue_areas)

    def test_islam_related_additions_scoped_to_existing_areas(self):
        self.assertIn(7, self.match("A statutory definition of Islamophobia").issue_areas)
        self.assertIn(7, self.match("Islamist pressure on schools").issue_areas)
        self.assertIn(6, self.match("The grooming gangs national inquiry").issue_areas)
        self.assertIn(9, self.match("Sharia councils and marriage law").issue_areas)

    def test_new_terms_do_not_reintroduce_noise(self):
        # Bare excluded words still never match alone.
        self.assertFalse(self.match("Energy transition targets").matched())
        # "maid" should not ride in on MAiD (case-insensitive fallback risk).
        self.assertFalse(self.match("The maid service industry").matched())
        # Plain migration/immigration items stay out: not a taxonomy area.
        self.assertFalse(self.match("Net migration statistics for 2026").matched())
        self.assertFalse(self.match("Asylum accommodation costs").matched())

    def test_loose_pq_noise_is_suppressed(self):
        # "British Steel: Jingye Group" is a real loose-search PQ hit; filter drops it.
        self.assertFalse(self.match("British Steel: Jingye Group").matched())


if __name__ == "__main__":
    unittest.main()
