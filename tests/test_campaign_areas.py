"""Campaign name -> taxonomy area, for both benchmark sources.

The mapping feeds RF#1 baselines, so a wrong area does not fail loudly -- it
quietly moves the median a campaigner is told to expect. These tests pin the
cases that were actually wrong, with the evidence in each docstring.
"""

import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import log_campaign_performance as lcp
import load_looker_campaigns as llc


class RseAnchorTests(unittest.TestCase):
    """RSE is Relationships and Sex Education, not the tail of another word."""

    def test_word_endings_are_not_rse(self):
        for name in ("Reverse deadly DIY abortion decision in Wales",
                     "Justice for Jennifer: Nurse disciplined over pronouns",
                     "On Trial for a Bible Verse: Free Speech in Finland",
                     "Stand with Sarah Morse"):
            self.assertNotIn(
                6, lcp.areas_for(name),
                "'{0}' reached area 6 through a word ending".format(name))

    def test_real_rse_campaigns_still_map(self):
        for name in ("Children at risk! Block safeguarding loopholes in RSE",
                     "Uphold Parental Rights to withdraw children from RSE!",
                     "For 100% safeguarding - Set up RSE Watchdog!"):
            self.assertIn(6, lcp.areas_for(name), name)

    def test_a_pupils_question_is_still_education(self):
        """Sarah Morse held area 6 only via the Morse/rse false positive.
        \\bpupil keeps it, for the actual reason."""
        self.assertIn(6, lcp.areas_for(
            "Sacked for Answering a Pupil's Question Honestly: Sarah Morse"))


class KeywordGapTests(unittest.TestCase):
    """Each gap is a real campaign from the widened Looker export."""

    CASES = (
        ("Exposing Stella Creasy's danger", 1),
        ("CSW68", 1),
        ("Stop the UN's New Attack on Life and Family at CSW70!", 1),
        ("Reject EU's Same-Sex Parenthood Certificate", 9),
        ("PDC: Protect Darts Competition for Women!", 5),
        ("Say NO to LGBT Youth Scotland in Scottish Primary Schools", 6),
        ("Stand with Keira and James: Stop Puberty Blocker Trials", 3),
        ("Justice for Jennifer", 3),
    )

    def test_each_gap_now_maps(self):
        for name, area in self.CASES:
            self.assertIn(area, lcp.areas_for(name), name)

    def test_for_women_needs_a_noun_and_does_not_swallow_everything(self):
        """A bare 'for women' would map any campaign mentioning women to sex
        based rights."""
        self.assertNotIn(5, lcp.areas_for("Justice for women in Nigeria"))


class CivilLibertiesTests(unittest.TestCase):
    """Area 7 widened to civil liberties, Christopher 2026-08-20.

    ~400,000 signatures of EN GB campaigning on health sovereignty, digital ID
    and UN governance had no benchmark. Widened rather than given a new area
    because digital ID ALREADY landed in 7: 31 of 32 ledger rows carrying it
    were tagged via "age verification" and "Online Harms".
    """

    HEALTH_SOVEREIGNTY = (
        "Say NO to the WHO's Health Dictatorship-Reject the Pandemic Treaty!",
        "Break Free from UN Control: Reject the International Health Regulations",
        "Defund the World Health Organization",
        "Exit IHR Pandemic",
        "accelerated push pandemic-INB Meeting 11th",
    )
    DIGITAL_ID = (
        "No Digital ID: Stop the Surveillance State",
        "Stop Starmer's Stealth Digital ID Scheme Hidden in the Schools Bill",
        "Digital Totalitarianism",
    )
    UN_GOVERNANCE = (
        "Reject Agenda 2030! Don't Let the UN Rewrite Your Future",
        "Doha Summit: Stop the UN's Agenda 2030 Power Grab",
    )

    def test_health_sovereignty_maps_to_seven(self):
        for name in self.HEALTH_SOVEREIGNTY:
            self.assertIn(7, lcp.areas_for(name), name)

    def test_digital_id_maps_to_seven(self):
        for name in self.DIGITAL_ID:
            self.assertIn(7, lcp.areas_for(name), name)

    def test_un_governance_maps_to_seven(self):
        """The flagged pair -- UN governance rather than the three issues named,
        included so 36,000 signatures are not left unmapped. One line to
        strike in KEYWORD_AREAS if unwanted."""
        for name in self.UN_GOVERNANCE:
            self.assertIn(7, lcp.areas_for(name), name)

    def test_acronyms_are_word_anchored_here(self):
        """This list is a separate LOWERCASE layer and does not inherit the
        taxonomy's all-caps case-sensitivity -- the same gap that let "rse\\b"
        match "nurse". So the acronyms must be \\b-anchored."""
        for name in ("Inbox zero campaign", "Their inbuilt bias",
                     "Sinbad the sailor"):
            self.assertNotIn(7, lcp.areas_for(name), name)

    def test_existing_area_seven_campaigns_are_unaffected(self):
        for name in ("Repeal the Online Safety Act",
                     "Stand in solidarity with Simon: Teacher sacked over "
                     "lawful Facebook posts"):
            self.assertIn(7, lcp.areas_for(name), name)

    def test_islamophobia_campaigns_reach_seven_like_the_taxonomy(self):
        """The two layers disagreed. config/taxonomy.yaml puts Islamophobia and
        "Islamophobia definition" in area 7, but KEYWORD_AREAS had no pattern
        for it, so "Defend the freedom to critique Islam - stop 'Islamophobia'
        blasphemy law" reached only area 8 via "blasphem". It is both a
        blasphemy-law and a free-speech campaign, and the campaign layer should
        not disagree with the parliamentary one about which."""
        areas = lcp.areas_for("Defend the freedom to critique Islam - stop "
                              "'Islamophobia' blasphemy law")
        self.assertIn(7, areas)
        self.assertIn(8, areas)


