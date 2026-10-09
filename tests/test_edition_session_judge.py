"""The editions session judge (10 October 2026): one generic queue for the
fifteen country editions and the Latam monitor (tools/edition_judge.py
--queue-out / --queue-in / --rerender, src/edition_judge.py), the scores in
the editions, the Latam alert gate and hold, the runner
(tools/session_judge.sh, with a FAKE claude: nothing here calls a model),
the Mini job and its plist. No network, no spend."""

import glob
import json
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

from src import country_edition as ce, edition_judge as ej, session_queue as sq  # noqa: E402
import coverage  # noqa: E402
import edition_judge as tj  # noqa: E402
import latam_alerts  # noqa: E402
import latam_monitor  # noqa: E402
import test_country_edition as tce  # noqa: E402
import test_latam_monitor as tlm  # noqa: E402
from test_prov_session_judge import FAKE_CLAUDE, fill  # noqa: E402

TODAY = tce.TODAY
MARK = tj.QUEUE_MARKER
VOTE = "at:vote:XXVIII/I/525@XXVIII/NRSITZ/87#210+2"
QUESTION = "at:question:XXVIII/J/1"


EDITION_SCORES = ("CREATE TABLE edition_scores (item TEXT PRIMARY KEY, cc TEXT NOT NULL, "
                  "score INTEGER NOT NULL, why TEXT, model TEXT, scored_at TEXT)")


