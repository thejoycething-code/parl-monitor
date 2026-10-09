"""Netherlands: Tweede Kamer votes, positions, fracties and members
(tools/nl_rollcalls.py, src/nl_store.py). No network.

Fixtures in tests/fixtures/nl are REAL responses from the Open Data Portaal,
saved 9 October 2026 by the collector's own queries:

  besluiten.json  five decisions with the collector's $expand: a roll call
                  on an Embryowet amendment (150 members, 46-97); a show of
                  hands where three members of Groep Markuszower voted apart
                  from their group; the rainbow-flag roll call of 8 October,
                  whose positions were not yet published; Faber's motion on
                  transgender women in women's prisons; and a vote carrying a
                  declared mistake (vergissing). nextLink removed.
  fracties.json   the 17 sitting fracties, whole.
  members.json    current seats, trimmed to six of 150 rows.
  taxonomy-nl-test.yaml  three terms for the tests, NOT the proposed taxonomy.
"""

import importlib.util
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, nl_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "nl")
TEST_TAX = os.path.join(FIX, "taxonomy-nl-test.yaml")
TODAY = "2026-10-09"

ROLL_CALL = "4df30700-56ad-45bb-a916-167b6541228a"      # 2026Z07564, Embryowet amendment
SPLIT = "2a67b884-e78e-4ccb-a21f-b97df9801d99"          # 2026Z08607
PENDING = "65d66131-e28d-4817-bdc7-5c651e761f98"        # 2026Z21728, rainbow flag
FABER = "f7f12681-e8da-47a9-80a4-dd96ee6bb78b"          # 2026Z06890
MISTAKE = "9ea410c3-d0ef-4291-b4ed-01fe9e83d01b"        # 2026Z20773


