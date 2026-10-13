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
from unittest import mock

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

    def get_bytes(self, url, feed, slug, **kw):
        body = self._find(url)
        return body.encode("utf-8") if isinstance(body, str) else body


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
        ("web.legisrn.gov.ar", read("rn.html")),
        ("larus.legislaturadelchubut.gob.ar", read("chu.json")),
        ("legislaturajujuy.gov.ar", read("juj.json")),
        ("hcdcorrientes.gov.ar", read("ctes-dip.html")),
        ("siel.diputadossantafe.gov.ar/index.php?go=le", read("sf-dip-state.html")),
        ("siel.diputadossantafe.gov.ar/index.php?i=", "<html></html>"),
        ("siel.diputadossantafe.gov.ar/", read("sf-dip.html")),
        ("senadosalta.gob.ar/wp-json/wp/v2/posts?categories=56,57,58", read("sal-sen-approved.json")),
        ("senadosalta.gob.ar/wp-json/wp/v2/posts", read("sal-sen.json")),
        ("diputadosalta.gob.ar/web/proyectos_aprobados_por_periodo?periodo=2026&tipo=ley", read("sal-dip.html")),
        ("diputadosalta.gob.ar/web/proyectos_aprobados_por_periodo", "<html></html>"),
        ("diputadosalta.gob.ar/web/asuntos_entrados", read("sal-dip-ae.html")),
        ("diputadosalta.gob.ar/documentos_legislativos/2059/", b"2059"),
        ("diputadosalta.gob.ar/documentos_legislativos/2058/", b"2058"),
    ]


def fake_pdf_text(blob):
    """The Asuntos Entrados 'PDFs' of the routes are their document ids; the
    text is pypdf's own output of 13 October 2026 (layout mode)."""
    return read("sal-dip-ae-{0}.txt".format(blob.decode("ascii")))


