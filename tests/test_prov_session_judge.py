"""The provinces session judge (option 3, 9 October 2026): the queue file
(src/session_queue.py), tools/prov_triage.py --queue-out / --queue-in, the
runner (tools/session_judge.sh, with a FAKE claude: nothing here calls a
model), the Mini job and its plist. No network, no spend."""

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

from src import db, noise, session_queue as sq, triage  # noqa: E402
import test_prov_monitor as tpm  # noqa: E402
import coverage  # noqa: E402

pt = tpm.pt
MARK = pt.QUEUE_MARKER


def items(*ids):
    return [triage.TriageItem(id=i, title="Title " + i, text="Text\nof " + i, tier=1,
                              issue_areas=[3], watchlist_hit=False) for i in ids]


def fill(path, scores):
    """Fill SCORE/WHY per id the way a session would: {id: (score, why)}."""
    out, cur = [], None
    for line in open(path, encoding="utf-8").read().splitlines():
        m = re.match(r"^### item: (\S+)$", line)
        if m:
            cur = m.group(1)
        if cur in scores and line == "SCORE: ":
            line = "SCORE: {0}".format(scores[cur][0])
        elif cur in scores and line == "WHY: ":
            line = "WHY: {0}".format(scores[cur][1])
        out.append(line)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")


class QueueFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "q.md")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, *ids):
        return sq.write_queue(self.path, items(*ids), "T", MARK, pt.SYSTEM_PROMPT_PROV)

    def test_round_trip(self):
        self.assertEqual(self.write("prov_bills:a", "prov_bills:b"), 2)
        text = open(self.path, encoding="utf-8").read()
        self.assertIn("- text: Text of prov_bills:a", text)          # one line, the API judge's text
        self.assertIn("Canadian provinces monitor", text)              # the provincial frame
        fill(self.path, {"prov_bills:a": (3, "A trigger."), "prov_bills:b": (0, "Unrelated.")})
        res, refused, blank = sq.read_queue(self.path, MARK)
        self.assertEqual([(r.id, r.score, r.why) for r in res],
                         [("prov_bills:a", 3, "A trigger."), ("prov_bills:b", 0, "Unrelated.")])
        self.assertEqual((refused, blank), ([], []))

    def test_the_header_itself_parses_as_nothing(self):
        self.write()
        self.assertEqual(sq.read_queue(self.path, MARK), ([], [], []))

    def test_malformed_items_are_refused_one_by_one(self):
        self.write("i:ok", "i:five", "i:word", "i:nowhy", "i:blank")
        fill(self.path, {"i:ok": (2, "Fine."), "i:five": (5, "x"), "i:word": ("two", "x"),
                         "i:nowhy": (1, "")})
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write("### item: i:ok\nSCORE: 1\nWHY: again\n"
                     "### item: i:dbl\nSCORE: 1\nSCORE: 2\nWHY: two scores\n")
        res, refused, blank = sq.read_queue(self.path, MARK)
        self.assertEqual([r.id for r in res], ["i:ok"])
        why = dict(refused)
        self.assertIn("not one digit 0-3", why["i:five"])
        self.assertIn("not one digit 0-3", why["i:word"])
        self.assertIn("no WHY", why["i:nowhy"])
        self.assertIn("appears twice", why["i:ok"])
        self.assertIn("two SCORE lines", why["i:dbl"])
        self.assertEqual(blank, ["i:blank"])

    def test_another_judges_file_is_refused_whole(self):
        sq.write_queue(self.path, items("x:1"), "T", "<!-- us-session-queue v1 -->", "frame")
        fill(self.path, {"x:1": (2, "y")})
        res, refused, _ = sq.read_queue(self.path, MARK)
        self.assertEqual(res, [])
        self.assertEqual(refused[0][0], "(file)")


