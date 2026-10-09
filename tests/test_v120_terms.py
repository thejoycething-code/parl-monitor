"""Taxonomy v1.20 (Christopher, 9 October 2026: "Add the state keyword and
other candidates to the taxonomy"). Each title is a real one from the store,
the Open States bulk files or the Oireachtas and APH records, as measured for
docs/keyword-taxonomy.md; the noise cases are the measured reasons for each
guard, veto or rejection."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import filter as filt  # noqa: E402

TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def areas(*text):
    return filt.filter_item(TAX, WL, *text).issue_areas


CAUGHT = [
    # area 1
    ("Signed EDM: At home abortions", 1),
    ("REPORTING OF INDUCED ABORTIONS", 1),
    ("Changes to born alive infant provisions made.", 1),
    ("Proposes constitutional amendment recognizing fundamental right to reproductive freedom.", 1),
    ("Legally protected health care activity.", 1),
    ("D.C. Shield Law Repeal Act", 1),
    # area 2
    ("An Act relative to end of life options", 2),
    ("Dying with Dignity Bill 2020", 2),
    # area 3
    ("Relating to prohibiting a public school teacher from supporting a student's gender "
     "transition; protecting minors", 3),
    ("Protecting Minors from Gender Transition Act", 3),
    ("Help Not Harm Act", 3),
    # area 5
    ("Relating to Women's Bill of Rights", 5),
    ("Sex Discrimination Amendment (Sex-based Rights) Bill 2026", 5),
    ("Riley Gaines Act", 5),
    ("SCH CD-BIO SEX-RESTROOM ACCESS", 5),
    # area 6
    ("Criminal Code Amendment (Using Technology to Generate Child Abuse Material) Bill 2025", 6),
    ("Online Safety Amendment (Strengthening Enforcement for the Social Media Minimum Age) Bill 2026", 6),
    ("Materials Harmful to Minors", 6),
    ("Prohibiting drag shows from being performed in front of minors", 6),
    ("Parental Choice in Education: Motion (Resumed) [Private Members]", 6),
    # area 7
    ("Online Safety (Recommender Algorithms) Bill 2026", 7),
    ("Office of the eSafety Commissioner; Order for the Production of Documents", 7),
    ("Broadcasting (Amendment) Bill 2026: to confer functions on Coimisiun na Mean", 7),
    ("Artificial Intelligence Companion Services (Protection of Children) Bill 2026: "
     "age-assurance", 7),
    # area 8
    ("An Act repealing the criminalization of blasphemy", 8),
    ("Thirty-seventh Amendment of the Constitution (Repeal of offence of publication or "
     "utterance of blasphemous matter) Bill 2018", 8),
    ("Establishment of the White House Faith Office", 8),
    # area 10
    ("Health (Assisted Human Reproduction) Bill 2023", 10),
    # area 12
    ("Ban on Sex for Rent Bill 2022", 12),
    ("Presidential Determination With Respect to the Efforts of Foreign Governments "
     "Regarding Trafficking in Persons", 12),
    # area 13
    ("Human Tissue (Authorisation) (Scotland) Bill", 13),
]

LEFT_ALONE = [
    # bare "born alive" is obstetrics, never a term
    ("Infants born alive at 24 weeks: neonatal outcomes", 1),
    # the resomation question: the bare hyphenated phrase is not a term
    ("Whether resomation can be offered as one of the end-of-life options", 2),
    # gender identity bare stays guarded (v1.19): anti-discrimination boilerplate
    ("Fair Lending for All Act: prohibits discrimination on the basis of sexual orientation "
     "or gender identity", 5),
    ("Restroom access for certain commercial motor vehicle operators", 5),
    # the guard keeps "Equality Act" to the US bill's subject
    ("Refund Equality Act", 5),
    ("Combatting Antisemitism, Hate and Extremism (Firearms and Customs Laws) Bill 2026", 7),
    ("Idaho Parental Choice Tax Credit", 6),
    ("Celebrating Reusable Nappy Week 2023: parental choice", 6),
    ("A shield law protecting journalists from disclosing confidential sources", 1),
    ("Medicare Advantage; Civil rights; Religious discrimination; Sex discrimination", 8),
    ("HIV Prevention Justice Act: transmission through human tissue", 13),
    ("Human trafficking and trafficking in persons at the border: unlawful immigration", 12),
]


class V120TermTests(unittest.TestCase):
    def test_each_measured_title_lands_in_its_area(self):
        for text, area in CAUGHT:
            self.assertIn(area, areas(text), text)

    def test_the_guards_vetoes_and_rejections_hold(self):
        for text, area in LEFT_ALONE:
            self.assertNotIn(area, areas(text), text)

    def test_the_equality_act_term_steps_aside_for_the_uk_act(self):
        res = filt.filter_item(TAX, WL, "Equality Act 2010: sexual orientation and gender identity")
        self.assertNotIn("Equality Act", res.matched_terms)

    def test_the_plural_is_tier_one(self):
        self.assertEqual(filt.filter_item(TAX, WL, "Telemedical Abortions").tier, 1)

    def test_minors_company_makes_gender_transition_tier_one(self):
        self.assertEqual(filt.filter_item(TAX, WL, "Gender transition services").tier, 2)
        self.assertEqual(filt.filter_item(
            TAX, WL, "Gender transition procedures for minors").tier, 1)


if __name__ == "__main__":
    unittest.main()
