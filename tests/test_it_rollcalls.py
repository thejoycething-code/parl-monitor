"""Italian Parliament bills, Senate and Camera votes (tools/it_rollcalls.py).
No network: every response is a real one saved on 9 October 2026 under
tests/fixtures/it/ (the Camera vote details trimmed to six members)."""

import importlib.util
import json
import os
import re
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, it_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "it")


def _load():
    spec = importlib.util.spec_from_file_location(
        "it_rollcalls", os.path.join(ROOT, "tools", "it_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


itr = _load()
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = itr.empty_watchlist()


def rows(name):
    with open(os.path.join(FIX, name + ".json"), "rb") as fh:
        data = json.loads(fh.read().decode("utf-8"), strict=False)
    return [{k: v.get("value") for k, v in b.items()} for b in data["results"]["bindings"]]


def fixture(name):
    with open(os.path.join(FIX, name + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


def store():
    return db.init_db(sqlite3.connect(":memory:"))


def bills():
    out = itr.parse_bills(rows("senato_bills_56640") + rows("senato_bills_57360"))
    return itr.attach_subjects(out, rows("senato_teseo_56640") + rows("senato_teseo_57360"))


class FakeClient:
    """Serves fixtures by the feed slug the collector asks for."""

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
                with open(os.path.join(FIX, name + ".json"), "rb") as fh:
                    return fh.read()
        return b'{"results": {"bindings": []}}'

    def get_json(self, url, feed, slug, **kw):
        self.asked.append(slug)
        if slug not in self.json:
            raise FetchError(url, feed, slug, 1, "not in fixtures")
        return self.json[slug]


class TestTeseo(unittest.TestCase):
    def test_accented_capitals_and_elisions(self):
        self.assertEqual(itr.teseo_label("LIBERTA' RELIGIOSA"), "libertà religiosa")
        self.assertEqual(itr.teseo_label("SESSO DELLE PERSONE E SESSUALITA'"),
                         "sesso delle persone e sessualità")
        self.assertEqual(itr.teseo_label("DIRITTO DELL' UNIONE EUROPEA"),
                         "diritto dell' unione europea")


class TestBills(unittest.TestCase):
    def test_both_readings_of_the_surrogacy_bill(self):
        b = bills()
        cam, sen = b["19/C.887"], b["19/S.824"]
        self.assertEqual((cam["chamber"], cam["number"]), ("C", "887"))
        self.assertEqual(cam["id_ddl"], sen["id_ddl"])          # one bill, two readings
        self.assertEqual(sen["status"], "appr. definit. Legge")
        self.assertTrue(sen["law"].startswith("Legge "))
        self.assertIn("surrogazione", cam["title"])
        self.assertTrue(cam["subjects"], "TESEO general terms attached")
        self.assertEqual(cam["subjects"], sorted(cam["subjects"]))

    def test_keys_never_titles(self):
        """C.887 and S.824 share a title; they are two rows."""
        b = bills()
        self.assertEqual(b["19/C.887"]["title"], b["19/S.824"]["title"])
        self.assertNotEqual(b["19/C.887"]["key"], b["19/S.824"]["key"])

    def test_english_taxonomy_is_blind_and_the_watchlist_is_not(self):
        b = bills()["19/C.887"]
        b_no_watch = dict(b, key="19/C.000")
        self.assertEqual(itr.classify_bill(TAX, WL, b_no_watch).issue_areas, [])
        res = itr.classify_bill(TAX, WL, b)
        self.assertEqual(res.issue_areas, [10])
        self.assertIn("watch:19/C.887", res.watchlist_hits)

    def test_an_italian_term_list_matches_title_and_subjects(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
            fh.write('version: t\nareas:\n  10_surrogacy_embryology:\n'
                     '    tier1: ["surrogazione di maternità"]\n    tier2: []\n'
                     'exclusions_global: []\n')
        try:
            tax = filt.load_taxonomy(fh.name)
        finally:
            os.unlink(fh.name)
        res = itr.classify_bill(tax, WL, dict(bills()["19/S.824"], key="19/S.000"))
        self.assertEqual(res.issue_areas, [10])


class TestSenateVotes(unittest.TestCase):
    def setUp(self):
        self.votes = itr.parse_senate_votes(rows("senato_votes_232"))

    def test_sitting_232_is_the_surrogacy_bill(self):
        self.assertEqual(len(self.votes), 45)
        final = self.votes["senato-19-232-24"]
        self.assertIn("19/S.824", final["bill_keys"])
        self.assertEqual(final["bill_keys"], ["19/S.163", "19/S.245", "19/S.475", "19/S.824"])
        self.assertEqual(final["bill_key"], "19/S.163")
        self.assertEqual(final["date"], "2024-10-16")
        self.assertEqual(final["is_final"], 1)
        self.assertEqual(final["outcome"], "approvato")
        self.assertEqual((final["sitting"], final["number"]), (232, 24))

    def test_positions_add_up_to_the_totals(self):
        final = self.votes["senato-19-232-24"]
        pos = itr.parse_senate_positions(rows("senato_positions_19-232-24"))
        count = lambda p: sum(1 for _, x in pos if x == p)  # noqa: E731
        self.assertEqual(count("aye"), final["ayes"])
        self.assertEqual(count("no"), final["noes"])
        self.assertEqual(len({m for m, _ in pos}), len(pos))  # one position each
        self.assertTrue(all(m.startswith("S:") for m, _ in pos))

    def test_store_with_watchlist_lends_bill_areas(self):
        conn = store()
        for b in bills().values():
            itr.store_bill(conn, b, itr.classify_bill(TAX, WL, b), "2026-10-09")
        areas = itr.store_division(conn, self.votes["senato-19-232-24"], TAX, WL, "2026-10-09")
        self.assertEqual(areas, [10])
        own = conn.execute("SELECT own_areas FROM it_divisions WHERE division_key=?",
                           ("senato-19-232-24",)).fetchone()[0]
        self.assertEqual(json.loads(own), [])  # 'Votazione finale' says nothing itself


class TestSenators(unittest.TestCase):
    def test_groups_by_date(self):
        members = itr.parse_senators(rows("senato_senators"))
        self.assertGreaterEqual(len(members), 200)
        m = members["S:32600"]  # Castellone, M5S throughout the 19th
        self.assertEqual(m["name"], "Maria Domenica Castellone")
        self.assertEqual(itr.group_on(m["groups"], "2024-10-16"), "M5S")
        self.assertIsNone(itr.group_on(m["groups"], "2020-01-01"))


class TestCameraBills(unittest.TestCase):
    def test_title_forms(self):
        own = itr.camera_own_bill
        self.assertEqual(own("Ordine del giorno n. 9/887 E ABB./19 ZAN ALESSANDRO (PD-IDP) - "
                             "Votazione Ordine del giorno 9/887 E ABB./19 PDL n. 0887"), "19/C.887")
        self.assertEqual(own("Emendamento 13.12 GHIRRA FRANCESCA (AVS) - Votazione Emendamento "
                             "13.12 DDL n. 2026"), "19/C.2026")
        self.assertEqual(own("PDL 2822-B - VOTO FINALE"), "19/C.2822-B")
        self.assertEqual(own("Pdl C. 2822-B art.3 Votaz. di fiducia"), "19/C.2822-B")
        self.assertEqual(own("DDL 3083-A - ODG 9/1 - Votazione Ordine del giorno 9/1"), "19/C.3083")
        self.assertEqual(own("ODG 9/2987-A/66 - Votazione Ordine del giorno 9/2987-A/66 "), "19/C.2987")
        self.assertIsNone(own("EM 19.7 - Votazione "))
        self.assertIsNone(own("Mozione n. 1-00390, limitatamente ai capoversi"))

    def test_inference_within_a_sitting(self):
        votes = [
            {"key": "a", "number": 1, "title": "Mozione n. 1-00472"},
            {"key": "b", "number": 2, "title": "EM 1.1 - Votazione "},
            {"key": "c", "number": 3, "title": "ODG 9/2886/76 - Votazione Ordine del giorno 9/2886/76 "},
            {"key": "d", "number": 4, "title": "Disposizioni per la tutela dei minori"},  # the final vote
            {"key": "e", "number": 5, "title": "EM 2.1 - Votazione "},
            {"key": "f", "number": 6, "title": "Articolo 1 - Votazione Articolo 1 DDL n. 1341"},
        ]
        got = itr.infer_camera_bills(votes)
        self.assertEqual(got["a"], (None, 0))                # motions take no bill
        self.assertEqual(got["b"], ("19/C.2886", 1))         # amendment: forward
        self.assertEqual(got["c"], ("19/C.2886", 0))
        self.assertEqual(got["d"], ("19/C.2886", 1))         # final vote: backward
        self.assertEqual(got["e"], ("19/C.1341", 1))         # never across to the earlier bill

    def test_real_page(self):
        page = itr.parse_camera_list(fixture("camera_votings_p337")["results"])
        self.assertEqual(len(page), 50)
        by = {v["key"]: v for v in page}
        v = by["camera-vs19_147_041"]
        self.assertEqual((v["sitting"], v["number"], v["date"]), (147, 41, "2023-07-26"))
        sitting = [x for x in page if x["sitting"] == 147]
        self.assertEqual(itr.infer_camera_bills(sitting)["camera-vs19_147_041"], ("19/C.887", 0))


class TestCameraDetail(unittest.TestCase):
    def test_positions(self):
        counts, pos, published = itr.parse_camera_detail(fixture("camera_voting_vs19_147_041"))
        self.assertTrue(published)
        self.assertEqual(len(pos), 6)
        self.assertTrue(all(re.match(r"^C:\d+$", m) for m, _, _, _ in pos))
        self.assertTrue({p for _, _, _, p in pos} <= set(itr.CAMERA_POSITIONS.values()))
        self.assertIsNotNone(counts["ayes"])

    def test_secret_placeholders_are_not_published(self):
        """vs19_723_001 was not a secret ballot; Openpolis had the totals the
        next morning and every member still at 'SEC'."""
        rec = fixture("camera_voting_vs19_723_001")
        _counts, pos, published = itr.parse_camera_detail(rec)
        self.assertFalse(rec["is_secret"])
        self.assertTrue(all(p == "secret" for _, _, _, p in pos))
        self.assertFalse(published)


class TestPulls(unittest.TestCase):
    def test_senate_pull_and_positions(self):
        conn = store()
        for b in bills().values():
            itr.store_bill(conn, b, itr.classify_bill(TAX, WL, b), "2026-10-09")
        client = FakeClient(sparql={
            "senate-votes-19-225": "senato_votes_232",   # sittings 225-249
            "senate-positions-senato-19-232-24": "senato_positions_19-232-24",
            "senators": "senato_senators",
        })
        orig = client.get_bytes

        def get_bytes(url, feed, slug, **kw):
            if slug.startswith("senate-max-sitting"):
                return b'{"results": {"bindings": [{"hi": {"value": "232"}}]}}'
            return orig(url, feed, slug, **kw)
        client.get_bytes = get_bytes
        read, ours, gaps = itr.pull_senate_votes(conn, client, "2026-10-09", TAX, WL)
        # every vote of the sitting inherits S.824's area 10 (by watchlist key)
        self.assertEqual((read, ours, gaps), (45, 24, 0))
        members, g = itr.pull_senators(conn, client, "2026-10-09")
        self.assertEqual(g, 0)
        fetched, gaps = itr.pull_positions(conn, client, "2026-10-09", members)
        # X15 (10 October 2026): every vote of the sitting, our 24 first.
        self.assertEqual((fetched, gaps), (45, 0))
        n = conn.execute("SELECT COUNT(*) FROM it_votes WHERE division_key='senato-19-232-24'"
                         ).fetchone()[0]
        self.assertGreater(n, 100)
        grp = conn.execute("SELECT grp FROM it_votes WHERE division_key='senato-19-232-24' "
                           "AND member_key='S:32600'").fetchone()
        self.assertEqual(grp, ("M5S",))
        # a second run asks for nothing it already has
        client.asked.clear()
        self.assertEqual(itr.pull_positions(conn, client, "2026-10-09", members), (0, 0))
        self.assertEqual(client.asked, [])

    def test_a_refused_range_is_a_gap_not_a_crash(self):
        conn = store()
        client = FakeClient(sparql={"bills-range": None})
        read, ours, gaps = itr.pull_bills(conn, client, "2026-10-09", TAX, WL, log=lambda *_: None)
        self.assertEqual((read, gaps), (0, 1))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='it-rollcalls'"
                                      ).fetchone()[0], 1)

    def test_camera_pull_holds_back_unpublished_positions(self):
        conn = store()
        page = fixture("camera_votings_p337")
        page["next"] = None
        client = FakeClient(json_by_slug={
            "camera-votings-19-p1": page,
            "camera-voting-vs19_147_041": fixture("camera_voting_vs19_147_041"),
        })
        # put the surrogacy bill on our ground through the watchlist
        b = bills()["19/C.887"]
        itr.store_bill(conn, b, itr.classify_bill(TAX, WL, b), "2026-10-09")
        read, ours, gaps = itr.pull_camera_votes(conn, client, "2026-10-09", TAX, WL,
                                                 log=lambda *_: None)
        self.assertEqual((read, gaps), (50, 0))
        row = conn.execute("SELECT bill_key, bill_inferred, areas FROM it_divisions "
                           "WHERE division_key='camera-vs19_147_041'").fetchone()
        self.assertEqual(row[:2], ("19/C.887", 0))
        self.assertEqual(json.loads(row[2]), [10])
        fetched, gaps = itr.pull_positions(conn, client, "2026-10-09", {}, log=lambda *_: None)
        self.assertGreaterEqual(fetched, 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM it_votes WHERE "
                                      "division_key='camera-vs19_147_041'").fetchone()[0], 6)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM it_members WHERE chamber='camera'"
                                      ).fetchone()[0], 6)


class TestReclassify(unittest.TestCase):
    def test_reclassify_is_offline_and_idempotent(self):
        conn = store()
        for b in bills().values():
            itr.store_bill(conn, b, itr.classify_bill(TAX, WL, b), "2026-10-09")
        for d in itr.parse_senate_votes(rows("senato_votes_232")).values():
            itr.store_division(conn, d, TAX, WL, "2026-10-09")
        self.assertEqual(itr.reclassify(conn, TAX, log=lambda *_: None), (0, 0))


class TestSchema(unittest.TestCase):
    def test_tables_declared(self):
        for t in it_store.TABLES:
            self.assertIn(t, db.TABLES)

    def test_watchlist_keys_are_well_formed(self):
        import re
        for key in it_store.watchlist():
            self.assertRegex(key, r"^\d+/[CS]\.\d+(-[A-Z]+)?$")


if __name__ == "__main__":
    unittest.main()
