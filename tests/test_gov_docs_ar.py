"""Argentina gov_docs reader (src/gov_doc_sources/ar.py): the Boletín
Oficial's first section and the consultapublica mirror. Fixtures captured
live on 16 October 2026 and trimmed (tests/fixtures/gov_docs/ar/): the
listing block of the 13 October edition, the aviso block of two avisos (Ley
27828 and ANSES Resolución 297/2026), and the two consultapublica rows the
petitions step stored."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from src import db, gov_docs as G  # noqa: E402
from src.gov_doc_sources import ar  # noqa: E402
from gov_docs_latam_helpers import fixture, load_petitions  # noqa: E402

TODAY = "2026-10-16"


class FakeClient:
    def __init__(self, listing=None):
        self.urls = []
        self.listing = listing or fixture("ar", "primera-20261013.html")

    def get_text(self, url, feed, slug, **kw):
        self.urls.append(url)
        if url == ar.DAY.format("20261013"):
            return self.listing
        if url == ar.AVISO.format("348838", "20261013"):
            return fixture("ar", "aviso-348838.html")
        if "/detalleAviso/" in url:
            raise RuntimeError("HTTP Error 404: Not Found")
        return "<html></html>"                     # another day: nothing listed


class ParseTests(unittest.TestCase):
    def test_listing(self):
        got = ar.parse_day(fixture("ar", "primera-20261013.html"), None)
        by = {e["doc_id"]: (r, e) for r, e in got}
        rubro, law = by["bo:348838"]
        self.assertEqual(rubro, "LEYES")
        self.assertEqual(law["doc_type"], "law")
        self.assertEqual(law["title"], "Ley 27828: Régimen de Zona Fría")
        self.assertEqual(law["body"], "Congreso de la Nación")
        self.assertEqual(law["published"], "2026-10-13")
        self.assertEqual(by["bo:348839"][1]["doc_type"], "regulation")      # promulgating decree
        self.assertEqual(by["bo:348841"][1]["body"], "Ministerio de Salud")
        self.assertEqual(ar._wanted(*by["bo:348841"]), 1)
        self.assertIsNone(ar._wanted(*by["bo:348842"]))                       # Seguridad: not read
        self.assertFalse([e for r, e in got if "AVISOS" in r])

    def test_aviso(self):
        got = ar.parse_aviso(fixture("ar", "aviso-348838.html"))
        self.assertTrue(got["operative"].startswith("Capítulo I Modificaciones al Régimen de Zona Fría"))
        res = ar.parse_aviso(fixture("ar", "aviso-348972.html"))
        self.assertTrue(res["operative"].startswith("ARTÍCULO 1°.- Apruébanse los procedimientos"))
        self.assertNotIn("e. 15/10/2026", res["operative"])
        self.assertLessEqual(len(res["operative"]), G.SUMMARY_CAP)

    def test_nice(self):
        self.assertEqual(ar.nice("MINISTERIO DE JUSTICIA Y DERECHOS HUMANOS"),
                         "Ministerio de Justicia y Derechos Humanos")


class CollectTests(unittest.TestCase):
    def test_collect(self):
        conn = db.init_db(db.connect(":memory:"))
        load_petitions(conn, "ar", "country_petitions-cp.json")
        client = FakeClient()
        listed, kept, gaps = G.collect(conn, "ar", client, TODAY, log=lambda *a: None)
        self.assertEqual(gaps, 0)
        # five weekday listings (12 to 16 October); then the wanted avisos of the 13th, laws
        # and decrees first: the law, its decree, the health ministry's resolution, ANMAT's
        # disposition
        avisos = [u for u in client.urls if "/detalleAviso/" in u]
        self.assertEqual(avisos[:2], [ar.AVISO.format("348838", "20261013"),
                                      ar.AVISO.format("348839", "20261013")])
        self.assertEqual(len(avisos), 4)
        self.assertIn(ar.AVISO.format("348852", "20261013"), avisos)
        # 20 first-section avisos listed, and the two consultations (closed in September
        # and early October, inside the 92-day window)
        self.assertEqual(listed, 22)
        self.assertEqual(kept, 0)          # nothing on our ground in this edition
        runs = dict(conn.execute("SELECT source, ok FROM gov_doc_runs WHERE cc='ar'").fetchall())
        self.assertEqual(runs, {"bo": 1, "cp": 1})

    def test_a_law_on_our_ground(self):
        """Synthetic: the captured law's subject heading replaced with words our
        taxonomy knows, to show the path end to end (nothing live was on our ground)."""
        listing = fixture("ar", "primera-20261013.html").replace("RÉGIMEN DE ZONA FRÍA",
                                                                  "INTERRUPCIÓN VOLUNTARIA DEL EMBARAZO")
        conn = db.init_db(db.connect(":memory:"))
        load_petitions(conn, "ar", "country_petitions-cp.json")
        G.collect(conn, "ar", FakeClient(listing), TODAY, log=lambda *a: None)
        rows = [dict(r) for r in conn.execute("SELECT doc_id, doc_type, tier, areas, summary FROM gov_docs")]
        self.assertEqual([(r["doc_id"], r["doc_type"], r["tier"]) for r in rows], [("bo:348838", "law", 1)])
        self.assertEqual(json.loads(rows[0]["areas"]), [1])
        self.assertTrue(rows[0]["summary"].startswith("Capítulo I"))


if __name__ == "__main__":
    unittest.main()
