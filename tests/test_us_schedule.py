"""The US week ahead (tools/us_schedule.py) and its edition section.

Real files only (tests/fixtures/us_schedule): the House floor list and
committee pages of the week of 14 September 2026, the last week the House sat
before the midterm recess; the Senate's hearings.xml and floor schedule of
that morning as the Internet Archive saved them; and the recess answers of
9 October 2026 (the House's "No meetings found." day, senate.gov's
"No committee hearings scheduled" and its pro forma sitting). No network.
"""

import datetime
import gzip
import importlib.util
import json
import os
import sqlite3
import sys
import unittest
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "us_schedule")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


uss = _load("us_schedule")
usm = _load("us_monitor")


def fixture(name):
    path = os.path.join(FIX, name)
    opener = gzip.open if name.endswith(".gz") else open
    with opener(path, "rb") as fh:
        return fh.read()


def text(name):
    return fixture(name).decode("utf-8", errors="replace")


class FakeClient:
    """URL -> fixture; anything else answers 404, as docs.house.gov does for
    a week with no list. `refuse` makes a host answer 403."""

    def __init__(self, pages, refuse=()):
        self.pages, self.refuse, self.asked = pages, refuse, []

    def get_bytes(self, url, feed, slug, **_kw):
        self.asked.append(url)
        for host in self.refuse:
            if host in url:
                raise FetchError(url, feed, slug, 1,
                                 urllib.error.HTTPError(url, 403, "Forbidden", None, None))
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1,
                             urllib.error.HTTPError(url, 404, "Not Found", None, None))
        return fixture(self.pages[url])

    def get_text(self, url, feed, slug, **kw):
        return self.get_bytes(url, feed, slug, **kw).decode("utf-8", errors="replace")


SEPT_PAGES = {
    uss.HOUSE_FLOOR.format("20260914"): "house_floor_20260914.xml.gz",
    uss.HOUSE_FLOOR_INDEX: "house_floor_index_20261009.html.gz",
    uss.HOUSE_DAY.format("09162026"): "house_cmte_day_09162026.html.gz",
    uss.HOUSE_DAY.format("10142026"): "house_cmte_day_10142026_recess.html.gz",
    uss.HOUSE_EVENT.format("119568"): "house_cmte_event_119568.html.gz",
    uss.HOUSE_EVENT.format("119566"): "house_cmte_event_119566.html.gz",
    uss.HOUSE_EVENT.format("119549"): "house_cmte_event_119549.html.gz",
    uss.HOUSE_EVENT.format("118858"): "house_cmte_event_118858.html.gz",
    uss.HOUSE_EVENT.format("119539"): "house_cmte_event_119539.html.gz",
    uss.SENATE_HEARINGS: "senate_hearings_20260914.xml",
    uss.SENATE_FLOOR: "senate_floor_schedule_20260914.htm",
}


def store():
    conn = db.init_db(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    return conn


def bill(conn, key, title, areas, score=None):
    _c, btype, number = key.split("/")
    conn.execute("INSERT INTO us_bills (bill_key, congress, bill_type, number, title, areas, "
                 "triage_score, latest_action) VALUES (?,?,?,?,?,?,?,?)",
                 (key, 119, btype, int(number), title, json.dumps(areas), score,
                  "Referred to the Committee."))


TAX = filt.load_taxonomy(uss.TAXONOMY)
WL = filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])
QUIET = lambda *_a, **_k: None  # noqa: E731


class BillRefTests(unittest.TestCase):
    def test_every_form_the_sources_print(self):
        cases = {
            "H.R. 309": ["119/hr/309"], "S.790": ["119/s/790"], "S. 283 ": ["119/s/283"],
            "H.J. Res. 210": ["119/hjres/210"], "H. Con. Res. 93": ["119/hconres/93"],
            "H. Res. 1530": ["119/hres/1530"], "S.Res. 12": ["119/sres/12"],
            "Senate amendments to H.R. 5334": ["119/hr/5334"],
            "H.R. 4464, the Preventive Health Savings Act; H.R. 6470, the Increasing":
                ["119/hr/4464", "119/hr/6470"],
        }
        for line, want in cases.items():
            self.assertEqual(uss.bill_refs(line, 119), want, line)

    def test_what_is_not_a_bill(self):
        for line in ("H. Rept. 119-825 - Report from the Committee on Rules",
                     "under 42 U.S.C. 1983", "Twenty-Five Years After 9/11",
                     "Pub. L. 119-21", "items 5 and 6"):
            self.assertEqual(uss.bill_refs(line, 119), [], line)


