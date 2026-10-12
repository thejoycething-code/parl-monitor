"""The term-list noise round of 10 October 2026 (taxonomy-sk, -it, -fr, -pt,
-nl and -es v0.2): each guard drops the false hit it was written for and
keeps the true ones. The texts are the ones measured (see each list's "How
it was made"), shortened.
"""

from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import courts, filter as filt  # noqa: E402

WL = filt.Watchlist([], [], [])


def tax(lang, country):
    return filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy-%s.yaml" % lang), country)


def areas(t, *fields):
    return filt.filter_item(t, WL, *fields).issue_areas or []


def passage_areas(t, text):
    """What the Slovak document reader (tier-1 passages only) files a text under."""
    return filt.aggregate_passages(filt.match_passages(t, WL, text))[0] or []


class SlovakTests(unittest.TestCase):
    def setUp(self):
        self.tax = tax("sk", "sk")

    def test_animal_euthanasia_is_not_ours(self):
        vet = ("klinické zručnosti požadované na prevenciu, diagnostiku a liečenie ochorení "
               "zvierat, posúdenie a zvládanie bolesti, sedácie, anestézie a eutanázie")
        self.assertNotIn(2, areas(self.tax, vet))
        self.assertNotIn(2, areas(self.tax, "Eutanázia psov vo veterinárnej praxi"))
        self.assertIn(2, areas(self.tax, "Návrh zákona o eutanázii a asistovanej samovražde"))

    def test_a_crime_catalogue_lends_no_areas(self):
        # Print 1445 (Police Act, passenger records): offence lists.
        for text in ("„j) sexuálne zneužívanie, sexuálne vykorisťovanie detí a detská pornografia,“.",
                     "stíhanie terorizmu a závažnej trestnej činnosti (ako je napríklad nelegálna "
                     "migrácia, obchodovanie s ľuďmi alebo výroba detskej pornografie)",
                     "Smernica 2011/93/EÚ o boji proti sexuálnemu zneužívaniu a sexuálnemu "
                     "vykorisťovaniu detí a proti detskej pornografii"):
            got = passage_areas(self.tax, text)
            for area in (6, 7, 12):
                self.assertNotIn(area, got, text)
        # The migration passage still files area 11: that is what it is about.
        self.assertIn(11, passage_areas(self.tax, "boja proti nelegálnej migrácii"))
        # Pornography named as a form of sexual exploitation is area 12's, not 7's.
        self.assertNotIn(7, passage_areas(
            self.tax, "a) prostitúcie alebo inej formy sexuálneho vykorisťovania vrátane pornografie,"))

    def test_a_trafficking_bill_keeps_area_12(self):
        # Print 1439's own passages (the anti-trafficking directive 2024/1712).
        text = ("Cieľom legislatívnej úpravy je zabezpečiť takú právnu úpravu trestného činu "
                "kupliarstva, aby jeho aplikácia bola vylúčená v prípadoch, ak je obeťou dieťa. "
                "Navrhovaná úprava má za cieľ zvýšiť úroveň ochrany detí pred sexuálnym "
                "vykorisťovaním.")
        self.assertIn(12, passage_areas(self.tax, text))
        self.assertIn(12, areas(self.tax, "Zákon o boji proti sexuálnemu vykorisťovaniu žien"))
        self.assertIn(7, areas(self.tax, "Návrh zákona o overovaní veku pri prístupe k pornografii"))

    def test_same_sex_officer_is_not_same_sex_marriage(self):
        self.assertNotIn(9, areas(self.tax, "Prehliadku osoby vykonáva osoba rovnakého pohlavia."))
        self.assertIn(9, areas(self.tax, "manželstvo pre osoby rovnakého pohlavia"))
        self.assertIn(9, areas(self.tax, "rodičovstvo osôb rovnakého pohlavia"))
        self.assertIn(9, areas(self.tax, "páry rovnakého pohlavia"))


class ItalianTests(unittest.TestCase):
    def setUp(self):
        self.it = tax("it", "it")
        self.ch = tax("it", "ch")

    def test_vita_umana_needs_life_issue_company(self):
        for text in ("Crisi della biodiversità e salute: conseguenze gravi per la vita umana",
                     "investimenti che mettono a rischio la salute o la vita umana"):
            self.assertNotIn(1, areas(self.ch, text), text)
        self.assertIn(1, areas(self.it, "Tutela della vita umana fin dal concepimento"))
        self.assertIn(1, areas(self.ch, "la vita umana dell'embrione"))
        self.assertIn(1, areas(self.it, "dignità della vita umana nel fine vita"))


