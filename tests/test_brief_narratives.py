"""Brief narratives on the free session judge (Chris, 16 October 2026).

The Campaigns Brief builders (tools/make_briefs.py, tools/de_briefs.py) drafted
their prose with the paid API, off since PR #209. tools/brief_narratives.py now
queues each pending narrative for Claude Code on the Mini (src/brief_narratives.py),
reads the answers back strictly, stores them, and the builders use them exactly
where the API's reply went. Fixtures only; no network, no model, no spend.
"""

import datetime
import glob
import importlib.util
import io
import json
import os
import plistlib
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import brief_narratives as bn  # noqa: E402
from src import db  # noqa: E402
from src import stance  # noqa: E402

TODAY = datetime.date(2026, 10, 18)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    conn.execute("INSERT INTO bills_board (bill_id, title, sponsor, house, stage, next_key_date, "
                 "what_next, areas, status) VALUES (4001, 'Assisted Dying (Test) Bill', "
                 "'Jane Doe MP', 'Commons', '2nd reading', '2026-11-06', "
                 "'Second reading on 6 November', '2', 'live')")
    conn.execute("INSERT INTO items (id, captured_at, source_feed, item_type, title, url, "
                 "issue_areas, triage_score, why_it_matters, deadline, tier) VALUES ('c1', "
                 "'2026-10-10', 'consultation', 'consultation', 'Consultation on relationships "
                 "education guidance', 'https://www.gov.uk/x', '[6]', 3, 'Parents lose their say.', "
                 "'2026-12-01', 1)")
    conn.execute("CREATE TABLE campaign_performance (petition_id INTEGER, name TEXT, areas TEXT, "
                 "new_members INTEGER, signatures INTEGER, logged_at TEXT, final INTEGER)")
    conn.execute("INSERT INTO campaign_performance VALUES (17165, 'Stop assisted suicide', '[2]', "
                 "900, 4000, '2026-10-01', 1)")
    conn.commit()
    return conn


UK_BILL = "bill-assisted-dying-test-bill"
UK_CONS = "consultation-consultation-on-relationships-education-guidance"


def narrative(**over):
    f = {
        "campaign_name": "Tell MPs: Never make death a treatment option",
        "background": ("MPs will debate the Assisted Dying (Test) Bill at second reading on 6 November.\n\n"
                       "Jane Doe MP has brought the Bill to the Commons. It would change the law on "
                       "the end of life, and vulnerable people would carry the risk.\n\n"
                       "**What:** A Bill to legalise assisted dying.\n**Who:** Jane Doe MP.\n"
                       "**Where it stands:** Awaiting second reading in the Commons.\n"
                       "**What's next:** Second reading on 6 November.\n"
                       "**Why it matters:** Once death is a treatment option, the pressure falls on the weakest."),
        "ask": "We ask every MP to vote against the Bill at second reading, because the duty of the law "
               "is to protect life, never to end it.",
        "injustice": "The vulnerable carry the risk: people who are ill or disabled could feel pressure to "
                     "die. The safeguards cannot hold: no law can see inside a family or a ward, and the "
                     "pressure is often silent. Doctors are asked to end life: medicine exists to heal.",
        "arguments": "Care, not killing: palliative care relieves suffering and deserves the money. "
                     "Safeguards erode: every jurisdiction that legalised assisted dying has widened it. "
                     "The disabled are afraid: disability groups oppose the Bill. Doctors object: many "
                     "would refuse to take part, and their conscience must be protected.",
        "urgency": "Second reading is on 6 November.\n\nOnce a Bill passes second reading it is far harder "
                   "to stop.\n\nSilence from the public would read as consent.",
        "listen": "MPs answer to their constituents, and thousands of us will write before the vote.",
        "bad_outcome": "MPs pass the Bill and the most vulnerable people in Britain are told death is an option.",
        "good_outcome": "MPs reject the Bill at second reading and Parliament invests in palliative care instead.",
        "offline": "Deliver the petition to Parliament before the vote.",
        "tim": "17165 - Stop assisted suicide - the same issue and the same audience",
        "image": "An elderly hand held by a younger one, warm light, hopeful.",
        "rf4_gain": "The Bill falls and the law keeps protecting life for this Parliament.\nScore: 4 - a narrow law stopped.",
        "rf4_cost": "The Bill passes and the precedent is set.\nBacklash check: our campaign keeps a calm tone, so it "
                    "cannot make things worse.\nScore: 0 - the loss would have happened regardless.",
    }
    f.update(over)
    return {k: v for k, v in f.items() if v is not None}


