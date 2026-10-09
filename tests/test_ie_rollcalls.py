"""Ireland: Oireachtas members, bills and divisions (tools/ie_rollcalls.py). No network.

The fixtures in tests/fixtures/ie are real API records saved on 9 October
2026: both Houses' full rosters, eleven bills and six divisions. Only the
`head` of each file was rebuilt (it saturates at 10,000 and is never read).
"""

import copy
import gzip
import importlib.util
import json
import os
import sqlite3
import sys
import unittest
from urllib.parse import parse_qs, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, ie_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FX = os.path.join(ROOT, "tests", "fixtures", "ie")


def _load():
    spec = importlib.util.spec_from_file_location(
        "ie_rollcalls", os.path.join(ROOT, "tools", "ie_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ier = _load()
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = ier.empty_watchlist()
CURRENT = ("dail/34", "seanad/27")


def fixture(name):
    path = os.path.join(FX, name)
    opener = gzip.open if name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


MEMBERS = {"dail/34": fixture("members-dail-34.json.gz"),
           "seanad/27": fixture("members-seanad-27.json.gz")}
BILLS = fixture("legislation.json")
VOTES = fixture("votes.json")


def bill_rec(key):
    return next(r for r in BILLS["results"]
                if "{0}/{1}".format(r["bill"]["billYear"], r["bill"]["billNo"]) == key)


def vote_rec(key):
    return next(r for r in VOTES["results"] if ier.division_key(r["division"]["uri"]) == key)


class FakeClient:
    """Answers like the API: lists by query, paged by limit and skip."""

    def __init__(self, members=None, bills=None, votes=None, fail=()):
        self.members = MEMBERS if members is None else members
        self.bills = BILLS if bills is None else bills
        self.votes = VOTES if votes is None else votes
        self.fail = fail
        self.asked = []

    def get_json(self, url, feed, slug, archive=True, **kw):
        self.asked.append(url)
        parts = urlsplit(url)
        path = parts.path.rsplit("/", 1)[-1]
        q = {k: v[0] for k, v in parse_qs(parts.query).items()}
        if path in self.fail:
            raise FetchError(url, feed, slug, 1, "HTTP 503")
        if path == "members":
            recs = (self.members.get(ier.house_key(q["chamber_id"])) or {}).get("results", [])
        elif path == "legislation":
            recs = self.bills["results"]
        elif path == "votes":
            hk = ier.house_key(q.get("chamber_id", ""))
            recs = [r for r in self.votes["results"]
                    if (hk and ier.house_key(r["division"]["house"]["uri"]) == hk)
                    or (q.get("chamber_type") == "committee"
                        and r["division"]["house"].get("committeeCode"))]
        else:
            return {"message": "Not found."}
        skip, limit = int(q.get("skip", 0)), int(q.get("limit", 10))
        # The real head saturates at 10,000; say so, to prove nobody reads it.
        return {"head": {"counts": {"resultCount": 10000}}, "results": recs[skip:skip + limit]}


def store():
    return db.init_db(sqlite3.connect(":memory:"))


def loaded(conn=None):
    conn = conn or store()
    ier.pull_members(conn, FakeClient(), "2026-10-09", (("dail", 34), ("seanad", 27)),
                     log=lambda *a: None)
    ier.pull_bills(conn, FakeClient(), "2026-10-09", current=CURRENT, tax=TAX, wl=WL,
                   log=lambda *a: None)
    return conn


class MemberTests(unittest.TestCase):
    def test_a_party_change_is_kept_as_dated_spells(self):
        conn = loaded()
        spells = conn.execute("SELECT party, start_date, end_date FROM ie_member_parties WHERE "
                              "member_code='Eoin-Hayes.D.2024-11-29' ORDER BY start_date").fetchall()
        self.assertEqual(spells, [("Social Democrats", "2024-11-29", "2025-01-10"),
                                  ("Independent", "2025-01-10", "2025-04-10"),
                                  ("Social Democrats", "2025-04-10", None)])

    def test_party_at_a_date_takes_the_spell_that_starts_on_the_day(self):
        book = ier.PartyBook(loaded())
        code = "Eoin-Hayes.D.2024-11-29"
        self.assertEqual(book.at(code, "2025-01-09", "dail/34"), "Social Democrats")
        self.assertEqual(book.at(code, "2025-01-10", "dail/34"), "Independent")
        self.assertEqual(book.at(code, "2025-04-10", "dail/34"), "Social Democrats")
        self.assertIsNone(book.at(code, "2024-11-01", "dail/34"))   # before he sat
        self.assertIsNone(book.at(code, "2025-02-01", "seanad/27"))  # not a senator

    def test_both_rosters_store_with_constituency_and_panel(self):
        conn = loaded()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ie_members").fetchone()[0], 235)
        self.assertEqual(conn.execute(
            "SELECT house, house_no, party, represents FROM ie_members "
            "WHERE member_code='Shay-Brennan.D.2024-11-29'").fetchone(),
            ("dail", 34, "Fianna Fáil", "Dublin Rathdown"))
        # Two TDs left the 34th Dail (one became President): the end is kept.
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ie_members WHERE house='dail' "
                                      "AND end_date IS NOT NULL").fetchone()[0], 2)

    def test_an_empty_roster_is_a_gap_not_a_quiet_success(self):
        conn = store()
        n, gaps = ier.pull_members(conn, FakeClient(members={}), "2026-10-09",
                                   (("dail", 35),), log=lambda *a: None)
        self.assertEqual((n, gaps), (0, 1))
        self.assertIn("no members", conn.execute("SELECT detail FROM gaps").fetchone()[0])


