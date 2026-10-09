"""Spain, Congreso de los Diputados: votes, initiatives, deputies
(tools/es_rollcalls.py). No network: real responses saved on 9 October 2026
under tests/fixtures/es/."""

import gzip
import importlib.util
import json
import os
import re
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, es_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "es")


def _load():
    spec = importlib.util.spec_from_file_location(
        "es_rollcalls", os.path.join(ROOT, "tools", "es_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


esr = _load()


def fixture(name):
    path = os.path.join(FIX, name)
    if name.endswith(".gz"):
        with gzip.open(path, "rb") as fh:
            return fh.read()
    with open(path, "rb") as fh:
        return fh.read()


def text(name):
    return fixture(name).decode("utf-8")


def store():
    conn = sqlite3.connect(":memory:")
    db.init_db(conn)
    return conn


TINY_TAXONOMY = """version: test
areas:
  9_marriage_family:
    tier1: ["nacionalidad española"]
    tier2: []
  11_migration:
    tier1: ["inmigración", "Pacto Europeo sobre Migración y Asilo"]
    tier2: []
exclusions_global: [vida]
"""


def tiny_taxonomy():
    fd, path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(TINY_TAXONOMY)
    try:
        return esr.load_taxonomy(path)
    finally:
        os.unlink(path)


class FakeClient:
    """Serves fixtures by URL; anything unknown raises FetchError."""

    def __init__(self, pages=None, files=None, fail=()):
        self.pages, self.files, self.fail = pages or {}, files or {}, set(fail)
        self.requested = []

    def _get(self, url, table):
        self.requested.append(url)
        if url in self.fail:
            raise FetchError(url, "es-rollcalls", "x", 1, "HTTP Error 503")
        for key, value in table.items():
            if key in url:
                return value
        raise FetchError(url, "es-rollcalls", "x", 1, "HTTP Error 404")

    def get_text(self, url, feed, slug, **kw):
        return self._get(url, self.pages)

    def get_bytes(self, url, feed, slug, **kw):
        return self._get(url, self.files)

    def get_json(self, url, feed, slug, **kw):
        return json.loads(self._get(url, self.files))


class Helpers(unittest.TestCase):
    def test_iso(self):
        self.assertEqual(esr.iso("30/9/2026"), "2026-09-30")
        self.assertEqual(esr.iso("06/10/2026"), "2026-10-06")
        self.assertIsNone(esr.iso(""))
        self.assertIsNone(esr.iso("Concluido"))

    def test_expediente_drops_the_subnumber(self):
        self.assertEqual(esr.expediente("121/000001/0000"), "121/000001")
        self.assertEqual(esr.expediente("162/000814"), "162/000814")
        self.assertIsNone(esr.expediente("caducado"))

    def test_initiative_key_carries_the_legislature(self):
        # Numbers restart every legislature: 122/000001 in the XV is not the
        # XVI's. A key without the legislature would merge them.
        self.assertEqual(esr.initiative_key(15, "122/000001/0000"), "15/122/000001")
        self.assertIsNone(esr.initiative_key(15, None))

    def test_roman(self):
        self.assertEqual(esr.roman(15), "XV")
        self.assertEqual(esr.roman(16), "XVI")


class Landing(unittest.TestCase):
    def test_every_voting_day_of_the_xv(self):
        leg, days = esr.parse_landing(text("landing-xv.html.gz"))
        self.assertEqual(leg, 15)
        self.assertEqual(len(days), 146)
        self.assertEqual(days[0], "2023-09-19")
        self.assertEqual(days[-1], "2026-09-30")

    def test_a_page_without_the_calendar_yields_nothing(self):
        self.assertEqual(esr.parse_landing("<html></html>"), (None, []))


class DayPage(unittest.TestCase):
    def setUp(self):
        self.votes = esr.parse_day(text("day-2026-09-10.html.gz"))

    def test_every_vote_file_listed(self):
        self.assertEqual(len(self.votes), 21)
        self.assertEqual([v["vote_number"] for v in self.votes], list(range(1, 22)))
        self.assertTrue(all(v["date"] == "2026-09-10" for v in self.votes))
        self.assertTrue(all(v["session"] == 196 and v["legislature"] == 15 for v in self.votes))
        self.assertTrue(all(v["json_url"].startswith("https://www.congreso.es/webpublica/")
                            for v in self.votes))

    def test_each_vote_is_joined_to_its_expediente(self):
        # The vote JSON does not carry the expediente: the day page is the
        # only place the vote meets its initiative.
        by_num = {v["vote_number"]: v for v in self.votes}
        self.assertEqual(by_num[1]["expediente"], "122/000072")
        self.assertEqual(by_num[4]["expediente"], "162/000833")
        self.assertEqual(by_num[7]["expediente"], "173/000186")
        self.assertEqual(by_num[21]["expediente"], "158/000024")
        self.assertTrue(all(v["expediente"] for v in self.votes))

    def test_section_title_and_points(self):
        v1 = self.votes[0]
        self.assertEqual(v1["section"], "Dictámenes de Comisiones sobre iniciativas legislativas.")
        self.assertTrue(v1["title"].startswith("Proposición de Ley sobre concesión de nacionalidad"))
        self.assertEqual(self.votes[6]["subgroup"], "Votación separada por puntos. Punto 1.a")
        self.assertEqual(self.votes[7]["subgroup"], "Votación separada por puntos. Punto 1.b")
        self.assertIsNone(self.votes[3]["subgroup"])
        self.assertEqual(v1["session_title"], "Sesión Plenaria número 196")

    def test_totals_from_the_page(self):
        self.assertEqual((self.votes[0]["yes"], self.votes[0]["no"], self.votes[0]["abstain"]),
                         (139, 207, 1))

    def test_division_key(self):
        self.assertEqual(esr.division_key(self.votes[0]), "congreso-15-196-1")


class Investiture(unittest.TestCase):
    def test_an_image_only_vote_is_kept_without_a_file(self):
        # 16 November 2023: the investiture of Pedro Sánchez, 'pública por
        # llamamiento', published as a chart image with no JSON.
        votes = esr.parse_day(text("day-2023-11-16.html.gz"))
        self.assertEqual(len(votes), 1)
        v = votes[0]
        self.assertIsNone(v["json_url"])
        self.assertEqual((v["expediente"], v["yes"], v["no"]), ("080/000002", 179, 171))
        self.assertIn("Sánchez Pérez-Castejón", v["title"])

    def test_it_is_stored_and_never_fetched(self):
        conn = store()
        client = FakeClient(pages={"targetDate=16/11/2023": text("day-2023-11-16.html.gz"),
                                   "/es/opendata/votaciones": text("landing-xv.html.gz")})
        _leg, nd, ns, nf, gaps = esr.pull_votes(conn, client, "2026-10-09",
                                                log=lambda *_: None, days=["2023-11-16"])
        self.assertEqual((nd, ns, nf, gaps), (1, 1, 0, 0))
        self.assertIsNone(conn.execute("SELECT json_url FROM es_divisions").fetchone()[0])


class VoteFile(unittest.TestCase):
    def test_positions_and_totals(self):
        v = esr.parse_vote_json(fixture("vote-15-196-1.json.gz"))
        self.assertEqual(len(v["positions"]), 350)
        self.assertEqual((v["present"], v["yes"], v["no"], v["abstain"], v["not_voting"]),
                         (347, 139, 207, 1, 3))
        self.assertEqual(v["assent"], 0)
        self.assertEqual(v["date"], "2026-09-10")
        self.assertIn("Enmiendas", v["subgroup"])
        positions = {p[2] for p in v["positions"]}
        self.assertLessEqual(positions, {"Sí", "No", "Abstención", "No vota"})
        name, grupo, voto, seat = v["positions"][0]
        self.assertRegex(name, r"^[^,]+, .+$")
        self.assertTrue(grupo)

    def test_a_secret_ballot_has_no_positions(self):
        # The suplicatorio of 30 September 2026: totals, no names.
        v = esr.parse_vote_json(fixture("vote-15-202-21.json.gz"))
        self.assertEqual(v["positions"], [])
        self.assertEqual(v["yes"], 340)

    def test_not_a_vote_file(self):
        self.assertIsNone(esr.parse_vote_json(b"<html>error</html>"))
        self.assertIsNone(esr.parse_vote_json(b'{"other": 1}'))


def day_client(fail=()):
    files = {"Votacion001/": fixture("vote-15-196-1.json.gz"),
             "Votacion007/": fixture("vote-15-196-7.json.gz")}
    for n in range(1, 22):
        files.setdefault("Votacion{0:03d}/".format(n), fixture("vote-15-196-1.json.gz"))
    return FakeClient(
        pages={"targetDate=10/09/2026": text("day-2026-09-10.html.gz"),
               "/es/opendata/votaciones": text("landing-xv.html.gz")},
        files=files, fail=fail)


class PullVotes(unittest.TestCase):
    def test_one_day_end_to_end_unclassified(self):
        conn = store()
        logs = []
        leg, nd, ns, nf, gaps = esr.pull_votes(conn, day_client(), "2026-10-09", tax=None,
                                               log=logs.append, days=["2026-09-10"])
        self.assertEqual((leg, nd, ns, nf, gaps), (15, 1, 21, 21, 0))
        row = conn.execute("SELECT initiative_key, areas, own_areas, positions, present "
                           "FROM es_divisions WHERE division_key='congreso-15-196-1'").fetchone()
        # No Spanish taxonomy: NULL, which means unclassified, never "[]".
        self.assertEqual(row, ("15/122/000072", None, None, 350, 347))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM es_votes").fetchone()[0], 21 * 350)
        self.assertEqual(conn.execute("SELECT listed FROM es_vote_days WHERE day='2026-09-10'")
                         .fetchone()[0], 21)

    def test_index_only_reads_no_vote_file(self):
        conn = store()
        client = day_client()
        _leg, _nd, ns, nf, _g = esr.pull_votes(conn, client, "2026-10-09", log=lambda *_: None,
                                               days=["2026-09-10"], index_only=True)
        self.assertEqual((ns, nf), (21, 0))
        self.assertFalse(any(u.endswith(".json") for u in client.requested))
        self.assertIsNone(conn.execute("SELECT positions FROM es_divisions LIMIT 1").fetchone()[0])

    def test_a_failed_vote_file_is_a_gap_and_the_rest_carry_on(self):
        conn = store()
        client = day_client()
        esr.pull_votes(conn, client, "2026-10-09", log=lambda *_: None, days=["2026-09-10"],
                       index_only=True)
        url = conn.execute("SELECT json_url FROM es_divisions WHERE vote_number=3").fetchone()[0]
        client.fail = {url}
        _leg, _nd, _ns, nf, gaps = esr.pull_votes(conn, client, "2026-10-09",
                                                  log=lambda *_: None, days=["2026-09-10"])
        self.assertEqual((nf, gaps), (20, 1))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='es-rollcalls'")
                         .fetchone()[0], 1)
        # The next run picks up only the one still missing.
        client.fail = set()
        _leg, _nd, _ns, nf, gaps = esr.pull_votes(conn, client, "2026-10-09",
                                                  log=lambda *_: None, days=["2026-09-10"])
        self.assertEqual((nf, gaps), (1, 0))

    def test_an_old_stored_day_is_not_reread(self):
        conn = store()
        client = day_client()
        esr.pull_votes(conn, client, "2026-10-09", log=lambda *_: None, days=["2026-09-10"])
        client.requested.clear()
        _leg, nd, _ns, nf, _g = esr.pull_votes(conn, client, "2026-12-01",
                                               log=lambda *_: None, days=["2026-09-10"])
        self.assertEqual((nd, nf), (0, 0))
        self.assertFalse(any("targetDate=10/09/2026" in u for u in client.requested))

    def test_a_recent_day_is_reread_without_refetching_positions(self):
        conn = store()
        client = day_client()
        esr.pull_votes(conn, client, "2026-09-12", log=lambda *_: None, days=["2026-09-10"])
        _leg, nd, _ns, nf, _g = esr.pull_votes(conn, client, "2026-09-13",
                                               log=lambda *_: None, days=["2026-09-10"])
        self.assertEqual((nd, nf), (1, 0))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM es_votes").fetchone()[0], 21 * 350)

    def test_a_landing_page_without_days_is_a_gap(self):
        conn = store()
        client = FakeClient(pages={"/es/opendata/votaciones": "<html>maintenance</html>"})
        _leg, nd, ns, nf, gaps = esr.pull_votes(conn, client, "2026-10-09", log=lambda *_: None)
        self.assertEqual((nd, ns, nf, gaps), (0, 0, 0, 1))

    def test_budget_stops_cleanly(self):
        class Spent:
            seconds = 0

            def exhausted(self):
                return True

            def disclose(self, what, done):
                return "budget reached after {0} {1}".format(done, what)
        conn = store()
        logs = []
        _leg, nd, ns, nf, gaps = esr.pull_votes(conn, day_client(), "2026-10-09",
                                                log=logs.append, budget=Spent(),
                                                days=["2026-09-10"])
        self.assertEqual((nd, ns, nf, gaps), (0, 0, 0, 0))
        self.assertTrue(any("budget reached" in l for l in logs))


class Classification(unittest.TestCase):
    def setUp(self):
        self.saved = dict(es_store._WATCH)

    def tearDown(self):
        es_store._WATCH.clear()
        es_store._WATCH.update(self.saved)

    def test_classified_with_a_taxonomy_and_hidden_migration(self):
        conn = store()
        tax = tiny_taxonomy()
        esr.pull_votes(conn, day_client(), "2026-10-09", tax=tax, log=lambda *_: None,
                       days=["2026-09-10"], index_only=True)
        areas = json.loads(conn.execute("SELECT areas FROM es_divisions WHERE vote_number=1")
                           .fetchone()[0])
        self.assertEqual(areas, [9])
        unmatched = conn.execute("SELECT areas FROM es_divisions WHERE vote_number=21").fetchone()[0]
        self.assertEqual(unmatched, "[]")
        self.assertFalse(esr.on_our_ground([11]))
        self.assertTrue(esr.on_our_ground([9, 11]))

    def test_watchlist_lends_areas_by_key_even_without_a_taxonomy(self):
        es_store._WATCH[es_store.WATCHLIST] = {"15/162/000833": ([1], "test")}
        conn = store()
        esr.pull_votes(conn, day_client(), "2026-10-09", tax=None, log=lambda *_: None,
                       days=["2026-09-10"], index_only=True)
        row = conn.execute("SELECT areas, matched_terms FROM es_divisions WHERE vote_number=4"
                           ).fetchone()
        self.assertEqual(json.loads(row[0]), [1])
        self.assertIn("watch:15/162/000833", json.loads(row[1]))
        self.assertIsNone(conn.execute("SELECT areas FROM es_divisions WHERE vote_number=5")
                          .fetchone()[0])

    def test_a_vote_inherits_its_initiatives_areas(self):
        conn = store()
        conn.execute("INSERT INTO es_initiatives (initiative_key, legislature, expediente, "
                     "objeto, areas) VALUES ('15/173/000186', 15, '173/000186', 'x', '[6]')")
        tax = tiny_taxonomy()
        esr.pull_votes(conn, day_client(), "2026-10-09", tax=tax, log=lambda *_: None,
                       days=["2026-09-10"], index_only=True)
        own, areas = conn.execute("SELECT own_areas, areas FROM es_divisions WHERE vote_number=7"
                                  ).fetchone()
        self.assertEqual((json.loads(own), json.loads(areas)), ([], [6]))

    def test_reclassify_offline(self):
        conn = store()
        esr.pull_votes(conn, day_client(), "2026-10-09", tax=None, log=lambda *_: None,
                       days=["2026-09-10"], index_only=True)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM es_divisions WHERE areas IS NULL")
                         .fetchone()[0], 21)
        _ci, changed = esr.reclassify(conn, tiny_taxonomy(), log=lambda *_: None)
        self.assertEqual(changed, 21)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM es_divisions WHERE areas IS NULL")
                         .fetchone()[0], 0)

    def test_the_shipped_watchlist_parses_and_is_keyed_by_id(self):
        es_store._WATCH.clear()
        for key in es_store.watchlist():
            self.assertRegex(key, r"^\d{2}/\d{3}/\d{6}$")

    def test_no_spanish_taxonomy_ships_yet(self):
        # The term list is PROPOSED in docs/spain-scope.md; the yaml is
        # generated only once Christopher approves it. When it lands, this
        # test is the reminder to delete it.
        self.assertFalse(os.path.exists(esr.TAXONOMY_ES))
        self.assertIsNone(esr.load_taxonomy())


