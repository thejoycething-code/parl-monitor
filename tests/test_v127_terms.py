"""English taxonomy v1.27 and Quebec French v0.5 (16 October 2026): Canada's
"2SLGBTQI+" family.

Chris asked for 2SLGBTQI+ and its variants (2SLGBTQ+, 2SLGBTQIA+, 2SLGBT,
LGBTQ2S+, LGBTQ2+, the French 2ELGBTQI+) so items like the Senate committee
study on 2SLGBTQI+ youth are tagged and scored. Modelled on v1.26's guarded
"gender identity": tier 2, area 3 with children/school company, area 5 with
single-sex company, boilerplate vetoed. Measured in docs/keyword-taxonomy.md
(area 3 notes).

The tokenizer point: "+" is not a word character and digits are, so the
terms are ALL-CAPS stems (2SLGB*, LGBTQ2*, ...). A term written "2SLGBTQI+"
would match that one spelling only.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import filter as filt  # noqa: E402

EN = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
QC = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy-qc.yaml"))
FR = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy-fr.yaml"), country="fr")
WL = filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])
STEMS = {"2SLGB*", "2ELGB*", "LGBTQ2*", "LGBTQI2*", "LGBT2*"}


def hit(text, tax=EN):
    res = filt.filter_item(tax, WL, text, title="")
    return res.tier, res.issue_areas, set(res.matched_terms) & STEMS


class Versions(unittest.TestCase):
    def test_versions(self):
        self.assertEqual(EN.version, "1.27")
        self.assertEqual(QC.version, "0.6")   # v0.6: tests/test_taxonomy_1016.py


class Tokenizer(unittest.TestCase):
    """Every spelling the store holds reaches a stem."""

    def test_every_variant_matches_with_company(self):
        for form in ("2SLGBTQI+", "2SLGBTQ+", "2SLGBTQIA+", "2SLGBTQQIA+", "2SLGBT", "2SLGBTQi+",
                     "2SLGBTQ2IA+", "2ELGBTQI+", "LGBTQ2", "LGBTQ2+", "LGBTQ2S+", "LGBTQ2IA+",
                     "LGBTQI2S+", "LGBT2SQ", "LGBTQ2S-plus"):
            tier, areas, terms = hit("supports for {0} youth in schools".format(form))
            self.assertEqual((tier, areas), (2, [3]), form)
            self.assertTrue(terms, form)

    def test_plus_at_end_of_sentence_and_before_punctuation(self):
        for text in ("Senate study on the youth of the 2SLGBTQI+.",
                     "students (2SLGBTQIA+), in our schools",
                     "2SLGBTQI+\nyouth"):
            self.assertEqual(hit(text)[:2], (2, [3]), text)

    def test_not_inside_a_longer_token(self):
        self.assertEqual(hit("x2SLGBTQI+ youth")[:2], (None, []))
        self.assertEqual(hit("A2ELGBTQ youth")[:2], (None, []))

    def test_case_sensitive(self):
        # ALL-CAPS terms match case-sensitively (the matcher's acronym rule).
        self.assertEqual(hit("2slgbtqi+ youth")[:2], (None, []))

    def test_plain_lgbtq_is_not_a_new_term(self):
        self.assertEqual(hit("LGBTQ+ youth in schools")[2], set())


class Guards(unittest.TestCase):
    def test_on_our_ground_gains_area_3(self):
        for text in ("Senate committee study on 2SLGBTQI+ youth",
                     "students' pronoun choices and 2SLGBTQI+ policies in schools",
                     "the parental rights movement, which aims to deny 2SLGBTQI+ youth their rights",
                     "GSAs should be granted immediately; LGBTQ2S students in private schools",
                     "drag queens reading stories to children; the 2SLGBTQIA+ community",
                     "2SLGBTQIA+ minors and puberty blockers"):
            # Some of these carry other terms too ("parental rights" is area 6,
            # tier 1); the stem's own contribution is area 3.
            tier, areas, terms = hit(text)
            self.assertIn(3, areas, text)
            self.assertTrue(terms, text)

    def test_single_sex_company_gains_area_5(self):
        tier, areas, _ = hit("2SLGBTQI+ inmates placed in federal prisons for women")
        self.assertEqual(tier, 2)
        self.assertIn(5, areas)
        self.assertIn(5, hit("2SLGBTQIA+ athletes and the female sport category")[1])

    def test_bare_form_matches_nothing(self):
        for text in ("the 2SLGBTQI+ community", "members of the LGBTQ2+ community",
                     "an abortion clinic serving LGBTQ2SI+ patients"):
            # (the clinic sentence is area 1 on "abortion"; the stem adds nothing)
            self.assertEqual(hit(text)[2], set(), text)

    def test_womens_shelter_is_not_area_5_company(self):
        self.assertEqual(hit("2SLGBTQIA+ communities and women's shelters")[:2], (None, []))


class Vetoes(unittest.TestCase):
    def test_boilerplate_is_vetoed(self):
        for text in (
                # equity lists
                "women, Indigenous peoples, racialized Canadians and 2SLGBTQI+ youth",
                "violence against Indigenous women, girls and 2SLGBTQQIA people; residential schools",
                "equity-deserving groups, including 2SLGBTQI+ students",
                "GBA Plus found 2SLGBTQI+ youth are affected",
                # funding programmes
                "the Federal 2SLGBTQI+ Action Plan funds youth organisations",
                "the 2SLGBTQI+ Community Capacity Fund supports youth groups",
                # pride and awareness days
                "Pride Month: we celebrate 2SLGBTQI+ youth",
                "International Day Against Homophobia, Transphobia and Biphobia: 2SLGBTQIA+ youth",
                # health equity
                "health equity for 2SLGBTQI+ youth and the social determinants of health",
                # carried elsewhere
                "a hate crime against 2SLGBTQI+ youth",
                "Bill C-6 bans conversion therapy for LGBTQ2 children",
                "surrogacy and children of LGBTQ2+ parents",
                # SOGI lists and codes
                "discrimination on grounds of sexual orientation, gender identity: 2SLGBTQI+ students",
                "the Human Rights Code protects 2SLGBTQI+ youth"):
            areas = hit(text)[1]
            self.assertNotIn(3, areas, text)
            self.assertNotIn(5, areas, text)


class QuebecFrench(unittest.TestCase):
    def test_french_forms_with_company(self):
        for text in ("les jeunes 2ELGBTQI+ à l'école",
                     "la communauté LGBTQ2+ et les élèves",
                     "la lecture de contes pour enfants par des drag-queens; la communauté LGBTQI2S+",
                     "les mineurs 2SLGBTQIA+ et la puberté"):
            tier, areas, terms = hit(text, QC)
            self.assertEqual((tier, areas), (2, [3]), text)
            self.assertTrue(terms, text)

    def test_french_area_5(self):
        self.assertIn(5, hit("les athlètes 2ELGBTQI+ et le sport féminin", QC)[1])

    def test_french_bare_and_boilerplate(self):
        for text in ("la communauté 2ELGBTQI+",
                     "le Mois de la fierté : les jeunes 2ELGBTQI+",
                     "le Plan d'action 2ELGBTQI+ fédéral pour les jeunes",
                     "les crimes haineux contre les jeunes 2ELGBTQI+",
                     "la filiation des enfants de parents LGBTQ2+"):
            # (crimes haineux and filiation are terms of areas 7 and 9 themselves)
            self.assertEqual(hit(text, QC)[2], set(), text)

    def test_french_addendum_inherits(self):
        # taxonomy-fr extends taxonomy-qc: France, Belgium, Switzerland get the stems.
        self.assertEqual(hit("les jeunes 2ELGBTQI+ à l'école", FR)[:2], (2, [3]))


if __name__ == "__main__":
    unittest.main()