def _load():
    spec = importlib.util.spec_from_file_location(
        "nl_rollcalls", os.path.join(ROOT, "tools", "nl_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


nlr = _load()


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


def decisions():
    return {b["Id"]: b for b in fixture("besluiten.json")["value"]}


def store():
    return db.init_db(db.connect(":memory:"))


def quiet(*_a, **_k):
    pass


NO_TAX = filt.Taxonomy(version="none", terms={}, exclusions=set())


class FakeClient:
    """Serves queued JSON pages; records the URLs asked for."""

    def __init__(self, pages=None, fail_at=None):
        self.pages = list(pages or [])
        self.urls = []
        self.fail_at = fail_at

    def get_json(self, url, feed, slug, archive=True):
        self.urls.append(url)
        if self.fail_at is not None and len(self.urls) - 1 == self.fail_at:
            raise FetchError(url, feed, slug, 4, "HTTP Error 503")
        return self.pages.pop(0)


class ParseTests(unittest.TestCase):

    def test_a_show_of_hands_is_one_position_per_group(self):
        d = nlr.parse_decision(decisions()[FABER])
        self.assertEqual(d["stemmingssoort"], "Met handopsteken")
        self.assertEqual({p["kind"] for p in d["positions"]}, {"fractie"})
        self.assertEqual(d["zaken"][0]["nummer"], "2026Z06890")
        self.assertEqual(d["zaken"][0]["dossiers"], ["24587"])
        self.assertEqual(d["date"][:4], "2026")

    def test_a_roll_call_is_one_position_per_member_and_tallies_to_the_record(self):
        d = nlr.parse_decision(decisions()[ROLL_CALL])
        self.assertEqual(d["stemmingssoort"], "Hoofdelijk")
        self.assertEqual(len(d["positions"]), 150)
        self.assertTrue(all(p["persoon_id"] for p in d["positions"]))
        self.assertTrue(all(p["zetels"] is None for p in d["positions"]))
        # The Kamer's own words say 46-97; the positions must agree.
        self.assertIn("(46-97)", d["besluit_tekst"])
        self.assertEqual(nlr.tally(d), (46, 97, 7))
        self.assertEqual(d["date"], "2026-06-02")

    def test_members_voting_apart_from_their_group_are_not_counted_twice(self):
        d = nlr.parse_decision(decisions()[SPLIT])
        apart = [p for p in d["positions"] if p["kind"] == "lid"]
        self.assertEqual(len(apart), 3)
        self.assertEqual({p["fractie"] for p in apart}, {"Groep Markuszower"})
        voor, tegen, niet = nlr.tally(d)
        self.assertEqual(voor + tegen + niet, 150)

    def test_a_show_of_hands_counts_seats_to_150(self):
        d = nlr.parse_decision(decisions()[FABER])
        self.assertEqual(sum(x for x in nlr.tally(d) if x is not None), 150)

    def test_a_vote_whose_positions_are_not_yet_published_still_has_its_result(self):
        d = nlr.parse_decision(decisions()[PENDING])
        self.assertEqual(d["positions"], [])
        self.assertIn("Aangenomen", d["besluit_tekst"])
        # The tally falls back to the Kamer's own printed count.
        self.assertEqual(nlr.tally(d), (90, 36, None))

    def test_a_declared_mistake_is_kept_not_dropped(self):
        d = nlr.parse_decision(decisions()[MISTAKE])
        flagged = [p for p in d["positions"] if p["vergissing"]]
        self.assertEqual([(p["actor"], p["position"]) for p in flagged], [("DENK", "Tegen")])

    def test_a_decision_without_a_vote_is_not_a_division(self):
        self.assertIsNone(nlr.parse_decision({"Id": "x", "StemmingsSoort": None}))
        self.assertIsNone(nlr.parse_decision({"Id": "x", "StemmingsSoort": "Zonder stemming"}))

    def test_dossier_keys(self):
        self.assertEqual(nlr.dossier_key({"Nummer": 36800, "Toevoeging": "XVI"}), "36800-XVI")
        self.assertEqual(nlr.dossier_key({"Nummer": 36390, "Toevoeging": None}), "36390")
        self.assertEqual(nlr.dossier_key({"Nummer": 21501, "Toevoeging": "02"}), "21501-02")
        self.assertIsNone(nlr.dossier_key({}))

    def test_member_names(self):
        self.assertEqual(nlr.member_name({"Roepnaam": "Diederik", "Tussenvoegsel": "van",
                                          "Achternaam": "Dijk"}), "Diederik van Dijk")
        self.assertEqual(nlr.member_name({"Initialen": "J.M.M.", "Achternaam": "Schilder"}),
                         "J.M.M. Schilder")

    def test_the_url_encodes_a_plus_but_keeps_odata_punctuation(self):
        u = nlr.decisions_url("2026-09-01")
        self.assertIn("T00:00:00%2B02:00", u)
        self.assertIn("$expand=Stemming(", u)
        self.assertNotIn(" ", u)


class StoreTests(unittest.TestCase):

    def setUp(self):
        self.conn = store()

    def test_tables_are_declared(self):
        for t in nl_store.TABLES:
            self.assertIn(t, db.TABLES)

    def test_a_pull_stores_votes_positions_and_zaken(self):
        page = fixture("besluiten.json")
        n = nlr.pull_decisions(self.conn, FakeClient([page]), TODAY, "2025-11-12", NO_TAX,
                               log=quiet)
        self.assertEqual((n["read"], n["stored"], n["pending"], n["gaps"]), (5, 5, 1, 0))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM nl_divisions").fetchone()[0], 5)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM nl_votes WHERE besluit_id=?", (ROLL_CALL,)).fetchone()[0], 150)
        row = self.conn.execute("SELECT positions_pending, voor, tegen FROM nl_divisions "
                                "WHERE besluit_id=?", (PENDING,)).fetchone()
        self.assertEqual(tuple(row), (1, 90, 36))
        # Roll-call voters land in nl_members even before the members list is read.
        self.assertGreater(self.conn.execute("SELECT COUNT(*) FROM nl_members").fetchone()[0], 100)

    def test_the_watchlist_classifies_by_key_before_any_taxonomy_exists(self):
        nlr.pull_decisions(self.conn, FakeClient([fixture("besluiten.json")]), TODAY,
                           "2025-11-12", NO_TAX, log=quiet)
        areas = dict(self.conn.execute("SELECT zaak_nummer, areas FROM nl_zaken"))
        self.assertEqual(json.loads(areas["2026Z21728"]), [5])      # zaak key
        self.assertEqual(json.loads(areas["2026Z07564"]), [10])     # dossier 36677
        self.assertEqual(json.loads(areas["2026Z06890"]), [])       # no taxonomy yet
        terms = self.conn.execute("SELECT matched_terms FROM nl_zaken WHERE zaak_nummer="
                                  "'2026Z07564'").fetchone()[0]
        self.assertIn("watch:dossier:36677", terms)

    def test_a_reread_fills_pending_positions_and_replaces_them_wholesale(self):
        page = fixture("besluiten.json")
        nlr.pull_decisions(self.conn, FakeClient([page]), TODAY, "2025-11-12", NO_TAX, log=quiet)
        # The next run: the portal has published the rainbow-flag positions,
        # and one of the Embryowet roll call's rows has been withdrawn.
        later = fixture("besluiten.json")
        by_id = {b["Id"]: b for b in later["value"]}
        by_id[PENDING]["Stemming"] = [
            {"Id": "s-1", "Soort": "Voor", "FractieGrootte": None, "ActorNaam": "Piri",
             "ActorFractie": "PRO", "Vergissing": False, "Persoon_Id": "p-1", "Fractie_Id": "f-1"}]
        by_id[ROLL_CALL]["Stemming"] = by_id[ROLL_CALL]["Stemming"][1:]
        nlr.pull_decisions(self.conn, FakeClient([later]), TODAY, "2025-11-12", NO_TAX, log=quiet)
        self.assertEqual(self.conn.execute("SELECT positions_pending FROM nl_divisions WHERE "
                                           "besluit_id=?", (PENDING,)).fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM nl_votes WHERE besluit_id=?",
                                           (ROLL_CALL,)).fetchone()[0], 149)

    def test_a_withdrawn_decision_is_dropped_with_its_positions(self):
        nlr.pull_decisions(self.conn, FakeClient([fixture("besluiten.json")]), TODAY,
                           "2025-11-12", NO_TAX, log=quiet)
        gone = fixture("besluiten.json")
        gone["value"] = [b for b in gone["value"] if b["Id"] == FABER]
        gone["value"][0]["Verwijderd"] = True
        n = nlr.pull_decisions(self.conn, FakeClient([gone]), TODAY, "2025-11-12", NO_TAX,
                               log=quiet)
        self.assertEqual(n["deleted"], 1)
        self.assertIsNone(self.conn.execute("SELECT 1 FROM nl_divisions WHERE besluit_id=?",
                                            (FABER,)).fetchone())
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM nl_votes WHERE besluit_id=?",
                                           (FABER,)).fetchone()[0], 0)

    def test_pages_follow_next_link(self):
        page = fixture("besluiten.json")
        first = {"value": page["value"][:2], "@odata.nextLink": nlr.BASE + "Besluit?$skiptoken=x"}
        second = {"value": page["value"][2:]}
        client = FakeClient([first, second])
        n = nlr.pull_decisions(self.conn, client, TODAY, "2025-11-12", NO_TAX, log=quiet)
        self.assertEqual((n["pages"], n["stored"]), (2, 5))
        self.assertEqual(client.urls[1], nlr.BASE + "Besluit?$skiptoken=x")

    def test_a_failed_page_is_a_gap_and_keeps_what_was_stored(self):
        page = fixture("besluiten.json")
        first = {"value": page["value"][:2], "@odata.nextLink": nlr.BASE + "Besluit?$skiptoken=x"}
        n = nlr.pull_decisions(self.conn, FakeClient([first], fail_at=1), TODAY, "2025-11-12",
                               NO_TAX, log=quiet)
        self.assertEqual((n["stored"], n["gaps"]), (2, 1))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM gaps WHERE feed=?",
                                           (nlr.FEED,)).fetchone()[0], 1)

    def test_the_budget_stops_the_drain_and_says_so(self):
        class Spent:
            def exhausted(self):
                return True

            def disclose(self, what, done):
                return "budget"
        n = nlr.pull_decisions(self.conn, FakeClient([]), TODAY, "2025-11-12", NO_TAX,
                               log=quiet, budget=Spent())
        self.assertEqual((n["pages"], n["gaps"]), (0, 1))

    def test_positions_still_missing_after_two_weeks_are_a_gap(self):
        nlr.pull_decisions(self.conn, FakeClient([fixture("besluiten.json")]), TODAY,
                           "2025-11-12", NO_TAX, log=quiet)
        self.assertEqual(nlr.check_pending(self.conn, TODAY, log=quiet), 0)
        self.assertEqual(nlr.check_pending(self.conn, "2026-10-30", log=quiet), 1)

    def test_the_window(self):
        self.assertEqual(nlr.window_start(self.conn, TODAY), nlr.TERM_START)
        nlr.pull_decisions(self.conn, FakeClient([fixture("besluiten.json")]), TODAY,
                           "2025-11-12", NO_TAX, log=quiet)
        self.assertEqual(nlr.window_start(self.conn, TODAY), "2026-08-28")
        self.assertEqual(nlr.window_start(self.conn, TODAY, since="2026-01-01"), "2026-01-01")
        self.assertEqual(nlr.window_start(self.conn, "2025-12-01"), nlr.TERM_START)

    def test_members_and_fracties(self):
        n_f = nlr.pull_fracties(self.conn, FakeClient([fixture("fracties.json")]), TODAY)
        n_m = nlr.pull_members(self.conn, FakeClient([fixture("members.json")]), TODAY)
        self.assertEqual((n_f, n_m), (17, 6))
        self.assertEqual(self.conn.execute("SELECT SUM(zetels) FROM nl_fracties").fetchone()[0], 150)
        row = self.conn.execute("SELECT name, fractie FROM nl_members WHERE name LIKE '%Piri'"
                                ).fetchone()
        self.assertEqual(tuple(row), ("Kati Piri", "PRO"))
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(nl_members)")}
        # Data minimisation: no birth date, residence or gender is stored.
        self.assertFalse(cols & {"geboortedatum", "woonplaats", "geslacht"})


