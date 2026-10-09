"""Australia's Federal Parliament: members, bills, divisions (tools/au_rollcalls.py).

No network. The fixtures under tests/fixtures/au are REAL, trimmed: whole
elements cut from the OpenAustralia day files, member lists, Handbook pages
and Register of Legislation answers fetched on 9 October 2026, nothing edited
inside an element (see docs/australia-scope.md).
"""

import datetime as dt
import importlib.util
import json
import os
import re
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import au_store, db, filter as filt  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "au")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


aur = _load("au_rollcalls")
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = aur.empty_watchlist()
TODAY = "2026-10-09"


def fixture(name):
    with open(os.path.join(FIX, name), "rb") as fh:
        return fh.read()


def day(name, chamber, date):
    return aur.parse_day(fixture(name), chamber, date)


class FakeClient:
    """Serves the fixtures by URL; anything else raises FetchError."""

    def __init__(self, pages=None):
        self.pages = dict(pages or {})
        self.asked = []

    def _get(self, url):
        self.asked.append(url)
        if url not in self.pages:
            raise FetchError(url, "au", "x", 1, "404")
        page = self.pages[url]
        if isinstance(page, Exception):
            raise page
        return page

    def get_bytes(self, url, feed, slug, archive=True, **kw):
        return self._get(url)

    def get_text(self, url, feed, slug, archive=True, **kw):
        return self._get(url).decode("utf-8")

    def get_json(self, url, feed, slug, archive=True, **kw):
        return json.loads(self._get(url))


def member_pages():
    pages = {aur.MEMBERS.format(n): fixture(n + ".xml") for n in aur.MEMBER_FILES}
    # Served a hundred at a time, as the Handbook does (it refuses $top > 100).
    hb = json.loads(fixture("handbook_current.json"))["value"]
    for skip in range(0, len(hb) + 1, aur.HANDBOOK_PAGE):
        pages[aur.HANDBOOK.format(aur.HANDBOOK_PAGE, skip)] = json.dumps(
            {"value": hb[skip:skip + aur.HANDBOOK_PAGE]}).encode("utf-8")
    return pages


def store():
    return db.init_db(sqlite3.connect(":memory:"))


def with_members(conn=None):
    conn = conn or store()
    aur.pull_members(conn, FakeClient(member_pages()), TODAY, aur.PARLIAMENTS[48][0], log=lambda *_: None)
    return conn


class SchemaTests(unittest.TestCase):
    def test_every_au_table_is_declared_and_created(self):
        conn = store()
        have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in au_store.TABLES:
            self.assertIn(t, db.TABLES)
            self.assertIn(t, have)


class ListingTests(unittest.TestCase):
    def test_the_apache_index_gives_each_day_and_its_stamp(self):
        rows = aur.parse_listing(fixture("listing_senate.html").decode("utf-8"))
        self.assertIn(("2026-09-17", "2026-09-18 09:05"), rows)
        # A re-parsed day carries the re-parse's stamp, not the sitting's.
        self.assertIn(("2026-07-01", "2026-08-25 19:31"), rows)
        self.assertEqual(rows, sorted(rows))

    def test_a_challenge_page_lists_nothing(self):
        self.assertEqual(aur.parse_listing("<html>Just a moment...</html>"), [])


