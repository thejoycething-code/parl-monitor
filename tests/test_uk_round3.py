"""Round 3 of the UK countdown (Chris, 16 October 2026): the sitting-days
line, paid AI off for the UK weekly (the free session judge instead), the
Holyrood question summaries, the JOINT COMMITTEE tag, and petitions and
gov.uk documents read from uk_petitions / govuk_docs. Fixtures only: no
network, and no model is ever called."""

import datetime
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import countdown as cd, db, digest, filter as filt, sitting_days as sd, stance, triage  # noqa: E402

WEEK = "2026-10-19"
WATCHLIST = os.path.join(ROOT, "config", "watchlist.yaml")


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return conn


# -- A: the sitting-days line ------------------------------------------------------

WESTMINSTER = [
    {"StartDate": "2026-09-16T00:00:00", "EndDate": "2026-10-11T00:00:00", "Category": "Recess - Commons",
     "House": "Commons", "Description": None},
    {"StartDate": "2026-09-18T00:00:00", "EndDate": "2026-10-11T00:00:00", "Category": "Recess - Lords",
     "House": "Lords", "Description": None},
    {"StartDate": "2026-10-23T00:00:00", "EndDate": "2026-10-23T00:00:00",
     "Category": "Non-sitting Friday - Commons", "House": "Commons", "Description": None},
    {"StartDate": "2026-11-05T00:00:00", "EndDate": "2026-11-09T00:00:00", "Category": "Recess - Commons",
     "House": "Commons", "Description": None},
    {"StartDate": "2026-11-05T00:00:00", "EndDate": "2026-11-06T00:00:00", "Category": "Recess - Lords",
     "House": "Lords", "Description": None},
]
HOLYROOD = [
    {"EventID": "S7M-00153", "SubmissionDateTime": "2026-05-26T12:34:49", "Title": "Parliamentary Recess Dates",
     "ItemText": "That the Parliament agrees the following parliamentary recess dates under Rule 2.3.1: "
                 "27 June to 30 August 2026 (inclusive), 10 to 25 October 2026 (inclusive), 19 December "
                 "2026 to 3 January 2027 (inclusive)."},
    {"EventID": "S6M-13045", "SubmissionDateTime": "2024-04-30T12:26:42", "Title": "Parliamentary Recess Dates",
     "ItemText": "That the Parliament agrees the following parliamentary recess dates under Rule 2.3.1: "
                 "11 to 26 October 2025 (inclusive)."},
    {"EventID": "S7M-00999", "SubmissionDateTime": "2026-06-01T00:00:00", "Title": "Business Programme",
     "ItemText": "That the Parliament agrees the following programme of business 10 to 25 October 2026"},
]
SENEDD = """<?xml version="1.0"?><meetings>
<meeting><meetingid>16317</meetingid><meetingdate>20/10/2026</meetingdate><meetingstatus>Confirmed</meetingstatus></meeting>
<meeting><meetingid>16318</meetingid><meetingdate>21/10/2026</meetingdate><meetingstatus>Confirmed</meetingstatus></meeting>
<meeting><meetingid>16399</meetingid><meetingdate>22/10/2026</meetingdate><meetingstatus>Cancelled</meetingstatus></meeting>
<meeting><meetingid>16420</meetingid><meetingdate>03/11/2026</meetingdate><meetingstatus>Confirmed</meetingstatus></meeting>
</meetings>"""
NI_PAGE = ("<h1>Recess Dates</h1><p>The Business Committee has agreed the following recess dates for 2026/27:"
           "</p><p><strong>Summer 2026</strong></p><p>4 July 2026 to 30 August 2026</p>"
           "<p><strong>Halloween 2026</strong></p><p>24 October 2026 to 1 November 2026</p>"
           "<p><strong>Christmas 2026</strong></p><p>12 December 2026 to 3 January 2027</p>"
           "<p><strong>Easter 2027</strong></p><p>20 March 2027 to dissolution</p>")


class FakeClient:
    def __init__(self, fail=()):
        self.fail = set(fail)
        self.urls = []

    def _check(self, url):
        self.urls.append(url)
        for f in self.fail:
            if f in url:
                raise RuntimeError("HTTP 503")

    def get_json(self, url, *a, **k):
        self._check(url)
        return WESTMINSTER if "whatson" in url else HOLYROOD

    def get_text(self, url, *a, **k):
        self._check(url)
        return SENEDD if "senedd" in url else NI_PAGE


