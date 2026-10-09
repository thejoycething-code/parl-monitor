"""The Canada federal edition (tools/ca_monitor.py). No network: a store built in memory."""

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cam = _load("ca_monitor")
TODAY = "2026-10-09"
C218 = "2nd reading of Bill C-218, An Act to amend the Criminal Code (medical assistance in dying)"


def store():
    conn = db.init_db(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    return conn


def bill(conn, number, title, areas, status, last_stage=None, last_at=None, introduced="2025-06-20",
         assent=None, parl=45, sess=1, kind="Private Member’s Bill", sponsor="Tamara Jansen",
         pid="105774"):
    conn.execute("INSERT INTO ca_bills (bill_key, parliament, session, number, long_title, status, "
                 "is_government, sponsor, sponsor_person_id, royal_assent_at, areas, bill_type, "
                 "introduced_at, last_stage, last_stage_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 ("{0}-{1}/{2}".format(parl, sess, number), parl, sess, number, title, status,
                  int("Government" in kind), sponsor, pid, assent, json.dumps(areas), kind,
                  introduced, last_stage, last_at))


def division(conn, number, date, subject, areas, bill_number=None, result="Negatived",
             chamber="commons", positions=(("1", "Yea", "Conservative"), ("2", "Nay", "Liberal"),
                                           ("3", "Nay", "Liberal"), ("4", "Paired", "Liberal"))):
    key = "{0}-45-1-{1}".format(chamber, number)
    conn.execute("INSERT INTO ca_divisions (division_key, chamber, parliament, session, number, date, "
                 "subject, result, yeas, nays, paired, abstentions, bill_number, areas, "
                 "positions_fetched) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
                 (key, chamber, 45, 1, number, date, subject, result, 1, 2,
                  1 if chamber == "commons" else None, 1 if chamber == "senate" else None,
                  bill_number, json.dumps(areas)))
    for pid, pos, party in positions:
        conn.execute("INSERT INTO ca_votes (division_key, person_id, position, party) VALUES (?,?,?,?)",
                     (key, pid, pos, party))
    return key


def petition(conn, pid, presented, prayer, areas, tier, score=None, why=None, mp="Arnold Viersen",
             sigs=30):
    conn.execute("INSERT INTO ca_petitions (petition_id, presented_number, kind, presented, prayer, "
                 "mp_person_id, mp_name, signatures, areas, tier, triage_score, why_it_matters) "
                 "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                 (pid, pid, "Paper petition", presented, prayer, mp, mp, sigs, json.dumps(areas),
                  tier, score, why))


class EditionTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        bill(self.conn, "C-218", "An Act to amend the Criminal Code (medical assistance in dying)",
             [2], "Bill defeated", "First reading in the House of Commons", "2025-06-20")
        bill(self.conn, "C-34", "An Act to enact the Digital Safety Act", [6, 7],
             "At consideration in committee in the House of Commons",
             "Second reading in the House of Commons", "2026-10-07", introduced="2026-06-10",
             kind="House Government Bill", sponsor="Marc Miller", pid=None)
        bill(self.conn, "C-300", "An Act respecting conscience rights of health professionals", [2],
             "At second reading in the House of Commons", "First reading in the House of Commons",
             "2026-10-06", introduced="2026-10-06", pid="999")
        bill(self.conn, "C-9", "Combatting Hate Act", [7, 8], "Royal assent received", "Royal assent",
             "2026-06-18", assent="2026-06-18T07:45:00-04:00", kind="House Government Bill")
        bill(self.conn, "C-50", "Border Act", [11], "At second reading in the House of Commons",
             "First reading in the House of Commons", "2026-10-06", introduced="2026-10-06")
        self.c218 = division(self.conn, 177, "2026-10-07T15:45:00", C218, [2], "C-218")
        # A Senate vote whose own title is neutral: its areas come from its bill.
        division(self.conn, 700500, "2026-10-08", "Motion in amendment - Bill C-9", [7, 8], "C-9",
                 result="Defeated", chamber="senate",
                 positions=(("senator-1", "Yea", "C"), ("senator-2", "Nay", "ISG"),
                            ("senator-3", "Abstention", "ISG")))
        division(self.conn, 176, "2026-10-07T15:30:00", "Opposition Motion (Diesel prices)", [])
        petition(self.conn, "451-01220", "2026-10-05", "We call on Parliament to pass C-218.", [2], 2,
                 3, "Supports Bill C-218 on MAID.")
        petition(self.conn, "451-01221", "2026-10-06", "We call on Parliament to pass C-218.", [2], 2,
                 3, "Supports Bill C-218 on MAID.", mp="Ted Falk")
        petition(self.conn, "451-01300", "2026-10-06", "Tariffs and misinformation.", [6], 2)
        petition(self.conn, "451-01301", "2026-10-06", "Protect children from pornography online.",
                 [6], 1)
        petition(self.conn, "451-01302", "2026-10-06", "Fund prison chaplains.", [8], 2, 1, "Marginal.")
        self.conn.execute("INSERT INTO ca_sittings (sitting_key, parliament, session, number, date) "
                          "VALUES ('45-1-145', 45, 1, 145, '2026-10-05')")
        self.conn.execute("INSERT INTO ca_speeches (speech_id, sitting_key, date, subject, speaker, "
                          "party, areas, text) VALUES (?,?,?,?,?,?,?,?)",
                          ("1", "45-1-145", "2026-10-05", "Petitions — Medical Assistance in Dying",
                           "Arnold Viersen (Peace River—Westlock, CPC)", "Conservative", "[2]",
                           "A LONG SPEECH TEXT THAT MUST NEVER APPEAR"))
        self.stance = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
        self.stance.write("divisions:\n"
                          "  - key: senate-45-1-700500\n    title: Martin-style amendment\n"
                          "    draft: true\n    yea: 2\n    why_yea: SECRET-DIRECTION\n"
                          "    nay: -1\n    why_nay: SECRET-DIRECTION\n"
                          "bills: []\n")
        self.stance.close()
        self.old = cam.STANCE
        cam.STANCE = self.stance.name

    def tearDown(self):
        cam.STANCE = self.old
        os.unlink(self.stance.name)

    def render(self):
        return cam.render_edition(self.conn, TODAY)

    def test_divisions_carry_result_split_and_what_matched(self):
        text = self.render()
        self.assertIn("## Divisions this week (2)", text)
        self.assertIn("**Negatived** 1-2, 1 paired; Lib 0-2, CPC 1-0", text)
        self.assertIn("matched on own text", text)
        # The Senate motion matches only through C-9's areas: marked as inherited.
        self.assertIn("**Defeated** 1-2-1 (Yea-Nay-Abst); ISG 0-1-1, C 1-0", text)
        self.assertIn("matched on bill only", text)
        self.assertNotIn("Diesel", text)

    def test_no_verdicts_and_no_em_dashes(self):
        text = self.render()
        self.assertNotIn("—", text)
        for word in ("a win", "a defeat", "victory", "good news", "bad news"):
            self.assertNotIn(word, text.lower())

    def test_bills_moved_new_live_assent_fallen(self):
        text = self.render()
        moved = text.split("## Bills that moved this week")[1].split("## New bills")[0]
        self.assertIn("C-34", moved)        # a stage completed this week
        self.assertIn("C-218", moved)       # divided on this week
        self.assertNotIn("C-50", text)      # migration only: never shown
        new = text.split("## New bills this week (1)")[1].split("## Live bills")[0]
        self.assertIn("C-300", new)
        self.assertIn("Royal Assent 2026-06-18", text.split("## Royal Assent this session (1)")[1])
        fallen = text.split("## Fallen (1)")[1].split("##")[0]
        self.assertIn("C-218", fallen)
        self.assertIn("defeated at a division on 2026-10-07", fallen)

    def test_an_earlier_sessions_bill_falls_whatever_its_status(self):
        # A new session that began this week: the last session's live bill fell.
        self.conn.execute("UPDATE ca_bills SET parliament=45, session=2, bill_key='45-2/'||number, "
                          "introduced_at='2026-10-01' WHERE number IN ('C-300', 'C-34')")
        bill(self.conn, "C-260", "Preventing Coercion of Persons Not Seeking Medical Assistance in "
             "Dying Act", [2], "At second reading in the House of Commons", parl=45, sess=1)
        self.conn.execute("UPDATE ca_bills SET introduced_at='2026-10-01' WHERE session=2")
        text = self.render()
        self.assertIn("45th Parliament, 2nd session", text)
        fallen = text.split("## Fallen")[1].split("## Debate")[0]
        self.assertIn("C-260", fallen)
        self.assertIn("fell at the end of the 45th Parliament, 1st session", fallen)
        live = text.split("## Live bills")[1].split("## Royal Assent")[0]
        self.assertNotIn("C-260", live)

    def test_petitions_fold_drives_and_hold_back_noise(self):
        text = self.render()
        section = text.split("## Petitions")[1].split("## Canada Gazette")[0]
        self.assertIn("(2 copies)", section)
        self.assertIn("Arnold Viersen, Ted Falk", section)
        self.assertIn("Supports Bill C-218 on MAID.", section)
        self.assertIn("*Unscored.* Protect children", section)       # tier 1, unjudged: shown
        self.assertNotIn("misinformation", section)                     # tier 2, unjudged: held
        self.assertNotIn("chaplains", section)                          # judged 1: held
        self.assertIn("2 text(s) held back", section)

    def test_debate_is_one_line_and_a_link_never_the_text(self):
        text = self.render()
        self.assertNotIn("A LONG SPEECH TEXT", text)
        self.assertIn("(https://www.ourcommons.ca/DocumentViewer/en/45-1/house/sitting-145/hansard)", text)
        self.assertIn("Petitions - Medical Assistance in Dying. 1 speech(es) by Arnold Viersen", text)

    def test_5ca_lists_unsigned_readings_and_never_a_direction(self):
        text = self.render()
        section = text.split("## 5CA status")[1].split("## Coverage")[0]
        self.assertIn("0 signed, 1 drafted and awaiting sign-off", section)
        self.assertIn("`senate-45-1-700500` Martin-style amendment: drafted, awaiting sign-off", section)
        self.assertIn("House division 177", section)                   # no reading at all
        self.assertIn("[C-300]", section)                               # a PMB with no reading
        self.assertNotIn("SECRET-DIRECTION", text)
        self.assertNotIn("+2", text)
        self.assertIn("reading drafted, awaiting sign-off: places nobody", text)
        self.assertIn("no reading yet: places nobody", text)

    def test_renders_without_any_score(self):
        self.conn.execute("UPDATE ca_petitions SET triage_score=NULL, why_it_matters=NULL")
        text = self.render()
        self.assertIn("**No item is scored yet**", text)
        self.assertNotIn("**[3]**", text)
        section = text.split("## Petitions")[1].split("## Canada Gazette")[0]
        self.assertIn("Protect children", section)
        self.assertNotIn("C-218.", section)                             # tier 2 unjudged: held

    def test_quiet_week_says_so(self):
        text = cam.render_edition(self.conn, "2026-12-30")
        self.assertIn("Parliament recorded no division on our ground this week", text)
        self.assertIn("## Divisions (none this week; last 30 days: 0)", text)
        self.assertIn("The latest on our ground", text)

    def test_dm_is_a_summary_with_the_link(self):
        msg = cam.dm_summary(self.conn, TODAY, os.path.join(ROOT, "editions", "ca-monitor-2026-10-09.md"))
        self.assertIn("Canada Federal Monitor - week ending 2026-10-09", msg)
        self.assertIn("2 division(s) on our ground", msg)
        self.assertIn("editions/ca-monitor-2026-10-09.md", msg)
        self.assertNotIn("—", msg)


