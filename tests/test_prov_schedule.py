"""The provincial collectors on a schedule, and the backfill to 2010.

Christopher, 3 October 2026: "Schedule the provincial collectors and
backfill to 2010", and for Quebec "DO what is necessary".

  * .github/workflows/prov-weekly.yml ("Provinces weekly"): one step per
    province, each on its own clock and run whatever the one before did,
    then the 5CA sheets, then the raw archive, the store and the sidecar,
    exactly as the Canada weekly does. Dispatched with `provinces` and
    `since`, the same workflow runs the backfill instead.
  * tools/prov_collect.py --resume (the weekly window) and --all-sessions
    (the backfill), with the sessions taken from each legislature's OWN
    index -- never from a list typed into the repo, which would skip a
    forgotten session in silence.
  * tools/coverage.py watches the provincial tables.

No network: index pages are trimmed copies from the probes of 2 October 2026
in tests/fixtures/prov/.
"""

import importlib.util
import json
import os
import re
import sys
import unittest

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, prov_store as ps  # noqa: E402
from src.ingest import (prov_ab as ab, prov_bc as bc, prov_mb as mb, prov_nb as nb,  # noqa: E402
                        prov_nl as nl, prov_ns as ns, prov_on as on, prov_qc as qc, prov_sk as sk)
from src.prov_fetch import Context, overlaps, session_order  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "prov")
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "prov-weekly.yml")
BUILT = ("ab", "sk", "bc", "mb", "on", "nb", "nl", "qc", "ns")