class ProgramParseTests(unittest.TestCase):

    def test_three_letter_topic_code_parses(self):
        """FM and FAM both occur. Demanding two letters dropped 'Demand BBC
        Children In Need CEO Resigns!' -- 14,583 signatures -- as unnamed."""
        listname, name = llc.parse_program(
            "EN_GB-2024-22-11-Local-FAM-ZRE-14402-Children_in_Need_Funding")
        self.assertEqual(listname, "EN_GB")
        self.assertEqual(name, "Children in Need Funding")

    def test_two_letter_code_still_parses(self):
        _, name = llc.parse_program(
            "EN_GB-2024-06-11-Global-FM-CJO-13320-Parenthood_Recognition_EU")
        self.assertEqual(name, "Parenthood Recognition EU")


class ResolveAreasTests(unittest.TestCase):
    """The petition id is an exact key and beats matching a truncated slug."""

    # {pid: ([areas], local_name)} -- resolve_areas needs the local NAME too,
    # so out_of_taxonomy can be checked against the public petition title.
    BY_PID = {13425: ([5], "Stand with Darlington nurses for safe spaces"),
              15317: ([], "Sign Our Open Letter to Candidates")}

    def test_the_petition_id_wins_over_the_slug(self):
        """'Support NHS nurses in their fi' is cut mid-word; the local row says
        'Stand with Darlington nurses for safe spaces for women', area 5."""
        areas, source = llc.resolve_areas(
            "EN_GB-2024-06-28-Local-NA-ZRE-13425-Support_NHS_nurses_in_their_fi",
            "Support NHS nurses in their fi", self.BY_PID)
        self.assertEqual(areas, [5])
        self.assertIn("petition-id join", source)

    def test_a_settled_exclusion_survives_the_slug(self):
        """Was "an empty local mapping is an answer", using Sadiq Khan as the
        example. Christopher's 2026-08-20 decision maps that campaign to area 6
        (CSE), so the example is superseded -- but the principle still holds and
        is now enforced by out_of_taxonomy being the final authority, rather
        than by an empty area list blocking the slug."""
        areas, source = llc.resolve_areas(
            "EN_GB-2025-04-25-Local-NA-CJO-15317-UK_Local_Elections_Open_Letter",
            "UK Local Elections Open Letter", self.BY_PID)
        self.assertEqual(areas, [])
        self.assertIn("out of taxonomy", source)

    def test_keywords_are_the_fallback_when_the_id_is_absent(self):
        """Six programs carry no usable id (-NA- or an empty segment), and the
        ids disagree between systems for at least one campaign."""
        areas, source = llc.resolve_areas(
            "EN_GB-2024-02-15-Global-FM-CJO-NA-CSW68-CSW68", "CSW68",
            self.BY_PID)
        self.assertEqual(areas, [1])
        self.assertIn("keywords", source)

    def test_no_id_and_no_name_is_reported_not_guessed(self):
        areas, source = llc.resolve_areas("garbage", "", {})
        self.assertEqual(areas, [])
        self.assertIn("unresolved", source)


