"""The US, Irish and Australian session judges (9 October 2026, Christopher:
"Switch US, Ireland and Australia scoring to the free route"): each tool's
--queue-out / --queue-in (src/session_queue.py), the runner
(tools/session_judge.sh, with a FAKE claude: nothing here calls a model),
the Mini jobs and their plists. No network, no spend. One class per country,
on one shared set of checks."""

import glob
import os
import plistlib
import re
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import session_queue as sq  # noqa: E402
import coverage  # noqa: E402
import test_au_monitor as tau  # noqa: E402
import test_ie_monitor as tie  # noqa: E402
import test_prov_session_judge as tprov  # noqa: E402
import test_us_monitor as tus  # noqa: E402

MARKERS = {"us": "<!-- us-session-queue v1 -->", "ie": "<!-- ie-session-queue v1 -->",
           "au": "<!-- au-session-queue v1 -->", "prov": "<!-- prov-session-queue v1 -->"}
fill = tprov.fill


def us_store():
    conn = tus.store()
    tus.bill(conn, "119/hr/21", "Born-Alive Abortion Survivors Protection Act", [1],
             "Received in the Senate.", "2026-10-06", cosponsors=163)
    tus.bill(conn, "119/hr/99", "Parental Rights in Education Act", [5],
             "Referred to the Committee.", "2026-10-07", introduced="2026-10-07")
    tus.bill(conn, "119/s/146", "TAKE IT DOWN Act", [7], "Became Public Law No: 119-12.",
             "2025-05-19", law="Public Law 119-12")
    tus.bill(conn, "119/hr/9", "Border Act", [11], "Referred to the Committee.", "2026-10-06")
    tus.vote(conn, "house-119-2-240", "house", 240, "2026-10-08", "119/hr/21", "H R 21", [1], [1])
    conn.commit()
    return conn


def ie_store():
    conn = tie.store()
    tie.bill(conn, "2026/10", "Three Day Wait Bill 2026", [1], at="2026-10-07")
    tie.bill(conn, "2025/44", "Assisted Dying Bill 2025", [2], at="2026-06-01")
    tie.bill(conn, "2026/3", "International Protection Bill 2026", [11])
    tie.division(conn, "dail/34/2026-10-08/vote_12", "2026-10-08", "2026/10", [1], [1],
                 amendment="To delete the three-day wait.")
    conn.commit()
    return conn


def au_store():
    conn = tau.store()
    tau.bill(conn, "s1500", "Sex Discrimination Amendment (Recognising Biological Sex) Bill 2026",
             [5], first="2026-07-01", stage="First Reading", stage_date="2026-07-01")
    tau.bill(conn, "r7600", "New Born Alive Bill 2026", [1], first="2026-09-15",
             stage="Second Reading", stage_date="2026-09-15")
    tau.bill(conn, "r7401", "Migration Amendment Bill 2025", [11])
    tau.division(conn, "senate-2026-09-15-8", "2026-09-15", 8, [5], [5])
    conn.commit()
    return conn