class DayParsingTests(unittest.TestCase):
    def setUp(self):
        self.day = day("senate_2026-09-17.xml", "senate", "2026-09-17")
        self.divs = {d["number"]: d for d in self.day["divisions"]}

    def test_divisions_come_with_their_counts(self):
        d = self.divs[1]
        self.assertEqual((d["ayes"], d["noes"], d["pairs"]), (34, 19, 11))
        self.assertEqual(aur.division_key(d), "senate-2026-09-17-1")

    def test_a_division_joins_its_debates_bill_by_id(self):
        self.assertEqual(self.divs[1]["bills"], ["s1518"])
        self.assertEqual(self.divs[8]["bills"], ["r7501"])

    def test_business_with_no_bill_joins_none(self):
        # A committee reference: its own words are all it has.
        self.assertEqual(self.divs[4]["bills"], [])
        self.assertTrue(self.divs[4]["motion"].startswith("I move:That the following matter be referred"))

    def test_the_chairs_question_and_the_motion_are_kept_apart(self):
        self.assertEqual(self.divs[1]["question"], "The question is that the second reading be agreed to.")
        self.assertEqual(self.divs[1]["motion"], "I move:That the question be now put.")

    def test_pairs_are_paired_and_never_given_a_side(self):
        votes = self.divs[1]["votes"]
        paired = [v for v in votes if v["position"] == "Paired"]
        self.assertEqual(len(paired), 22)          # 11 pairs, two senators each
        self.assertEqual(len(votes) - len(paired), 34 + 19)
        self.assertEqual({v["position"] for v in votes}, {"Aye", "No", "Paired"})

    def test_a_heading_names_the_stage(self):
        self.assertIn(("s1518", "Second Reading"), self.day["stages"])
        self.assertEqual(aur.heading_stage("X Bill 2026; Y Bill 2026; Third Reading"), "Third Reading")
        self.assertIsNone(aur.heading_stage("Appropriation Bill (No. 1) 2025-2026"))
        self.assertIsNone(aur.heading_stage("Cognates; Customs Tariff Amendment Bill 2025"))
        self.assertIsNone(aur.heading_stage("X Bill 2026; Order for the Production of Documents"))