class SittingDaysTests(unittest.TestCase):
    def test_parsers_read_what_each_source_says(self):
        self.assertIn(("Commons", "recess", "2026-11-05", "2026-11-09", "Recess - Commons"),
                      sd.parse_westminster(WESTMINSTER))
        hol = sd.parse_holyrood(HOLYROOD)
        self.assertIn(("Holyrood", "recess", "2026-10-10", "2026-10-25", "S7M-00153"), hol)
        self.assertIn(("Holyrood", "recess", "2026-12-19", "2027-01-03", "S7M-00153"), hol)
        self.assertFalse([r for r in hol if r[4] == "S7M-00999"])          # not a recess motion
        self.assertEqual([r[2] for r in sd.parse_senedd_meetings(SENEDD)],
                         ["2026-10-20", "2026-10-21", "2026-11-03"])        # the cancelled one goes
        ni = sd.parse_ni(NI_PAGE)
        self.assertIn(("NI Assembly", "recess", "2026-10-24", "2026-11-01", "Halloween 2026"), ni)
        self.assertFalse([r for r in ni if "Easter" in r[4]])               # "to dissolution": no date to state

    def test_the_line_for_the_week_of_19_october(self):
        conn = store()
        got = sd.collect(FakeClient(), conn, datetime.date(2026, 10, 16), log=lambda *_: None)
        self.assertTrue(all(got.values()))
        line, missing = sd.sitting_line(conn, WEEK)
        self.assertEqual(line, "Commons and Lords sitting · Holyrood in recess until Sun 25 Oct · "
                               "Senedd sitting (Plenary Tue 20 and Wed 21 Oct) · "
                               "NI Assembly sitting, in recess from Sat 24 Oct")
        self.assertEqual(missing, [])
        line, _ = sd.sitting_line(conn, "2026-10-26")
        self.assertIn("Senedd: no Plenary this week, next Tue 3 Nov", line)
        self.assertIn("NI Assembly in recess until Sun 1 Nov", line)
        self.assertIn("Holyrood sitting", line)
        line, _ = sd.sitting_line(conn, "2026-11-02")
        self.assertTrue(line.startswith("Commons and Lords sitting, in recess from Thu 5 Nov"))

    def test_a_source_that_fails_is_left_out_never_guessed(self):
        conn = store()
        gaps = []
        got = sd.collect(FakeClient(fail=("niassembly",)), conn, datetime.date(2026, 10, 16),
                         log=lambda *_: None, gap=gaps.append)
        self.assertIsNone(got["NI Assembly"])
        self.assertTrue(gaps and "NI Assembly" in gaps[0])
        line, missing = sd.sitting_line(conn, WEEK)
        self.assertNotIn("NI Assembly", line)
        self.assertEqual(missing, ["NI Assembly"])
        # A later failure keeps the last good rows.
        sd.collect(FakeClient(), conn, datetime.date(2026, 10, 16), log=lambda *_: None)
        sd.collect(FakeClient(fail=("niassembly",)), conn, datetime.date(2026, 10, 16),
                   log=lambda *_: None, gap=lambda *_: None)
        self.assertIn("NI Assembly", sd.sitting_line(conn, WEEK)[0])

    def test_no_table_no_line(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        self.assertEqual(sd.sitting_line(conn, WEEK), (None, ["Westminster", "Holyrood", "Senedd", "NI Assembly"]))

    def test_canvas_and_post_carry_the_line(self):
        e = digest.Edition(week_commencing=WEEK, mode="normal", number=10)
        e.sitting_line = "Commons and Lords sitting · Holyrood in recess until Sun 25 Oct"
        e.sitting_missing = ["Senedd"]
        md = digest.render(e)
        self.assertIn("*Sitting this week:* Commons and Lords sitting · Holyrood in recess until Sun 25 Oct", md)
        self.assertLess(md.index("Sitting this week"), md.index("## This week"))
        self.assertIn("Sitting days: no published calendar read for Senedd", md)
        post = cd.slack_post(e)
        self.assertEqual(post.splitlines()[1], "_Commons and Lords sitting · Holyrood in recess until Sun 25 Oct_")

    def test_the_pull_and_the_monday_reread_both_read_it(self):
        src = open(os.path.join(ROOT, "run_weekly.py"), encoding="utf-8").read()
        self.assertIn('("sitting-days", lambda: refresh_sitting_days(conn, edition, base=client))', src)
        mon = open(os.path.join(ROOT, "run_monday.py"), encoding="utf-8").read()
        self.assertLess(mon.index("run_weekly.refresh_sitting_days(conn, week"),
                        mon.index("run_weekly.render_edition(week"))


# -- B: paid AI off ----------------------------------------------------------------

def seed_item(conn, item_id, tier=1, feed="pq", date="2026-10-14", areas=(3,), terms=("puberty blockers",)):
    conn.execute("INSERT INTO items (id, captured_at, source_feed, item_type, title, url, event_date, "
                 "issue_areas, matched_terms, tier, triage_score, extra) "
                 "VALUES (?, '2026-10-14', ?, 'x', ?, 'https://example.org', ?, ?, ?, ?, NULL, '{}')",
                 (item_id, feed, "Item " + item_id, date, json.dumps(list(areas)), json.dumps(list(terms)), tier))
    conn.commit()


NO_MODEL = AssertionError("no paid model call may happen without UK_PAID_JUDGE=1")


class PaidOffTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-present"})
        self.env.start()
        os.environ.pop("UK_PAID_JUDGE", None)
        import run_weekly
        self.rw = run_weekly
        self.secrets = mock.patch.object(run_weekly.publish, "load_secrets",
                                         return_value={"anthropic_api_key": "sk-test-secrets"})
        self.secrets.start()

    def tearDown(self):
        self.secrets.stop()
        self.env.stop()

    def test_sunday_triage_with_a_key_makes_no_paid_call(self):
        conn = store()
        seed_item(conn, "pq:1")
        wl = filt.load_watchlist(WATCHLIST)
        with mock.patch.object(triage, "score_live", side_effect=NO_MODEL), \
                mock.patch.object(triage, "score_in_slices", side_effect=NO_MODEL), \
                mock.patch.object(triage, "_default_transport", side_effect=NO_MODEL, create=True):
            for mode in (None, "auto", "live"):
                status = self.rw.run_triage_pass(conn, wl, WEEK, mode=mode)
                self.assertIn("free session judge", status)
        self.assertIsNone(conn.execute("SELECT triage_score FROM items WHERE id='pq:1'").fetchone()[0])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM api_spend").fetchone()[0], 0)

    def test_the_paid_path_needs_the_flag(self):
        conn = store()
        seed_item(conn, "pq:1")
        wl = filt.load_watchlist(WATCHLIST)
        fake = [triage.TriageResult("pq:1", 2, [3], "Paid line.")]
        with mock.patch.dict(os.environ, {"UK_PAID_JUDGE": "1"}), \
                mock.patch.object(triage, "triage", return_value=fake) as paid:
            status = self.rw.run_triage_pass(conn, wl, WEEK)
        self.assertTrue(paid.called)
        self.assertIn("(live)", status)

    def test_stance_pass_with_a_key_makes_no_paid_call(self):
        conn = store()
        with mock.patch.object(stance, "score_pending", side_effect=NO_MODEL), \
                mock.patch.object(stance, "classify_batch", side_effect=NO_MODEL):
            status = self.rw.run_stance_pass(conn, WEEK)
        self.assertTrue(status.startswith("skipped: the paid judge is off"))

    def test_devolved_judge_with_a_key_makes_no_paid_call(self):
        import devolved_triage as dt
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "s.db")
            conn = db.init_db(db.connect(path))
            dt.ensure_columns(conn)
            conn.execute("INSERT INTO sd_items (id, kind, dated, body, areas, tier, first_seen, last_seen) "
                         "VALUES ('q1', 'question', ?, 'Puberty blockers', '[3]', 1, 'x', 'x')",
                         (datetime.date.today().isoformat(),))
            conn.commit()
            conn.close()
            out = io.StringIO()
            with mock.patch.object(sys, "argv", ["devolved_triage.py", "--db", path]), \
                    mock.patch.object(dt.triage, "score_in_slices", side_effect=NO_MODEL), \
                    redirect_stdout(out):
                self.assertEqual(dt.main(), 0)
            self.assertIn("the paid judge is off", out.getvalue())
            conn = db.connect(path)
            self.assertIsNone(conn.execute("SELECT triage_score FROM sd_items").fetchone()[0])

    def test_monday_runs_the_devolved_judge_through_the_session_judge(self):
        import run_monday
        src = open(run_monday.__file__, encoding="utf-8").read()
        block = src[src.index("THE DEVOLVED JUDGE"):src.index("seen = whatson_reread_and_judge(week)")]
        self.assertIn("if run_weekly.paid_judge_opted_in():", block)
        self.assertIn('"session_judge.sh"', block)
        self.assertIn("tools/session_judge.sh tools/uk_whatson_judge.py", src)

    def test_rules_alone_render_for_items_the_judge_has_not_reached(self):
        conn = store()
        seed_item(conn, "pq:1", tier=1)
        seed_item(conn, "pq:2", tier=2)
        e = digest.Edition(week_commencing=WEEK, mode="normal", number=10)
        self.rw.sections_from_store(conn, e)
        ids = [r.get("qid") for r in e.pq_rows]
        self.assertEqual(ids, ["1"])                       # tier 1 shows, tier 2 waits
        self.assertEqual(e.pq_rows[0]["tag"], 2)
        self.assertIsNone(conn.execute("SELECT triage_score FROM items WHERE id='pq:1'").fetchone()[0])


