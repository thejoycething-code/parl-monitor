"""Australia's states and territories (tools/au_states.py, src/au_states_store.py,
src/au_states_edition.py and its place in tools/au_monitor.py). No network:
trimmed real replies under tests/fixtures/au_states/ as served on 13 October
2026 (the NSW Hansard API's year list, one Legislative Council contents
document and one fragment; the Victorian register's search answer; the
Queensland register's bills and Acts; South Australia's sessions, bills and
members; the Western Australian and Tasmanian Acts feeds; Tasmania's bill
list; the ACT's What's new; the Northern Territory's bills by session), the
repo's own English taxonomy, an in-memory store.

The ACT fixture's Act row and bills table are CONSTRUCTED in the shape of
the real Notifications table (the probed week listed neither); the fixture
says so in a comment."""
import io
import json
import os
import sqlite3
import sys
import unittest
import urllib.error
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import au_states as S  # noqa: E402
from src import au_states_edition as E, au_states_store as aus, db, drain  # noqa: E402
from src.http import FetchError  # noqa: E402
from tests.robots_fakes import guarded  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "au_states")
TODAY = "2026-10-13"
WATCH = os.path.join(ROOT, "config", "watchlist-au-states.yaml")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


TOC_ID = "HANSARD-1820781676-105230"
FRAGMENT_ID = "HANSARD-1820781676-105298"


def replies():
    """URL -> body, for every source as served on 13 October 2026."""
    qld_b = S.qld_url('Repealed=N AND PrintType=("bill.first" OR "bill.firstnongovintro") AND '
                      'ParliamentNo=58 AND Year=2026?')
    qld_a = S.qld_url("Repealed=N AND PrintType=act.new AND Year=2026?")
    empty_qld = json.dumps({"data": [], "totalCount": {"__type__": "Integer", "__value__": 0}})
    return {
        S.NSW_YEAR.format(year=2026): fixture("nsw_year_2026.json"),
        S.NSW_YEAR.format(year=2025): "[]",
        S.NSW_TOC.format(id=TOC_ID): fixture("nsw_toc_lc_2026-09-16.xml"),
        # The Assembly's day, trimmed to its header: nothing on our ground.
        S.NSW_TOC.format(id="HANSARD-1323879322-168542"): (
            '<hansard.toc><hansard.header><date>2026-09-16T00:00:00+10:00</date>'
            '<chamber>Legislative Assembly</chamber></hansard.header></hansard.toc>'),
        S.NSW_FRAGMENT.format(id=FRAGMENT_ID): fixture("nsw_fragment_105298.xml"),
        S.VIC_SEARCH: fixture("vic_bills.json"),
        qld_b: fixture("qld_bills.json"),
        qld_a: fixture("qld_acts.json"),
        S.qld_url('Repealed=N AND PrintType=("bill.first" OR "bill.firstnongovintro") AND '
                  'ParliamentNo=58 AND Year=2025?'): empty_qld,
        S.qld_url("Repealed=N AND PrintType=act.new AND Year=2025?"): empty_qld,
        S.SA_API + "GetSessions": fixture("sa_sessions.json"),
        S.SA_API + "Search/?resultsPerPage=4000&parliamentSession=56th%2F1st": fixture("sa_search.json"),
        S.SA_API + "GetMembersforSession?sessionId=182": fixture("sa_members.json"),
        S.WA_ASPASSED: fixture("wa_aspassed.atom"),
        S.TAS_BILLS.format(year=2026): fixture("tas_bills_2026.html"),
        S.TAS_BILLS.format(year=2025): "<html></html>",
        S.TAS_ACTS: fixture("tas_acts.atom"),
        S.ACT_WHATSNEW: fixture("act_whatsnew.html"),
        S.NT_SESSIONS: fixture("nt_by_session.html"),
    }


