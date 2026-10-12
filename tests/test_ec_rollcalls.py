"""Ecuador, Asamblea Nacional: plenary votes, positions, register, roster
(tools/ec_rollcalls.py). No network: real responses saved on 9 October 2026
under tests/fixtures/ec/."""

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

from src import db, ec_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "ec")
TODAY = "2026-10-09"


def _load():
    spec = importlib.util.spec_from_file_location(
        "ec_rollcalls", os.path.join(ROOT, "tools", "ec_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ecr = _load()


def fixture(name):
    path = os.path.join(FIX, name)
    opener = gzip.open if name.endswith(".gz") else open
    with opener(path, "rb") as fh:
        return fh.read()


def text(name):
    return fixture(name).decode("utf-8")


def store():
    conn = sqlite3.connect(":memory:")
    db.init_db(conn)
    return conn


TINY_TAXONOMY = """version: test
areas:
  1_abortion:
    tier1: ["interrupción voluntaria del embarazo"]
    tier2: []
  11_migration:
    tier1: ["movilidad humana"]
    tier2: []
exclusions_global: [vida]
"""


def tiny_taxonomy():
    fd, path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(TINY_TAXONOMY)
    try:
        return ecr.load_taxonomy(path)
    finally:
        os.unlink(path)


class FakeClient:
    """Serves fixtures by URL substring; anything unknown raises FetchError."""

    def __init__(self, files=None, pages=None, fail=()):
        self.files, self.pages, self.fail = files or {}, pages or {}, set(fail)
        self.requested = []

    def _get(self, url, table):
        self.requested.append(url)
        if any(f in url for f in self.fail):
            raise FetchError(url, "ec-rollcalls", "x", 1, "HTTP Error 503")
        for key, value in table.items():
            if key in url:
                return value
        raise FetchError(url, "ec-rollcalls", "x", 1, "HTTP Error 404")

    def get_bytes(self, url, feed, slug, **kw):
        return self._get(url, self.files)

    def get_text(self, url, feed, slug, **kw):
        return self._get(url, self.pages)


def quiet(*_a, **_k):
    pass


class Helpers(unittest.TestCase):
    def test_local_date_is_ecuador_time(self):
        # Served in UTC; Ecuador is UTC-5 all year. A vote at 03:00 UTC was
        # cast the evening before in Quito.
        self.assertEqual(ecr.local_date("2026-09-03T19:21:04.000+00:00"), "2026-09-03")
        self.assertEqual(ecr.local_date("2026-09-04T03:10:00.000+00:00"), "2026-09-03")
        self.assertIsNone(ecr.local_date(None))

    def test_division_key_is_the_vote_number(self):
        self.assertEqual(ecr.division_key(1004966), "ec-1004966")

    def test_name_key_joins_differently_ordered_names(self):
        a = ec_store.name_key("URRESTA GUZMÁN", "JHAJAIRA ESTEFANÍA")
        b = ec_store.name_key("Jhajaira Estefanía Urresta Guzmán")
        self.assertEqual(a, b)
        self.assertEqual(a, "ESTEFANIA GUZMAN JHAJAIRA URRESTA")

    def test_party_slug(self):
        base = "https://www.asambleanacional.gob.ec/sites/default/files/styles/avatar_partido/public/"
        self.assertEqual(ecr.party_slug(base + "avatar-mujer-adn.png?itok=X"), "adn")
        self.assertEqual(ecr.party_slug(base + "avatar-hombre-revolucion-ciudadana.png?itok=P"),
                         "revolucion-ciudadana")
        self.assertEqual(ecr.party_slug(base + "avatar-pachakutik-mujer.png"), "pachakutik")
        # The page's own misspelling, kept working.
        self.assertEqual(ecr.party_slug(base + "avartar-psc-hombre.png"), "psc")
        self.assertEqual(ecr.party_slug(base + "avatar-26.png"), "26")
        self.assertIsNone(ecr.party_slug("/sites/all/modules/an_asambleistas/img/ico/presidente.png"))


class Periods(unittest.TestCase):
    def setUp(self):
        self.periods = ecr.parse_periods(fixture("period.json"))

    def test_every_period_since_2009(self):
        self.assertEqual([p[0] for p in self.periods], [2, 4, 5, 6, 7, 8])
        self.assertEqual(self.periods[-1], (8, "2025-05-14", "2029-05-13"))

    def test_current_period(self):
        self.assertEqual(ecr.current_period(self.periods, TODAY)[0], 8)
        self.assertEqual(ecr.current_period(self.periods, "2024-06-01")[0], 7)

    def test_the_gap_between_periods_falls_back_to_the_last_begun(self):
        # 2023-05-17 to 2023-11-17: the muerte cruzada dissolution. No period
        # holds those dates; the last one begun is 6.
        self.assertEqual(ecr.current_period(self.periods, "2023-08-01")[0], 6)

    def test_not_json_is_nothing(self):
        self.assertEqual(ecr.parse_periods(b"<html>"), [])


class VoteList(unittest.TestCase):
    def setUp(self):
        self.votes = ecr.parse_vote_list(fixture("votinglist-2026-09-01-to-10-08.json"))

    def test_every_vote_in_the_window(self):
        self.assertEqual(len(self.votes), 34)
        self.assertEqual(len({v["voting_id"] for v in self.votes}), 34)

    def test_fields(self):
        v = next(x for x in self.votes if x["voting_id"] == 1004966)
        self.assertEqual(v["date"], "2026-09-03")
        self.assertEqual(v["session"], 121)
        self.assertEqual((v["yes"], v["no"], v["blank"], v["abstain"]), (87, 50, 0, 2))
        self.assertIn("Transporte Terrestre", v["theme"])
        self.assertTrue(v["proposal"].startswith("Aprobación del Proyecto de Ley"))

    def test_an_empty_window_is_an_empty_list_not_an_error(self):
        # The service answers 200 [] for a window with no votes and for a
        # vote number that does not exist.
        self.assertEqual(ecr.parse_vote_list(b"[]"), [])
        self.assertIsNone(ecr.parse_vote_list(b"<html>error</html>"))


class Detail(unittest.TestCase):
    def test_positions(self):
        pos = ecr.parse_detail(fixture("votingdetail-1004966.json"))
        self.assertEqual(len(pos), 139)
        counts = {}
        for _n, _k, p, _s in pos:
            counts[p] = counts.get(p, 0) + 1
        self.assertEqual(counts, {"SI": 87, "NO": 50, "ABSTENCION": 2})
        self.assertIn(("URRESTA GUZMÁN JHAJAIRA ESTEFANÍA",
                       "ESTEFANIA GUZMAN JHAJAIRA URRESTA", "SI", "66"), pos)

    def test_the_2022_abortion_law(self):
        # 17 February 2022, the approving motion of the IVE-for-rape law.
        pos = ecr.parse_detail(fixture("votingdetail-1002666.json"))
        self.assertEqual(len(pos), 130)
        self.assertEqual(sum(1 for p in pos if p[2] == "SI"), 75)
        self.assertEqual(sum(1 for p in pos if p[2] == "NO"), 41)
        self.assertEqual(sum(1 for p in pos if p[2] == "ABSTENCION"), 14)

    def test_empty_and_broken(self):
        self.assertEqual(ecr.parse_detail(b"[]"), [])
        self.assertIsNone(ecr.parse_detail(b"oops"))


class Register(unittest.TestCase):
    def test_register_puts_surnames_first(self):
        members = ecr.parse_members(fixture("members.json.gz"))
        self.assertEqual(len(members), 798)
        first = members[0]
        self.assertEqual(first[:2], (2, "ABRIL ABRIL JAIME HERIBERTO"))


class Roster(unittest.TestCase):
    def setUp(self):
        self.roster = ecr.parse_roster(text("pleno-asambleistas.html.gz"))

    def test_the_sitting_151(self):
        self.assertEqual(len(self.roster), 151)

    def test_party_counts(self):
        counts = {}
        for r in self.roster:
            counts[r[3]] = counts.get(r[3], 0) + 1
        self.assertEqual(counts["adn"], 67)
        self.assertEqual(counts["revolucion-ciudadana"], 61)
        self.assertEqual(counts["pachakutik"], 9)
        self.assertEqual(counts["psc"], 4)
        self.assertEqual(counts["26"] + counts["16"] + counts["15"], 10)

    def test_a_card(self):
        card = next(r for r in self.roster if r[0] == "Adrián Ernesto Castro Piedra")
        self.assertEqual(card[2], "Azuay")
        self.assertEqual(card[3:], ("adn", "Acción Democrática Nacional (ADN)"))

    def test_unlabelled_list_numbers_have_no_party_label(self):
        card = next(r for r in self.roster if r[3] == "26")
        self.assertIsNone(card[4])


class Classify(unittest.TestCase):
    def test_no_taxonomy_no_watch_is_unclassified(self):
        self.assertEqual(ecr.classify(None, "ec-1", "Ley de tránsito"), (None, None, [], None))

    def test_watchlist_lends_areas_by_key_without_a_taxonomy(self):
        own, combined, terms, tier = ecr.classify(None, "ec-1002666", "anything")
        self.assertIsNone(own)
        self.assertEqual(combined, [1])
        self.assertEqual(terms, ["watch:ec-1002666"])
        self.assertEqual(tier, 2)

    def test_taxonomy_matches_spanish(self):
        tax = tiny_taxonomy()
        votes = ecr.parse_vote_list(fixture("votinglist-2022-02-17.json"))
        hits = [ecr.classify(tax, ecr.division_key(v["voting_id"]), v["theme"], v["proposal"])
                for v in votes]
        self.assertEqual(sum(1 for h in hits if 1 in (h[1] or [])), 3)

    def test_classified_but_nothing_found_is_an_empty_list(self):
        own, combined, _t, _tier = ecr.classify(tiny_taxonomy(), "ec-1", "Ley de tránsito")
        self.assertEqual((own, combined), ([], []))


class PullVotes(unittest.TestCase):
    def client(self, **kw):
        files = {"reports/votingList": fixture("votinglist-2026-09-01-to-10-08.json"),
                 "idVoting=1004966": fixture("votingdetail-1004966.json")}
        files.update(kw.pop("files", {}))
        return FakeClient(files=files, **kw)

    def test_the_fetch_cap_counts_attempts_and_an_unserved_detail_is_a_gap(self):
        conn = store()
        listed, stored, details, gaps = ecr.pull_votes(
            conn, self.client(), TODAY, (8, "2025-05-14", "2029-05-13"),
            log=quiet, limit=1)
        self.assertEqual((listed, stored, details, gaps), (34, 34, 0, 1))

    def test_details_and_totals(self):
        conn = store()
        client = self.client()
        ecr.pull_votes(conn, client, TODAY, (8, "2025-05-14", "2029-05-13"), log=quiet,
                       index_only=True)
        conn.execute("UPDATE ec_divisions SET positions=0 WHERE division_key != 'ec-1004966'")
        _l, _s, details, gaps = ecr.pull_votes(conn, client, TODAY, (8, "2025-05-14", "2029-05-13"),
                                               log=quiet)
        self.assertEqual((details, gaps), (1, 0))
        n = conn.execute("SELECT positions FROM ec_divisions WHERE division_key='ec-1004966'"
                         ).fetchone()[0]
        self.assertEqual(n, 139)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ec_votes").fetchone()[0], 139)

    def test_the_second_run_lists_only_from_the_last_date_less_a_fortnight(self):
        conn = store()
        client = self.client()
        period = (8, "2025-05-14", "2029-05-13")
        ecr.pull_votes(conn, client, TODAY, period, log=quiet, index_only=True)
        self.assertIn("dateIn=2025-05-14", client.requested[0])
        ecr.pull_votes(conn, client, TODAY, period, log=quiet, index_only=True)
        last = conn.execute("SELECT MAX(date) FROM ec_divisions").fetchone()[0]
        self.assertEqual(last, "2026-10-06")
        self.assertIn("dateIn=2026-09-22", client.requested[-1])

    def test_a_detail_that_does_not_add_up_is_stored_and_said(self):
        conn = store()
        bad = json.dumps(json.loads(fixture("votingdetail-1004966.json"))[:100]).encode()
        client = self.client(files={"idVoting=1004966": bad})
        ecr.pull_votes(conn, client, TODAY, (8, "2025-05-14", "2029-05-13"), log=quiet,
                       index_only=True)
        conn.execute("UPDATE ec_divisions SET positions=0 WHERE division_key != 'ec-1004966'")
        _l, _s, details, gaps = ecr.pull_votes(conn, client, TODAY, (8, "2025-05-14", "2029-05-13"),
                                               log=quiet)
        self.assertEqual((details, gaps), (1, 1))
        detail = conn.execute("SELECT detail FROM gaps").fetchone()[0]
        self.assertIn("ec-1004966: 100 position(s)", detail)

    def test_a_failed_list_is_a_gap_not_a_crash(self):
        conn = store()
        listed, stored, details, gaps = ecr.pull_votes(
            conn, FakeClient(fail=("votingList",)), TODAY, (8, "2025-05-14", "2029-05-13"),
            log=quiet)
        self.assertEqual((listed, stored, details, gaps), (0, 0, 0, 1))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0], 1)

    def test_an_empty_detail_is_a_gap(self):
        conn = store()
        client = self.client(files={"idVoting=1004966": b"[]"})
        ecr.pull_votes(conn, client, TODAY, (8, "2025-05-14", "2029-05-13"), log=quiet,
                       index_only=True)
        conn.execute("UPDATE ec_divisions SET positions=0 WHERE division_key != 'ec-1004966'")
        _l, _s, details, gaps = ecr.pull_votes(conn, client, TODAY, (8, "2025-05-14", "2029-05-13"),
                                               log=quiet)
        self.assertEqual((details, gaps), (0, 1))
        self.assertIsNone(conn.execute(
            "SELECT positions FROM ec_divisions WHERE division_key='ec-1004966'").fetchone()[0])


