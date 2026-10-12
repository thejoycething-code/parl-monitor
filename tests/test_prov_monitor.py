"""The provinces edition (tools/prov_monitor.py) and its judge
(tools/prov_triage.py). No network: a store built in memory."""

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, prov_store as ps, triage  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pm = _load("prov_monitor")
pt = _load("prov_triage")
TODAY, SINCE = "2026-10-14", "2026-10-07"

STANCE = """divisions:
  - key: ab-31-3-2026-10-08-1
    yea: 2
    why_yea: "for"
    nay: -2
    why_nay: "against"
  - key: ab-31-3-2026-10-08-2
    yea: 1
    nay: -1
    draft: true
  - key: ab-31-3-2026-10-09-1
    placeable: false
    reason: "Unanimous: tells no member apart."
bills: []
"""


def store():
    conn = db.init_db(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    return conn


def member(conn, prov, key, name, party):
    conn.execute("INSERT INTO prov_members (prov, member_key, name, party, sitting) VALUES (?,?,?,?,1)",
                 (prov, key, name, party))


def bill(conn, key, title, areas, stages=(), assent=None, gov=1, first_seen="2026-10-01"):
    prov, rest = key.split("-", 1)
    leg, sess = rest.split("/")[0].split("-")
    ps.store_bill(conn, {"bill_key": key, "prov": prov, "legislature": int(leg), "session": int(sess),
                         "number": key.split("/")[1], "title_en": title, "is_government": gov,
                         "stages": list(stages), "royal_assent": assent, "areas": areas,
                         "page_url": "https://example.org/" + key}, when=first_seen)


def division(conn, key, bill_key, areas, date, kind="recorded", votes=(), first_seen=None,
             stage="Third Reading", question=None, result="Carried"):
    prov, leg, sess = key.split("-")[:3]
    ps.store_division(conn, {
        "division_key": key, "prov": prov, "legislature": int(leg), "session": int(sess),
        "date": date, "seq": key.rsplit("-", 1)[1], "kind": kind, "bill_key": bill_key,
        "stage": stage, "result": result, "question": question,
        "yeas": sum(v[1] == "Yea" for v in votes) if kind == "recorded" else None,
        "nays": sum(v[1] == "Nay" for v in votes) if kind == "recorded" else None,
        "areas": areas, "positions_ok": 1 if kind == "recorded" else None,
        "source_url": "https://example.org/vp/" + key,
        "votes": [{"position": pos, "ordinal": i, "raw_label": m, "member_key": m,
                   "party_at_vote": party} for i, (m, pos, party) in enumerate(votes)]},
        when=first_seen or date)


def speech(conn, prov, sid, member_key, date, subject, excerpt, areas, first_seen=None):
    conn.execute("INSERT INTO prov_speeches (speech_id, prov, sitting_key, date, subject, member_key, "
                 "speaker_label, areas, excerpt, first_seen, seq, tier, source_url) "
                 "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (sid, prov, sid.rsplit("-", 1)[0], date, subject, member_key, member_key,
                  json.dumps(areas), excerpt, first_seen or date, int(sid.rsplit("-", 1)[1]), 1,
                  "https://example.org/hansard/" + sid))


VOTES = (("a1", "Yea", "United Conservative"), ("a2", "Yea", "United Conservative"),
         ("a3", "Nay", "Alberta New Democratic Party"))


class EditionTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        self.tmp = tempfile.TemporaryDirectory()
        self.stance = os.path.join(self.tmp.name, "stance.yaml")
        with open(self.stance, "w", encoding="utf-8") as fh:
            fh.write(STANCE)
        self.sheets = os.path.join(self.tmp.name, "5ca")
        os.makedirs(self.sheets)
        with open(os.path.join(self.sheets, "prov-5ca-ab-gender-medicine-children.csv"), "w",
                  encoding="utf-8") as fh:
            fh.write("Decision-Maker,++,+,0,-,--\n"
                     '"Totals - 87 sitting decision-makers (3 former listed, not counted)",47,0,5,0,35\n')
        for k, n, p in (("a1", "Danielle Smith", "United Conservative"),
                        ("a2", "Adriana LaGrange", "United Conservative"),
                        ("a3", "Rakhi Pancholi", "Alberta New Democratic Party")):
            member(self.conn, "ab", k, n, p)
        bill(self.conn, "ab-31-3/9", "Health Statutes Amendment Act, 2026", [3],
             stages=[{"stage": "First Reading", "date": "2026-10-01"},
                     {"stage": "Third Reading", "date": "2026-10-08"},
                     {"stage": "Royal Assent", "date": "2026-10-09"}])
        bill(self.conn, "ab-31-3/10", "Budget Act", [], stages=[{"stage": "First Reading", "date": "2026-10-08"}])
        division(self.conn, "ab-31-3-2026-10-08-1", "ab-31-3/9", [3], "2026-10-08", votes=VOTES)
        division(self.conn, "ab-31-3-2026-10-08-2", "ab-31-3/9", [3], "2026-10-08", votes=VOTES,
                 stage="Second Reading")
        division(self.conn, "ab-31-3-2026-10-09-3", "ab-31-3/9", [3], "2026-10-09", kind="voice",
                 stage="Committee of the Whole", result="Agreed to")
        division(self.conn, "ab-31-3-2026-10-09-4", "ab-31-3/10", [], "2026-10-09", votes=VOTES)
        speech(self.conn, "ab", "ab-31-3-2026-10-08-12", "a3", "2026-10-08", "Bill 9",
               "This bill — puberty blockers", [3])
        speech(self.conn, "ab", "ab-31-3-2026-10-08-14", "a3", "2026-10-08", "Bill 9",
               "And again", [3])
        speech(self.conn, "ab", "ab-31-3-2026-10-08-20", "a1", "2026-10-08", "Border", "Migration", [11])
        self.conn.commit()

    def tearDown(self):
        self.tmp.cleanup()

    def render(self):
        return pm.render_edition(self.conn, TODAY, SINCE, stance_path=self.stance,
                                 sheet_dir=self.sheets)

    def test_an_active_province_gets_its_section_and_the_quiet_ones_one_line(self):
        text = self.render()
        self.assertIn("## Alberta", text)
        self.assertNotIn("## Quebec", text)
        quiet = next(ln for ln in text.splitlines() if ln.startswith("**Quiet this week**"))
        for name in ("Saskatchewan", "British Columbia", "Manitoba", "Ontario", "Quebec",
                     "New Brunswick", "Newfoundland and Labrador", "Nova Scotia"):
            self.assertIn(name, quiet)
        self.assertNotIn("Alberta", quiet)
        self.assertIn("Prince Edward Island", text)

    def test_divisions_carry_their_party_split_and_tally_never_a_verdict(self):
        text = self.render()
        self.assertIn("Party split (Yea-Nay): UCP 2-0, NDP 0-1.", text)
        self.assertIn("Carried 2-1", text)
        for word in ("win", "defeat", "victory"):
            self.assertNotRegex(text.lower(), r"\b{0}\b".format(word))

    def test_a_direction_only_where_the_reading_is_signed(self):
        text = self.render()
        self.assertIn("Signed reading (config/prov_stance.yaml): Yea +2, Nay -2.", text)
        # The draft reading of the second reading prints no direction.
        self.assertEqual(text.count("Yea +"), 1)
        self.assertNotIn("Yea +1", text)

    def test_voice_decisions_say_there_is_no_member_record(self):
        self.assertIn("on voice, no member record", self.render())

    def test_a_division_off_our_ground_is_not_shown(self):
        self.assertNotIn("Budget Act", self.render())

    def test_bills_assented_and_speeches_folded_one_line_with_a_link(self):
        text = self.render()
        self.assertIn("**Royal assent** · [Bill 9 (31-3)]", text)
        self.assertIn("received royal assent", text)
        self.assertIn("(2 turns)", text)
        self.assertIn("[Hansard](https://example.org/hansard/", text)
        self.assertNotIn("Migration", text.split("## Coverage")[0].replace(
            "Migration is matched", ""))

    def test_the_5ca_headline_comes_from_the_sheets_and_counts_signed_readings(self):
        text = self.render()
        self.assertIn("**5CA, signed readings only:** 1 confirmed division reading(s).", text)
        self.assertIn("Gender medicine children: ++ 47 · + 0 · 0 (not placed) 5 · - 0 · -- 35 "
                      "(of 87 sitting)", text)

    def test_no_em_dashes(self):
        self.assertNotIn("—", self.render())

    def test_a_quiet_week_says_so(self):
        text = pm.render_edition(self.conn, "2026-12-01", "2026-11-24", stance_path=self.stance,
                                 sheet_dir=self.sheets)
        self.assertIn("Nothing on our ground in any province this week", text)
        self.assertNotIn("## Alberta", text)

    def test_a_record_collected_late_is_shown_and_marked(self):
        division(self.conn, "ab-31-3-2026-09-30-1", "ab-31-3/9", [3], "2026-09-30", votes=VOTES,
                 first_seen="2026-10-10")
        division(self.conn, "ab-31-3-2026-09-29-1", "ab-31-3/9", [3], "2026-09-29", votes=VOTES,
                 first_seen="2026-09-29")
        got = pm.divisions(self.conn, "ab", SINCE, TODAY)
        keys = {d["division_key"]: w for w, d in got}
        self.assertEqual(keys.get("ab-31-3-2026-09-30-1"), "late")
        self.assertNotIn("ab-31-3-2026-09-29-1", keys)
        self.assertIn("_(collected late)_", self.render())

    def test_bills_fall_when_the_next_session_opens(self):
        bill(self.conn, "ab-31-2/5", "Education Amendment Act", [6],
             stages=[{"stage": "First Reading", "date": "2026-03-01"}])
        bill(self.conn, "ab-31-2/6", "Passed Act", [6],
             stages=[{"stage": "Royal Assent", "date": "2026-04-01"}])
        division(self.conn, "ab-31-2-2026-03-02-1", None, [], "2026-03-02", votes=VOTES)
        text = self.render()
        self.assertIn("**Fell with session 31-2**", text)
        self.assertIn("Education Amendment Act", text)
        self.assertNotIn("Passed Act", text)

    def test_scores_order_and_annotate_when_the_judge_has_run(self):
        self.conn.execute("INSERT INTO prov_scores (item, prov, score, why) VALUES (?,?,?,?)",
                          ("prov_bills:ab-31-3/9", "ab", 3, "Restricts puberty blockers."))
        text = self.render()
        self.assertIn("**[3]**", text)
        self.assertIn("_Restricts puberty blockers._", text)
        self.assertNotIn("No item is scored", text)

    def test_an_ownerless_act_line_is_refused(self):
        with self.assertRaises(ValueError):
            pm.refuse_ownerless_act("- [ACT] write to the minister")
        pm.refuse_ownerless_act("- [ACT] write to the minister, owner: Greg")

    def test_the_dm_goes_to_christopher_alone(self):
        text = pm.dm_summary(self.conn, TODAY, SINCE, path=os.path.join(
            ROOT, "editions", "prov-monitor-2026-10-14.md"))
        self.assertIn("*Alberta*", text)
        self.assertIn("editions/prov-monitor-2026-10-14.md", text)
        sent = {}
        from src import publish
        real_dm, real_secrets = publish.slack_dm, publish.load_secrets
        publish.slack_dm = lambda secrets, t: sent.update(secrets) or "sent"
        publish.load_secrets = lambda: {"slack_dm_user_id": "USOMEONEELSE", "slack_bot_token": "x"}
        try:
            pm.send_dm(text)
        finally:
            publish.slack_dm, publish.load_secrets = real_dm, real_secrets
        self.assertEqual(sent["slack_dm_user_id"], "U05LJP0BT61")


class JudgeTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        bill(self.conn, "ab-31-3/9", "Health Statutes Amendment Act, 2026", [3],
             stages=[{"stage": "First Reading", "date": "2026-10-01"}])
        bill(self.conn, "ab-31-3/10", "Budget Act", [], stages=[])
        bill(self.conn, "ab-31-3/11", "Border Act", [11], stages=[])
        division(self.conn, "ab-31-3-2026-10-08-1", "ab-31-3/9", [3], "2026-10-08", votes=VOTES)
        division(self.conn, "ab-31-3-2026-10-08-2", "ab-31-3/10", [6], "2026-10-08", votes=VOTES,
                 question="That the Assembly affirm parents' rights")
        division(self.conn, "ab-31-3-2026-10-08-3", None, [1], "2026-10-08", votes=VOTES,
                 question="Safe access zones motion")
        speech(self.conn, "ab", "ab-31-3-2026-10-08-12", "a3", "2026-10-08", "Bill 9", "blockers", [3])
        speech(self.conn, "ab", "ab-31-1-2024-11-19-12", "a3", "2024-11-19", "Bill 27", "old", [6])
        self.conn.commit()

    def ids(self, **kw):
        return [i.id for i in pt.pending(self.conn, TODAY, **kw)]

    def test_what_is_judged(self):
        ids = self.ids()
        self.assertIn("prov_bills:ab-31-3/9", ids)
        self.assertNotIn("prov_bills:ab-31-3/10", ids)          # off our ground
        self.assertNotIn("prov_bills:ab-31-3/11", ids)          # migration only
        # A division on a bill on our ground takes the bill's score: never paid twice.
        self.assertNotIn("prov_divisions:ab-31-3-2026-10-08-1", ids)
        # Divisions whose areas are their own are judged.
        self.assertIn("prov_divisions:ab-31-3-2026-10-08-2", ids)
        self.assertIn("prov_divisions:ab-31-3-2026-10-08-3", ids)
        self.assertIn("prov_speeches:ab-31-3-2026-10-08-12", ids)
        self.assertNotIn("prov_speeches:ab-31-1-2024-11-19-12", ids)   # beyond RECENT_DAYS
        self.assertIn("prov_speeches:ab-31-1-2024-11-19-12", self.ids(all_speeches=True))

    def test_scored_once_ever_and_a_rescore_requeues(self):
        n = pt.apply(self.conn, [triage.TriageResult(id="prov_bills:ab-31-3/9", score=3, areas=[3],
                                                      why_it_matters="Restricts blockers.")],
                     today=TODAY)
        self.assertEqual(n, 1)
        self.assertNotIn("prov_bills:ab-31-3/9", self.ids())
        # A Hansard day read again rewrites its speeches; the score lives apart.
        pt.apply(self.conn, [triage.TriageResult(id="prov_speeches:ab-31-3-2026-10-08-12", score=2, areas=[3],
                                                  why_it_matters="x")], today=TODAY)
        self.conn.execute("DELETE FROM prov_speeches WHERE sitting_key='ab-31-3-2026-10-08'")
        speech(self.conn, "ab", "ab-31-3-2026-10-08-12", "a3", "2026-10-08", "Bill 9", "blockers", [3])
        self.assertNotIn("prov_speeches:ab-31-3-2026-10-08-12", self.ids())
        self.assertEqual(pt.rescore(self.conn, "ab-31-3/9"), 1)
        self.assertIn("prov_bills:ab-31-3/9", self.ids())

    def test_the_frame_is_provincial(self):
        self.assertIn("Canadian provinces monitor", pt.SYSTEM_PROMPT_PROV)
        self.assertNotEqual(pt.SYSTEM_PROMPT_PROV, triage.SYSTEM_PROMPT)

    def test_the_dry_run_estimate(self):
        """Measured per-item tokens at the judge's rates: about $2.38 a thousand."""
        self.assertGreater(pt.estimate_usd(len(pt.pending(self.conn, TODAY))), 0)
        self.assertAlmostEqual(pt.estimate_usd(1000), 2.38, places=2)


