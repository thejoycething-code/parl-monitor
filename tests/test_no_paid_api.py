"""Paid AI off everywhere (Chris, 16 October 2026): "ALL model scoring moves
off the paid Claude API onto the free session judge".

What is held here:
  * a key present is never consent: every pass that ever spent runs its paid
    path only when its own flag (src/paid_ai.py) is exactly "1";
  * the two transports to api.anthropic.com refuse with no flag set, before
    any network call;
  * each judge's weekly entry point, with a key in the environment and no
    flag, sends nothing and leaves its rows UNSCORED for the session judge;
  * the German, EU and Canadian judges and the German stance pass speak the
    session-queue protocol tools/session_judge.sh drives (--queue-out /
    --queue-in), round trip, strictly;
  * no GitHub workflow carries the key or a paid flag (the backup runs are
    rules-only), and no job or plist sets a paid flag;
  * the new Mini job (europe-session-judge) and Canada's fold-in to the
    provinces' job are wired, slotted and heartbeat-ed.
"""

import glob
import importlib.util
import io
import json
import os
import plistlib
import re
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import ca_store, db, paid_ai, session_queue, stance, triage  # noqa: E402

FLAG_VARS = sorted(set(paid_ai.FLAGS.values()))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def keyed_env(**extra):
    """A key present, every paid flag absent: the case that must not spend."""
    env = {k: v for k, v in os.environ.items() if k not in FLAG_VARS}
    env["ANTHROPIC_API_KEY"] = "sk-ant-test-not-a-real-key"
    env.update(extra)
    return env


def no_network():
    """Patch every route to the API so any attempt fails the test."""
    boom = AssertionError("a paid call was attempted")
    return [mock.patch("urllib.request.urlopen", side_effect=boom),
            mock.patch.object(triage, "score_live", side_effect=boom),
            mock.patch.object(stance, "classify_batch", side_effect=boom)]


class FlagTests(unittest.TestCase):
    def test_a_key_alone_opts_nothing_in(self):
        env = keyed_env()
        for name in paid_ai.FLAGS:
            self.assertFalse(paid_ai.allowed(name, env), name)

    def test_only_exactly_one_opts_a_pass_in(self):
        for value, want in (("1", True), (" 1 ", True), ("on", False), ("true", False), ("0", False), ("", False)):
            self.assertEqual(paid_ai.allowed("de-triage", {"DE_TRIAGE_PAID": value}), want, value)

    def test_one_pass_opted_in_does_not_open_another(self):
        env = {"DE_TRIAGE_PAID": "1"}
        self.assertTrue(paid_ai.allowed("de-triage", env))
        for name in ("de-stance", "eu-triage", "ca-triage", "us-triage", "triage", "brief-narrative"):
            self.assertFalse(paid_ai.allowed(name, env), name)

    def test_every_recorded_pass_has_a_flag(self):
        """Every pass name the code records in api_spend is gated."""
        names = set()
        for path in glob.glob(os.path.join(ROOT, "tools", "*.py")) + glob.glob(os.path.join(ROOT, "src", "*.py")) \
                + [os.path.join(ROOT, "run_weekly.py")]:
            text = open(path, encoding="utf-8").read()
            names |= set(re.findall(r'spend\.record\(\s*conn,\s*"([a-z-]+)"', text))
            names |= set(re.findall(r'^PASS(?:_NAME)? = "([a-z-]+)"', text, re.M))
        self.assertTrue({"de-triage", "de-stance", "ca-triage", "eu-triage"} <= names, names)
        self.assertEqual(sorted(n for n in names if n not in paid_ai.FLAGS), [])


class TransportTests(unittest.TestCase):
    def test_both_transports_refuse_before_the_network(self):
        payload = {"model": "x", "max_tokens": 10, "messages": []}
        with mock.patch.dict(os.environ, keyed_env(), clear=True), \
                mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")) as net:
            for mod in (triage, stance):
                with self.assertRaises(paid_ai.PaidAIOff):
                    mod._default_transport(payload, "sk-ant-test")
            net.assert_not_called()

    def test_a_flag_lets_the_transport_through(self):
        paid_ai.check_transport({"EU_TRIAGE_PAID": "1"})       # no raise
        with self.assertRaises(paid_ai.PaidAIOff):
            paid_ai.check_transport({"ANTHROPIC_API_KEY": "sk"})

    def test_every_api_call_site_goes_through_a_guarded_transport(self):
        hits = []
        for path in glob.glob(os.path.join(ROOT, "**", "*.py"), recursive=True):
            if "/tests/" in path or "/data/" in path or "/.claude/" in path[len(ROOT):]:
                continue
            if "api.anthropic.com" in open(path, encoding="utf-8").read():
                hits.append(os.path.relpath(path, ROOT))
        self.assertEqual(sorted(hits), ["src/stance.py", "src/triage.py"])
        for rel in hits:
            text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
            body = text[text.index("def _default_transport"):]
            self.assertLess(body.index("paid_ai.check_transport()"), body.index("api.anthropic.com"), rel)