class BillTests(unittest.TestCase):
    def test_current_is_not_alive_when_the_bill_lapsed(self):
        # Voluntary Assisted Dying Bill 2024: 'Current' in the API, lapsed at
        # the dissolution of 8 November 2024, never restored.
        b = ier.parse_bill(bill_rec("2024/50"), CURRENT)
        self.assertEqual((b["status"], b["last_stage_house"], b["lapsed_at"]),
                         ("Current", "dail/33", "2024-11-08"))
        self.assertFalse(b["alive"])

    def test_a_restored_bill_is_alive_though_its_last_stage_is_in_an_old_dail(self):
        b = ier.parse_bill(bill_rec("2018/34"), CURRENT)
        self.assertEqual(b["last_stage_house"], "dail/32")
        self.assertTrue(b["restored_at"])
        self.assertTrue(b["alive"])

    def test_enacted_and_defeated_bills_are_not_alive(self):
        enacted = ier.parse_bill(bill_rec("2026/74"), CURRENT)
        self.assertEqual((enacted["status"], enacted["act"]), ("Enacted", "Act 32 of 2026"))
        self.assertFalse(enacted["alive"])
        self.assertFalse(ier.parse_bill(bill_rec("2026/40"), CURRENT)["alive"])
        self.assertTrue(ier.parse_bill(bill_rec("2026/10"), CURRENT)["alive"])

    def test_bills_classify_on_short_and_long_title(self):
        res = ier.classify_bill(TAX, WL, ier.parse_bill(bill_rec("2026/47"), CURRENT))
        # Health (Abolition of Three Day Wait Rule) (Amendment) Bill 2026: the
        # title says nothing; the long title says termination of pregnancy.
        self.assertEqual(res.issue_areas, [1])

    def test_the_watchlist_applies_by_key(self):
        res = ier.classify_bill(TAX, WL, ier.parse_bill(bill_rec("2026/7"), CURRENT))
        self.assertEqual(res.issue_areas, [7])
        self.assertIn("watch:2026/7", res.watchlist_hits)

    def test_sponsors_by_member_and_by_office(self):
        conn = loaded()
        pmb = conn.execute("SELECT member_code, office FROM ie_sponsors WHERE bill_key='2026/47'").fetchall()
        self.assertTrue(pmb and all(code and code.count(".") >= 2 for code, _ in pmb))
        gov = conn.execute("SELECT sponsor, member_code, office FROM ie_sponsors "
                           "WHERE bill_key='2026/74'").fetchall()
        self.assertEqual(gov, [("Minister for Health", None, "Minister for Health")])

    def test_ministerial_titles_do_not_file_a_text_under_migration(self):
        text = "asked the Minister for Justice, Home Affairs and Migration about court delays"
        self.assertNotIn(11, filt.filter_item(TAX, WL, ier.strip_offices(text)).issue_areas)
        # Migration said anywhere else still counts.
        self.assertIn(11,filt.filter_item(TAX, WL, ier.strip_offices(
            text + " and migration policy")).issue_areas)

    def test_the_office_is_what_matched_before_it_was_struck(self):
        text = "the Minister for Justice, Home Affairs and Migration"
        self.assertIn(11, filt.filter_item(TAX, WL, text).issue_areas)
        self.assertEqual(filt.filter_item(TAX, WL, ier.strip_offices(text)).issue_areas, [])