if __name__ == "__main__":
    unittest.main()


class SmartQuoteAndSlugTests(unittest.TestCase):
    """Two silent matching failures, both found on 2026-08-20."""

    def test_curly_apostrophes_are_folded(self):
        """src/filter.py folds smart quotes for the taxonomy; KEYWORD_AREAS did
        not. 31 of 366 campaign names carry a curly apostrophe, and nothing was
        affected only by luck -- until "children'?s rights" was added and
        matched "Don\u2019t Let the UN Redefine Children\u2019s Rights!" not at all."""
        self.assertIn(6, lcp.areas_for(
            "Don\u2019t Let the UN Redefine Children\u2019s Rights!"))
        self.assertIn(6, lcp.areas_for(
            "Don't Let the UN Redefine Children's Rights!"))

    def test_hyphen_delimited_slugs_match(self):
        """Looker names are program slugs and punctuation there is arbitrary:
        parse_program folds underscores but not hyphens, so
        "Virgin-Island-Scrap-Show" kept its hyphens and matched nothing."""
        self.assertIn(6, lcp.areas_for("Virgin-Island-Scrap-Show"))
        self.assertIn(6, lcp.areas_for("'Virgin Island': Scrap Outrageous Show"))

    def test_real_hyphens_in_patterns_still_match(self):
        """Regression on the fix: testing a de-hyphenated variant must not stop
        patterns that want a genuine hyphen from matching the original."""
        self.assertIn(1, lcp.areas_for("Join the pro-life fightback"))
        self.assertIn(5, lcp.areas_for("Protect single-sex wards"))
        self.assertIn(7, lcp.areas_for("Scrap non-crime hate incidents"))


class OutOfTaxonomyTests(unittest.TestCase):
    """A settled decision must not read as an unfixed gap.

    Without this the same rows were re-litigated every time somebody read the
    unmapped list. Each reason states its own status.
    """

    def test_settled_exclusions_carry_a_reason(self):
        for name in ("Sign Our Open Letter to Candidates: Tell Them What "
                     "Matters To You",
                     "Your Local Councillors Have More Power Than You Think",
                     "Stop divisive Progress Pride flag displays",
                     "Fundraising-Stay Out",
                     "TEST-Stop UN Thought Police"):
            self.assertIsNotNone(lcp.out_of_taxonomy(name), name)

    def test_nothing_is_left_open(self):
        """Both open questions were closed by Christopher on 2026-08-20 -- CSE
        to area 6, and the BBC campaign to area 3 once he said what it was
        about. Every entry left in the registry is SETTLED, and the campaigns
        that used to sit there now carry an area."""
        for _, reason in lcp.OUT_OF_TAXONOMY:
            self.assertNotIn("OPEN QUESTION", reason, reason[:50])
        for closed, area in (
                ("Telford: End the Sexual Abuse - Enforce the Law", 6),
                ("Demand Sadiq Khan's Resignation: Failing London and "
                 "Ignoring Abuse", 6),
                ("Demand BBC Children In Need CEO Resigns!", 3)):
            self.assertIsNone(lcp.out_of_taxonomy(closed), closed)
            self.assertIn(area, lcp.areas_for(closed), closed)

    def test_children_in_need_is_anchored_to_bbc_or_ceo(self):
        """Bare "children in need" is the statutory social-care term (s17
        Children Act, the Children in Need census). Unanchored, it would file a
        social-care campaign under gender medicine."""
        self.assertIn(3, lcp.areas_for("Demand BBC Children In Need CEO Resigns!"))
        self.assertNotIn(3, lcp.areas_for(
            "Publish the children in need census data in full"))

    def test_a_mapped_campaign_is_not_listed_as_out_of_scope(self):
        """The registry must never explain away something that has an area."""
        for name in ("Repeal the Online Safety Act",
                     "No Digital ID: Stop the Surveillance State",
                     "Runcorn and Helsby by-election: A life and death vote"):
            self.assertTrue(lcp.areas_for(name), name)
            self.assertIsNone(lcp.out_of_taxonomy(name), name)

    def test_by_elections_are_mapped_by_subject_not_excluded(self):
        """Gorton and Denton is [3,7] and Makerfield [4,3,7], so a by-election
        naming a subject is mapped by it; only generic election tools are out."""
        self.assertIn(2, lcp.areas_for(
            "Runcorn and Helsby by-election: A life and death vote"))
        self.assertIsNotNone(lcp.out_of_taxonomy(
            "Sign Our Open Letter to Candidates"))