class SessionQueueTests(unittest.TestCase):
    def fill(self, path, value, line="SCORE"):
        text = open(path, encoding="utf-8").read()
        text = text.replace(line + ": \nWHY: ", "{0}: {1}\nWHY: A concrete line about it.".format(line, value))
        open(path, "w", encoding="utf-8").write(text)

    def test_pull_judge_round_trip(self):
        import uk_pull_judge as j
        conn = store()
        seed_item(conn, "pq:1", tier=2, date="2026-10-01")
        seed_item(conn, "pq:2", tier=1, date="2026-09-01")
        wl = filt.load_watchlist(WATCHLIST)
        self.assertEqual([i.id for i in j.pending(conn, wl)], ["pq:2", "pq:1"])     # tier 1 first
        with tempfile.TemporaryDirectory() as tmp:
            q = os.path.join(tmp, "queue.md")
            self.assertEqual(j.queue_out(conn, wl, q, "2026-10-18", 5, log=lambda *_: None), 2)
            self.fill(q, 3)
            self.assertEqual(j.queue_in(conn, wl, q, "2026-10-18", log=lambda *_: None), 2)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM items WHERE triage_score = 3").fetchone()[0], 2)
        self.assertEqual(conn.execute("SELECT judge, model FROM session_scores LIMIT 1").fetchone()[:],
                         ("uk", "claude-code-session"))

    def test_stance_judge_round_trip_and_refusals(self):
        import uk_stance_judge as j
        conn = store()
        stance.ensure_table(conn)
        conn.execute("INSERT INTO mp_events VALUES (1, '2026-10-10', 'pq', 'pq:9', 'Asked about blockers', '[3]', '')")
        conn.execute("INSERT INTO mp_events VALUES (2, '2026-10-10', 'pq', 'pq:8', 'Asked about borders', '[11]', '')")
        conn.commit()
        self.assertEqual([r["ref"] for r in j.pending(conn)], ["pq:9"])     # migration-only skipped
        with tempfile.TemporaryDirectory() as tmp:
            q = os.path.join(tmp, "queue.md")
            j.queue_out(conn, q, "2026-10-18", 10, raw_dir=tmp, log=lambda *_: None)
            text = open(q, encoding="utf-8").read()
            self.assertIn("### item: pq:9", text)
            open(q, "w", encoding="utf-8").write(text.replace("STANCE: \nWHY: ", "STANCE: 7\nWHY: Too far."))
            self.assertEqual(j.queue_in(conn, q, "2026-10-18", log=lambda *_: None), 0)   # refused
            open(q, "w", encoding="utf-8").write(text.replace("STANCE: \nWHY: ", "STANCE: -1\nWHY: Leans against."))
            self.assertEqual(j.queue_in(conn, q, "2026-10-18", log=lambda *_: None), 1)
        self.assertEqual(conn.execute("SELECT stance, model FROM stance WHERE ref='pq:9'").fetchone()[:],
                         (-1, "claude-code-session"))
        self.assertIn("STANCE", j.STANCE_PROMPT)

    def test_devolved_judge_round_trip(self):
        import devolved_triage as dt
        conn = store()
        dt.ensure_columns(conn)
        conn.execute("INSERT INTO sd_items (id, kind, dated, body, areas, tier, first_seen, last_seen) "
                     "VALUES ('q1', 'question', ?, 'Puberty blockers', '[3]', 1, 'x', 'x')",
                     (datetime.date.today().isoformat(),))
        conn.commit()
        with tempfile.TemporaryDirectory() as tmp:
            q = os.path.join(tmp, "queue.md")
            self.assertEqual(dt.queue_out(conn, q, 10, datetime.date.today().isoformat(), log=lambda *_: None), 1)
            self.fill(q, 2)
            self.assertEqual(dt.queue_in(conn, q, datetime.date.today().isoformat(), log=lambda *_: None), 1)
        self.assertEqual(conn.execute("SELECT triage_score FROM sd_items").fetchone()[0], 2)