def slurp(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def score(conn, iid, s, why="Why.", today=TODAY, model=ej.SESSION_MODEL):
    ej.write(conn, iid.split(":", 1)[0], iid, s, why, today, model)
    conn.commit()


class Austria(tce.AustriaTests):
    """The Austrian fixture store of tests/test_country_edition.py, with the
    edition_scores table and a tier-1 question that is not watched."""

    def setUp(self):
        super().setUp()
        self.conn.execute(EDITION_SCORES)       # as src/db.py declares it
        self.path = os.path.join(self.tmp, "q.md")

    def test_one_floor_vote_once_with_derived_members(self):     # the parent's, not rerun
        pass

    def pending(self):
        return [ej.item_id(it) for it in tj.pending(self.conn, TODAY, self.cfg, self.eds)]

    def ids(self):
        return re.findall(r"^### item: (\S+)$", slurp(self.path), re.M)

    def qout(self, limit=25):
        return tj.queue_out(self.conn, self.path, TODAY, limit, self.cfg, self.eds,
                            log=lambda *_: None)

    def qin(self, log=None):
        return tj.queue_in(self.conn, self.path, TODAY, self.cfg, self.eds,
                           log=log or (lambda *_: None))


class QueueTests(Austria):
    def test_queue_out_then_in_once_ever(self):
        n, rest = self.qout()
        self.assertEqual((n, rest), (4, 0))
        ids = self.ids()
        self.assertEqual(ids, self.pending())
        text = slurp(self.path)
        self.assertIn(MARK, text.splitlines()[:5])
        self.assertIn("fifteen weekly editions", text)                    # the frame
        self.assertIn("Country: Austria, Nationalrat and Bundesrat (titles in German).", text)
        self.assertIn("- title: Sterbeverfügungsgesetz-Novelle 2026", text)  # source's words
        self.assertIn("Watched by CitizenGO: Sterbeverfügungsgesetz-Novelle 2026", text)
        self.assertIn("Not on the watchlist.", text)
        fill(self.path, {i: (2, "Matters.") for i in ids})
        self.assertEqual(self.qin(), (4, 0, 0))
        rows = self.conn.execute("SELECT item, cc, score, why, model, scored_at FROM "
                                 "edition_scores").fetchall()
        self.assertEqual({r[0] for r in rows}, set(ids))
        self.assertTrue(all(tuple(r)[1:] == ("at", 2, "Matters.", "claude-code-session", TODAY)
                            for r in rows))
        self.assertEqual(self.pending(), [])
        logs = []
        self.assertEqual(self.qin(logs.append)[0], 0)                     # once ever
        self.assertTrue(any("already scored" in x for x in logs))

    def test_priority_watched_then_tier1_then_tier2_and_a_limit(self):
        ids = self.pending()
        self.assertEqual(ids[-1], QUESTION)                               # not watched: last
        self.assertEqual(self.qout(limit=1), (1, 3))
        self.assertEqual(self.ids(), ids[:1])

    def test_a_vote_group_is_offered_once_and_its_score_holds_for_the_group(self):
        from src import at_store  # noqa: F401
        self.conn.execute("INSERT INTO at_divisions (division_key, item_key, date, body, question, "
                          "outcome, areas) VALUES (?,?,?,?,?,?,?)",
                          ("XXVIII/I/525@XXVIII/NRSITZ/86#1", "XXVIII/I/525", "2026-10-06", "NR",
                           "Antrag auf Rückverweisung", "abgelehnt", "[2]"))
        got = [i for i in self.pending() if i.startswith("at:vote:")]
        self.assertEqual(len(got), 1)
        score(self.conn, got[0], 3, "A trigger.")
        self.assertFalse([i for i in self.pending() if i.startswith("at:vote:")])
        items = ce.gather(self.conn, ce.adapter("at"), tce.SINCE, TODAY, self.cfg)
        votes = [it for it in items if it["kind"] == "vote"]
        self.assertTrue(votes and all(v["judge"] == 3 for v in votes))

    def test_unknown_and_malformed_ids_are_refused_and_good_ones_applied(self):
        self.qout()
        fill(self.path, {QUESTION: (1, "Background."), VOTE: (7, "x")})
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write("### item: at:new:NOPE\nSCORE: 2\nWHY: x\n"
                     "### item: prov_bills:ab-1\nSCORE: 2\nWHY: x\n")
        logs = []
        self.assertEqual(self.qin(logs.append), (1, 3, 2))
        self.assertEqual(sum("not a pending edition item" in x for x in logs), 2)
        self.assertTrue(any("not one digit 0-3" in x for x in logs))

    def test_another_judges_file_is_refused_whole(self):
        sq.write_queue(self.path, [], "T", "<!-- prov-session-queue v1 -->", "frame")
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write("### item: {0}\nSCORE: 2\nWHY: x\n".format(QUESTION))
        self.assertIsNone(self.qin())
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM edition_scores").fetchone()[0], 0)

    def test_a_muted_item_is_not_queued(self):
        self.write("edition-noise-at.yaml", "exclude_titles: ['schwangerschaftsabbruch']\n")
        self.assertNotIn(QUESTION, self.pending())


class RenderTests(Austria):
    def render(self):
        return ce.render(self.conn, ce.adapter("at"), TODAY, tce.SINCE, config_dir=self.cfg,
                         directory=self.eds)

    def test_unscored_renders_as_before(self):
        before = self.render()
        self.assertIn("The AI judge is off (X16)", before)
        self.assertNotIn("_Judge", before)
        score(self.conn, "es:new:other", 3)                  # another country's score: no change
        self.assertEqual(self.render(), before)

    def test_scores_show_order_and_lead(self):
        before = self.render()
        self.assertIn("Anfrage zum Schwangerschaftsabbruch", leading_block(before))  # tier 1
        score(self.conn, QUESTION, 1, "Background: a routine statistics question.")
        text = self.render()
        self.assertIn("_Judge 1/3: Background: a routine statistics question._", text)
        self.assertIn("read for relevance by the free session judge", text)
        self.assertNotIn("Anfrage zum Schwangerschaftsabbruch", leading_block(text))
        self.assertIn("Anfrage zum Schwangerschaftsabbruch", text)        # still shown
        self.assertNotIn("—", text)
        dm = ce.dm_summary(self.conn, ce.adapter("at"), TODAY, tce.SINCE, config_dir=self.cfg,
                           directory=self.eds)
        self.assertIn("session judge's scores", dm)

    def test_a_zero_leaves_the_edition_and_is_counted_but_never_a_watched_item(self):
        score(self.conn, QUESTION, 0, "Unrelated.")
        score(self.conn, "at:new:XXVIII/AA/78", 0, "Unrelated.")      # watched: stays
        text = self.render()
        self.assertNotIn("Anfrage zum Schwangerschaftsabbruch", text)
        self.assertIn("1 item the judge scored 0", text)
        self.assertIn("XXVIII/AA/78", text)

    def test_rerender_rewrites_in_place_and_reports_a_changed_lead(self):
        path = ce.edition_path("at", TODAY, self.eds)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.render() + "\n")
        self.assertEqual(tj.rerender(self.conn, TODAY, {"at"}, self.eds, self.cfg,
                                     log=lambda *_: None), [])
        self.assertIsNone(tj.update_dm([]))
        score(self.conn, QUESTION, 1, "Background.")
        self.assertEqual(tj.scored_on(self.conn, TODAY), {"at"})
        changed = tj.rerender(self.conn, TODAY, None, self.eds, self.cfg, log=lambda *_: None)
        self.assertEqual([c[0] for c in changed], ["Austria"])
        self.assertIn("_Judge 1/3: Background._", slurp(path))
        dm = tj.update_dm(changed)
        self.assertIn("*Country editions, re-scored*", dm)
        self.assertIn("editions/", dm)
        self.assertNotIn("Anfrage", dm)
        self.assertIn("_Sterbeverfügungsgesetz-Novelle 2026_", dm)
        self.assertNotIn("—", dm)

    def test_an_old_edition_is_history(self):
        old = ce.edition_path("at", "2026-09-20", self.eds)
        with open(old, "w", encoding="utf-8") as fh:
            fh.write("# old\n")
        score(self.conn, QUESTION, 3)
        tj.rerender(self.conn, TODAY, {"at"}, self.eds, self.cfg, log=lambda *_: None)
        self.assertEqual(slurp(old), "# old\n")