class FakeClient:
    """Serves replies(); a body that is an Exception is raised. Records every
    URL asked for."""

    def __init__(self, overrides=None):
        self.bodies = replies()
        self.bodies.update(overrides or {})
        self.asked = []

    def _get(self, url, feed, slug):
        self.asked.append(url)
        if url not in self.bodies:
            raise AssertionError("unexpected URL " + url)
        body = self.bodies[url]
        if isinstance(body, Exception):
            raise body
        return body

    def get_text(self, url, feed, slug, *a, **kw):
        return self._get(url, feed, slug)

    def get_bytes(self, url, feed, slug, *a, **kw):
        return self._get(url, feed, slug).encode("utf-8")

    def get_json(self, url, feed, slug, *a, **kw):
        return json.loads(self._get(url, feed, slug))

    def post_json(self, url, body, feed, slug, *a, **kw):
        assert isinstance(body, str) and '"field_bill_parliament_current"' in body
        return json.loads(self._get(url, feed, slug))


def refused(url):
    return FetchError(url, S.FEED, "x", 1, urllib.error.HTTPError(url, 503, "Unavailable", {}, None))


def store():
    conn = db.init_db(db.connect(":memory:"))
    conn.row_factory = None
    return conn


def run(conn, client=None, robots=None, sources=S.SOURCE_ORDER, today=TODAY):
    inner = client or FakeClient()
    g, _serving = guarded(inner, robots or {}, S.FEED)
    with redirect_stdout(io.StringIO()):
        gaps = S.run(conn, g, today, S.load_taxonomy(), drain.Budget(600), list(sources))
    return gaps, inner


