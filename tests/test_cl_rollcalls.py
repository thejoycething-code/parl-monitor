"""Chile's National Congress: bills, Cámara and Senate votes, members
(tools/cl_rollcalls.py). No network: real responses trimmed into
tests/fixtures/cl/ on 9 October 2026."""

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import cl_store, db, filter as filt  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "cl")


def _load():
    spec = importlib.util.spec_from_file_location(
        "cl_rollcalls", os.path.join(ROOT, "tools", "cl_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


clr = _load()


def fx(name):
    with open(os.path.join(FIX, name), "rb") as fh:
        return fh.read()


# A small Spanish taxonomy for the tests only: config/taxonomy-es.yaml does not
# exist until Christopher approves the terms in docs/chile-scope.md.
TEST_TAXONOMY = """
version: test
areas:
  1_abortion:
    tier1: ["aborto*", "interrupcion voluntaria del embarazo"]
    tier2: []
  2_assisted_dying:
    tier1: ["eutanasia", "muerte digna"]
    tier2: []
  7_free_speech_online_safety:
    tier1: ["libertad de expresion"]
    tier2: []
  11_migration:
    tier1: []
    tier2: ["migracion"]
"""


def test_taxonomy():
    fd, path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(TEST_TAXONOMY)
    try:
        return filt.load_taxonomy(path)
    finally:
        os.unlink(path)


TAX = test_taxonomy()


class FakeClient:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def _get(self, url):
        self.calls.append(url)
        for prefix, body in self.routes.items():
            if url.startswith(prefix):
                if isinstance(body, Exception):
                    raise body
                return body
        raise FetchError(url, "cl-rollcalls", "x", 1, "404")

    def get_bytes(self, url, feed, slug, timeout=None, archive=True, first_bytes=None):
        return self._get(url)

    def get_text(self, url, feed, slug, timeout=None, archive=True, fallback_encoding=None):
        return self._get(url).decode("utf-8")


def store():
    conn = db.init_db(sqlite3.connect(":memory:"))
    return conn


class ParserTests(unittest.TestCase):
    def test_vote_list(self):
        votes = clr.parse_vote_list(fx("votaciones-2026.xml"))
        self.assertEqual(len(votes), 5)
        v = votes[1]
        self.assertEqual((v["id"], v["boletin"], v["yes"], v["no"], v["abstain"]),
                         (90328, "15805-07", 111, 23, 5))
        self.assertEqual(v["kind"], "Proyecto de Ley")
        # A resolution or an agreement carries no boletín.
        self.assertIsNone(votes[2]["boletin"])
        self.assertEqual(votes[2]["kind"], "Proyecto de Resolución")

    def test_vote_detail(self):
        d = clr.parse_vote_detail(fx("votacion-90328.xml"))
        self.assertEqual(d["id"], 90328)
        self.assertEqual(len(d["positions"]), 5)
        first = d["positions"][0]
        self.assertEqual((first["member_key"], first["name"], first["position"]),
                         ("D-803", "René Alinco Bustos", "En Contra"))
        self.assertIn("No Vota", {p["position"] for p in d["positions"]})

    def test_error_bodies_at_200_are_not_records(self):
        self.assertIsNone(clr.parse_bill(fx("proyecto-nil.xml")))
        self.assertIsNone(clr.parse_senate_votes(fx("senado-no-existe.html")))
        self.assertIsNone(clr.parse_senate_projects(fx("senado-no-existe.html")))
        self.assertIsNone(clr.parse_vote_list(b"<html>maintenance</html>"))
        self.assertIsNone(clr.parse_vote_detail(b"not xml at all"))

    def test_bill_carries_vote_text(self):
        b = clr.parse_bill(fx("proyecto-15805-07.xml"))
        self.assertEqual(b["boletin"], "15805-07")
        self.assertTrue(b["title"].startswith("Establece normas generales sobre el uso de la fuerza"))
        self.assertEqual(b["initiative"], "Mensaje")
        text, stage, _ = b["votes"][90328]
        self.assertIn("Comisión Mixta", text)
        self.assertEqual(stage, "Comisión Mixta")

    def test_bill_list(self):
        bills = clr.parse_bill_list(fx("mociones-2026.xml"))
        self.assertEqual([b["boletin"] for b in bills], ["18173-21", "18327-07", "18132-04"])
        self.assertEqual(bills[0]["introduced"], "2026-04-08")

    def test_deputies_and_party_on_a_date(self):
        deps = clr.parse_deputies(fx("diputados.xml"))
        self.assertEqual(len(deps), 2)
        d = deps[0]
        self.assertEqual(d["member_key"], "D-1074")
        # Communist 2019-2024, then independent.
        self.assertEqual(clr.party_on(d["spells"], "2023-05-01"), "PC")
        self.assertEqual(clr.party_on(d["spells"], "2026-10-07T13:18:43"), "IND")
        self.assertIsNone(clr.party_on(d["spells"], "2010-01-01"))

    def test_boletin_normalised(self):
        self.assertEqual(clr.norm_boletin("Boletín N° 15.805-07"), "15805-07")
        self.assertEqual(clr.norm_boletin("Boletín N°15805-7"), "15805-07")
        self.assertIsNone(clr.norm_boletin("Proyecto de Resolución N° 72"))
        self.assertEqual(clr.boletin_number("15805-07"), 15805)

    def test_senate_votes(self):
        votes = clr.parse_senate_votes(fx("senado-votaciones-15805.xml"))
        self.assertEqual(len(votes), 1)
        v = votes[0]
        self.assertEqual((v["date"], v["yes"], v["no"], v["abstain"]), ("2024-06-18", 40, 0, 3))
        self.assertEqual(v["kind"], "Discusión general")
        self.assertEqual(len(v["positions"]), 43)

    def test_senate_projects(self):
        ps = clr.parse_senate_projects(fx("senado-tramitacion.xml"))
        self.assertEqual(len(ps), 1)
        p = ps[0]
        self.assertEqual(p["boletin"], "10986-24")
        self.assertIn("MONUMENTOS", p["subjects"])
        self.assertTrue(p["authors"])
        self.assertTrue(p["votes"] and p["votes"][0]["positions"])

    def test_senators_page_has_all_and_ids(self):
        s = clr.parse_senators_page(fx("senadores-page.html").decode("utf-8"))
        keys = {x["member_key"] for x in s}
        self.assertIn("S-1507", keys)          # Cicardini, elected 2025
        self.assertTrue(all(x["party"] for x in s))
        vig = clr.parse_senadores_vigentes(fx("senadores-vigentes.xml"))
        self.assertEqual(len(vig), 31)         # the stale list: no Cicardini
        self.assertNotIn("S-1507", {x["member_key"] for x in vig})


class SenatorNameTests(unittest.TestCase):
    def setUp(self):
        self.idx = clr.SenatorIndex(clr.parse_senators_page(
            fx("senadores-page.html").decode("utf-8")))

    def test_resolves_printed_names(self):
        self.assertEqual(self.idx.resolve("Gatica B., María José")["surname2"], "Bertin")
        self.assertEqual(self.idx.resolve("Cicardini M., Daniella ")["member_key"], "S-1507")
        # Two Núñez: the initial decides.
        self.assertEqual(self.idx.resolve("Núñez U., Paulina")["surname2"], "Urrutia")
        self.assertEqual(self.idx.resolve("Núñez A., Daniel")["surname2"], "Arancibia")
        # No second surname printed as "  ."
        self.assertEqual(self.idx.resolve("Edwards  ., Rojo")["given"], "Rojo")

    def test_never_guesses(self):
        # A former senator sharing a current senator's surname.
        self.assertIsNone(self.idx.resolve("Castro P., Juan"))
        self.assertEqual(self.idx.resolve("Castro G., Juan Luis")["given"], "Juan Luis")
        self.assertIsNone(self.idx.resolve("Desconocido X., Nadie"))


class ClassifyTests(unittest.TestCase):
    def test_accents_folded(self):
        res = clr.classify(TAX, "Regula la interrupción voluntaria del embarazo")
        self.assertEqual(res.issue_areas, [1])
        res = clr.classify(TAX, "SOBRE LIBERTAD DE EXPRESIÓN")
        self.assertEqual(res.issue_areas, [7])

    def test_hidden_area_is_not_our_ground(self):
        self.assertFalse(clr.on_our_ground([11]))
        self.assertTrue(clr.on_our_ground([11, 1]))

    def test_watchlist_by_boletin(self):
        fd, path = tempfile.mkstemp(suffix=".yaml")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("bills:\n  '15805-07':\n    areas: [7]\n    why: test\n")
        try:
            res = clr.classify(TAX, "Establece normas sobre el uso de la fuerza")
            cl_store.add_watch_areas(res, "15805-07", path=path)
            self.assertEqual(res.issue_areas, [7])
            self.assertEqual(res.watchlist_hits, ["watch:15805-07"])
            res2 = clr.classify(TAX, "Establece normas sobre el uso de la fuerza")
            cl_store.add_watch_areas(res2, "15806-07", path=path)
            self.assertEqual(res2.issue_areas, [])
        finally:
            os.unlink(path)

    def test_the_real_watchlist_loads(self):
        for boletin, (areas, why) in cl_store.watchlist().items():
            self.assertRegex(boletin, r"^\d{4,5}-\d{2}$")
            self.assertTrue(areas and why, boletin)


class PullTests(unittest.TestCase):
    def routes(self, **over):
        r = {
            clr.VOTES_YEAR.format(2026): fx("votaciones-2026.xml"),
            clr.VOTE_DETAIL.format(""): fx("votacion-90328.xml"),
            clr.BILL.format(""): fx("proyecto-15805-07.xml"),
        }
        r.update(over)
        return r

    def test_camara_pull_stores_votes_positions_and_resumes(self):
        conn = store()
        client = FakeClient(self.routes())
        stored, ours, gaps = clr.pull_camara(conn, client, TAX, "2026-10-09", since="2026-10-01")
        # Five votes listed; the fake answers every detail with vote 90328's
        # body, which is fine: the head comes from the list.
        self.assertEqual((stored, gaps), (5, 0))
        row = conn.execute("SELECT boletin, text, stage, yes, result FROM cl_divisions "
                           "WHERE division_key='camara-90328'").fetchone()
        self.assertEqual(row[0], "15805-07")
        self.assertIn("Comisión Mixta", row[1])
        self.assertEqual((row[3], row[4]), (111, "Aprobado"))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM cl_votes WHERE "
                                      "division_key='camara-90328'").fetchone()[0], 5)
        # The bill is fetched once per boletín, not per vote.
        self.assertEqual(sum("retornarProyectoLey" in c for c in client.calls), 2)
        # A second run fetches no detail: everything is stored.
        client2 = FakeClient(self.routes())
        stored2, _, _ = clr.pull_camara(conn, client2, TAX, "2026-10-09", since="2026-10-01")
        self.assertEqual(stored2, 0)
        self.assertFalse(any("retornarVotacionDetalle" in c for c in client2.calls))

    def test_party_at_the_vote(self):
        conn = store()
        conn.execute("INSERT INTO cl_party_spells VALUES ('D-803','PRI','x','2022-03-11',"
                     "'2026-03-10')")
        conn.execute("INSERT INTO cl_party_spells VALUES ('D-803','IND','x','2026-03-11',NULL)")
        clr.pull_camara(conn, FakeClient(self.routes()), TAX, "2026-10-09", since="2026-10-01")
        self.assertEqual(conn.execute("SELECT party FROM cl_votes WHERE member_key='D-803' "
                                      "AND division_key='camara-90328'").fetchone()[0], "IND")

    def test_detail_failure_is_a_gap_and_stops_the_year(self):
        conn = store()
        client = FakeClient(self.routes(**{clr.VOTE_DETAIL.format(""): FetchError(
            "u", "cl-rollcalls", "x", 3, "timeout")}))
        stored, _, gaps = clr.pull_camara(conn, client, TAX, "2026-10-09", since="2026-10-01")
        self.assertEqual((stored, gaps), (0, 1))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='cl-rollcalls'")
                         .fetchone()[0], 1)

    def test_limit_is_disclosed(self):
        conn = store()
        logs = []
        stored, _, _ = clr.pull_camara(conn, FakeClient(self.routes()), TAX, "2026-10-09",
                                       since="2026-10-01", limit=2, log=logs.append)
        self.assertEqual(stored, 2)
        self.assertTrue(any("fetch cap" in line for line in logs))

    def test_senate_pull_from_tramitacion(self):
        conn = store()
        senators = clr.parse_senators_page(fx("senadores-page.html").decode("utf-8"))
        client = FakeClient({clr.SEN + "tramitacion.php": fx("senado-tramitacion.xml")})
        nb, nv, ours, unresolved, gaps = clr.pull_senate(conn, client, TAX, "2026-10-09",
                                                         senators, days=14)
        self.assertEqual((nb, gaps), (1, 0))
        self.assertGreater(nv, 0)
        # The date is percent-encoded: the service rejects raw slashes.
        self.assertIn("fecha=25%2F09%2F2026", client.calls[0])
        keys = {r[0] for r in conn.execute("SELECT member_key FROM cl_votes")}
        # Names the six-senator test list cannot resolve are kept, unguessed.
        self.assertTrue(unresolved)
        self.assertTrue(all(k.startswith("S-") for k in keys))
        # Re-running stores the same divisions, not new ones.
        clr.pull_senate(conn, client, TAX, "2026-10-09", senators, days=14)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM cl_divisions").fetchone()[0], nv)

    def test_watched_bills_are_read_every_run(self):
        conn = store()
        client = FakeClient({clr.SEN + "tramitacion.php": b"<proyectos></proyectos>"})
        clr.pull_senate(conn, client, TAX, "2026-10-09", [], days=14)
        for boletin in cl_store.watchlist():
            self.assertIn(clr.SEN_BILL.format(clr.boletin_number(boletin)), client.calls)

    def test_senate_window_is_capped(self):
        conn = store()
        client = FakeClient({clr.SEN + "tramitacion.php": fx("senado-tramitacion.xml")})
        clr.pull_senate(conn, client, TAX, "2026-10-09", [], days=90)
        self.assertIn("fecha=11%2F09%2F2026", client.calls[0])

    def test_senate_error_page_is_a_gap(self):
        conn = store()
        client = FakeClient({clr.SEN + "tramitacion.php": fx("senado-no-existe.html")})
        _, _, _, _, gaps = clr.pull_senate(conn, client, TAX, "2026-10-09", [], days=14)
        self.assertEqual(gaps, 1)

    def test_senate_backfill_takes_the_number_only(self):
        conn = store()
        clr.store_bill(conn, TAX, {"boletin": "17564-11",
                                   "title": "Regula la interrupción voluntaria del embarazo"},
                       "2026-10-09")
        client = FakeClient({clr.SEN + "tramitacion.php": b"<proyectos></proyectos>",
                             clr.SEN + "votaciones.php": fx("senado-votaciones-15805.xml")})
        clr.pull_senate(conn, client, TAX, "2026-10-09", [], days=14, backfill=True)
        self.assertIn(clr.SEN_VOTES.format(17564), client.calls)
        row = conn.execute("SELECT areas, own_areas FROM cl_divisions WHERE boletin='17564-11'"
                           ).fetchone()
        self.assertEqual(json.loads(row[0]), [1])    # inherited from the bill
        self.assertEqual(json.loads(row[1]), [])     # the vote's own text is about force

    def test_senate_keys_stable_and_distinct(self):
        v = {"session": "29/372", "date": "2024-06-18", "stage": "x", "kind": "y", "text": "z"}
        seen = {}
        a = clr.senate_division_key("15805-07", v, seen)
        b = clr.senate_division_key("15805-07", dict(v), seen)
        self.assertNotEqual(a, b)
        self.assertEqual(a, clr.senate_division_key("15805-07", dict(v), {}))
        self.assertTrue(a.startswith("senado-15805-"))


