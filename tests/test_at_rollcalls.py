"""Austria: members, Verhandlungsgegenstände and Klub votes (tools/at_rollcalls.py).
No network: every reply is a real one archived on 9 October 2026, trimmed, in
tests/fixtures/at/."""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest
import urllib.robotparser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import at_store, db, filter as filt  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "at")


def _load():
    spec = importlib.util.spec_from_file_location(
        "at_rollcalls", os.path.join(ROOT, "tools", "at_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


atr = _load()
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy-de.yaml"))
WL = atr.empty_watchlist()


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


def content(name):
    return fixture(name)["content"]


class FakeClient:
    """Serves the fixtures by URL; records what was asked for."""

    user_agent = "CitizenGO-ParlMonitor/1.0 (contact: test)"

    def __init__(self, details=None, fail=(), robots=""):
        self.details = details if details is not None else {
            "XXVIII/I/525": "detail-xxviii-i-525.json",
            "XXVIII/UEA/139": "detail-xxviii-uea-139.json",
            "XXVIII/A/295": "detail-xxviii-a-295.json",
        }
        self.fail = set(fail)
        self.robots = robots
        self.fetched = []

    def post_json(self, url, body, feed, slug, timeout=None):
        if "WFW_002" in url:
            return fixture("members-nr.json")
        if "WFW_005" in url:
            return fixture("members-br.json")
        chamber = json.loads(body)["NRBR"][0]
        return fixture("items-{0}.json".format(chamber.lower()))

    def get_json(self, url, feed, slug):
        key = url.split("/gegenstand/", 1)[1].split("?", 1)[0]
        self.fetched.append(key)
        if key in self.fail:
            raise FetchError(url, feed, slug, 1, Exception("HTTP Error 503"))
        name = self.details.get(key)
        return fixture(name) if name else {"content": {"stages": []}}

    def get_text(self, url, feed, slug, archive=True):
        return self.robots


def fresh_db():
    return db.init_db(db.connect(":memory:"))


class Helpers(unittest.TestCase):
    def test_dates_lists_keys(self):
        self.assertEqual(atr.iso_date("15.10.2025"), "2025-10-15")
        self.assertEqual(atr.iso_date("2025-10-15T00:00:00"), "2025-10-15")
        self.assertIsNone(atr.iso_date(""))
        self.assertEqual(atr.json_list('["32508", ""]'), ["32508"])
        self.assertEqual(atr.json_list("not json"), [])
        self.assertEqual(atr.item_key("/gegenstand/XXVIII/I/525"), "XXVIII/I/525")
        self.assertEqual(atr.item_key("/gegenstand/BR/A-BR/434"), "BR/A-BR/434")
        self.assertIsNone(atr.item_key("/person/88386"))
        self.assertEqual(atr.strip_tags("<b>angenommen</b><br>Dafür:&nbsp;ÖVP"),
                         "angenommen\nDafür: ÖVP")

    def test_klub_list(self):
        self.assertEqual(atr.klub_list("ÖVP, SPÖ, NEOS"), ["ÖVP", "SPÖ", "NEOS"])
        self.assertEqual(atr.klub_list("-"), [])
        self.assertEqual(atr.klub_list(""), [])


class Lists(unittest.TestCase):
    def test_items_parse_and_drop_eu_documents(self):
        items, missing = atr.parse_items(fixture("items-nr.json"))
        self.assertEqual(missing, [])
        keys = [it["item_key"] for it in items]
        self.assertNotIn("XXVIII/EUBTG/1047", keys)          # EU document dropped
        self.assertEqual(len(items), 8)
        rv = next(it for it in items if it["item_key"] == "XXVIII/I/525")
        self.assertEqual(rv["art"], "RV")
        self.assertEqual(rv["chamber"], "NR")
        self.assertEqual(rv["vote_text"], "Dafür: F, V, S, N, Dagegen: G")
        self.assertRegex(rv["last_date"], r"^\d{4}-\d{2}-\d{2}$")
        named = next(it for it in items if it["item_key"] == "XXVIII/A/372")
        self.assertIn("abgegebene Stimmen: 171", named["vote_comment"])

    def test_bundesrat_keys(self):
        items, _ = atr.parse_items(fixture("items-br.json"))
        by_key = {it["item_key"]: it for it in items}
        self.assertEqual(by_key["BR/A-BR/428"]["chamber"], "BR")
        # The Nationalrat's Beschluss is listed in the Bundesrat too, under
        # the Nationalrat's key: one item, not two.
        self.assertEqual(by_key["XXVIII/BNR/192"]["chamber"], "NR")

    def test_renamed_column_is_reported_not_guessed(self):
        reply = fixture("items-nr.json")
        for h in reply["header"]:
            if h["label"] == "Betreff":
                h["label"] = "Titel"
        items, missing = atr.parse_items(reply)
        self.assertEqual(items, [])
        self.assertEqual(missing, ["Betreff"])

    def test_members(self):
        nr = atr.parse_members(fixture("members-nr.json"), "NR")
        br = atr.parse_members(fixture("members-br.json"), "BR")
        self.assertEqual(len(nr), 3)
        self.assertEqual(nr[0]["pad"], "38385")
        self.assertEqual(nr[0]["klub"], "NEOS")
        self.assertEqual(br[0]["klub"], "FPÖ")
        self.assertNotIn("<", br[1]["name"])                  # <sup>a</sup> stripped


class Classification(unittest.TestCase):
    def test_taxonomy_de_misses_sterbeverfuegung_and_the_watchlist_catches_it(self):
        bare = filt.filter_item(TAX, WL, "Sterbeverfügungsgesetz-Novelle 2026 – StVfG-Nov 2026")
        self.assertEqual(bare.issue_areas, [])
        res = atr.classify_item(TAX, WL, "XXVIII/I/525",
                                "Sterbeverfügungsgesetz-Novelle 2026 – StVfG-Nov 2026")
        self.assertEqual(res.issue_areas, [2])
        self.assertIn("watch:XXVIII/I/525", res.watchlist_hits)

    def test_watchlist_is_by_key_not_title(self):
        # The same title under an unwatched key stays off our ground.
        res = atr.classify_item(TAX, WL, "XXVIII/I/99999",
                                "Sterbeverfügungsgesetz-Novelle 2026 – StVfG-Nov 2026")
        self.assertEqual(res.issue_areas, [])

    def test_taxonomy_de_on_austrian_titles(self):
        res = atr.classify_item(TAX, WL, "XXVIII/UEA/139",
                                "Schutz des Frauensports - Teilnahmepflicht nach dem "
                                "biologischen Geschlecht")
        self.assertEqual(res.issue_areas, [5])

    def test_watchlist_file_is_well_formed(self):
        watch = at_store.watchlist()
        self.assertTrue(watch)
        for key, (areas, why) in watch.items():
            self.assertRegex(key, r"^(XXVIII|BR)/[A-Z0-9()\-]+/\d+$")
            self.assertTrue(areas and all(1 <= a <= 13 for a in areas))
            self.assertTrue(why)


class Votes(unittest.TestCase):
    def votes(self, name, chamber="NR"):
        return [v for v in (atr.parse_vote(s, chamber) for s in
                            atr.page_stages(content(name))) if v]

    def test_government_bill_every_vote(self):
        votes = self.votes("detail-xxviii-i-525.json")
        questions = [v["question"] for v in votes]
        self.assertIn("Gesetzesvorschlag in zweiter Lesung", questions)
        self.assertIn("Gesetzesvorschlag in dritter Lesung", questions)
        third = next(v for v in votes if v["question"] == "Gesetzesvorschlag in dritter Lesung")
        self.assertEqual(third["body"], "NR")
        self.assertEqual(third["outcome"], "angenommen")
        self.assertEqual(third["against"], ["GRÜNE"])
        self.assertEqual(set(third["for"]), {"FPÖ", "ÖVP", "SPÖ", "NEOS"})
        self.assertTrue(third["sitting"].startswith("XXVIII/NRSITZ/"))
        committee = [v for v in votes if v["body"] == "Justizausschuss"]
        self.assertEqual(len(committee), 1)
        self.assertIsNone(committee[0]["sitting"])
        br = [v for v in votes if v["body"] == "BR"]
        self.assertEqual(len(br), 1)
        self.assertEqual(br[0]["question"], "Antrag, keinen Einspruch zu erheben")
        self.assertTrue(br[0]["sitting"].startswith("BR/BRSITZ/"))

    def test_motion_page_without_phases(self):
        # An unselbständiger Entschließungsantrag carries content.stages, no phases.
        votes = self.votes("detail-xxviii-uea-139.json")
        self.assertEqual(len(votes), 1)
        v = votes[0]
        self.assertEqual(v["outcome"], "abgelehnt")
        self.assertEqual(v["for"], ["FPÖ"])
        self.assertEqual(v["against"], ["ÖVP", "SPÖ", "NEOS", "GRÜNE"])
        self.assertEqual(v["question"], "Unselbständiger Entschließungsantrag")

    def test_namentliche_abstimmung(self):
        votes = self.votes("detail-xxviii-a-372.json")
        named = [v for v in votes if v["roll_call"]]
        self.assertEqual(len(named), 2)                       # Nationalrat and Bundesrat
        nr = next(v for v in named if v["body"] == "NR")
        self.assertEqual((nr["yes_count"], nr["no_count"]), (121, 50))
        br = next(v for v in named if v["body"] == "BR")
        self.assertEqual((br["yes_count"], br["no_count"]), (43, 16))

    def test_procedure_without_klubs_is_not_a_vote(self):
        stage = {"date": "01.01.2026",
                 "text": "Antrag auf Einholung einer Stellungnahme von Bundesministerium - angenommen"}
        self.assertIsNone(atr.parse_vote(stage, "NR"))

    def test_unanimous(self):
        stage = {"date": "03.06.2026", "text": "991. Sitzung: Antrag, keinen Einspruch zu "
                 "erheben, <b>angenommen</b><br>Einstimmig",
                 "fsth": [{"gp_code": "BR", "sitzung_id": 991, "url": "/dokument/BR/BRSITZ/991/x.html#80",
                           "title": "Abstimmung"}]}
        v = atr.parse_vote(stage, "NR")
        self.assertEqual(v["unanimous"], 1)
        self.assertEqual(v["body"], "BR")
        self.assertEqual(v["rn"], "80")

    def test_division_keys_are_stable_and_unique(self):
        votes = self.votes("detail-xxviii-i-525.json")
        keys = atr.division_keys("XXVIII/I/525", votes)
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(keys, atr.division_keys("XXVIII/I/525", votes))
        self.assertTrue(any("@Justizausschuss/" in k for k in keys))
        self.assertTrue(all(k.startswith("XXVIII/I/525@") for k in keys))


class Pull(unittest.TestCase):
    def test_end_to_end(self):
        conn = fresh_db()
        client = FakeClient()
        n, gaps = atr.pull_members(conn, client, "2026-10-09", log=lambda *a: None)
        self.assertEqual((n, gaps), (6, 0))
        stored, ours, gaps = atr.pull_items(conn, client, "2026-10-09", tax=TAX, wl=WL,
                                            log=lambda *a: None)
        self.assertEqual(gaps, 0)
        self.assertEqual(stored, 11)                          # 8 NR + 3 BR, one shared
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM at_items").fetchone()[0], 10)
        pages, divs, skipped, gaps = atr.pull_details(conn, client, "2026-10-09",
                                                      log=lambda *a: None)
        self.assertEqual(gaps, 0)
        # Only items on our ground or watched that can be voted on; never the
        # written question, the gun law or the CEMT bill.
        self.assertNotIn("XXVIII/J/6616", client.fetched)
        self.assertNotIn("XXVIII/A/372", client.fetched)
        self.assertNotIn("XXVIII/I/248", client.fetched)
        for key in ("XXVIII/I/525", "XXVIII/UEA/139", "XXVIII/A/295", "XXVIII/A/1026",
                    "XXVIII/BNR/192"):
            self.assertIn(key, client.fetched)
        third = conn.execute(
            "SELECT division_key, outcome, areas FROM at_divisions WHERE item_key='XXVIII/I/525' "
            "AND question='Gesetzesvorschlag in dritter Lesung'").fetchone()
        self.assertEqual(third[1], "angenommen")
        self.assertEqual(json.loads(third[2]), [2])
        klubs = dict(conn.execute("SELECT klub, position FROM at_votes WHERE division_key=?",
                                  (third[0],)).fetchall())
        self.assertEqual(klubs["GRÜNE"], "Dagegen")
        self.assertEqual(klubs["FPÖ"], "Dafür")
        desc = conn.execute("SELECT description FROM at_items WHERE item_key='XXVIII/I/525'"
                            ).fetchone()[0]
        self.assertTrue(desc)
        # A second run reads nothing: no item moved.
        again = FakeClient()
        self.assertEqual(atr.pull_details(conn, again, "2026-10-16", log=lambda *a: None)[0], 0)
        self.assertEqual(again.fetched, [])
        # The list says one moved: that one is read again, and the re-read upserts.
        conn.execute("UPDATE at_items SET last_date='2026-10-15' WHERE item_key='XXVIII/I/525'")
        before = conn.execute("SELECT COUNT(*) FROM at_divisions").fetchone()[0]
        atr.pull_details(conn, again, "2026-10-16", log=lambda *a: None)
        self.assertEqual(again.fetched, ["XXVIII/I/525"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM at_divisions").fetchone()[0], before)

    def test_failed_page_is_a_gap_and_is_retried(self):
        conn = fresh_db()
        atr.pull_items(conn, FakeClient(), "2026-10-09", tax=TAX, wl=WL, log=lambda *a: None)
        client = FakeClient(fail={"XXVIII/I/525"})
        _, _, _, gaps = atr.pull_details(conn, client, "2026-10-09", log=lambda *a: None)
        self.assertEqual(gaps, 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='at-rollcalls'"
                                      ).fetchone()[0], 1)
        self.assertIsNone(conn.execute("SELECT detail_date FROM at_items WHERE "
                                       "item_key='XXVIII/I/525'").fetchone()[0])
        retry = FakeClient()
        atr.pull_details(conn, retry, "2026-10-10", log=lambda *a: None)
        self.assertEqual(retry.fetched, ["XXVIII/I/525"])

    def test_robots_disallow_is_honoured(self):
        conn = fresh_db()
        atr.pull_items(conn, FakeClient(), "2026-10-09", tax=TAX, wl=WL, log=lambda *a: None)
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(["User-agent: *", "Disallow: /gegenstand/XXVIII/UEA/139"])
        client = FakeClient()
        _, _, skipped, _ = atr.pull_details(conn, client, "2026-10-09", robots=rp,
                                            log=lambda *a: None)
        self.assertEqual(skipped, 1)
        self.assertNotIn("XXVIII/UEA/139", client.fetched)

    def test_empty_or_broken_list_is_a_gap(self):
        class Empty(FakeClient):
            def post_json(self, url, body, feed, slug, timeout=None):
                reply = fixture("items-nr.json")
                reply["rows"] = []
                return reply
        conn = fresh_db()
        stored, _, gaps = atr.pull_items(conn, Empty(), "2026-10-09", tax=TAX, wl=WL,
                                         log=lambda *a: None)
        self.assertEqual((stored, gaps), (0, 2))

    def test_reclassify_offline(self):
        conn = fresh_db()
        client = FakeClient()
        atr.pull_items(conn, client, "2026-10-09", tax=TAX, wl=WL, log=lambda *a: None)
        atr.pull_details(conn, client, "2026-10-09", log=lambda *a: None)
        conn.execute("UPDATE at_items SET areas='[]'")
        conn.execute("UPDATE at_divisions SET areas='[]'")
        changed = atr.reclassify(conn, tax=TAX, log=lambda *a: None)
        self.assertGreater(changed, 0)
        areas = conn.execute("SELECT areas FROM at_divisions WHERE item_key='XXVIII/UEA/139'"
                             ).fetchone()[0]
        self.assertEqual(json.loads(areas), [5])


class Schema(unittest.TestCase):
    def test_tables_declared_and_created(self):
        conn = fresh_db()
        have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in at_store.TABLES:
            self.assertIn(t, db.TABLES)
            self.assertIn(t, have)

    def test_schema_is_idempotent(self):
        conn = sqlite3.connect(":memory:")
        at_store.ensure_schema(conn)
        at_store.ensure_schema(conn)


class DerivedPositionsTests(unittest.TestCase):
    """X5 (Chris, 10 October 2026): member records derived from the Klub,
    labelled as derived, never stored."""

    def test_members_take_their_klubs_position_labelled_derived(self):
        conn = sqlite3.connect(":memory:")
        at_store.ensure_schema(conn)
        conn.execute("INSERT INTO at_divisions (division_key, item_key, body) VALUES ('d', 'i', 'NR')")
        conn.execute("INSERT INTO at_votes VALUES ('d', 'ÖVP', 'Dafür'), ('d', 'SPÖ', 'Dagegen')")
        conn.execute("INSERT INTO at_members (pad, name, chamber, klub) VALUES "
                     "('1', 'A', 'NR', 'ÖVP'), ('2', 'B', 'BR', 'ÖVP'), ('3', 'C', 'NR', 'SPÖ')")
        rows = at_store.derived_member_positions(conn, "d")
        self.assertEqual({(r["member_id"], r["position"]) for r in rows}, {("1", "Dafür"), ("3", "Dagegen")})
        self.assertTrue(all(r["derived"] for r in rows))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM at_votes").fetchone()[0], 2)

    def test_a_committee_vote_derives_nothing(self):
        conn = sqlite3.connect(":memory:")
        at_store.ensure_schema(conn)
        conn.execute("INSERT INTO at_divisions (division_key, item_key, body) VALUES ('d', 'i', 'Justizausschuss')")
        self.assertEqual(at_store.derived_member_positions(conn, "d"), [])


if __name__ == "__main__":
    unittest.main()