class WindowTests(unittest.TestCase):
    def test_a_friday_run_covers_the_next_week(self):
        self.assertEqual(uss.window(datetime.date(2026, 10, 9)),
                         (datetime.date(2026, 10, 9), datetime.date(2026, 10, 18)))
        self.assertEqual(usm.ahead_window("2026-10-09"),
                         (datetime.date(2026, 10, 9), datetime.date(2026, 10, 18)))

    def test_a_monday_run_covers_its_own_week(self):
        self.assertEqual(uss.window(datetime.date(2026, 9, 14)),
                         (datetime.date(2026, 9, 14), datetime.date(2026, 9, 20)))


class HouseFloorTests(unittest.TestCase):
    def setUp(self):
        self.week = uss.parse_house_floor(fixture("house_floor_20260914.xml.gz"))

    def test_the_week_and_every_item_keyed_on_its_bill(self):
        self.assertEqual(self.week["week_of"], "2026-09-14")
        self.assertEqual(self.week["congress"], 119)
        self.assertEqual(len(self.week["items"]), 78)
        self.assertEqual([i for i in self.week["items"] if not i["bills"]], [])
        keys = [k for i in self.week["items"] for k in i["bills"]]
        for key in ("119/hr/7834", "119/s/790", "119/hjres/210", "119/hconres/93",
                    "119/hres/1530", "119/hr/5334"):
            self.assertIn(key, keys)

    def test_the_three_categories(self):
        cats = {i["category"] for i in self.week["items"]}
        self.assertEqual(cats, {"suspension", "rule", "may be considered"})
        first = self.week["items"][0]
        self.assertEqual((first["legis_num"], first["category"]), ("S. 283", "suspension"))
        self.assertTrue(first["doc_url"].endswith("S283_SUS_xml.pdf"))

    def test_no_url_keeps_a_space(self):
        for i in self.week["items"]:
            self.assertNotIn(" ", i["doc_url"] or "")

    def test_the_latest_week_posted(self):
        self.assertEqual(uss.latest_floor_week(text("house_floor_index_20261009.html.gz")),
                         "2026-09-14")

    def test_anything_else_is_none(self):
        self.assertIsNone(uss.parse_house_floor(b"<html>not found</html>"))
        self.assertIsNone(uss.parse_house_floor(fixture("senate_hearings_20260914.xml")))