def collect(conn, client=None, watch=None, sources=R.SOURCES, today=TODAY, robots=None):
    client = client or FakeClient(routes())
    g, _ = guarded(client, robots or {}, R.FEED)
    with mock.patch.object(R, "sal_pdf_text", fake_pdf_text):
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


    def test_rn(self):
        got = R.parse_rn(read("rn.html"))
        self.assertEqual(len(got), 5)
        self.assertEqual(got[0]["bill_key"], "rn:1256/2026")
        self.assertEqual(got[0]["kind"], "declaracion")
        self.assertEqual(got[0]["author"], "SCAVO Roberta")
        self.assertIsNone(got[0]["presented"])       # new by the day first listed
        self.assertTrue(got[0]["url"].startswith("https://web.legisrn.gov.ar/legislativa/proyectos/ver?c=P&n=1256"))

    def test_chu_keeps_no_staff_logins(self):
        got = R.parse_chu(read("chu.json"))
        self.assertEqual(got[0]["bill_key"], "chu:PL120/2026")
        self.assertEqual(got[0]["kind"], "ley")
        self.assertEqual(got[0]["presented"], "2026-10-09")
        self.assertTrue(got[0]["status"].startswith("Comisiones"))
        self.assertNotIn("@", json.dumps(got))

    def test_juj(self):
        got = R.parse_juj(read("juj.json"))
        self.assertEqual(got[0]["bill_key"], "juj:18-CC-26")
        self.assertEqual(got[0]["presented"], "2026-10-01")

    def test_ctes(self):
        got = {r["expediente"]: r for r in R.parse_ctes(read("ctes-dip.html"))}
        self.assertEqual(len(got), 5)
        self.assertEqual(got["20431"]["kind"], "ley")
        self.assertEqual(got["20431"]["author"], "Senadora Ascúa")
        self.assertEqual(got["20459"]["sanctioned"], 1)
        self.assertEqual(got["20459"]["presented"], "2026-09-23")


    def test_sf_dip_list(self):
        got = {r["expediente"]: r for r in R.parse_sf_dip(read("sf-dip.html"))}
        self.assertEqual(len(got), 5)
        r = got["60170"]
        self.assertIn("LEY JOHANNA", r["title"])
        self.assertNotIn("BLOQUE", r["title"])            # the bloc goes to the author
        self.assertEqual(r["author"], "BROUWER, Beatriz Ana (BLOQUE UNITE POR SANTA FE)")
        self.assertEqual(r["kind"], "ley")
        self.assertEqual(r["status"], "En Carátula")
        self.assertEqual(r["presented"], "2026-10-09")
        self.assertEqual(r["url"], "https://siel.diputadossantafe.gov.ar/index.php?go=d&id=60132")
        self.assertEqual(got["60174"]["kind"], "declaracion")
        self.assertFalse(r["stage"])
        # a bloc printed without the word BLOQUE still goes to the author
        page = read("sf-dip.html").replace("*BLOQUE UNITE POR SANTA FE*", "*COMPROMISO JUSTICIALISTA*")
        r = next(x for x in R.parse_sf_dip(page) if x["expediente"] == "60170")
        self.assertTrue(r["title"].endswith("PERINATAL)"))
        self.assertEqual(r["author"], "BROUWER, Beatriz Ana (COMPROMISO JUSTICIALISTA)")

    def test_sf_dip_state_list_has_the_extra_column(self):
        # the search results show the 'Pasada' column the list hides in a comment
        got = {r["expediente"]: r for r in R.parse_sf_dip(read("sf-dip-state.html"), stage=True)}
        self.assertEqual(set(got), {"59497", "59163", "58516"})
        self.assertEqual(got["59497"]["status"], "1/2 Sanción")
        self.assertTrue(got["59497"]["title"].startswith("VENIDO EN REVISIÓN"))
        self.assertEqual(got["58516"]["status"], "1/2 Sanción (Ley 14486)")
        self.assertTrue(all(r["stage"] for r in got.values()))
        self.assertEqual(R.sf_search_fields("11")["estado"], "11")

    def test_sal_sen(self):
        got = {r["expediente"]: r for r in R.parse_sal_sen(read("sal-sen.json"))}
        self.assertEqual(len(got), 9)
        r = got["90-34699/2026"]
        self.assertEqual(r["bill_key"], "sal-sen:90-34699/2026")
        self.assertEqual(r["kind"], "declaracion")
        self.assertEqual(r["status"], "En trámite")
        self.assertEqual(r["presented"], "2026-10-08")
        self.assertEqual(r["author"], "ESTEBAN D’ANDREA CORNEJO, EDGARDO GONZALO GUAYMAS, JOSÉ ROLANDO GUAIMÁS")
        self.assertTrue(r["title"].startswith("Medidas de asistencia económica"))
        self.assertIn("90-34648/2026", got)               # 'Expte.N°90-...' with no spaces
        self.assertEqual(got["91-54649/2026"]["status"], "Aprobado")
        self.assertEqual(got["91-54649/2026"]["author"], "Cámara de Diputados")
        self.assertEqual(got["91-54649/2026"]["sanctioned"], 0)      # a law: chamber approval only
        self.assertEqual(got["90-34684/2026"]["sanctioned"], 1)      # a resolution: final

    def test_sal_dip(self):
        got = R.parse_sal_dip(read("sal-dip.html"), "ley")
        self.assertEqual(len(got), 5)
        self.assertEqual(got[0]["bill_key"], "sal-dip:91-52092/25")
        self.assertEqual(got[0]["presented"], "2025-04-03")
        self.assertEqual(got[0]["status"], "Aprobado")
        self.assertEqual(got[0]["url"], "https://www.diputadosalta.gob.ar/web/expediente/67938")
        self.assertTrue(all(r["stage"] for r in got))