class ReclassifyTests(unittest.TestCase):

    def test_reclassify_applies_a_taxonomy_offline_and_votes_follow_their_zaak(self):
        conn = store()
        nlr.pull_decisions(conn, FakeClient([fixture("besluiten.json")]), TODAY, "2025-11-12",
                           NO_TAX, log=quiet)
        tax = nlr.load_taxonomy(TEST_TAX, log=quiet)
        changed_z, changed_d = nlr.reclassify(conn, tax, log=quiet)
        self.assertEqual((changed_z, changed_d), (1, 1))
        own, areas = conn.execute("SELECT own_areas, areas FROM nl_zaken WHERE "
                                  "zaak_nummer='2026Z06890'").fetchone()
        self.assertEqual((json.loads(own), json.loads(areas)), ([5], [5]))
        self.assertEqual(json.loads(conn.execute(
            "SELECT areas FROM nl_divisions WHERE besluit_id=?", (FABER,)).fetchone()[0]), [5])

    def test_the_dossier_title_lends_its_areas_but_own_areas_stay_apart(self):
        conn = store()
        nlr.pull_decisions(conn, FakeClient([fixture("besluiten.json")]), TODAY, "2025-11-12",
                           nlr.load_taxonomy(TEST_TAX, log=quiet), log=quiet)
        own, areas, terms = conn.execute(
            "SELECT own_areas, areas, matched_terms FROM nl_zaken WHERE zaak_nummer='2026Z07564'"
        ).fetchone()
        self.assertIn(10, json.loads(areas))
        self.assertIn("Embryowet", json.loads(terms))
        self.assertIsInstance(json.loads(own), list)

    def test_a_missing_taxonomy_is_empty_and_said_so(self):
        said = []
        tax = nlr.load_taxonomy(os.path.join(FIX, "no-such-taxonomy.yaml"), log=said.append)
        self.assertEqual(tax.terms, {})
        self.assertTrue(any("not yet approved" in s for s in said))

    def test_the_english_taxonomy_is_not_the_default(self):
        self.assertTrue(nlr.TAXONOMY.endswith("taxonomy-nl.yaml"))


