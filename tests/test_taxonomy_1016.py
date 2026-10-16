"""Taxonomy fixes Chris approved on 16 October 2026 (measured in the masters'
Notes):

  * Croatian v0.2: udžbenic* widened to udžbeni* (the singular cases).
  * Quebec French v0.6 (and so France, Belgium, Switzerland): embryon* split
    into embryon / embryons and a guarded embryonnaire*, so the figurative
    "embryonnaire" (a tank's "programme embryonnaire", a project "au stade
    embryonnaire") is not embryology.
  * France v0.4: an amendment to the aide a mourir bill that cites the IVG
    conscience clause as its model is assisted dying (area 2), not abortion
    (area 1). The abortion words carry an assisted-dying veto for France only;
    "clause de conscience" counts for area 2 with assisted-dying company.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import filter as filt  # noqa: E402

CFG = os.path.join(ROOT, "config")
HR = filt.load_taxonomy(os.path.join(CFG, "taxonomy-hr.yaml"), country="hr")
QC = filt.load_taxonomy(os.path.join(CFG, "taxonomy-qc.yaml"))
FR = filt.load_taxonomy(os.path.join(CFG, "taxonomy-fr.yaml"), country="fr")
BE = filt.load_taxonomy(os.path.join(CFG, "taxonomy-fr.yaml"), country="be")
CH = filt.load_taxonomy(os.path.join(CFG, "taxonomy-fr.yaml"), country="ch")
WL = filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def areas(tax, text):
    return filt.filter_item(tax, WL, text, title="").issue_areas


def tier(tax, text):
    return filt.filter_item(tax, WL, text, title="").tier


class Versions(unittest.TestCase):
    def test_versions(self):
        self.assertEqual(HR.version, "0.2")
        self.assertEqual(QC.version, "0.6")
        self.assertEqual(FR.version, "0.4")


class CroatianTextbooks(unittest.TestCase):
    def test_every_case_of_udzbenik(self):
        for text in ("Nabava udžbenika za osnovne škole", "PRIJEDLOG ZAKONA O UDŽBENICIMA",
                     "besplatni udžbenik", "o udžbeniku", "udžbenikom", "udžbenički standard",
                     "udzbenika (bez dijakritika)"):
            self.assertIn(6, areas(HR, text), text)

    def test_nothing_else(self):
        self.assertEqual(areas(HR, "Zakon o državnom proračunu"), [])


class Embryology(unittest.TestCase):
    TANK = ("Constatant que les retards du programme MGCS compromettent le renouvellement des "
            "capacités de combat blindé lourd, alors que le programme reste embryonnaire, la "
            "présente actualisation met fin à la participation de la France à ce programme.")

    def test_figurative_embryonnaire_is_not_embryology(self):
        for tax in (QC, FR, BE, CH):
            for text in (self.TANK, "le projet est encore au stade embryonnaire",
                         "les idées de la Coalition sont embryonnaires"):
                self.assertNotIn(10, areas(tax, text), text)

    def test_genuine_uses_still_match(self):
        for tax in (QC, FR, BE, CH):
            for text in ("la conservation des gamètes et des embryons",
                         "recherche sur l'embryon humain",
                         "le sort des embryons surnuméraires",
                         "on n'implante qu'un seul embryon par tentative",
                         "la recherche sur les cellules souches embryonnaires",
                         "le développement embryonnaire après fécondation in vitro"):
                self.assertEqual(tier(tax, text), 1, text)
                self.assertIn(10, areas(tax, text), text)


class ConscienceClause(unittest.TestCase):
    # an-17-2065 (first reading, 23 May 2025), the expose sommaire and dispositif
    AN_2065 = ("Cet amendement introduit une clause de conscience d'établissement. Il a pour objet "
               "d'appliquer au projet de loi la clause de conscience collective prévalant pour "
               "l'IVG (article L 2212-8 CSP). Après l'alinéa 8, insérer l'alinéa suivant : « II bis. "
               "– Un établissement de santé privé peut refuser que l'aide active à mourir soit "
               "pratiquée dans ses locaux. »")
    # an-17-5678: the IVG precedent in words
    AN_5678 = ("Cet amendement introduit une clause de conscience d'établissement qui prémunit les "
               "établissements de santé privés et confessionnels de l'obligation de pratiquer une "
               "euthanasie ou un suicide assisté dans leurs locaux. Cette clause de conscience dite "
               "collective est déjà en vigueur pour les interruptions volontaires de grossesse.")
    # an-17-5663: the list of other conscience clauses
    AN_5663 = ("la clause de conscience des soignants, spécifique à l'aide à mourir, est essentielle. "
               "Les dispositions légales qui prévoient des clauses de conscience spécifiques (IVG, "
               "stérilisation à visée contraceptive, recherche sur les cellules souches "
               "embryonnaires) portent toujours clairement les actes concernés.")

    def test_assisted_dying_amendments_are_area_2_only(self):
        for text in (self.AN_2065, self.AN_5678, self.AN_5663):
            got = filt.filter_item(FR, WL, text, title="")
            self.assertEqual(got.issue_areas, [2], text[:60])
            self.assertEqual(got.tier, 1)
            self.assertIn("clause de conscience", got.matched_terms)

    def test_an_abortion_conscience_clause_stays_area_1(self):
        text = ("Supprimer la clause de conscience spécifique à l'IVG prévue à l'article L. 2212-8 "
                "du code de la santé publique.")
        self.assertEqual(areas(FR, text), [1])
        self.assertEqual(areas(FR, "L'avortement est un droit."), [1])
        self.assertEqual(areas(FR, "délit d'entrave à l'interruption volontaire de grossesse"), [1])

    def test_entrave_modelled_on_ivg_in_the_assisted_dying_bill_is_area_2(self):
        text = ("Créer un délit d'entrave à l'aide à mourir sur le modèle du délit d'entrave à "
                "l'IVG.")
        self.assertEqual(areas(FR, text), [2])

    def test_belgium_and_switzerland_keep_both_areas(self):
        text = ("proposition de loi relative à la clause de conscience en matière d'euthanasie et "
                "d'interruption volontaire de grossesse (IVG)")
        self.assertEqual(areas(BE, text), [1, 2])
        self.assertEqual(areas(CH, text), [1, 2])

    def test_a_bare_conscience_clause_is_nothing(self):
        self.assertEqual(areas(FR, "la clause de conscience des journalistes"), [])


if __name__ == "__main__":
    unittest.main()