class ParserTests(unittest.TestCase):
    def test_nsw_year_lists_each_houses_contents(self):
        days = S.parse_nsw_year(json.loads(fixture("nsw_year_2026.json")))
        self.assertEqual([(d[0], d[1], d[2]) for d in days], [
            ("2026-09-16", "Legislative Assembly", "HANSARD-1323879322-168542"),
            ("2026-09-16", "Legislative Council", TOC_ID)])
        self.assertEqual(days[1][4], 1)   # uncorrected draft

    def test_nsw_contents_give_bills_stages_divisions_and_speakers(self):
        toc = S.parse_nsw_toc(fixture("nsw_toc_lc_2026-09-16.xml"))
        self.assertEqual((toc["date"], toc["chamber"]), ("2026-09-16", "Legislative Council"))
        bills = [t["bills"] for t in toc["topics"]]
        self.assertIn([("18794", "Abortion Law Reform Amendment (Sex Selection Prohibition) Bill 2025")],
                      bills)
        topic = next(t for t in toc["topics"] if t["uid"] == FRAGMENT_ID)
        self.assertEqual(topic["stages"], ["Second Reading Debate"])
        d = topic["divisions"][0]
        self.assertEqual((d["ayes"], d["noes"], d["pairs"]), (16, 21, 0))
        self.assertEqual(sum(v == "aye" for _m, v in d["votes"]), 16)
        self.assertEqual(sum(v == "no" for _m, v in d["votes"]), 21)
        self.assertTrue(toc["talkers"])
        self.assertTrue(all(name for name, _e in toc["talkers"].values()))

    def test_nsw_fragment_gives_the_question_and_the_result(self):
        self.assertEqual(S.parse_nsw_fragment(fixture("nsw_fragment_105298.xml")),
                         [("The question is that this bill be now read a second time.",
                           "Motion negatived.")])

    def test_a_question_runs_past_honorifics(self):
        text = ("The question is that the amendment of the Hon. Rod Roberts be agreed to. "
                "The Council divided. Ayes 3 Noes 4 Amendment negatived.")
        self.assertEqual(S.parse_nsw_fragment(text), [
            ("The question is that the amendment of the Hon. Rod Roberts be agreed to.",
             "Amendment negatived.")])

    def test_victoria_maps_the_registers_stage(self):
        bills = {b["ext_id"]: b for b in S.parse_vic(json.loads(fixture("vic_bills.json")))}
        self.assertEqual(bills["22549"]["status"], "assented")
        self.assertEqual(bills["22301"]["status"], "before")
        self.assertEqual(bills["22301"]["stage"], "Council - second reading")
        self.assertEqual(bills["22702"]["status"], "defeated")
        self.assertTrue(bills["22549"]["url"].startswith("https://www.legislation.vic.gov.au/bills/"))
        self.assertNotIn("site-6", bills["22549"]["url"])
        self.assertTrue(bills["22713"]["introduced_by"])

    def test_queensland_bills_and_acts(self):
        bills = S.parse_qld(json.loads(fixture("qld_bills.json")))
        acts = S.parse_qld(json.loads(fixture("qld_acts.json")), acts=True)
        self.assertTrue(all(b["stage"] == "introduced" for b in bills))
        self.assertTrue(all(a["url"].endswith(a["ext_id"]) for a in acts))
        self.assertEqual(acts[0]["number"], "No. 4 of 2026")

    def test_a_bill_and_its_act_fold_to_one_name(self):
        self.assertEqual(S.bill_name("Statutory Holidays Amendment Bill 2025"),
                         S.bill_name("Statutory Holidays Amendment Act 2026"))
        self.assertNotEqual(S.bill_name("Liquor Amendment Bill 2026"),
                            S.bill_name("Liquor Amendment (No. 2) Bill 2026") + " x")

    def test_south_australia_session_and_statuses(self):
        self.assertEqual(S.sa_session(json.loads(fixture("sa_sessions.json")))["sessionId"], 182)
        items = {b["ext_id"]: b for b in S.parse_sa(json.loads(fixture("sa_search.json")))}
        self.assertEqual(items["5618"]["status"], "assented")
        self.assertEqual(items["5622"]["status"], "defeated")
        self.assertEqual(items["5622"]["url"], "https://salt.parliament.sa.gov.au/bill/5622")

    def test_acts_feeds(self):
        wa = S.parse_wa(fixture("wa_aspassed.atom"))
        self.assertIn("A147447", [a["ext_id"] for a in wa])
        tas = S.parse_tas_acts(fixture("tas_acts.atom"))
        self.assertEqual(tas[0]["ext_id"], "act-2026-018")
        self.assertEqual(tas[0]["number"], "No. 18 of 2026")

    def test_tasmania_names_its_bills_without_a_stage(self):
        bills = S.parse_tas_bills(fixture("tas_bills_2026.html"), 2026)
        self.assertEqual(len(bills), 21)
        self.assertTrue(all(b["status"] == "unknown" for b in bills))
        self.assertIn("Statutory Holidays Amendment Bill 2026", [b["title"] for b in bills])
        self.assertTrue(all(b["ext_id"].startswith("2026:") for b in bills))

    def test_act_reads_acts_and_bills_but_not_instruments(self):
        acts, bills = S.parse_act(fixture("act_whatsnew.html"))
        self.assertEqual([(a["ext_id"], a["made"]) for a in acts], [("A2026-31", "2026-10-09")])
        self.assertEqual([(b["ext_id"], b["introduced"]) for b in bills], [("db_99001", "2026-10-08")])

    def test_northern_territory_reads_the_current_assembly_only(self):
        bills = {b["title"]: b for b in S.parse_nt(fixture("nt_by_session.html"))}
        self.assertNotIn("An older Assembly Bill 2017", bills)
        vad = bills["Rights of the Terminally Ill Bill 2026"]
        self.assertEqual((vad["status"], vad["introduced"], vad["stage_date"]),
                         ("passed", "2026-07-23", "2026-08-27"))
        self.assertEqual(vad["stage"], "passed (amended)")
        self.assertEqual(bills["Marine Facilities (Access and Pricing) Bill 2026"]["status"], "before")


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        self.gaps, self.client = run(self.conn)

    def q(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def test_every_source_is_read_with_no_gap(self):
        self.assertEqual(self.gaps, 0)
        reads = {r[0]: r[1] for r in self.q("SELECT source, status FROM aus_reads")}
        for src in ("nsw", "vic", "qld-bills", "qld-acts", "sa", "wa-acts", "tas-bills", "tas-acts",
                    "act-acts", "nt"):
            self.assertEqual(reads.get(src), "ok", src)

    def test_titles_are_classified_with_the_english_taxonomy(self):
        areas = {k: json.loads(a) for k, a in self.q("SELECT bill_key, areas FROM aus_bills")}
        self.assertEqual(areas["vic:22549"], [2])        # Voluntary Assisted Dying Amendment Bill 2025
        self.assertEqual(areas["vic:22286"], [1])        # Constitution Amendment (Abortion) Bill 2024
        self.assertEqual(areas["nsw:18794"], [1])
        self.assertEqual(areas["sa:5632"], [1])          # Termination of Pregnancy (Restrictions ...)

    def test_the_watchlist_applies_by_key(self):
        row = self.q("SELECT areas, matched_terms FROM aus_bills WHERE bill_key=?",
                     ("nt:EBD33A287B5F496FBF9D3DE24A9FD373",))[0]
        self.assertEqual(json.loads(row[0]), [2])
        self.assertIn("watch:nt:EBD33A287B5F496FBF9D3DE24A9FD373", json.loads(row[1]))
        act = self.q("SELECT areas FROM aus_acts WHERE act_key='wa:A147447'")[0]
        self.assertEqual(json.loads(act[0]), [5])

    def test_nsw_division_with_votes_question_and_defeat(self):
        d = self.q("SELECT chamber, ayes, noes, question, result, areas, own_areas, bill_keys "
                   "FROM aus_divisions")
        self.assertEqual(len(d), 1)
        chamber, ayes, noes, question, result, areas, own, keys = d[0]
        self.assertEqual((chamber, ayes, noes), ("Legislative Council", 16, 21))
        self.assertEqual(question, "The question is that this bill be now read a second time.")
        self.assertEqual(result, "Motion negatived.")
        self.assertEqual((json.loads(areas), json.loads(own)), ([1], []))
        self.assertEqual(json.loads(keys), ["nsw:18794"])
        self.assertEqual(self.q("SELECT COUNT(*) FROM aus_votes")[0][0], 37)
        bill = self.q("SELECT status, stage, stage_date FROM aus_bills WHERE bill_key='nsw:18794'")[0]
        self.assertEqual(bill, ("defeated", "Second reading negatived", "2026-09-16"))
        named = self.q("SELECT COUNT(*) FROM aus_votes v JOIN aus_members m USING (member_key)")[0][0]
        self.assertGreater(named, 0)

    def test_nsw_stages_are_dated_by_the_sitting(self):
        ev = self.q("SELECT date, chamber, stage, source FROM aus_bill_events WHERE bill_key='nsw:18938'")
        self.assertEqual(ev, [("2026-09-16", "Legislative Council", "First Reading", "hansard")])

    def test_an_act_settles_its_bill(self):
        rows = self.q("SELECT b.status, b.act_key FROM aus_bills b WHERE b.state='qld' "
                      "AND b.act_key IS NOT NULL")
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r[0] == "assented" for r in rows))
        tas = self.q("SELECT status, stage FROM aus_bills WHERE state='tas' AND act_key='tas:act-2026-018'")
        self.assertEqual(tas, [("assented", "Act")])

    def test_first_read_rows_are_seeds_and_a_later_read_adds_and_dates_events(self):
        self.assertEqual(self.q("SELECT COUNT(*) FROM aus_bills WHERE state='vic' AND seed=0")[0][0], 0)
        self.assertEqual(self.q("SELECT COUNT(*) FROM aus_bill_events WHERE bill_key LIKE 'vic:%'")[0][0], 0)
        data = json.loads(fixture("vic_bills.json"))
        for h in data["hits"]["hits"]:
            if h["_source"]["nid"] == [22301]:
                h["_source"]["field_legislation_status"] = ["Passed and Assented to"]
                h["_source"]["changed"] = ["2026-10-20T10:00:00+11:00"]
        run(self.conn, FakeClient({S.VIC_SEARCH: json.dumps(data)}), sources=("vic",),
            today="2026-10-20")
        row = self.q("SELECT status, stage, stage_date FROM aus_bills WHERE bill_key='vic:22301'")[0]
        self.assertEqual(row, ("assented", "Passed and Assented to", "2026-10-20"))
        ev = self.q("SELECT date, stage, source FROM aus_bill_events WHERE bill_key='vic:22301'")
        self.assertEqual(ev, [("2026-10-20", "Passed and Assented to", "list")])

    def test_a_rerun_reads_no_nsw_day_twice(self):
        before = len(self.client.asked)
        _g, client = run(self.conn, sources=("nsw",))
        self.assertNotIn(S.NSW_TOC.format(id=TOC_ID), client.asked)
        self.assertNotIn(S.NSW_FRAGMENT.format(id=FRAGMENT_ID), client.asked)
        self.assertGreater(before, 0)

    def test_reclassify_is_offline_and_stable(self):
        before = self.q("SELECT bill_key, areas FROM aus_bills ORDER BY 1")
        with redirect_stdout(io.StringIO()):
            S.reclassify(self.conn, S.load_taxonomy())
        self.assertEqual(self.q("SELECT bill_key, areas FROM aus_bills ORDER BY 1"), before)
        self.assertEqual(json.loads(self.q("SELECT areas FROM aus_divisions")[0][0]), [1])