class FrenchTests(unittest.TestCase):
    def setUp(self):
        self.fr = tax("fr", "fr")

    def test_separatisme_needs_religious_company(self):
        self.assertNotIn(8, areas(self.fr, "Abrogation des zones à faibles émissions",
                                  "une ségrégation et un séparatisme territorial et social"))
        self.assertNotIn(8, areas(self.fr, "Lutter contre le séparatisme social dans nos territoires"))
        self.assertIn(8, areas(self.fr, "Projet de loi confortant le respect des principes de la "
                                        "République et de lutte contre le séparatisme"))
        self.assertIn(8, areas(self.fr, "le séparatisme islamiste"))

    def test_france_only_still(self):
        self.assertNotIn(8, areas(tax("fr", "be"), "le séparatisme islamiste"))


class SwissIvgTests(unittest.TestCase):
    """'IVG' is abortion in French and Italian and, in a Swiss text, mostly
    the Invalidity Insurance Act (11 October 2026). The texts are the store's:
    the AHV survivors' pensions bill 24.078 (24 September 2025), the autism
    early-intervention bill 24.066 and the Fristenregelung postulate 23.3762."""

    AHV = ("Art. 35 (gilt auch für Ziff. II 1. IVG Art. 37 Abs. 1bis und "
           "Übergangsbestimmung, Ziff. III Abs. 5)")
    AUTISM = ("Bundesgesetz über die Invalidenversicherung IVG (Intensive Frühintervention "
              "bei Autismus-Spektrum-Störungen, IFI). Änderung")

    def test_the_invalidity_insurance_act_is_not_abortion_for_ch(self):
        for lang in ("fr", "it"):
            for text in (self.AHV, self.AUTISM, "Modification de la LAI et de l'IVG"):
                self.assertNotIn(1, areas(tax(lang, "ch"), text), (lang, text))

    def test_ivg_with_abortion_company_still_counts_for_ch(self):
        for lang in ("fr", "it"):
            self.assertIn(1, areas(tax(lang, "ch"), "Evaluation der Fristenregelung (IVG), "
                                                    "Schwangerschaft"))
        self.assertIn(1, areas(tax("fr", "ch"), "Accès à l'IVG: la grossesse non désirée"))
        self.assertIn(1, areas(tax("it", "ch"), "IVG e aborto farmacologico"))

    def test_france_belgium_and_italy_keep_bare_ivg(self):
        for lang, cc in (("fr", "fr"), ("fr", "be"), ("it", "it")):
            self.assertIn(1, areas(tax(lang, cc), "Allonger le délai d'accès à l'IVG"), cc)
            hits = filt.filter_item(tax(lang, cc), WL, "Proposition de loi IVG").matched_terms
            self.assertIn("IVG", hits, cc)


class PortugueseTests(unittest.TestCase):
    def setUp(self):
        self.pt = tax("pt", "pt")

    def test_end_of_life_vehicles_are_not_ours(self):
        self.assertNotIn(2, areas(self.pt, "Sistema Integrado de Gestão de Veículos em Fim de Vida"))
        self.assertNotIn(2, areas(self.pt, "gestão de resíduos de pneus em fim de vida"))
        self.assertIn(2, areas(self.pt, "cuidados de saúde em fim de vida"))


class DutchTests(unittest.TestCase):
    def setUp(self):
        self.nl = tax("nl", "nl")

    def test_transitie_needs_gender_company(self):
        school = ("Je moet niet beginnen met een transitie naar een nieuw systeem waarin "
                  "zo veel mogelijk kinderen naar regulier onderwijs gaan")
        self.assertNotIn(3, areas(self.nl, school))
        self.assertIn(3, areas(self.nl, "de medische transitie van jongeren met genderdysforie"))
        self.assertIn(3, areas(self.nl, "transitie met hormonen in de puberteit"))
        self.assertIn(3, areas(tax("nl", "be"), "een transitie naar het andere geslacht"))


