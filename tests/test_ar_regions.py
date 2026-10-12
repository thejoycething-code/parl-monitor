"""Argentina's provincial layer (13 October 2026): tools/ar_regions.py, the
store src/ar_regions_store.py and the edition's "Provincial legislatures"
section (src/editions/ar.py), on real replies of 13 October 2026 trimmed
into tests/fixtures/ar_regions/ (no network)."""

import datetime
import importlib.util
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db  # noqa: E402
from src import country_edition as ce  # noqa: E402
from src.http import FetchError  # noqa: E402
from tests.robots_fakes import guarded  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "ar_regions")
TODAY = datetime.date(2026, 10, 13)


def tool(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = tool("ar_regions")


def read(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def store():
    return db.init_db(db.connect(":memory:"))


def quiet(*a, **k):
    pass


class FakeClient:
    """Serves fixtures by URL substring; records what was asked."""

    def __init__(self, routes):
        self.routes = routes
        self.asked = []
        self.forms = []
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

    def get_text(self, url, feed, slug, **kw):
        return self._find(url)

    def post_form(self, url, fields, feed, slug, **kw):
        self.forms.append((url, fields))
        return self._find(url)


EMPTY_SAIJ = json.dumps({"searchResults": {"documentResultList": []}})


def routes(saij=None, caba=None):
    return [
        ("saij.gob.ar/busqueda?o=0&", saij if saij is not None else read("saij.json")),
        ("saij.gob.ar/busqueda", EMPTY_SAIJ),
        ("normas.gba.gob.ar/resultados?page=1", read("normas-gba.html")),
        ("normas.gba.gob.ar/resultados", "<html></html>"),
        ("hcdiputados-ba.gov.ar", read("ba-dip.html")),
        ("parlamentaria.legislatura.gob.ar", caba if caba is not None else read("caba.xml")),
        ("Asuntos.aspx?id=", read("cba-session.html")),
        ("Asuntos.aspx", read("cba-sessions.html")),
        ("senadoer.gob.ar/buscador-proyectos", read("er-sen.html")),
    ]


def collect(conn, client=None, watch=None, sources=R.SOURCES, today=TODAY):
    client = client or FakeClient(routes())
    g, _ = guarded(client, {}, R.FEED)
    gaps = R.collect(conn, g, today, sources, R.load_taxonomy(), watch or {}, log=quiet)
    return gaps, client


class Parsers(unittest.TestCase):

    def test_saij_keeps_laws_with_province_and_number(self):
        got = R.parse_saij(read("saij.json"))
        keys = [r["law_key"] for r in got]
        self.assertIn("sf/ley/14488", keys)
        self.assertEqual(len(keys), len(set(keys)))
        sf = next(r for r in got if r["law_key"] == "sf/ley/14488")
        self.assertEqual(sf["published"], "2026-10-07")
        self.assertEqual(sf["sanctioned"], "2026-10-01")
        self.assertTrue(sf["url"].startswith("https://www.saij.gob.ar/14488-local-santa-fe"))
        self.assertIn("Derecho procesal", sf["descriptors"])
        # SAIJ's 'novedad' notes duplicate laws and are skipped
        self.assertEqual(len(got), 5)

    def test_saij_single_descriptor_object(self):
        doc = {"metadata": {"uuid": "u1", "document-content-type": "legislacion",
                            "friendly-url": {"description": "x"}},
               "content": {"provincia": "Tucumán", "numero-norma": 9001, "fecha": "2026-10-01",
                           "titulo-norma": "Ley de prueba",
                           "descriptores": {"descriptor": {"elegido": {"termino": "familia"}}}}}
        reply = json.dumps({"searchResults": {"documentResultList": [
            {"documentAbstract": json.dumps({"document": doc})}]}})
        got = R.parse_saij(reply)
        self.assertEqual(got[0]["law_key"], "tuc/ley/9001")
        self.assertEqual(got[0]["descriptors"], ["familia"])

    def test_normas(self):
        got = R.parse_normas(read("normas-gba.html"))
        self.assertEqual(len(got), 10)
        self.assertEqual(got[0]["law_key"], "ba/ley/15627")
        self.assertEqual(got[0]["published"], "2026-10-02")
        self.assertIn("CASINOS", got[0]["title"])

    def test_ba_dip(self):
        page = read("ba-dip.html")
        got = {r["expediente"]: r for r in R.parse_ba_dip(page)}
        self.assertEqual(R.ba_dip_total(page), 4)
        r = got["D-3281/26-27"]
        self.assertEqual(r["title"], "DE ADHESIÓN AL DÍA MUNDIAL DE LA SALUD SEXUAL.")
        self.assertEqual(r["kind"], "declaracion")
        self.assertTrue(r["author"].startswith("BRAGA ROMINA"))
        self.assertEqual(r["presented"], "2026-09-29")
        self.assertTrue(r["url"].endswith(".pdf"))
        self.assertIn("E-122/25-26-1", got)      # an alcance other than 0 is kept

    def test_caba(self):
        got = {r["bill_key"]: r for r in R.parse_caba(read("caba.xml"))}
        r = got["caba:2563-D-2026"]
        self.assertIn("TERAPIAS DE CONVERSIÓN", r["title"])
        self.assertEqual(r["status"], "EN COMISION · MUJERES, GÉNEROS Y DIVERSIDADES")
        self.assertEqual(r["sanctioned"], 0)
        self.assertTrue(r["url"].startswith("https://parlamentaria.legislatura.gob.ar/pages/expediente.aspx?id="))

    def test_cba(self):
        sessions = R.parse_cba_sessions(read("cba-sessions.html"))
        self.assertEqual(sessions[0][1], "2026-10-07")
        got = {r["expediente"]: r for r in R.parse_cba_session(read("cba-session.html"), "2026-10-07", "u")}
        r = got["47972/L/26"]
        self.assertEqual(r["kind"], "ley")
        self.assertEqual(r["author"], "Gvozdenovich")
        self.assertIn("Asuntos Constitucionales", r["committee"])
        self.assertEqual(got["48034/P/26"]["kind"], "pliego")

    def test_er_sen(self):
        got = R.parse_er_sen(read("er-sen.html"))
        self.assertEqual(len(got), 10)
        first = got[0]
        self.assertEqual(first["bill_key"], "er-sen:34502")
        self.assertEqual(first["presented"], "2026-09-30")
        self.assertIn("Media sanción", first["status"])
        self.assertTrue(any(r["sanctioned"] for r in got))


class Collect(unittest.TestCase):

    def test_weekly_read_stores_every_source(self):
        conn = store()
        gaps, client = collect(conn)
        self.assertEqual(gaps, 0)
        reads = dict(conn.execute("SELECT source, status FROM arp_reads").fetchall())
        self.assertEqual(set(reads), set(R.SOURCES))
        self.assertTrue(all(v == "ok" for v in reads.values()))
        n = dict(conn.execute("SELECT legislature, COUNT(*) FROM arp_bills GROUP BY 1").fetchall())
        self.assertEqual(n["caba"], 4)
        self.assertEqual(n["ba-dip"], 4)
        self.assertEqual(n["er-sen"], 10)
        # Córdoba: only sessions in the last CBA_SESSION_DAYS, each read once
        cba_reads = [u for u in client.asked if "Asuntos.aspx?id=" in u]
        self.assertTrue(cba_reads)
        # the conversion-practices bill is on our ground (area 4)
        areas = json.loads(conn.execute("SELECT areas FROM arp_bills WHERE bill_key='caba:2563-D-2026'").fetchone()[0])
        self.assertIn(4, areas)
        # SAIJ and normas.gba meet on one key per law
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM arp_laws WHERE province='ba'").fetchone()[0], 10)
        # every host's interval was set, and the first read is a seed
        self.assertEqual(client.throttles["www.hcdiputados-ba.gov.ar"], 5.0)
        self.assertEqual(conn.execute("SELECT MIN(seed) FROM arp_bills").fetchone()[0], 1)

    def test_cordoba_sessions_read_once(self):
        conn = store()
        _, first = collect(conn, sources=("cba",))
        _, second = collect(conn, sources=("cba",))
        self.assertTrue([u for u in first.asked if "?id=" in u])
        self.assertEqual([u for u in second.asked if "?id=" in u], [])

    def test_status_change_is_a_stage_move(self):
        conn = store()
        collect(conn, sources=("caba",))
        moved_xml = read("caba.xml").replace("<descripcion>EN COMISION</descripcion>",
                                             "<descripcion>CON DESPACHO</descripcion>", 1)
        self.assertNotEqual(moved_xml, read("caba.xml"))
        later = TODAY + datetime.timedelta(days=7)
        collect(conn, FakeClient(routes(caba=moved_xml)), sources=("caba",), today=later)
        got = conn.execute("SELECT bill_key, moved, prev_status, status, seed FROM arp_bills "
                           "WHERE moved IS NOT NULL").fetchall()
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][1], later.isoformat())
        self.assertTrue(got[0][2].startswith("EN COMISION"))
        self.assertTrue(got[0][3].startswith("CON DESPACHO"))

    def test_watch_key_marks_tier_one(self):
        conn = store()
        collect(conn, watch={"ba-dip:D-3281/26-27": [3]}, sources=("ba-dip",))
        areas, tier = conn.execute("SELECT areas, tier FROM arp_bills WHERE bill_key='ba-dip:D-3281/26-27'").fetchone()
        self.assertEqual(json.loads(areas), [3])
        self.assertEqual(tier, 1)

    def test_failure_is_a_gap_not_fatal(self):
        conn = store()
        bad = FakeClient([("parlamentaria", FetchError("u", R.FEED, "s", 3, "HTTP 500"))] + routes())
        gaps, _ = collect(conn, bad, sources=("caba", "er-sen"))
        self.assertEqual(gaps, 1)
        status = dict(conn.execute("SELECT source, status FROM arp_reads").fetchall())
        self.assertTrue(status["caba"].startswith("failed"))
        self.assertEqual(status["er-sen"], "ok")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed=?", (R.FEED,)).fetchone()[0], 1)

    def test_robots_refusal_is_a_gap(self):
        conn = store()
        client = FakeClient(routes())
        g, _ = guarded(client, {"www.senadoer.gob.ar": "User-agent: *\nDisallow: /buscador-proyectos"}, R.FEED)
        gaps = R.collect(conn, g, TODAY, ("er-sen",), None, {}, log=quiet)
        self.assertEqual(gaps, 1)
        self.assertEqual(client.asked, [])
        self.assertIn("robots.txt", conn.execute("SELECT status FROM arp_reads WHERE source='er-sen'").fetchone()[0])

    def test_reclassify(self):
        conn = store()
        collect(conn, sources=("caba",))
        conn.execute("UPDATE arp_bills SET areas='[]'")
        n = R.reclassify(conn, R.load_taxonomy(), {})
        self.assertGreaterEqual(n, 4)
        areas = json.loads(conn.execute("SELECT areas FROM arp_bills WHERE bill_key='caba:2563-D-2026'").fetchone()[0])
        self.assertIn(4, areas)