class StoreTests(unittest.TestCase):
    """--queue-out and --queue-in on a store built in memory."""

    def setUp(self):
        self.base = tpm.EditionTests("test_an_active_province_gets_its_section_and_the_quiet_ones_one_line")
        self.base.setUp()
        self.conn = self.base.conn
        self.path = os.path.join(self.base.tmp.name, "q.md")
        noise._FILES.clear()

    def tearDown(self):
        self.base.tearDown()

    def ids(self):
        return [m for m in re.findall(r"^### item: (\S+)$", open(self.path, encoding="utf-8").read(), re.M)]

    def test_queue_out_then_in_scores_like_the_api(self):
        n, _rest = pt.queue_out(self.conn, self.path, tpm.TODAY, 25, log=lambda *_: None)
        self.assertGreater(n, 0)
        ids = self.ids()
        self.assertEqual(ids, [i.id for i in pt.pending(self.conn, tpm.TODAY)][:25])
        fill(self.path, {i: (2, "Matters.") for i in ids})
        got = pt.queue_in(self.conn, self.path, tpm.TODAY, log=lambda *_: None)
        self.assertEqual(got, (len(ids), 0, 0))
        rows = self.conn.execute("SELECT item, prov, score, why, model, scored_at FROM prov_scores").fetchall()
        self.assertEqual({r[0] for r in rows}, set(ids))
        self.assertTrue(all(r[1] == "ab" and r[2] == 2 and r[3] == "Matters." and
                            r[4] == "claude-code-session" and r[5] == tpm.TODAY for r in rows))
        self.assertEqual(pt.pending(self.conn, tpm.TODAY), [])
        # once ever: the same file again changes nothing
        logs = []
        self.assertEqual(pt.queue_in(self.conn, self.path, tpm.TODAY, log=logs.append)[0], 0)
        self.assertTrue(any("already scored" in x for x in logs))

    def test_a_limit_caps_the_queue(self):
        n, rest = pt.queue_out(self.conn, self.path, tpm.TODAY, 1, log=lambda *_: None)
        self.assertEqual(n, 1)
        self.assertEqual(len(self.ids()), 1)
        self.assertGreaterEqual(rest, 1)

    def test_unknown_ids_are_refused_and_good_ones_applied(self):
        pt.queue_out(self.conn, self.path, tpm.TODAY, 25, log=lambda *_: None)
        good = self.ids()[0]
        fill(self.path, {good: (3, "Trigger.")})
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write("### item: prov_bills:zz-9-9/1\nSCORE: 2\nWHY: x\n"
                     "### item: items:uk-1\nSCORE: 2\nWHY: x\n")
        logs = []
        self.assertEqual(pt.queue_in(self.conn, self.path, tpm.TODAY, log=logs.append), (1, 2, len(self.ids()) - 3))
        self.assertEqual(sum("not a provincial item" in x for x in logs), 2)

    def test_a_noise_muted_item_is_not_queued(self):
        tpm.bill(self.conn, "ns-65-1/57", "Down Syndrome Day Act", [1],
                 stages=[{"stage": "First Reading", "date": "2026-10-08"}])
        self.conn.execute("UPDATE prov_bills SET matched_terms='[\"Down syndrome\"]' WHERE bill_key='ns-65-1/57'")
        self.assertIn("prov_bills:ns-65-1/57", [i.id for i in pt.pending(self.conn, tpm.TODAY)])
        pt.queue_out(self.conn, self.path, tpm.TODAY, 25, log=lambda *_: None)
        self.assertNotIn("prov_bills:ns-65-1/57", self.ids())

    def test_the_wrong_file_fails(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("# not a queue\n### item: prov_bills:ab-31-3/9\nSCORE: 2\nWHY: x\n")
        self.assertIsNone(pt.queue_in(self.conn, self.path, tpm.TODAY, log=lambda *_: None))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM prov_scores").fetchone()[0], 0)


FAKE_CLAUDE = r'''#!/bin/bash
# A stand-in for the Claude Code CLI: no model, no network.
case "$1" in
  auth) echo '{"loggedIn": %(logged)s, "authMethod": "%(method)s"}'; exit 0 ;;
  --help) echo "--restricted  --permission-prompts  --tools"; exit 0 ;;
esac
env > "$FAKE_LOG.env"
echo "$@" > "$FAKE_LOG.args"
cat > "$FAKE_LOG.prompt"
ls > "$FAKE_LOG.ls"
python3 - <<'PY'
import re
p = "queue.md"
out, cur = [], None
for line in open(p, encoding="utf-8").read().splitlines():
    if line.startswith("### item: "):
        cur = line.split(": ", 1)[1]
    if cur and line == "SCORE: ":
        line = "SCORE: 2"
    elif cur and line == "WHY: ":
        line = "WHY: Scored by the fake session."
    out.append(line)
open(p, "w", encoding="utf-8").write("\n".join(out) + "\n")
PY
echo "scored"
'''


class RunnerTests(unittest.TestCase):
    """tools/session_judge.sh, with a fake claude on PATH."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = os.path.join(self.tmp.name, "bin")
        os.makedirs(self.bin)
        self.db = os.path.join(self.tmp.name, "store.db")
        base = tpm.EditionTests("test_an_active_province_gets_its_section_and_the_quiet_ones_one_line")
        base.setUp()
        disk = sqlite3.connect(self.db)
        base.conn.backup(disk)
        disk.close()
        base.tearDown()
        self.log = os.path.join(self.tmp.name, "fake")

    def tearDown(self):
        self.tmp.cleanup()

    def claude(self, logged="true", method="claude.ai"):
        path = os.path.join(self.bin, "claude")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(FAKE_CLAUDE % {"logged": logged, "method": method})
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)

    def run_judge(self, path_dirs=None, max_items="100", chunk="1"):
        env = dict(os.environ, FAKE_LOG=self.log, ANTHROPIC_API_KEY="sk-must-not-leak",
                   PATH=":".join(path_dirs or [self.bin, os.path.dirname(sys.executable),
                                               "/usr/bin", "/bin"]))
        return subprocess.run(
            ["bash", os.path.join(ROOT, "tools", "session_judge.sh"), "tools/prov_triage.py",
             max_items, chunk, "--db", self.db, "--date", tpm.TODAY],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)

    def scores(self):
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT item, score, model FROM prov_scores").fetchall()
        finally:
            conn.close()

    def test_scores_round_by_round_within_the_cap(self):
        self.claude()
        p = self.run_judge(max_items="2", chunk="1")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        got = self.scores()
        self.assertEqual(len(got), 2)
        self.assertTrue(all(s == 2 and m == "claude-code-session" for _, s, m in got))
        self.assertIn("session judge: 2 item(s) scored this run", p.stdout)
        self.assertIn("round 2: 1 item(s) to claude", p.stdout)
        env = open(self.log + ".env", encoding="utf-8").read()
        self.assertNotIn("ANTHROPIC_API_KEY", env)               # never API spend
        args = open(self.log + ".args", encoding="utf-8").read().split()
        for flag in ("-p", "--restricted", "--strict-mcp-config", "--no-session-persistence"):
            self.assertIn(flag, args)
        self.assertEqual(args[args.index("--tools") + 1], "Read,Edit")
        self.assertEqual(args[args.index("--permission-prompts") + 1], "none")
        self.assertEqual(open(self.log + ".ls", encoding="utf-8").read().split(), ["queue.md"])
        self.assertIn("queue.md", open(self.log + ".prompt", encoding="utf-8").read())

    def test_no_claude_is_a_gap_and_the_store_is_untouched(self):
        before = os.path.getmtime(self.db)
        p = self.run_judge(path_dirs=["/usr/bin", "/bin"])
        self.assertEqual(p.returncode, 3)
        self.assertIn("[gap] session judge: the claude CLI is not installed", p.stdout)
        self.assertEqual(os.path.getmtime(self.db), before)

    def test_signed_out_or_api_key_auth_is_a_gap(self):
        for logged, method in (("false", "none"), ("true", "apiKey")):
            self.claude(logged, method)
            p = self.run_judge()
            self.assertEqual(p.returncode, 3, (logged, method))
            self.assertIn("[gap] session judge: claude is not signed in to a claude.ai account", p.stdout)
            self.assertEqual(self.scores() if self._has_scores() else [], [])

    def _has_scores(self):
        conn = sqlite3.connect(self.db)
        try:
            return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE name='prov_scores'").fetchone())
        finally:
            conn.close()


class JobTests(unittest.TestCase):
    def read(self, *path):
        with open(os.path.join(ROOT, *path), encoding="utf-8") as fh:
            return fh.read()

    def test_order_score_then_edition_then_archive_then_store(self):
        job = self.read("jobs", "prov-session-judge.sh")
        steps = [job.index(s) for s in ("bash tools/session_judge.sh tools/prov_triage.py",
                                        "python3 tools/prov_monitor.py --edition --date",
                                        "python3 tools/raw_state.py --push",
                                        "python3 tools/db_state.py --push")]
        self.assertEqual(steps, sorted(steps))
        self.assertIn("# mini_run: commit editions", job)
        self.assertNotIn("--dm", job)                              # the weekly already spoke
        # a gap (exit 3) leaves before anything is published
        self.assertLess(job.index('if [ "$jrc" -eq 3 ]'), job.index("raw_state.py --push"))
        self.assertIn('GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Provinces session judge}"', job)

    def test_its_heartbeat_is_its_own_and_on_demand(self):
        self.assertIn("Provinces session judge", coverage.ON_DEMAND)
        self.assertNotIn("Provinces session judge", coverage.PIPELINES)

    def test_mini_only_no_workflow(self):
        for path in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
            text = open(path, encoding="utf-8").read()
            self.assertNotIn("prov-session-judge", text, path)
            self.assertNotIn("Provinces session judge", text, path)

    def test_the_paid_judge_stays_gated_and_the_runner_never_uses_the_key(self):
        self.assertIn('if [ "$JUDGE" = "on" ]', self.read("jobs", "prov-weekly.sh"))
        runner = self.read("tools", "session_judge.sh")
        self.assertIn("unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN", runner)
        self.assertIn('d.get("authMethod") == "claude.ai"', runner)

    def test_the_plist_runs_after_the_weekly_and_starts_with_no_other_job(self):
        def slots(name):
            with open(os.path.join(ROOT, "ops", "launchd",
                                   "net.citizengo.parlmonitor.{0}.plist".format(name)), "rb") as fh:
                doc = plistlib.load(fh)
            s = doc["StartCalendarInterval"]
            return doc, s if isinstance(s, list) else [s]
        doc, mine = slots("prov-session-judge")
        self.assertEqual(doc["ProgramArguments"][-1], "prov-session-judge")
        self.assertTrue(doc["ProgramArguments"][1].startswith("/Users/christopherjoyce/runner/"))
        _, weekly = slots("prov-weekly")
        self.assertEqual({(s["Weekday"], s["Hour"], s["Minute"]) for s in mine}, {(3, 16, 15)})
        for s in mine:
            w = weekly[0]
            self.assertEqual(s["Weekday"], w["Weekday"])
            self.assertGreater((s["Hour"], s["Minute"]), (w["Hour"], w["Minute"]))
        for path in glob.glob(os.path.join(ROOT, "ops", "launchd", "*.plist")):
            if "prov-session-judge" in path:
                continue
            with open(path, "rb") as fh:
                theirs = plistlib.load(fh).get("StartCalendarInterval") or []
            for t in theirs if isinstance(theirs, list) else [theirs]:
                for s in mine:
                    if t.get("Weekday") in (None, s["Weekday"]):
                        self.assertNotEqual((t.get("Hour", 0), t.get("Minute", 0)),
                                            (s["Hour"], s["Minute"]), path)


if __name__ == "__main__":
    unittest.main()