def fx(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _conn():
    return db.init_db(db.connect(":memory:"))


def codes(sessions, since=None, until=None):
    return [s["code"] for s in sessions if overlaps(s, since, until)]


def text():
    with open(WORKFLOW, encoding="utf-8") as fh:
        return fh.read()


def spec():
    doc = yaml.safe_load(text())
    return doc, doc.get("on", doc.get(True))


def steps():
    doc, _ = spec()
    return doc["jobs"]["collect"]["steps"]


# -- the sessions each legislature's own index lists ----------------------------

class SessionListTests(unittest.TestCase):
    """Since 2010, from the index each collector already reads."""

    def test_alberta_menu_lists_every_session_back_to_1990(self):
        s = ab.parse_sessions(fx("ab_vp_session_menu.html"))
        self.assertEqual(s[0]["code"], "22-2")
        self.assertEqual(codes(s, "2010-01-01"),
                         ["27-2", "27-3", "27-4", "27-5", "28-1", "28-2", "28-3", "29-1", "29-2",
                          "29-3", "29-4", "29-5", "30-1", "30-2", "30-3", "30-4", "31-1", "31-2"])
        # The selected session is in the menu too, with its years.
        self.assertIn({"code": "31-2", "start": "2025-01-01", "end": "2026-12-31"}, s)
        # A one-year session ("(2019)") spans that year only.
        self.assertIn({"code": "29-5", "start": "2019-01-01", "end": "2019-12-31"}, s)

    def test_bc_sessions_carry_the_apis_own_dates(self):
        nodes = json.loads(fx("bc_sessions.json"))["data"]["allSessions"]["nodes"]
        s = bc.parse_sessions(nodes)
        self.assertEqual([x["code"] for x in s], ["42-1", "42-2", "42-3", "42-4", "42-5", "43-1", "43-2"])
        self.assertEqual(s[-1]["start"], "2026-02-12")

    def test_manitoba_rows_pair_years_with_their_session(self):
        s = mb.parse_sessions(fx("mb_vp_sessions.html"))
        self.assertEqual(s[0], {"code": "40-1", "start": "2011-01-01", "end": "2012-12-31"})
        self.assertIn({"code": "41-1", "start": "2016-01-01", "end": "2016-12-31"}, s)   # "&nbsp;2016&nbsp;"
        self.assertEqual(s[-1]["code"], "43-3")

    def test_ontario_labels_print_dates(self):
        s = on.parse_sessions(fx("on_house_docs.html"))
        self.assertEqual(s[0], {"code": "40-1", "start": "2011-11-21", "end": "2012-10-15"})
        self.assertEqual(len(s), 8)

    def test_new_brunswick_includes_the_pages_own_session(self):
        s = nb.parse_sessions(fx("nb_journals_session_menu.html"))
        self.assertEqual(codes(s, "2010-01-01")[:2], ["56-4", "57-1"])
        self.assertIn({"code": "60-2", "start": "2022-01-01", "end": "2023-12-31"}, s)   # <span class="selected">
        self.assertIn({"code": "59-1", "start": "2018-01-01", "end": "2018-12-31"}, s)   # "(2018)"
        self.assertEqual(s[-1], {"code": "61-2", "start": "2025-01-01", "end": None})     # "(2025-)": still open

    def test_newfoundland_skips_the_swearing_in_links(self):
        s = nl.parse_sessions(fx("nl_hansard_index_sessions.html"))
        self.assertEqual(codes(s, "2010-01-01")[:3], ["46-2", "46-3", "46-4"])
        self.assertEqual(s[-1], {"code": "51-1", "start": "2025-01-01", "end": None})     # "2025--"
        self.assertIn({"code": "46-4", "start": "2011-01-01", "end": "2011-12-31"}, s)
        self.assertEqual(len({x["code"] for x in s}), len(s))

    def test_quebec_select_prints_french_dates(self):
        s = qc.parse_sessions(fx("qc_session_select.html"))
        self.assertEqual(codes(s, "2010-01-01"),
                         ["39-1", "39-2", "40-1", "41-1", "42-1", "42-2", "43-1", "43-2", "43-3"])
        self.assertIn({"code": "39-2", "start": "2011-02-23", "end": "2012-08-01"}, s)
        self.assertEqual(qc.parse_sessions(fx("qc_sittings_43-2.html"))[-1]["code"], "43-3")

    def test_nova_scotia_from_the_hansard_index_dated_by_the_assembly_pages(self):
        pairs = ns.index_sessions(fx("ns_hansard_index.html"))
        self.assertIn((61, 2), pairs)
        self.assertEqual(pairs[0], (65, 1))
        d = ns.parse_assembly_dates(fx("ns_assembly_dates_61.html"), 61)
        self.assertEqual(d[2], {"start": "2010-03-25", "end": "2011-03-31"})
        self.assertEqual(ns.parse_assembly_dates(fx("ns_assembly_dates_65.html"), 65)[1]["end"], None)

    def test_every_session_based_module_lists_sessions_and_sk_is_date_driven(self):
        for mod in (ab, bc, mb, on, nb, nl, qc, ns):
            self.assertTrue(callable(getattr(mod, "list_sessions", None)), mod.__name__)
        self.assertTrue(sk.DATE_DRIVEN)

    def test_sessions_order_by_legislature_then_session(self):
        self.assertLess(session_order("9-4"), session_order("10-1"))
        self.assertLess(session_order("43-3"), session_order("44-1"))


class SaskatchewanWindowTests(unittest.TestCase):
    def test_a_long_window_is_asked_a_year_at_a_time(self):
        self.assertEqual(sk.year_windows("2010-03-01", "2011-06-30"),
                         [("2010-03-01", "2010-12-31"), ("2011-01-01", "2011-06-30")])
        self.assertEqual(len(sk.year_windows("2010-01-01", "2026-10-07")), 17)
        self.assertEqual(sk.year_windows("2026-09-23", "2026-10-07"), [("2026-09-23", "2026-10-07")])

    def test_a_year_still_paging_at_the_cap_is_a_gap_not_a_silent_cut(self):
        nxt = ('<a class="page-link" href="/legislative-business/archive/?page={0}" rel="next">'
               'Next</a>')

        class Pager:
            user_agent = "CitizenGO-ParlMonitor/1.0 (contact: test)"
            throttle = 1.1

            def __init__(self):
                self.n = 0

            def get_text(self, url, feed, slug, archive=True, fallback_encoding=None):
                if url.endswith("robots.txt"):
                    from src.http import FetchError
                    raise FetchError(url, feed, slug, 1, "HTTP Error 404")
                self.n += 1
                return nxt.format(self.n)

        ctx = Context(_conn(), Pager(), "sk", since="2026-01-01", until="2026-02-01",
                      log=lambda *a: None)
        sk.collect(ctx)
        self.assertTrue(any("still a next page after" in g for g in ctx.gaps), ctx.gaps)


# -- the runner: --resume, the session plan, --roster-only -----------------------

class _Mod:
    """A collector that records what it was asked for."""
    PROV = "ab"
    CURRENT_SESSION = "31-2"
    __name__ = "src.ingest.prov_ab"

    def __init__(self, listed):
        self.listed = listed
        self.asked = []

    def list_sessions(self, ctx):
        return self.listed

    def collect(self, ctx, session=None, roster=True, bills=True):
        self.asked.append((session, ctx.since, ctx.until))
        return {"records_read": 1}


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.runner = _load("prov_collect")

    def _sitting(self, conn, prov, date, status="ok", url=None):
        ps.store_sitting(conn, prov, "{0}-31-2-{1}".format(prov, date), date, url or "u-" + date,
                         status=status)

    def test_resume_starts_two_weeks_before_the_newest_record(self):
        import datetime
        conn = _conn()
        self._sitting(conn, "ab", "2026-05-14")
        self._sitting(conn, "ab", "2026-05-28")
        self._sitting(conn, "bc", "2026-09-30")              # another province's record is not ours
        since = self.runner.resume_since(conn, "ab", today=datetime.date(2026, 10, 7), log=lambda *a: None)
        self.assertEqual(since, "2026-05-14")

    def test_resume_reaches_back_to_a_record_still_owed(self):
        import datetime
        conn = _conn()
        self._sitting(conn, "mb", "2026-07-02", status="gap")   # Hansard not out yet that day
        self._sitting(conn, "mb", "2026-09-30")
        since = self.runner.resume_since(conn, "mb", today=datetime.date(2026, 10, 7), log=lambda *a: None)
        self.assertEqual(since, "2026-07-02")
        # ...but not to one owed for longer than OWED_DAYS: that is the backfill's.
        conn2 = _conn()
        self._sitting(conn2, "mb", "2025-06-02", status="unreadable")
        self._sitting(conn2, "mb", "2026-09-30")
        self.assertEqual(self.runner.resume_since(conn2, "mb", today=datetime.date(2026, 10, 7),
                                                  log=lambda *a: None), "2026-09-16")

    def test_resume_on_an_empty_store_is_the_modules_own_default_said_out_loud(self):
        lines = []
        self.assertIsNone(self.runner.resume_since(_conn(), "qc", log=lines.append))
        self.assertTrue(any("nothing read for this province yet" in ln for ln in lines))

    def test_the_weekly_reads_current_and_a_newer_listed_session_with_a_gap(self):
        """Quebec's 44th legislature: collected the week it is listed, and the
        run fails loudly until CURRENT_SESSION is moved."""
        mod = _Mod([{"code": "31-1", "start": "2023-01-01", "end": "2025-12-31"},
                    {"code": "31-2", "start": "2025-01-01", "end": "2026-12-31"},
                    {"code": "31-3", "start": "2026-01-01", "end": None}])
        self.runner.module_for = lambda prov: mod
        stats, gaps = self.runner.run(_conn(), None, "ab", log=lambda *a: None)
        self.assertEqual([a[0] for a in mod.asked], ["31-2", "31-3"])
        self.assertEqual(len(gaps), 1)
        self.assertIn("newer than CURRENT_SESSION 31-2", gaps[0])
        self.assertIn("src/ingest/prov_ab.py", gaps[0])

    def test_the_weekly_with_nothing_newer_reads_the_current_session_only(self):
        mod = _Mod([{"code": "31-2", "start": "2025-01-01", "end": None}])
        self.runner.module_for = lambda prov: mod
        _stats, gaps = self.runner.run(_conn(), None, "ab", log=lambda *a: None)
        self.assertEqual([a[0] for a in mod.asked], ["31-2"])
        self.assertEqual(gaps, [])

    def test_all_sessions_reads_every_listed_session_touching_the_window_oldest_first(self):
        mod = _Mod(ab.parse_sessions(fx("ab_vp_session_menu.html")))
        self.runner.module_for = lambda prov: mod
        self.runner.run(_conn(), None, "ab", since="2010-01-01", all_sessions=True, log=lambda *a: None)
        asked = [a[0] for a in mod.asked]
        self.assertEqual(asked[0], "27-2")
        self.assertEqual(asked[-1], "31-2")
        self.assertEqual(len(asked), 18)
        self.assertTrue(all(a[1] == "2010-01-01" for a in mod.asked), "the window is passed on")

    def test_all_sessions_without_a_list_collects_nothing_and_says_so(self):
        mod = _Mod([])
        self.runner.module_for = lambda prov: mod
        _stats, gaps = self.runner.run(_conn(), None, "ab", since="2010-01-01", all_sessions=True,
                                       log=lambda *a: None)
        self.assertEqual(mod.asked, [])
        self.assertTrue(gaps and "cannot choose its sessions" in gaps[0])

    def test_all_sessions_needs_a_since(self):
        self.runner.module_for = lambda prov: _Mod([])
        with self.assertRaises(SystemExit):
            self.runner.run(_conn(), None, "ab", all_sessions=True, log=lambda *a: None)

    def test_one_clock_across_sessions_and_the_rest_is_disclosed(self):
        from src import drain
        mod = _Mod(ab.parse_sessions(fx("ab_vp_session_menu.html")))
        self.runner.module_for = lambda prov: mod
        lines = []
        self.runner.run(_conn(), None, "ab", since="2010-01-01", all_sessions=True,
                        budget=drain.Budget(0), log=lines.append)
        self.assertEqual(len(mod.asked), 1)             # the first is always started
        self.assertTrue(any("sessions not started this run" in ln for ln in lines))

    def test_saskatchewan_needs_no_session_list(self):
        class Sk:
            PROV = "sk"
            CURRENT_SESSION = "30-2"
            DATE_DRIVEN = True
            asked = []

            @classmethod
            def collect(cls, ctx, session=None, roster=True, bills=True):
                cls.asked.append((session, ctx.since))
                return {}
        self.runner.module_for = lambda prov: Sk
        self.runner.run(_conn(), None, "sk", since="2010-01-01", all_sessions=True, log=lambda *a: None)
        self.assertEqual(Sk.asked, [(None, "2010-01-01")])

    def test_roster_only_is_quebecs_and_refuses_elsewhere(self):
        self.runner.module_for = lambda prov: _Mod([])
        with self.assertRaises(SystemExit):
            self.runner.run(_conn(), None, "ab", roster_only=True, log=lambda *a: None)
        self.assertTrue(callable(qc.refresh_roster))


class ClosedSessionBillTests(unittest.TestCase):
    """A re-dispatched backfill must not spend its clock re-reading a closed
    session's finished bill pages (Alberta re-read every page every run)."""

    def test_alberta_keeps_a_closed_sessions_finished_bill(self):
        conn = _conn()
        key = ps.bill_key("ab", 30, 1, "1")
        ps.store_bill(conn, {"bill_key": key, "prov": "ab", "legislature": 30, "session": 1,
                             "number": "1", "stages": [], "text_read": 1})
        listing = ('<div class="header">Government Bills</div>'
                   '<a href="/x/bill?billinfoid=1&from=bills">Bill&nbsp;1</a></div>'
                   '<div>A Title</div>')

        class C:
            user_agent = "CitizenGO-ParlMonitor/1.0 (contact: test)"
            throttle = 1.1
            asked = []

            def get_text(self, url, feed, slug, archive=True, fallback_encoding=None):
                self.asked.append(url)
                if "bills-by-legislature" in url:
                    return listing
                from src.http import FetchError
                raise FetchError(url, feed, slug, 1, "HTTP Error 404")

        client = C()
        ctx = Context(conn, client, "ab", log=lambda *a: None)
        items = ab.parse_bill_list(listing)
        self.assertEqual(len(items), 1, "the fixture listing must parse")
        ab.fetch_bills(ctx, 30, 1, None, None)
        self.assertFalse(any("billinfoid" in u for u in client.asked), client.asked)


# -- the workflow ------------------------------------------------------------------

class WorkflowTests(unittest.TestCase):
    def test_it_is_named_as_the_coverage_watch_and_the_alert_expect(self):
        doc, _ = spec()
        self.assertEqual(doc["name"], "Provinces weekly")
        cov = _load("coverage")
        self.assertIn("Provinces weekly", cov.PIPELINES)
        with open(os.path.join(ROOT, ".github", "workflows", "alert.yml"), encoding="utf-8") as fh:
            alert = fh.read()
        self.assertIn('"Provinces weekly"', alert)

    def test_one_writer_at_a_time(self):
        doc, _ = spec()
        self.assertEqual(doc["concurrency"]["group"], "parl-monitor-state")
        self.assertIs(doc["concurrency"]["cancel-in-progress"], False)

    def test_a_weekly_schedule_with_a_gated_retry_slot(self):
        _doc, on_ = spec()
        crons = [c["cron"] for c in on_["schedule"]]
        self.assertEqual(len(crons), 2)
        self.assertEqual({c.split()[-1] for c in crons}, {"3"}, "both slots on the same day, for the gate")
        t = text()
        self.assertIn("needs: gate", t)
        self.assertIn("prov-weekly.yml/runs", t)

    def test_no_other_stateful_weekly_runs_that_day_inside_our_window(self):
        """Wednesday 10:00-18:00 UTC must hold no other parl-monitor-state
        cron: the group keeps ONE pending run, and a third arrival cancels it."""
        import glob
        for path in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
            if path == WORKFLOW:
                continue
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            if "group: parl-monitor-state" not in src:
                continue
            for c in re.findall(r'^\s*- cron: "([^"]+)"', src, re.M):
                minute, hour, dom, _mon, dow = c.split()
                if dom != "*":
                    continue          # monthly, keyed on the day of the month
                days = set()
                for part in dow.split(","):
                    if part == "*":
                        days |= set("0123456")
                    elif "-" in part:
                        a, b = part.split("-")
                        days |= {str(d) for d in range(int(a), int(b) + 1)}
                    else:
                        days.add(part)
                if "3" not in days:
                    continue
                for h in hour.split(","):
                    self.assertFalse(10 <= int(h) < 18, "{0}: {1}".format(os.path.basename(path), c))

    def test_every_built_province_has_its_own_step_on_its_own_clock(self):
        found = {}
        for s in steps():
            run = s.get("run", "")
            m = re.search(r"prov_collect\.py --prov (\w+) --resume --budget-seconds (\d+)", run)
            if m:
                found[m.group(1)] = s
                self.assertIn("always()", s["if"], s["name"])
                self.assertIn("steps.fetch.outcome == 'success'", s["if"], s["name"])
                self.assertIn("timeout-minutes", s, s["name"])
                self.assertGreater(s["timeout-minutes"] * 60, int(m.group(2)),
                                   s["name"] + ": the step timeout must exceed its clock")
                self.assertEqual(run.count("prov_collect.py"), 1, "one province per step")
        self.assertEqual(sorted(found), sorted(BUILT))

    def test_quebec_reads_its_roster_again_every_week_before_collecting(self):
        names = [s.get("name") for s in steps()]
        roster = next(i for i, s in enumerate(steps()) if "--prov qc --roster-only" in s.get("run", ""))
        collect = next(i for i, s in enumerate(steps()) if "--prov qc --resume" in s.get("run", ""))
        self.assertLess(roster, collect, names)
        self.assertIn("always()", steps()[roster]["if"])

    def test_a_5ca_sheet_step_for_every_province_after_the_collectors(self):
        idx = {s.get("name"): i for i, s in enumerate(steps())}
        last_collect = max(i for i, s in enumerate(steps()) if "prov_collect.py" in s.get("run", ""))
        for p in BUILT:
            step = next(s for s in steps() if "prov_5ca.py --prov {0} --all".format(p) in s.get("run", ""))
            self.assertIn("always()", step["if"])
            self.assertGreater(idx[step["name"]], last_collect)

    def test_archive_store_and_sidecar_are_published_as_the_canada_weekly_does(self):
        names = [s.get("name") for s in steps()]
        for n in ("Fetch the store", "Fetch the raw archive", "Publish the raw archive",
                  "Publish the store", "Commit state", "Health summary"):
            self.assertIn(n, names)
        self.assertLess(names.index("Publish the raw archive"), names.index("Publish the store"))
        self.assertLess(names.index("Publish the store"), names.index("Commit state"))
        by = {s.get("name"): s for s in steps()}
        for n in ("Publish the raw archive", "Publish the store", "Commit state"):
            self.assertEqual(by[n]["if"], "always() && steps.fetch.outcome == 'success'", n)
        commit = by["Commit state"]["run"]
        self.assertIn("git add data/", commit)
        self.assertIn("for attempt in 1 2 3", commit)
        self.assertIn("git pull --rebase --autostash", commit)
        self.assertIn("the sidecar commit never reached origin", commit)

    def test_the_backfill_is_a_dispatch_with_provinces_and_since(self):
        _doc, on_ = spec()
        inputs = on_["workflow_dispatch"]["inputs"]
        self.assertEqual(inputs["provinces"]["default"], "")
        self.assertEqual(inputs["since"]["default"], "2010-01-01")
        self.assertIn("minutes", inputs)
        bf = next(s for s in steps() if "--all-sessions" in s.get("run", ""))
        self.assertIn("inputs.provinces != ''", bf["if"])
        self.assertIn("always()", bf["if"])
        self.assertIn('--since "$SINCE"', bf["run"])
        self.assertIn('--budget-seconds "$PER"', bf["run"])
        self.assertIn("|| rc=1", bf["run"], "one province failing must not cost the others")
        self.assertIn('if [ "$MINUTES" -gt 300 ]', bf["run"], "the clock is bounded under the 330-minute job")
        self.assertLessEqual(bf["timeout-minutes"], 330)
        doc, _ = spec()
        self.assertIn("330", str(doc["jobs"]["collect"]["timeout-minutes"]))

    def test_a_backfill_dispatch_skips_the_weekly_steps(self):
        for s in steps():
            if "--resume" in s.get("run", "") or "--roster-only" in s.get("run", ""):
                self.assertIn("inputs.provinces == ''", s["if"], s["name"])

    def test_the_backfill_refuses_an_unbuilt_province_by_name(self):
        bf = next(s for s in steps() if "--all-sessions" in s.get("run", ""))
        self.assertIn("ab|sk|bc|mb|on|nb|nl|qc|ns)", bf["run"])

    def test_no_slack_credential_and_no_model_key(self):
        t = text()
        self.assertNotIn("SLACK", t)
        self.assertNotIn("ANTHROPIC_API_KEY", t)


# -- coverage ----------------------------------------------------------------------

class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.cov = _load("coverage")

    def test_the_provincial_tables_are_placed_as_measured(self):
        feeds = {f[0] for f in self.cov.FEEDS}
        self.assertTrue({"prov_members", "prov_bills"} <= feeds)
        self.assertIn("prov_divisions", self.cov.ONCE_EVER)
        self.assertEqual(self.cov.PIPELINE_FEEDS["Provinces weekly"], ["prov_members", "prov_bills"])

    def test_an_empty_table_is_excused_only_until_the_first_heartbeat(self):
        import datetime
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE source_runs (source TEXT PRIMARY KEY, last_run TEXT NOT NULL, "
                     "run_id TEXT, note TEXT)")
        for t in ("prov_members", "prov_bills", "prov_divisions", "prov_sittings"):
            conn.execute("CREATE TABLE {0} (x TEXT, last_seen TEXT)".format(t))
        feeds, once = self.cov.FEEDS, self.cov.ONCE_EVER
        self.cov.FEEDS = [f for f in feeds if f[0].startswith("prov_")]
        self.cov.ONCE_EVER = {k: v for k, v in once.items() if k.startswith("prov_")}
        try:
            lines = []
            overdue = self.cov.check(conn, today=datetime.date(2026, 10, 4), log=lines.append)
            self.assertEqual([o for o in overdue if "prov_" in o], [])
            self.assertTrue(any("AWAITING FIRST RUN" in ln for ln in lines))
            conn.execute("INSERT INTO source_runs VALUES ('Provinces weekly', '2026-10-07', '1', '')")
            overdue = self.cov.check(conn, today=datetime.date(2026, 10, 8), log=lambda *a: None)
            for t in ("prov_members", "prov_bills", "prov_divisions"):
                self.assertTrue(any(t in o and "NO ROWS" in o for o in overdue), (t, overdue))
        finally:
            self.cov.FEEDS, self.cov.ONCE_EVER = feeds, once


if __name__ == "__main__":
    unittest.main()


class KnownGapsTests(unittest.TestCase):
    """3 Oct 2026: a reviewed permanent gap is recorded but does not fail."""

    def test_a_listed_gap_is_known_and_an_unlisted_one_is_not(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "prov_collect", os.path.join(ROOT, "tools", "prov_collect.py"))
        pc = importlib.util.module_from_spec(spec); spec.loader.exec_module(pc)
        self.assertTrue(pc.known_gap("nb", "journal 2023-06-09: truncated PDF: no %%EOF marker"))
        self.assertFalse(pc.known_gap("nb", "journal 2023-06-10: truncated"))
        self.assertFalse(pc.known_gap("ab", "journal 2023-06-09: truncated"))
