"""IT2 (Chris, 10 October 2026): the Camera's own dati.camera.it SPARQL
service as the backup, or main when quicker, to Openpolis for Camera votes,
keeping vote keys stable (tools/it_rollcalls.py). No network: the two
camera_sparql_* fixtures are real answers saved on 10 October 2026."""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, it_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "it")


def _load():
    spec = importlib.util.spec_from_file_location(
        "it_rollcalls_it2", os.path.join(ROOT, "tools", "it_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


itr = _load()
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = itr.empty_watchlist()
QUIET = dict(log=lambda *_: None)


def raw(name):
    with open(os.path.join(FIX, name + ".json"), "rb") as fh:
        return fh.read()


def rows(name):
    data = json.loads(raw(name).decode("utf-8"), strict=False)
    return [{k: v.get("value") for k, v in b.items()} for b in data["results"]["bindings"]]


def fixture(name):
    return json.loads(raw(name).decode("utf-8"))


def store():
    return db.init_db(sqlite3.connect(":memory:"))


class FakeClient:
    """SPARQL by slug prefix (bytes), JSON by slug; None is a refusal."""

    def __init__(self, sparql=None, json_by_slug=None):
        self.sparql = sparql or {}
        self.json = json_by_slug or {}
        self.asked = []

    def get_bytes(self, url, feed, slug, **kw):
        self.asked.append(slug)
        for prefix, name in self.sparql.items():
            if slug.startswith(prefix):
                if name is None:
                    raise FetchError(url, feed, slug, 1, "HTTP Error 502")
                return raw(name)
        return b'{"results": {"bindings": []}}'

    def get_json(self, url, feed, slug, **kw):
        self.asked.append(slug)
        answer = self.json.get(slug)
        if answer is None:
            raise FetchError(url, feed, slug, 1, "HTTP Error 503")
        return answer


class QueryTests(unittest.TestCase):
    def test_the_range_never_combines_and_with_less_than(self):
        # The Camera's firewall rejects a query holding both (10 October 2026).
        q = itr.q_camera_votes(19, "20261007", "20261009")
        self.assertNotIn("&&", q)
        self.assertIn('FILTER(?date >= "20261007") FILTER(?date < "20261009")', q)

    def test_months_cover_the_window(self):
        self.assertEqual(itr._months("2026-09-20", "2026-10-11"),
                         [("20260920", "20261001"), ("20261001", "20261101")])

    def test_source_setting(self):
        with mock.patch.dict(os.environ, {"IT_CAMERA_SOURCE": "camera"}):
            self.assertEqual(itr.camera_source(), "camera")
        with mock.patch.dict(os.environ, {"IT_CAMERA_SOURCE": "nonsense"}):
            self.assertEqual(itr.camera_source(), "auto")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(itr.camera_source(), "auto")


class ParseTests(unittest.TestCase):
    def test_the_list_keys_votes_as_openpolis_does(self):
        votes = itr.parse_camera_sparql_list(rows("camera_sparql_votes_20261007"))
        self.assertEqual(len(votes), 35)
        final = votes[0]
        self.assertEqual(final["key"], "camera-vs19_723_001")
        self.assertEqual((final["sitting"], final["number"], final["date"]), (723, 1, "2026-10-08"))
        self.assertEqual(final["title"], "PDL 2822-B - VOTO FINALE")   # as Openpolis titles it
        self.assertEqual((final["ayes"], final["noes"], final["abstentions"]), (227, 164, 0))
        self.assertEqual((final["outcome"], final["is_final"], final["is_secret"]),
                         ("Approvata", 1, True))
        op = {v["key"]: v for v in itr.parse_camera_list(
            [fixture("camera_voting_vs19_723_001") | {"identifier": "vs19_723_001"}])}
        self.assertEqual(set(op), {"camera-vs19_723_001"})
        self.assertEqual(op["camera-vs19_723_001"]["title"], final["title"])

    def test_titles_match_openpolis(self):
        self.assertEqual(
            itr.camera_sparql_title("Votazione Ordine del giorno 9/887 E ABB./19 PDL n. 0887",
                                    "Ordine del giorno n. 9/887 E ABB./19 ZAN ALESSANDRO (PD-IDP)"),
            fixture("camera_voting_vs19_147_041")["title"])
        self.assertEqual(itr.camera_sparql_title("Votazione finale ", "PDL 2822-B - VOTO FINALE"),
                         "PDL 2822-B - VOTO FINALE")

    def test_the_bill_is_inferred_from_either_source(self):
        votes = itr.parse_camera_sparql_list(rows("camera_sparql_votes_20261007"))
        sitting = [v for v in votes if v["sitting"] == 722]
        bills = itr.infer_camera_bills(sitting)
        self.assertEqual(bills["camera-vs19_722_004"], ("19/C.2822-B", 0))   # 'ODG 9/2822-B/7'

    def test_positions(self):
        pos = itr.parse_camera_sparql_positions(rows("camera_sparql_positions_vs19_147_041"))
        self.assertEqual(len(pos), 399)
        counts = {}
        for _cid, _name, _grp, p in pos:
            counts[p] = counts.get(p, 0) + 1
        # The Openpolis totals for the same vote: 103 ayes, 159 noes, 13 abstentions.
        self.assertEqual((counts["aye"], counts["no"], counts["abstain"]), (103, 159, 13))
        self.assertEqual(counts["absent"], 124)        # absent and on mission alike
        cuperlo = [p for p in pos if p[0] == "302422"][0]
        self.assertEqual(cuperlo, ("302422", "CUPERLO GIANNI", "PD-IDP", "aye"))


class NameTests(unittest.TestCase):
    def _names(self, members):
        conn = store()
        for key, name, grp in members:
            itr.upsert_member(conn, key, "camera", name, grp, None, "2026-10-10")
        return conn, itr.CameraNames(conn)

    def test_whole_name_in_either_order(self):
        _conn, names = self._names([("C:207", "Davide Aiello", "M5S")])
        self.assertEqual(names.resolve("307394", "AIELLO DAVIDE", "M5S"), ("C:207", True))

    def test_the_name_in_use_by_surname_within_the_group(self):
        _conn, names = self._names([("C:1", "Giovanni Cuperlo", "PD-IDP"),
                                    ("C:2", "Andrea Giorgio Felice Maria Orsini", "FI-PPE"),
                                    ("C:3", "Carmela Di Lauro", "M5S")])
        self.assertEqual(names.resolve("302422", "CUPERLO GIANNI", "PD-IDP"), ("C:1", True))
        self.assertEqual(names.resolve("300299", "ORSINI ANDREA", "FI-PPE"), ("C:2", True))
        self.assertEqual(names.resolve("307210", "DI LAURO CARMEN", "M5S"), ("C:3", True))

    def test_never_a_guess(self):
        _conn, names = self._names([("C:1", "Mario Rossi", "FDI"), ("C:2", "Luca Rossi", "FDI")])
        self.assertEqual(names.resolve("999", "ROSSI GIOVANNI", "FDI"), ("CD:999", False))
        self.assertEqual(names.resolve("998", "BIANCHI ANNA", None), ("CD:998", False))

    def test_a_matched_camera_id_is_remembered(self):
        conn, names = self._names([("C:207", "Davide Aiello", "M5S")])
        conn.execute("UPDATE it_members SET camera_id='307394' WHERE member_key='C:207'")
        self.assertEqual(itr.CameraNames(conn).resolve("307394", "SOMEONE ELSE"), ("C:207", True))


class PullTests(unittest.TestCase):
    def test_openpolis_refused_the_camera_lists_the_same_keys(self):
        conn = store()
        client = FakeClient(sparql={"camera-sparql-votes-19-202610": "camera_sparql_votes_20261007"})
        read, ours, gaps = itr.pull_camera_votes(conn, client, "2026-10-09", TAX, WL,
                                                 source="auto", **QUIET)
        self.assertEqual(gaps, 0)
        self.assertEqual(read, 35)
        self.assertIn("camera-votings-19-p1", client.asked)        # Openpolis was asked first
        row = conn.execute("SELECT bill_key, ayes, noes, title FROM it_divisions "
                           "WHERE division_key='camera-vs19_723_001'").fetchone()
        self.assertEqual(row, ("19/C.2822-B", 227, 164, "PDL 2822-B - VOTO FINALE"))

    def test_openpolis_only_records_a_refusal_as_a_gap(self):
        conn = store()
        read, ours, gaps = itr.pull_camera_votes(conn, FakeClient(), "2026-10-09", TAX, WL,
                                                 source="openpolis", **QUIET)
        self.assertEqual((read, gaps), (0, 1))

    def _division(self, conn, key, areas):
        conn.execute("INSERT INTO it_divisions (division_key, chamber, legislature, date, title, "
                     "areas, positions_fetched) VALUES (?, 'camera', 19, '2023-07-26', 't', ?, 0)",
                     (key, json.dumps(areas)))

    def _openpolis_members(self, conn):
        for mv in fixture("camera_voting_vs19_147_041")["members_votes"]:
            m = mv["membership"]
            itr.upsert_member(conn, "C:{0}".format(m["id"]), "camera",
                              "{0} {1}".format(m["given_name"], m["family_name"]),
                              mv["group"]["acronym"], None, "2026-10-10")

    def test_off_our_ground_the_quicker_camera_service_goes_first(self):
        conn = store()
        self._openpolis_members(conn)
        self._division(conn, "camera-vs19_147_041", [])
        client = FakeClient(sparql={"camera-sparql-positions-vs19_147_041":
                                    "camera_sparql_positions_vs19_147_041"})
        fetched, gaps = itr.pull_positions(conn, client, "2026-10-10", {}, source="auto", **QUIET)
        self.assertEqual((fetched, gaps), (1, 0))
        self.assertNotIn("camera-voting-vs19_147_041", client.asked)
        self.assertEqual(conn.execute("SELECT positions_source FROM it_divisions").fetchone()[0],
                         "camera")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM it_votes").fetchone()[0], 399)
        # The six Openpolis members keep their keys; the Camera says absent
        # where Openpolis says on mission (Lucia Albano).
        got = dict(conn.execute("SELECT member_key, position FROM it_votes "
                                "WHERE member_key LIKE 'C:%'"))
        self.assertEqual(len(got), 6)
        self.assertEqual(got["C:208"], "absent")
        self.assertEqual(conn.execute("SELECT camera_id FROM it_members WHERE member_key='C:207'"
                                      ).fetchone()[0], "307394")

    def test_on_our_ground_openpolis_goes_first(self):
        conn = store()
        self._division(conn, "camera-vs19_147_041", [10])
        client = FakeClient(json_by_slug={
            "camera-voting-vs19_147_041": fixture("camera_voting_vs19_147_041")})
        fetched, gaps = itr.pull_positions(conn, client, "2026-10-10", {}, source="auto", **QUIET)
        self.assertEqual((fetched, gaps), (1, 0))
        self.assertEqual(conn.execute("SELECT positions_source FROM it_divisions").fetchone()[0],
                         "openpolis")
        self.assertEqual(dict(conn.execute("SELECT member_key, position FROM it_votes"))["C:208"],
                         "mission")

    def test_openpolis_down_on_our_ground_falls_back_to_the_camera(self):
        conn = store()
        self._openpolis_members(conn)
        self._division(conn, "camera-vs19_147_041", [10])
        client = FakeClient(sparql={"camera-sparql-positions-vs19_147_041":
                                    "camera_sparql_positions_vs19_147_041"})
        fetched, gaps = itr.pull_positions(conn, client, "2026-10-10", {}, source="auto", **QUIET)
        self.assertEqual((fetched, gaps), (1, 0))
        self.assertEqual(conn.execute("SELECT positions_source FROM it_divisions").fetchone()[0],
                         "camera")

    def test_both_refusing_is_a_gap_and_the_vote_is_retried(self):
        conn = store()
        self._division(conn, "camera-vs19_147_041", [10])
        client = FakeClient(sparql={"camera-sparql-positions": None})
        fetched, gaps = itr.pull_positions(conn, client, "2026-10-10", {}, source="auto", **QUIET)
        self.assertEqual((fetched, gaps), (0, 1))
        self.assertEqual(conn.execute("SELECT positions_fetched FROM it_divisions").fetchone()[0], 0)


class SchemaTests(unittest.TestCase):
    def test_an_old_store_gains_the_columns(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE it_members (member_key TEXT PRIMARY KEY, chamber TEXT)")
        conn.execute("CREATE TABLE it_divisions (division_key TEXT PRIMARY KEY, chamber TEXT, "
                     "bill_key TEXT)")
        it_store.ensure_schema(conn)
        self.assertIn("camera_id", {r[1] for r in conn.execute("PRAGMA table_info(it_members)")})
        self.assertIn("positions_source",
                      {r[1] for r in conn.execute("PRAGMA table_info(it_divisions)")})


if __name__ == "__main__":
    unittest.main()