class SantaFeRobots(unittest.TestCase):
    """SIEL's robots.txt names AI agents and has no '*' group (13 October
    2026). Our collector's user agent is allowed; the reader stops the
    moment any rule covers our user agent."""

    def run_sf(self, robots_txt):
        conn = store()
        client = FakeClient(routes())
        g, _ = guarded(client, {"siel.diputadossantafe.gov.ar": robots_txt}, R.FEED)
        gaps = R.collect(conn, g, TODAY, ("sf-dip",), R.load_taxonomy(), {}, log=quiet)
        return conn, client, gaps

    def test_live_robots_allows_our_agent(self):
        conn, client, gaps = self.run_sf(read("siel-robots.txt"))
        self.assertEqual(gaps, 0)
        self.assertIn("User-agent: ClaudeBot", read("siel-robots.txt"))
        self.assertTrue(any("siel.diputadossantafe" in u for u in client.asked))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM arp_bills WHERE legislature='sf-dip'").fetchone()[0], 8)

    def test_wildcard_disallow_anywhere_stops_siel(self):
        # even a rule for a path we never ask for: a rule now covers us
        txt = read("siel-robots.txt") + "\nUser-agent: *\nDisallow: /privado/\n"
        conn, client, gaps = self.run_sf(txt)
        self.assertEqual(gaps, 1)
        self.assertEqual(client.asked, [])
        status = conn.execute("SELECT status FROM arp_reads WHERE source='sf-dip'").fetchone()[0]
        self.assertIn("covering our user agent", status)

    def test_our_name_stops_siel(self):
        txt = read("siel-robots.txt") + "\nUser-agent: CitizenGO-ParlMonitor\nDisallow: /\n"
        _, client, gaps = self.run_sf(txt)
        self.assertEqual(gaps, 1)
        self.assertEqual(client.asked, [])

    def test_unreachable_robots_stops_siel(self):
        _, client, gaps = self.run_sf(503)
        self.assertGreaterEqual(gaps, 1)
        self.assertEqual(client.asked, [])

    def test_unguarded_client_never_reads_siel(self):
        conn = store()
        client = FakeClient(routes())
        gaps = R.collect(conn, client, TODAY, ("sf-dip",), None, {}, log=quiet)
        self.assertEqual(gaps, 1)
        self.assertEqual(client.asked, [])


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
        self.assertEqual(n["rn"], 5)
        self.assertEqual(n["chu"], 4)
        self.assertEqual(n["juj"], 4)
        self.assertEqual(n["ctes-dip"], 5)
        self.assertEqual(n["sf-dip"], 8)        # five new, three from the media-sanción list
        self.assertEqual(n["sal-sen"], 12)
        self.assertEqual(n["sal-dip"], 109)     # 5 approved, 104 from two Asuntos Entrados
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

    def test_first_sight_in_a_stage_list_is_a_move(self):
        conn = store()
        collect(conn, sources=("sal-dip",))                 # first read: seeds, no moves
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM arp_bills WHERE moved IS NOT NULL").fetchone()[0], 0)
        extra = read("sal-dip.html").replace("91-52092/25", "91-59999/26")
        later = TODAY + datetime.timedelta(days=7)
        client = FakeClient([("tipo=ley", extra), ("diputadosalta.gob.ar", "<html></html>")])
        collect(conn, client, sources=("sal-dip",), today=later)
        got = conn.execute("SELECT moved, status, seed FROM arp_bills WHERE bill_key='sal-dip:91-59999/26'").fetchone()
        self.assertEqual(tuple(got), (later.isoformat(), "Aprobado", 0))

    def test_salta_senate_approval_is_a_stage_move(self):
        conn = store()
        moved = read("sal-sen.json").replace('"categories": [\n52\n]', '"categories": [\n58\n]', 1)
        collect(conn, sources=("sal-sen",))
        self.assertNotEqual(moved, read("sal-sen.json"))
        later = TODAY + datetime.timedelta(days=7)
        client = FakeClient([("categories=56,57,58", "[]"), ("senadosalta.gob.ar", moved)])
        collect(conn, client, sources=("sal-sen",), today=later)
        got = conn.execute("SELECT prev_status, status, moved FROM arp_bills WHERE moved IS NOT NULL").fetchall()
        self.assertEqual([tuple(r) for r in got], [("En trámite", "Aprobado", later.isoformat())])

    def test_watch_key_marks_tier_one(self):
        conn = store()
        collect(conn, watch={"ba-dip:D-3281/26-27": [3]}, sources=("ba-dip",))
        areas, tier = conn.execute("SELECT areas, tier FROM arp_bills WHERE bill_key='ba-dip:D-3281/26-27'").fetchone()
        # area 1 from taxonomy-es v0.4's "salud sexual" (Argentina): the bill
        # is the adhesion to World Sexual Health Day; area 3 from the watch key
        self.assertEqual(json.loads(areas), [1, 3])
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

    def test_salta_intake_in_coverage_and_the_patron_saint_left_out(self):
        text = "\n".join(self.ar.provincial_section(self.conn, "2026-08-01", "2026-10-13", self.wl))
        self.assertIn("Asuntos Entrados PDFs (read 13 Oct", text)
        # 'nonato*' in San Ramón Nonato's feast day: the noise rule drops it
        self.assertNotIn("sal-dip:91-54567/26", text)
        kept, dropped = self.ar.provincial_items(self.conn, "2026-08-01", "2026-10-13", self.wl)
        self.assertIn("sal-dip:91-54567/26", [it["key"] for it in dropped])

    def test_no_provincial_rows_says_not_run(self):
        conn = store()
        lines = self.ar.provincial_coverage(conn, "2026-09-28", "2026-10-13")
        self.assertIn("has not run yet", lines[0])