class WiringTests(unittest.TestCase):
    """Both callers of the provinces weekly run the judge (gated) and the
    edition after the collectors, and commit editions/."""

    def read(self, *path):
        return open(os.path.join(ROOT, *path), encoding="utf-8").read()

    def test_the_mini_job_runs_the_gated_judge_then_the_edition(self):
        job = self.read("jobs", "prov-weekly.sh")
        self.assertIn("# mini_run: commit editions", job)
        self.assertIn('if [ "$JUDGE" = "on" ]', job)
        self.assertIn("gh variable get PROV_JUDGE", job)
        last_speech = job.index("tools/prov_speeches.py --prov qc")
        self.assertLess(last_speech, job.index("python3 tools/prov_triage.py"))
        self.assertLess(job.index("python3 tools/prov_triage.py"), job.index("python3 tools/prov_monitor.py"))
        self.assertLess(job.rindex("tools/prov_5ca.py"), job.index("python3 tools/prov_monitor.py"))
        self.assertIn("editions/prov-monitor-$TODAY.md", job)     # speaks once a day

    def test_the_workflow_gates_the_judge_on_the_variable(self):
        flow = self.read(".github", "workflows", "prov-weekly.yml")
        self.assertIn("vars.PROV_JUDGE == 'on'", flow)
        self.assertIn("git add data/ editions/", flow)
        self.assertIn("slack_dm_user_id: U05LJP0BT61", flow)


if __name__ == "__main__":
    unittest.main()
