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
        # v0.9: RSE needs education company (in Scotland it is also the Royal
        # Society of Edinburgh). "guidance" is in the guard, so this realistic
        # heading still matches; a bare acronym with no education word at all
        # no longer does, and the Society's honorary degrees never did carry
        # one -- measured on the first Holyrood pull, 3 of 5 RSE rows were the
        # Society.
        self.assertIn(6, self.match("New RSE guidance published").issue_areas)
        self.assertNotIn(6, self.match(
            "Royal Society of Edinburgh Recognises Dundee Scientists RSE"
            ).issue_areas)

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


class ConversionCarveOutTests(unittest.TestCase):
    """v1.6 (Christopher, 2026-09-04): whether ordinary prayer and pastoral
    support fall inside a conversion-practices ban is the whole contested
    ground of the UK debate, and none of it was catchable.

    Every term is guarded, because bare "prayer" is worse than noisy: the
    matcher works on substrings, so across 20,539 items it matched "World
    Day of Prayer" and a paint SPRAYER in a royal-warrant motion.
    """

    @classmethod
    def setUpClass(cls):
        cls.tax = filt.load_taxonomy(TAXONOMY)
        cls.wl = filt.load_watchlist(WATCHLIST)

    def match(self, *fields):
        return filt.filter_item(self.tax, self.wl, *fields)

    def test_the_carve_out_debate_is_caught(self):
        r = self.match("To ask whether hospital chaplains may pray with "
                       "patients who request it, and whether the conversion "
                       "practices ban affects pastoral care")
        self.assertIn(4, r.issue_areas)

    def test_prayer_without_the_debate_is_not(self):
        self.assertNotIn(4, self.match("World Day of Prayer 2024").issue_areas)
        self.assertNotIn(4, self.match(
            "Alan Scott Panel Beater and Paint Sprayer Granted Royal "
            "Warrant").issue_areas)

    def test_the_buffer_zone_fight_stays_where_it_was(self):
        """"silent prayer" is area 7's buffer-zone offence and area 1's
        clinic ground. A guarded "prayer" in area 4 must not annex it."""
        areas = self.match("Silent prayer within a safe access zone").issue_areas
        self.assertIn(7, areas)
        self.assertNotIn(4, areas)

    def test_unambiguous_terms_need_no_guard(self):
        self.assertIn(4, self.match("Spiritual abuse in church "
                                    "settings").issue_areas)


class ProstitutionAreaTests(unittest.TestCase):
    """Area 12, new at v1.6. Nothing in the eleven areas covered the
    Nordic-model ground; the only term reaching it was bare `prostitution`
    in area 5, which filed a live Scottish Bill and an EP report on
    regulating prostitution under single-sex spaces."""

    @classmethod
    def setUpClass(cls):
        cls.tax = filt.load_taxonomy(TAXONOMY)
        cls.wl = filt.load_watchlist(WATCHLIST)

    def match(self, *fields):
        return filt.filter_item(self.tax, self.wl, *fields)

    def test_the_live_bill_lands_in_its_own_area(self):
        areas = self.match("Prostitution (Offences and Support) "
                           "(Scotland) Bill").issue_areas
        self.assertIn(12, areas)
        self.assertNotIn(5, areas, "it left area 5 at v1.6")

    def test_the_demand_side_vocabulary(self):
        self.assertIn(12, self.match("Combatting Commercial Sexual "
                                     "Exploitation").issue_areas)
        self.assertIn(12, self.match("Adopting the Nordic model to tackle "
                                     "demand for prostitution").issue_areas)

    def test_the_other_nordic_model_is_a_different_debate(self):
        self.assertEqual(self.match("The Nordic model of labour market "
                                    "flexibility and welfare").issue_areas, [])

    def test_child_sexual_exploitation_is_not_annexed(self):
        """Bare "sexual exploitation" was deliberately left out: 17 items
        carry it and most are child protection, which area 6 owns."""
        areas = self.match("Child sexual exploitation in Rotherham").issue_areas
        self.assertIn(6, areas)
        self.assertNotIn(12, areas)