class WatchlistTests(unittest.TestCase):

    def test_every_entry_is_keyed_by_number_and_explained(self):
        import re
        wl = nl_store.watchlist()
        self.assertTrue(wl["dossiers"])
        for key, (areas, why) in wl["dossiers"].items():
            self.assertRegex(key, r"^\d{5}(-[0-9A-Z()]+)?$", key)
            self.assertTrue(areas and why, key)
            self.assertTrue(all(1 <= a <= 13 for a in areas), key)
        for key, (areas, why) in wl["zaken"].items():
            self.assertTrue(re.match(r"^\d{4}Z\d{5}$", key), key)
            self.assertTrue(areas and why, key)

    def test_add_watch_areas(self):
        res = filt.FilterResult()
        nl_store.add_watch_areas(res, "2026Z99999", ["36390"])
        self.assertEqual(res.issue_areas, [9, 10])
        self.assertEqual(res.tier, 2)
        self.assertEqual(res.watchlist_hits, ["watch:dossier:36390"])
        res = filt.FilterResult()
        nl_store.add_watch_areas(res, "2026Z99999", ["99999"])
        self.assertEqual((res.issue_areas, res.tier), ([], None))


class JobTests(unittest.TestCase):
    """The Mini-first weekly: one script, two callers."""

    def read(self, *parts):
        with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
            return fh.read()

    def test_the_job_publishes_after_the_collector_and_tolerates_gaps(self):
        job = self.read("jobs", "nl-weekly.sh")
        self.assertIn('GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Netherlands weekly}"', job)
        self.assertLess(job.index("tools/nl_rollcalls.py --budget-seconds"),
                        job.index("tools/raw_state.py --push"))
        self.assertLess(job.index("tools/raw_state.py --push"), job.index("tools/db_state.py --push"))
        self.assertIn('[ "$rc" -ne 3 ]', job)

    def test_the_workflow_is_gated_by_the_mini(self):
        wf = self.read(".github", "workflows", "nl-weekly.yml")
        self.assertTrue(wf.startswith("name: Netherlands weekly\n"))
        self.assertIn("job: NL_WEEKLY", wf)
        self.assertIn("bash jobs/nl-weekly.sh", wf)
        self.assertIn("group: parl-monitor-state", wf)

    def test_the_plist_runs_the_job_through_mini_run(self):
        plist = self.read("ops", "launchd", "net.citizengo.parlmonitor.nl-weekly.plist")
        self.assertIn("<string>nl-weekly</string>", plist)
        self.assertIn("tools/mini_run.sh", plist)


if __name__ == "__main__":
    unittest.main()
