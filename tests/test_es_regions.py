"""Spain's regional layer (tools/es_regions.py, src/es_regions_store.py, the
regional section of src/editions/es.py). No network: trimmed real replies
under tests/fixtures/es_regions/ (the BOE's open-data summary of 6 October
and 29 August 2026, and the five parliaments' lists as served on 12 October
2026), the repo's own Spanish taxonomy, an in-memory store."""
import json
import os
import sqlite3
import sys
import unittest
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import es_regions as R  # noqa: E402
from src import country_edition as ce, db, drain, es_regions_store as esr  # noqa: E402
from src.editions import es  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "es_regions")
TODAY = "2026-10-12"


def fixture(name, mode="r"):
    with open(os.path.join(FIX, name), mode) as fh:
        return fh.read()


class FakeClient:
    """get_text for the BOE (one issue served, the rest 404), get_bytes for
    the lists; records every URL asked for."""

    def __init__(self, days=None, lists=None):
        self.days = days or {}
        self.lists = lists or {}
        self.asked = []

    def get_text(self, url, feed, slug, headers=None, **kw):
        self.asked.append(url)
        assert headers == {"Accept": "application/json"}
        day = url.rsplit("/", 1)[1]
        if day in self.days:
            return self.days[day]
        raise FetchError(url, feed, slug, 1, urllib.error.HTTPError(url, 404, "Not Found", {}, None))

    def get_bytes(self, url, feed, slug, **kw):
        self.asked.append(url)
        for key, body in self.lists.items():
            if R.SOURCES[key] == url:
                if isinstance(body, Exception):
                    raise body
                return body
        raise AssertionError("unexpected URL " + url)


def store():
    conn = db.init_db(db.connect(":memory:"))
    return conn


class ParseBoe(unittest.TestCase):
    def test_section_one_communities_only(self):
        laws = R.parse_boe(json.loads(fixture("boe-sumario-20261006.json")), "2026-10-06")
        self.assertEqual([(x["boe_id"], x["region"], x["rank"]) for x in laws],
                         [("BOE-A-2026-20746", "as", "ley"), ("BOE-A-2026-20747", "nc", "ley")])
        self.assertEqual(laws[0]["heading"], "Derechos y prestaciones vitales")
        self.assertEqual(laws[0]["department"], "8150")
        self.assertTrue(laws[0]["url_pdf"].endswith("BOE-A-2026-20746.pdf"))
        self.assertTrue(laws[1]["title"].startswith("Ley Foral 15/2026"))

    def test_madrid_laws(self):
        laws = R.parse_boe(json.loads(fixture("boe-sumario-20260829.json")), "2026-08-29")
        self.assertEqual({x["region"] for x in laws}, {"md"})
        self.assertTrue(any("concebido" in x["title"] for x in laws))

    def test_ranks(self):
        for title, rank in (("Ley Foral 15/2026, de 24 de septiembre", "ley"),
                            ("Ley del Principado de Asturias 6/2026", "ley"),
                            ("Decreto-ley 2/2026, de 29 de julio", "decreto-ley"),
                            ("Decreto-ley Foral 1/2026, de 15 de abril", "decreto-ley"),
                            ("Decreto Legislativo 1/2026", "decreto legislativo"),
                            ("Decreto 163/2026, de 9 de septiembre", "decreto"),
                            ("Corrección de errores del Decreto 105/2026", "correction"),
                            ("Resolución ISP/300/2026, de 6 de febrero", "other")):
            self.assertEqual(R.rank_of(title), rank, title)

    def test_departments(self):
        for name, code in (("COMUNIDAD AUTÓNOMA DE ANDALUCÍA", "an"),
                           ("COMUNIDAD DE CASTILLA Y LEÓN", "cl"),
                           ("COMUNIDAD AUTÓNOMA DE CASTILLA-LA MANCHA", "cm"),
                           ("COMUNIDAD AUTÓNOMA DE CATALUÑA", "ct"),
                           ("COMUNIDAD AUTÓNOMA DE LAS ILLES BALEARS", "ib"),
                           ("COMUNIDAD AUTÓNOMA DE LA REGIÓN DE MURCIA", "mc"),
                           ("COMUNIDAD FORAL DE NAVARRA", "nc"),
                           ("COMUNITAT VALENCIANA", "vc"),
                           ("CIUDAD DE CEUTA", None),
                           ("MINISTERIO DE DEFENSA", None)):
            self.assertEqual(R.region_of_department(name), code, name)