def leading_block(text):
    return "\n".join(tj.leading(text))


class LatamTests(tlm.Fixture):
    """The Latam edition, and the alert gate and hold, on the Latam fixture."""
    PEDIDO = "uy:pedido:L50/07799"           # tier 1, not watched
    WATCHED = "co:new:camara/2026/114"

    def run_pass(self, today=tlm.TODAY):
        self.sent = []
        return latam_alerts.run(self.conn, ["co", "uy"], today, 30, True, 8,
                                lambda t: self.sent.append(t) or {"ok": True}, self.ledgers,
                                self.cfg, log=lambda *a: None)

    def seeded(self):
        self.run_pass()
        for name in os.listdir(self.ledgers):
            path = os.path.join(self.ledgers, name)
            with open(path) as fh:
                ledger = json.load(fh)
            ledger["sent"] = {}
            with open(path, "w") as fh:
                json.dump(ledger, fh)

    def keys(self, got):
        return {k for _, k, _ in got}

    def test_the_latam_items_are_in_the_shared_queue(self):
        got = [ej.item_id(it) for it in tj.pending(self.conn, tlm.TODAY, self.cfg)]
        self.assertIn(self.PEDIDO, got)
        self.assertIn(self.WATCHED, got)
        self.assertLess(got.index(self.WATCHED), got.index(self.PEDIDO))   # watched first

    def test_scores_in_the_edition(self):
        score(self.conn, self.PEDIDO, 0, "Unrelated.", tlm.TODAY)
        score(self.conn, self.WATCHED, 0, "Unrelated.", tlm.TODAY)
        text = latam_monitor.render_edition(self.conn, tlm.TODAY, tlm.SINCE,
                                            ledger={"moves": []}, config_dir=self.cfg)
        self.assertNotIn("BLOQUEO PUBERAL", text)
        self.assertIn("Uruguay 1 (1 item the judge scored 0)", text)
        self.assertIn("VIDA DESDE LA FECUNDACIÓN", text)              # watched: stays
        self.assertIn("_Judge 0/3: Unrelated._", text)
        self.assertIn("**The session judge.**", text)

    def test_unscored_and_judge_not_running_alerts_as_before(self):
        self.seeded()
        self.assertEqual(self.keys(self.run_pass()),
                         {"co|new|camara/2026/114", "uy|pedido|L50/07799"})

    def test_a_judged_tier1_item_alerts_only_at_2_or_3(self):
        self.seeded()
        score(self.conn, self.PEDIDO, 1, "Background.", tlm.TODAY)
        score(self.conn, self.WATCHED, 1, "Background.", tlm.TODAY)
        self.assertEqual(self.keys(self.run_pass()), {"co|new|camara/2026/114"})  # watched always
        self.conn.execute("DELETE FROM edition_scores WHERE item=?", (self.PEDIDO,))
        score(self.conn, self.PEDIDO, 3, "Puberty blockers for minors.", tlm.TODAY)
        self.assertEqual(self.keys(self.run_pass()), {"uy|pedido|L50/07799"})

    def test_held_for_a_running_judge_then_released(self):
        self.seeded()
        score(self.conn, "co:new:other", 2, "x", tlm.TODAY)                # the judge is running
        self.assertEqual(self.keys(self.run_pass()), {"co|new|camara/2026/114"})
        with open(os.path.join(self.ledgers, "uy.json")) as fh:
            self.assertEqual(json.load(fh)["held"], {"uy|pedido|L50/07799": tlm.TODAY})
        # the judge scores it 2: the next pass (the judge's job) sends it
        score(self.conn, self.PEDIDO, 2, "Puberty blockers for minors.", tlm.TODAY)
        self.assertEqual(self.keys(self.run_pass("2026-10-11")), {"uy|pedido|L50/07799"})
        with open(os.path.join(self.ledgers, "uy.json")) as fh:
            self.assertEqual(json.load(fh)["held"], {})

    def test_a_held_item_the_judge_never_reads_goes_out_after_the_hold(self):
        self.seeded()
        score(self.conn, "co:new:other", 2, "x", tlm.TODAY)
        self.run_pass()
        self.assertEqual(self.keys(self.run_pass("2026-10-16")), set())    # 7 days: still held
        score(self.conn, "co:new:other2", 2, "x", "2026-10-17")           # still running
        self.assertEqual(self.keys(self.run_pass("2026-10-17")), {"uy|pedido|L50/07799"})