class PullMembers(unittest.TestCase):
    def test_register_and_roster(self):
        conn = store()
        client = FakeClient(files={"assemblymemberlist": fixture("members.json.gz")},
                            pages={"pleno-asambleistas": text("pleno-asambleistas.html.gz")})
        self.assertEqual(ecr.pull_members(conn, client, TODAY, log=quiet), (798, 0))
        self.assertEqual(ecr.pull_roster(conn, client, TODAY, log=quiet), (151, 0))

    def test_a_roster_page_that_changed_shape_is_not_stored(self):
        conn = store()
        client = FakeClient(pages={"pleno-asambleistas": "<html>nothing</html>"})
        self.assertEqual(ecr.pull_roster(conn, client, TODAY, log=quiet), (0, 1))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ec_roster").fetchone()[0], 0)


class Reclassify(unittest.TestCase):
    def test_offline_rederivation(self):
        conn = store()
        client = FakeClient(files={"reports/votingList": fixture("votinglist-2022-02-17.json")})
        ecr.pull_votes(conn, client, TODAY, (6, "2021-05-14", "2023-05-17"), log=quiet,
                       index_only=True)
        # Without a taxonomy only the watched votes carry areas.
        watched = conn.execute("SELECT COUNT(*) FROM ec_divisions WHERE areas IS NOT NULL"
                               ).fetchone()[0]
        self.assertEqual(watched, 3)
        changed = ecr.reclassify(conn, tiny_taxonomy(), log=quiet)
        self.assertEqual(changed, 3)    # the other three votes: NULL -> []
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ec_divisions WHERE areas IS NULL"
                                      ).fetchone()[0], 0)


class Watchlist(unittest.TestCase):
    def test_keys_are_division_keys(self):
        for key in ec_store.watchlist():
            self.assertRegex(key, r"^ec-\d+$")

    def test_tables_declared(self):
        for t in ec_store.TABLES:
            self.assertIn(t, db.TABLES)


if __name__ == "__main__":
    unittest.main()
