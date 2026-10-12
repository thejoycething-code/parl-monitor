"""Uruguay: the Cámara de Representantes' open-data files and IMPO's laws
(tools/uy_rollcalls.py). No network: real responses saved on 9 October 2026
under tests/fixtures/uy/ (the Cámara's files trimmed to a few records)."""

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, uy_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "uy")


def _load():
    spec = importlib.util.spec_from_file_location(
        "uy_rollcalls", os.path.join(ROOT, "tools", "uy_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


uyr = _load()


def fixture(name):
    with open(os.path.join(FIX, name), "rb") as fh:
        return fh.read()


def store():
    conn = sqlite3.connect(":memory:")
    db.init_db(conn)
    return conn


TINY_TAXONOMY = """version: test
areas:
  1_abortion:
    tier1: ["interrupción voluntaria del embarazo"]
    tier2: []
  2_assisted_dying:
    tier1: ["eutanasia*", "muerte digna"]
    tier2: []
  8_freedom_of_religion:
    tier1: [laicidad]
    tier2: []
exclusions_global: [vida]
"""


def tiny_taxonomy():
    fd, path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(TINY_TAXONOMY)
    try:
        return uyr.load_taxonomy(path)
    finally:
        os.unlink(path)


def http_404(url):
    return FetchError(url, "uy", "x", 1, urllib.error.HTTPError(url, 404, "Not Found", {}, None))


class FakeClient:
    """Serves fixtures by URL. A law address not listed answers like IMPO
    does for a wrong year (200, HTML); `missing` addresses answer 404;
    `fail` addresses fail outright."""

    def __init__(self, files=None, missing=(), fail=()):
        self.files, self.missing, self.fail = files or {}, set(missing), set(fail)
        self.asked, self.archived, self.throttles = [], [], {}

    def get_bytes(self, url, feed, slug, archive=True, **kw):
        self.asked.append(url)
        if url in self.fail:
            raise FetchError(url, feed, slug, 4, "refused")
        if url in self.missing:
            raise http_404(url)
        if url in self.files:
            return self.files[url]
        if "/bases/leyes/" in url:
            return fixture("law-20531-2026-wrong.html")
        raise FetchError(url, feed, slug, 1, "not in fixtures")

    def _archive(self, raw, feed, slug):
        self.archived.append(slug)

    def set_host_throttle(self, host, seconds):
        self.throttles[host] = seconds


def law_url(n, y):
    return uyr.LAW_URL.format(n=n, y=y) + "?json=true"


CAMARA = {
    uyr.MEMBERS_URL: fixture("DAdiputadosNomina2.json"),
    uyr.QUESTIONS_URL: fixture("DApedidosInformes.json"),
    uyr.SITTINGS_URL: fixture("DAdiarioSesiones.json"),
}


class HelperTests(unittest.TestCase):
    def test_dates_in_every_shape_the_files_use(self):
        self.assertEqual(uyr.iso_date("2026/07/14"), "2026-07-14")
        self.assertEqual(uyr.iso_date("24/10/2025"), "2025-10-24")
        self.assertEqual(uyr.iso_date(1394496000000), "2014-03-11")
        self.assertIsNone(uyr.iso_date(""))
        self.assertIsNone(uyr.iso_date("pronto"))

    def test_question_key_is_the_oficio_number(self):
        self.assertEqual(uyr.question_key(
            "https://documentos.diputados.gub.uy/docs/L50/Oficio/01105.pdf"), "L50/01105")
        self.assertIsNone(uyr.question_key("https://example.org/x.pdf"))

    def test_deaccent_folds_capitals_and_enye(self):
        self.assertEqual(uyr.deaccent("INTERRUPCIÓN Niñez género"), "INTERRUPCION Ninez genero")


class ParserTests(unittest.TestCase):
    def test_members_strip_the_padding_and_keep_the_ballot_as_text(self):
        members = uyr.parse_members(json.loads(fixture("DAdiputadosNomina2.json")))
        self.assertEqual(len(members), 5)
        first = members[0]
        self.assertEqual(first["name"], "ABBONDANZA MENDARO, FLORENCIA")
        self.assertEqual(first["party"], "Frente Amplio")
        self.assertEqual(first["hoja"], "1001")

    def test_questions(self):
        qs = uyr.parse_questions(json.loads(fixture("DApedidosInformes.json")))
        self.assertEqual(len(qs), 7)
        self.assertTrue(all(q["question_key"].startswith("L50/") for q in qs))
        self.assertTrue(all(q["legislature"] == 50 for q in qs))
        self.assertTrue(all(len(q["date"]) == 10 for q in qs))
        self.assertTrue(any("INTERRUPCIÓN VOLUNTARIA" in q["tema"] for q in qs))

    def test_sittings_read_both_date_shapes(self):
        ss = uyr.parse_sittings(json.loads(fixture("DAdiarioSesiones.json")))
        by = {s["diario"]: s for s in ss}
        self.assertEqual(by[4578]["date"], "2025-08-12")       # the euthanasia sitting
        self.assertEqual(by[4578]["sesion_tipo"], "EXT")
        self.assertTrue(by[4578]["url"].endswith("d4578.pdf"))
        self.assertEqual(by[3911]["date"], "2014-03-11")       # epoch milliseconds

    def test_law_json_is_latin1_with_raw_newlines(self):
        law = uyr.parse_law(fixture("law-20431-2025.json"))
        self.assertEqual(law["law_number"], 20431)
        self.assertEqual(law["year"], 2025)
        self.assertEqual(law["name"], "LEY DE MUERTE DIGNA; EUTANASIA")
        self.assertEqual(law["promulgated"], "2025-10-24")
        self.assertEqual(law["published"], "2025-11-05")
        self.assertEqual(law["articles"], 13)
        self.assertTrue(law["text"].startswith("(Objeto).- La presente ley"))
        self.assertIn("se le practique la eutanasia", law["text"])
        # Cut at TEXT_CHARS: the commission (article 11) is past the cut.
        self.assertEqual(len(law["text"]), uyr.TEXT_CHARS)

    def test_a_wrong_year_page_is_not_a_law(self):
        self.assertIsNone(uyr.parse_law(fixture("law-20531-2026-wrong.html")))
        self.assertIsNone(uyr.parse_law(b"{not json"))


class PullTests(unittest.TestCase):
    def test_camara_files_stored_unclassified_without_a_taxonomy(self):
        conn = store()
        client = FakeClient(CAMARA)
        self.assertEqual(uyr.pull_members(conn, client, "2026-10-09"), (5, 0))
        self.assertEqual(uyr.pull_questions(conn, client, "2026-10-09"), (7, 0, 0))
        self.assertEqual(uyr.pull_sittings(conn, client, "2026-10-09"), (3, 0))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM uy_questions WHERE areas IS NULL")
                         .fetchone()[0], 7)
        # Re-reading the same files updates in place.
        uyr.pull_members(conn, client, "2026-10-16")
        self.assertEqual(conn.execute("SELECT COUNT(*), MIN(first_seen), MAX(last_seen) "
                                      "FROM uy_members").fetchone(),
                         (5, "2026-10-09", "2026-10-16"))

    def test_questions_classified_with_folded_accents(self):
        conn = store()
        read, ours, gaps = uyr.pull_questions(conn, FakeClient(CAMARA), "2026-10-09",
                                              tax=tiny_taxonomy())
        self.assertEqual((read, gaps), (7, 0))
        rows = dict(conn.execute("SELECT tema, areas FROM uy_questions").fetchall())
        ive = [t for t in rows if t.startswith("INTERRUPCIÓN VOLUNTARIA")][0]
        self.assertEqual(json.loads(rows[ive]), [1])
        laic = [t for t in rows if "LAICIDAD" in t][0]
        self.assertEqual(json.loads(rows[laic]), [8])
        self.assertEqual(ours, 4)   # IVE, laicidad, and the orca's "eutanasia" (a known false hit)

    def test_a_refused_file_is_a_gap_not_a_crash(self):
        conn = store()
        client = FakeClient(CAMARA, fail=[uyr.QUESTIONS_URL])
        self.assertEqual(uyr.pull_questions(conn, client, "2026-10-09", log=lambda *_: None),
                         (0, 0, 1))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed=?",
                                      (uyr.FEED,)).fetchone()[0], 1)


