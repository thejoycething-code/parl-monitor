"""The puberty blocker vote audit (13 October 2026): English v1.24, Spanish
v0.5, Quebec French v0.4 (and the French addendum built on it), Slovak v0.3.

Every caught title is a stored division or business the audit found
untagged or mis-tagged (read-only reads of the local store; the Swiss
French texts from the Federal Assembly's open OData service). The notes in
each master record the counts.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import filter as filt  # noqa: E402

WL = filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def tax(lang, country=None):
    name = "taxonomy.yaml" if lang == "en" else "taxonomy-%s.yaml" % lang
    return filt.load_taxonomy(os.path.join(ROOT, "config", name), country=country)


def hit(taxonomy, *text):
    res = filt.filter_item(taxonomy, WL, *text)
    return res.issue_areas, res.matched_terms


class Versions(unittest.TestCase):
    def test_versions(self):
        # English 1.25 since the same day (the "single sex" forms):
        # tests/test_v125_terms.py pins it.
        self.assertIn(tax("en").version, ("1.24", "1.25", "1.26"))
        self.assertEqual(tax("es").version, "0.5")
        self.assertEqual(tax("qc").version, "0.4")
        self.assertEqual(tax("sk").version, "0.3")


class English(unittest.TestCase):
    T = tax("en")

    def test_us_bill_names(self):
        # H.R. 3492 and H.R. 498: the roll calls carried area 3 by bill
        # inheritance only, with no matched term.
        areas, terms = hit(self.T, "On Passage", "Protect Children’s Innocence Act")
        self.assertIn(3, areas)
        self.assertIn("Protect Children's Innocence", terms)
        areas, terms = hit(self.T, "On Passage", "Do No Harm in Medicaid Act")
        self.assertIn(3, areas)

    def test_welsh_prescribing_regulations(self):
        title = ("Item 11. Motion to annul the National Health Service (General Medical "
                 "Services Contracts) (Prescription of Drugs Etc.) (Wales) (Amendment) "
                 "(No. 2) Regulations 2024")
        self.assertIn(3, hit(self.T, title)[0])

    def test_other_prescription_regulations_stay_out(self):
        title = ("The National Health Service (General Medical Services Contracts) "
                 "(Prescription of Drugs Etc.) (Wales) (Amendment) Regulations 2023")
        self.assertNotIn(3, hit(self.T, title)[0])

    def test_gnrh_order(self):
        title = ("The Medicines (Gonadotrophin-Releasing Hormone Analogues) "
                 "(Restrictions on Private Sales and Supplies) Order 2024")
        self.assertIn(3, hit(self.T, title)[0])
        # The drug class alone is prostate-cancer and IVF vocabulary.
        self.assertNotIn(3, hit(self.T, "Gonadotrophin-releasing hormone analogues for prostate cancer")[0])


class Spanish(unittest.TestCase):
    def test_chile_budget_glosa(self):
        t = tax("es", "cl")
        text = ("El Ministerio de Salud no podra financiar gastos relacionados con la "
                "administracion de medicamentos con fines de uso de terapia hormonal, sea "
                "bloqueo de pubertad u hormonacion cruzada")
        areas, terms = hit(t, text)
        self.assertIn(3, areas)
        self.assertIn("bloqueo de pubertad", terms)


class QuebecFrench(unittest.TestCase):
    def test_charter_ground_alone_is_not_area_3(self):
        for lang in ("qc", "fr"):
            t = tax(lang, "ch" if lang == "fr" else None)
            self.assertNotIn(3, hit(t, "Approfondir les connaissances sur les discriminations "
                                       "multiples", "orientation sexuelle, identité de genre")[0])
            self.assertNotIn(3, hit(t, "Pour une politique fédérale cohérente en matière de santé "
                                       "sexuelle", "personnes transgenres")[0])

    def test_with_minors_it_still_is(self):
        t = tax("qc")
        self.assertIn(3, hit(t, "Les élèves et l'identité de genre à l'école")[0])
        self.assertIn(3, hit(t, "Loi visant à améliorer la situation des mineurs transgenres")[0])


class Slovak(unittest.TestCase):
    T = tax("sk", "sk")

    def test_sex_change_alone_is_not_area_3(self):
        self.assertNotIn(3, hit(self.T, "rozsudky týkajúce sa otázky zmenu pohlavia")[0])

    def test_sex_change_of_minors_is(self):
        self.assertIn(3, hit(self.T, "zákaz zmeny pohlavia u maloletých")[0])


if __name__ == "__main__":
    unittest.main()