class HouseCommitteeTests(unittest.TestCase):
    def test_a_sitting_day(self):
        rows = uss.parse_house_day(text("house_cmte_day_09162026.html.gz"))
        self.assertEqual(len(rows), 17)
        self.assertEqual(rows[0], {"event_id": "119566", "committee": "Committee on the Budget",
                                   "title": "H.R. 4464, the Preventive Health Savings Act; "
                                            "H.R. 6470, the Increasing Baseline Updates Act",
                                   "time": "09:30", "location": "210 CHOB"})

    def test_a_recess_day_is_empty_and_a_strange_page_is_none(self):
        self.assertEqual(uss.parse_house_day(text("house_cmte_day_10142026_recess.html.gz")), [])
        self.assertIsNone(uss.parse_house_day("<html><body>Service unavailable</body></html>"))

    def test_each_bill_keeps_its_own_line(self):
        ev = uss.parse_house_event(text("house_cmte_event_119568.html.gz"), 119)
        self.assertTrue(ev["lines"]["119/hr/10329"].startswith(
            "H.R. 10329 \u2013 Combating Foreign Threats to Main Street Act"))
        senate = uss.parse_senate_hearings(fixture("senate_hearings_20260914.xml"), 119)
        epw = [m for m in senate if m["identifier"] == "338754"][0]
        self.assertTrue(epw["lines"]["119/s/5045"].startswith("A bill to amend the Clean Air Act"))

    def test_a_markup_names_its_bills_from_the_legislation_list(self):
        ev = uss.parse_house_event(text("house_cmte_event_119568.html.gz"), 119)
        self.assertEqual((ev["kind"], ev["date"], ev["status"]), ("markup", "2026-09-16", "scheduled"))
        self.assertEqual(ev["committee"], "Committee on Small Business")
        self.assertEqual(len(ev["bills"]), 10)
        # The meeting XML prints this one as a bare "10355"; the page does not.
        self.assertIn("119/hr/10355", ev["bills"])

    def test_bills_in_the_title(self):
        ev = uss.parse_house_event(text("house_cmte_event_119566.html.gz"), 119)
        self.assertEqual(ev["kind"], "markup")
        self.assertEqual(ev["bills"][:2], ["119/hr/4464", "119/hr/6470"])

    def test_a_rescheduled_legislative_hearing(self):
        ev = uss.parse_house_event(text("house_cmte_event_119549.html.gz"), 119)
        self.assertEqual((ev["kind"], ev["status"], ev["date"]),
                         ("hearing", "rescheduled", "2026-09-15"))
        self.assertEqual(len(ev["bills"]), 16)

    def test_a_rules_meeting_and_a_field_hearing(self):
        rules = uss.parse_house_event(text("house_cmte_event_118858.html.gz"), 119)
        self.assertEqual(rules["kind"], "meeting")
        self.assertIn("119/hjres/210", rules["bills"])
        field = uss.parse_house_event(text("house_cmte_event_119539.html.gz"), 119)
        self.assertEqual((field["kind"], field["date"], field["bills"]),
                         ("hearing", "2026-09-14", []))
        self.assertEqual(field["title"], "Examining Healthcare Markets: Fraud and Competition")


class SenateTests(unittest.TestCase):
    def test_the_hearings_file(self):
        meetings = uss.parse_senate_hearings(fixture("senate_hearings_20260914.xml"), 119)
        self.assertEqual(len(meetings), 17)           # the placeholder is not a meeting
        epw = [m for m in meetings if m["committee"] == "Environment and Public Works"][0]
        self.assertEqual((epw["date"], epw["time"], epw["kind"]), ("2026-09-16", "09:30", "markup"))
        self.assertEqual(epw["bills"], ["119/s/3135", "119/s/5045", "119/s/5249"])
        commerce = [m for m in meetings if m["identifier"] == "338749"][0]
        self.assertIn("119/hr/7022", commerce["bills"])

    def test_a_nomination_is_not_a_bill(self):
        meetings = uss.parse_senate_hearings(fixture("senate_hearings_20260914.xml"), 119)
        help_ = [m for m in meetings if m["committee"].startswith("Health, Education")][0]
        self.assertEqual(help_["bills"], [])

    def test_the_recess_file_is_empty(self):
        self.assertEqual(uss.parse_senate_hearings(fixture("senate_hearings_20261008_recess.xml"), 119), [])

    def test_the_next_sitting(self):
        self.assertEqual(uss.parse_senate_floor(text("senate_floor_schedule_20260914.htm"), 119),
                         {"date": "2026-09-14", "note": "Convene at 3:00 p.m.", "bills": []})
        recess = uss.parse_senate_floor(text("senate_floor_schedule_20261009_recess.htm"), 119)
        self.assertEqual(recess["date"], "2026-10-09")
        self.assertIn("pro forma", recess["note"])


