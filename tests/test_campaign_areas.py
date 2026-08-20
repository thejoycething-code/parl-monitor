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

    BY_PID = {13425: [5], 16792: []}

    def test_the_petition_id_wins_over_the_slug(self):
        """'Support NHS nurses in their fi' is cut mid-word; the local row says
        'Stand with Darlington nurses for safe spaces for women', area 5."""
        areas, source = llc.resolve_areas(
            "EN_GB-2024-06-28-Local-NA-ZRE-13425-Support_NHS_nurses_in_their_fi",
            "Support NHS nurses in their fi", self.BY_PID)
        self.assertEqual(areas, [5])
        self.assertIn("petition-id join", source)

    def test_an_empty_local_mapping_is_an_answer_not_a_miss(self):
        """The curated sweep looked at Sadiq Khan and left it out of the
        taxonomy. Falling through to keywords would overrule that silently."""
        areas, source = llc.resolve_areas(
            "EN_GB-2025-10-20-Local-OT-ZRE-16792-Demand_Sadiq_Khans_Resignation",
            "Demand Sadiq Khans Resignation", self.BY_PID)
        self.assertEqual(areas, [])
        self.assertIn("petition-id join", source)

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
