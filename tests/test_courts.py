"""X8 constitutional courts (10 October 2026): src/courts.py and the four
collectors, on real replies in tests/fixtures/courts/ (no network)."""

import datetime
import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import courts, db, latam  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "courts")
TODAY = "2026-10-10"


def tool(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def store():
    return db.init_db(db.connect(":memory:"))


class FakeClient:
    """Serves fixtures by URL substring; records what was asked."""

    def __init__(self, routes):
        self.routes = routes
        self.asked = []
        self.throttles = {}

    def set_host_throttle(self, host, seconds):
        self.throttles[host] = seconds

    def _find(self, url):
        self.asked.append(url)
        for part, body in self.routes:
            if part in url:
                if isinstance(body, Exception):
                    raise body
                return body
        raise AssertionError("unexpected fetch: " + url)

    def get_json(self, url, feed, slug, **kw):
        return json.loads(self._find(url))

    def get_text(self, url, feed, slug, **kw):
        return self._find(url)


class SchemaTests(unittest.TestCase):
    def test_every_country_has_its_rulings_table(self):
        conn = store()
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for cc in ("co", "ec", "pe", "pt"):
            self.assertIn(cc + "_rulings", names)
            self.assertIn(cc + "_rulings", db.TABLES)


class GuardTests(unittest.TestCase):
    def test_causales_needs_abortion_company(self):
        tax = courts.load_taxonomy("ec")
        areas, terms, _ = courts.classify(
            tax, "Nulidad de laudo arbitral",
            "verificar si se han configurado las causales taxativas del art. 31 de la Ley de Arbitraje")
        self.assertNotIn("causales", terms)
        areas, terms, _ = courts.classify(
            tax, "Aborto por violación", "las causales de aborto no punible y el embarazo forzado")
        self.assertIn(1, areas)


class ColombiaTests(unittest.TestCase):
    def setUp(self):
        self.mod = tool("co_courts")
        self.conn = store()
        self.tax = courts.load_taxonomy("co")

    def test_parse_and_store(self):
        rows = self.mod.parse(json.loads(read("co_exhortos.json")))
        self.assertEqual(len(rows), 7)
        c055 = [r for r in rows if r["ruling_key"] == "C-055/22"][0]
        self.assertEqual(c055["kind"], "exhortation")
        self.assertEqual(c055["date"], "2022-02-21")
        self.assertTrue(c055["url"].endswith("C-055-22.htm"))
        client = FakeClient([("fbtr-7k2r", read("co_exhortos.json"))])
        got = self.mod.pull(self.conn, client, TODAY, self.tax, log=lambda *a: None)
        self.assertEqual(got[:2], (7, 7))
        areas = {r[0]: json.loads(r[1]) for r in self.conn.execute(
            "SELECT ruling_key, areas FROM co_rulings")}
        self.assertIn(1, areas["C-055/22"])           # abortion
        self.assertIn(2, areas["C-239/97"])           # muerte digna
        self.assertIn(10, areas["T-127/24"])          # surrogacy
        self.assertEqual(areas["C-473/94"], [])       # the strike law: not ours

    def test_unreadable_is_a_gap(self):
        from src.http import FetchError
        client = FakeClient([("fbtr-7k2r", FetchError("u", "f", "s", 1, "boom"))])
        got = self.mod.pull(self.conn, client, TODAY, self.tax, log=lambda *a: None)
        self.assertEqual(got[3], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0], 1)