class LawWalkTests(unittest.TestCase):
    def test_walk_from_the_newest_law_crossing_into_a_new_year(self):
        conn = store()
        uyr.store_law(conn, uyr.parse_law(fixture("law-20431-2025.json")), None, "2026-10-01")
        # 20432 is (for the test) the 2026 law: asked under 2025 first, then 2026.
        files = {law_url(20432, 2026): fixture("law-20530-2026.json").replace(b'"20530"', b'"20432"')}
        client = FakeClient(files)
        stored, ours, gaps = uyr.pull_laws(conn, client, "2026-10-09")
        self.assertEqual((stored, gaps), (1, 0))
        self.assertEqual(client.throttles["www.impo.com.uy"], uyr.IMPO_CRAWL_DELAY)
        self.assertEqual(client.asked[:2], [law_url(20432, 2025), law_url(20432, 2026)])
        # Then MAX_MISSES numbers, each under 2026 and 2027 -- but never a
        # year after this one.
        self.assertNotIn(law_url(20433, 2025), client.asked)
        self.assertEqual(conn.execute("SELECT year, url FROM uy_laws WHERE law_number=20432")
                         .fetchone(), (2026, "https://www.impo.com.uy/bases/leyes/20432-2026"))
        self.assertEqual(client.archived, ["law-20432-2026"])   # the HTML misses are not archived

    def test_watchlist_lends_areas_without_a_taxonomy(self):
        conn = store()
        areas = uyr.store_law(conn, uyr.parse_law(fixture("law-20431-2025.json")), None, "2026-10-09")
        self.assertEqual(areas, [2])
        row = conn.execute("SELECT areas, matched_terms, tier FROM uy_laws").fetchone()
        self.assertEqual((json.loads(row[0]), json.loads(row[1]), row[2]),
                         ([2], ["watch:ley:20431"], 2))
        other = uyr.store_law(conn, uyr.parse_law(fixture("law-20530-2026.json")), None, "2026-10-09")
        self.assertIsNone(other)

    def test_taxonomy_and_watchlist_together(self):
        conn = store()
        areas = uyr.store_law(conn, uyr.parse_law(fixture("law-20431-2025.json")),
                              tiny_taxonomy(), "2026-10-09")
        self.assertEqual(areas, [2])
        terms = json.loads(conn.execute("SELECT matched_terms FROM uy_laws").fetchone()[0])
        self.assertIn("eutanasia*", terms)
        self.assertIn("watch:ley:20431", terms)

    def test_a_404_is_a_miss_and_a_refusal_is_a_gap(self):
        conn = store()
        uyr.store_law(conn, uyr.parse_law(fixture("law-20530-2026.json")), None, "2026-10-01")
        client = FakeClient(missing=[law_url(20531, 2026)], fail=[law_url(20532, 2026)])
        stored, ours, gaps = uyr.pull_laws(conn, client, "2026-10-09", log=lambda *_: None)
        self.assertEqual((stored, gaps), (0, 1))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0], 1)

    def test_plan_reasks_holes_below_the_newest_law(self):
        conn = store()
        for n in (20380, 20383):
            law = uyr.parse_law(fixture("law-20530-2026.json").replace(b'"20530"', b'"%d"' % n))
            uyr.store_law(conn, law, None, "2026-10-01")
        holes, first, year = uyr.law_plan(conn)
        self.assertEqual((holes, first, year), ([20381, 20382], 20384, 2026))

    def test_first_walk_starts_at_START_LAW(self):
        self.assertEqual(uyr.law_plan(store()), ([], uyr.START_LAW, None))


class ReclassifyAndSchemaTests(unittest.TestCase):
    def test_reclassify_offline(self):
        conn = store()
        uyr.pull_questions(conn, FakeClient(CAMARA), "2026-10-09")
        uyr.store_law(conn, uyr.parse_law(fixture("law-20530-2026.json")), None, "2026-10-09")
        changed = uyr.reclassify(conn, tiny_taxonomy(), log=lambda *_: None)
        self.assertEqual(changed, 8)   # every NULL becomes a list
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM uy_questions WHERE areas IS NULL")
                         .fetchone()[0], 0)

    def test_tables_declared(self):
        for t in uy_store.TABLES:
            self.assertIn(t, db.TABLES)

    def test_watchlist_keys_are_keys_not_titles(self):
        wl = uy_store.watchlist()
        self.assertTrue(wl)
        for key in wl:
            self.assertRegex(key, r"^(ley|asunto):\d+$")


if __name__ == "__main__":
    unittest.main()
