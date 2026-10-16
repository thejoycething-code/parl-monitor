"""Canada (federal) on the shared country frameworks (16 October 2026): the
reader adapter src/editions/ca.py, member profiles, the vote pages and bill
timelines, the week ahead (src/agendas/ca.py, rendered by tools/ca_monitor.py
in the countdown layout) and the same-day vote briefs, weekly and daily.
Fixtures: tests/fixtures/ca/ (pages saved 16 October 2026). No network."""

import gzip
import importlib.util
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import agenda, chamber_store, country5ca, db  # noqa: E402
from src import country_edition as ce  # noqa: E402
from src import country_vote_brief as cvb  # noqa: E402
from src import country_votes as cv  # noqa: E402
from src import edition_review  # noqa: E402
from src import member_profiles as mp  # noqa: E402
from src import vote_brief_sources as vs  # noqa: E402
from src.agendas import ca as ca_agenda  # noqa: E402
from src.editions import ca  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "ca")
TODAY = "2026-10-16"
C218 = "2nd reading of Bill C-218, An Act to amend the Criminal Code (medical assistance in dying)"


def fixture(name):
    with gzip.open(os.path.join(FIX, name), "rt", encoding="utf-8") as fh:
        return fh.read()


def _load_tool(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_store(path):
    conn = db.init_db(db.connect(path))
    agenda.ensure_schema(conn)
    members = [("1", "Ann Liberal", "Liberal", "Riding One", "Ontario"),
               ("2", "Bob Tory", "Conservative", "Riding Two", "Alberta"),
               ("3", "Cy Indy", "Independent", "Riding Three", "Quebec"),
               ("4", "Dee Liberal", "Liberal", "Riding Four", "Ontario"),
               ("5", "Eve Liberal", "Liberal", "Riding Five", "Ontario")]
    for pid, name, party, riding, prov in members:
        conn.execute("INSERT INTO ca_members (person_id, name, party, constituency, province, "
                     "first_seen, last_seen) VALUES (?,?,?,?,?,?,?)",
                     (pid, name, party, riding, prov, TODAY, TODAY))
    conn.execute("INSERT INTO ca_senators (person_id, name, affiliation, province, first_seen, "
                 "last_seen) VALUES ('senator-9', 'Doe, Jane', 'ISG', 'Manitoba', ?, ?)",
                 (TODAY, TODAY))
    conn.execute(
        "INSERT INTO ca_bills (bill_key, parliament, session, number, long_title, short_title, "
        "status, sponsor, sponsor_person_id, areas, matched_terms, tier, introduced_at, "
        "last_stage, last_stage_at, bill_type, first_seen, last_seen) VALUES "
        "('45-1/C-218', 45, 1, 'C-218', 'An Act to amend the Criminal Code (medical "
        "assistance in dying)', NULL, 'At second reading', 'Bob Tory', '2', '[2]', '[]', 2, "
        "'2025-06-20', 'First reading in the House of Commons', '2025-06-20', "
        "'Private Member''s Bill', ?, ?)", (TODAY, TODAY))
    divs = [("commons-45-1-177", "commons", 177, "2026-10-07T15:45:00", C218, "Negatived",
             3, 3, 2, None, "C-218", "[2]", 2, 1),
            ("commons-45-1-178", "commons", 178, "2026-10-08T15:15:00",
             "2nd reading of Bill C-39, An Act respecting certain measures to strengthen the "
             "economy", "Agreed To", 296, 26, 10, None, "C-39", "[]", None, 0),
            ("senate-45-1-555", "senate", 555, "2026-10-08",
             "Some Act - S-99 - Third Reading", "Adopted", 1, 0, None, 1, "S-99", "[8]", 2, 1)]
    for key, ch, num, date, subj, res, y, n, paired, abst, bill, areas, tier, fetched in divs:
        conn.execute("INSERT INTO ca_divisions (division_key, chamber, parliament, session, "
                     "number, date, subject, result, yeas, nays, paired, abstentions, "
                     "bill_number, areas, matched_terms, tier, positions_fetched, first_seen, "
                     "last_seen) VALUES (?,?,45,1,?,?,?,?,?,?,?,?,?,?,'[]',?,?,?,?)",
                     (key, ch, num, date, subj, res, y, n, paired, abst, bill, areas, tier,
                      fetched, TODAY, TODAY))
    votes = [("commons-45-1-177", "1", "Nay", "Liberal"), ("commons-45-1-177", "4", "Nay", "Liberal"),
             ("commons-45-1-177", "5", "Yea", "Liberal"),
             ("commons-45-1-177", "2", "Yea", "Conservative"),
             ("commons-45-1-177", "3", "Yea", "Independent"),
             ("senate-45-1-555", "senator-9", "Yea", "ISG")]
    for key, pid, pos, party in votes:
        conn.execute("INSERT INTO ca_votes (division_key, person_id, position, party) "
                     "VALUES (?,?,?,?)", (key, pid, pos, party))
    conn.commit()
    return conn


STANCE = """divisions:
  - key: commons-45-1-177
    title: "2nd reading of Bill C-218"
    yea: 2
    nay: -2
  - key: senate-45-1-555
    title: "S-99"
    placeable: false
    reason: "evidence only"
"""
WATCH = """bills:
  "45-1/C-218": {title: "An Act to amend the Criminal Code (medical assistance in dying)", areas: [2]}
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = os.path.join(self.dir, "store.db")
        self.conn = make_store(self.db)
        self.cfg = os.path.join(self.dir, "config")
        os.makedirs(self.cfg)
        with open(os.path.join(self.cfg, "ca_stance.yaml"), "w") as fh:
            fh.write(STANCE)
        with open(os.path.join(self.cfg, "watchlist-ca.yaml"), "w") as fh:
            fh.write(WATCH)

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.dir, ignore_errors=True)


class ReaderAdapter(Base):
    def items(self):
        self.conn.row_factory = sqlite3.Row
        return ca.items(self.conn, "2026-09-30", TODAY, ce.watchlist_of(ca.COUNTRY, self.cfg))

    def test_divisions_on_our_ground_with_caucus_at_the_vote(self):
        votes = {it["key"]: it for it in self.items() if it["kind"] == "vote"}
        self.assertEqual(set(votes), {"commons-45-1-177", "senate-45-1-555"})   # 178: not ours
        v = votes["commons-45-1-177"]
        self.assertTrue(v["watched"])
        self.assertEqual(v["group"], "45-1/C-218")
        self.assertIn("Paired: 2 member(s), who place nobody.", v["lines"])
        self.assertTrue(any(ln.startswith("By caucus at the vote") and "Liberal 1-2" in ln
                            for ln in v["lines"]))
        # Eve broke from the Liberal majority; the Independent has no line to break.
        self.assertEqual(v["rebels"], ["Eve Liberal (Liberal)"])
        self.assertEqual(len(v["positions"]), 5)
        self.assertIn("division No. 177", v["takeaway"])
        self.assertEqual(v["url"], "https://www.ourcommons.ca/members/en/votes/45/1/177")
        s = votes["senate-45-1-555"]
        self.assertTrue(s["url"].startswith("https://sencanada.ca/en/in-the-chamber/votes/details/555/"))
        self.assertTrue(s["final"])
        self.assertIn("1 abstaining", s["lines"][0])

    def test_no_em_dash_in_what_the_adapter_writes(self):
        for it in self.items():
            for text in [it.get("takeaway") or ""] + list(it["lines"]):
                self.assertNotIn("—", text)

    def test_chamber_store_never_reads_canadas_own_speeches_table(self):
        self.assertEqual(chamber_store.edition_items(self.conn, "ca", "2026-01-01", TODAY, {}), [])
        self.assertEqual(chamber_store.coverage_lines(self.conn, "ca", "2026-01-01", TODAY), [])

    def test_gather_runs_over_the_adapter(self):
        got = ce.gather(self.conn, ca.COUNTRY, "2026-09-30", TODAY, self.cfg)
        self.assertIn("commons-45-1-177", {it["key"] for it in got})

    def test_canada_keeps_its_own_edition_and_send_path(self):
        self.assertNotIn("ca", edition_review.OWN)
        self.assertNotIn("ca", country5ca.SPECS)       # its 5CA is tools/ca_5ca.py's
        self.assertFalse(os.path.exists(os.path.join(ROOT, "tools", "ca_monitor_edition.py")))


class Profiles(Base):
    def test_profiles_from_the_store(self):
        data = mp.build(self.conn, "ca", TODAY, self.cfg)
        m = data["members"]
        self.assertEqual(data["votes"], 2)
        eve = m["5"]
        self.assertEqual(eve.votes[0]["position"], "Yea")
        self.assertEqual(eve.votes[0]["party"], "Liberal")
        self.assertEqual(eve.votes[0]["basis"], mp.AT_VOTE)
        self.assertEqual(m["senator-9"].chamber, "Senate")
        self.assertEqual(m["senator-9"].votes[0]["party"], "ISG")
        self.assertEqual([a["key"] for a in m["2"].authored], ["45-1/C-218"])
        out = os.path.join(self.dir, "profiles")
        written, _ = mp.write(data, out)
        self.assertEqual(written, 6)
        with open(os.path.join(out, "ca", "index.md"), encoding="utf-8") as fh:
            self.assertIn("Doe, Jane", fh.read())


class VotePages(Base):
    def test_readings_only_when_confirmed_and_canadian_words(self):
        data = cv.build(self.conn, "ca", TODAY, self.cfg)
        self.assertEqual(data["labels"], ["Yea", "Nay"])
        by = {d["k"]: d for d in data["divisions"]}
        r = by["commons-45-1-177"]["reading"]
        self.assertEqual((r["state"], r["yea"], r["nay"]), ("confirmed", 2, -2))
        self.assertIsNone(r["on"])                       # the file signs in batches
        self.assertEqual(by["senate-45-1-555"]["reading"], {"state": cv.EVIDENCE_ONLY})
        self.assertEqual((by["commons-45-1-177"]["y"], by["commons-45-1-177"]["n"]), (3, 3))
        self.assertEqual(by["senate-45-1-555"]["ab"], 1)
        self.assertEqual(by["commons-45-1-177"]["c"], "House of Commons")
        self.assertEqual(len(by["commons-45-1-177"]["rb"]), 1)
        page = cv.render_page(data)
        self.assertIn("Canada: votes on our ground", page)

    def test_a_draft_reading_carries_no_direction(self):
        with open(os.path.join(self.cfg, "ca_stance.yaml"), "w") as fh:
            fh.write(STANCE.replace("    yea: 2\n", "    draft: true\n    yea: 2\n"))
        data = cv.build(self.conn, "ca", TODAY, self.cfg)
        r = {d["k"]: d for d in data["divisions"]}["commons-45-1-177"]["reading"]
        self.assertEqual(r, {"state": cv.AWAITING})

    def test_timeline_of_a_watched_bill(self):
        tl = cv.timelines(self.conn, "ca", TODAY, self.cfg)
        self.assertEqual([b["key"] for b in tl], ["45-1/C-218"])
        kinds = [e[1] for e in tl[0]["events"]]
        self.assertEqual(kinds, ["introduced", "stage", "vote"])
        self.assertIn("Yea 3, Nay 3", tl[0]["events"][-1][2])

    def test_every_other_country_reads_as_before(self):
        self.assertIsNone(cv.own_readings("pl"))
        self.assertIn("ca", cv.COUNTRIES)
        self.assertIn("ca", cv.BILLS)


class WeekAhead(unittest.TestCase):
    def test_house_committee_notices(self):
        pts = ca_agenda.parse_house_meetings(fixture("house-meetings-2026-10-16.html.gz"), TODAY)
        self.assertEqual(len(pts), 24)                    # the stale April notice left out
        fina = next(p for p in pts if "(FINA)" in p["body"])
        self.assertEqual((fina["date"], fina["time"], fina["refs"]), ("2026-10-19", "11:00",
                                                                     ["45-1/C-31"]))
        self.assertEqual(fina["kind"], "committee")
        secu = next(p for p in pts if "(SECU)" in p["body"])
        self.assertEqual(secu["status"], "In camera")
        self.assertTrue(all(p["url"].startswith("https://www.") for p in pts))

    def test_projected_order_of_business_english_half_only(self):
        date, sitting, pts = ca_agenda.parse_projected(fixture("projected-business-150.html.gz"))
        self.assertEqual((date, sitting), ("2026-10-19", "150"))
        titles = [p["title"] for p in pts]
        self.assertEqual(len(pts), 5)
        self.assertIn("C-40, Strengthening Canada's Defence Sector Act: Second reading (first "
                      "time debated)", titles)
        self.assertFalse(any("lecture" in t for t in titles))
        s217 = next(p for p in pts if p["refs"] == ["45-1/S-217"])
        self.assertTrue(s217["detail"].startswith("Private Members' Business"))
        self.assertEqual(s217["time"], "11:00")

    def test_sitting_calendar(self):
        days = ca_agenda.parse_calendar(fixture("sitting-calendar.html.gz"))
        self.assertIn("2026-10-19", days)
        self.assertNotIn("2026-10-14", days)               # the constituency week

    def test_senate_committee_schedule(self):
        pts = ca_agenda.parse_senate_meetings(fixture("senate-meetings-upcoming.html.gz"), TODAY)
        self.assertEqual(len(pts), 25)                     # the joint BILI meeting left out
        ridr = next(p for p in pts if p["item_id"] == "sen-mtg-706232")
        self.assertEqual(ridr["refs"], ["45-1/C-234"])
        self.assertEqual((ridr["time"], ridr["status"]), ("16:00", "Partly in camera"))
        self.assertIn("Clause-by-clause consideration", ridr["detail"])
        self.assertFalse(any("Joint" in p["body"] for p in pts))

    def test_senate_order_paper_bill_items(self):
        url, session, issue, date = ca_agenda.latest_order_paper(fixture("senate-op-index.html.gz"))
        self.assertEqual((session, issue, date), ("45-1", 93, "2026-10-20"))
        pts = ca_agenda.parse_order_paper(fixture("senate-order-paper-093.html.gz"), date,
                                          session, url, issue)
        self.assertEqual(len(pts), 39)
        s231 = next(p for p in pts if p["refs"] == ["45-1/S-231"])
        self.assertIn("medical assistance in dying", s231["title"])
        self.assertEqual(s231["detail"], "Other Business; Senate Public Bills – Second Reading")
        self.assertIn("may be called", s231["status"])

    def test_collect_and_the_editions_countdown(self):
        d = tempfile.mkdtemp()
        try:
            conn = db.init_db(db.connect(os.path.join(d, "s.db")))
            routes = {"Committees/en/Meetings": fixture("house-meetings-2026-10-16.html.gz"),
                      "projected-business": fixture("projected-business-150.html.gz"),
                      "sitting-calendar": fixture("sitting-calendar.html.gz"),
                      "GetTablePartialView": fixture("senate-meetings-upcoming.html.gz"),
                      "orderpaper/093op": fixture("senate-order-paper-093.html.gz"),
                      "order-papers-notice-papers": fixture("senate-op-index.html.gz")}

            class Client:
                def get_text(self, url, feed, slug, **kw):
                    return next(v for k, v in routes.items() if k in url)
            n, ours, gaps = agenda.collect(conn, "ca", Client(), TODAY, log=lambda *a: None)
            self.assertEqual((n, gaps), (93, 0))
            self.assertGreaterEqual(ours, 2)               # S-231 and S-240 are watched
            run = agenda.latest_run(conn, "ca")
            self.assertEqual(run[4], "2026-10-19")         # next sitting, from the calendar
            mon = _load_tool("ca_monitor")
            lines, note = mon.week_ahead_section(conn, TODAY, mon.area_names())
            text = "\n".join(lines)
            self.assertIn("## This week · Mon 12 to Sun 18 October", text)
            self.assertIn("## Further afield · Mon 19 October to 13 December", text)
            self.assertIn("| Tue 20 Oct | SENATE |", text)
            self.assertIn("watched: S-231", text)
            self.assertNotIn("—", text)
            self.assertIn("next sitting 19 October 2026", note)
            conn.close()
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_no_agenda_no_section(self):
        d = tempfile.mkdtemp()
        try:
            conn = db.init_db(db.connect(os.path.join(d, "s.db")))
            mon = _load_tool("ca_monitor")
            self.assertEqual(mon.week_ahead_section(conn, TODAY, {}), ([], None))
            conn.close()
        finally:
            shutil.rmtree(d, ignore_errors=True)


def vote_xml(number, subject, date, bill):
    return ("<Vote><ParliamentNumber>45</ParliamentNumber><SessionNumber>1</SessionNumber>"
            "<DecisionEventDateTime>{2}</DecisionEventDateTime>"
            "<DecisionDivisionNumber>{0}</DecisionDivisionNumber>"
            "<DecisionDivisionSubject>{1}</DecisionDivisionSubject>"
            "<DecisionResultName>Negatived</DecisionResultName>"
            "<DecisionDivisionNumberOfYeas>2</DecisionDivisionNumberOfYeas>"
            "<DecisionDivisionNumberOfNays>1</DecisionDivisionNumberOfNays>"
            "<DecisionDivisionNumberOfPaired>0</DecisionDivisionNumberOfPaired>"
            "<BillNumberCode>{3}</BillNumberCode></Vote>").format(number, subject, date, bill)


def participant(pid, first, last, party, yea):
    return ("<VoteParticipant><PersonId>{0}</PersonId><PersonOfficialFirstName>{1}"
            "</PersonOfficialFirstName><PersonOfficialLastName>{2}</PersonOfficialLastName>"
            "<CaucusShortName>{3}</CaucusShortName><VoteValueName>{4}</VoteValueName>"
            "<IsVoteYea>{5}</IsVoteYea><IsVoteNay>{6}</IsVoteNay><IsVotePaired>false"
            "</IsVotePaired></VoteParticipant>").format(
                pid, first, last, party, "Yea" if yea else "Nay",
                "true" if yea else "false", "false" if yea else "true")


class VoteBriefs(Base):
    def test_canada_is_briefed_after_its_weekly_and_held_for_positions(self):
        self.assertIn("ca", cvb.EDITIONS)
        self.assertIn("ca", cvb.POSITIONS_LATER)
        out, ledger = os.path.join(self.dir, "briefs"), os.path.join(self.dir, "ledger")
        cvb.save(dict(cvb.load("ca", ledger), seeded="test"), TODAY, ledger)
        self.conn.row_factory = sqlite3.Row
        n = cvb.run(self.conn, ["ca"], "2026-09-30", TODAY, out_dir=out, dm=False,
                    directory=ledger, log=lambda *a: None)
        self.assertEqual(n, 1)          # the tier-2 Senate vote is not briefed; C-218 is watched
        brief = open(os.path.join(out, sorted(os.listdir(out))[0]), encoding="utf-8").read()
        self.assertIn("Canada vote brief", brief)
        self.assertIn("Broke from their group (1): Eve Liberal (Liberal).", brief)
        self.assertIn("tools/ca_5ca.py", brief)
        self.assertNotIn("docs/5ca-ca-readings.md", brief)

    def test_first_pass_seeds_silently(self):
        ledger = os.path.join(self.dir, "ledger")
        self.conn.row_factory = sqlite3.Row
        n = cvb.run(self.conn, ["ca"], "2026-09-30", TODAY, out_dir=os.path.join(self.dir, "b"),
                    dm=True, directory=ledger, log=lambda *a: None,
                    sender=lambda *a: self.fail("nothing is sent on a first pass"))
        self.assertEqual(n, 0)
        self.assertEqual(len(cvb.load("ca", ledger)["sent"]), 1)

    def test_daily_reader_reads_todays_commons_divisions(self):
        self.assertIn("ca", vs.DAILY)
        listing = "<ArrayOfVote>{0}{1}</ArrayOfVote>".format(
            vote_xml(180, C218.replace("2nd", "3rd"), "2026-10-15T15:30:00", "C-218"),
            vote_xml(170, "Opposition Motion (Diesel prices)", "2026-09-01T15:30:00", ""))
        detail = ("<ArrayOfVoteParticipant>" + participant(1, "Ann", "Liberal", "Liberal", False)
                  + participant(2, "Bob", "Tory", "Conservative", True)
                  + participant(6, "Fay", "Liberal", "Liberal", True) + "</ArrayOfVoteParticipant>")
        asked = []

        class Client:
            def get_text(self, url, feed, slug, **kw):
                asked.append(url)
                return detail if url.endswith("/45/1/180/xml") else listing
        conn = db.init_db(db.connect(os.path.join(self.dir, "scratch.db")))
        self.assertEqual(vs.CA.collect(conn, Client(), "2026-10-13", TODAY, log=lambda *a: None), 1)
        conn.row_factory = sqlite3.Row
        want = {it["key"] for it, _r in cvb.candidates(conn, "ca", "2026-10-13", TODAY)
                if cvb.awaiting_positions(it)}
        self.assertEqual(want, {"commons-45-1-180"})       # watched C-218, no positions yet
        conn.row_factory = None
        self.assertEqual(vs.CA.positions(conn, Client(), TODAY, log=lambda *a: None, keys=want), 1)
        conn.row_factory = sqlite3.Row
        (it, why), = cvb.candidates(conn, "ca", "2026-10-13", TODAY)
        self.assertEqual(why, "watched")
        self.assertEqual(len(it["positions"]), 3)
        self.assertEqual(len(asked), 2)                    # the list and one division
        conn.close()


class Wiring(unittest.TestCase):
    def read(self, *parts):
        with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
            return fh.read()

    def test_the_weekly_runs_each_framework_before_the_edition(self):
        job = self.read("jobs", "ca-weekly.sh")
        edition = job.index("python3 tools/ca_monitor.py")
        for step in ("python3 tools/country_agenda.py ca", "python3 tools/member_profiles.py ca",
                     "python3 tools/country_vote_briefs.py --country ca --send"):
            self.assertLess(job.index("python3 tools/ca_rollcalls.py"), job.index(step), step)
            self.assertLess(job.index(step), edition, step)
        self.assertIn("# mini_run: commit editions profiles", job)
        self.assertIn("git add data/ editions/ profiles/", self.read(".github", "workflows",
                                                                   "ca-weekly.yml"))
        self.assertIn("ca", _load_tool("country_agenda").COUNTRIES)


if __name__ == "__main__":
    unittest.main()
