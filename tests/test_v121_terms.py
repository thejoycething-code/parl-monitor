"""Taxonomy v1.21 (Christopher, 9 October 2026: "add the three terms").

The Senate amendment-purpose work (docs/us-scope.md, "Senate amendment
purposes") found three real Senate votes that stopped inheriting their bill's
areas and then matched nothing, because the taxonomy did not say the Senate's
words. Each purpose below is the stored one, verbatim; the noise cases are the
measured reasons for each veto, narrowing or rejection in
docs/keyword-taxonomy.md.
"""

import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import filter as filt  # noqa: E402


def _load():
    spec = importlib.util.spec_from_file_location(
        "us_rollcalls", os.path.join(ROOT, "tools", "us_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


usr = _load()
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])

# (stored description, area): Senate 2025 votes 356 and 358 on H.R. 1, and
# vote 402 on H.R. 4. The description is 'vote title | purpose | purpose'.
SENATE_VOTES = [
    ("Motion to Waive All Applicable Budgetary Discipline Re: Kennedy Amdt. No. 2775 | "
     "To amend the Internal Revenue Code of 1986 to provide a deduction for expenses of "
     "home educators. | To amend the Internal Revenue Code of 1986 to provide a deduction "
     "for expenses of home educators.", "S.Amdt. 2775", 6),
    ("Hirono Amdt. No. 2382 | To eliminate a program of qualified elementary and secondary "
     "education scholarships for public, private, or religious schools. | To eliminate a "
     "program of qualified elementary and secondary education scholarships for public, "
     "private, or religious schools.", "S.Amdt. 2382", 6),
    ("Rosen Amdt. No. 2878 | To strike the rescission of funds appropriated for Global "
     "Health programs, including family planning and reproductive health. | To strike the "
     "rescission of funds appropriated for Global Health programs, including family "
     "planning and reproductive health.", "S.Amdt. 2878", 1),
]


def areas(*text):
    return filt.filter_item(TAX, WL, *text).issue_areas


CAUGHT = [
    # area 6, home education (tier 1)
    ("To ask the Scottish Government whether specific COVID-19 guidance for home educators "
     "will be published.", 6),
    ("It is the responsibility of the home-educator to contact their local authority", 6),
    ("Home School Graduation Recognition Act", 6),
    ("Requires home schooled students to participate in certain annual in person "
     "assessments", 6),
    ("To ask the Scottish Government how many children have been home-schooled in each of "
     "the last five years.", 6),
    # area 6, school choice (tier 2)
    ("Universal School Choice Act", 6),
    ("National School Choice Week, 2026", 6),
    ("Federal Scholarship Tax Credit: qualified contributions to scholarship granting "
     "organizations", 6),
    ("Education Freedom Scholarships and Opportunity Act", 6),
    # area 1 (tier 2)
    ("Expanding Access to Family Planning Act", 1),
    ("Prohibits deceptive advertising for reproductive health services.", 1),
]

LEFT_ALONE = [
    # a home-school link worker is a council post, not home education
    ("how many schools currently have a home-school link worker", 6),
    ("Heather Longmuir, a respected home school liaison officer, has retired", 6),
    # bare "reproductive health" was rejected: maternal and gynaecological
    # health, and the Simpson Centre for Reproductive Health (a maternity unit)
    ("A resolution recognizing the seriousness of polycystic ovary syndrome and its "
     "effect on reproductive health", 1),
    ("knitting baby hats for the maternity unit at the Simpson Centre for Reproductive "
     "Health", 1),
    # "religious school*" was rejected: Canadian hate-crime and security debates
    ("shouted threats at parents outside a religious school", 6),
    # "school voucher*" was rejected: prize vouchers
    ("the first prize awarded to the pupils was 500 pounds worth of school vouchers", 6),
    # higher-education scholarships are not school choice
    ("Strengthening Pathways to Health Professions Act: higher education scholarships", 6),
]


class SenatePurposeTests(unittest.TestCase):
    def test_the_three_senate_votes_stand_on_their_own_purpose(self):
        for desc, num, area in SENATE_VOTES:
            purpose = usr.senate_purpose(desc, num)
            self.assertTrue(purpose, desc)
            d = {"description": desc, "question": "", "amendment_author": None,
                 "amendment_text": purpose, "chamber": "senate"}
            own, combined = usr.classify_division(TAX, WL, d, [1, 5, 6, 11])
            # the purpose is the vote's own subject: H.R. 1's areas are not lent
            self.assertEqual(combined, [area], desc)
            self.assertEqual(own.issue_areas, [area], desc)


class V121TermTests(unittest.TestCase):
    def test_each_measured_text_lands_in_its_area(self):
        for text, area in CAUGHT:
            self.assertIn(area, areas(text), text)

    def test_the_vetoes_and_rejections_hold(self):
        for text, area in LEFT_ALONE:
            self.assertNotIn(area, areas(text), text)

    def test_home_education_is_tier_one_and_school_choice_tier_two(self):
        self.assertEqual(filt.filter_item(TAX, WL, "a deduction for expenses of home "
                                                    "educators").tier, 1)
        self.assertEqual(filt.filter_item(TAX, WL, "Universal School Choice Act").tier, 2)

    def test_family_planning_is_tier_two(self):
        # contraception is area 1 tier 2 by decision (v1.17); family planning
        # sits with it, so triage keeps only what touches life.
        self.assertEqual(filt.filter_item(TAX, WL, "family planning services").tier, 2)

    def test_a_veto_does_not_silence_the_existing_home_schooling_term(self):
        res = filt.filter_item(TAX, WL, "home schooling, and the home-school link worker")
        self.assertIn(6, res.issue_areas)
        self.assertNotIn("home-school*", res.matched_terms)


if __name__ == "__main__":
    unittest.main()
