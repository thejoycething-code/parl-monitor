"""Spain's gov_docs reader (src/gov_doc_sources/es.py): the BOE's section I
and the ministries' participation pages, on fixtures captured live on
16 October 2026."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs as G  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.gov_doc_sources import es  # noqa: E402

TODAY = "2026-10-16"
FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs", "es")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


PAGES = {
    es.BOE_SUMARIO.format("20261015"): "boe-sumario-20261015.json",
    es.IGUALDAD + "audienciapublica/": "igualdad-audiencia.html",
    es.IGUALDAD + "consultapublica/": "igualdad-consulta.html",
    es.SANIDAD + "audiencia/home.htm": "sanidad-audiencia.html",
    es.SANIDAD + "consultas/home.htm": "sanidad-consultas.html",
    es.MPR + "consultaprevia/Paginas/index.aspx": "mpr-consultaprevia.html",
    es.MPR + "audienciapublica/Paginas/index.aspx": "mpr-audiencia.html",
    es.JUSTICIA: "justicia.html",
    es.EDUCACION_LIST: "educacion-list.html",
    es.EDUCACION + "/servicios-al-ciudadano/informacion-publica/audiencia-informacion-publica/"
                   "abiertos/2026/prd-rd1322010-rd6592023.html": "educacion-item.html",
}


class FakeClient:
    """Serves the fixtures; any other URL answers 404 (a BOE day with no
    issue, or a host that did not answer)."""

    def __init__(self):
        self.asked = []

    def get_text(self, url, feed, slug, *args, **kwargs):
        self.asked.append(url)
        if url in PAGES:
            return fixture(PAGES[url])
        raise FetchError(url, feed, slug, 1, Exception("HTTP Error 404: Not Found"))


class BoeTests(unittest.TestCase):
    def test_section_one_national_acts(self):
        got = es.parse_boe(json.loads(fixture("boe-sumario-20261015.json")), "2026-10-15")
        self.assertEqual(len(got), 11)
        first = got[0]
        self.assertEqual(first["doc_id"], "boe:BOE-A-2026-21445")
        self.assertEqual(first["doc_type"], "regulation")
        self.assertEqual(first["body"], "Ministerio de la Presidencia, Justicia y Relaciones con las Cortes")
        self.assertEqual(first["published"], "2026-10-15")
        self.assertTrue(first["url"].startswith("https://www.boe.es/"))
        self.assertTrue(any(e["body"] == "Ministerio de Juventud e Infancia" for e in got))

    def test_types(self):
        self.assertEqual(es.boe_type("Ley Orgánica 1/2026, de 3 de marzo, de ..."), "law")
        self.assertEqual(es.boe_type("Real Decreto-ley 5/2026, de 2 de junio"), "law")
        self.assertEqual(es.boe_type("Real Decreto 824/2026, de 14 de octubre"), "regulation")
        self.assertEqual(es.boe_type("Orden SND/1/2026, de 2 de enero"), "regulation")

    def test_no_sundays(self):
        days = list(es.boe_days(TODAY, 8))
        self.assertTrue(all(d.weekday() != 6 for d in days))
        self.assertEqual(len(days), 7)


class ParticipationTests(unittest.TestCase):
    def parse(self, name, url, kind, code="x"):
        return es.parse_participation(fixture(name), url, kind, "Ministerio", code)

    def test_igualdad_audiencia(self):
        got = self.parse("igualdad-audiencia.html", es.IGUALDAD + "audienciapublica/", "audiencia",
                         "igualdad")
        ive = got[0]
        self.assertIn("interrupción voluntaria del embarazo", ive["title"])
        self.assertEqual(ive["doc_type"], "regulation_draft")
        self.assertEqual((ive["published"], ive["closing_date"]), ("2026-10-07", "2026-10-19"))
        self.assertTrue(ive["url"].startswith(es.IGUALDAD + "audienciapublica/"))
        bills = [e for e in got if e["doc_type"] == "bill_draft"]
        self.assertTrue(any("violencia vicaria" in e["title"] for e in bills))

    def test_igualdad_consulta_page_keeps_the_banner_an_audiencia(self):
        got = self.parse("igualdad-consulta.html", es.IGUALDAD + "consultapublica/", "consulta")
        self.assertEqual(got[0]["doc_type"], "regulation_draft")      # the open audiencia banner
        self.assertTrue(all(e["doc_type"] == "consultation" for e in got[1:]))

    def test_sanidad_long_dates(self):
        aud = self.parse("sanidad-audiencia.html", es.SANIDAD + "audiencia/home.htm", "audiencia")
        self.assertEqual(len(aud), 4)
        self.assertEqual((aud[0]["published"], aud[0]["closing_date"]), ("2026-10-02", "2026-10-26"))
        cons = self.parse("sanidad-consultas.html", es.SANIDAD + "consultas/home.htm", "consulta")
        ive = [e for e in cons if "831/2010" in e["title"]][0]
        self.assertEqual(ive["doc_type"], "consultation")
        self.assertEqual(ive["closing_date"], "2026-10-20")

    def test_mpr_split_cells(self):
        got = self.parse("mpr-audiencia.html", es.MPR + "audienciapublica/Paginas/index.aspx",
                         "audiencia")
        self.assertGreater(len(got), 10)
        honour = [e for e in got if "derecho al honor" in e["title"]][0]
        self.assertEqual(honour["doc_type"], "bill_draft")
        self.assertEqual(honour["closing_date"], "2026-01-30")
        religion = [e for e in got if "Libertad Religiosa" in e["title"]][0]
        self.assertEqual(religion["doc_type"], "regulation_draft")

    def test_justicia_free_text(self):
        got = self.parse("justicia.html", es.JUSTICIA, "mixed")
        self.assertEqual(len(got), 3)
        self.assertTrue(all(e["doc_type"] == "regulation_draft" for e in got))
        rc = [e for e in got if "Registro Civil" in e["title"]][0]
        self.assertEqual((rc["published"], rc["closing_date"]), ("2026-10-02", "2026-11-02"))
        arancel = [e for e in got if "1427/1989" in e["title"]][0]   # 'del 25 de septiembre al 16 de octubre de 2026'
        self.assertEqual((arancel["published"], arancel["closing_date"]), ("2026-09-25", "2026-10-16"))

    def test_educacion(self):
        items = es.parse_educacion_list(fixture("educacion-list.html"))
        self.assertEqual(len(items), 10)
        self.assertEqual(sum(1 for i in items if i[1] == "audiencia"), 3)
        self.assertEqual(es.parse_educacion_item(fixture("educacion-item.html")),
                         ("2026-10-15", "2026-11-05"))

    def test_educacion_reads_item_pages_only_for_our_ground(self):
        client = FakeClient()
        target = [u for u in PAGES if u.endswith("prd-rd1322010-rd6592023.html")][0]
        real = es._looks_ours
        es._looks_ours = lambda title, taxes, wl: "132/2010" in title
        try:
            got = es.fetch_educacion(client, TODAY, taxes=[], wl={})
        finally:
            es._looks_ours = real
        self.assertEqual(client.asked, [es.EDUCACION_LIST, target])
        item = [e for e in got.entries if e["url"] == target][0]
        self.assertEqual(item["doc_type"], "regulation_draft")
        self.assertEqual(item["closing_date"], "2026-11-05")


class CollectTests(unittest.TestCase):
    def test_collect(self):
        conn = db.init_db(db.connect(":memory:"))
        listed, kept, gaps = G.collect(conn, "es", FakeClient(), TODAY, log=lambda *a: None)
        self.assertGreater(listed, 20)
        rows = {r["doc_id"]: dict(r) for r in conn.execute("SELECT * FROM gov_docs WHERE cc='es'")}
        self.assertEqual(kept, len(rows))
        ive = [r for r in rows.values() if r["source"] == "igualdad"][0]
        self.assertEqual(ive["doc_type"], "regulation_draft")
        self.assertEqual(ive["closing_date"], "2026-10-19")
        self.assertIn(1, json.loads(ive["areas"]))
        san = [r for r in rows.values() if r["source"] == "sanidad"][0]
        self.assertEqual((san["doc_type"], san["closing_date"]), ("consultation", "2026-10-20"))
        due = G.deadline_rows(conn, "es", TODAY, "2026-12-31")
        self.assertEqual([d["closing_date"] for d in due], ["2026-10-19", "2026-10-20"])
        # Juventud e Infancia and Derechos Sociales did not answer: two gaps, loud
        self.assertEqual(gaps, 2)
        runs = {r[0]: r[1] for r in conn.execute(
            "SELECT source, ok FROM gov_doc_runs WHERE cc='es'")}
        self.assertEqual(runs["juventud"], 0)
        self.assertEqual(runs["boe"], 1)


if __name__ == "__main__":
    unittest.main()