class StoreTests(unittest.TestCase):
    def test_tables_declared(self):
        for t in cl_store.TABLES:
            self.assertIn(t, db.TABLES)

    def test_bill_merge_keeps_what_each_source_knows(self):
        conn = store()
        clr.store_bill(conn, TAX, {"boletin": "17732-11", "title": "Regula la eutanasia",
                                   "introduced": "2025-08-01"}, "2026-10-01")
        clr.store_bill(conn, TAX, {"boletin": "17732-11", "title": None, "stage": "Primer trámite",
                                   "subjects": ["EUTANASIA"], "authors": ["A, B"]}, "2026-10-09")
        row = conn.execute("SELECT title, introduced, stage, subjects, areas, first_seen, "
                           "last_seen FROM cl_bills").fetchone()
        self.assertEqual(row[:3], ("Regula la eutanasia", "2025-08-01", "Primer trámite"))
        self.assertEqual(json.loads(row[3]), ["EUTANASIA"])
        self.assertEqual(json.loads(row[4]), [2])
        self.assertEqual(row[5:], ("2026-10-01", "2026-10-09"))

    def test_reclassify(self):
        conn = store()
        empty = filt.Taxonomy(version="0", terms={}, exclusions=set())
        clr.store_bill(conn, empty, {"boletin": "17732-11", "title": "Regula la eutanasia"},
                       "2026-10-09")
        self.assertEqual(conn.execute("SELECT areas FROM cl_bills").fetchone()[0], "[]")
        changed_b, _ = clr.reclassify(conn, TAX, log=lambda *_: None)
        self.assertEqual(changed_b, 1)
        self.assertEqual(conn.execute("SELECT areas FROM cl_bills").fetchone()[0], "[2]")


if __name__ == "__main__":
    unittest.main()