class ChildSexualExploitationTests(unittest.TestCase):
    """CSE belongs in area 6, child protection (Christopher, 2026-08-20).

    It previously had four homes: Telford unmapped, Sadiq Khan unmapped, the
    grooming-gangs cover-up campaign at area 7 via its open-justice ask, and
    "Deport Shabir Ahmed" under migration.
    """

    def test_cse_campaigns_map_to_child_protection(self):
        for name in ("Telford: End the Sexual Abuse - Enforce the Law",
                     "Demand Sadiq Khan's Resignation: Failing London and "
                     "Ignoring Abuse",
                     "Grooming Gangs Stop the cover",
                     "Rotherham: rape gang cover-up"):
            self.assertIn(6, lcp.areas_for(name), name)

    def test_grooming_products_are_not_child_protection(self):
        """The bare "groom" pattern used to sit in area 3 and its only hit was
        a razor brand. It must reach neither 3 by that route nor 6."""
        areas = lcp.areas_for(
            "Boycott Braun: Grooming brand glamourises mutilation")
        self.assertNotIn(6, areas)
        self.assertIn(3, areas, "still area 3, via 'mutilat'")

    def test_the_deportation_campaign_is_dual_tagged(self):
        """"Deport Shabir Ahmed Now! Protect Our Children From Predators" is a
        grooming-gang case whose ASK is deportation, so it sits in area 11 too.
        Christopher chose to dual-tag it (2026-08-20) after being shown that
        this makes it VISIBLE: make_briefs strips excluded areas and keeps the
        rest, so [11, 6] appears in area 6 briefs with migration hidden."""
        areas = lcp.areas_for(
            "Deport Shabir Ahmed Now! Protect Our Children From Predators")
        self.assertIn(11, areas)
        self.assertIn(6, areas)

    def test_stripping_an_excluded_area_leaves_the_rest(self):
        """The mechanism the dual-tag relies on, pinned so it cannot drift into
        an any-match exclusion that would re-hide the campaign."""
        import make_briefs as mb
        kept = [a for a in [11, 6] if a not in mb.EXCLUDED_AREAS]
        self.assertEqual(kept, [6])
        self.assertEqual([a for a in [11] if a not in mb.EXCLUDED_AREAS], [])

    def test_cse_is_no_longer_an_open_question(self):
        self.assertIsNone(lcp.out_of_taxonomy(
            "Telford: End the Sexual Abuse - Enforce the Law"))


class ResolveAreasUnionTests(unittest.TestCase):
    """The public petition title and the internal working title each carry
    vocabulary the other lacks, so the two are unioned."""

    BY_PID = {17624: ([7], "Lammy, Starmer: Protect Open Justice, Reinstate "
                           "CourtDesk"),
              15317: ([], "Sign Our Open Letter to Candidates: Tell Them What "
                          "Matters To You"),
              13425: ([5], "Stand with Darlington nurses for safe spaces")}

    def test_the_slug_adds_what_the_public_title_cannot_say(self):
        """Petition 17624 is "Protect Open Justice" publicly and
        "Grooming_Gangs_Stop_the_cover" internally. Only the slug says what it
        is about, so mapping from the local name alone missed area 6."""
        areas, source = llc.resolve_areas(
            "EN_GB-2026-02-12-Local-NA-ZRE-17624-Grooming_Gangs_Stop_the_cover",
            "Grooming Gangs Stop the cover", self.BY_PID)
        self.assertIn(7, areas)
        self.assertIn(6, areas)
        self.assertIn("slug keywords", source)

    def test_a_settled_exclusion_cannot_be_undone_by_a_slug(self):
        """out_of_taxonomy is the final authority."""
        areas, source = llc.resolve_areas(
            "EN_GB-2025-04-25-Local-NA-CJO-15317-UK_Local_Elections_Open_Letter",
            "UK Local Elections Open Letter", self.BY_PID)
        self.assertEqual(areas, [])
        self.assertIn("out of taxonomy", source)

    def test_a_slug_never_removes_a_curated_area(self):
        areas, _ = llc.resolve_areas(
            "EN_GB-2024-06-28-Local-NA-ZRE-13425-Support_NHS_nurses_in_their_fi",
            "Support NHS nurses in their fi", self.BY_PID)
        self.assertIn(5, areas)