FAKE_CLAUDE = """#!/bin/bash
if [ "$1" = "auth" ]; then echo '{"loggedIn": true, "authMethod": "claude.ai"}'; exit 0; fi
if [ "$1" = "--help" ]; then echo "--restricted --permission-prompts"; exit 0; fi
env | grep -q ANTHROPIC_API_KEY && { echo "KEY LEAKED"; exit 9; }
python3 - <<'PY'
import re
p = "queue.md"
t = open(p).read()
t = t.replace("SCORE: \\nWHY: ", "SCORE: 2\\nWHY: Filled by the fake session.")
t = t.replace("STANCE: \\nWHY: ", "STANCE: 1\\nWHY: Filled by the fake session.")
open(p, "w").write(t)
PY
echo done
"""


class JobTests(unittest.TestCase):
    def test_the_job_runs_three_queues_in_order_then_publishes(self):
        job = open(os.path.join(ROOT, "jobs", "uk-session-judge.sh"), encoding="utf-8").read()
        steps = [job.index(s) for s in ("bash tools/session_judge.sh tools/uk_pull_judge.py",
                                        "bash tools/session_judge.sh tools/devolved_triage.py",
                                        "bash tools/session_judge.sh tools/uk_stance_judge.py",
                                        "python3 tools/raw_state.py --push",
                                        "python3 tools/db_state.py --push")]
        self.assertEqual(steps, sorted(steps))
        self.assertIn('GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-UK session judge}"', job)
        self.assertNotIn("UK_PAID_JUDGE", job.split("set -o pipefail", 1)[1])
        plist = open(os.path.join(ROOT, "ops", "launchd", "net.citizengo.parlmonitor.uk-session-judge.plist"),
                     encoding="utf-8").read()
        self.assertIn("<key>Weekday</key><integer>0</integer><key>Hour</key><integer>12</integer>"
                      "<key>Minute</key><integer>30</integer>", plist)

    def test_the_session_judge_scores_with_a_key_in_the_environment_and_spends_nothing(self):
        """tools/session_judge.sh with a FAKE claude and a key exported: the
        key never reaches claude, and the scores land."""
        with tempfile.TemporaryDirectory() as tmp:
            bindir = os.path.join(tmp, "bin")
            os.makedirs(bindir)
            fake = os.path.join(bindir, "claude")
            with open(fake, "w") as fh:
                fh.write(FAKE_CLAUDE)
            os.chmod(fake, 0o755)
            path = os.path.join(tmp, "s.db")
            conn = db.init_db(db.connect(path))
            seed_item(conn, "pq:1")
            conn.close()
            env = dict(os.environ, PATH=bindir + os.pathsep + os.environ["PATH"], PARL_DB=path,
                       ANTHROPIC_API_KEY="sk-test-present", TMPDIR=tmp)
            out = subprocess.run(["bash", os.path.join(ROOT, "tools", "session_judge.sh"),
                                  "tools/uk_pull_judge.py", "10", "5"], cwd=ROOT, env=env,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            log = out.stdout.decode()
            self.assertEqual(out.returncode, 0, log)
            self.assertNotIn("KEY LEAKED", log)
            conn = db.connect(path)
            self.assertEqual(conn.execute("SELECT triage_score FROM items WHERE id='pq:1'").fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM api_spend").fetchone()[0], 0)


# -- C: question summaries, the JOINT COMMITTEE tag ---------------------------------

class SmallFixTests(unittest.TestCase):
    def test_holyrood_questions_lose_the_boilerplate_and_end_on_a_phrase(self):
        q = cd.question_summary
        self.assertEqual(q("To ask the Scottish Government what assessment it has made of the risk of modern "
                           "slavery affecting individuals who become destitute as a result of their employer's "
                           "sponsorship license being revoked."),
                         "The risk of modern slavery affecting individuals who become destitute")
        self.assertEqual(q("To ask the Scottish Government what assessment it has made of the comparative level "
                           "of funding available to listed places of worship in Scotland through the £1 million "
                           "Historic Environment Scotland fund."),
                         "The comparative level of funding available to listed places of worship in Scotland")
        self.assertEqual(q("To ask the Scottish Government whether it plans to introduce gender-neutral "
                           "designation options for both parents when registering births."),
                         "Plans to introduce gender-neutral designation options for both parents when registering births")
        self.assertEqual(q("To ask the Scottish Government for what reason it has never undertaken a comprehensive "
                           "assessment of adoptees as a distinct group across their whole life course under the "
                           "Equality Act 2010."),
                         "Why it has never undertaken a comprehensive assessment of adoptees as a distinct group")
        for text in ("To ask the Scottish Government what it is doing to support the treatment and care of "
                     "cisgender female, transgender and gender diverse individuals with Ehlers-Danlos syndrome "
                     "and Hypermobility Spectrum Disorder.",):
            got = q(text)
            self.assertFalse(got.lower().startswith("to ask"))
            self.assertNotIn(got.rsplit(" ", 1)[-1].lower(), cd._DANGLING)

    def test_joint_committees_are_not_the_commons(self):
        self.assertEqual(cd.house_tag("Joint Select & Joint Committees", None,
                                      "Draft Conversion Practices Bill (Joint Committee)"), "JOINT COMMITTEE")
        self.assertEqual(cd.house_tag("Commons", "Committee Room 4",
                                      "Draft Conversion Practices Bill (Joint Committee)"), "JOINT COMMITTEE")
        self.assertEqual(cd.house_tag("Commons", "Westminster Hall", "Select Committee Statement on the "
                                      "Fourth Report of the Joint Committee on Human Rights"), "COMMONS")
        self.assertIn(cd.JOINT, cd.TAGS)


# -- D: petitions and gov.uk documents ---------------------------------------------

def petitions_table(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS uk_petitions (petition_id INTEGER PRIMARY KEY, title TEXT, state TEXT, "
                 "signatures INTEGER, threshold_reached TEXT, response_date TEXT, debate_date TEXT, url TEXT, "
                 "areas TEXT, matched_terms TEXT, first_seen TEXT, last_seen TEXT)")
    rows = [
        (700001, "Ban puberty blockers for under-18s permanently", "awaiting_debate", 120456, "100k", "2026-09-01",
         "2026-11-02", "https://petition.parliament.uk/petitions/700001", "[3]"),
        (700002, "Protect buffer zones review", "open", 15000, "10k", "2026-10-15", None, None, "[1]"),
        (700003, "Fund the railways", "open", 200000, "100k", None, None, None, "[]"),
        (700004, "Stop small boats", "open", 50000, "10k", None, None, None, "[11]"),
        (700005, "Old closed one", "closed", 30000, "10k", "2025-01-01", "2025-03-01", None, "[2]"),
        (700006, "Keep sex-based rights", "open", 9000, None, None, None, None, "[5]"),
    ]
    conn.executemany("INSERT INTO uk_petitions (petition_id, title, state, signatures, threshold_reached, "
                     "response_date, debate_date, url, areas, first_seen, last_seen) "
                     "VALUES (?,?,?,?,?,?,?,?,?,'x','x')", rows)


def govuk_table(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS govuk_docs (base_path TEXT PRIMARY KEY, title TEXT, doc_type TEXT, organisation TEXT, "
                 "public_updated_at TEXT, closing_date TEXT, url TEXT, areas TEXT, matched_terms TEXT, "
                 "first_seen TEXT, last_seen TEXT)")
    rows = [
        ("/government/consultations/rshe", "RSHE guidance consultation", "open_consultation", "Department for Education",
         "2026-10-01T09:00:00Z", "2026-11-20", None, "[6]", '["relationships education"]'),
        ("/government/consultations/old", "Closed one", "closed_consultation", "DHSC", "2026-10-14", "2026-10-10",
         None, "[3]", "[]"),
        ("/government/consultations/outcome", "Response on safe access zones", "consultation_outcome", "Home Office",
         "2026-10-13", None, None, "[1]", '["buffer zones"]'),
        ("/government/publications/blockers", "Puberty blockers trial update", "publication", "DHSC",
         "2026-10-15T10:00:00Z", None, None, "[3]", '["puberty blockers", "cross-sex hormones"]'),
        ("/government/publications/roads", "Roads", "publication", "DfT", "2026-10-15", None, None, "[]", "[]"),
        ("/government/publications/old", "Older paper", "publication", "MoJ", "2026-09-01", None, None, "[2]", "[]"),
    ]
    conn.executemany("INSERT INTO govuk_docs (base_path, title, doc_type, organisation, public_updated_at, "
                     "closing_date, url, areas, matched_terms, first_seen, last_seen) "
                     "VALUES (?,?,?,?,?,?,?,?,?,'x','x')", rows)


class PetitionsAndGovukTests(unittest.TestCase):
    def test_absent_tables_are_a_coverage_line(self):
        conn = store()
        self.assertEqual(cd.petitions_from_store(conn, WEEK), ([], cd.PETITIONS_NOTE))
        self.assertEqual(cd.govuk_from_store(conn, WEEK), ([], [], cd.GOVUK_NOTE))

    def test_petitions_on_our_ground_past_a_threshold(self):
        conn = store()
        petitions_table(conn)
        rows, note = cd.petitions_from_store(conn, WEEK)
        self.assertIsNone(note)
        self.assertEqual([p["id"] for p in rows], ["700001", "700002"])
        md = cd.render_petitions(rows)
        self.assertIn("## Petitions", md)
        self.assertIn("| [Ban puberty blockers for under-18s permanently](https://petition.parliament.uk/petitions/"
                      "700001) | 120,456 | debate in Westminster Hall, Mon 2 Nov |", md)
        self.assertIn("Government responded 15 Oct", md)
        self.assertIn("https://petition.parliament.uk/petitions/700002", md)
        timeline = cd.petition_rows(rows, [], WEEK)
        self.assertEqual([(r.date, r.where, r.detail) for r in timeline],
                         [("2026-11-02", "COMMONS", "Westminster Hall petition debate")])
        # What's On already has the debate: no second row.
        have = [cd.Row(date="2026-11-02", where="COMMONS", title="e-petition 700001 relating to puberty blockers")]
        self.assertEqual(cd.petition_rows(rows, have, WEEK), [])

    def test_govuk_consultations_are_uk_govt_deadlines_and_publications_a_short_block(self):
        conn = store()
        govuk_table(conn)
        rows, pubs, note = cd.govuk_from_store(conn, WEEK)
        self.assertIsNone(note)
        self.assertEqual([(r.date, r.where, r.title, r.url) for r in rows],
                         [("2026-11-20", "UK GOVT", "RSHE guidance consultation",
                           "https://www.gov.uk/government/consultations/rshe")])
        self.assertEqual([p["title"] for p in pubs], ["Puberty blockers trial update",
                                                      "Response on safe access zones"])
        md = cd.render_publications(pubs)
        self.assertIn("## Government publications", md)
        self.assertIn("- 15 Oct · [Puberty blockers trial update](https://www.gov.uk/government/publications/"
                      "blockers) (DHSC, publication)", md)
        # The edition's own consultation feed already has it: retagged, not doubled.
        existing = [cd.from_deadline({"type": "Consultation", "title": "RSHE guidance consultation",
                                      "url": "https://www.gov.uk/government/consultations/rshe",
                                      "deadline": "2026-11-20", "areas": [6]})]
        merged = cd.merge_consultations(existing, rows)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].where, "UK GOVT")

    def test_blocks_sit_after_key_questions(self):
        e = digest.Edition(week_commencing=WEEK, mode="normal", number=10)
        e.key_questions = [{"where": "HOLYROOD", "answered": "2026-10-01", "asker": "Carol Mochan", "score": 2,
                            "url": None, "why": "Why it matters.", "areas": [3], "refs": ["S7W-1"],
                            "headings": ["The risk of modern slavery"]}]
        e.petitions = [{"id": "1", "title": "A petition", "state": "open", "signatures": 12000,
                        "threshold": "10k", "response_date": None, "debate_date": None, "areas": [3], "url": "u"}]
        e.gov_publications = [{"title": "A paper", "url": "v", "type": "guidance", "organisation": "DfE",
                               "date": "2026-10-14", "areas": [6], "weight": 1}]
        e.source_notes = ["Something: not collected yet."]
        md = digest.render(e)
        order = [md.index(h) for h in ("## Key questions", "## Petitions", "## Government publications",
                                       "## Reference")]
        self.assertEqual(order, sorted(order))
        self.assertIn("- Something: not collected yet.", md)


if __name__ == "__main__":
    unittest.main()