class DivisionTests(unittest.TestCase):
    def test_keys_are_the_uri_path_because_vote_ids_restart(self):
        self.assertEqual(ier.division_key(
            "https://data.oireachtas.ie/ie/oireachtas/division/house/dail/34/2026-10-06/vote_214"),
            "dail/34/2026-10-06/vote_214")
        self.assertEqual(ier.division_key(
            "https://data.oireachtas.ie/ie/oireachtas/division/committee/dail/34/"
            "select_committee_on_health/2026-05-13/vote_1"),
            "committee/dail/34/select_committee_on_health/2026-05-13/vote_1")

    def test_a_division_parses_with_every_vote(self):
        d = ier.parse_division(vote_rec("dail/34/2025-12-17/vote_205"))
        self.assertEqual((d["chamber"], d["house_key"], d["outcome"], d["ta"], d["nil"]),
                         ("dail", "dail/34", "Lost", 71, 73))
        self.assertEqual(len(d["positions"]), d["ta"] + d["nil"] + (d["staon"] or 0))
        # Tá, Níl and Staon in one English vocabulary; Staon is recorded by name.
        self.assertEqual({p["position"] for p in d["positions"]}, {"Yes", "No", "Abstain"})
        self.assertEqual(sum(p["position"] == "Abstain" for p in d["positions"]), d["staon"])

    def test_a_committee_division_belongs_to_its_parent_house(self):
        d = ier.parse_division(vote_rec(
            "committee/dail/34/select_committee_on_arts_media_communications_culture_and_sport/"
            "2026-09-22/vote_1"))
        self.assertEqual((d["chamber"], d["house_key"]), ("committee", "dail/34"))
        self.assertEqual(d["committee"], "Select Committee on Arts, Media, Communications, Culture and Sport")

    def test_votes_join_bills_by_debate_section_id(self):
        conn = loaded()
        stored, ours, gaps = ier.pull_divisions(conn, FakeClient(), "2026-10-09",
                                                (("dail", 34), ("seanad", 27)), tax=TAX, wl=WL,
                                                log=lambda *a: None)
        self.assertEqual((stored, gaps), (6, 0))
        rows = dict(conn.execute("SELECT division_key, bill_key FROM ie_divisions"))
        self.assertEqual(rows["seanad/27/2025-11-05/vote_1"], "2022/14")
        self.assertEqual(rows["dail/34/2026-06-17/vote_149"], "2026/47")
        self.assertEqual(rows["dail/34/2026-03-04/vote_58"], "2026/7")
        self.assertEqual(rows["committee/dail/34/select_committee_on_arts_media_communications_"
                              "culture_and_sport/2026-09-22/vote_1"], "2026/54")

    def test_an_unlisted_section_is_never_joined_on_its_title(self):
        # The motion of 17 December 2025 to restore an abortion bill: its debate
        # section is not in any bill record, so no bill_key -- the printed name
        # is kept as text, and the vote still lands on its own words.
        conn = loaded()
        ier.pull_divisions(conn, FakeClient(), "2026-10-09", (("dail", 34),), committees=False,
                           tax=TAX, wl=WL, log=lambda *a: None)
        row = conn.execute("SELECT bill_key, debate_bill, own_areas, areas FROM ie_divisions "
                           "WHERE division_key='dail/34/2025-12-17/vote_205'").fetchone()
        self.assertEqual(row[:2], (None, "Health (Regulation of Termination of Pregnancy) "
                                         "(Amendment) Bill 2023"))
        self.assertEqual((json.loads(row[2]), json.loads(row[3])), ([1], [1]))

    def test_an_amendment_vote_inherits_its_bills_areas_and_keeps_its_own_apart(self):
        conn = loaded()
        ier.pull_divisions(conn, FakeClient(), "2026-10-09", (("dail", 34),), committees=False,
                           tax=TAX, wl=WL, log=lambda *a: None)
        own, areas, subject = conn.execute(
            "SELECT own_areas, areas, subject FROM ie_divisions "
            "WHERE division_key='dail/34/2026-03-04/vote_58'").fetchone()
        self.assertEqual(subject, "Amendment put:")
        self.assertEqual((json.loads(own), json.loads(areas)), ([], [7]))

    def test_party_is_the_party_at_the_vote(self):
        conn = loaded()
        ier.pull_divisions(conn, FakeClient(), "2026-10-09", (("dail", 34), ("seanad", 27)),
                           tax=TAX, wl=WL, log=lambda *a: None)
        self.assertEqual(conn.execute(
            "SELECT party FROM ie_votes WHERE division_key='dail/34/2025-01-23/vote_2' "
            "AND member_code='Eoin-Hayes.D.2024-11-29'").fetchone()[0], "Independent")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ie_votes WHERE party IS NULL").fetchone()[0], 0)

    def test_a_voter_with_no_spell_is_a_gap_never_a_guess(self):
        conn = loaded()
        rec = copy.deepcopy(vote_rec("dail/34/2026-06-17/vote_149"))
        rec["division"]["tallies"]["taVotes"]["members"].append(
            {"member": {"memberCode": "Nobody-Known.D.2030-01-01", "showAs": "Known, Nobody."}})
        client = FakeClient(votes={"results": [rec]})
        _stored, _ours, gaps = ier.pull_divisions(conn, client, "2026-10-09", (("dail", 34),),
                                                  committees=False, tax=TAX, wl=WL,
                                                  log=lambda *a: None)
        self.assertEqual(gaps, 1)
        self.assertIsNone(conn.execute("SELECT party FROM ie_votes WHERE "
                                       "member_code='Nobody-Known.D.2030-01-01'").fetchone()[0])
        self.assertIn("no party spell", conn.execute("SELECT detail FROM gaps").fetchone()[0])

    def test_a_section_that_carries_two_bills_joins_neither(self):
        conn = loaded()
        d = ier.parse_division(vote_rec("dail/34/2026-06-17/vote_149"))
        conn.execute("INSERT INTO ie_bill_debates (debate_uri, debate_section, bill_key) VALUES (?,?,?)",
                     (d["debate_uri"], d["debate_section"], "2026/10"))
        _areas, problems = ier.store_division(conn, d, TAX, WL, "2026-10-09", ier.PartyBook(conn))
        self.assertIsNone(conn.execute("SELECT bill_key FROM ie_divisions").fetchone()[0])
        self.assertIn("carries 2 bills", problems[0])

    def test_a_refused_list_is_a_gap_and_the_run_carries_on(self):
        conn = loaded()
        _s, _o, gaps = ier.pull_divisions(conn, FakeClient(fail=("votes",)), "2026-10-09",
                                          (("dail", 34),), committees=False, tax=TAX, wl=WL,
                                          log=lambda *a: None)
        self.assertEqual(gaps, 1)