class FamilyEconomicsTests(unittest.TestCase):
    """v1.6, scoped NARROW on measurement: childcare (61 unmatched items),
    child poverty (60) and maternity (32) are devolved service
    administration, not family policy. What is ours is the demographic
    argument, which this area already half-carried."""

    @classmethod
    def setUpClass(cls):
        cls.tax = filt.load_taxonomy(TAXONOMY)
        cls.wl = filt.load_watchlist(WATCHLIST)

    def match(self, *fields):
        return filt.filter_item(self.tax, self.wl, *fields)

    def test_the_demographic_argument_is_caught(self):
        self.assertIn(9, self.match("Infertility, the principal medical "
                                    "cause of declining birth rates").issue_areas)
        self.assertIn(9, self.match("Ending the Two-child Benefit "
                                    "Cap").issue_areas)

    def test_service_administration_stays_out(self):
        self.assertEqual(self.match("Funding rates for the early learning "
                                    "and childcare entitlement").issue_areas, [])
        self.assertEqual(self.match("Child Poverty Delivery Plan progress "
                                    "update").issue_areas, [])
        self.assertEqual(self.match("NHS Grampian midwife recruitment and "
                                    "maternity services review").issue_areas, [])


class RecallGapTests(unittest.TestCase):
    """Five gaps found by PROBING realistic phrasings against the filter,
    rather than waiting for each to be missed in the wild (v1.6,
    Christopher, 2026-09-04). Each is a phrase a chamber actually used.
    """

    @classmethod
    def setUpClass(cls):
        cls.tax = filt.load_taxonomy(TAXONOMY)
        cls.wl = filt.load_watchlist(WATCHLIST)

    def match(self, *fields):
        return filt.filter_item(self.tax, self.wl, *fields)

    def test_bare_freedom_of_religion(self):
        """The area carried "freedom of religion or belief" and "religious
        freedom" but not the commonest phrasing of its own subject -- the
        same blind spot "freedom of speech" was at v1.3."""
        self.assertIn(8, self.match("Restrictions on the use of church "
                                    "bells and freedom of religion").issue_areas)
        self.assertIn(8, self.match("International Freedom of Religion or "
                                    "Belief Day").issue_areas)

    def test_bare_gender_recognition(self):
        """The Act and the certificate were both terms, but neither is a
        substring of the Scottish SSI's title."""
        self.assertIn(5, self.match("Gender Recognition (Disclosure of "
                                    "Information) (Scotland) Order 2023"
                                    ).issue_areas)

    def test_forced_conversion_and_anti_conversion_laws(self):
        """The EP resolution on Maria Shahbaz matched only by luck, through
        tier-2 "religious minorit*"."""
        areas = self.match("The abduction, forced conversion and child "
                           "marriage of Maria Shahbaz").issue_areas
        self.assertIn(8, areas)
        self.assertIn(9, areas, "child marriage is area 9's ground")
        self.assertIn(8, self.match("Nepal's anti-conversion law and its use "
                                    "against Christians").issue_areas)

    def test_trafficking_is_campaignable_not_buried_in_migration(self):
        """Area 11 is collated and never campaigned, so filing
        anti-trafficking there would have hidden a campaign family behind
        a flag meant for border policy."""
        for text in ("Amending the Human Trafficking and Exploitation "
                     "(Scotland) Act",
                     "New EU sanctions regime against migrant smuggling and "
                     "human trafficking",
                     "Modern Slavery Act review",
                     "Trafficking for sexual exploitation across EU borders"):
            self.assertIn(12, self.match(text).issue_areas, text)

    def test_bare_trafficking_is_deliberately_not_a_term(self):
        """10 corpus items carry bare "trafficking" and they include
        narco-trafficking and counterfeit goods."""
        self.assertEqual(self.match("Narco-trafficking in Europe's waters: "
                                    "protecting our borders").issue_areas, [])
        self.assertEqual(self.match("Trafficking of counterfeit "
                                    "goods").issue_areas, [])