class Country:
    """The shared checks; a subclass names its country."""
    cc = None
    tool = None            # the loaded tools/<cc>_triage.py module
    make = None            # a store with pending items, migration-only rows among them
    frame_words = None
    name = None            # the heartbeat
    weekly = None
    monitor = None
    cap = None

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "q.md")
        self.conn = type(self).make()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def ids(self):
        return re.findall(r"^### item: (\S+)$", open(self.path, encoding="utf-8").read(), re.M)

    def quiet(self, *_):
        pass

    def score_of(self, item):
        table, _, key = item.partition(":")
        return self.conn.execute("SELECT triage_score, why_it_matters FROM {0} WHERE {1} = ?".format(
            table, self.tool.SOURCES[table]), (key,)).fetchone()

    # --- the queue ----------------------------------------------------------
    def test_the_marker_is_its_own(self):
        self.assertEqual(self.tool.QUEUE_MARKER, MARKERS[self.cc])

    def test_queue_round_trip_scores_like_the_api(self):
        pending = [i.id for i in self.tool.pending(self.conn)]
        self.assertGreaterEqual(len(pending), 3)
        n, rest = self.tool.queue_out(self.conn, self.path, "2026-10-09", 25, log=self.quiet)
        self.assertEqual((n, rest), (len(pending), 0))
        self.assertEqual(self.ids(), pending)                    # newest first, as the API judge
        text = open(self.path, encoding="utf-8").read()
        self.assertIn(MARKERS[self.cc], text.splitlines()[:5])
        self.assertIn(self.frame_words, text)                     # the country's own frame
        first = self.tool.pending(self.conn)[0]
        self.assertIn("- text: " + " ".join(first.text.split()), text)   # the API judge's text
        self.assertNotIn(":119/hr/9\n", text)
        fill(self.path, {i: (2, "Matters here.") for i in pending})
        got = self.tool.queue_in(self.conn, self.path, "2026-10-09", log=self.quiet)
        self.assertEqual(got, (len(pending), 0, 0))
        for i in pending:
            self.assertEqual(tuple(self.score_of(i)), (2, "Matters here."))
        rows = self.conn.execute("SELECT item, judge, model, score, scored_at FROM session_scores").fetchall()
        self.assertEqual({r[0] for r in rows}, set(pending))
        self.assertTrue(all(r[1:] == (self.cc, "claude-code-session", 2, "2026-10-09") for r in rows))
        self.assertEqual(self.tool.pending(self.conn), [])
        # once ever: the same file again changes nothing
        logs = []
        self.assertEqual(self.tool.queue_in(self.conn, self.path, "2026-10-09", log=logs.append)[0], 0)
        self.assertTrue(any("already scored" in x for x in logs))

    def test_a_limit_caps_the_queue(self):
        n, rest = self.tool.queue_out(self.conn, self.path, "2026-10-09", 1, log=self.quiet)
        self.assertEqual((n, len(self.ids())), (1, 1))
        self.assertGreaterEqual(rest, 2)

    def test_malformed_items_are_refused_and_good_ones_applied(self):
        self.tool.queue_out(self.conn, self.path, "2026-10-09", 25, log=self.quiet)
        a, b, c = self.ids()[:3]
        fill(self.path, {a: (3, "A trigger."), b: (5, "Out of range."), c: (1, "")})
        foreign = "items:uk-1" if self.cc != "us" else "ie_bills:2026/10"
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write("### item: {0}:nope\nSCORE: 2\nWHY: x\n"
                     "### item: {1}\nSCORE: 2\nWHY: x\n".format(list(self.tool.SOURCES)[0], foreign))
        logs = []
        got = self.tool.queue_in(self.conn, self.path, "2026-10-09", log=logs.append)
        self.assertEqual(got, (1, 4, len(self.ids()) - 5))
        self.assertEqual(tuple(self.score_of(a)), (3, "A trigger."))
        self.assertEqual(self.score_of(b)[0], None)
        self.assertEqual(self.score_of(c)[0], None)
        joined = "\n".join(logs)
        self.assertIn("not one digit 0-3", joined)
        self.assertIn("scored with no WHY", joined)
        self.assertIn("in the store", joined)
        self.assertIn("not a", joined)

    def test_another_judges_queue_is_refused_whole(self):
        for other, marker in MARKERS.items():
            if other == self.cc:
                continue
            items = self.tool.pending(self.conn)
            sq.write_queue(self.path, items, "T", marker, "frame")
            fill(self.path, {i.id: (3, "Wrong judge.") for i in items})
            logs = []
            self.assertIsNone(self.tool.queue_in(self.conn, self.path, "2026-10-09", log=logs.append))
            self.assertIn("not this judge's queue", logs[0])
            self.assertEqual(len(self.tool.pending(self.conn)), len(items), other)

    def test_rescore_clears_the_session_note(self):
        self.tool.queue_out(self.conn, self.path, "2026-10-09", 25, log=self.quiet)
        first = self.ids()[0]
        fill(self.path, {first: (3, "Trigger.")})
        self.tool.queue_in(self.conn, self.path, "2026-10-09", log=self.quiet)
        table = first.partition(":")[0]
        self.assertEqual(self.tool.rescore(self.conn, first if table != list(self.tool.SOURCES)[0]
                                           else first.partition(":")[2]), 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM session_scores").fetchone()[0], 0)
        self.assertIn(first, [i.id for i in self.tool.pending(self.conn)])

    # --- the runner, with a fake claude ------------------------------------
    def disk(self):
        db = os.path.join(self.tmp.name, "store.db")
        out = sqlite3.connect(db)
        self.conn.backup(out)
        out.close()
        return db

    def fake_claude(self, logged="true", method="claude.ai"):
        bindir = os.path.join(self.tmp.name, "bin")
        os.makedirs(bindir, exist_ok=True)
        path = os.path.join(bindir, "claude")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(tprov.FAKE_CLAUDE % {"logged": logged, "method": method})
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return bindir

    def run_judge(self, db, path_dirs, max_items="100", chunk="25"):
        env = dict(os.environ, FAKE_LOG=os.path.join(self.tmp.name, "fake"),
                   ANTHROPIC_API_KEY="sk-must-not-leak", ANTHROPIC_AUTH_TOKEN="tok-must-not-leak",
                   PATH=":".join(path_dirs))
        return subprocess.run(
            ["bash", os.path.join(ROOT, "tools", "session_judge.sh"),
             "tools/{0}_triage.py".format(self.cc), max_items, chunk,
             "--db", db, "--date", "2026-10-09"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)

    def test_fake_claude_end_to_end_without_the_api_key(self):
        db = self.disk()
        want = len(self.tool.pending(self.conn))
        p = self.run_judge(db, [self.fake_claude(), os.path.dirname(sys.executable), "/usr/bin", "/bin"],
                           max_items="2", chunk="1")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("round 2: 1 item(s) to claude", p.stdout)
        self.assertIn("session judge: 2 item(s) scored this run", p.stdout)
        conn = sqlite3.connect(db)
        try:
            rows = conn.execute("SELECT item, judge, model, score FROM session_scores").fetchall()
        finally:
            conn.close()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r[1:] == (self.cc, "claude-code-session", 2) for r in rows))
        env = open(os.path.join(self.tmp.name, "fake.env"), encoding="utf-8").read()
        self.assertNotIn("ANTHROPIC_API_KEY", env)               # never API spend
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", env)
        self.assertNotIn("must-not-leak", env)
        args = open(os.path.join(self.tmp.name, "fake.args"), encoding="utf-8").read().split()
        self.assertEqual(args[args.index("--tools") + 1], "Read,Edit")
        self.assertIn("--restricted", args)
        self.assertGreater(want, 2)

    def test_no_claude_or_api_key_auth_is_a_gap_and_the_store_untouched(self):
        db = self.disk()
        before = os.path.getmtime(db)
        p = self.run_judge(db, ["/usr/bin", "/bin"])
        self.assertEqual(p.returncode, 3)
        self.assertIn("[gap] session judge: the claude CLI is not installed", p.stdout)
        for logged, method in (("true", "apiKey"), ("false", "none")):
            p = self.run_judge(db, [self.fake_claude(logged, method),
                                    os.path.dirname(sys.executable), "/usr/bin", "/bin"])
            self.assertEqual(p.returncode, 3, (logged, method))
            self.assertIn("not signed in to a claude.ai account", p.stdout)
        self.assertEqual(os.path.getmtime(db), before)

    # --- the job, its heartbeat and its plist -----------------------------
    def read(self, *path):
        with open(os.path.join(ROOT, *path), encoding="utf-8") as fh:
            return fh.read()

    def test_job_order_score_then_edition_then_archive_then_store(self):
        job = self.read("jobs", "{0}-session-judge.sh".format(self.cc))
        steps = [job.index(s) for s in (
            'bash tools/session_judge.sh tools/{0}_triage.py "${{SESSION_JUDGE_MAX:-{1}}}" 25'.format(
                self.cc, self.cap),
            "python3 tools/{0} --edition --date".format(self.monitor),
            "python3 tools/raw_state.py --push", "python3 tools/db_state.py --push")]
        self.assertEqual(steps, sorted(steps))
        self.assertIn("# mini_run: commit editions\n", job)
        self.assertNotIn("--dm", job)                              # the weekly already spoke
        self.assertLess(job.index('if [ "$jrc" -eq 3 ]'), job.index("raw_state.py --push"))
        self.assertIn('GITHUB_WORKFLOW="${{GITHUB_WORKFLOW:-{0}}}"'.format(self.name), job)
        self.assertIn("editions/{0}-monitor-".format(self.cc), job)
        self.assertTrue(os.access(os.path.join(ROOT, "jobs", "{0}-session-judge.sh".format(self.cc)), os.X_OK))

    def test_heartbeat_is_its_own_and_on_demand(self):
        self.assertIn(self.name, coverage.ON_DEMAND)
        self.assertNotIn(self.name, coverage.PIPELINES)

    def test_mini_only_no_workflow(self):
        for path in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
            # A weekly's comments may point at the job; no step may run it.
            text = "\n".join(ln.split("#", 1)[0] for ln in self.read(path).splitlines())
            self.assertNotIn("{0}-session-judge".format(self.cc), text, path)
            self.assertNotIn(self.name, text, path)

    def test_the_paid_judge_stays_in_the_weekly_and_gated(self):
        job = self.read("jobs", "{0}-weekly.sh".format(self.cc))
        self.assertIn('if [ "$JUDGE" = "on" ]; then\n', job)
        self.assertIn("python3 tools/{0}_triage.py --".format(self.cc),
                      job.split('if [ "$JUDGE" = "on" ]; then\n')[1].split("\nfi\n")[0])
        flow = self.read(".github", "workflows", "{0}-weekly.yml".format(self.cc))
        self.assertIn("{0}_JUDGE: ${{{{ vars.{0}_JUDGE }}}}".format(self.cc.upper()), flow)

    def test_plist_after_its_weekly(self):
        doc, mine = plist_slots("{0}-session-judge".format(self.cc))
        self.assertEqual(doc["ProgramArguments"][-1], "{0}-session-judge".format(self.cc))
        self.assertTrue(doc["ProgramArguments"][1].startswith("/Users/christopherjoyce/runner/"))
        self.assertTrue(doc["StandardOutPath"].startswith("/Users/christopherjoyce/runner/logs/"))
        self.assertGreaterEqual(int(doc["EnvironmentVariables"]["JOB_TIMEOUT"]), 5400)
        _, weekly = plist_slots(self.weekly)
        for s in mine:
            self.assertEqual(s["Weekday"], weekly[0]["Weekday"])
            self.assertGreater((s["Hour"], s["Minute"]), (weekly[0]["Hour"], weekly[0]["Minute"]))


