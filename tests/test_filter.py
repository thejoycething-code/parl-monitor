"""Taxonomy + watchlist filter tests (handoff sections 6, 7)."""

import gzip
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import filter as filt
from src import intel

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

    # -- guarded terms ("buffer zone*" needs company) -----------------------

    def test_buffer_zone_needs_abortion_context(self):
        """A buffer zone is also a pesticide margin and a military perimeter.

        Until 2026-08-17 "buffer zone*" was an unguarded TIER 1 term for area
        1, so a question about pesticide margins was classified as an abortion
        item at top confidence -- WATCH in the edition, and a row in the area 1
        5CA.
        """
        for title, body in [
                ("Bees and Butterflies: Pesticides", "pesticide buffer zones near watercourses"),
                ("Military Land: Salisbury", "buffer zones around the training estate")]:
            with self.subTest(title):
                self.assertEqual(self.match(title, body).issue_areas, [],
                                 "someone else's buffer zone is not our subject")

    def test_buffer_zone_still_matches_when_company_is_kept(self):
        # Including the euphemism: an item can be about clinic zones without
        # ever using the word "abortion", which is why the guard list carries
        # "clinic*" and "termination*" and not "abortion" alone.
        for title, body in [
                ("Abortion: Clinics", "buffer zones outside abortion clinics"),
                ("Public Order", "buffer zones around clinics providing terminations")]:
            with self.subTest(title):
                self.assertIn(1, self.match(title, body).issue_areas)

    def test_guard_must_be_in_the_same_passage(self):
        """A speech mentioning both, paragraphs apart, is not thereby ours.

        The guard is evaluated against whatever text is being scanned, so in
        match_passages the company has to be kept in the same passage. A
        long speech brushing against abortion once must not retrospectively
        qualify its pesticide paragraph.
        """
        speech = ("I turn to the pesticide regulations. Buffer zones near "
                  "watercourses remain too narrow to protect pollinators.\n\n"
                  "Separately, I congratulate the Minister on the abortion "
                  "statistics published last week.")
        matched = [t for m in filt.match_passages(self.tax, self.wl, speech)
                   for t in m.result.matched_terms]
        self.assertIn("abortion", matched)          # the second paragraph is real
        self.assertNotIn("buffer zone*", matched)   # the first is somebody else's

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

    def test_broad_act_mentioned_in_passing_lends_no_area(self):
        """A shoplifting question citing the Crime and Policing Act was being
        filed under abortion, because that Act carried decriminalisation
        (Christopher, 2026-08-05)."""
        r = self.match("Anti-social Behaviour and Shoplifting",
                       "Asked what the Crime and Policing Act 2026 does about retail theft.")
        self.assertIn("Crime and Policing", r.watchlist_hits)
        self.assertEqual(r.issue_areas, [])        # no abortion tag

    def test_broad_act_in_a_mid_text_passage_lends_no_area(self):
        """Passage matching must not treat every passage as a title, or a
        broad Act cited anywhere in a speech lends its areas again."""
        tax = filt.load_taxonomy(TAXONOMY)
        wl = filt.load_watchlist(WATCHLIST)
        matches = filt.match_passages(
            tax, wl,
            "We must act on retail theft.\n\nThe Crime and Policing Act 2026 "
            "gives police new powers over shoplifting gangs.",
            title="Retail Crime")
        areas, terms, excerpt = filt.aggregate_passages(matches)
        self.assertNotIn(1, areas)

    def test_broad_act_in_the_title_is_the_subject_and_does_lend_its_area(self):
        r = self.match("Crime and Policing Act 2026 (Commencement No. 2) Regulations")
        self.assertIn(1, r.issue_areas)

    def test_broad_act_with_corroborating_term_lends_its_area(self):
        r = self.match("Abortion: Prosecutions",
                       "Asked about section 241 of the Crime and Policing Act 2026.")
        self.assertIn(1, r.issue_areas)

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


class UnTaxonomyTests(unittest.TestCase):
    """The UN taxonomy: same eleven areas, the UN's vocabulary.

    Exists because taxonomy.yaml matched ZERO of the fifteen OHCHR calls open
    on 2026-08-17 -- it reads British legislative vocabulary, and these are UN
    thematic titles.
    """

    @classmethod
    def setUpClass(cls):
        cls.un = filt.load_taxonomy(os.path.join(ROOT, "config", "un-taxonomy.yaml"))
        cls.uk = filt.load_taxonomy(TAXONOMY)
        cls.wl = filt.load_watchlist(WATCHLIST)

    def areas(self, text, tax=None):
        return filt.filter_item(tax or self.un, self.wl, text).issue_areas

    def test_reads_un_set_phrases_the_uk_taxonomy_misses(self):
        for text, area in [
                ("comprehensive sexuality education in schools", 6),
                ("child, early and forced marriage", 9),
                ("sexual and reproductive health and rights", 1),
                ("freedom of religion or belief", 8),
                ("legal gender recognition based on self-identification", 5)]:
            with self.subTest(text):
                self.assertIn(area, self.areas(text))

    def test_right_to_life_needs_the_unborn_context(self):
        """In UN usage "right to life" is overwhelmingly death-penalty work,
        so the term is guarded rather than claimed for area 1."""
        self.assertEqual(self.areas("abolish the death penalty and protect the right to life"), [])
        self.assertIn(1, self.areas("protect the right to life from conception"))

    def test_migrant_workers_no_longer_fires(self):
        """Removed after measuring: 11 hits in 299 unfiltered recommendations,
        every one a generic treaty-accession line."""
        self.assertEqual(
            self.areas("Accede to the Convention on the Rights of All Migrant Workers"), [])

    def test_areas_match_the_parliamentary_taxonomy_exactly(self):
        """Two vocabularies, one set of areas -- otherwise a UN item could
        not be filed alongside a Westminster one."""
        self.assertEqual(sorted(self.un.terms), sorted(self.uk.terms))