class HyphenFoldTests(unittest.TestCase):
    """Parliament's detail endpoint writes "single‑sex" with a NON-BREAKING
    hyphen (U+2011). The filter folded smart quotes but not hyphens, so
    the tier-1 term "single-sex space*" failed on a question that plainly
    contained it, and a retag on 2026-09-06 cleared two ledger rows
    (pq:1902205, pq:1902208) before anyone saw why.
    """

    @classmethod
    def setUpClass(cls):
        cls.tax = filt.load_taxonomy(TAXONOMY)
        cls.wl = filt.load_watchlist(WATCHLIST)

    def match(self, *fields):
        return filt.filter_item(self.tax, self.wl, *fields)

    def test_the_real_question_now_matches(self):
        q = ("To ask the Secretary of State for Health and Social Care, whether "
             "his Department will consider adopting or developing national "
             "guidance for NHS trusts on the management of single\u2011sex spaces")
        self.assertIn(5, self.match("NHS Trusts: Gender", q).issue_areas)

    def test_every_hyphen_in_the_family_folds(self):
        for cp in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2212"):
            self.assertIn(5, self.match("single%ssex wards on NHS sites" % cp).issue_areas,
                          "U+%04X did not fold" % ord(cp))

    def test_a_soft_hyphen_is_removed_not_replaced(self):
        self.assertIn(5, self.match("single-sex\u00ad spaces").issue_areas)

    def test_an_em_dash_is_left_alone(self):
        """A clause separator, not a joiner: folding it would not create a
        match and would change quoted excerpts."""
        self.assertEqual(filt._fold("guidance \u2014 similar"), "guidance \u2014 similar")


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
        # DERIVED, not a magic number: the two files must carry the same
        # areas (the test above pins that), so hardcoding the count here
        # meant adding area 12 failed a test about NAME fields.
        parl = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
        self.assertEqual(len(names), len(parl))


class ReligiousEducationTermTests(unittest.TestCase):
    """'religious education' joined area 6 tier 1 at v1.0 (Christopher,
    2026-08-22), prompted by NI's RE Core Syllabus consultation passing
    unmarked. Measured before adding: 24 devolved rows + 4 Westminster,
    every sample on-topic, so no guard is needed."""

    @classmethod
    def setUpClass(cls):
        cls.tax = filt.load_taxonomy(
            os.path.join(ROOT, "config", "taxonomy.yaml"))
        cls.wl = filt.load_watchlist(
            os.path.join(ROOT, "config", "watchlist.yaml"))

    def _res(self, text):
        return filt.filter_item(self.tax, self.wl, text)

    def test_the_term_is_tier_1_area_6(self):
        r = self._res("Consultation on the Religious Education Core Syllabus")
        self.assertIn(6, r.issue_areas or [])
        self.assertEqual(r.tier, 1)

    def test_the_scottish_withdrawal_bill_matches(self):
        r = self._res("Children (Withdrawal from Religious Education and "
                      "Amendment of UNCRC Compatibility Duty) (Scotland) "
                      "Bill")
        self.assertIn(6, r.issue_areas or [])

    def test_religious_alone_is_not_enough(self):
        self.assertEqual(
            self._res("a religious charity funding higher education "
                      "bursaries").issue_areas or [], [],
            "the words apart must not match: it is the phrase that is "
            "precise")


class VawgTermTests(unittest.TestCase):
    """VAWG vocabulary joined area 5 tier 2 at v1.1 (Christopher,
    2026-08-22). Tier 2 on the Equality Act logic: 72 devolved + 103
    Westminster rows measured, and MOST are strategy administration and
    awareness weeks -- triage gates them; the definition-of-woman and
    single-sex-service slice is what scores."""

    @classmethod
    def setUpClass(cls):
        cls.tax = filt.load_taxonomy(
            os.path.join(ROOT, "config", "taxonomy.yaml"))
        cls.wl = filt.load_watchlist(
            os.path.join(ROOT, "config", "watchlist.yaml"))

    def _res(self, text):
        return filt.filter_item(self.tax, self.wl, text)

    def test_the_phrase_is_tier_2_area_5(self):
        r = self._res("a strategy to prevent violence against women and "
                      "girls in Scotland")
        self.assertIn(5, r.issue_areas or [])
        self.assertEqual(r.tier, 2)

    def test_vawdasv_is_the_welsh_statutory_frame(self):
        r = self._res("an update on the VAWDASV national indicators")
        self.assertIn(5, r.issue_areas or [])

    def test_acronyms_are_case_sensitive(self):
        self.assertEqual(self._res("the vawg conference").issue_areas or [],
                         [])

    def test_the_bare_shorter_phrase_does_not_match(self):
        self.assertEqual(
            self._res("a history of violence against women in "
                      "literature").issue_areas or [], [],
            "only the full statutory phrase matches -- 'violence against "
            "women' alone is not a term")