class EcuadorTests(unittest.TestCase):
    def setUp(self):
        self.mod = tool("ec_courts")

    def test_parse(self):
        rows = {r["ruling_key"]: r for r in self.mod.parse(json.loads(read("ec_posts.json")))}
        self.assertIn("ec:92-22-IN/26", rows)
        r = rows["ec:92-22-IN/26"]
        self.assertEqual((r["kind"], r["case_no"], r["date"]), ("ruling", "92-22-IN/26", "2026-08-26"))
        self.assertFalse(r["summary"].startswith("Sentencia"))       # the title is not repeated
        bulletin = [r for r in rows.values() if r["formation"] == "Boletines comunicacionales"][0]
        self.assertEqual(bulletin["kind"], "ruling")                 # "emite sentencia"
        self.assertEqual(bulletin["case_no"], "1313-19-JP/26")
        comunicado = [r for r in rows.values() if r["formation"] == "Comunicados"][0]
        self.assertTrue(comunicado["ruling_key"].startswith("ec-post:"))

    def test_since_date(self):
        conn = store()
        self.assertEqual(self.mod.since_date(conn, today=datetime.date(2026, 10, 10)), "2025-10-10")
        conn.execute("INSERT INTO ec_rulings (ruling_key, court, kind, date) VALUES ('k','c','ruling',"
                     "'2026-08-26')")
        self.assertEqual(self.mod.since_date(conn), "2026-07-27")
        self.assertEqual(self.mod.since_date(conn, "2024-01-01"), "2024-01-01")

    def test_identity_ruling_classified(self):
        conn = store()
        client = FakeClient([("wp-json", read("ec_posts.json"))])
        self.mod.pull(conn, client, TODAY, courts.load_taxonomy("ec"), "2026-01-01",
                      log=lambda *a: None)
        areas = json.loads(conn.execute("SELECT areas FROM ec_rulings WHERE ruling_key LIKE "
                                        "'ec-post:%' AND case_no='1313-19-JP/26'").fetchone()[0])
        self.assertIn(3, areas)          # gender identity of a minor


