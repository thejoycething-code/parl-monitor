"""Guatemala, Congreso de la República: sessions, votes, initiatives,
deputies (tools/gt_rollcalls.py). No network: real responses fetched from a
GitHub runner on 9 October 2026, saved under tests/fixtures/gt/."""

import gzip
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gt_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "gt")


def _load():
    spec = importlib.util.spec_from_file_location(
        "gt_rollcalls", os.path.join(ROOT, "tools", "gt_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gtr = _load()


def text(name):
    path = os.path.join(FIX, name)
    opener = gzip.open if name.endswith(".gz") else open
    with opener(path, "rb") as fh:
        return fh.read().decode("utf-8")


def store():
    conn = sqlite3.connect(":memory:")
    db.init_db(conn)
    return conn


TINY_TAXONOMY = """version: test
areas:
  6_parental_rights_education:
    tier1: ["educación sexual"]
    tier2: []
  11_migration:
    tier1: ["migrantes"]
    tier2: []
exclusions_global: [vida]
"""


def tiny_taxonomy():
    fd, path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(TINY_TAXONOMY)
    try:
        return gtr.load_taxonomy(path)
    finally:
        os.unlink(path)


class FakeClient:
    """Serves fixtures by URL substring; anything unknown is a 404."""

    def __init__(self, pages=None, fail=None):
        self.pages, self.fail = pages or {}, fail or {}
        self.requested = []

    def get_text(self, url, feed, slug, **kw):
        self.requested.append(url)
        for key, cause in self.fail.items():
            if key in url:
                raise FetchError(url, feed, slug, 1, cause)
        for key, value in self.pages.items():
            if key in url:
                return value
        raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")


class Helpers(unittest.TestCase):
    def test_iso(self):
        self.assertEqual(gtr.iso("No. 42, Fase 1, Fecha 08/09/2026 12:59:43"), "2026-09-08")
        self.assertIsNone(gtr.iso("Generar PDF"))

    def test_iso_long(self):
        self.assertEqual(gtr.iso_long("Martes, 08 de septiembre de 2026"), "2026-09-08")
        self.assertEqual(gtr.iso_long("Jueves, 11 de abril de 2024"), "2024-04-11")
        self.assertIsNone(gtr.iso_long("pronto"))

    def test_the_initiative_a_question_names(self):
        self.assertEqual(gtr.iniciativa_in(
            "APROBACIÓN EN ÚNICO DEBATE DEL PROYECTO DE DECRETO QUE DISPONE APROBAR LA "
            "INICIATIVA DE LEY 6844"), "6844")
        self.assertEqual(gtr.iniciativa_in("APROBACIÓN DE MOCIÓN PRIVILEGIADA URGENCIA NACIONAL 6047"),
                         "6047")
        self.assertEqual(gtr.iniciativa_in("APROBACIÓN DE MOCIÓN DE REVISIÓN 5272"), "5272")
        self.assertEqual(gtr.iniciativa_in(
            "APROBACIÓN DE MOCIÓN PRIVILEGIADA PARA ALTERAR EL ORDEN DEL DÍA (URGENCIA NACIONAL 6844)"),
            "6844")
        # The vote that shelved Decreto 18-2022 named nothing: procedural.
        self.assertIsNone(gtr.iniciativa_in("APROBACIÓN DE PROYECTO DE ACUERDO"))
        self.assertIsNone(gtr.iniciativa_in("APROBACIÓN DEL ORDEN DEL DÍA"))

    def test_name_key_joins_both_name_orders(self):
        self.assertEqual(gt_store.name_key("Aguirre Estrada Luis Fernando"),
                         gt_store.name_key("Luis Fernando Aguirre Estrada"))
        self.assertEqual(gt_store.name_key("Velásquez Bámaca Sabino Sebastián"),
                         gt_store.name_key("Sabino Sebastián Velásquez Bamaca"))

    def test_challenge_pages_are_recognised(self):
        self.assertTrue(gtr.is_challenge(text("challenge-incapsula.html")))
        self.assertFalse(gtr.is_challenge(text("vote-51365.html.gz")))


class Sessions(unittest.TestCase):
    def test_every_session_since_2009(self):
        s = gtr.parse_sessions(text("sessions.html.gz"))
        self.assertEqual(len(s), 1089)
        self.assertEqual(s[0], {"session_id": "41394", "tipo": "Ordinaria", "numero": 50,
                                "label": "No. 50, Fase 1, Fecha 08/10/2026 08:51:25",
                                "date": "2026-10-08"})
        self.assertEqual(s[-1]["date"], "2009-03-12")
        self.assertEqual(len([x for x in s if x["date"] >= gtr.SINCE]), 190)

    def test_a_session_page_lists_its_questions(self):
        votes = gtr.parse_session(text("session-41385.html.gz"))
        self.assertEqual(len(votes), 11)
        five = [v for v in votes if v["number"] == 5][0]
        self.assertEqual(five["question_id"], "51365")
        self.assertEqual(five["session_id"], "41385")
        self.assertEqual(five["date"], "2026-09-08")
        self.assertEqual(five["iniciativa"], "6844")
        self.assertIsNone([v for v in votes if v["number"] == 1][0]["iniciativa"])

    def test_the_5272_votes_of_8_march_2022(self):
        votes = gtr.parse_session(text("session-41013.html.gz"))
        ours = [v for v in votes if v["iniciativa"] == "5272"]
        self.assertEqual(len(ours), 15)
        third = [v for v in ours if v["title"].startswith("APROBACIÓN EN TERCER DEBATE")][0]
        self.assertEqual(third["question_id"], "34598")


class VotePage(unittest.TestCase):
    def test_every_deputy_and_the_totals(self):
        v = gtr.parse_vote(text("vote-51365.html.gz"))
        self.assertEqual((v["yes"], v["no"], v["absent"], v["leave"]), (136, 10, 8, 6))
        self.assertEqual(len(v["positions"]), 160)
        self.assertEqual(v["number"], 5)
        self.assertIn("INICIATIVA DE LEY 6844", v["title"])
        self.assertEqual(v["positions"][0], ("Villagrán Alvarez Jorge Mario", "PRESENTE", "A FAVOR"))
        self.assertIn(("Aguirre Estrada Luis Fernando", "LICENCIA / EXCUSA", "LICENCIA"),
                      v["positions"])

    def test_a_2022_vote_reads_the_same(self):
        v = gtr.parse_vote(text("vote-34575.html.gz"))
        self.assertEqual((v["yes"], v["no"], v["absent"], v["leave"]), (90, 38, 25, 7))

    def test_a_page_without_tabs_is_not_a_vote(self):
        self.assertIsNone(gtr.parse_vote("<html><body>nada</body></html>"))


class Initiatives(unittest.TestCase):
    def test_the_listing(self):
        items = gtr.parse_initiatives(text("initiatives.html.gz"))
        self.assertEqual(len(items), 500)
        first = items[0]
        self.assertEqual(first["numero"], "6859")
        self.assertEqual(first["detail_id"], "6498")
        self.assertEqual(first["conocio_pleno"], "2026-10-06")
        self.assertTrue(first["resumen"].startswith("Iniciativa que dispone aprobar reformas"))
        self.assertTrue(all(i["resumen"] for i in items))
        self.assertEqual(len({i["numero"] for i in items}), 500)


class Members(unittest.TestCase):
    def test_one_card_per_deputy(self):
        m = gtr.parse_members(text("home.html.gz"))
        self.assertEqual(len(m), 160)
        first = m[0]
        self.assertEqual(first, {"member_id": "929", "name": "Luis Fernando Aguirre Estrada",
                                 "bloque": "CABAL", "distrito": "Lista Nacional"})
        blocs = [x["bloque"] for x in m]
        self.assertEqual(blocs.count("INDEPENDIENTE"), 38)
        self.assertEqual(blocs.count("VAMOS"), 38)
        self.assertNotIn(None, blocs)


class Pull(unittest.TestCase):
    def client(self, **kw):
        return FakeClient(pages={
            "votaciones_pleno": text("sessions.html.gz"),
            "eventos_votaciones/41385": text("session-41385.html.gz"),
            "detalle_de_votacion/51365/": text("vote-51365.html.gz"),
            "seccion_informacion_legislativa/iniciativas": text("initiatives.html.gz"),
        }, **kw)

    def test_a_session_and_its_votes(self):
        conn, c = store(), self.client()
        logs = []
        read, stored, pages, gaps = gtr.pull_votes(conn, c, "2026-09-09", since="2026-09-08",
                                                   log=logs.append)
        self.assertEqual((read, stored), (1, 11))
        # One vote page is in the fixtures; the other ten are 404 gaps, disclosed.
        self.assertEqual(pages, 1)
        self.assertEqual(gaps, 10)
        row = conn.execute("SELECT yes, no, absent, leave, positions, iniciativa, procedural "
                           "FROM gt_divisions WHERE division_key='gt-51365'").fetchone()
        self.assertEqual(row, (136, 10, 8, 6, 160, "6844", 0))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gt_votes").fetchone()[0], 160)
        self.assertEqual(conn.execute(
            "SELECT listed FROM gt_sessions WHERE session_id='41385'").fetchone()[0], 11)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='gt-rollcalls'")
                         .fetchone()[0], 10)

    def test_a_read_session_is_not_read_again_once_old(self):
        conn = store()
        quiet = lambda *_: None  # noqa: E731
        gtr.pull_votes(conn, self.client(), "2026-09-09", since="2026-09-08", index_only=True,
                       log=quiet)
        c = self.client()
        gtr.pull_votes(conn, c, "2026-10-09", since="2026-09-08", index_only=True, log=quiet)
        self.assertFalse(any("eventos_votaciones/41385" in u for u in c.requested))

    def test_a_challenge_stops_the_run(self):
        conn = store()
        c = self.client(fail={"votaciones_pleno": "HTTP Error 403: Forbidden"})
        with self.assertRaises(gtr.Challenged):
            gtr.pull_votes(conn, c, "2026-09-09", since="2026-09-08")
        self.assertEqual(len(c.requested), 1)

    def test_a_challenge_served_as_200_stops_it_too(self):
        conn = store()
        c = FakeClient(pages={"votaciones_pleno": text("challenge-incapsula.html")})
        with self.assertRaises(gtr.Challenged):
            gtr.pull_votes(conn, c, "2026-09-09")


class OlderInitiatives(unittest.TestCase):
    def test_the_search_page_is_the_same_card(self):
        items = gtr.parse_initiatives(text("search-5272.html.gz"))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["numero"], "5272")
        self.assertEqual(items[0]["conocio_pleno"], "2017-04-27")
        self.assertEqual(items[0]["resumen"],
                         "Iniciativa que dispone aprobar Ley para la Protección de la Vida y la Familia.")

    def test_a_voted_initiative_missing_from_the_listing_is_read_by_number(self):
        conn = store()
        for v in gtr.parse_session(text("session-41013.html.gz")):
            gtr.store_division(conn, v, None, "2026-10-09")
        c = FakeClient(pages={"buscador_iniciativas/5272": text("search-5272.html.gz")})
        read, gaps = gtr.pull_missing_initiatives(conn, c, "2026-10-09", tax=tiny_taxonomy(),
                                                  log=lambda *_: None)
        self.assertEqual(read, 1)
        self.assertTrue(any(u.endswith("/buscador_iniciativas/5272") for u in c.requested))
        # Every other number the session names, and the rest of the
        # watchlist, were 404s here: gaps, disclosed.
        self.assertGreater(gaps, 0)
        row = conn.execute("SELECT conocio_pleno FROM gt_initiatives WHERE numero='5272'").fetchone()
        self.assertEqual(row[0], "2017-04-27")
        areas = {a for (a,) in conn.execute(
            "SELECT areas FROM gt_divisions WHERE iniciativa='5272'")}
        self.assertEqual(areas, {"[1, 5, 6, 9]"})