class SpanishTests(unittest.TestCase):
    def test_causales_needs_abortion_company(self):
        for cc in ("cl", "co", "mx", "bo", "hn"):
            es = tax("es", cc)
            for text in ("Establece causales de inhabilidades y recusación respecto de jueces",
                         "causales de nulidad de votación recibida en casilla",
                         "Bajo qué causales se dispuso la destitución del director",
                         "las causales por las que una aeronave aborte su despegue"):
                self.assertNotIn(1, areas(es, text), (cc, text))
            self.assertIn(1, areas(es, "las causales de aborto no punible"), cc)
            self.assertIn(1, areas(es, "interrupción del embarazo en tres causales"), cc)
        # "Tres causales" is not company: Ecuador's Constitution has its own
        # three grounds. Chile's and the Dominican Republic's own term stays.
        art146 = "las tres causales previstas en el artículo 146 de la Constitución"
        self.assertNotIn(1, areas(tax("es", "ec"), art146))
        self.assertIn(1, areas(tax("es", "cl"), "el aborto en tres causales"))

    def test_tres_causales_needs_abortion_company(self):
        # Chile's euthanasia bill 17732-11 regulates "la eutanasia en tres
        # causales": assisted dying, not abortion.
        for cc in ("cl", "do"):
            es = tax("es", cc)
            for text in ("Regula la eutanasia en tres causales",
                         "Modifica diversos cuerpos legales para regular la eutanasia en tres causales"):
                got = areas(es, text)
                self.assertNotIn(1, got, (cc, text))
                self.assertIn(2, got, (cc, text))
            for text in ("Regula la despenalización de la interrupción voluntaria del embarazo en tres causales",
                         "el aborto en tres causales",
                         "tres causales: riesgo de vida de la mujer embarazada"):
                self.assertIn(1, areas(es, text), (cc, text))

    def test_the_court_side_mask_is_gone(self):
        # The guard now lives in taxonomy-es; src/courts.py no longer masks.
        self.assertFalse(hasattr(courts, "COURT_GUARDS"))
        t = courts.load_taxonomy("ec")
        _a, terms, _t = courts.classify(
            t, "Nulidad de laudo arbitral",
            "verificar si se han configurado las causales taxativas del art. 31 de la Ley de Arbitraje")
        self.assertNotIn("causales", terms)
        got, terms, _t = courts.classify(t, "Sentencia", "las causales de aborto no punible")
        self.assertIn(1, got)
        self.assertIn("causales", terms)


class SpainAndMexicoTermsTests(unittest.TestCase):
    """Taxonomy-es v0.3 (12 October 2026, Chris: "Add the Spain keyword
    terms", "Add the Mexico and Italy keyword terms too"). The titles are the
    measured ones (docs/keyword-taxonomy-es.md, "How it was made")."""

    MADRID = ("Ley 5/2026, de 7 de julio, de reconocimiento del concebido en la aplicación "
              "de las medidas de apoyo a la familia en la Comunidad de Madrid.")

    def test_madrid_conceived_child_law(self):
        got = areas(tax("es", "es"), self.MADRID)
        self.assertIn(1, got)
        self.assertIn(9, got)

    def test_designed_is_not_conceived(self):
        for country in ("es", "mx", "ar"):
            self.assertNotIn(1, areas(tax("es", country),
                                      "Programa concebido para el apoyo a la pequeña empresa"))

    def test_teachers_authority_is_not_added(self):
        res = filt.filter_item(tax("es", "es"), WL, "Proyecto de Ley de autoridad del profesorado")
        self.assertEqual(res.issue_areas or [], [])

    def test_hate_crimes_reach_free_speech(self):
        t = tax("es", "mx")
        self.assertIn(7, areas(t, "Iniciativa para tipificar como delito el crimen de odio, motivado "
                                  "por orientación sexual o identidad de género"))
        self.assertIn(7, areas(t, "Capítulo denominado CRÍMENES DE ODIO MOTIVADO POR ORIENTACIÓN SEXUAL"))

    def test_vicarious_violence_is_family_everywhere(self):
        for country, title in (("es", "Proyecto de Ley Orgánica de medidas en materia de violencia vicaria."),
                               ("mx", "Iniciativa que adiciona diversas disposiciones del Código Penal, "
                                      "en materia del delito de violencia vicaria"),
                               ("pa", "QUE ESTABLECE MEDIDAS PARA PREVENIR, ATENDER Y ERRADICAR LA VIOLENCIA "
                                      "VICARIA EN LA REPUBLICA DE PANAMA")):
            self.assertIn(9, areas(tax("es", country), title), country)


if __name__ == "__main__":
    unittest.main()
