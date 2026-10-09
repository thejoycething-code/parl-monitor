"""The Dominican Republic's Congress: Camara de Diputados iniciativas,
sessions, votes and positions (tools/do_rollcalls.py). No network: every
fixture is a real SIL Ciudadano reply archived on 9 October 2026, trimmed
to a few rows (tests/fixtures/do/)."""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, do_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "do")
API = "https://www.diputadosrd.gob.do/sil/api/"


def _load():
    spec = importlib.util.spec_from_file_location(
        "do_rollcalls", os.path.join(ROOT, "tools", "do_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dor = _load()
TAX = dor.load_taxonomy(os.path.join(FIX, "taxonomy-es-test.yaml"))
WL = dor.empty_watchlist()
TODAY = "2026-10-09"


def fx(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as handle:
        return json.load(handle)


def store():
    return db.init_db(sqlite3.connect(":memory:"))


def empty():
    return {"page": 1, "pageSize": 10, "total": 0, "results": []}


class FakeClient:
    """get_json from a dict of url prefix -> payload (longest prefix wins);
    a payload that is an Exception is raised; anything unrouted is a 400."""

    def __init__(self, routes=None):
        self.routes = routes or {}
        self.calls = []

    def get_json(self, url, feed, slug, **kw):
        self.calls.append(url)
        for prefix in sorted(self.routes, key=len, reverse=True):
            if url.startswith(prefix):
                payload = self.routes[prefix]
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise FetchError(url, "t", "t", 1, Exception("HTTP Error 400: Bad Request"))


def vote_routes():
    return {
        API + "sesion/sesiones?page=1&": fx("sessions_p1.json"),
        API + "sesion/votaciones?page=1&id=134544&": fx("session_votes_134544_p1.json"),
        API + "sesion/votaciones?page=1&id=134514&": fx("session_votes_134514_p1.json"),
        API + "votacion/iniciativas/?page=1&id=22789&": fx("vote_bills_22789.json"),
        API + "votacion/iniciativas/?page=1&id=22790&": fx("vote_bills_22790.json"),
        API + "votacion/iniciativas/?page=1&id=22379&": fx("vote_bills_22379.json"),
        API + "votacion/legisladores/?page=1&id=22379&": fx("positions_22379_p1.json"),
        API + "votacion/legisladores/?page=2&id=22379&": fx("positions_22379_p2.json"),
    }


class BillTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        self.client = FakeClient({
            API + "iniciativa/getIniciativas?page=1&": fx("bills_2024-2028_p1.json")})

    def test_bills_stored_by_number_with_status_and_areas(self):
        read, ours, gaps = dor.pull_bills(self.conn, self.client, TODAY, tax=TAX, wl=WL,
                                          watch={})
        self.assertEqual((read, ours, gaps), (3, 2, 0))
        row = self.conn.execute(
            "SELECT sil_id, period, kind, origin, status, law_number, promulgated, areas "
            "FROM do_bills WHERE bill_key='04557-2024-2028-CD'").fetchone()
        self.assertEqual(row[0], 157019)
        self.assertEqual(row[1], "2024-2028")
        self.assertEqual(row[4], "Promulgado")
        self.assertEqual(json.loads(row[7]), [1])   # 'Código Penal', accents folded
        parents = self.conn.execute("SELECT areas, matched_terms FROM do_bills "
                                    "WHERE bill_key='06115-2024-2028-CD'").fetchone()
        self.assertEqual(json.loads(parents[0]), [6])
        reading = self.conn.execute("SELECT areas FROM do_bills "
                                    "WHERE bill_key='06465-2024-2028-CD'").fetchone()
        self.assertEqual(json.loads(reading[0]), [])

    def test_the_period_id_rides_on_every_request(self):
        dor.pull_bills(self.conn, self.client, TODAY, tax=TAX, wl=WL, watch={})
        self.assertTrue(all(u.endswith("periodoId=2761") for u in self.client.calls))

    def test_watchlist_adds_areas_by_key_never_title(self):
        watch = {"06465-2024-2028-CD": ([6], "test")}
        dor.pull_bills(self.conn, self.client, TODAY, tax=TAX, wl=WL, watch=watch)
        areas, terms = self.conn.execute("SELECT areas, matched_terms FROM do_bills "
                                         "WHERE bill_key='06465-2024-2028-CD'").fetchone()
        self.assertEqual(json.loads(areas), [6])
        self.assertIn("watch:06465-2024-2028-CD", json.loads(terms))

    def test_a_failed_page_is_a_gap_not_a_crash(self):
        client = FakeClient({API + "iniciativa/getIniciativas?page=1&":
                             FetchError("u", "t", "t", 3, Exception("timed out"))})
        read, ours, gaps = dor.pull_bills(self.conn, client, TODAY, tax=TAX, wl=WL, watch={})
        self.assertEqual(read, 0)
        self.assertGreaterEqual(gaps, 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0], gaps)

    def test_parse_bill_single_record(self):
        b = dor.parse_bill(fx("bill_159796.json"))
        self.assertEqual(b["bill_key"], "06342-2024-2028-CD")
        self.assertEqual(b["deposited"], "2026-09-15")
        self.assertEqual(b["status"], "Enviado a Comisión")
        self.assertIsNone(b["law_number"])


class VoteTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()

    def run_votes(self, routes=None, watch=None, contested_days=dor.CONTESTED_DAYS):
        client = FakeClient(routes if routes is not None else vote_routes())
        out = dor.pull_votes(self.conn, client, TODAY, tax=TAX, wl=WL, watch=watch or {},
                             contested_days=contested_days)
        return out, client

    def test_headers_stored_for_every_vote_with_counts(self):
        (stored, ours, pos, gaps), _ = self.run_votes()
        self.assertEqual((stored, ours, pos, gaps), (3, 0, 0, 0))
        row = self.conn.execute(
            "SELECT session_id, session_number, number, date, yes, no, present, members "
            "FROM do_divisions WHERE division_key='cd/22379'").fetchone()
        self.assertEqual(row[0], 134514)
        self.assertEqual(row[3], "2026-06-18")
        self.assertEqual(row[4:], (27, 140, 171, 190))

    def test_vote_inherits_the_linked_and_named_iniciativas(self):
        self.run_votes()
        refs = json.loads(self.conn.execute(
            "SELECT bill_refs FROM do_divisions WHERE division_key='cd/22790'").fetchone()[0])
        # the SIL's own link, then the numbers the motion names itself
        self.assertIn("05421-2024-2028-CD", refs)
        self.assertIn("06043-2024-2028-CD", refs)
        fiscal = json.loads(self.conn.execute(
            "SELECT bill_refs FROM do_divisions WHERE division_key='cd/22379'").fetchone()[0])
        self.assertEqual(fiscal, ["05950-2024-2028-CD"])

    def test_old_contested_vote_keeps_header_only_by_default(self):
        self.run_votes()
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM do_votes").fetchone()[0], 0)
        self.assertEqual(self.conn.execute(
            "SELECT positions_read FROM do_divisions WHERE division_key='cd/22379'").fetchone()[0], 0)

    def test_contested_vote_positions_across_pages(self):
        (_s, _o, pos, gaps), _ = self.run_votes(contested_days=400)
        self.assertEqual((pos, gaps), (1, 0))
        rows = self.conn.execute("SELECT position, COUNT(*) FROM do_votes "
                                 "WHERE division_key='cd/22379' GROUP BY position").fetchall()
        self.assertEqual(dict(rows), {"AU": 3, "NO": 3, "SI": 3, "SV": 3})
        read, n = self.conn.execute("SELECT positions_read, positions FROM do_divisions "
                                    "WHERE division_key='cd/22379'").fetchone()
        self.assertEqual((read, n), (1, 12))
        # each deputy becomes a member, party as at the vote
        party = self.conn.execute("SELECT party FROM do_votes WHERE division_key='cd/22379' "
                                  "AND member_key='cd/3358'").fetchone()
        self.assertEqual(party, ("PRM",))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM do_members").fetchone()[0], 12)

    def test_a_watched_bill_brings_its_votes_positions(self):
        routes = vote_routes()
        routes[API + "votacion/legisladores/?page=1&id=22790&"] = empty()
        (_s, _o, pos, _g), client = self.run_votes(
            routes=routes, watch={"05421-2024-2028-CD": ([6], "test")})
        self.assertEqual(pos, 1)
        self.assertTrue(any("legisladores/?page=1&id=22790" in u for u in client.calls))

    def test_second_run_skips_read_sessions_and_known_votes(self):
        self.run_votes()
        # Everything is older than the lookback, so a re-run stops at once.
        far = "2027-01-01"
        client = FakeClient(vote_routes())
        stored, _o, _p, gaps = dor.pull_votes(self.conn, client, far, tax=TAX, wl=WL, watch={})
        self.assertEqual((stored, gaps), (0, 0))
        self.assertFalse(any("votaciones" in u for u in client.calls))

    def test_a_vote_whose_link_fails_leaves_the_session_unread(self):
        routes = vote_routes()
        routes[API + "votacion/iniciativas/?page=1&id=22790&"] = FetchError(
            "u", "t", "t", 3, Exception("timed out"))
        (stored, _o, _p, gaps), _ = self.run_votes(routes=routes)
        self.assertEqual((stored, gaps), (2, 1))
        unread = self.conn.execute(
            "SELECT votes_read FROM do_sessions WHERE session_id=134544").fetchone()[0]
        self.assertIsNone(unread)

    def test_session_list_failure_is_one_gap(self):
        (stored, _o, _p, gaps), _ = self.run_votes(routes={})
        self.assertEqual((stored, gaps), (0, 1))

    def test_motion_numbers(self):
        self.assertEqual(dor.motion_bill_refs(
            "las iniciativas números: 06043-2024-2028-CD y 05421-2024-2028-CD, y 06043-2024-2028-CD"),
            ["06043-2024-2028-CD", "05421-2024-2028-CD"])

    def test_wants_positions(self):
        d = {"no": 0, "abstain": 0, "date": "2026-10-07"}
        self.assertFalse(dor.wants_positions(d, [], [], {}, TODAY))
        self.assertTrue(dor.wants_positions(d, [1], [], {}, TODAY))
        self.assertFalse(dor.wants_positions(d, [11], [], {}, TODAY))  # migration: collated only
        d["no"] = 2
        self.assertTrue(dor.wants_positions(d, [], [], {}, TODAY))
        d["date"] = "2026-06-01"
        self.assertFalse(dor.wants_positions(d, [], [], {}, TODAY))


class AreaTests(unittest.TestCase):
    def test_vote_takes_its_bills_areas_and_reclassify_rederives(self):
        conn = store()
        client = FakeClient(dict(vote_routes(), **{
            API + "iniciativa/getIniciativas?page=1&": fx("bills_2024-2028_p1.json")}))
        dor.pull_bills(conn, client, TODAY, tax=TAX, wl=WL, watch={})
        # Pretend the fiscal vote was on the Penal Code: re-point its link.
        dor.pull_votes(conn, client, TODAY, tax=TAX, wl=WL, watch={})
        conn.execute("UPDATE do_divisions SET bill_refs=? WHERE division_key='cd/22379'",
                     (json.dumps(["04557-2024-2028-CD"]),))
        conn.commit()
        dor.reclassify(conn, tax=TAX, log=lambda *_: None)
        areas = json.loads(conn.execute("SELECT areas FROM do_divisions "
                                        "WHERE division_key='cd/22379'").fetchone()[0])
        self.assertEqual(areas, [1])


class MemberTests(unittest.TestCase):
    def test_legislators_kept_institutions_skipped(self):
        conn = store()
        routes = {API + "legislador/legisladores?page=1&keyword=a&": fx("members_a_p1.json")}
        n, gaps = dor.pull_members(conn, FakeClient(routes), TODAY)
        # 'o' is unrouted: one gap, and the 'a' list is still stored
        self.assertEqual(gaps, 1)
        roles = {r for (r,) in conn.execute("SELECT role FROM do_members")}
        self.assertTrue(all(r.lower().startswith(("diputad", "senador")) for r in roles))
        self.assertEqual(n, conn.execute("SELECT COUNT(*) FROM do_members").fetchone()[0])
        self.assertIsNone(conn.execute("SELECT 1 FROM do_members WHERE member_key='cd/1503'")
                          .fetchone())   # Poder Ejecutivo

    def test_vote_name_never_replaces_list_name(self):
        conn = store()
        dor.store_member(conn, {"member_key": "cd/1", "legislador_id": 1, "name": "Ana Abreu",
                                "role": "Diputada", "party": "PRM", "province": "Santiago",
                                "constituency": None, "period": "2024-2028"}, TODAY)
        dor.store_member(conn, {"member_key": "cd/1", "legislador_id": 1, "name": "ABREU ANA",
                                "role": None, "party": "PRM", "province": None,
                                "constituency": None, "period": None}, TODAY,
                         overwrite_name=False)
        self.assertEqual(conn.execute("SELECT name, role, province FROM do_members").fetchone(),
                         ("Ana Abreu", "Diputada", "Santiago"))


class StoreTests(unittest.TestCase):
    def test_tables_declared_and_created(self):
        conn = store()
        for t in do_store.TABLES:
            self.assertIn(t, db.TABLES)
            conn.execute("SELECT * FROM {0} LIMIT 1".format(t))

    def test_watchlist_file_is_keyed_by_number(self):
        wl = do_store.watchlist()
        for key, (areas, why) in wl.items():
            self.assertRegex(key, r"^\d{5}-\d{4}-\d{4}-CD$")
            self.assertTrue(areas)
            self.assertTrue(why)

    def test_watchlist_has_no_em_dash(self):
        with open(do_store.WATCHLIST, encoding="utf-8") as handle:
            self.assertNotIn("—", handle.read())


if __name__ == "__main__":
    unittest.main()