class SaltaAsuntosEntrados(unittest.TestCase):
    """Salta Diputados' intake (13 October 2026): the Asuntos Entrados index
    and two sittings' PDFs as pypdf read them (tests/fixtures/ar_regions/
    sal-dip-ae-2059.txt and -2058.txt, layout mode)."""

    def test_index(self):
        got = R.parse_sal_ae_index(read("sal-dip-ae.html"))
        self.assertEqual(len(got), 4)
        self.assertEqual(got[0], ("2059", "2026-08-25",
                                  "https://www.diputadosalta.gob.ar/documentos_legislativos/2059/download_file"))
        self.assertEqual([d[0] for d in got], ["2059", "2058", "2057", "2042"])

    def test_sitting_of_25_august(self):
        rows = R.parse_sal_ae(read("sal-dip-ae-2059.txt"), None, "u")
        self.assertEqual(len(rows), 64)
        self.assertEqual(len({r["bill_key"] for r in rows}), 64)
        first = rows[0]
        self.assertEqual(first["bill_key"], "sal-dip:91-54525/26")
        self.assertEqual(first["kind"], "ley")
        self.assertEqual(first["presented"], "2026-08-25")         # from the PDF's own header
        self.assertTrue(first["title"].startswith("Programa Provincial de Erradicación Progresiva"))
        self.assertEqual(first["author"], "CARTUCCIA, Laura D")
        self.assertTrue(first["committee"].startswith("de Asuntos Municipales y Transporte"))
        self.assertFalse(first["stage"])
        kinds = {r["expediente"]: r["kind"] for r in rows}
        self.assertEqual(kinds["91-54553/26"], "ley")              # VIH adhesion, section III
        self.assertEqual(kinds["91-54523/26"], "resolucion")
        self.assertEqual(kinds["91-54580/26"], "resolucion")       # documentation, kind inline
        self.assertEqual(kinds["91-54583/26"], "proyecto")         # added during the sitting
        # the official notes ('Expte. 91 -54.162/26 - Cde.') are not projects
        self.assertNotIn("91-54162/26", kinds)
        archived = {r["expediente"]: r["status"] for r in rows}
        self.assertEqual(archived["91-54523/26"], "Entrado y archivado")
        self.assertEqual(archived["91-54525/26"], "Entrado")

    def test_sitting_of_11_august(self):
        rows = {r["expediente"]: r for r in R.parse_sal_ae(read("sal-dip-ae-2058.txt"), "2026-08-11", "u")}
        self.assertEqual(len(rows), 40)
        self.assertEqual(rows["90-34083/25"]["kind"], "ley")       # a Senate bill in revision
        self.assertEqual(rows["91-54522/26"]["kind"], "ley")       # under 'Proyecto de Ley'
        self.assertEqual(rows["91-54519/26"]["kind"], "declaracion")
        self.assertNotIn("91-54263/26", rows)                     # a committee report ('Exptes.')
        self.assertTrue(all(r["presented"] == "2026-08-11" for r in rows.values()))

    def test_blank_pdf_has_no_projects(self):
        import io
        import pypdf
        w = pypdf.PdfWriter()
        w.add_blank_page(width=595, height=842)
        buf = io.BytesIO()
        w.write(buf)
        self.assertEqual(R.parse_sal_ae(R.sal_pdf_text(buf.getvalue())), [])
        with self.assertRaises(ValueError):
            R.sal_pdf_text(b"not a pdf")

    def test_first_read_takes_the_newest_sittings_and_marks_the_rest(self):
        conn = store()
        gaps, client = collect(conn, sources=("sal-dip", "sal-dip-ae"))
        self.assertEqual(gaps, 0)
        pdfs = [u for u in client.asked if "documentos_legislativos" in u]
        self.assertEqual(len(pdfs), R.SAL_AE_PDFS)
        n = conn.execute("SELECT COUNT(*) FROM arp_bills WHERE legislature='sal-dip' AND status LIKE "
                         "'Entrado%'").fetchone()[0]
        self.assertEqual(n, 104)
        self.assertEqual(conn.execute("SELECT MIN(seed) FROM arp_bills WHERE status LIKE 'Entrado%'")
                         .fetchone()[0], 1)
        cursor = json.loads(conn.execute("SELECT cursor FROM arp_reads WHERE source='sal-dip-ae'").fetchone()[0])
        self.assertEqual(set(cursor), {"2059", "2058", "2057", "2042"})
        # the second week asks the index only
        _, again = collect(conn, sources=("sal-dip-ae",))
        self.assertEqual([u for u in again.asked if "documentos_legislativos" in u], [])

    def test_new_sitting_is_read_and_an_approval_is_not_overwritten(self):
        conn = store()
        collect(conn, sources=("sal-dip", "sal-dip-ae"))
        # a week later: a new sitting (2060) lists a project the approved list
        # already holds, and one more
        index = read("sal-dip-ae.html").replace(
            "<tbody>", '<tbody>\n<tr><td><a href="/documentos_legislativos/2060/download_file">'
            'Asuntos Entrados</a></td><td>01/09/2026</td></tr>', 1)
        text = read("sal-dip-ae-2058.txt").replace("91-54489/26", "91-52092/25").replace(
            "91-54491/26", "91-55555/26")
        later = TODAY + datetime.timedelta(days=7)
        client = FakeClient([("asuntos_entrados", index), ("documentos_legislativos/2060/", b"2060")])
        g, _ = guarded(client, {}, R.FEED)
        with mock.patch.object(R, "sal_pdf_text", lambda blob: text):
            gaps = R.collect(conn, g, later, ("sal-dip-ae",), R.load_taxonomy(), {}, log=quiet)
        self.assertEqual(gaps, 0)
        self.assertEqual([u for u in client.asked if "documentos_legislativos" in u],
                         ["https://www.diputadosalta.gob.ar/documentos_legislativos/2060/download_file"])
        approved = conn.execute("SELECT status, moved FROM arp_bills WHERE bill_key='sal-dip:91-52092/25'").fetchone()
        self.assertEqual(approved[0], "Aprobado")
        fresh = conn.execute("SELECT status, seed, presented, first_seen FROM arp_bills "
                             "WHERE bill_key='sal-dip:91-55555/26'").fetchone()
        self.assertEqual(tuple(fresh), ("Entrado", 0, "2026-09-01", later.isoformat()))

    def test_unreadable_pdf_is_a_gap_and_the_other_is_read(self):
        conn = store()
        bad = [("documentos_legislativos/2059/", FetchError("u", R.FEED, "s", 3, "HTTP 500"))] + routes()
        gaps, _ = collect(conn, FakeClient(bad), sources=("sal-dip-ae",))
        self.assertEqual(gaps, 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM arp_bills").fetchone()[0], 40)
        self.assertEqual(conn.execute("SELECT status FROM arp_reads WHERE source='sal-dip-ae'").fetchone()[0], "ok")

    def test_robots_refusal_reads_no_pdf(self):
        conn = store()
        robots = {"www.diputadosalta.gob.ar": "User-agent: *\nDisallow: /documentos_legislativos/"}
        gaps, client = collect(conn, sources=("sal-dip-ae",), robots=robots)
        self.assertEqual(gaps, 1)
        self.assertEqual([u for u in client.asked if "documentos_legislativos" in u], [])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM arp_bills").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
