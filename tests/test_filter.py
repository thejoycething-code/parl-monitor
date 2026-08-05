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


class PassageMatchingTests(unittest.TestCase):
    """Stage 1 of the cross-tagging fix: a long speech is tagged with the
    areas its passages support, not every area it brushes against."""

    def setUp(self):
        self.tax = filt.load_taxonomy(TAXONOMY)
        self.wl = filt.load_watchlist(WATCHLIST)

    def test_paragraphs_split_and_markup_stripped(self):
        text = ('First paragraph about nothing.\r\n\r\n'
                'Second <span class="column-number">1712</span>paragraph.')
        parts = filt.split_passages(text)
        self.assertEqual(len(parts), 2)
        self.assertNotIn("<span", parts[1])
        self.assertIn("1712paragraph", parts[1].replace(" ", ""))

    def test_long_paragraph_broken_on_sentences(self):
        para = " ".join("Sentence number {0} here.".format(n) for n in range(200))
        parts = filt.split_passages(para, max_chars=300)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(p) <= 320 for p in parts))

    def test_unrelated_speech_mentioning_one_term_is_not_tagged_everywhere(self):
        """The Diana Johnson case: a knife-crime speech that mentions the
        Online Safety Act must not land on the abortion sheet."""
        text = ("I rise to speak about knife crime in my constituency.\r\n\r\n"
                "Retailers must do more, and the Online Safety Act gives "
                "Ofcom powers we should use.\r\n\r\n"
                "Youth services need funding.")
        matches = filt.match_passages(self.tax, self.wl, text, title="Knife Crime")
        areas, terms, excerpt = filt.aggregate_passages(matches)
        self.assertIn(7, areas)          # free speech / online safety: real
        self.assertNotIn(1, areas)       # abortion: never mentioned
        self.assertIn("Online Safety Act", excerpt)

    def test_excerpt_is_the_matching_passage_not_the_title(self):
        text = ("Opening remarks on procedure.\r\n\r\n"
                "Women attending an abortion clinic deserve protection from "
                "intimidation, which is why safe access zones matter.")
        matches = filt.match_passages(self.tax, self.wl, text, title="Topical Questions")
        _areas, _terms, excerpt = filt.aggregate_passages(matches)
        self.assertIn("safe access zones", excerpt)
        self.assertNotIn("Topical Questions", excerpt)

    def test_title_match_counts_as_its_own_passage(self):
        matches = filt.match_passages(self.tax, self.wl, "Nothing relevant here.",
                                      title="Abortion Clinics: Buffer Zones")
        areas, _terms, _excerpt = filt.aggregate_passages(matches)
        self.assertIn(1, areas)

    def test_no_qualifying_passage_returns_nothing(self):
        matches = filt.match_passages(self.tax, self.wl,
                                      "Hedgerow buffer strips on farmland.",
                                      title="Agriculture Bill")
        self.assertEqual(filt.aggregate_passages(matches), ([], [], None))


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
        r = self.match("SPUC published a briefing about the weather")
        self.assertIn("SPUC", r.watchlist_hits)
        self.assertEqual(r.min_score, 2)
        self.assertTrue(r.to_triage)

    def test_parliamentarian_names_are_not_matching_entities(self):
        """Christopher, 2026-08-05: Hansard prints members' names
        structurally, so a name must not admit an item on its own."""
        r = self.match("Kim Leadbeater made remarks about the weather")
        self.assertEqual(r.watchlist_hits, [])
        self.assertFalse(r.matched())
        self.assertIn("Kim Leadbeater", filt.load_watchlist(WATCHLIST).people)

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
        # "data migration" style noise reaches triage as tier 2 only, never tier 1.
        r = self.match("Data migration for NHS records systems")
        self.assertEqual(r.tier, 2)

    def test_area_11_migration(self):
        # Scope decision reversed 2026-08-03: migration is now area 11.
        r = self.match("Net migration statistics for 2026")
        self.assertIn(11, r.issue_areas)
        self.assertEqual(r.tier, 1)
        self.assertIn(11, self.match("Asylum accommodation costs").issue_areas)
        self.assertIn(11, self.match("Small boats arrivals in the Channel").issue_areas)
        self.assertIn(11, self.match("Legislative Scrutiny: Immigration and Asylum Bill").issue_areas)
        # Watchlist: the live bill matches as an entity too.
        self.assertIn("Immigration and Asylum Bill",
                      self.match("Committee stage of the Immigration and Asylum Bill").watchlist_hits)

    def test_loose_pq_noise_is_suppressed(self):
        # "British Steel: Jingye Group" is a real loose-search PQ hit; filter drops it.
        self.assertFalse(self.match("British Steel: Jingye Group").matched())


if __name__ == "__main__":
    unittest.main()