class PagingTests(unittest.TestCase):
    def test_paging_runs_to_a_short_page_not_to_the_count(self):
        client = FakeClient()
        recs, complete = ier.fetch_all(client, "members",
                                       {"chamber_id": ier.HOUSE_URI.format("dail", 34)}, "m", size=50)
        self.assertTrue(complete)
        self.assertEqual(len(recs), 176)
        self.assertEqual(len(client.asked), 4)   # 50, 50, 50, 26

    def test_an_answer_without_results_is_an_error(self):
        with self.assertRaises(ValueError):
            ier.fetch_all(FakeClient(), "nonsense", {}, "x")


class ReclassifyTests(unittest.TestCase):
    def test_reclassify_is_idempotent(self):
        conn = loaded()
        ier.pull_divisions(conn, FakeClient(), "2026-10-09", (("dail", 34), ("seanad", 27)),
                           tax=TAX, wl=WL, log=lambda *a: None)
        self.assertEqual(ier.reclassify(conn, tax=TAX, log=lambda *a: None), (0, 0))


class ScheduleTests(unittest.TestCase):
    """Mini first, GitHub as backup, in a slot no other workflow uses."""

    WORKFLOWS = os.path.join(ROOT, ".github", "workflows")

    def _crons(self):
        import glob
        import re
        out = {}
        for path in glob.glob(os.path.join(self.WORKFLOWS, "*.yml")):
            with open(path, encoding="utf-8") as fh:
                out[os.path.basename(path)] = re.findall(r'^\s*- cron: "([^"]+)"', fh.read(), re.M)
        return out

    def test_the_slot_collides_with_no_other_cron(self):
        crons = self._crons()
        mine = crons.pop("ie-weekly.yml")
        self.assertEqual(mine, ["30 8 * * 5"])
        for name, theirs in crons.items():
            for c in theirs:
                minute, hour, _dom, _mon, dow = c.split()
                same_time = minute == "30" and "8" in hour.replace("-", ",").split(",")
                same_day = dow in ("*", "5") or ("-" in dow and int(dow[0]) <= 5 <= int(dow[-1]))
                self.assertFalse(same_time and same_day, "{0}: {1}".format(name, c))

    def test_the_workflow_is_gated_by_the_mini_and_shares_its_job_script(self):
        with open(os.path.join(self.WORKFLOWS, "ie-weekly.yml"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("uses: ./.github/workflows/mini-check.yml", text)
        self.assertIn("job: IE_WEEKLY", text)
        self.assertIn("bash jobs/ie-weekly.sh", text)
        self.assertIn("group: parl-monitor-state", text)
        with open(os.path.join(ROOT, "jobs", "ie-weekly.sh"), encoding="utf-8") as fh:
            job = fh.read()
        self.assertLess(job.index("raw_state.py --push"), job.index("db_state.py --push"))
        self.assertNotIn("mini_run: no-store", job)   # it writes the store

    def test_the_mini_runs_the_london_hour_the_cron_names_in_summer(self):
        import plistlib
        with open(os.path.join(ROOT, "ops", "launchd",
                               "net.citizengo.parlmonitor.ie-weekly.plist"), "rb") as fh:
            plist = plistlib.load(fh)
        self.assertEqual(plist["ProgramArguments"][-1], "ie-weekly")
        self.assertTrue(plist["ProgramArguments"][1].startswith("/Users/christopherjoyce/runner/"))
        self.assertEqual(plist["StartCalendarInterval"],
                         [{"Weekday": 5, "Hour": 9, "Minute": 30}])

    def test_a_mini_run_covers_the_slot_and_github_skips(self):
        import datetime as dt
        spec = importlib.util.spec_from_file_location(
            "mini_check", os.path.join(ROOT, "tools", "mini_check.py"))
        mc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mc)
        now = dt.datetime(2026, 10, 16, 11, 0, tzinfo=dt.timezone.utc)   # a late backup
        run, _why = mc.decide("schedule", "30 8 * * 5", "2026-10-16T08:30:04Z", now)
        self.assertFalse(run)
        run, _why = mc.decide("schedule", "30 8 * * 5", "2026-10-09T08:30:04Z", now)
        self.assertTrue(run)


class WatchlistTests(unittest.TestCase):
    def test_every_entry_is_a_bill_key_with_areas_and_a_reason(self):
        for key, (areas, why) in ie_store.watchlist().items():
            year, number = key.split("/")
            self.assertTrue(year.isdigit() and len(year) == 4 and number.isdigit(), key)
            self.assertTrue(areas and all(1 <= a <= 13 for a in areas), key)
            self.assertTrue(why, key)

    def test_the_tables_are_declared(self):
        for table in ie_store.TABLES:
            self.assertIn(table, db.TABLES)


if __name__ == "__main__":
    unittest.main()