class PeruTests(unittest.TestCase):
    def setUp(self):
        self.mod = tool("pe_courts")

    def test_listing_and_dates(self):
        notes = self.mod.parse_listing(read("pe_listing.html"))
        self.assertEqual(len(notes), 6)
        self.assertEqual(notes[0]["date"], "2026-10-09")
        self.assertTrue(notes[0]["url"].startswith("https://www.tc.gob.pe/institucional/notas-de-prensa/"))
        self.assertEqual(self.mod.es_date("9 de setiembre de 2026"), "2026-09-09")

    def test_kinds(self):
        k = self.mod.kind_of
        self.assertEqual(k("LA PRESENCIA DEL CRUCIFIJO Y LA BIBLIA EN ESPACIOS PÚBLICOS NO AFECTA "
                           "LA LIBERTAD RELIGIOSA"), "ruling")
        self.assertEqual(k("TC VERÁ CAUSA SOBRE RECONOCIMIENTO DE MATRIMONIO IGUALITARIO"), "hearing")
        self.assertEqual(k("MAGISTRADO DEL TC PRESENTÓ LIBRO EN LA FERIA"), "press")
        self.assertEqual(k("SENTENCIAS EMBLEMÁTICAS ANALIZADAS EN CONFERENCIA"), "press")

    def test_note_page(self):
        date, title, text, lists = self.mod.parse_note(read("pe_note_hearing.html"))
        self.assertEqual(date, "2026-09-09")
        self.assertIn("AUDIENCIA", title)
        self.assertEqual(len(lists), 2)
        self.assertEqual(self.mod.kind_of(title), "hearing")

    def test_feed_backfill(self):
        conn = store()
        got = self.mod.backfill_feed(conn, None, TODAY, courts.load_taxonomy("pe"),
                                     xml=read("pe_feed.xml"))
        self.assertEqual(got[0], 4)
        rows = {r[0]: (r[1], json.loads(r[2])) for r in conn.execute(
            "SELECT title, kind, areas FROM pe_rulings")}
        crucifix = [v for t, v in rows.items() if "CRUCIFIJO" in t][0]
        self.assertEqual(crucifix[0], "ruling")
        self.assertIn(8, crucifix[1])

    def test_weekly_reads_only_what_matters_and_respects_crawl_delay(self):
        conn = store()
        client = FakeClient([("notas-de-prensa/page/", "<html></html>"),
                             ("/notas-de-prensa/tc-", read("pe_note_hearing.html")),
                             ("/notas-de-prensa/", read("pe_listing.html"))])
        self.mod.pull(conn, client, TODAY, courts.load_taxonomy("pe"), log=lambda *a: None,
                      max_pages=1)
        self.assertEqual(client.throttles.get("www.tc.gob.pe"), 30.0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM pe_rulings").fetchone()[0], 6)
        # Six institutional notes: the listing is enough, no note page read.
        self.assertEqual(len(client.asked), 1)


class PortugalTests(unittest.TestCase):
    def setUp(self):
        self.mod = tool("pt_courts")

    def test_landing(self):
        got = self.mod.parse_list(read("pt_landing.html"))
        self.assertEqual(len(got), 30)
        self.assertEqual(got[0], {"year": 2026, "number": 835, "process": "1030/26",
                                  "formation": "Conf.", "especie": "Reclamação",
                                  "date": "2026-10-01", "relator": "Cons. Luís Filipe Lameiras"})
        self.assertFalse(self.mod.readable("Conf."))
        self.assertTrue(self.mod.readable("2ª Secção"))
        self.assertTrue(self.mod.readable("Plenário"))

    def test_euthanasia_ruling_parts(self):
        opening, disp = self.mod.parts(self.mod.page_text(read("pt_acordao_2023_5.html")))
        self.assertTrue(opening.startswith("ACÓRDÃO Nº 5/2023"))
        self.assertTrue(disp.startswith("III – Decisão"))
        self.assertIn("Pronunciar-se pela inconstitucionalidade", disp)
        areas, terms, tier = courts.classify(courts.load_taxonomy("pt"), "Acórdão 5/2023",
                                             opening, disp)
        self.assertEqual((areas, tier), ([2], 1))

    def test_register_then_read_plenary_first_and_stop_on_429(self):
        from src.http import FetchError
        conn = store()
        tax = courts.load_taxonomy("pt")
        for e in self.mod.parse_list(read("pt_landing.html")):
            self.mod.register(conn, e, tax, TODAY)
        conn.execute("UPDATE pt_rulings SET formation='Plenário' WHERE ruling_key='2026/800'")
        waiting = self.mod.to_read(conn, 50)
        self.assertTrue(all(self.mod.readable(r[1]) for r in waiting))
        self.assertNotIn("2026/835", [r[0] for r in waiting])        # Conf.: never read
        got = self.mod.pull(conn, FakeClient([("tc/acordaos/2026", FetchError(
            "u", "f", "s", 1, "HTTP Error 429")), ("tc/acordaos/", read("pt_landing.html"))]),
            TODAY, tax, log=lambda *a: None)
        listed, new, nread, ours, gaps = got
        self.assertEqual((listed, new, nread, gaps), (30, 0, 0, 1))


class EditionTests(unittest.TestCase):
    def _row(self, conn, cc, key, date, first_seen, areas="[2]", kind="ruling"):
        conn.execute("INSERT INTO {0}_rulings (ruling_key, court, kind, date, title, areas, tier, "
                     "first_seen, last_seen) VALUES (?,?,?,?,?,?,1,?,?)".format(cc),
                     (key, "Corte", kind, date, "t " + key, areas, first_seen, first_seen))

    def test_news_rows_window_late_and_seed(self):
        conn = store()
        self._row(conn, "co", "seeded-old", "2026-08-01", "2026-09-01")    # seed day, old date
        self._row(conn, "co", "in-window", "2026-09-20", "2026-09-01")
        self._row(conn, "co", "late", "2026-08-15", "2026-09-25")          # published late
        self._row(conn, "co", "too-old", "2020-01-01", "2026-09-25")
        self._row(conn, "co", "noise", "2026-09-20", "2026-09-20", areas="[]")
        self._row(conn, "co", "press", "2026-09-20", "2026-09-20", kind="press")
        got = [r["ruling_key"] for r in courts.news_rows(conn, "co", "2026-09-10", "2026-10-10")]
        self.assertEqual(sorted(got), ["in-window", "late"])

    def test_latam_items_carry_rulings(self):
        conn = store()
        self._row(conn, "ec", "ec:34-19-IN/21", "2026-09-20", "2026-09-20", areas="[1]")
        items = latam.country_items(conn, "ec", "2026-09-10", "2026-10-10")
        rulings = [i for i in items if i["kind"] == "ruling"]
        self.assertEqual(len(rulings), 1)
        self.assertEqual(rulings[0]["areas"], [1])
        self.assertTrue(rulings[0]["lines"][0].startswith("Ruling of the Corte"))

    def test_portugal_edition_carries_rulings(self):
        from src.editions import pt
        conn = store()
        self._row(conn, "pt", "2023/5", "2026-09-20", "2026-09-20")
        got = [i for i in pt.items(conn, "2026-09-10", "2026-10-10", {}) if i["kind"] == "ruling"]
        self.assertEqual(len(got), 1)
        self.assertIn("Constitutional", latam.KINDS["ruling"])


if __name__ == "__main__":
    unittest.main()