class ParseLists(unittest.TestCase):
    def test_andalucia_rss_latin1(self):
        bills = R.parse_an(R.decode(fixture("an-iniciativas.rss", "rb")))
        self.assertEqual([b["expediente"] for b in bills],
                         ["13-26/PPL-000002", "13-26/PPL-000001", "13-26/ILPA-000001"])
        self.assertEqual(bills[0]["kind"], "proposición de ley")
        self.assertEqual(bills[2]["kind"], "ilp")
        self.assertTrue(bills[0]["title"].startswith("Proposición de Ley relativa a acoso"))
        self.assertEqual(bills[0]["presented"], "2026-09-08")
        self.assertNotIn("utm_", bills[0]["url"])

    def test_canarias_list(self):
        bills = R.parse_cn(fixture("cn-leyes.html"))
        self.assertEqual(len(bills), 12)
        first = {b["expediente"]: b for b in bills}
        self.assertEqual(first["11L/DL-0026"]["kind"], "decreto-ley")
        self.assertEqual(first["11L/PL-0012"]["title"], "Proyecto de Ley Canaria de la Ciencia.")
        self.assertTrue(first["11L/PL-0016"]["title"].startswith("Proyecto de Ley de modificación"))
        self.assertEqual(first["11L/PPL-0007"]["kind"], "proposición de ley")
        self.assertTrue(first["11L/PPL-0007"]["url"].startswith("https://www.parcan.es/iniciativas/"))

    def test_la_rioja_list(self):
        bills = R.parse_ri(fixture("ri-proyectos.html"))
        self.assertEqual([(b["expediente"], b["status"], b["presented"]) for b in bills],
                         [("11L/PL-0020", "en tramitación", "2026-09-29"),
                          ("11L/PL-0019", "en tramitación", "2026-09-29"),
                          ("11L/PL-0008", "cerrado", "2024-11-05")])
        self.assertEqual(bills[0]["proponent"], "Gobierno de La Rioja")
        self.assertTrue(bills[2]["title"].startswith("Proyecto de Ley de garantías"))

    def test_cantabria_dossiers(self):
        bills = R.parse_cb(fixture("cb-dossieres.html"))
        self.assertEqual(bills[0]["expediente"], "180/XI")
        self.assertEqual(bills[0]["presented"], "2026-10-05")
        self.assertEqual({b["kind"] for b in bills}, {"proyecto de ley"})
        self.assertTrue(any("LGTBI" in b["title"] for b in bills))

    def test_valencia_is_valencian(self):
        bills = R.parse_vc(fixture("vc-iniciatives.html"))
        self.assertEqual(len(bills), 2)
        self.assertEqual({b["lang"] for b in bills}, {"ca"})
        self.assertEqual(bills[0]["expediente"], "205133716300936")
        self.assertEqual(bills[0]["presented"], "2026-09-30")
        self.assertEqual(bills[1]["kind"], "proposición de ley")


