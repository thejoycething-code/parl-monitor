"""Chile gov_docs reader (src/gov_doc_sources/cl.py): the Diario Oficial's
Normas Generales summary page. Fixtures captured live on 16 October 2026
(tests/fixtures/gov_docs/cl/, untrimmed: about 30 KB each): today's edition
(44575), the previous one (44574, 15 October) and the empty page answered for
an edition number asked with the wrong date."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs as G  # noqa: E402
from src.gov_doc_sources import cl  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs", "cl")
TODAY = "2026-10-16"


def text(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


class FakeClient:
    def __init__(self, today_page=None):
        self.urls = []
        self.today_page = today_page

    def get_text(self, url, feed, slug, **kw):
        self.urls.append(url)
        if url == cl.TODAY_URL:
            return self.today_page or text("index-today.html")
        if url == cl.EDITION.format("15-10-2026", 44574):
            return text("index-15-10-2026-44574.html")
        return text("index-empty.html")


class ParseTests(unittest.TestCase):
    def test_current_edition(self):
        self.assertEqual(cl.current_edition(text("index-today.html")), ("2026-10-16", 44575))
        self.assertTrue(cl.has_edition(text("index-today.html")))
        self.assertFalse(cl.has_edition(text("index-empty.html")))

    def test_rows(self):
        got = cl.parse_edition(text("index-today.html"), "2026-10-16")
        self.assertTrue(len(got) >= 10)
        e = [x for x in got if x["doc_id"] == "do:2886884"][0]
        self.assertEqual(e["body"], "Ministerio de Hacienda")
        self.assertTrue(e["title"].startswith("Resolución exenta número 668, de 2026.- Determina"))
        self.assertEqual(e["url"], "https://www.diariooficial.interior.gob.cl/publicaciones/2026/10/16/"
                                   "44575/01/2886884.pdf")
        self.assertEqual(e["doc_type"], "regulation")
        self.assertTrue(all("/01/" in x["url"] for x in got))      # Normas Generales only

    def test_doc_types(self):
        self.assertEqual(cl.doc_type("Ley núm. 21.800.- Modifica el Código Civil"), "law")
        self.assertEqual(cl.doc_type("Resolución exenta número 545, de 2026.- Dispone efectuar "
                                     "consulta ciudadana en el marco de ..."), "regulation_draft")
        got = cl.parse_edition(text("index-15-10-2026-44574.html"), "2026-10-15")
        self.assertTrue([x for x in got if x["doc_type"] == "regulation_draft"])


class CollectTests(unittest.TestCase):
    def test_walks_back_and_stores_nothing_off_our_ground(self):
        conn = db.init_db(db.connect(":memory:"))
        client = FakeClient()
        listed, kept, gaps = G.collect(conn, "cl", client, TODAY, log=lambda *a: None)
        self.assertEqual(gaps, 0)
        self.assertIn(cl.EDITION.format("15-10-2026", 44574), client.urls)
        # after 44574 the fake answers empty pages: four earlier dates and the same date, then stop
        self.assertEqual(len(client.urls), 1 + 1 + 5)
        self.assertGreater(listed, 20)
        self.assertEqual(kept, 0)        # the live fortnight had nothing on our ground
        run = conn.execute("SELECT ok, listed, kept FROM gov_doc_runs WHERE cc='cl'").fetchone()
        self.assertEqual(tuple(run), (1, listed, 0))

    def test_a_law_on_our_ground_is_kept(self):
        """Synthetic: one captured row's words replaced with a law our taxonomy knows,
        to show the path end to end (the live fortnight had nothing on our ground)."""
        page = text("index-today.html").replace(
            "Resolución exenta número 668, de 2026.- Determina tasas de interés de referencia",
            "Ley núm. 21.900.- Regula la eutanasia y el suicidio asistido")
        conn = db.init_db(db.connect(":memory:"))
        G.collect(conn, "cl", FakeClient(today_page=page), TODAY, log=lambda *a: None)
        rows = [dict(r) for r in conn.execute("SELECT doc_id, doc_type, tier FROM gov_docs")]
        self.assertEqual(rows, [{"doc_id": "do:2886884", "doc_type": "law", "tier": 1}])


if __name__ == "__main__":
    unittest.main()
