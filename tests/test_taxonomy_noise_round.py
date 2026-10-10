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


if __name__ == "__main__":
    unittest.main()