class RunnerTests(unittest.TestCase):
    """tools/session_judge.sh with tools/edition_judge.py and a fake claude."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = os.path.join(self.tmp.name, "bin")
        os.makedirs(self.bin)
        self.db = os.path.join(self.tmp.name, "store.db")
        base = tlm.Fixture("setUp")
        base.setUp()
        disk = sqlite3.connect(self.db)
        base.conn.backup(disk)
        disk.close()
        base.tearDown()
        self.log = os.path.join(self.tmp.name, "fake")
        path = os.path.join(self.bin, "claude")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(FAKE_CLAUDE % {"logged": "true", "method": "claude.ai"})
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)

    def tearDown(self):
        self.tmp.cleanup()

    def test_scores_round_by_round_within_the_cap_and_never_with_the_key(self):
        env = dict(os.environ, FAKE_LOG=self.log, ANTHROPIC_API_KEY="sk-must-not-leak",
                   PATH=":".join([self.bin, os.path.dirname(sys.executable), "/usr/bin", "/bin"]))
        p = subprocess.run(
            ["bash", os.path.join(ROOT, "tools", "session_judge.sh"), "tools/edition_judge.py",
             "3", "2", "--db", self.db, "--date", tlm.TODAY],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("session judge: 3 item(s) scored this run", p.stdout)
        self.assertIn("round 2: 1 item(s) to claude", p.stdout)
        conn = sqlite3.connect(self.db)
        got = conn.execute("SELECT score, model FROM edition_scores").fetchall()
        conn.close()
        self.assertEqual(got, [(2, "claude-code-session")] * 3)
        self.assertNotIn("ANTHROPIC_API_KEY", slurp(self.log + ".env"))


class JobTests(unittest.TestCase):
    JOB = "editions-session-judge"

    def read(self, *path):
        with open(os.path.join(ROOT, *path), encoding="utf-8") as fh:
            return fh.read()

    def test_order_score_rewrite_alerts_archive_store(self):
        job = self.read("jobs", self.JOB + ".sh")
        steps = [job.index(s) for s in ("bash tools/session_judge.sh tools/edition_judge.py",
                                        "python3 tools/edition_judge.py --rerender --dm",
                                        "python3 tools/latam_alerts.py --send",
                                        "python3 tools/raw_state.py --push",
                                        "python3 tools/db_state.py --push")]
        self.assertEqual(steps, sorted(steps))
        self.assertIn('"${SESSION_JUDGE_MAX:-100}" 25', job)
        self.assertIn("# mini_run: commit editions", job)
        self.assertLess(job.index('if [ "$jrc" -eq 3 ]'), job.index("--rerender"))
        self.assertIn('GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Editions session judge}"', job)
        self.assertNotIn("ANTHROPIC_API_KEY", job)

    def test_heartbeat_on_demand_and_installed_with_the_country_jobs(self):
        self.assertIn("Editions session judge", coverage.ON_DEMAND)
        self.assertNotIn("Editions session judge", coverage.PIPELINES)
        self.assertIn(self.JOB, self.read("ops", "install_country_jobs.sh"))

    def test_mini_only_no_workflow(self):
        for path in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
            text = slurp(path)
            self.assertNotIn(self.JOB, text, path)
            self.assertNotIn("edition_judge.py", text, path)

    def test_the_slot_follows_every_country_weekly_and_starts_with_no_other_job(self):
        def slots(path):
            with open(path, "rb") as fh:
                doc = plistlib.load(fh)
            s = doc.get("StartCalendarInterval") or []
            return doc, s if isinstance(s, list) else [s]
        lpath = os.path.join(ROOT, "ops", "launchd", "net.citizengo.parlmonitor.{0}.plist")
        doc, mine = slots(lpath.format(self.JOB))
        self.assertEqual(doc["ProgramArguments"][-1], self.JOB)
        self.assertTrue(doc["ProgramArguments"][1].startswith("/Users/christopherjoyce/runner/"))
        self.assertEqual([(s["Weekday"], s["Hour"], s["Minute"]) for s in mine], [(0, 16, 45)])
        week = lambda s: (s["Weekday"] or 7, s["Hour"], s["Minute"])  # noqa: E731  Sunday last
        for cc in ej.EDITION_CCS + tuple(c for c in ej.LATAM_CCS if c not in ("ve", "nic")):
            path = lpath.format(cc + "-weekly")
            if not os.path.exists(path):
                continue
            for s in slots(path)[1]:
                self.assertLess(week(s), week(mine[0]), path)
        for path in glob.glob(os.path.join(ROOT, "ops", "launchd", "*.plist")):
            if self.JOB in path:
                continue
            for t in slots(path)[1]:
                if t.get("Weekday") in (None, 0):
                    self.assertNotEqual((t.get("Hour", 0), t.get("Minute", 0)), (16, 45), path)

    def test_provinces_untouched(self):
        self.assertIn("bash tools/session_judge.sh tools/prov_triage.py",
                      self.read("jobs", "prov-session-judge.sh"))


if __name__ == "__main__":
    unittest.main()
