"""The Australian edition (tools/au_monitor.py), its judge (tools/au_triage.py)
and the aph.gov.au probe (tools/au_probe.py). No network: a store built in memory."""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


aum = _load("au_monitor")
aut = _load("au_triage")
aup = _load("au_probe")
TODAY = "2026-09-18"


def store():
    conn = db.init_db(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    return conn


def bill(conn, bill_id, title, areas, first="2026-03-01", stage=None, stage_date=None,
         act=None, parliament=48, score=None, why=None):
    conn.execute("INSERT INTO au_bills (bill_id, parliament, origin, title, first_date, last_stage, "
                 "last_stage_chamber, last_stage_date, act_id, act_name, assent_date, areas, "
                 "triage_score, why_it_matters) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (bill_id, parliament, "senate" if bill_id.startswith("s") else "house", title,
                  first, stage, "senate" if stage else None, stage_date,
                  act, (title.replace("Bill", "Act") if act else None),
                  ("2026-09-11" if act else None), json.dumps(areas), score, why))


def division(conn, key, date, number, areas, own, bills=(), ayes=22, noes=32, pairs=10,
             question="The question is that the motion be agreed to.", heading="Consideration of Legislation",
             chamber="senate", tier=None,
             votes=(("1", "Aye", "Liberal Party"), ("2", "No", "Australian Labor Party"),
                    ("3", "Paired", "Australian Labor Party"), ("4", "Paired", "Liberal Party"))):
    conn.execute("INSERT INTO au_divisions (division_key, chamber, parliament, date, number, "
                 "minor_heading, bill_ids, question, motion, ayes, noes, pairs, own_areas, areas, tier) "
                 "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (key, chamber, 48, date, number, heading, json.dumps(list(bills)), question,
                  "I move: That the bill be restored to the Notice Paper.", ayes, noes, pairs,
                  json.dumps(own), json.dumps(areas), tier))
    for pid, pos, party in votes:
        conn.execute("INSERT INTO au_votes (division_key, person_id, position, party) VALUES (?,?,?,?)",
                     (key, pid, pos, party))


class EditionTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        bill(self.conn, "s1500", "Sex Discrimination Amendment (Recognising Biological Sex) Bill 2026",
             [5], first="2026-07-01", stage="First Reading", stage_date="2026-07-01")
        bill(self.conn, "r7512", "Online Safety Amendment (Social Media Minimum Age) Bill 2026", [6, 7],
             first="2026-07-01", stage="Third Reading", stage_date="2026-09-16", act="C2026A00083")
        bill(self.conn, "r7401", "Migration Amendment (Combatting Migrant Exploitation) Bill 2025", [11])
        bill(self.conn, "r7327", "Appropriation Bill (No. 1) 2025-2026", [7], parliament=47)
        bill(self.conn, "r7600", "New Born Alive Bill 2026", [1], first="2026-09-15",
             stage="Second Reading", stage_date="2026-09-15")

    def test_a_quiet_week_says_so_and_names_the_last_sitting(self):
        division(self.conn, "senate-2026-07-01-16", "2026-07-01", 16, [5], [5], bills=["s1500"])
        text = aum.render_edition(self.conn, "2026-10-09")
        self.assertIn("Parliament recorded no division on our ground this week", text)
        self.assertIn("the Senate on 2026-07-01", text)

    def test_divisions_show_tally_pairs_and_party_split_and_no_verdict(self):
        division(self.conn, "senate-2026-09-15-8", "2026-09-15", 8, [5], [5])
        text = aum.render_edition(self.conn, TODAY)
        self.assertIn("**Negatived** 22-32, 10 pairs", text)
        self.assertIn("ALP 0-1, LIB 1-0; paired ALP 1, LIB 1", text)
        for word in ("victory", "defeat", " win", " loss", "good news", "bad news"):
            self.assertNotIn(word, text.lower())

    def test_an_inherited_area_is_marked_bill_only(self):
        division(self.conn, "senate-2026-09-10-6", "2026-09-10", 6, [6, 7], [], bills=["r7512"],
                 ayes=33, noes=23, pairs=0, question="The question is that the amendment on sheet 4104 be agreed to.")
        text = aum.render_edition(self.conn, TODAY)
        self.assertIn("**Agreed to** 33-23", text)
        self.assertIn("matched on bill only", text)
        self.assertIn("On: [r7512]", text)

    def test_repeated_divisions_fold_into_one_line(self):
        for n in range(3):
            division(self.conn, "senate-2026-09-1{0}-1".format(n + 4), "2026-09-1{0}".format(n + 4), 1,
                     [5], [], bills=["s1500"], question="The question is that the question be now put.")
        lines = [l for l in aum.render_edition(self.conn, TODAY).split("\n")
                 if l.startswith("- ") and "[division" in l]
        self.assertEqual(len(lines), 1)
        self.assertIn("(x3, 2026-09-14 to 2026-09-16)", lines[0])

    def test_migration_only_and_earlier_parliaments_are_never_shown(self):
        text = aum.render_edition(self.conn, TODAY)
        self.assertNotIn("Migrant Exploitation", text)
        self.assertNotIn("r7327", text)

    def test_sections_place_each_bill(self):
        text = aum.render_edition(self.conn, TODAY)
        new = text.split("## New bills this week")[1].split("## Before Parliament")[0]
        self.assertIn("r7600", new)
        moved = text.split("## Bills that moved this week")[1].split("## New bills")[0]
        self.assertIn("r7512", moved)
        live = text.split("## Before Parliament")[1].split("## Enacted")[0]
        self.assertIn("s1500", live)
        self.assertNotIn("r7512", live)
        enacted = text.split("## Enacted this Parliament")[1].split("## Coverage")[0]
        self.assertIn("C2026A00083", enacted)

    def test_coverage_says_plainly_what_aph_blocks(self):
        text = aum.render_edition(self.conn, TODAY)
        cov = text.split("## Coverage")[1]
        for thing in ("aph.gov.au", "explanatory memoranda", "sitting calendar", "Senate estimates",
                      "e-petitions", "Votes and Proceedings"):
            self.assertIn(thing, cov)

    def test_unscored_says_so_and_scored_shows_the_why(self):
        self.assertIn("No item is scored yet", aum.render_edition(self.conn, TODAY))
        self.conn.execute("UPDATE au_bills SET triage_score=3, why_it_matters='Defines sex as "
                          "biological in the Sex Discrimination Act.' WHERE bill_id='s1500'")
        text = aum.render_edition(self.conn, TODAY)
        self.assertNotIn("No item is scored yet", text)
        self.assertIn("**[3]**", text)
        self.assertIn("Defines sex as biological", text)

    def test_no_em_dashes(self):
        bill(self.conn, "r7700", "An Act — with a dash", [1])
        self.assertNotIn("—", aum.render_edition(self.conn, TODAY))

    def test_the_dm_is_short_and_links_the_edition(self):
        dm = aum.dm_summary(self.conn, TODAY, os.path.join(ROOT, "editions", "au-monitor-2026-09-18.md"))
        self.assertIn("Australian Parliament Monitor - week ending 2026-09-18", dm)
        self.assertIn("editions/au-monitor-2026-09-18.md", dm)
        self.assertLess(len(dm.split("\n")), 15)