class Classification(unittest.TestCase):
    def test_unclassified_without_a_taxonomy(self):
        conn = store()
        gtr.pull_initiatives(conn, Pull().client(), "2026-10-09", tax=None)
        nulls = conn.execute("SELECT COUNT(*) FROM gt_initiatives WHERE areas IS NULL").fetchone()[0]
        watched = conn.execute("SELECT areas FROM gt_initiatives WHERE numero='6453'").fetchone()[0]
        self.assertEqual(json.loads(watched), [6])
        self.assertEqual(nulls, 500 - 3)   # 6453, 6607, 6278 are watched and in the listing

    def test_a_vote_inherits_its_initiative(self):
        conn, tax = store(), tiny_taxonomy()
        read, ours, gaps = gtr.pull_initiatives(conn, Pull().client(), "2026-10-09", tax=tax)
        self.assertEqual(read, 500)
        sex_ed = json.loads(conn.execute(
            "SELECT areas FROM gt_initiatives WHERE numero='6453'").fetchone()[0])
        self.assertEqual(sex_ed, [6])
        d = {"question_id": "1", "session_id": "1", "date": "2026-01-01",
             "title": "APROBACIÓN EN TERCER DEBATE DEL PROYECTO DE DECRETO QUE DISPONE APROBAR "
                      "LA INICIATIVA DE LEY 6453", "iniciativa": "6453"}
        key, areas = gtr.store_division(conn, d, tax, "2026-10-09")
        self.assertEqual(areas, [6])

    def test_the_5272_votes_carry_the_watchlist_without_a_taxonomy(self):
        conn = store()
        for v in gtr.parse_session(text("session-41013.html.gz")):
            gtr.store_division(conn, v, None, "2026-10-09")
        rows = conn.execute("SELECT areas FROM gt_divisions WHERE iniciativa='5272'").fetchall()
        self.assertEqual(len(rows), 15)
        self.assertTrue(all(json.loads(a) == [1, 5, 6, 9] for (a,) in rows))
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM gt_divisions WHERE iniciativa IS NULL AND areas IS NOT NULL"
        ).fetchone()[0], 0)

    def test_reclassify_is_offline_and_idempotent(self):
        conn, tax = store(), tiny_taxonomy()
        gtr.pull_initiatives(conn, Pull().client(), "2026-10-09", tax=None)
        changed, _ = gtr.reclassify(conn, tax, log=lambda *_: None)
        self.assertGreater(changed, 0)
        self.assertEqual(gtr.reclassify(conn, tax, log=lambda *_: None), (0, 0))


class Schema(unittest.TestCase):
    def test_tables_are_declared(self):
        for t in gt_store.TABLES:
            self.assertIn(t, db.TABLES)

    def test_watchlist_is_keyed_by_number(self):
        w = gt_store.watchlist()
        self.assertIn("5272", w)
        self.assertTrue(all(k.isdigit() for k in w))


if __name__ == "__main__":
    unittest.main()