class StageTests(unittest.TestCase):
    def test_a_senate_bill_counts_its_house_stages_second(self):
        s = {"royal_assent_at": None, "number": "S-209", "last_stage": "First reading in the House of Commons"}
        c = {"royal_assent_at": None, "number": "C-34", "last_stage": "Second reading in the House of Commons"}
        self.assertGreater(cam.stage_rank(s), cam.stage_rank(c))
        self.assertEqual(cam.stage_rank({"royal_assent_at": "2026", "number": "C-9", "last_stage": ""}), 11)


class WiringTests(unittest.TestCase):
    def test_both_callers_write_the_edition_and_commit_it(self):
        job = open(os.path.join(ROOT, "jobs", "ca-weekly.sh"), encoding="utf-8").read()
        flow = open(os.path.join(ROOT, ".github", "workflows", "ca-weekly.yml"), encoding="utf-8").read()
        for text in (job, flow):
            self.assertIn("python3 tools/ca_monitor.py --edition --dm", text)
            self.assertIn("editions/ca-monitor-$TODAY.md", text)
            # After the judge, before the store is published.
            self.assertLess(text.index("python3 tools/ca_triage.py"),
                            text.index("python3 tools/ca_monitor.py"))
            self.assertLess(text.index("python3 tools/ca_monitor.py"),
                            text.index("python3 tools/db_state.py --push"))
        self.assertIn("# mini_run: commit editions", job)
        self.assertIn("git add data/ editions/", flow)
        self.assertIn("U05LJP0BT61", job)
        self.assertIn("slack_dm_user_id: U05LJP0BT61", flow)


if __name__ == "__main__":
    unittest.main()
