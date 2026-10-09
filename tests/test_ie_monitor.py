"""The Irish edition (tools/ie_monitor.py) and judge (tools/ie_triage.py).
No network: a store built in memory."""

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


iem = _load("ie_monitor")
iet = _load("ie_triage")
TODAY = "2026-10-09"


def store():
    conn = db.init_db(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    return conn


def bill(conn, key, title, areas, stage="Second Stage", house="dail/34", at="2026-05-07",
         introduced="2026-01-20", status="Current", alive=1, act=None, origin="dail",
         score=None, why=None, source="Private Member"):
    year, number = key.split("/")
    conn.execute("INSERT INTO ie_bills (bill_key, year, number, title, areas, last_stage, "
                 "last_stage_house, last_stage_at, introduced, status, alive, act, origin_house, "
                 "triage_score, why_it_matters, source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (key, int(year), int(number), title, json.dumps(areas), stage, house, at,
                  introduced, status, alive, act, origin, score, why, source))
    conn.execute("INSERT INTO ie_sponsors (bill_key, sponsor, member_code, name, is_primary) "
                 "VALUES (?,?,?,?,1)", (key, "Ruth-Coppinger.D.2014-05-23", "Ruth-Coppinger.D.2014-05-23",
                                        "Ruth Coppinger"))


def division(conn, key, date, bill_key, areas, own, subject="Question put:", outcome="Lost",
             chamber="dail", amendment=None, ref=None, title="X Bill 2026: Second Stage",
             votes=(("A", "Yes", "Sinn Féin"), ("B", "No", "Fianna Fáil"), ("C", "No", "Fianna Fáil"),
                    ("D", "Abstain", "Labour Party"))):
    conn.execute("INSERT INTO ie_divisions (division_key, chamber, house_key, date, vote_id, "
                 "debate_title, subject, outcome, ta, nil, staon, bill_key, areas, own_areas, "
                 "amendment_text, amendment_ref) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (key, chamber, "dail/34", date, key.rsplit("/", 1)[-1], title, subject, outcome,
                  1, 2, 1, bill_key, json.dumps(areas), json.dumps(own), amendment, ref))
    for code, pos, party in votes:
        conn.execute("INSERT INTO ie_votes (division_key, member_code, position, party) "
                     "VALUES (?,?,?,?)", (key, code, pos, party))


class EditionTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        bill(self.conn, "2026/47", "Health (Abolition of Three Day Wait Rule) (Amendment) Bill 2026", [1])
        bill(self.conn, "2026/91", "Migration Pact Bill 2026", [11])
        bill(self.conn, "2024/50", "Voluntary Assisted Dying Bill 2024", [2], house="dail/33",
             at="2024-07-01", alive=0)
        bill(self.conn, "2026/74", "Contraception Bill 2026", [1], stage="Enacted", house=None,
             status="Enacted", alive=0, act="Act 32 of 2026", at="2026-07-21", source="Government")
        bill(self.conn, "2026/40", "Reproductive Rights (Amendment) Bill 2026", [1],
             stage="First Stage", status="Defeated", alive=0, at="2026-04-28")
        bill(self.conn, "2026/99", "New Online Bill 2026", [7], stage="First Stage",
             at="2026-10-07", introduced="2026-10-07")

    def test_a_quiet_week_says_so_and_names_the_last_divisions(self):
        division(self.conn, "dail/34/2026-06-17/vote_149", "2026-06-17", "2026/47", [1], [])
        text = iem.render_edition(self.conn, TODAY)
        self.assertIn("The Oireachtas recorded no division on our ground this week", text)
        self.assertIn("The Dáil last divided on 2026-06-17", text)
        # A quiet month still shows the latest fight.
        self.assertIn("The latest on our ground", text)

    def test_party_split_with_abstentions_and_what_matched(self):
        division(self.conn, "dail/34/2026-10-07/vote_5", "2026-10-07", "2026/47", [1], [])
        text = iem.render_edition(self.conn, TODAY)
        self.assertIn("FF 0-2, SF 1-0, Lab 0-0-1", text)
        self.assertIn("1-2-1 (Tá-Níl-Staon)", text)
        self.assertIn("matched on bill only", text)
        self.assertNotIn("recorded no division", text)

    def test_an_amendment_that_matched_on_its_own_says_so_and_shows_its_text(self):
        division(self.conn, "dail/34/2026-10-07/vote_6", "2026-10-07", "2026/47", [1], [1],
                 subject="Amendment put:", amendment="I move amendment No. 3: to insert abortion",
                 ref="amendment No. 3")
        text = iem.render_edition(self.conn, TODAY)
        self.assertIn("matched on amendment", text)
        self.assertIn("I move amendment No. 3", text)

    def test_amendments_read_and_blank_fold_into_a_count(self):
        for n in range(3):
            division(self.conn, "dail/34/2026-10-07/vote_{0}".format(20 + n), "2026-10-07",
                     "2026/47", [1], [], subject="Amendment put:",
                     amendment="I move amendment No. {0}: to delete line 4".format(n),
                     ref="amendment No. {0}".format(n))
        text = iem.render_edition(self.conn, TODAY)
        self.assertIn("3 amendment division(s) on", text)
        self.assertNotIn("to delete line 4", text)

    def test_repeated_divisions_fold_into_one_line(self):
        for n in range(3):
            division(self.conn, "dail/34/2026-10-0{0}/vote_{0}".format(n + 5), "2026-10-0{0}".format(n + 5),
                     "2026/47", [1], [1])
        lines = [l for l in iem.render_edition(self.conn, TODAY).split("\n")
                 if l.startswith("- ") and "[division]" in l]
        self.assertEqual(len(lines), 1)
        self.assertIn("(x3, 2026-10-05 to 2026-10-07)", lines[0])

    def test_migration_only_is_never_shown(self):
        self.assertNotIn("Migration Pact", iem.render_edition(self.conn, TODAY))

    def test_sections_place_bills_by_liveness_not_status(self):
        text = iem.render_edition(self.conn, TODAY)
        live = text.split("## Live bills")[1].split("## Enacted")[0]
        self.assertIn("Three Day Wait", live)
        self.assertNotIn("Voluntary Assisted Dying", live)
        lapsed = text.split("## Lapsed and not restored")[1].split("## Coverage")[0]
        self.assertIn("Voluntary Assisted Dying", lapsed)
        self.assertIn("Act 32 of 2026", text.split("## Enacted")[1].split("## Defeated")[0])
        self.assertIn("Reproductive Rights", text.split("## Defeated")[1].split("## Lapsed")[0])
        self.assertIn("New Online Bill", text.split("## New bills this week")[1].split("## Live")[0])

    def test_unscored_says_so_and_scored_shows_the_why(self):
        self.assertIn("No item is scored yet", iem.render_edition(self.conn, TODAY))
        self.conn.execute("UPDATE ie_bills SET triage_score=3, why_it_matters='Removes the wait.' "
                          "WHERE bill_key='2026/47'")
        text = iem.render_edition(self.conn, TODAY)
        self.assertNotIn("No item is scored yet", text)
        self.assertIn("**[3]**", text)
        self.assertIn("Removes the wait.", text)

    def test_dates_count_down_and_recent_ones_stay(self):
        text = iem.render_edition(self.conn, TODAY)
        self.assertIn("**2026-10-06** (3 days ago): Budget 2027", text)
        self.assertIn("2 live bill(s) on our ground today", text)

    def test_no_verdict_words_and_no_em_dashes(self):
        bill(self.conn, "2026/98", "An Act — with a dash", [1])
        division(self.conn, "dail/34/2026-10-07/vote_7", "2026-10-07", "2026/47", [1], [1])
        text = iem.render_edition(self.conn, TODAY)
        self.assertNotIn("—", text)
        import re
        for word in (r"\bwin\b", r"\bvictory\b", r"\bdefeat for\b", r"\bblow to\b"):
            self.assertIsNone(re.search(word, text.lower()), word)

    def test_the_dm_is_short_and_links_the_edition(self):
        dm = iem.dm_summary(self.conn, TODAY, os.path.join(ROOT, "editions", "ie-monitor-2026-10-09.md"))
        self.assertIn("Ireland Oireachtas Monitor - week ending 2026-10-09", dm)
        self.assertIn("editions/ie-monitor-2026-10-09.md", dm)
        self.assertLess(len(dm.split("\n")), 15)


class JudgeQueueTests(unittest.TestCase):
    def test_the_queue_takes_bills_and_own_text_divisions_only(self):
        conn = store()
        bill(conn, "2026/47", "Three Day Wait", [1])
        bill(conn, "2026/91", "Migration Pact Bill", [11])
        division(conn, "dail/34/2026-06-17/vote_1", "2026-06-17", "2026/47", [1], [])
        division(conn, "dail/34/2026-06-17/vote_2", "2026-06-17", "2026/47", [1], [1])
        ids = sorted(i.id for i in iet.pending(conn))
        self.assertEqual(ids, ["ie_bills:2026/47", "ie_divisions:dail/34/2026-06-17/vote_2"])

    def test_scores_are_written_once_and_rescore_requeues(self):
        conn = store()
        bill(conn, "2026/47", "Three Day Wait", [1])

        class R:
            id, score, why_it_matters = "ie_bills:2026/47", 3, "Why."
        self.assertEqual(iet.apply(conn, [R()]), 1)
        self.assertEqual(iet.pending(conn), [])
        self.assertEqual(iet.rescore(conn, "2026/47"), 1)
        self.assertEqual(len(iet.pending(conn)), 1)

    def test_the_frame_is_irish(self):
        self.assertIn("Oireachtas", iet.SYSTEM_PROMPT_IE)
        self.assertNotIn("CitizenGO UK's parliamentary monitor", iet.SYSTEM_PROMPT_IE)

    def test_the_estimate_is_small_and_not_zero(self):
        self.assertGreater(iet.estimate_usd(42), 0.01)
        self.assertLess(iet.estimate_usd(42), 1.0)


if __name__ == "__main__":
    unittest.main()