def answer_text(fields):
    return "\n".join("@@{0}@@\n{1}\n".format(k, v) for k, v in fields.items())


def fill(path, answers):
    """Do what the session does: replace each item's placeholder line."""
    text = open(path, encoding="utf-8").read()
    for iid, ans in answers.items():
        text = text.replace(bn.PLACEHOLDER.format(iid), ans)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.briefs = os.path.join(self.tmp, "briefs")
        os.makedirs(self.briefs)
        self.tool = _load("brief_narratives")
        self.b = self.tool.Builders(self.briefs)
        self.conn = store()
        # Subjects as of the fixture date; German subjects patched per test.
        real = self.b.mb.subjects
        self.b.mb.subjects = lambda conn, today=None: real(conn, TODAY)
        self.b.de.subjects = lambda conn, today=None: []
        # No Asana task may ever be opened from a test.
        p = mock.patch("src.publish.load_secrets", return_value={})
        p.start()
        self.addCleanup(p.stop)
        # A key in the environment, no flag: the paid transport must never run.
        p2 = mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"})
        p2.start()
        self.addCleanup(p2.stop)
        p3 = mock.patch.object(stance, "_default_transport", side_effect=AssertionError("paid API called"))
        p3.start()
        self.addCleanup(p3.stop)
        self.q = os.path.join(self.tmp, "queue.md")

    def run_tool(self, fn, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            res = fn(self.conn, self.b, *args)
        return res, out.getvalue()


class QueueRoundTripTests(Base):
    def test_queue_carries_the_api_frame_and_payload(self):
        n, log = self.run_tool(self.tool.queue_out, self.q, 5)
        self.assertEqual(n, 2)
        self.assertIn("session queue: 2 item(s) written", log)
        text = open(self.q, encoding="utf-8").read()
        self.assertIn(bn.QUEUE_MARKER, text.splitlines()[1])
        # The drafter's own frame, verbatim: house style, BBC-style Background, markers.
        self.assertIn(self.b.mb.DRAFT_SYSTEM.strip(), text)
        self.assertIn("BACKGROUND (Christopher's rule, 12 October 2026", text)
        # The exact payload the API was sent.
        s = [x for x in self.b.mb.subjects(self.conn) if x["slug"] == UK_BILL][0]
        want = bn.payload_text(self.b.mb.narrative_payload(s, self.b.mb.uk_facts(self.conn, s)))
        self.assertIn(want, text)
        self.assertIn(bn.PLACEHOLDER.format("uk:" + UK_BILL), text)

    def test_round_trip_stores_and_the_queue_empties(self):
        self.run_tool(self.tool.queue_out, self.q, 1)
        fill(self.q, {"uk:" + UK_BILL: answer_text(narrative())})
        res, log = self.run_tool(self.tool.queue_in, self.q, TODAY)
        self.assertEqual(res, (1, 0, 0), log)
        self.assertIn("session queue: 1 item(s) scored", log)
        got = bn.stored(self.conn, UK_BILL)
        self.assertEqual(got["campaign_name"], "Tell MPs: Never make death a treatment option")
        self.assertIn("**Why it matters:**", got["background"])
        row = self.conn.execute("SELECT builder, model FROM brief_narratives").fetchone()
        self.assertEqual(tuple(row), ("uk", "claude-code-session"))
        # Next queue: only the other subject.
        self.run_tool(self.tool.queue_out, self.q, 5)
        text = open(self.q, encoding="utf-8").read()
        self.assertNotIn("### item: uk:" + UK_BILL, text)
        self.assertIn("### item: uk:" + UK_CONS, text)

    def test_an_untouched_item_is_blank_and_stays_pending(self):
        self.run_tool(self.tool.queue_out, self.q, 2)
        res, log = self.run_tool(self.tool.queue_in, self.q, TODAY)
        self.assertEqual(res, (0, 0, 2))
        self.assertIsNone(bn.stored(self.conn, UK_BILL))

    def test_a_drafted_narrative_is_written_once(self):
        self.run_tool(self.tool.queue_out, self.q, 1)
        saved = open(self.q, encoding="utf-8").read()
        fill(self.q, {"uk:" + UK_BILL: answer_text(narrative())})
        self.run_tool(self.tool.queue_in, self.q, TODAY)
        with open(self.q, "w", encoding="utf-8") as fh:
            fh.write(saved)
        fill(self.q, {"uk:" + UK_BILL: answer_text(narrative(campaign_name="Tell MPs: something else"))})
        res, log = self.run_tool(self.tool.queue_in, self.q, TODAY)
        self.assertEqual(res[0], 0)
        self.assertIn("not pending", log)
        self.assertEqual(bn.stored(self.conn, UK_BILL)["campaign_name"],
                         "Tell MPs: Never make death a treatment option")

    def test_another_queue_is_refused_whole(self):
        with open(self.q, "w", encoding="utf-8") as fh:
            fh.write("# Judge queue\n<!-- vote-meaning-queue v1 -->\n### item: uk:{0}\n".format(UK_BILL))
        res, log = self.run_tool(self.tool.queue_in, self.q, TODAY)
        self.assertIsNone(res)
        self.assertIn("[gap]", log)


class StrictReadingTests(Base):
    def refused_for(self, fields=None, raw=None):
        bn.ensure(self.conn)
        self.conn.execute("DELETE FROM brief_narrative_refusals")   # one check per call
        self.run_tool(self.tool.queue_out, self.q, 1)
        fill(self.q, {"uk:" + UK_BILL: raw if raw is not None else answer_text(fields)})
        res, log = self.run_tool(self.tool.queue_in, self.q, TODAY)
        self.assertEqual(res[0], 0, log)
        self.assertIsNone(bn.stored(self.conn, UK_BILL))
        return log

    def test_missing_field(self):
        self.assertIn("missing field(s): urgency", self.refused_for(narrative(urgency=None)))

    def test_optional_fields_may_be_omitted(self):
        self.run_tool(self.tool.queue_out, self.q, 1)
        fill(self.q, {"uk:" + UK_BILL: answer_text(narrative(tim=None, addressee=None))})
        res, _ = self.run_tool(self.tool.queue_in, self.q, TODAY)
        self.assertEqual(res[0], 1)

    def test_duplicate_and_unknown_fields(self):
        dup = answer_text(narrative()) + "\n@@ask@@\nAgain.\n"
        self.assertIn("appears twice", self.refused_for(raw=dup))
        self.assertIn("unknown field", self.refused_for(raw=answer_text(narrative()) + "\n@@why_now@@\nx\n"))

    def test_prose_before_the_first_marker(self):
        self.assertIn("prose before the first field marker",
                      self.refused_for(raw="Here you go:\n" + answer_text(narrative())))

    def test_em_dash(self):
        self.assertIn("em dash", self.refused_for(narrative(ask="We ask MPs — every one of them — "
                                                                 "to vote against the Bill at second reading.")))

    def test_an_em_dash_inside_a_copied_record_title_is_allowed(self):
        wanted = [f for f, _ in self.b.mb.NARRATIVE_FIELDS]
        tim = "14715 - No Scrutiny, No Safeguards, No Way\u2014Tell MPs to Reject Assisted Suicide - same issue"
        record = '{"title": "No Scrutiny, No Safeguards, No Way\u2014Tell MPs to Reject Assisted Suicide"}'
        self.assertIsNone(bn.check_fields(narrative(tim=tim), record, wanted, [14715]))
        self.assertIn("em dash", bn.check_fields(narrative(tim=tim.replace("same issue", "same\u2014issue")),
                                                 record, wanted, [14715]))

    def test_american_spelling(self):
        self.assertIn("American spelling", self.refused_for(narrative(
            listen="MPs answer to their constituents, and we will organize thousands of letters.")))

    def test_a_word_the_record_uses_is_allowed(self):
        bn_check = bn.check_fields(narrative(listen="The World Health Organization has said nothing on "
                                                    "this and MPs answer to constituents."),
                                   '{"t": "World Health Organization"}',
                                   [f for f, _ in self.b.mb.NARRATIVE_FIELDS], [17165])
        self.assertIsNone(bn_check)

    def test_length_limit(self):
        self.assertIn("over", self.refused_for(narrative(campaign_name="Tell MPs: " + "no " * 80)))

    def test_markdown_heading(self):
        self.assertIn("markdown heading", self.refused_for(narrative(
            urgency="## Deadline\nSecond reading is on 6 November, and silence reads as consent to MPs.")))

    def test_house_shape(self):
        self.assertIn("open 'Tell '", self.refused_for(narrative(campaign_name="Stop the Assisted Dying Bill now")))
        self.assertIn("labelled line", self.refused_for(narrative(
            background="MPs will debate the Bill on 6 November. " * 10)))
        self.assertIn("Backlash check", self.refused_for(narrative(
            rf4_cost="The Bill passes and the precedent is set for the whole country.\nScore: 0 - regardless.")))

    def test_an_invented_quotation_is_refused(self):
        bg = narrative()["background"].replace(
            "It would change", 'Jane Doe said "this Bill will give everyone a choice at the end" and it would change')
        self.assertIn("quotes words the record does not hold", self.refused_for(narrative(background=bg)))

    def test_a_quotation_from_the_record_passes(self):
        bg = narrative()["background"].replace(
            "It would change", 'The minister said “we will not rush a change of this gravity”, and it would change')
        record = '{"said": "We will not rush a change of this gravity, the minister said."}'
        self.assertIsNone(bn.check_fields(narrative(background=bg), record,
                                          [f for f, _ in self.b.mb.NARRATIVE_FIELDS], [17165]))
        self.assertIn("quotes words", bn.check_fields(narrative(background=bg), '{"said": "nothing"}',
                                                      [f for f, _ in self.b.mb.NARRATIVE_FIELDS], [17165]))

    def test_tim_ids_come_from_the_candidates(self):
        self.assertIn("not in facts.tim_candidates",
                      self.refused_for(narrative(tim="99999 - Invented petition - same issue")))

    def test_damaged_sections_and_twice_seen_ids(self):
        self.run_tool(self.tool.queue_out, self.q, 1)
        text = open(self.q, encoding="utf-8").read().replace("#### End of uk:" + UK_BILL, "")
        with open(self.q, "w", encoding="utf-8") as fh:
            fh.write(text)
        res, log = self.run_tool(self.tool.queue_in, self.q, TODAY)
        self.assertIn("damaged", log)
        self.run_tool(self.tool.queue_out, self.q, 1)
        text = open(self.q, encoding="utf-8").read()
        block = text[text.index("### item:"):]
        with open(self.q, "w", encoding="utf-8") as fh:
            fh.write(text + "\n" + block)
        fill(self.q, {"uk:" + UK_BILL: answer_text(narrative())})
        res, log = self.run_tool(self.tool.queue_in, self.q, TODAY)
        self.assertIn("the id appears twice", log)

    def test_a_refused_item_goes_to_the_back(self):
        self.refused_for(narrative(urgency=None))
        self.run_tool(self.tool.queue_out, self.q, 1)
        self.assertIn("### item: uk:" + UK_CONS, open(self.q, encoding="utf-8").read())


class BuildersUseTheStoredNarrativeTests(Base):
    def test_make_briefs_renders_the_stored_narrative_with_a_key_and_no_flag(self):
        s = [x for x in self.b.mb.subjects(self.conn) if x["slug"] == UK_BILL][0]
        bn.save(self.conn, UK_BILL, "uk", narrative(), {"x": 1}, "2026-10-18")
        out = io.StringIO()
        with redirect_stdout(out):
            slug, drafted = self.b.mb.write_one(self.conn, s, {}, TODAY, "sk-ant-test")
        self.assertTrue(drafted)
        md = open(os.path.join(self.briefs, UK_BILL + ".md"), encoding="utf-8").read()
        self.assertIn("# Campaigns Brief (DRAFT): Tell MPs: Never make death a treatment option", md)
        self.assertIn("**What's next:** Second reading on 6 November.", md)
        self.assertNotIn("NARRATIVE NOT DRAFTED", md)
        csv_text = open(os.path.join(self.briefs, UK_BILL + ".csv"), encoding="utf-8").read()
        self.assertIn("vote against the Bill at second reading", csv_text)
        self.assertNotIn("[CAMPAIGNER: draft needed]", csv_text.split("RED FOX FOUR")[0]
                         .replace("Ideas for eventual Offline Actions,[CAMPAIGNER: draft needed]", ""))

    def test_without_one_the_brief_says_not_drafted_yet(self):
        s = [x for x in self.b.mb.subjects(self.conn) if x["slug"] == UK_BILL][0]
        with redirect_stdout(io.StringIO()):
            self.b.mb.write_one(self.conn, s, {}, TODAY, None)
        md = open(os.path.join(self.briefs, UK_BILL + ".md"), encoding="utf-8").read()
        self.assertIn("NARRATIVE NOT DRAFTED YET", md)
        self.assertTrue(self.tool.has_placeholders(os.path.join(self.briefs, UK_BILL + ".md")))

    def test_de_briefs_renders_the_stored_narrative(self):
        subject = {"kind": "petition", "slug": "de-test-petition-1", "title": "Keine Test-Petition",
                   "areas": [1], "area_labels": ["Abortion"], "stage": "open for co-signature",
                   "sponsor": None, "deadline": "2026-11-30", "why": "Matters.", "url": "https://x"}
        bn.save(self.conn, subject["slug"], "de", narrative(), {"x": 1}, "2026-10-18")
        with redirect_stdout(io.StringIO()):
            path, drafted = self.b.de.write_brief(self.conn, subject, self.b.mb, None, "2026-10-18")
        self.assertTrue(drafted)
        md = open(path, encoding="utf-8").read()
        self.assertIn("Tell MPs: Never make death a treatment option", md)
        self.assertNotIn("NARRATIVE NOT DRAFTED", md)


class BackfillTests(Base):
    def test_a_live_placeholder_brief_is_filled_and_rerendered_in_place(self):
        s = [x for x in self.b.mb.subjects(self.conn) if x["slug"] == UK_BILL][0]
        with redirect_stdout(io.StringIO()):
            self.b.mb.write_one(self.conn, s, {}, TODAY, None)      # shipped with placeholders
        self.conn.execute("UPDATE brief_log SET asana_gid = 'A1', drive_file_id = 'D1' WHERE slug = ?",
                          (UK_BILL,))
        self.conn.commit()
        out = io.StringIO()
        with redirect_stdout(out):
            self.tool.report(self.conn, self.b)
        self.assertIn("1 show the narrative placeholder: 1 to backfill", out.getvalue())
        self.run_tool(self.tool.queue_out, self.q, 5)
        text = open(self.q, encoding="utf-8").read()
        # New subjects first, the backfill after.
        self.assertLess(text.index("### item: uk:" + UK_CONS), text.index("### item: uk:" + UK_BILL))
        fill(self.q, {"uk:" + UK_BILL: answer_text(narrative())})
        res, log = self.run_tool(self.tool.queue_in, self.q, TODAY)
        self.assertEqual(res[0], 1, log)
        self.assertIn("re-rendered its brief", log)
        self.assertIn("asana: keeping the existing review task A1", log)
        md = open(os.path.join(self.briefs, UK_BILL + ".md"), encoding="utf-8").read()
        self.assertNotIn("NARRATIVE NOT DRAFTED", md)
        self.assertIn("Tell MPs: Never make death a treatment option", md)
        row = self.conn.execute("SELECT status, asana_gid, drive_file_id, narrative_rewrite FROM brief_log "
                                "WHERE slug = ?", (UK_BILL,)).fetchone()
        self.assertEqual(tuple(row), ("pending", "A1", "D1", "due"))

    def test_a_rerender_never_opens_a_review_task(self):
        s = [x for x in self.b.mb.subjects(self.conn) if x["slug"] == UK_BILL][0]
        with redirect_stdout(io.StringIO()):
            self.b.mb.write_one(self.conn, s, {}, TODAY, None)
        with mock.patch("src.publish.load_secrets", return_value={"asana_pat": "x"}), \
                mock.patch("src.publish.asana_create_brief_approval",
                           side_effect=AssertionError("asana")) as made:
            bn.save(self.conn, UK_BILL, "uk", narrative(), {"x": 1})
            with redirect_stdout(io.StringIO()):
                self.b.mb.write_one(self.conn, s, {}, TODAY, None, rerender=True)
            made.assert_not_called()

    def test_a_closed_subject_is_counted_not_queued(self):
        with open(os.path.join(self.briefs, "bill-gone.md"), "w", encoding="utf-8") as fh:
            fh.write("> **NARRATIVE NOT DRAFTED YET: ...**\n")
        self.b.mb.ensure_log(self.conn)
        self.conn.execute("INSERT INTO brief_log (slug, subject, generated_at, path, status) VALUES "
                          "('bill-gone', 'Gone Bill', '2026-10-12', 'x', 'pending')")
        found = self.tool.survey(self.conn, self.b)
        self.assertIn(("uk", "bill-gone"), found["stuck"])
        self.assertNotIn("bill-gone", [it["slug"] for it in found["pending"]])

    def test_the_report_writes_nothing(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        db.init_db(conn)
        before = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
        with redirect_stdout(io.StringIO()):
            self.tool.report(conn, self.b)
        self.assertEqual(before, {r[0] for r in conn.execute("SELECT name FROM sqlite_master")})


class DriveRefillTests(unittest.TestCase):
    def setUp(self):
        self.pub = _load("publish_briefs_to_drive")
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("CREATE TABLE brief_log (slug TEXT PRIMARY KEY, subject TEXT, status TEXT, "
                          "drive_file_id TEXT, narrative_rewrite TEXT)")
        self.conn.execute("INSERT INTO brief_log VALUES ('a', 'A', 'pending', 'D1', 'due')")
        self.conn.execute("INSERT INTO brief_log VALUES ('b', 'B', 'pending', 'D2', 'due')")

    def test_refilled_only_while_no_person_has_edited_it(self):
        editors = {"D1": None, "D2": "campaigner@citizengo.net"}
        with mock.patch.object(self.pub, "edited_by_a_person", side_effect=lambda t, f: editors[f]), \
                mock.patch.object(self.pub, "publish_one", return_value=("D1", "ok")) as pub, \
                redirect_stdout(io.StringIO()) as out:
            self.assertEqual(self.pub.refill_narrated(self.conn, "tok"), 1)
        pub.assert_called_once_with("tok", "a", "A", into="D1")
        states = dict(self.conn.execute("SELECT slug, narrative_rewrite FROM brief_log"))
        self.assertEqual(states["a"], "done")
        self.assertEqual(states["b"], "held: edited in Drive by campaigner@citizengo.net")
        self.assertIn("held", out.getvalue())

    def test_the_editor_check_reads_drive_metadata(self):
        with mock.patch.object(self.pub, "api", return_value={"lastModifyingUser": {"me": True}}) as api:
            self.assertIsNone(self.pub.edited_by_a_person("tok", "D1"))
        self.assertIn("lastModifyingUser", api.call_args[0][1])
        with mock.patch.object(self.pub, "api", return_value={
                "lastModifyingUser": {"me": False, "emailAddress": "x@y"}}):
            self.assertEqual(self.pub.edited_by_a_person("tok", "D1"), "x@y")


class NoPaidCallTests(Base):
    def test_the_whole_flow_with_a_key_present_never_spends(self):
        # The transport is patched to fail (Base); urlopen too, for good measure.
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")):
            self.run_tool(self.tool.queue_out, self.q, 2)
            fill(self.q, {"uk:" + UK_BILL: answer_text(narrative())})
            self.run_tool(self.tool.queue_in, self.q, TODAY)
            for s in self.b.mb.subjects(self.conn):
                with redirect_stdout(io.StringIO()):
                    self.b.mb.write_one(self.conn, s, {}, TODAY, "sk-ant-test")
        self.assertTrue(bn.stored(self.conn, UK_BILL))

    def test_the_tool_never_reads_a_key(self):
        src = open(os.path.join(ROOT, "tools", "brief_narratives.py"), encoding="utf-8").read()
        src += open(os.path.join(ROOT, "src", "brief_narratives.py"), encoding="utf-8").read()
        for word in ("anthropic_api_key", "ANTHROPIC_API_KEY", "_default_transport", "load_secrets"):
            self.assertNotIn(word, src)


class JobTests(unittest.TestCase):
    def read(self, *path):
        with open(os.path.join(ROOT, *path), encoding="utf-8") as fh:
            return fh.read()

    def test_job_runs_the_session_judge_with_the_narrative_prompt(self):
        job = self.read("jobs", "brief-narratives.sh")
        self.assertTrue(os.access(os.path.join(ROOT, "jobs", "brief-narratives.sh"), os.X_OK))
        self.assertIn('GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Brief narratives}"', job)
        self.assertIn("# mini_run: commit briefs", job)
        steps = [job.index(s) for s in ("b.NARRATIVE_PROMPT",
                                        'bash tools/session_judge.sh tools/brief_narratives.py "$MAX" 1',
                                        'if [ "$jrc" -eq 3 ]',
                                        "python3 tools/db_state.py --push")]
        self.assertEqual(steps, sorted(steps))
        self.assertIn('MAX="${BRIEF_NARRATIVE_MAX:-6}"', job)

    def test_slot_and_heartbeat(self):
        import coverage
        self.assertIn("Brief narratives", coverage.ON_DEMAND)
        with open(os.path.join(ROOT, "ops", "launchd", "net.citizengo.parlmonitor.brief-narratives.plist"),
                  "rb") as fh:
            doc = plistlib.load(fh)
        self.assertEqual(doc["ProgramArguments"][-1], "brief-narratives")
        s = doc["StartCalendarInterval"]
        self.assertEqual((s["Weekday"], s["Hour"], s["Minute"]), (0, 18, 15))
        # Six one-brief rounds of at most CLAUDE_ROUND_TIMEOUT fit the job's limit.
        self.assertGreaterEqual(int(doc["EnvironmentVariables"]["JOB_TIMEOUT"]), 6 * 780 + 600)
        for path in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
            self.assertNotIn("brief-narratives", open(path, encoding="utf-8").read(), path)

    def test_before_the_builders_and_after_the_uk_judge(self):
        def slot(name):
            with open(os.path.join(ROOT, "ops", "launchd", "net.citizengo.parlmonitor.{0}.plist".format(name)),
                      "rb") as fh:
                s = plistlib.load(fh)["StartCalendarInterval"]
            return (s["Weekday"], s["Hour"], s["Minute"])
        mine = slot("brief-narratives")
        self.assertLess(slot("uk-session-judge"), mine)
        self.assertLess(slot("editions-session-judge"), mine)
        self.assertLess(mine, slot("de-weekly"))       # builds the German briefs, Sunday 20:00
        self.assertEqual(slot("monday-publish")[0], 1)  # builds the UK briefs, Monday 04:00

    def test_prompt_is_the_session_contract(self):
        p = bn.NARRATIVE_PROMPT
        for words in ("queue.md", "[[DRAFT HERE: <id>]]", "@@field_id@@", "never invent",
                      "British spelling, no em dashes", "Read or create no other file"):
            self.assertIn(words, p)
        self.assertNotIn("—", p)


if __name__ == "__main__":
    unittest.main()