class CivilLibertiesTermTests(unittest.TestCase):
    """Area 7 widened at taxonomy v0.6 (Christopher, 2026-08-20).

    Health sovereignty and digital ID had no home in the eleven areas. The
    risky term is bare WHO, which is also an English pronoun.
    """

    @classmethod
    def setUpClass(cls):
        cls.tax = filt.load_taxonomy(
            os.path.join(ROOT, "config", "taxonomy.yaml"))
        cls.wl = filt.load_watchlist(
            os.path.join(ROOT, "config", "watchlist.yaml"))

    def _areas(self, text):
        return filt.filter_item(self.tax, self.wl, text).issue_areas or []

    def test_who_the_pronoun_never_matches(self):
        """Bare WHO is ALL-CAPS, so it matches case-sensitively -- the same
        convention that stops RSE matching "nurse"."""
        for text in ("Members who wish to speak should indicate",
                     "Ministers who have not yet replied to letters",
                     "Ask the Secretary of State who is responsible"):
            self.assertNotIn(7, self._areas(text), text)

    def test_who_alone_is_guarded_as_well_as_case_sensitive(self):
        """Case-sensitivity does not survive an ALL-CAPS heading, and most WHO
        mentions are global health aid rather than sovereignty, so the term
        also requires company."""
        self.assertNotIn(7, self._areas(
            "The WHO published guidance on malaria nets"))
        self.assertIn(7, self._areas(
            "The WHO pandemic accord was signed in Geneva"))

    def test_the_who_name_spelled_out_needs_company_too(self):
        """v0.8. Unguarded, it filed the NI motion "Addressing the Mental
        Health Crisis" under area 7: its text only says the recommendations
        "align with recent calls from the World Health Organisation and the
        United Nations for systematic mental health reform". WHO as a research
        citation, not health sovereignty -- and any health motion citing WHO
        would have done the same."""
        self.assertNotIn(7, self._areas(
            "recommendations align with recent calls from the World Health "
            "Organisation and the United Nations for mental health reform"))
        self.assertNotIn(7, self._areas(
            "World Health Organization guidance on malaria nets"))
        self.assertIn(7, self._areas(
            "World Health Organisation pandemic treaty negotiations resume"))

    def test_health_sovereignty_terms(self):
        for text in ("Pandemic treaty negotiations resume",
                     "Withdraw from the International Health Regulations",
                     "The UK should exit the IHR before the deadline"):
            self.assertIn(7, self._areas(text), text)

    def test_digital_id_terms(self):
        for text in ("Digital ID: Public Consultation",
                     "Plans for a digital identity system",
                     "Central Bank Digital Currency consultation",
                     "The BritCard proposal"):
            self.assertIn(7, self._areas(text), text)

    def test_existing_area_seven_terms_still_match(self):
        """Regression: widening must not disturb what area 7 already caught."""
        for text in ("Online Safety Act enforcement by Ofcom",
                     "non-crime hate incidents recorded by police",
                     "Higher Education (Freedom of Speech) Act duties",
                     "age verification for pornography sites"):
            self.assertIn(7, self._areas(text), text)

    def test_nursing_items_do_not_reach_area_seven(self):
        self.assertNotIn(7, self._areas("Nurse recruitment in the NHS"))


class AreaNameOverrideTests(unittest.TestCase):
    """area_names() prefers an explicit `name:`, falling back to the key.

    The override exists because make_5ca.py builds CSV FILENAMES from the
    label, so relabelling an area renames its sheets. Only area 7 declares a
    name; the other ten must keep the derived label and their filenames.
    """

    def test_area_seven_uses_the_declared_name(self):
        names = intel.area_names(
            os.path.join(ROOT, "config", "taxonomy.yaml"))
        self.assertEqual(names[7], "Free speech, privacy and civil liberties")

    def test_the_other_ten_keep_the_key_derived_label(self):
        names = intel.area_names(
            os.path.join(ROOT, "config", "taxonomy.yaml"))
        self.assertEqual(names[1], "Abortion")
        self.assertEqual(names[2], "Assisted dying")
        self.assertEqual(names[5], "Sex based rights")
        self.assertEqual(names[11], "Migration")

    def test_a_taxonomy_without_name_fields_is_unchanged(self):
        """config/un-taxonomy.yaml is hand-maintained and declares no names."""
        names = intel.area_names(
            os.path.join(ROOT, "config", "un-taxonomy.yaml"))
        self.assertEqual(names[7], "Free speech online safety")
        self.assertEqual(len(names), 11)