class Collect(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        self.tax = R.load_taxonomy()
        self.assertIsNotNone(self.tax, "config/taxonomy-es.yaml is part of the repo")

    def test_boe_pull_skips_sundays_and_404s(self):
        client = FakeClient(days={"20261006": fixture("boe-sumario-20261006.json")})
        read, stored, ours, gaps = R.pull_boe(self.conn, client, TODAY, self.tax,
                                              drain.Budget(60), days=7)
        self.assertEqual((read, stored, gaps), (1, 2, 0))
        self.assertFalse(any(u.endswith("20261011") for u in client.asked))   # a Sunday
        row = self.conn.execute("SELECT last_day, items, status FROM esr_reads WHERE source='boe'").fetchone()
        self.assertEqual(tuple(row), ("2026-10-06", 2, "ok"))
        # The next run starts from the newest issue read, less the re-read.
        days = R.boe_days(self.conn, "2026-10-14")
        self.assertEqual(days[0].isoformat(), "2026-10-05")

    def test_boe_failure_is_a_gap(self):
        class Down(FakeClient):
            def get_text(self, url, feed, slug, headers=None, **kw):
                raise FetchError(url, feed, slug, 4, OSError("timed out"))
        _, _, _, gaps = R.pull_boe(self.conn, Down(), TODAY, self.tax, drain.Budget(60), days=3)
        self.assertEqual(gaps, 2)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='es-regions'").fetchone()[0], 2)

    def test_lgbti_law_is_on_our_ground(self):
        law = {"boe_id": "BOE-A-2026-8073", "region": "ct", "department": "8070",
               "published": "2026-04-11", "rank": "ley", "heading": "Derechos LGBTI",
               "title": "Ley 13/2025, de 29 de diciembre, de los derechos de las personas LGBTI "
                        "y la erradicación de la LGBTI-fobia.", "url_html": None, "url_pdf": None}
        self.assertTrue(R.on_our_ground(R.store_law(self.conn, self.tax, law, TODAY)))

    def test_seed_then_new(self):
        lists = {"cb": fixture("cb-dossieres.html", "rb")}
        n, _, g = R.pull_list(self.conn, FakeClient(lists=lists), "2026-10-05", self.tax, "cb")
        self.assertEqual((n, g), (6, 0))
        self.assertEqual(self.conn.execute("SELECT MIN(seed) FROM esr_bills").fetchone()[0], 1)
        # A week later one more dossier, with no date: new, not seed.
        extra = (b'<li class="list-group-item node-bop"><div class="views-field views-field-title">'
                 b'<span class="field-content"><a href="/informacion-general/181xi-legislatura" '
                 b'hreflang="es">181/XI Legislatura</a></span></div><div class="views-field '
                 b'views-field-field-t-tulo"><div class="field-content">Proyecto de Ley de '
                 b'protecci\xc3\xb3n de la familia de Cantabria.</div></div></li>')
        body = lists["cb"].replace(b"<ul>\n", b"<ul>\n" + extra + b"\n", 1)
        R.pull_list(self.conn, FakeClient(lists={"cb": body}), "2026-10-12", self.tax, "cb")
        row = self.conn.execute("SELECT seed, first_seen, presented FROM esr_bills "
                                "WHERE bill_key='cb:181/XI'").fetchone()
        self.assertEqual(tuple(row), (0, "2026-10-12", None))
        old = self.conn.execute("SELECT first_seen, last_seen FROM esr_bills "
                                "WHERE bill_key='cb:180/XI'").fetchone()
        self.assertEqual(tuple(old), ("2026-10-05", "2026-10-12"))

    def test_valencian_titles_stay_unclassified(self):
        R.pull_list(self.conn, FakeClient(lists={"vc": fixture("vc-iniciatives.html", "rb")}),
                    TODAY, self.tax, "vc")
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM esr_bills WHERE region='vc' AND areas IS NULL").fetchone()[0], 2)

    def test_empty_list_is_a_gap(self):
        n, _, g = R.pull_list(self.conn, FakeClient(lists={"an": b"<rss></rss>"}), TODAY,
                              self.tax, "an")
        self.assertEqual((n, g), (0, 1))
        self.assertEqual(self.conn.execute("SELECT status FROM esr_reads WHERE source='an'")
                         .fetchone()[0], "empty")

    def test_refused_list_is_a_gap(self):
        err = FetchError(R.SOURCES["cn"], R.FEED, "list-cn", 1,
                         urllib.error.HTTPError(R.SOURCES["cn"], 503, "x", {}, None))
        n, _, g = R.pull_list(self.conn, FakeClient(lists={"cn": err}), TODAY, self.tax, "cn")
        self.assertEqual((n, g), (0, 1))

    def test_reclassify_offline(self):
        R.pull_list(self.conn, FakeClient(lists={"cb": fixture("cb-dossieres.html", "rb")}),
                    TODAY, self.tax, "cb")
        self.conn.execute("UPDATE esr_bills SET areas=NULL")
        R.reclassify(self.conn, self.tax)
        self.assertGreater(self.conn.execute(
            "SELECT COUNT(*) FROM esr_bills WHERE areas IS NOT NULL").fetchone()[0], 0)


class Edition(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        tax = R.load_taxonomy()
        client = FakeClient(days={"20261006": fixture("boe-sumario-20261006.json")},
                            lists={"cb": fixture("cb-dossieres.html", "rb"),
                                   "an": fixture("an-iniciativas.rss", "rb"),
                                   "vc": fixture("vc-iniciatives.html", "rb")})
        R.pull_boe(self.conn, client, TODAY, tax, drain.Budget(60), days=7)
        for src in ("cb", "an", "vc"):
            R.pull_list(self.conn, client, TODAY, tax, src)
        R.store_law(self.conn, tax, {
            "boe_id": "BOE-A-2026-8073", "region": "ct", "department": "8070",
            "published": "2026-10-10", "rank": "ley", "heading": None,
            "title": "Ley 13/2025, de 29 de diciembre, de los derechos de las personas LGBTI "
                     "y la erradicación de la LGBTI-fobia.", "url_html": "https://x", "url_pdf": None},
            TODAY)
        self.conn.commit()
        self.dir = os.path.join(FIX, "no-editions-here")

    def render(self, since):
        return ce.render(self.conn, es.COUNTRY, TODAY, since=since, directory=self.dir)

    def test_section_on_a_quiet_congreso_week(self):
        text = self.render("2026-09-01")
        self.assertIn("**A quiet", text)
        self.assertIn("## Regional parliaments", text)
        self.assertIn("### Regional laws in the BOE", text)
        self.assertIn("Law of Cataluña, published in the BOE on 10 October 2026", text)
        self.assertIn("### New regional bills", text)
        self.assertIn("an:13-26/PPL-000002", text)
        self.assertIn("Members' bill in the Parlamento de Andalucía", text)
        # Cantabria's dossiers dated before the window stay out, seed or not.
        self.assertNotIn("cb:175/XI", text)
        # The two Valencian bills are counted, never shown.
        self.assertIn("Not classified, published in a co-official language only: 2 new bill(s)", text)
        self.assertNotIn("Pojecte de llei", text)
        self.assertNotIn("—", text)

    def test_window_is_the_editions(self):
        text = self.render("2026-10-08")
        self.assertIn("BOE-A-2026-8073", text)
        self.assertNotIn("an:13-26/PPL-000002", text)    # presented 8 September

    def test_section_sits_before_the_watchlist(self):
        self.conn.execute(
            "INSERT INTO es_initiatives (initiative_key, legislature, expediente, tipo, objeto, "
            "presentada, areas, matched_terms, tier) VALUES ('15/122/000201', 15, '122/000201', "
            "'Proposición de ley de Grupos Parlamentarios del Congreso', 'Proposición de Ley "
            "para penalizar las terapias de conversión.', '2026-10-09', '[5]', "
            "'[\"terapias de conversión\"]', 1)")
        text = self.render("2026-10-05")
        self.assertLess(text.index("## New on our ground"), text.index("## Regional parliaments"))
        self.assertLess(text.index("## Regional parliaments"), text.index("## Watchlist"))
        self.assertEqual(text.count("## Regional parliaments"), 1)

    def test_dm_line(self):
        line = es.regional_dm_line(self.conn, TODAY, directory=self.dir)
        self.assertTrue(line.startswith("_Regional parliaments:"))
        self.assertIn("in the edition", line)

    def test_no_layer_yet(self):
        conn = store()
        text = ce.render(conn, es.COUNTRY, TODAY, since="2026-10-05", directory=self.dir)
        self.assertIn("The regional layer has not run yet", text)
        self.assertIsNone(es.regional_dm_line(conn, TODAY, directory=self.dir))


if __name__ == "__main__":
    unittest.main()