class _Store:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "t.db")
        self.conn = db.init_db(db.connect(self.path))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def run_main(self, mod, argv, env=None):
        out = io.StringIO()
        patches = no_network()
        with mock.patch.dict(os.environ, env or keyed_env(), clear=True), \
                mock.patch.object(sys, "argv", argv), redirect_stdout(out):
            for p in patches:
                p.start()
            try:
                rc = mod.main()
            finally:
                for p in patches:
                    p.stop()
        return rc, out.getvalue()


def fill(path, scores):
    """Fill a queue file's SCORE/WHY (or STANCE/WHY) lines as a session would."""
    text = open(path, encoding="utf-8").read()
    out, cur = [], None
    for line in text.split("\n"):
        m = re.match(r"^### item: (\S+)$", line)
        if m:
            cur = m.group(1)
        if cur in scores and line in ("SCORE: ", "STANCE: "):
            line = line + str(scores[cur])
        elif cur in scores and line == "WHY: ":
            line = "WHY: A test why-line for {0}.".format(cur)
        out.append(line)
    open(path, "w", encoding="utf-8").write("\n".join(out))


class GermanJudgeTests(_Store, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.mod = _load("de_triage")
        self.mod.ensure_columns(self.conn)
        for i, d in ((1, "2026-10-01"), (2, "2026-10-08")):
            self.conn.execute("INSERT INTO de_documents (doc_id, datum, titel, excerpt, areas, tier, first_seen, last_seen) "
                              "VALUES (?,?,?,?,?,?,'2026-10-08','2026-10-08')", ("d{0}".format(i), d, "Gesetz {0}".format(i),
                                                      "Schwangerschaftsabbruch", "[1]", 1))
        self.conn.commit()

    def test_a_key_alone_sends_nothing_and_leaves_rows_unscored(self):
        rc, out = self.run_main(self.mod, ["de_triage.py", "--db", self.path])
        self.assertEqual(rc, 0)
        self.assertIn("left for the free session judge", out)
        self.assertIn("DE_TRIAGE_PAID=1", out)
        n = self.conn.execute("SELECT COUNT(*) FROM de_documents WHERE triage_score IS NULL").fetchone()[0]
        self.assertEqual(n, 2)                    # never stub-scored

    def test_queue_round_trip_newest_first(self):
        q = os.path.join(self.tmp.name, "q.md")
        rc, out = self.run_main(self.mod, ["de_triage.py", "--db", self.path, "--queue-out", q, "--limit", "1"])
        self.assertIn("session queue: 1 item(s) written", out)
        body = open(q, encoding="utf-8").read()
        self.assertIn("<!-- de-session-queue v1 -->", body)
        self.assertIn("German parliamentary monitor", body)          # the German frame
        self.assertIn("### item: de_documents:d2", body)             # newest first
        self.assertNotIn("d1", body.split("---", 1)[1])
        fill(q, {"de_documents:d2": 3})
        rc, out = self.run_main(self.mod, ["de_triage.py", "--db", self.path, "--queue-in", q])
        self.assertEqual(rc, 0)
        self.assertIn("session queue: 1 item(s) scored", out)
        row = self.conn.execute("SELECT triage_score, why_it_matters FROM de_documents WHERE doc_id='d2'").fetchone()
        self.assertEqual(row[0], 3)
        self.assertIn("test why-line", row[1])
        banked = self.conn.execute("SELECT mode FROM judge_verdicts WHERE item_id='de_documents:d2'").fetchone()
        self.assertEqual(banked[0], "session")
        # once ever: the same file applied again is refused, not rewritten
        rc, out = self.run_main(self.mod, ["de_triage.py", "--db", self.path, "--queue-in", q])
        self.assertIn("already scored", out)

    def test_another_judges_queue_is_refused_whole(self):
        q = os.path.join(self.tmp.name, "q.md")
        open(q, "w").write("# x\n<!-- eu-session-queue v1 -->\n### item: de_documents:d2\nSCORE: 3\nWHY: x\n")
        rc, out = self.run_main(self.mod, ["de_triage.py", "--db", self.path, "--queue-in", q])
        self.assertEqual(rc, 1)
        self.assertIsNone(self.conn.execute("SELECT triage_score FROM de_documents WHERE doc_id='d2'").fetchone()[0])

    def test_the_paid_path_needs_its_own_flag(self):
        with mock.patch.object(self.mod.triage, "score_live", return_value=[]) as live, \
                mock.patch.dict(os.environ, keyed_env(DE_TRIAGE_PAID="1"), clear=True), \
                mock.patch.object(sys, "argv", ["de_triage.py", "--db", self.path]), redirect_stdout(io.StringIO()):
            self.mod.main()
        self.assertTrue(live.called)


class GermanStanceTests(_Store, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.mod = _load("de_stance")
        area = stance.positioned([1, 2, 3, 4, 5, 6, 7, 8])[0]
        for i, d in ((1, "2026-10-01"), (2, "2026-10-08")):
            self.conn.execute("INSERT INTO de_speeches (speech_id, date, speaker, party, role, text, excerpt, areas, "
                              "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,'2026-10-08','2026-10-08')", ("s{0}".format(i), d, "Abg. {0}".format(i), "CDU", "member",
                                                          "Eine lange Rede. " * 20, "Rede", json.dumps([area])))
        self.conn.commit()

    def test_a_key_alone_sends_nothing(self):
        rc, out = self.run_main(self.mod, ["de_stance.py", "--db", self.path, "--limit", "40"])
        self.assertEqual(rc, 0)
        self.assertIn("DE_STANCE_PAID=1", out)
        stance.ensure_table(self.conn)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM stance").fetchone()[0], 0)

    def test_queue_round_trip(self):
        q = os.path.join(self.tmp.name, "q.md")
        rc, out = self.run_main(self.mod, ["de_stance.py", "--db", self.path, "--queue-out", q, "--limit", "5"])
        self.assertIn("session queue: 2 item(s) written", out)
        body = open(q, encoding="utf-8").read()
        self.assertIn("<!-- de-stance-session-queue v1 -->", body)
        self.assertLess(body.index("de-speech:s2"), body.index("de-speech:s1"))     # newest first
        fill(q, {"de-speech:s2": -2, "de-speech:s1": "7"})
        rc, out = self.run_main(self.mod, ["de_stance.py", "--db", self.path, "--queue-in", q])
        self.assertIn("session queue: 1 item(s) scored, 1 refused", out)            # 7 is off the gradient
        row = self.conn.execute("SELECT stance, model FROM stance WHERE ref='de-speech:s2'").fetchone()
        self.assertEqual((row[0], row[1]), (-2, "claude-code-session"))

    def test_the_uk_stance_queue_is_refused(self):
        q = os.path.join(self.tmp.name, "q.md")
        open(q, "w").write("# x\n<!-- uk-stance-session-queue v1 -->\n### item: de-speech:s2\nSTANCE: 1\nWHY: x\n")
        rc, out = self.run_main(self.mod, ["de_stance.py", "--db", self.path, "--queue-in", q])
        self.assertEqual(rc, 1)


class EUJudgeTests(_Store, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.mod = _load("eu_triage")
        self.mod.ensure_columns(self.conn)
        self.conn.execute("INSERT INTO eu_texts (identifier, date, title, excerpt, areas, tier, first_seen, last_seen) "
                          "VALUES ('T10-1', '2026-10-08', 'Resolution', 'surrogacy', '[1]', 1, '2026-10-08', '2026-10-08')")
        self.conn.commit()

    def test_a_key_alone_sends_nothing_and_never_stubs(self):
        rc, out = self.run_main(self.mod, ["eu_triage.py", "--db", self.path])
        self.assertEqual(rc, 0)
        self.assertIn("EU_TRIAGE_PAID=1", out)
        self.assertIsNone(self.conn.execute("SELECT triage_score FROM eu_texts").fetchone()[0])

    def test_no_key_and_no_flag_never_stubs_either(self):
        env = keyed_env()
        del env["ANTHROPIC_API_KEY"]
        rc, out = self.run_main(self.mod, ["eu_triage.py", "--db", self.path], env=env)
        self.assertIsNone(self.conn.execute("SELECT triage_score FROM eu_texts").fetchone()[0])

    def test_queue_round_trip(self):
        q = os.path.join(self.tmp.name, "q.md")
        rc, out = self.run_main(self.mod, ["eu_triage.py", "--db", self.path, "--queue-out", q, "--limit", "25"])
        self.assertIn("session queue: 1 item(s) written", out)
        self.assertIn("<!-- eu-session-queue v1 -->", open(q, encoding="utf-8").read())
        fill(q, {"eu_texts:T10-1": 2})
        rc, out = self.run_main(self.mod, ["eu_triage.py", "--db", self.path, "--queue-in", q])
        self.assertIn("session queue: 1 item(s) scored", out)
        self.assertEqual(self.conn.execute("SELECT triage_score FROM eu_texts").fetchone()[0], 2)


class CanadaJudgeTests(_Store, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.mod = _load("ca_triage")
        ca_store.ensure_schema(self.conn)
        self.conn.execute("INSERT INTO ca_petitions (petition_id, category, keywords, prayer, presented, areas, tier) "
                          "VALUES ('e-1', 'Health', '[\"euthanasia\"]', 'We call on...', '2026-10-08', '[2]', 1)")
        self.conn.commit()

    def test_a_key_alone_sends_nothing(self):
        rc, out = self.run_main(self.mod, ["ca_triage.py", "--db", self.path])
        self.assertEqual(rc, 0)
        self.assertIn("CA_TRIAGE_PAID=1", out)
        self.assertIsNone(self.conn.execute("SELECT triage_score FROM ca_petitions").fetchone()[0])

    def test_queue_round_trip_carries_both_frames(self):
        q = os.path.join(self.tmp.name, "q.md")
        self.run_main(self.mod, ["ca_triage.py", "--db", self.path, "--queue-out", q, "--limit", "25"])
        body = open(q, encoding="utf-8").read()
        self.assertIn("<!-- ca-session-queue v1 -->", body)
        self.assertIn("ca_petitions: use THIS frame", body)
        self.assertIn("ca_judgments: use THIS frame instead", body)
        fill(q, {"ca_petitions:e-1": 2})
        rc, out = self.run_main(self.mod, ["ca_triage.py", "--db", self.path, "--queue-in", q])
        self.assertIn("session queue: 1 item(s) scored", out)
        self.assertEqual(self.conn.execute("SELECT triage_score FROM ca_petitions").fetchone()[0], 2)


class TheOtherJudgesTests(unittest.TestCase):
    """US, Ireland, Australia, provinces: the repository variable alone no
    longer reaches the paid path; each needs its own flag too."""

    def test_each_needs_its_flag(self):
        item = triage.TriageItem(id="x:1", title="t", text="t", tier=1, issue_areas=[1], watchlist_hit=False)
        for cc in ("us", "ie", "au", "prov"):
            mod = _load(cc + "_triage")
            with tempfile.TemporaryDirectory() as tmp:
                out = io.StringIO()
                patches = no_network() + [mock.patch.object(mod, "pending", return_value=[item] * 3)]
                for p in patches:
                    p.start()
                try:
                    with mock.patch.dict(os.environ, keyed_env(**{cc.upper() + "_JUDGE": "on"}), clear=True), \
                            mock.patch.object(sys, "argv", [cc, "--db", os.path.join(tmp, "t.db")]), \
                            redirect_stdout(out):
                        self.assertEqual(mod.main(), 0, cc)
                finally:
                    for p in patches:
                        p.stop()
                self.assertIn("{0}_TRIAGE_PAID=1".format(cc.upper()), out.getvalue(), cc)


class DraftingAndHandToolsTests(unittest.TestCase):
    def test_brief_narratives_are_not_drafted_with_a_key_alone(self):
        mb = _load("make_briefs")
        subject = {"title": "t", "kind": "bill", "area_labels": []}
        with mock.patch.dict(os.environ, keyed_env(), clear=True), \
                mock.patch.object(mb.stance, "_default_transport", side_effect=AssertionError("paid")):
            self.assertIsNone(mb.draft_narrative(subject, {}, "sk-ant-test"))

    def test_hand_tools_check_their_flags(self):
        for rel, name in (("tools/pick_speeches.py", "speech-pick"), ("tools/debate_report.py", "debate-report"),
                          ("tools/debate_pack.py", "debate-pack"), ("tools/judge_eval.py", "judge-rescore"),
                          ("tools/score_stance.py", "stance-rescore"),
                          ("tools/rescore_blind_speeches.py", "stance-rescore"),
                          ("tools/make_briefs.py", "brief-narrative"), ("tools/de_briefs.py", "brief-narrative")):
            text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
            self.assertIn('paid_ai.allowed("{0}")'.format(name), text, rel)


class GitHubIsRulesOnlyTests(unittest.TestCase):
    def test_no_workflow_carries_the_key_or_a_paid_flag(self):
        for path in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
            text = "\n".join(l for l in open(path, encoding="utf-8").read().split("\n")
                              if not l.strip().startswith("#"))
            self.assertNotIn("secrets.ANTHROPIC_API_KEY", text, path)
            self.assertNotIn("anthropic_api_key:", text, path)
            for var in FLAG_VARS:
                self.assertNotIn(var, text, path)

    def test_no_job_or_plist_sets_a_paid_flag(self):
        paths = glob.glob(os.path.join(ROOT, "jobs", "*.sh")) + glob.glob(os.path.join(ROOT, "tools", "*.sh")) \
            + glob.glob(os.path.join(ROOT, "ops", "launchd", "*.plist"))
        for path in paths:
            for line in open(path, encoding="utf-8").read().split("\n"):
                code = line.split("#", 1)[0] if path.endswith(".sh") else line
                if path.endswith(".plist") and ("<!--" in line or line.startswith("     ")):
                    continue
                for var in FLAG_VARS:
                    self.assertNotIn(var, code, "{0}: {1}".format(path, line))


def plist_slots(name):
    with open(os.path.join(ROOT, "ops", "launchd", "net.citizengo.parlmonitor.{0}.plist".format(name)), "rb") as fh:
        doc = plistlib.load(fh)
    s = doc["StartCalendarInterval"]
    return doc, s if isinstance(s, list) else [s]


class MiniJobTests(unittest.TestCase):
    def read(self, *path):
        with open(os.path.join(ROOT, *path), encoding="utf-8") as fh:
            return fh.read()

    def test_europe_job_order(self):
        job = self.read("jobs", "europe-session-judge.sh")
        steps = [job.index(s) for s in ("bash tools/session_judge.sh tools/de_triage.py",
                                        'if [ "$jrc" -eq 3 ]',
                                        "bash tools/session_judge.sh tools/eu_triage.py",
                                        "bash tools/session_judge.sh tools/de_stance.py",
                                        "render_edition",
                                        "python3 tools/raw_state.py --push",
                                        "python3 tools/db_state.py --push")]
        self.assertEqual(steps, sorted(steps))
        self.assertIn("uk_stance_judge as s; print(s.STANCE_PROMPT)", job)
        self.assertIn('GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Europe session judge}"', job)
        self.assertIn("# mini_run: commit editions", job)
        self.assertNotIn("--dm", job)
        self.assertTrue(os.access(os.path.join(ROOT, "jobs", "europe-session-judge.sh"), os.X_OK))

    def test_europe_job_heartbeat_and_no_workflow(self):
        import coverage
        self.assertIn("Europe session judge", coverage.ON_DEMAND)
        for path in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
            text = open(path, encoding="utf-8").read()
            self.assertNotIn("europe-session-judge", text, path)

    def test_europe_slot_after_both_weeklies(self):
        doc, mine = plist_slots("europe-session-judge")
        self.assertEqual(doc["ProgramArguments"][-1], "europe-session-judge")
        self.assertEqual({(s["Weekday"], s["Hour"], s["Minute"]) for s in mine}, {(1, 14, 30)})
        # clear of the protected slots
        for name, slot in (("un-weekday", (1, 8, 30)), ("uk-session-judge", (0, 12, 30)),
                           ("editions-session-judge", (0, 16, 45))):
            self.assertNotIn(slot, {(s["Weekday"], s["Hour"], s["Minute"]) for s in mine}, name)

    def test_canada_federal_rides_the_provinces_job(self):
        job = self.read("jobs", "prov-session-judge.sh")
        steps = [job.index(s) for s in ("bash tools/session_judge.sh tools/prov_triage.py",
                                        'if [ "$jrc" -eq 3 ]',
                                        "bash tools/session_judge.sh tools/ca_triage.py",
                                        "python3 tools/ca_monitor.py --edition --date",
                                        "python3 tools/db_state.py --push")]
        self.assertEqual(steps, sorted(steps))
        self.assertGreaterEqual(int(plist_slots("prov-session-judge")[0]["EnvironmentVariables"]["JOB_TIMEOUT"]),
                                7200)

    def test_weeklies_no_longer_promise_spend(self):
        for job in ("de-weekly", "eu-weekly", "ca-weekly"):
            self.assertNotIn("Triage spends", self.read("jobs", job + ".sh"), job)
            self.assertNotIn("Triage and stance spend", self.read("jobs", job + ".sh"), job)


if __name__ == "__main__":
    unittest.main()