class JudgeTests(unittest.TestCase):
    def test_the_queue_takes_current_bills_and_own_text_divisions_only(self):
        conn = store()
        bill(conn, "s1500", "Biological Sex Bill", [5])
        bill(conn, "r7401", "Migration Bill", [11])
        bill(conn, "r7327", "Old Bill", [7], parliament=47)
        division(conn, "senate-2026-09-15-8", "2026-09-15", 8, [5], [5])
        division(conn, "senate-2026-09-10-6", "2026-09-10", 6, [6, 7], [], bills=["r7512"])
        ids = sorted(i.id for i in aut.pending(conn))
        self.assertEqual(ids, ["au_bills:s1500", "au_divisions:senate-2026-09-15-8"])

    def test_scores_are_written_once_and_rescore_requeues(self):
        conn = store()
        bill(conn, "s1500", "Biological Sex Bill", [5])

        class R:
            id, score, why_it_matters = "au_bills:s1500", 3, "Why."
        self.assertEqual(aut.apply(conn, [R()]), 1)
        self.assertEqual(aut.pending(conn), [])
        self.assertEqual(aut.rescore(conn, "s1500"), 1)
        self.assertEqual(len(aut.pending(conn)), 1)

    def test_the_frame_is_australian_and_says_titles_only(self):
        self.assertIn("Australian Federal Parliament", aut.SYSTEM_PROMPT_AU)
        self.assertIn("TITLE ONLY", aut.SYSTEM_PROMPT_AU)

    def test_the_judge_is_gated_and_off(self):
        with open(os.path.join(ROOT, "jobs", "au-weekly.sh"), encoding="utf-8") as fh:
            job = fh.read()
        self.assertIn('if [ "$JUDGE" = "on" ]; then', job)
        with open(os.path.join(ROOT, ".github", "workflows", "au-weekly.yml"), encoding="utf-8") as fh:
            self.assertIn("AU_JUDGE: ${{ vars.AU_JUDGE }}", fh.read())


class JobTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "jobs", "au-weekly.sh"), encoding="utf-8") as fh:
            self.job = fh.read()

    def test_it_speaks_once_a_day(self):
        self.assertIn('git ls-files --error-unmatch "editions/au-monitor-$TODAY.md"', self.job)
        block = self.job.split('if git ls-files --error-unmatch "editions/au-monitor-$TODAY.md"')[1]
        rewrite, send = block.split("\nelse\n", 1)
        self.assertNotIn("--dm", rewrite)
        self.assertIn("--dm", send.split("\nfi")[0])

    def test_the_runner_commits_editions_and_the_dm_goes_to_christopher_alone(self):
        self.assertIn("\n# mini_run: commit editions\n", self.job)
        self.assertIn("U05LJP0BT61", self.job)
        with open(os.path.join(ROOT, ".github", "workflows", "au-weekly.yml"), encoding="utf-8") as fh:
            self.assertIn("git add data/ editions/", fh.read())


class FakeProber:
    def __init__(self, replies):
        self.replies, self.blocked = replies, {}

    def get(self, url):
        r = self.replies.get(url)
        if r == "refuse":
            from urllib.parse import urlsplit
            self.blocked[urlsplit(url).netloc] = "challenge at " + url
            return None
        return r


class ProbeTests(unittest.TestCase):
    def test_a_refused_host_is_never_asked_again(self):
        first = aup.TARGETS[0][1]
        rows = aup.probe(FakeProber({first: "refuse"}), log=lambda *_: None)
        www = [r for r in rows if "www.aph.gov.au" in r[1]]
        self.assertTrue(www[0][2].startswith("refused"))
        self.assertTrue(all(r[2].startswith("not asked") for r in www[1:]))

    def test_an_answer_carries_a_text_sample(self):
        url = aup.TARGETS[6][1]
        body = b"<html><title>Sitting calendar</title><body><h1>2026 sitting days</h1></body></html>"
        rows = aup.probe(FakeProber({url: (url, 200, "text/html", body)}), targets=[("cal", url)])
        self.assertEqual(rows[0][2], "answered")
        self.assertIn("2026 sitting days", rows[0][5])
        self.assertIn("| [cal](", aup.table(rows))

    def test_the_workflow_is_dispatch_only_and_writes_nothing(self):
        with open(os.path.join(ROOT, ".github", "workflows", "au-probe.yml"), encoding="utf-8") as fh:
            yml = fh.read()
        self.assertNotIn("schedule", yml)
        self.assertNotIn("db_state", yml)
        self.assertNotIn("git commit", yml)
        self.assertIn("contents: read", yml)


if __name__ == "__main__":
    unittest.main()