def plist_slots(name):
    with open(os.path.join(ROOT, "ops", "launchd",
                           "net.citizengo.parlmonitor.{0}.plist".format(name)), "rb") as fh:
        doc = plistlib.load(fh)
    s = doc.get("StartCalendarInterval") or []
    return doc, s if isinstance(s, list) else [s]


class USSessionJudgeTests(Country, unittest.TestCase):
    cc, tool, make = "us", tus.ust, staticmethod(us_store)
    frame_words, name, weekly, monitor, cap = ("US Congress monitor", "US session judge",
                                              "us-weekly", "us_monitor.py", 150)

    def test_amendment_purpose_reaches_the_queue(self):
        self.conn.execute("UPDATE us_divisions SET amendment_text = 'To prohibit gender transition "
                          "procedures for minors.'")
        self.tool.queue_out(self.conn, self.path, "2026-10-09", 25, log=self.quiet)
        self.assertIn("Amendment: To prohibit gender transition procedures for minors.",
                      open(self.path, encoding="utf-8").read())


class IESessionJudgeTests(Country, unittest.TestCase):
    cc, tool, make = "ie", tie.iet, staticmethod(ie_store)
    frame_words, name, weekly, monitor, cap = ("CitizenGO's Ireland monitor", "Ireland session judge",
                                              "ie-weekly", "ie_monitor.py", 100)