class PullTests(unittest.TestCase):
    def sept(self, refuse=()):
        conn = store()
        bill(conn, "119/hr/7834", "Safe Cloud Storage Act", [6, 7], score=2)
        bill(conn, "119/s/5354", "A bill to reauthorize native housing", [5])
        client = FakeClient(SEPT_PAGES, refuse=refuse)
        today = "2026-09-11"
        uss.pull_house_floor(conn, client, ["2026-09-07", "2026-09-14"], today, TAX, WL, log=QUIET)
        uss.pull_house_committees(conn, client, [datetime.date(2026, 9, 16)], today, TAX, WL,
                                  log=QUIET)
        uss.pull_senate(conn, client, datetime.date(2026, 9, 11), datetime.date(2026, 9, 20),
                        today, TAX, WL, log=QUIET)
        return conn, client

    def test_floor_rows_are_keyed_on_the_bill_and_join_us_bills(self):
        conn, _c = self.sept()
        row = conn.execute("SELECT s.*, b.areas FROM us_schedule s JOIN us_bills b "
                           "USING (bill_key) WHERE s.sched_key=?",
                           ("house-floor-2026-09-14/119/hr/7834",)).fetchone()
        self.assertEqual((row["kind"], row["week_of"], row["category"], row["status"]),
                         ("floor", "2026-09-14", "suspension", "listed"))
        self.assertEqual(json.loads(row["areas"]), [6, 7])
        weeks = {(r["week_of"], r["status"], r["items"]) for r in conn.execute(
            "SELECT * FROM us_schedule_weeks WHERE chamber='house' AND source='floor'")}
        self.assertEqual(weeks, {("2026-09-07", "none", 0), ("2026-09-14", "listed", 78)})

    def test_committee_meetings_and_their_bills(self):
        conn, _c = self.sept()
        n = conn.execute("SELECT COUNT(*) FROM us_meetings WHERE chamber='house'").fetchone()[0]
        self.assertEqual(n, 17)
        # Twelve of the day's pages are not fixtures: each is a gap, and the
        # meeting is still stored from the day's own line.
        gaps = conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='us-schedule' AND "
                            "detail LIKE 'house meeting%'").fetchone()[0]
        self.assertEqual(gaps, 15)
        row = conn.execute("SELECT * FROM us_schedule WHERE sched_key=?",
                           ("house-cmte-119568/119/hr/10355",)).fetchone()
        self.assertEqual((row["kind"], row["date"], row["week_of"], row["meeting_key"]),
                         ("markup", "2026-09-16", "2026-09-14", "house-119568"))

    def test_senate_meetings_and_the_next_sitting(self):
        conn, _c = self.sept()
        n = conn.execute("SELECT COUNT(*) FROM us_meetings WHERE chamber='senate'").fetchone()[0]
        self.assertEqual(n, 17)
        self.assertIsNotNone(conn.execute(
            "SELECT 1 FROM us_schedule WHERE sched_key='senate-cmte-338754/119/s/5045'").fetchone())
        note = conn.execute("SELECT note FROM us_schedule_weeks WHERE chamber='senate' AND "
                            "source='floor'").fetchone()[0]
        self.assertEqual(note, "2026-09-14: Convene at 3:00 p.m.")

    def test_a_refused_senate_is_one_gap_and_never_overwrites_a_read(self):
        conn, client = self.sept()
        uss.pull_senate(conn, FakeClient(SEPT_PAGES, refuse=("senate.gov",)),
                        datetime.date(2026, 9, 11), datetime.date(2026, 9, 20), "2026-09-12",
                        TAX, WL, log=QUIET)
        rows = {(r["source"], r["week_of"]): r["status"] for r in conn.execute(
            "SELECT * FROM us_schedule_weeks WHERE chamber='senate'")}
        self.assertEqual(rows[("committees", "2026-09-14")], "listed")
        self.assertEqual(rows[("committees", "2026-09-07")], "none")
        self.assertEqual(rows[("floor", "2026-09-14")], "listed")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='us-schedule' AND "
                                      "detail LIKE 'senate schedule%'").fetchone()[0], 1)

    def test_a_recess_week_reads_the_last_list_and_says_none(self):
        conn = store()
        client = FakeClient(SEPT_PAGES)
        t = uss.pull_house_floor(conn, client, ["2026-10-05", "2026-10-12"], "2026-10-09",
                                 TAX, WL, log=QUIET)
        self.assertEqual(t.latest, "2026-09-14")
        self.assertEqual(t.gaps, 0)
        statuses = dict(conn.execute("SELECT week_of, status FROM us_schedule_weeks").fetchall())
        self.assertEqual(statuses, {"2026-10-05": "none", "2026-10-12": "none",
                                    "2026-09-14": "listed"})
        days = uss.seed_days(conn, t.latest)
        self.assertEqual(days[0], datetime.date(2026, 9, 14))
        self.assertEqual(len(days), 5)
        t2 = uss.pull_house_committees(conn, client, [datetime.date(2026, 10, 14)], "2026-10-09",
                                       TAX, WL, log=QUIET)
        self.assertEqual((t2.meetings, t2.gaps), (0, 0))

    def test_the_seed_is_once(self):
        conn = store()
        conn.execute("INSERT INTO us_meetings (meeting_key, chamber) VALUES ('house-1', 'house')")
        self.assertEqual(uss.seed_days(conn, "2026-09-14"), [])

    def test_the_heartbeat(self):
        conn = store()
        uss.stamp_heartbeat(conn, "2026-10-09")
        self.assertEqual(conn.execute("SELECT last_run FROM source_runs WHERE source=?",
                                      (uss.HEARTBEAT,)).fetchone()[0], "2026-10-09")


