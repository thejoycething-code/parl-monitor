"""PE4 (12 October 2026): Peru's regional governments and Lima Metropolitana,
tools/pe_regions.py, the Latam adapter (src/latam.items_pe_regional) and
the edition's regional sub-heading, on real replies trimmed into
tests/fixtures/pe_regions/ (no network)."""

import datetime
import importlib.util
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, latam  # noqa: E402
from src.http import FetchError  # noqa: E402
from tests.robots_fakes import guarded  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "pe_regions")
TODAY = datetime.date(2026, 10, 12)


def tool(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


P = tool("pe_regions")


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
        self.forms = []

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
        self.forms.append(fields)
        return self._find(url)


AREQUIPA = [{"key": "arequipa", "name": "Arequipa", "gobpe": "regionarequipa",
             "types": ["40-ordenanza-regional"], "gazette": ["GOBIERNO REGIONAL DE AREQUIPA"]}]


def quiet(*a, **k):
    pass


def collect(conn, watch=None, gobpe=True):
    regions = P.load_regions()
    index = P.gazette_index(regions)
    tax = P.load_taxonomy()
    client = FakeClient([("Normas/Filtro", read("gazette.html")),
                         ("regionarequipa/normas-legales/tipos/40", read("gobpe_arequipa_ordenanzas.html"))])
    got = P.pull_gazette(conn, client, TODAY, TODAY - datetime.timedelta(days=14), tax,
                         watch or {}, index, log=quiet)
    if gobpe:
        P.pull_gobpe(conn, client, TODAY, tax, watch or {}, AREQUIPA, log=quiet)
    return got, client


def row(conn, key):
    cur = conn.execute("SELECT * FROM pe_regional_norms WHERE norm_key=?", (key,))
    r = cur.fetchone()
    return dict(zip([d[0] for d in cur.description], r)) if r else None


class RegionsConfigTests(unittest.TestCase):
    def test_twenty_five_regions_and_lima(self):
        regs = P.load_regions()
        self.assertEqual(len(regs), 26)
        self.assertEqual(len({r["key"] for r in regs}), 26)
        self.assertEqual(len({r["gobpe"] for r in regs}), 26)
        self.assertIn("lima-metropolitana", {r["key"] for r in regs})
        for r in regs:
            self.assertTrue(r["types"], r["key"])
            self.assertTrue(all("ordenanza" in t or "acuerdo" in t for t in r["types"]), r["key"])

    def test_headings_fold_and_drop_the_digital_tail(self):
        idx = P.gazette_index(P.load_regions())
        self.assertEqual(P.region_of("GOBIERNO REGIONAL DE JUNÍN", idx), "junin")
        self.assertEqual(P.region_of("GOBIERNO REGIONAL DEL CUSCO", idx), "cusco")
        self.assertEqual(P.region_of("MUNICIPALIDAD METROPOLITANA DE LIMA <br />Publicación Digital",
                                     idx), "lima-metropolitana")
        self.assertEqual(P.region_of("GOBIERNO REGIONAL DE LIMA", idx), "lima")
        self.assertIsNone(P.region_of("MUNICIPALIDAD DE SAN BORJA", idx))
        self.assertIsNone(P.region_of("CULTURA", idx))


class NumberTests(unittest.TestCase):
    def test_reduced_numbers_meet_across_sources(self):
        self.assertEqual(P.reduced("000013-2026-GR.LAMB/CR", "2026-09-10"), "13-2026")
        self.assertEqual(P.reduced("0013-2026-GR.LAMB/CR", "2026-09-01"), "13-2026")
        self.assertEqual(P.reduced("O.R.0272.2025", "2025-07-01"), "272-2025")
        self.assertEqual(P.reduced("562-AREQUIPA", "2026-10-08"), "562-2026")
        self.assertEqual(P.reduced("D9-2026-GR.CAJ/CR", "2026-10-03"), "9-2026")
        self.assertEqual(P.reduced("2883 - 2026/GRP-CR", "2026-10-01"), "2883-2026")
        # A typed letter O in the year: the date's year stands in.
        self.assertEqual(P.reduced("017 - 2O26-RMDD/CR", "2026-09-21"), "17-2026")
        self.assertIsNone(P.reduced("sin número", "2026-01-01"))

    def test_number_and_kind_from_the_heading(self):
        t = "ORDENANZA  N° 000013-2026-GR.LAMB/CR [516296499 - 11]"
        self.assertEqual(P.number_of(t), "000013-2026-GR.LAMB/CR")
        self.assertEqual(P.kind_of(t), "ordenanza")
        self.assertEqual(P.kind_of("RESOLUCIÓN DIRECTORAL N° 126"), "resolucion")
        self.assertEqual(P.kind_of("Decretos de Alcaldía N° 010"), "decreto")
        self.assertEqual(P.kind_of("FE DE ERRATAS"), "otro")


class ParseTests(unittest.TestCase):
    def test_gazette_keeps_regions_and_lima_only(self):
        rows = P.parse_gazette(read("gazette.html"), P.gazette_index(P.load_regions()))
        keys = [r["norm_key"] for r in rows]
        self.assertEqual(keys, ["arequipa/ordenanza/561-2026", "junin/ordenanza/433-2026",
                                "madre-de-dios/acuerdo/98-2026", "pasco/resolucion/299-2026",
                                "lima-metropolitana/ordenanza/2859-2026",
                                "lima-metropolitana/decreto/10-2026"])
        a = rows[0]
        self.assertEqual(a["date"], "2026-10-01")
        self.assertEqual(a["number"], "561-AREQUIPA")
        self.assertEqual(a["body"], "GOBIERNO REGIONAL DE AREQUIPA")
        self.assertTrue(a["url"].startswith("https://busquedas.elperuano.pe/dispositivo/NL/"))
        self.assertIn("matrimonios y las uniones infantiles", a["summary"])
        lima = rows[4]
        self.assertEqual(lima["body"], "MUNICIPALIDAD METROPOLITANA DE LIMA")
        self.assertNotIn("[", lima["title"])

    def test_gobpe_rows(self):
        rows = P.parse_gobpe(read("gobpe_arequipa_ordenanzas.html"), "arequipa", "40-ordenanza-regional")
        self.assertEqual([r["norm_key"] for r in rows],
                         ["arequipa/ordenanza/562-2026", "arequipa/ordenanza/561-2026",
                          "arequipa/ordenanza/538-2025"])
        self.assertTrue(all(r["pdf_url"].startswith("https://cdn.www.gob.pe/") for r in rows))
        self.assertTrue(rows[0]["url"].startswith("https://www.gob.pe/institucion/regionarequipa/"))
        self.assertEqual(rows[2]["date"], "2025-07-31")

    def test_form_fields_are_day_first(self):
        f = P.gazette_fields(datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        self.assertEqual((f["cddesde"], f["cdhasta"]), ("01/09/2026", "30/09/2026"))
        self.assertIn("dateparam=10%2F12%2F2026", P.gazette_url(TODAY))


class StoreTests(unittest.TestCase):
    def test_two_sources_meet_on_one_row(self):
        conn = store()
        (read_n, new, ours, gaps), client = collect(conn)
        self.assertEqual((read_n, new, gaps), (6, 6, 0))
        self.assertEqual(client.throttles[P.GAZETTE_HOST], P.GAZETTE_DELAY_S)
        self.assertEqual(client.throttles[P.GOBPE_HOST], P.GOBPE_DELAY_S)
        r = row(conn, "arequipa/ordenanza/561-2026")
        self.assertEqual(r["source"], "elperuano+gob.pe")
        self.assertEqual(r["date"], "2026-10-01")             # the gazette's date wins
        self.assertIn("elperuano.pe", r["url"])
        self.assertIn("Créase", r["summary"])                  # the longer sumilla wins
        self.assertEqual(json.loads(r["areas"]), [9])
        esi = row(conn, "arequipa/ordenanza/538-2025")
        self.assertEqual(esi["source"], "gob.pe")
        self.assertEqual(json.loads(esi["areas"]), [6])
        self.assertEqual(esi["tier"], 1)
        n = conn.execute("SELECT COUNT(*) FROM pe_regional_norms").fetchone()[0]
        self.assertEqual(n, 8)

    def test_watchlist_by_key(self):
        conn = store()
        collect(conn, watch={"junin/ordenanza/433-2026": [8]}, gobpe=False)
        r = row(conn, "junin/ordenanza/433-2026")
        self.assertEqual(json.loads(r["areas"]), [8])
        self.assertEqual(r["tier"], 1)

    def test_gazette_refusal_is_a_gap(self):
        conn = store()
        client = FakeClient([("Normas/Filtro", FetchError("u", "f", "s", 1, OSError("refused")))])
        got = P.pull_gazette(conn, client, TODAY, TODAY, None, {}, {}, log=quiet)
        self.assertEqual(got, (0, 0, 0, 1))
        gaps = conn.execute("SELECT detail FROM gaps WHERE feed='pe-regions'").fetchall()
        self.assertEqual(len(gaps), 1)

    def test_gobpe_budget_stops_with_a_gap(self):
        conn = store()
        client = FakeClient([])
        got = P.pull_gobpe(conn, client, TODAY, None, {}, AREQUIPA, deadline=0, log=quiet)
        self.assertEqual(got[3], 1)
        self.assertEqual(client.asked, [])

    def test_reclassify(self):
        conn = store()
        collect(conn)
        self.assertEqual(P.reclassify(conn, P.load_taxonomy(), {}), 8)


class LatamTests(unittest.TestCase):
    def setUp(self):
        latam._WATCH.clear()

    def test_regional_items_in_the_peru_section(self):
        conn = store()
        collect(conn)
        # The first run seeds: rows first seen today count by their own date.
        items = latam.country_items(conn, "pe", "2026-09-12", "2026-10-12", ledger={})
        keys = [it["key"] for it in items if it["kind"] == "regional"]
        self.assertEqual(keys, ["arequipa/ordenanza/561-2026"])
        it = items[0]
        self.assertEqual(it["areas"], [9])
        self.assertIn("Gobierno Regional de Arequipa", it["lines"][0])
        self.assertIn("published in El Peruano, also on gob.pe", it["lines"][0])
        # The ESI ordinance of July 2025 is seed, not news.
        self.assertNotIn("arequipa/ordenanza/538-2025", keys)

    def test_a_late_listing_after_the_seed_is_news(self):
        conn = store()
        collect(conn)
        conn.execute("UPDATE pe_regional_norms SET first_seen='2026-10-01' "
                     "WHERE norm_key != 'arequipa/ordenanza/562-2026'")
        conn.execute("UPDATE pe_regional_norms SET date='2026-08-20', first_seen='2026-10-11' "
                     "WHERE norm_key='arequipa/ordenanza/538-2025'")
        items = latam.items_pe_regional(conn, "2026-10-05", "2026-10-12", {})
        self.assertIn("arequipa/ordenanza/538-2025", [it["key"] for it in items])

    def test_resoluciones_are_never_shown(self):
        conn = store()
        collect(conn, watch={"pasco/resolucion/299-2026": [9]}, gobpe=False)
        items = latam.items_pe_regional(conn, "2026-09-12", "2026-10-12",
                                        {"pasco/resolucion/299-2026": {}})
        self.assertEqual([it["key"] for it in items if "pasco" in it["key"]], [])

    def test_tourist_interest_is_filtered(self):
        from src import latam_noise
        it = latam.item("pe", "regional", "pasco/acuerdo/91-2026", "2026-10-01",
                        "DECLARAR de Interés Turístico Regional la Iglesia Colonial", [8], 2)
        kept, out = latam_noise.split([it])
        self.assertEqual(kept, [])

    def test_edition_sub_heading_and_coverage(self):
        lm = tool("latam_monitor")
        conn = store()
        collect(conn)
        text = lm.render_edition(conn, "2026-10-12", since="2026-09-11", ledger={})
        self.assertIn("## Peru", text)
        self.assertIn("### Regional governments and Lima Metropolitana", text)
        self.assertIn("arequipa/ordenanza/561-2026", text)
        self.assertIn("1 regional norm", text)
        self.assertIn("**Peru's regions** (PE4)", text)
        self.assertNotIn("—", text)


class RobotsAtRunTime(unittest.TestCase):
    """robots.txt is asked on every run, per host, before any request
    (src/robots_guard), not only when the collector was built."""

    def client(self, robots):
        inner = FakeClient([("Normas/Filtro", read("gazette.html")),
                            ("regionarequipa/normas-legales/tipos/40",
                             read("gobpe_arequipa_ordenanzas.html"))])
        client, serving = guarded(inner, robots, P.FEED)
        return client, inner, serving

    def gaps(self, conn):
        return [r[0] for r in conn.execute("SELECT detail FROM gaps WHERE feed='pe-regions'")]

    def test_a_disallowed_path_is_skipped_with_a_gap(self):
        conn = store()
        client, inner, serving = self.client(
            {P.GOBPE_HOST: read("../robots/gobpe-disallow-arequipa.txt")})
        got = P.pull_gobpe(conn, client, TODAY, P.load_taxonomy(), {}, AREQUIPA, log=quiet)
        self.assertEqual(got, (0, 0, 0, 1))
        self.assertEqual(inner.asked, [])
        self.assertIn("robots.txt disallows", self.gaps(conn)[0])
        self.assertEqual(serving.host_throttles[P.GOBPE_HOST], 4.0)   # Crawl-delay above ours

    def test_a_503_robots_txt_skips_the_host(self):
        conn = store()
        client, inner, _ = self.client({P.GAZETTE_HOST: 503, P.GOBPE_HOST: 503})
        got = P.pull_gazette(conn, client, TODAY, TODAY, None, {}, {}, log=quiet)
        self.assertEqual(got, (0, 0, 0, 1))
        two = AREQUIPA + [dict(AREQUIPA[0], key="cusco", gobpe="regioncusco")]
        got = P.pull_gobpe(conn, client, TODAY, None, {}, two, log=quiet)
        self.assertEqual(got[3], 1)          # one gap for the host, not one per region
        self.assertEqual(inner.asked, [])
        self.assertEqual(inner.forms, [])
        gaps = self.gaps(conn)
        self.assertEqual(len(gaps), 2)
        self.assertTrue(all("unreachable (503)" in g for g in gaps))

    def test_a_404_robots_txt_allows(self):
        conn = store()
        client, inner, serving = self.client({})
        regions = P.load_regions()
        got = P.pull_gazette(conn, client, TODAY, TODAY - datetime.timedelta(days=14),
                             P.load_taxonomy(), {}, P.gazette_index(regions), log=quiet)
        self.assertGreater(got[0], 0)
        self.assertEqual(got[3], 0)
        P.pull_gobpe(conn, client, TODAY, P.load_taxonomy(), {}, AREQUIPA, log=quiet)
        self.assertEqual(sorted(serving.robots_asked), sorted([P.GAZETTE_HOST, P.GOBPE_HOST]))
        self.assertEqual(self.gaps(conn), [])


if __name__ == "__main__":
    unittest.main()
