"""Slovakia, Národná rada: members, prints, votes, positions and
interpellations (tools/sk_rollcalls.py). No network: real responses saved
on 9 October 2026 under tests/fixtures/sk."""

import datetime as dt
import importlib.util
import json
import os
import re
import sqlite3
import sys
import unittest

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, sk_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "sk")


def _load():
    spec = importlib.util.spec_from_file_location(
        "sk_rollcalls", os.path.join(ROOT, "tools", "sk_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


skr = _load()
TAX = filt.load_taxonomy(os.path.join(FIX, "taxonomy-test.yaml"))
WL = skr.empty_watchlist()
TODAY = "2026-10-09"


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def fixture_json(name):
    return json.loads(fixture(name))


class FakeClient:
    """Answers the open-data lists and the vote pages from fixtures; any
    vote page without a fixture fails as the real host would on a bad day."""

    def __init__(self):
        self.pages = []

    def get_json(self, url, feed, slug, archive=True):
        for part, name in (("MembersOfParliament", "members.json"), ("Bill/Bills", "bills.json"),
                           ("Voting/Votings", "votings.json"),
                           ("Interpellations", "interpellations.json")):
            if part in url:
                return fixture_json(name)
        raise AssertionError("unexpected URL " + url)

    def get_text(self, url, feed, slug, archive=True):
        vid = url.rsplit("=", 1)[1]
        self.pages.append(int(vid))
        path = os.path.join(FIX, "vote_{0}.html".format(vid))
        if not os.path.exists(path):
            raise FetchError(url, feed, slug, 4, "timed out")
        return fixture("vote_{0}.html".format(vid))


def memdb():
    return db.init_db(db.connect(":memory:"))


def run_all(conn, client, tax=TAX, everything=False):
    skr.pull_members(conn, client, TODAY)
    skr.pull_bills(conn, client, TODAY, tax=tax, wl=WL)
    skr.pull_votings(conn, client, TODAY, tax=tax, wl=WL)
    skr.pull_interpellations(conn, client, TODAY, tax=tax, wl=WL)
    return skr.pull_positions(conn, client, TODAY, everything=everything, log=lambda *_: None)


class VotePageTests(unittest.TestCase):
    """The hlasklub page is the only source of positions."""

    def setUp(self):
        self.positions = skr.parse_vote_page(fixture("vote_56965.html"))

    def test_every_seat_is_read(self):
        self.assertEqual(len(self.positions), 150)
        self.assertEqual(len({p["mp_id"] for p in self.positions}), 150)

    def test_the_constitutional_amendment_tallies_as_published(self):
        """26 September 2025, tlač 733 in third reading: 90 for, 7 against."""
        self.assertEqual(skr.tally(self.positions), {"Z": 90, "P": 7, "N": 2, "0": 51})

    def test_club_is_taken_from_the_block_the_member_sits_in(self):
        clubs = {p["club"] for p in self.positions}
        self.assertIn("SMER - SD", clubs)
        self.assertIn("KDH", clubs)
        self.assertNotIn("Klub SMER - SD", clubs)

    def test_members_outside_any_club_have_none(self):
        self.assertIn(None, {p["club"] for p in self.positions})

    def test_names_are_unescaped(self):
        names = {p["name"] for p in self.positions}
        self.assertTrue(any("č" in n or "á" in n for n in names))
        self.assertFalse(any("&" in n for n in names))

    def test_a_page_with_no_table_is_none_not_empty(self):
        self.assertIsNone(skr.parse_vote_page("<html><body>Chyba</body></html>"))
        self.assertIsNone(skr.parse_vote_page(""))

    def test_totals_check_agrees_with_the_open_data(self):
        rows = {v["voting_id"]: v for v in skr.parse_votings(fixture_json("votings.json"))}
        for vid in (56965, 56356):
            page = skr.parse_vote_page(fixture("vote_{0}.html".format(vid)))
            self.assertEqual(skr.check_totals(page, rows[vid]), [], vid)

    def test_the_absent_count_is_not_checked(self):
        """The open data says 53 absent on 56965, with 99 present: 152 seats
        in a chamber of 150. The page's 51 is right."""
        row = {v["voting_id"]: v for v in skr.parse_votings(fixture_json("votings.json"))}[56965]
        self.assertEqual((row["present"], row["absent"]), (99, 53))
        self.assertEqual(skr.tally(self.positions)["0"], 51)
        self.assertEqual(skr.check_totals(self.positions, row), [])

    def test_totals_check_names_a_disagreement(self):
        row = {"agreed": 91, "disagreed": 7, "abstained": 0, "not_voting": 2, "absent": 51}
        self.assertEqual(skr.check_totals(self.positions, row), ["Z page 90 != open data 91"])


class ParseTests(unittest.TestCase):

    def test_bill_key_is_term_and_print(self):
        self.assertEqual(skr.bill_key(9, "733"), "9/733")
        self.assertIsNone(skr.bill_key(9, ""))
        self.assertIsNone(skr.bill_key(9, None))

    def test_iso_date_drops_only_an_empty_time(self):
        self.assertEqual(skr.iso_date("2025-09-26T00:00:00"), "2025-09-26")
        self.assertEqual(skr.iso_date("2026-10-06T18:44:40"), "2026-10-06T18:44:40")
        self.assertIsNone(skr.iso_date(None))

    def test_votings_carry_the_print_and_the_totals(self):
        v = {x["voting_id"]: x for x in skr.parse_votings(fixture_json("votings.json"))}[56965]
        self.assertEqual((v["tlac"], v["meeting"], v["agreed"], v["disagreed"]), ("733", 39, 90, 7))

    def test_the_constitutional_flag_is_not_to_be_trusted(self):
        """The final vote on a constitutional amendment, flagged false. It is
        false on every vote of term 9: stored as published, never relied on."""
        v = {x["voting_id"]: x for x in skr.parse_votings(fixture_json("votings.json"))}[56965]
        self.assertFalse(v["is_constitutional"])

    def test_a_vote_with_no_print_has_none(self):
        v = {x["voting_id"]: x for x in skr.parse_votings(fixture_json("votings.json"))}[57961]
        self.assertIsNone(v["tlac"])

    def test_members_key_on_poslanec_id(self):
        m = skr.parse_members(fixture_json("members.json"))
        self.assertTrue(all(isinstance(x["mp_id"], int) for x in m))
        self.assertTrue(all(x["name"] for x in m))


class TaxonomyFindingTests(unittest.TestCase):
    """The finding that shapes the edition: English terms are blind to
    Slovak, and Slovak terms must be written as stems."""

    TITLE = ("Návrh poslancov Národnej rady Slovenskej republiky Anny ZÁBORSKEJ a Richarda "
             "VAŠEČKU na vydanie zákona, ktorým sa mení zákon č. 73/1986 Zb. o umelom "
             "prerušení tehotenstva v znení neskorších predpisov")

    def test_the_english_taxonomy_misses_an_abortion_bill(self):
        en = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        self.assertEqual(filt.filter_item(en, WL, self.TITLE).issue_areas, [])

    def test_a_stem_catches_the_inflected_form(self):
        res = filt.filter_item(TAX, WL, self.TITLE)
        self.assertEqual(res.issue_areas, [1])
        self.assertEqual(res.tier, 1)

    def test_a_stem_that_keeps_the_ending_now_matches_too(self):
        """'prerušeni*' missed 'prerušení' (í is not i) until the shared
        filter learned to fold accents at the countries merge (X3, 10
        October 2026). The draft list made exactly this mistake before it
        was measured; folding makes the stem forgiving."""
        bad = filt.Taxonomy(version="x", terms={1: {1: [
            ("umel* prerušeni* tehotenstva",) + filt._compile_term("umel* prerušeni* tehotenstva")
            + ([], [])], 2: []}}, exclusions=set())
        self.assertEqual(filt.filter_item(bad, WL, self.TITLE).issue_areas, [1])

    def test_the_law_number_is_a_term(self):
        res = filt.filter_item(TAX, WL, "zákon, ktorým sa mení zákon č. 36/2005 Z. z. o rodine")
        self.assertEqual(res.issue_areas, [9])

    def test_without_an_approved_list_there_are_no_terms_and_never_english(self):
        tax = skr.load_taxonomy(os.path.join(FIX, "no-such-taxonomy.yaml"))
        self.assertEqual(tax.terms, {})
        self.assertEqual(filt.filter_item(tax, WL, self.TITLE).issue_areas, [])


class CollectorTests(unittest.TestCase):

    def setUp(self):
        self.conn = memdb()
        self.client = FakeClient()

    def test_tables_are_declared(self):
        for t in sk_store.TABLES:
            self.assertIn(t, db.TABLES)

    def test_the_watchlist_puts_the_amendment_on_our_ground_by_key(self):
        run_all(self.conn, self.client, tax=skr.empty_taxonomy())
        areas = json.loads(self.conn.execute(
            "SELECT areas FROM sk_bills WHERE bill_key='9/733'").fetchone()[0])
        self.assertEqual(areas, [5, 6, 9, 10])

    def test_votes_inherit_their_prints_areas(self):
        run_all(self.conn, self.client, tax=skr.empty_taxonomy())
        own, areas = self.conn.execute(
            "SELECT own_areas, areas FROM sk_divisions WHERE voting_id=56965").fetchone()
        self.assertEqual(json.loads(own), [])
        self.assertEqual(json.loads(areas), [5, 6, 9, 10])

    def test_positions_are_read_only_for_votes_on_our_ground(self):
        """With no taxonomy, only the watchlisted print's votes: 56965 has a
        page, 56254 does not and is a gap, and nothing else is fetched."""
        read, gaps = run_all(self.conn, self.client, tax=skr.empty_taxonomy())
        self.assertEqual(sorted(self.client.pages), [56254, 56965])
        self.assertEqual((read, gaps), (1, 1))
        n = self.conn.execute("SELECT COUNT(*) FROM sk_votes WHERE voting_id=56965").fetchone()[0]
        self.assertEqual(n, 150)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='sk-rollcalls'")
                         .fetchone()[0], 1)

    def test_the_club_is_stored_per_vote(self):
        run_all(self.conn, self.client, tax=skr.empty_taxonomy())
        clubs = {r[0] for r in self.conn.execute(
            "SELECT DISTINCT club FROM sk_votes WHERE voting_id=56965")}
        self.assertIn("SMER - SD", clubs)

    def test_a_vote_read_once_is_not_read_again(self):
        run_all(self.conn, self.client, tax=skr.empty_taxonomy())
        self.client.pages = []
        run_all(self.conn, self.client, tax=skr.empty_taxonomy())
        self.assertEqual(self.client.pages, [56254])   # only the one still owed

    def test_a_secret_ballot_is_never_fetched(self):
        run_all(self.conn, self.client, tax=skr.empty_taxonomy(), everything=True)
        self.assertNotIn(51445, self.client.pages)
        self.assertIn(58014, self.client.pages)

    def test_reclassify_brings_a_vote_onto_our_ground_and_queues_it(self):
        run_all(self.conn, self.client, tax=skr.empty_taxonomy())
        self.assertNotIn(56356, [r["voting_id"] for r in skr.pending_positions(self.conn, 9)])
        skr.reclassify(self.conn, TAX, log=lambda *_: None)
        areas = json.loads(self.conn.execute(
            "SELECT areas FROM sk_divisions WHERE voting_id=56356").fetchone()[0])
        self.assertEqual(areas, [1])
        self.assertIn(56356, [r["voting_id"] for r in skr.pending_positions(self.conn, 9)])

    def test_interpellations_are_classified(self):
        run_all(self.conn, self.client)
        rows = dict(self.conn.execute("SELECT int_id, areas FROM sk_interpellations"))
        self.assertEqual(json.loads(rows[3918]), [5])
        self.assertEqual(json.loads(rows[2669]), [])

    def test_a_rerun_re_stamps_every_list(self):
        run_all(self.conn, self.client)
        self.conn.execute("UPDATE sk_bills SET last_seen='2026-01-01'")
        self.conn.execute("UPDATE sk_divisions SET last_seen='2026-01-01'")
        run_all(self.conn, self.client)
        for t in ("sk_bills", "sk_divisions", "sk_members", "sk_interpellations"):
            self.assertEqual(self.conn.execute(
                "SELECT MIN(last_seen) FROM {0}".format(t)).fetchone()[0], TODAY, t)

    def test_exit_code_three_means_gaps_were_recorded(self):
        src = fixture("../../../tools/sk_rollcalls.py")
        self.assertIn("return 3 if gaps else 0", src)


class WatchlistTests(unittest.TestCase):

    def test_every_entry_is_keyed_term_slash_print_with_a_reason(self):
        with open(os.path.join(ROOT, "config", "watchlist-sk.yaml"), encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        for key, spec in raw["bills"].items():
            self.assertRegex(key, r"^\d+/\d+$")
            self.assertTrue(spec.get("why"))
            self.assertTrue(spec.get("areas"))
            self.assertTrue(all(1 <= a <= 13 for a in spec["areas"]))


class ScheduleTests(unittest.TestCase):
    """The weekly runs on the Mini first; GitHub is the backup."""

    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "mini_check", os.path.join(ROOT, "tools", "mini_check.py"))
        self.mc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mc)
        with open(os.path.join(ROOT, ".github", "workflows", "sk-weekly.yml"), encoding="utf-8") as fh:
            self.yml = fh.read()
        self.crons = re.findall(r'cron:\s*"([^"]+)"', self.yml)

    def _decide(self, cron, now, last):
        return self.mc.decide("schedule", cron, last, now, grace_minutes=200)[0]

    def test_one_mini_run_covers_both_slots_summer_and_winter(self):
        utc = dt.timezone.utc
        for last in ("2026-07-07T01:00:05Z", "2026-11-10T02:00:05Z"):    # 02:00 London, BST / GMT
            for hour in (2, 4):
                now = dt.datetime.fromisoformat(last[:10] + "T{0:02d}:05:00".format(hour)).replace(
                    tzinfo=utc)
                self.assertFalse(self._decide("0 {0} * * 2".format(hour), now, last), (last, hour))

    def test_last_weeks_mini_run_does_not_cover_this_week(self):
        now = dt.datetime(2026, 10, 13, 2, 5, tzinfo=dt.timezone.utc)
        self.assertTrue(self._decide("0 2 * * 2", now, "2026-10-06T01:00:05Z"))

    def test_the_slots_collide_with_no_other_workflow(self):
        import glob
        self.assertEqual(self.crons, ["0 2 * * 2", "0 4 * * 2"])
        others = set()
        for path in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
            if path.endswith("sk-weekly.yml"):
                continue
            with open(path, encoding="utf-8") as fh:
                others |= set(re.findall(r'^\s*-\s*cron:\s*"([^"]+)"', fh.read(), re.M))
        self.assertFalse(set(self.crons) & others)

    def test_the_gate_the_plist_and_the_job_agree(self):
        self.assertIn("job: SK_WEEKLY", self.yml)
        self.assertIn("grace-minutes: 200", self.yml)
        self.assertIn('SK_PUBLISH: "false"', self.yml)
        with open(os.path.join(ROOT, "ops", "launchd", "net.citizengo.parlmonitor.sk-weekly.plist"),
                  encoding="utf-8") as fh:
            plist = fh.read()
        self.assertIn("<string>sk-weekly</string>", plist)
        self.assertIn("<key>Weekday</key><integer>2</integer><key>Hour</key><integer>2</integer>", plist)
        with open(os.path.join(ROOT, "jobs", "sk-weekly.sh"), encoding="utf-8") as fh:
            job = fh.read()
        self.assertIn('GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Slovakia weekly}"', job)
        self.assertIn("db_state.py --push", job)



class EditionRebelTests(unittest.TestCase):
    """The edition names members who voted against their club's majority;
    a non-attached deputy (stored with no club) has no club to break from."""

    def test_no_club_members_are_not_against_their_group(self):
        from src import country_edition as ce
        from src.editions import sk
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE sk_votes (voting_id, mp_id, club, position)")
        conn.execute("CREATE TABLE sk_members (mp_id, name)")
        votes = [(1, "Smer", "Z"), (2, "Smer", "Z"), (3, "Smer", "P"),
                 (4, None, "Z"), (5, None, "Z"), (6, None, "P")]
        for mp, club, pos in votes:
            conn.execute("INSERT INTO sk_votes VALUES (9, ?, ?, ?)", (mp, club, pos))
            conn.execute("INSERT INTO sk_members VALUES (?, ?)", (mp, "Member %d" % mp))
        pos = sk.positions(conn, {"is_secret": 0, "voting_id": 9})
        self.assertEqual(len(pos), 6)
        self.assertEqual(ce.rebels(pos, sk.YES, sk.NO), ["Member 3 (Smer)"])

if __name__ == "__main__":
    unittest.main()