class MemberTests(unittest.TestCase):
    def setUp(self):
        self.conn = with_members()

    def test_a_chair_votes_under_their_party_not_their_role(self):
        # Sue Lines, President of the Senate: OpenAustralia writes "PRES"
        # where the party goes on her current spell.
        party, role = self.conn.execute("SELECT party, role FROM au_offices "
                                        "WHERE office_id='lord/100944'").fetchone()
        self.assertEqual((party, role), ("Australian Labor Party", "PRES"))
        party, role = self.conn.execute("SELECT party, role FROM au_offices "
                                        "WHERE office_id='member/815'").fetchone()
        self.assertEqual((party, role), ("Australian Labor Party", "SPK"))

    def test_a_party_change_is_a_new_office_and_both_resolve_to_one_person(self):
        # Barnaby Joyce: Independent from 27 November 2025, One Nation from
        # 8 December. Two offices, one person, two parties.
        rows = self.conn.execute("SELECT office_id, person_id, party FROM au_offices "
                                 "WHERE office_id IN ('member/856', 'member/857')").fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({r[1] for r in rows}), 1)
        self.assertEqual(len({r[2] for r in rows}), 2)

    def test_the_handbook_id_is_kept_only_when_exactly_one_matches(self):
        n, with_phid = self.conn.execute("SELECT COUNT(*), COUNT(phid) FROM au_members "
                                         "WHERE current=1").fetchone()
        self.assertGreater(with_phid, 0)
        self.assertLessEqual(with_phid, n)
        idx = aur.phid_index([
            {"PHID": "A1", "FamilyName": "SMITH", "Electorate": "Bean", "MPorSenator": ["Member"]},
            {"PHID": "B2", "FamilyName": "SMITH", "Electorate": "Bean", "MPorSenator": ["Member"]},
            {"PHID": "C3", "FamilyName": "WONG", "SenateState": "South Australia",
             "MPorSenator": ["Senator"]}])
        self.assertEqual(len(idx[("house", "smith", "bean")]), 2)     # ambiguous: left blank
        # OpenAustralia writes "SA", the Handbook "South Australia": one key.
        self.assertEqual(idx[("senate", "wong", aur.electorate_key("senate", "SA"))], ["C3"])

    def test_a_handbook_failure_is_a_gap_and_the_members_still_load(self):
        conn = store()
        pages = member_pages()
        pages[aur.HANDBOOK.format(aur.HANDBOOK_PAGE, 0)] = FetchError("u", "au", "x", 1, "400")
        n, gaps = aur.pull_members(conn, FakeClient(pages), TODAY, aur.PARLIAMENTS[48][0],
                                   log=lambda *_: None)
        self.assertGreater(n, 100)
        self.assertEqual(gaps, 1)
        self.assertEqual(conn.execute("SELECT COUNT(phid) FROM au_members").fetchone()[0], 0)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.conn = with_members()

    def _store_day(self, name, chamber, date, wl_path=None):
        d = day(name, chamber, date)
        for bid, title in d["bills"].items():
            aur.store_bill(self.conn, TAX, WL, bid, title, date, TODAY, wl_path)
        out = []
        for div in d["divisions"]:
            out.append(aur.store_division(self.conn, div, TAX, WL, aur._offices(self.conn), TODAY))
        return out

    def test_every_vote_is_stored_with_the_party_at_the_vote(self):
        self._store_day("senate_2026-09-17.xml", "senate", "2026-09-17")
        rows = self.conn.execute("SELECT position, COUNT(*) FROM au_votes WHERE "
                                 "division_key='senate-2026-09-17-1' GROUP BY position").fetchall()
        self.assertEqual(dict(rows), {"Aye": 34, "No": 19, "Paired": 22})
        parties = {p for (p,) in self.conn.execute("SELECT DISTINCT party FROM au_votes")}
        self.assertFalse(parties & set(aur.ROLE_PARTIES))
        self.assertNotIn(None, parties)

    def test_an_unknown_office_is_dropped_and_reported_never_guessed(self):
        self.conn.execute("DELETE FROM au_offices WHERE office_id='lord/100944'")
        d = day("senate_2026-09-17.xml", "senate", "2026-09-17")["divisions"][0]
        key, _areas, unknown = aur.store_division(self.conn, d, TAX, WL, aur._offices(self.conn), TODAY)
        stored = self.conn.execute("SELECT COUNT(*) FROM au_votes WHERE division_key=?",
                                   (key,)).fetchone()[0]
        self.assertEqual(stored + len(unknown), len(d["votes"]))
        self.assertEqual(unknown, ["lord/100944"])

    def test_a_division_on_our_ground_by_its_own_text(self):
        # Senator Cash's motion to introduce the Sex Discrimination Amendment
        # (Restoring Common Sense and Recognising Biological Sex) Bill 2026.
        ((key, areas, _u),) = self._store_day("senate_2026-07-01.xml", "senate", "2026-07-01")
        self.assertEqual(key, "senate-2026-07-01-16")
        self.assertIn(5, areas)
        own = json.loads(self.conn.execute("SELECT own_areas FROM au_divisions WHERE "
                                           "division_key=?", (key,)).fetchone()[0])
        self.assertIn(5, own)

    def test_a_division_inherits_its_bills_areas_and_keeps_its_own_apart(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
            fh.write('bills:\n  "s1518": {areas: [13], why: "test"}\n')
        try:
            self._store_day("senate_2026-09-17.xml", "senate", "2026-09-17", wl_path=fh.name)
        finally:
            os.unlink(fh.name)
        own, areas = self.conn.execute("SELECT own_areas, areas FROM au_divisions WHERE "
                                       "division_key='senate-2026-09-17-1'").fetchone()
        self.assertEqual(json.loads(own), [])
        self.assertEqual(json.loads(areas), [13])

    def test_an_earlier_parliaments_bill_id_is_stored_under_its_own_parliament(self):
        # 30 July 2025: OpenAustralia tags the 48th's Appropriation Bill
        # (No. 1) debate with r7327, the 47th's lapsed bill of the same name.
        self._store_day("house_2025-07-30.xml", "house", "2025-07-30")
        got = dict(self.conn.execute("SELECT bill_id, parliament FROM au_bills"))
        self.assertEqual(got["r7327"], 47)
        self.assertEqual(got["r7335"], 48)

    def test_a_restored_division_upserts_rather_than_duplicates(self):
        self._store_day("senate_2026-09-17.xml", "senate", "2026-09-17")
        self._store_day("senate_2026-09-17.xml", "senate", "2026-09-17")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM au_divisions").fetchone()[0], 3)


class ClassificationTests(unittest.TestCase):
    def test_the_watchlist_is_applied_by_id_never_by_title(self):
        title = "Online Safety Amendment (Strengthening Enforcement for the Social Media Minimum Age) Bill 2026"
        self.assertEqual(aur.classify_bill(TAX, WL, "r7512", title).issue_areas, [6, 7])
        # The same words under another ID borrow nothing.
        self.assertEqual(aur.classify_bill(TAX, WL, "r9999", title).issue_areas, [])

    def test_watchlist_entries_are_well_formed(self):
        wl = au_store.watchlist()
        self.assertGreater(len(wl), 5)
        for key, (areas, why) in wl.items():
            self.assertRegex(key, r"^[rs]\d+$")
            self.assertTrue(areas and all(1 <= a <= 13 for a in areas), key)
            self.assertGreater(len(why or ""), 30, key)
            self.assertNotIn("—", why, key)        # no em dashes

    def test_debate_speeches_lend_nothing(self):
        d = {"minor": "Cost of Living", "major": "MATTERS OF URGENCY",
             "question": "The question is that the motion be agreed to.", "motion": None}
        own, areas = aur.classify_division(TAX, WL, d, [])
        self.assertEqual(areas, [])


class PullTests(unittest.TestCase):
    def _client(self, stamp="2026-09-18 09:05"):
        listing = fixture("listing_senate.html").decode("utf-8").replace(
            "2026-09-18 09:05", stamp).encode("utf-8")
        pages = member_pages()
        pages[aur.LISTING.format("representatives")] = b"<html><pre></pre></html>"
        pages[aur.LISTING.format("senate")] = listing
        pages[aur.DAY.format("senate", "2026-09-17")] = fixture("senate_2026-09-17.xml")
        pages[aur.DAY.format("senate", "2026-07-01")] = fixture("senate_2026-07-01.xml")
        return FakeClient(pages)

    def test_a_pull_reads_the_parliaments_days_and_records_what_it_could_not(self):
        conn = with_members()
        client = self._client()
        s = aur.pull_days(conn, client, TODAY, tax=TAX, wl=WL, log=lambda *_: None)
        # 2025-03-25/26 are the 47th's and never asked for; four listed days
        # of September are absent from the fake and are gaps; an empty House
        # listing is a gap, not "no sittings".
        self.assertFalse(any("2025-03-2" in u for u in client.asked))
        self.assertEqual(s["files"], 2)
        self.assertEqual(s["gaps"], 1 + 4)
        gaps = [g for (g,) in conn.execute("SELECT detail FROM gaps WHERE feed=?", (aur.FEED,))]
        self.assertTrue(any("representatives" in g for g in gaps))

    def test_an_unchanged_day_is_not_read_twice_and_a_reparsed_one_is(self):
        conn = with_members()
        aur.pull_days(conn, self._client(), TODAY, tax=TAX, wl=WL, log=lambda *_: None)
        again = self._client()
        aur.pull_days(conn, again, TODAY, tax=TAX, wl=WL, log=lambda *_: None)
        self.assertNotIn(aur.DAY.format("senate", "2026-09-17"), again.asked)
        moved = self._client(stamp="2026-10-01 09:05")
        aur.pull_days(conn, moved, TODAY, tax=TAX, wl=WL, log=lambda *_: None)
        self.assertIn(aur.DAY.format("senate", "2026-09-17"), moved.asked)

    def test_acts_mark_their_bills_and_an_unseen_bill_is_added_from_its_act(self):
        conn = store()
        aur.store_bill(conn, TAX, WL, "r7335", "Fair Work Amendment (Protecting Penalty and "
                       "Overtime Rates) Bill 2025", "2025-07-24", TODAY)
        pages = {aur.FRL_ACTS.format(2025): fixture("frl_acts_2025.json"),
                 aur.FRL_ACTS.format(2026): b'{"value": []}'}
        acts, matched, added, gaps = aur.pull_acts(conn, FakeClient(pages), TODAY, tax=TAX, wl=WL,
                                                   log=lambda *_: None)
        self.assertEqual((matched, gaps), (1, 0))
        self.assertEqual(added, acts - 1)
        act = conn.execute("SELECT act_id, assent_date FROM au_bills WHERE bill_id='r7335'").fetchone()
        self.assertTrue(act[0].startswith("C2025A"))
        title = conn.execute("SELECT title FROM au_bills WHERE bill_id='r7354'").fetchone()[0]
        self.assertEqual(title, "Appropriation Bill (No. 1) 2025-2026")

    def test_the_bill_link_on_an_act_parses(self):
        uri = ('https://parlinfo.aph.gov.au/parlInfo/search/display/display.w3p;query=Id%3A'
               '"legislation%2Fbillhome%2Fr7473"')
        self.assertEqual(aur.bill_of_act(uri), "r7473")
        self.assertIsNone(aur.bill_of_act(None))

    def test_reclassify_is_stable_and_offline(self):
        conn = with_members()
        aur.pull_days(conn, self._client(), TODAY, tax=TAX, wl=WL, log=lambda *_: None)
        aur.reclassify(conn, tax=TAX, log=lambda *_: None)
        self.assertEqual(aur.reclassify(conn, tax=TAX, log=lambda *_: None), (0, 0))


class ScheduleTests(unittest.TestCase):
    """The weekly runs on the Mini first; GitHub is the backup."""

    def setUp(self):
        self.mc = _load("mini_check")
        with open(os.path.join(ROOT, ".github", "workflows", "au-weekly.yml"), encoding="utf-8") as fh:
            self.yml = fh.read()
        self.crons = re.findall(r'cron:\s*"([^"]+)"', self.yml)

    def _decide(self, cron, now, last):
        return self.mc.decide("schedule", cron, last, now, grace_minutes=200)[0]

    def test_one_mini_run_covers_both_slots_summer_and_winter(self):
        utc = dt.timezone.utc
        for last in ("2026-07-10T01:00:05Z", "2026-11-13T02:00:05Z"):    # 02:00 London, BST / GMT
            day_ = last[:10]
            for hour in (2, 4):
                now = dt.datetime.fromisoformat(day_ + "T{0:02d}:05:00".format(hour)).replace(tzinfo=utc)
                self.assertFalse(self._decide("0 {0} * * 5".format(hour), now, last), (last, hour))

    def test_last_weeks_mini_run_does_not_cover_this_week(self):
        now = dt.datetime(2026, 10, 16, 2, 5, tzinfo=dt.timezone.utc)
        self.assertTrue(self._decide("0 2 * * 5", now, "2026-10-09T01:00:05Z"))

    def test_the_slots_collide_with_no_other_workflow_and_leave_ireland_room(self):
        import glob
        self.assertEqual(self.crons, ["0 2 * * 5", "0 4 * * 5"])
        others = set()
        for path in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
            if path.endswith("au-weekly.yml"):
                continue
            with open(path, encoding="utf-8") as fh:
                others |= set(re.findall(r'^\s*-\s*cron:\s*"([^"]+)"', fh.read(), re.M))
        self.assertFalse(set(self.crons) & others)
        for cron in self.crons:
            hour = int(cron.split()[1])
            self.assertFalse(6 <= hour <= 14, cron)

    def test_the_gate_and_the_plist_agree(self):
        self.assertIn("job: AU_WEEKLY", self.yml)
        self.assertIn("grace-minutes: 200", self.yml)
        with open(os.path.join(ROOT, "ops", "launchd", "net.citizengo.parlmonitor.au-weekly.plist"),
                  encoding="utf-8") as fh:
            plist = fh.read()
        self.assertIn("<string>au-weekly</string>", plist)
        self.assertIn("<key>Weekday</key><integer>5</integer><key>Hour</key><integer>2</integer>", plist)
        self.assertTrue(os.path.exists(os.path.join(ROOT, "jobs", "au-weekly.sh")))


if __name__ == "__main__":
    unittest.main()
