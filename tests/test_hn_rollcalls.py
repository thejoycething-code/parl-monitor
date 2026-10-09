"""Honduras, Congreso Nacional: deputies, sessions, agendas, expedientes,
press releases and La Gaceta (tools/hn_rollcalls.py). No network: real
responses saved on 9 October 2026 under tests/fixtures/hn/ (the deputies'
identity numbers and e-mails replaced before saving)."""

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

from src import db, hn_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "hn")


def _load():
    spec = importlib.util.spec_from_file_location(
        "hn_rollcalls", os.path.join(ROOT, "tools", "hn_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hnr = _load()


def raw(name):
    path = os.path.join(FIX, name)
    opener = gzip.open if name.endswith(".gz") else open
    with opener(path, "rb") as fh:
        return fh.read()


def js(name):
    return json.loads(raw(name).decode("utf-8"))


def store():
    conn = sqlite3.connect(":memory:")
    db.init_db(conn)
    return conn


TINY_TAXONOMY = """version: test
areas:
  1_abortion:
    tier1: ["no nacido*"]
    tier2: []
  6_parental_rights_education:
    tier1: ["derechos parentales"]
    tier2: []
  8_freedom_of_religion:
    tier1: ["lectura de la Biblia"]
    tier2: []
  11_migration:
    tier1: [migrante*]
    tier2: []
exclusions_global: [vida]
"""


def tiny_taxonomy():
    fh = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
    fh.write(TINY_TAXONOMY)
    fh.close()
    try:
        return hnr.load_taxonomy(fh.name)
    finally:
        os.unlink(fh.name)


class FakeClient:
    """Serves the fixtures by URL; anything else is a FetchError."""

    def __init__(self, fail=()):
        self.calls = []
        self.fail = set(fail)
        self.routes = {
            hnr.API + "/diputados": "diputados.json",
            hnr.API + "/sesiones?page=1&pageSize=100": "sesiones.json",
            hnr.API + "/sesiones/orden-del-dia?roomId=175": "orden-175.json",
            hnr.API + "/sesiones/175": "sesion-175.json",
            hnr.API + "/expediente?estado=6": "expediente-6.json",
            hnr.NEWS_API.format(limit=100, skip=0): "news.json",
            hnr.GACETA_MONTH.format(year=2026, month="septiembre"): "gaceta-2026-09.html.gz",
        }

    def _route(self, url):
        self.calls.append(url)
        if url in self.fail or url not in self.routes:
            raise FetchError(url, "hn", "x", 1, "not in fixtures")
        return raw(self.routes[url])

    def get_json(self, url, feed, slug, **kw):
        return json.loads(self._route(url).decode("utf-8"))

    def get_text(self, url, feed, slug, **kw):
        return self._route(url).decode("utf-8")


class Parsers(unittest.TestCase):
    def test_members_drop_the_identity_number_and_email(self):
        members = hnr.parse_members(js("diputados.json")["data"])
        self.assertEqual(len(members), 4)
        m = members[0]
        self.assertEqual(m["user_id"], 114)
        self.assertEqual(m["party"], "PARTIDO DEMOCRATA CRISTIANO DE HONDURAS")
        self.assertEqual(m["departamento"], "FRANCISCO MORAZAN")
        for row in members:
            self.assertNotIn("userDocument", row)
            self.assertNotIn("email", row)
            self.assertFalse(any("@" in str(v) for v in row.values()))

    def test_sessions(self):
        rows = hnr.parse_sessions(js("sesiones.json")["data"])
        self.assertEqual([r["room_id"] for r in rows], [175, 174, 173])
        self.assertEqual(rows[0]["list_name"], "Plenaria")
        self.assertEqual(rows[0]["schedule"], "2026-05-20 08:00:00")

    def test_agenda_items_carry_their_expediente_and_no_result(self):
        list_name, items = hnr.parse_agenda(js("orden-175.json")["data"])
        self.assertEqual(list_name, "Plenaria")
        self.assertEqual(len(items), 20)
        first = items[0]
        self.assertEqual(first["room_item_id"], 681)
        self.assertEqual(first["project_id"], 567)
        self.assertEqual(first["project_number"], "EXP-2026-0721")
        # The finding the scope doc rests on: no item carries a result.
        self.assertTrue(all(i["resultado"] is None for i in items))

    def test_statuses_come_from_the_session_detail(self):
        statuses = hnr.parse_session_detail(js("sesion-175.json")["data"])
        self.assertEqual(statuses[681], (0, 1))
        self.assertEqual(statuses[735], (4, 1))

    def test_expedientes(self):
        rows = hnr.parse_expedientes(js("expediente-6.json")["data"])
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(r["estado"] == "Aprobado" for r in rows))
        self.assertTrue(all(r["numero"].startswith("EXP-2026-") for r in rows))

    def test_unwrap_refuses_an_error_reply(self):
        with self.assertRaises(ValueError):
            hnr.unwrap({"isError": True, "message": "The value 'Aprobado' is not valid."}, "x")
        self.assertEqual(hnr.unwrap({"isError": False, "data": {"a": 1}}, "x"), {"a": 1})

    def test_news_body_is_decoded_from_the_jwt_payload(self):
        total, posts = hnr.parse_news(js("news.json"))
        self.assertEqual(total, 2405)
        bible = [p for p in posts if "Biblia" in p["title"]][0]
        self.assertIn("Secretaría de Educación", bible["body"])
        self.assertTrue(bible["created_at"].startswith("2026-09-22"))
        self.assertEqual(hnr.news_body("not-a-jwt"), "")

    def test_gazette_reads_the_issue_off_the_link_not_the_typed_title(self):
        issues, starts = hnr.parse_gazette(raw("gaceta-2026-09.html.gz").decode("utf-8"))
        self.assertEqual(len(issues), 12)
        numbers = [i["issue"] for i in issues]
        # '20260909 -37242' and '20260912- 37245' are typed by hand.
        self.assertIn(37242, numbers)
        self.assertIn(37245, numbers)
        by = {i["issue"]: i for i in issues}
        self.assertEqual(by[37241]["date"], "2026-09-08")
        self.assertIn("Decreto No. 151-2026", by[37241]["summary"])
        self.assertTrue(by[37241]["url"].endswith("/20260908-37241/download"))
        self.assertEqual(starts, [12, 24])


class Pulls(unittest.TestCase):
    TODAY = "2026-06-01"

    def test_full_pull_without_a_taxonomy_leaves_areas_null(self):
        conn, client = store(), FakeClient()
        self.assertEqual(hnr.pull_members(conn, client, self.TODAY, log=lambda *a: None), (4, 0))
        self.assertEqual(hnr.pull_sessions(conn, client, self.TODAY), (3, 0))
        read, stored, ours, gaps = hnr.pull_agendas(conn, client, self.TODAY, limit=1,
                                                    log=lambda *a: None)
        self.assertEqual((read, stored, ours), (1, 20, 0))
        nulls = conn.execute("SELECT COUNT(*) FROM hn_agenda_items WHERE areas IS NULL").fetchone()
        self.assertEqual(nulls[0], 20)
        self.assertEqual(conn.execute(
            "SELECT status FROM hn_agenda_items WHERE room_item_id=735").fetchone()[0], 4)
        self.assertEqual(conn.execute(
            "SELECT agenda_items FROM hn_sessions WHERE room_id=175").fetchone()[0], 20)
        # Agenda-linked files land in hn_bills with no estado yet.
        self.assertEqual(conn.execute(
            "SELECT estado FROM hn_bills WHERE project_id=567").fetchone()[0], None)
        # No DNI anywhere in the store.
        cols = [r[1] for r in conn.execute("PRAGMA table_info(hn_members)")]
        self.assertNotIn("user_document", cols)

    def test_unread_and_recent_sessions_are_due(self):
        conn, client = store(), FakeClient()
        hnr.pull_sessions(conn, client, self.TODAY)
        self.assertEqual(hnr.sessions_to_read(conn, self.TODAY), [175, 174, 173])
        conn.execute("UPDATE hn_sessions SET agenda_read='2026-05-21'")
        # 20 May is within 21 days of 1 June; 18 and 19 May too.
        self.assertEqual(len(hnr.sessions_to_read(conn, self.TODAY)), 3)
        self.assertEqual(hnr.sessions_to_read(conn, "2026-07-01"), [])

    def test_failed_agenda_is_a_gap_and_the_rest_continue(self):
        conn = store()
        client = FakeClient(fail={hnr.API + "/sesiones/orden-del-dia?roomId=175"})
        hnr.pull_sessions(conn, client, self.TODAY)
        read, stored, ours, gaps = hnr.pull_agendas(conn, client, self.TODAY,
                                                    log=lambda *a: None)
        # 174 and 173 are not in the fixtures either: three gaps, nothing read.
        self.assertEqual((read, gaps), (0, 3))
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM gaps WHERE feed='hn-rollcalls'").fetchone()[0], 3)

    def test_expedientes_fill_estado_and_an_agenda_sighting_never_blanks_it(self):
        conn, client = store(), FakeClient()
        read, ours, gaps = hnr.pull_expedientes(conn, client, self.TODAY,
                                                log=lambda *a: None)
        self.assertEqual((read, gaps), (10, 3))   # only estado=6 is in the fixtures
        pid, numero = conn.execute(
            "SELECT project_id, numero FROM hn_bills LIMIT 1").fetchone()
        hnr.store_bill(conn, {"project_id": pid, "numero": numero, "titulo": "x"},
                       None, "2026-06-02")
        self.assertEqual(conn.execute("SELECT estado FROM hn_bills WHERE project_id=?",
                                      (pid,)).fetchone()[0], "Aprobado")

    def test_news_and_classification_with_a_taxonomy(self):
        conn, client = store(), FakeClient()
        tax = tiny_taxonomy()
        # The fixture keeps two releases; `since` stops the walk at them, as
        # NEWS_SINCE stops the first run at the start of the legislature.
        read, new, ours, gaps = hnr.pull_news(conn, client, self.TODAY, tax=tax,
                                              log=lambda *a: None, since="2026-10-01")
        self.assertEqual((read, new, gaps), (2, 2, 0))
        self.assertGreaterEqual(ours, 1)
        areas = json.loads(conn.execute(
            "SELECT areas FROM hn_news WHERE title LIKE '%Biblia%'").fetchone()[0])
        self.assertIn(8, areas)
        # The second pull meets nothing new on its first page and stops.
        client.calls.clear()
        read, new, ours, gaps = hnr.pull_news(conn, client, self.TODAY, tax=tax,
                                              log=lambda *a: None)
        self.assertEqual(new, 0)
        self.assertEqual(len(client.calls), 1)

    def test_gazette_first_run_reads_every_month_then_two(self):
        conn = store()
        self.assertEqual(hnr.gazette_months(conn, "2026-03-05"),
                         [(2026, 1), (2026, 2), (2026, 3)])
        conn.execute("INSERT INTO hn_gazette (issue) VALUES (1)")
        self.assertEqual(hnr.gazette_months(conn, "2026-01-05"), [(2025, 12), (2026, 1)])

    def test_gazette_pull_follows_the_month_pages(self):
        conn, client = store(), FakeClient()
        conn.execute("INSERT INTO hn_gazette (issue) VALUES (1)")
        read, ours, gaps = hnr.pull_gazette(conn, client, "2026-09-30", log=lambda *a: None)
        # August fails (not in fixtures), September page 1 reads, start=12 fails.
        self.assertEqual(read, 12)
        self.assertEqual(gaps, 2)
        self.assertIn(hnr.GACETA_MONTH.format(year=2026, month="septiembre") + "?start=12",
                      client.calls)

    def test_watchlist_lends_areas_by_number_without_a_taxonomy(self):
        path = os.path.join(tempfile.mkdtemp(), "wl.yaml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('expedientes:\n  "EXP-2026-0721": {areas: [9], why: "test"}\n')
        hn_store._WATCH.clear()
        old = hn_store.WATCHLIST
        hn_store.WATCHLIST = path
        try:
            areas, terms, tier = hnr.classify(None, "EXP-2026-0721", "Proyecto Uremo")
            self.assertEqual((areas, tier), ([9], 2))
            self.assertEqual(hnr.classify(None, "EXP-2026-0001", "x"), (None, [], None))
        finally:
            hn_store.WATCHLIST = old
            hn_store._WATCH.clear()

    def test_reclassify_applies_a_new_taxonomy_offline(self):
        conn, client = store(), FakeClient()
        hnr.pull_news(conn, client, self.TODAY, log=lambda *a: None, since="2026-10-01")
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM hn_news WHERE areas IS NOT NULL").fetchone()[0], 0)
        changed = hnr.reclassify(conn, tiny_taxonomy(), log=lambda *a: None)
        self.assertEqual(changed, 2)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM hn_news WHERE areas IS NULL").fetchone()[0], 0)


class Shape(unittest.TestCase):
    def test_tables_are_declared(self):
        for t in hn_store.TABLES:
            self.assertIn(t, db.TABLES)

    def test_watchlist_file_parses_and_is_keyed_by_number(self):
        hn_store._WATCH.clear()
        wl = hn_store.watchlist()
        for key in wl:
            self.assertRegex(key, r"^EXP-\d{4}-\d{4}$")

    def test_job_publishes_raw_before_store(self):
        with open(os.path.join(ROOT, "jobs", "hn-weekly.sh"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertLess(src.index("raw_state.py --push"), src.index("db_state.py --push"))


if __name__ == "__main__":
    unittest.main()
