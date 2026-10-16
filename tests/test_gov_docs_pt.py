"""Portugal's gov_docs reader (src/gov_doc_sources/pt.py): the Diário da
República's RSS (Série I, Série II Parte C) and ConsultaLEX, on fixtures
captured live on 16 October 2026."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs as G  # noqa: E402
from src.gov_doc_sources import pt  # noqa: E402

TODAY = "2026-10-16"
FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs", "pt")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


PAGES = {pt.DR1: "dr-serie1.xml", pt.DR2C: "dr-serie2-c.xml", pt.CLEX: "consultalex-home.html"}

# A card as ConsultaLEX prints an OPEN consultation is not on the live page
# (none was open on 16 October 2026); this one is the live closed card with
# its countdown words changed, to pin the open branch of the parser.
OPEN_CARD = (
    '<div  id="x_ctl00_wtContent" class="card full-opacity"><span class="icon icon-educacao '
    'icon-large text-primary"></span><div class="heading5"><a href="#"><span id="x_wtOpenCpsTitle" '
    'tabindex="0">Projeto de decreto-lei que altera o regime da educação sexual em meio escolar'
    '</span></a></div><div class="margin-top-m card--consulta--description"><span '
    'id="x_wtCPDescription">Revisão da Lei n.º 60/2009 e da educação para a sexualidade</span></div>'
    '<div  class="card--dias-terminar"><div ><span class="text-neutral-2">Termina em</span></div >'
    '<div  class="text-uppercase text-primary text-bold heading5">12 dias</div ></div ></div>')


class FakeClient:
    def __init__(self, pages=None):
        self.pages = pages or {u: fixture(n) for u, n in PAGES.items()}

    def get_text(self, url, feed, slug, *args, **kwargs):
        return self.pages[url]


class DiarioTests(unittest.TestCase):
    def test_serie1(self):
        got = pt.parse_dr_rss(fixture("dr-serie1.xml"), "I")
        self.assertEqual(len(got), 3)
        portaria = got[2]
        self.assertEqual(portaria["doc_id"], "dr1:portaria/458-2026-1182082414")
        self.assertEqual(portaria["doc_type"], "regulation")
        self.assertEqual(portaria["body"], "Economia e Coesão Territorial")
        self.assertEqual(portaria["published"], "2026-10-16")
        self.assertTrue(portaria["title"].startswith("Portaria n.º 458/2026/1: Procede"))
        self.assertEqual(got[1]["body"], "Presidência do Conselho de Ministros")

    def test_serie2_c_skips_praise_and_staff_extracts(self):
        got = pt.parse_dr_rss(fixture("dr-serie2-c.xml"), "II-C")
        self.assertTrue(got)
        self.assertFalse(any("/louvor/" in e["doc_id"] or "/aviso-extrato/" in e["doc_id"]
                             for e in got))
        self.assertTrue(all(e["source"] == "dr2c" for e in got))

    def test_types(self):
        self.assertEqual(pt.dr_type("Lei n.º 12/2026"), "law")
        self.assertEqual(pt.dr_type("Decreto-Lei n.º 80/2026"), "law")
        self.assertEqual(pt.dr_type("Lei Orgânica n.º 3/2026"), "law")
        self.assertEqual(pt.dr_type("Portaria n.º 458/2026/1"), "regulation")
        self.assertEqual(pt.dr_type("Resolução da Assembleia da República n.º 9/2026"), "publication")

    def test_split_emitter(self):
        self.assertEqual(pt.split_emitter("Saúde Aprova o regulamento"), ("Saúde", "Aprova o regulamento"))


class ConsultalexTests(unittest.TestCase):
    def test_closed_cards(self):
        got = pt.parse_consultalex(fixture("consultalex-home.html"), TODAY)
        self.assertEqual(len(got), 9)
        first = got[0]
        self.assertEqual(first["title"], "Portaria que aprova o Regulamento da Rede Portuguesa Saber Fazer")
        self.assertEqual(first["doc_type"], "regulation_draft")
        self.assertEqual(first["closing_date"], "2026-10-01")          # 'Terminou | Há 15 dias'
        self.assertIn("cultura", first["body"])
        inclusive = [e for e in got if "educação inclusiva" in e["title"]][0]
        self.assertEqual(inclusive["closing_date"], "2026-07-17")

    def test_open_card(self):
        got = pt.parse_consultalex(OPEN_CARD, TODAY)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["closing_date"], "2026-10-28")
        self.assertEqual(got[0]["doc_type"], "regulation_draft")


class CollectTests(unittest.TestCase):
    def test_collect(self):
        conn = db.init_db(db.connect(":memory:"))
        pages = {u: fixture(n) for u, n in PAGES.items()}
        pages[pt.CLEX] = pages[pt.CLEX].replace("</form>", OPEN_CARD + "</form>", 1) \
            if "</form>" in pages[pt.CLEX] else pages[pt.CLEX] + OPEN_CARD
        listed, kept, gaps = G.collect(conn, "pt", FakeClient(pages), TODAY, log=lambda *a: None)
        self.assertEqual(gaps, 0)
        self.assertGreater(listed, 20)
        rows = [dict(r) for r in conn.execute("SELECT * FROM gov_docs WHERE cc='pt'")]
        self.assertEqual(kept, len(rows))
        due = G.deadline_rows(conn, "pt", TODAY, "2026-12-31")
        self.assertEqual(len(due), 1)
        self.assertEqual((due[0]["doc_type"], due[0]["closing_date"]), ("regulation_draft", "2026-10-28"))
        runs = {r[0]: r[1] for r in conn.execute("SELECT source, ok FROM gov_doc_runs WHERE cc='pt'")}
        self.assertEqual(runs, {"dr1": 1, "dr2c": 1, "clex": 1})


if __name__ == "__main__":
    unittest.main()