class EditionTests(unittest.TestCase):
    def sitting(self):
        conn, _c = PullTests().sept()
        return conn

    def test_a_sitting_week(self):
        conn = self.sitting()
        out = "\n".join(usm.render_coming_up(conn, "2026-09-11", usm.area_names()))
        self.assertIn("## Coming up: 11 September to 20 September", out)
        self.assertIn("[H.R. 7834](https://www.congress.gov/bill/119th-congress/house-bill/7834)", out)
        self.assertIn("week of 14 September, under suspension of the rules", out)
        self.assertIn("(matched on the bill)", out)
        self.assertIn("**[2]**", out)
        # The Senate's Indian Affairs hearing names S. 5354, on our ground here.
        self.assertIn("**Wednesday 16 September 14:30**, Senate Indian Affairs, hearing", out)
        self.assertIn("[S. 5354]", out)
        # Only the bill whose OWN line matched ("jawboning"), not its nine
        # neighbours on the same Commerce agenda.
        self.assertIn("[S. 4749]", out)
        self.assertNotIn("[S. 2586]", out)
        self.assertIn("Next sitting, Monday 14 September: Convene at 3:00 p.m.", out)
        self.assertNotIn("—", out)

    def test_the_recess(self):
        conn = store()
        client = FakeClient(SEPT_PAGES, refuse=("senate.gov",))
        uss.pull_house_floor(conn, client, ["2026-10-05", "2026-10-12"], "2026-10-09", TAX, WL,
                             log=QUIET)
        uss.pull_house_committees(conn, client, [datetime.date(2026, 10, 14)], "2026-10-09",
                                  TAX, WL, log=QUIET)
        uss.pull_senate(conn, client, datetime.date(2026, 10, 9), datetime.date(2026, 10, 18),
                        "2026-10-09", TAX, WL, log=QUIET)
        out = "\n".join(usm.render_coming_up(conn, "2026-10-09", usm.area_names()))
        self.assertIn("The House is out: no floor list is posted for the week of 12 October. "
                      "Its last list, for the week of 14 September, held 78 item(s)", out)
        self.assertIn("House: no meeting posted for these days. Senate: not read.", out)
        self.assertIn("senate.gov refused the machine that ran it", out)
        dm = usm.coming_up_dm(conn, "2026-10-09")
        self.assertEqual(dm, "*Coming up:* House out (no floor list for the week of 12 October); "
                             "0 committee meeting(s) on our ground; Senate schedule not read.")

    def test_a_store_never_collected(self):
        conn = store()
        out = "\n".join(usm.render_coming_up(conn, "2026-10-09", {}))
        self.assertIn("The week ahead was not collected", out)
        self.assertIsNone(usm.coming_up_dm(conn, "2026-10-09"))

    def test_the_whole_edition_renders_with_it(self):
        conn = self.sitting()
        out = usm.render_edition(conn, "2026-09-11")
        self.assertIn("## Coming up", out)
        self.assertLess(out.index("## Coming up"), out.index("## Recorded votes"))


if __name__ == "__main__":
    unittest.main()