class AUSessionJudgeTests(Country, unittest.TestCase):
    cc, tool, make = "au", tau.aut, staticmethod(au_store)
    frame_words, name, weekly, monitor, cap = ("Australian Federal Parliament monitor",
                                              "Australia session judge", "au-weekly",
                                              "au_monitor.py", 100)


class SlotTests(unittest.TestCase):
    """Every session judge starts at a minute no other Mini job starts on its
    day, and no other job starts in the half hour after it (its rounds run
    then; a longer run queues the next job on the runner lock, never the
    other way round)."""

    JUDGES = ("prov-session-judge", "editions-session-judge", "us-session-judge", "ie-session-judge",
              "au-session-judge")

    def test_the_slots(self):
        want = {"us-session-judge": {(5, 19, 30)}, "ie-session-judge": {(5, 18, 30)},
                "au-session-judge": {(5, 3, 10)}, "prov-session-judge": {(3, 16, 15)}}
        for name, slots in want.items():
            self.assertEqual({(s["Weekday"], s["Hour"], s["Minute"]) for s in plist_slots(name)[1]},
                             slots, name)

    def test_no_other_job_starts_with_or_just_after_a_session_judge(self):
        others = {}
        for path in glob.glob(os.path.join(ROOT, "ops", "launchd", "*.plist")):
            name = os.path.basename(path)[len("net.citizengo.parlmonitor."):-len(".plist")]
            others[name] = plist_slots(name)[1]
        for judge in self.JUDGES:
            for s in others[judge]:
                start = s["Hour"] * 60 + s["Minute"]
                for name, theirs in others.items():
                    if name == judge:
                        continue
                    for t in theirs:
                        if t.get("Weekday") not in (None, s["Weekday"]) or "Day" in t:
                            continue
                        at = t.get("Hour", 0) * 60 + t.get("Minute", 0)
                        self.assertFalse(start <= at < start + 30,
                                         "{0} starts at {1:02d}:{2:02d} on day {3}, within half "
                                         "an hour of {4}".format(name, at // 60, at % 60,
                                                                  s["Weekday"], judge))


if __name__ == "__main__":
    unittest.main()