class Edition(unittest.TestCase):

    def setUp(self):
        from src.editions import ar
        self.ar = ar
        self.conn = store()
        collect(self.conn)
        self.wl = ce.watchlist_of(ar.COUNTRY)

    def test_section_lists_new_bills_and_coverage(self):
        lines = self.ar.provincial_section(self.conn, "2026-09-28", "2026-10-13", self.wl)
        text = "\n".join(lines)
        self.assertTrue(text.startswith("## Provincial legislatures"))
        self.assertIn("Provincial coverage:", text)
        self.assertIn("SAIJ", text)
        # CABA's bills entered before the window are seeds with their own
        # dates: not new in this window
        self.assertNotIn("caba:2563-D-2026", text)
        self.assertIn("ba-dip:D-3189/26-27", text)      # Ley Micaela, entered 29 September

    def test_seed_bill_shown_by_its_own_date(self):
        text = "\n".join(self.ar.provincial_section(self.conn, "2026-08-01", "2026-10-13", self.wl))
        self.assertIn("caba:2563-D-2026", text)
        self.assertIn("Legislatura de la Ciudad", text)

    def test_post_render_inserts_before_watchlist(self):
        base = "# Edition\n\n_covering 29 September 2026 to 13 October 2026_\n\n## Watchlist\n\n- x\n"
        out = self.ar.post_render(self.conn, self.ar.COUNTRY, "2026-10-13", base, self.wl)
        self.assertLess(out.index("## Provincial legislatures"), out.index("## Watchlist"))
        self.assertLess(out.index("## Nearing lapse"), out.index("## Provincial legislatures"))

    def test_no_provincial_rows_says_not_run(self):
        conn = store()
        lines = self.ar.provincial_coverage(conn, "2026-09-28", "2026-10-13")
        self.assertIn("has not run yet", lines[0])


if __name__ == "__main__":
    unittest.main()
