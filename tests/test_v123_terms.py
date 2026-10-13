"""The regional terms round (Chris, 13 October 2026: "Accept the watchlists,
apply the terms after measuring"): English v1.23, Dutch v0.3, French v0.3,
German additions v0.3, Spanish v0.4.

Every caught title is a stored title the measurement found (scratch reads of
the regional layers and the local store, read-only); every left-out title is
the measured reason for a guard. The notes in each master record the counts.
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


def hit(taxonomy, text):
    res = filt.filter_item(taxonomy, WL, text)
    return res.issue_areas, res.matched_terms


class English(unittest.TestCase):
    T = tax("en")

    def test_versions(self):
        # English 1.24 and Spanish 0.5 since 13 October 2026 (the puberty
        # blocker vote audit): tests/test_v124_terms.py pins them.
        self.assertEqual(tax("nl").version, "0.3")
        self.assertEqual(tax("fr").version, "0.3")
        self.assertEqual(tax("atch").version, "0.3")
        self.assertIn(tax("es").version, ("0.4", "0.5"))

    def test_territory_terminally_ill_bill(self):
        areas, terms = hit(self.T, "Rights of the Terminally Ill Bill 2026")
        self.assertEqual(areas, [2])
        self.assertIn("terminally ill", terms)

    def test_terminally_ill_needs_its_guard(self):
        for title in ("Department for Work and Pensions Handling of Terminally Ill Benefits Claims",
                      "Immediate Access for the Terminally Ill Act",
                      "To ask the Scottish Executive how it ensures continuous improvements in the "
                      "level of support for terminally ill patients."):
            self.assertNotIn("terminally ill", hit(self.T, title)[1], title)

    def test_end_of_life_choices(self):
        self.assertEqual(hit(self.T, "End-of-Life Choices (Voluntary Assisted Dying) Bill 2020")[0], [2])
        self.assertEqual(hit(self.T, "End of Life Choices Bill")[0], [2])

    def test_births_deaths_marriages_guarded_by_sex_or_gender(self):
        areas, _ = hit(self.T, "Births, Deaths and Marriages Registration Amendment (Sex or Gender "
                               "Changes) Act 2024")
        self.assertEqual(areas, [5])
        self.assertEqual(hit(self.T, "Births, Deaths and Marriages Registration (Birth Certificates) "
                                     "Amendment")[0], [])

    def test_religious_exceptions(self):
        self.assertIn(8, hit(self.T, "Equal Opportunity (Religious Exceptions) Amendment Bill 2021")[0])
        self.assertIn(8, hit(self.T, "Sex Discrimination Amendment (Religious Educational "
                                     "Institutions) Bill")[0])
        # the bare statute name is someone else's subject
        self.assertEqual(hit(self.T, "Equal Opportunity Amendment (Work from Home) Bill 2026")[0], [])
        self.assertEqual(hit(self.T, "Equal Opportunity Amendment (Religious Freedom) Bill")[0], [8])

    def test_pornographic_is_matched(self):
        areas, terms = hit(self.T, "An Act to amend the Criminal Code (pornographic material)")
        self.assertEqual(areas, [7])
        self.assertIn("pornograph*", terms)
        self.assertEqual(hit(self.T, "Revenge Pornography")[0], [7])


class Dutch(unittest.TestCase):
    def test_flemish_family_allowance(self):
        be = tax("nl", "be")
        self.assertEqual(hit(be, "Verzoekschrift over de maatregelen in het groeipakket")[0], [9])
        self.assertEqual(hit(be, "Voorstel van ordonnantie tot wijziging van de ordonnantie van 25 april "
                                 "2019 tot regeling van de toekenning van gezinsbijslag")[0], [9])

    def test_tagged_belgium_only(self):
        self.assertEqual(hit(tax("nl", "nl"), "het Vlaamse groeipakket")[0], [])


class French(unittest.TestCase):
    def test_family_allowances_shared(self):
        for cc, title in (("be", "Proposition de résolution relative à l'affirmation qu'un enfant est un "
                                 "enfant, sans discrimination, dans les allocations familiales bruxelloises"),
                          ("fr", "Accorder le versement des allocations familiales dès le premier enfant"),
                          ("ch", "Loi sur les allocations familiales. Modification")):
            self.assertEqual(hit(tax("fr", cc), title)[0], [9], cc)

    def test_geneva_gender_medicine(self):
        ch = tax("fr", "ch")
        self.assertEqual(hit(ch, "demandant un moratoire sur les interventions de réassignation/conversion "
                                 "sexuelle destinées à des mineurs")[0], [3])
        self.assertEqual(hit(ch, "pour intégrer les soins de transition de genre dans le cadre de la "
                                 "médecine hautement spécialisée (MHS)")[0], [3])

    def test_quebec_untouched(self):
        self.assertEqual(hit(tax("qc"), "Loi sur les allocations familiales")[0], [])


class GermanAdditions(unittest.TestCase):
    def test_bern_titles(self):
        ch = tax("atch", "ch")
        self.assertEqual(hit(ch, "Geschlechtsänderungen: Wie bekämpft der Regierungsrat das "
                                 "Missbrauchspotenzial?")[0], [3])
        self.assertEqual(hit(ch, "Wie geht der Kanton Bern mit Sonderzeichen («Genderstern/Doppelpunkt») "
                                 "in offiziellen Dokumenten um?")[0], [5])

    def test_bundestag_untouched(self):
        self.assertEqual(hit(tax("de"), "Genderstern in Behördenschreiben")[0], [])


class Spanish(unittest.TestCase):
    def test_salud_sexual_for_argentina_only(self):
        title = "DE ADHESIÓN AL DÍA MUNDIAL DE LA SALUD SEXUAL."
        self.assertEqual(hit(tax("es", "ar"), title)[0], [1])
        self.assertEqual(hit(tax("es", "mx"), title)[0], [])

    def test_peru_child_marriage(self):
        pe = tax("es", "pe")
        self.assertIn("uniones infantiles tempranas forzadas", hit(
            pe, "Créase la Mesa Regional para la Prevención y Atención de los matrimonios y las uniones "
                "infantiles tempranas forzadas (MUITF)")[1])
        areas, terms = hit(pe, 'DECLARAR de Interés Regional la Implementación de la Ley N"31945')
        self.assertEqual(areas, [9])
        self.assertIn("31945", terms)
        # the number alone, with no law or marriage company, is not ours
        self.assertEqual(hit(pe, "Expediente 31945 de la Gerencia de Infraestructura")[0], [])
        self.assertEqual(hit(tax("es", "ar"), 'Ley N"31945')[0], [])


if __name__ == "__main__":
    unittest.main()