class FailureTests(unittest.TestCase):
    def test_a_failed_source_is_a_gap_and_the_rest_still_run(self):
        conn = store()
        gaps, client = run(conn, FakeClient({S.VIC_SEARCH: refused(S.VIC_SEARCH)}))
        self.assertEqual(gaps, 1)
        self.assertTrue(conn.execute("SELECT 1 FROM gaps WHERE feed='au-states' AND detail LIKE "
                                     "'Victoria%'").fetchone())
        self.assertEqual(conn.execute("SELECT status FROM aus_reads WHERE source='vic'").fetchone()[0][:6],
                         "failed")
        self.assertIn(S.NT_SESSIONS, client.asked)

    def test_robots_disallow_is_a_gap_and_nothing_is_fetched(self):
        conn = store()
        gaps, client = run(conn, robots={"legislation.nt.gov.au": "User-agent: *\nDisallow: /\n"},
                           sources=("nt",))
        self.assertEqual(gaps, 1)
        self.assertNotIn(S.NT_SESSIONS, client.asked)
        self.assertTrue(conn.execute("SELECT 1 FROM gaps WHERE detail LIKE '%robots.txt%'").fetchone())

    def test_an_empty_parse_is_a_gap_not_silence(self):
        conn = store()
        gaps, _c = run(conn, FakeClient({S.NT_SESSIONS: "<html>moved</html>"}), sources=("nt",))
        self.assertEqual(gaps, 1)
        self.assertEqual(conn.execute("SELECT status FROM aus_reads WHERE source='nt'").fetchone()[0],
                         "empty")


class EditionTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        run(self.conn)
        from src import intel
        self.names = intel.area_names(S.TAXONOMY)

    def test_the_section_renders_without_em_dashes(self):
        text = "\n".join(E.render(self.conn, "2026-09-20", self.names))
        self.assertIn("## States and territories", text)
        self.assertIn("### Divisions this week (1, New South Wales)", text)
        self.assertIn("**Negatived** 16-21", text)
        self.assertIn("matched on bill only", text)
        self.assertIn("Abortion Law Reform Amendment (Sex Selection Prohibition) Bill 2025", text)
        self.assertIn("### State coverage", text)
        self.assertNotIn("—", text)
        # Migration is never shown.
        self.assertNotIn("Migration", text.split("### State coverage")[0])

    def test_seeds_are_new_only_by_their_own_date(self):
        new = {r["bill_key"] for r in E.new_bills(self.conn, "2026-10-13")}
        self.assertNotIn("vic:22549", new)   # introduced 2025, first listed today as a seed
        self.assertIn("act:db_99001", new)   # presented 8 October 2026
        self.assertNotIn("nsw:18794", new)   # met in the backfill (16 September)

    def test_a_nsw_bill_read_in_its_sitting_week_is_new(self):
        conn = store()
        run(conn, sources=("nsw",), today="2026-09-18")
        new = {r["bill_key"] for r in E.new_bills(conn, "2026-09-18")}
        self.assertIn("nsw:18794", new)      # met in the week it was debated
        row = conn.execute("SELECT introduced, chamber FROM aus_bills WHERE bill_key='nsw:18938'"
                           ).fetchone()
        self.assertEqual(tuple(row), ("2026-09-16", "Legislative Council"))

    def test_before_lists_live_bills_on_our_ground(self):
        keys = [r["bill_key"] for r in E.before(self.conn)]
        self.assertIn("vic:22301", keys)
        self.assertNotIn("nsw:18794", keys)   # defeated
        self.assertNotIn("vic:22549", keys)   # assented

    def test_the_dm_line(self):
        line = E.dm_line(self.conn, "2026-09-20")
        self.assertIn("States and territories", line)
        self.assertIn("1 NSW division(s)", line)

    def test_a_store_that_never_ran_the_layer_says_so(self):
        conn = store()
        self.assertIn("has not run yet", "\n".join(E.render(conn, TODAY, self.names)))
        self.assertIsNone(E.dm_line(conn, TODAY))

    def test_the_australian_edition_carries_the_section(self):
        import au_monitor
        text = au_monitor.render_edition(self.conn, "2026-09-20")
        self.assertIn("## States and territories", text)
        self.assertIn("- **States and territories:**", text)
        self.assertNotIn("and the states and territories.", text)
        self.assertLess(text.index("## States and territories"), text.index("## Coverage"))
        dm = au_monitor.dm_summary(self.conn, "2026-09-20")
        self.assertIn("*States and territories:*", dm)


class WiringTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "jobs", "au-weekly.sh"), encoding="utf-8") as fh:
            self.job = fh.read()

    def test_the_weekly_runs_the_states_after_the_debates_and_before_the_edition(self):
        step = self.job.index("python3 tools/au_states.py --budget-seconds")
        self.assertLess(self.job.index("python3 tools/au_debates.py"), step)
        self.assertLess(step, self.job.index("tools/au_monitor.py --edition --dm"))
        self.assertIn('au_states.py --budget-seconds "$(bash tools/collector_budget.sh 300 "$SECONDS")"',
                      self.job)
        self.assertRegex(self.job, r'au_states\.py --budget-seconds[^\n]*\\\n\s*\|\| echo "  \[gap\]')
        self.assertIn("python3 tools/au_states.py --reclassify", self.job)
        # The federal collector's budget keeps room for the debates and the states.
        self.assertIn('collector_budget.sh 2700 "$SECONDS" 900', self.job)

    def test_the_tables_are_declared(self):
        for t in aus.TABLES:
            self.assertIn(t, db.TABLES)

    def test_every_request_goes_through_the_robots_guard(self):
        with open(os.path.join(ROOT, "tools", "au_states.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("return GuardedClient(client, FEED)", src)
        self.assertIsInstance(S.make_client(raw_dir=os.devnull), S.GuardedClient)

    def test_the_watchlist_is_keyed_by_state_and_id(self):
        import re
        keys = S.watchlist(WATCH)
        self.assertTrue(keys)
        for k in keys:
            self.assertRegex(k, r"^(nsw|vic|qld|wa|sa|tas|act|nt):\S+$")
            self.assertFalse(re.search(r"\s", k))


if __name__ == "__main__":
    unittest.main()