class Members(unittest.TestCase):
    def test_sitting_and_departed(self):
        conn = store()
        act = esr.parse_members(json.loads(fixture("diputados-activos.json")), sitting=True)
        baja = esr.parse_members(json.loads(fixture("diputados-baja.json")), sitting=False)
        for m in baja + act:
            esr.store_member(conn, 15, m, "2026-10-09")
        rows = dict(conn.execute("SELECT name, baja FROM es_members"))
        self.assertIsNone(rows["Abascal Conde, Santiago"])
        # Left at the dissolution of 6 October 2026 (not in the Diputación
        # Permanente).
        self.assertEqual(rows["Abades Martínez, Cristina"], "2026-10-06")
        self.assertEqual(rows["Verstrynge Revuelta, Lilith"], "2024-01-26")

    def test_the_members_file_is_discovered_from_the_page(self):
        page = text("members-page.html.gz")
        url = esr.discover(page, "diputados", "DiputadosActivos")
        self.assertRegex(url, r"^https://www\.congreso\.es/webpublica/opendata/diputados/"
                              r"DiputadosActivos__\d{14}\.json$")
        self.assertIsNone(esr.discover(page, "diputados", "NoSuchFile"))


class Initiatives(unittest.TestCase):
    def test_parse_and_store(self):
        conn = store()
        recs = esr.parse_initiatives(json.loads(fixture("iniciativas.json")))
        self.assertEqual(len(recs), 5)
        for i in recs:
            esr.store_initiative(conn, i, None, "2026-10-09")
        row = conn.execute("SELECT legislature, tipo, situacion, areas FROM es_initiatives "
                           "WHERE initiative_key='15/121/000115'").fetchone()
        self.assertEqual(row[0], 15)
        self.assertEqual(row[1], "Proyecto de ley")
        self.assertEqual(row[2], "Concluido - (Caducado)")
        self.assertIsNone(row[3])
        objeto = conn.execute("SELECT objeto FROM es_initiatives WHERE "
                              "initiative_key='15/121/000001'").fetchone()[0]
        self.assertNotIn("\n", objeto)
        keys = [r[0] for r in conn.execute("SELECT initiative_key FROM es_initiatives")]
        self.assertTrue(all(re.match(r"^15/12\d/\d{6}$", k) for k in keys))


class Schema(unittest.TestCase):
    def test_declared_in_db_tables(self):
        for t in es_store.TABLES:
            self.assertIn(t, db.TABLES)


if __name__ == "__main__":
    unittest.main()
