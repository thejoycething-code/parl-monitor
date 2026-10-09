"""The US edition (tools/us_monitor.py). No network: a store built in memory."""

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


usm = _load("us_monitor")
ust = _load("us_triage")
TODAY = "2026-10-09"


def store():
    conn = db.init_db(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    return conn


def bill(conn, key, title, areas, action, at, introduced="2025-02-01", law=None, cosponsors=3,
         score=None, why=None):
    _c, btype, number = key.split("/")
    conn.execute("INSERT INTO us_bills (bill_key, congress, bill_type, number, title, areas, "
                 "latest_action, latest_action_at, introduced, law, cosponsors, sponsor_name, "
                 "triage_score, why_it_matters) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (key, 119, btype, int(number), title, json.dumps(areas), action, at, introduced,
                  law, cosponsors, "Rep. Steube, W. Gregory [R-FL-17]", score, why))


def vote(conn, key, chamber, roll, date, bill_key, legis, areas, own, result="Passed",
         positions=(("A1", "Yea", "R"), ("B1", "Nay", "D"), ("C1", "Yea", "R"))):
    conn.execute("INSERT INTO us_divisions (division_key, chamber, congress, session, roll, date, "
                 "legis_num, bill_key, question, result, yeas, nays, areas, own_areas) "
                 "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (key, chamber, 119, 2, roll, date, legis, bill_key, "On Passage", result,
                  2, 1, json.dumps(areas), json.dumps(own)))
    for bio, pos, party in positions:
        conn.execute("INSERT INTO us_votes (division_key, bioguide, position, party) VALUES (?,?,?,?)",
                     (key, bio, pos, party))


class StageTests(unittest.TestCase):
    def row(self, action, btype="hr", law=None):
        return {"latest_action": action, "bill_type": btype, "law": law}

    def test_stages_from_the_latest_action(self):
        cases = [("Became Public Law No: 119-12.", "hr", "Public Law 119-12", "Law (Public Law 119-12)"),
                 ("Passed Senate without amendment by Unanimous Consent.", "hr", None, "Passed both chambers"),
                 ("Passed House.", "s", None, "Passed both chambers"),
                 ("Received in the Senate.", "hr", None, "Passed one chamber"),
                 ("Cloture on the motion to proceed to the measure not invoked in Senate.", "s", None,
                  "Failed on the floor"),
                 ("Placed on the Union Calendar, Calendar No. 698.", "hr", None, "Reported or on the calendar"),
                 ("Referred to the House Committee on the Judiciary.", "hr", None, "In committee"),
                 ("Introduced in House", "hr", None, "Introduced")]
        for action, btype, law, want in cases:
            self.assertEqual(usm.stage(self.row(action, btype, law))[1], want, action)


class EditionTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        bill(self.conn, "119/hr/21", "Born-Alive Abortion Survivors Protection Act", [1],
             "Received in the Senate.", "2026-10-06", cosponsors=163)
        bill(self.conn, "119/hr/9", "Border Act", [11], "Referred to the Committee.", "2026-10-06")
        bill(self.conn, "119/sres/5", "A resolution designating National Adoption Day", [6],
             "Submitted in the Senate, considered, and agreed to without amendment.", "2026-01-01")
        bill(self.conn, "119/hr/99", "New Act", [5], "Referred to the Committee.", "2026-10-07",
             introduced="2026-10-07")
        bill(self.conn, "119/s/146", "TAKE IT DOWN Act", [7], "Became Public Law No: 119-12.",
             "2025-05-19", law="Public Law 119-12")

    def test_a_quiet_week_says_so_and_names_the_last_votes(self):
        vote(self.conn, "house-119-2-1", "house", 1, "2026-09-16", "119/hr/21", "H R 21", [1], [])
        text = usm.render_edition(self.conn, TODAY)
        self.assertIn("Congress recorded no vote on our ground this week", text)
        self.assertIn("The House last voted on 2026-09-16", text)

    def test_votes_show_the_party_split_and_whether_their_own_text_matched(self):
        vote(self.conn, "house-119-2-5", "house", 5, "2026-10-08", "119/hr/21", "H R 21", [1], [])
        text = usm.render_edition(self.conn, TODAY)
        self.assertIn("R 2-0, D 0-1", text)
        self.assertIn("matched on bill only", text)
        self.assertNotIn("Congress recorded no vote", text)

    def test_repeated_votes_fold_into_one_line(self):
        for n in range(3):
            vote(self.conn, "senate-119-2-{0}".format(n), "senate", n, "2026-10-0{0}".format(n + 5),
                 "119/hr/21", "H.R. 21", [1], [1], result="Cloture Rejected")
        lines = [l for l in usm.render_edition(self.conn, TODAY).split("\n")
                 if l.startswith("- ") and "[Senate vote" in l]
        self.assertEqual(len(lines), 1)
        self.assertIn("(x3, 2026-10-05 to 2026-10-07)", lines[0])

    def test_migration_only_is_never_shown(self):
        self.assertNotIn("Border Act", usm.render_edition(self.conn, TODAY))

    def test_agreed_simple_resolutions_are_counted_not_listed_as_live(self):
        text = usm.render_edition(self.conn, TODAY)
        live = text.split("## Live beyond committee")[1].split("## Most-backed")[0]
        self.assertNotIn("National Adoption Day", live)
        self.assertIn("1 simple resolution(s) agreed", live)
        self.assertIn("Born-Alive", live)

    def test_unscored_says_so_and_scored_shows_the_why(self):
        self.assertIn("No item is scored yet", usm.render_edition(self.conn, TODAY))
        self.conn.execute("UPDATE us_bills SET triage_score=3, why_it_matters='Puts a duty of "
                          "care on practitioners.' WHERE bill_key='119/hr/21'")
        text = usm.render_edition(self.conn, TODAY)
        self.assertNotIn("No item is scored yet", text)
        self.assertIn("**[3]**", text)
        self.assertIn("Puts a duty of care on practitioners.", text)

    def test_the_end_of_congress_counts_what_falls(self):
        self.assertIn("**3 bill(s) on our ground are pending and fall then unless enacted.**",
                      usm.render_edition(self.conn, TODAY))

    def test_no_em_dashes(self):
        bill(self.conn, "119/hr/77", "An Act — with a dash", [1], "Received in the Senate.",
             "2026-10-07")
        self.assertNotIn("—", usm.render_edition(self.conn, TODAY))

    def test_the_dm_is_short_and_links_the_edition(self):
        dm = usm.dm_summary(self.conn, TODAY, os.path.join(ROOT, "editions", "us-monitor-2026-10-09.md"))
        self.assertIn("US Congress Monitor - week ending 2026-10-09", dm)
        self.assertIn("editions/us-monitor-2026-10-09.md", dm)
        self.assertLess(len(dm.split("\n")), 15)


class JudgeQueueTests(unittest.TestCase):
    def test_the_queue_takes_bills_and_own_text_votes_only(self):
        conn = store()
        bill(conn, "119/hr/21", "Born-Alive", [1], "Received in the Senate.", "2026-10-06")
        bill(conn, "119/hr/9", "Border Act", [11], "Referred.", "2026-10-06")
        vote(conn, "house-119-2-1", "house", 1, "2026-09-16", "119/hr/21", "H R 21", [1], [])
        vote(conn, "senate-119-2-2", "senate", 2, "2026-09-17", "119/hr/21", "H.R. 21", [1], [1])
        ids = [i.id for i in ust.pending(conn)]
        self.assertEqual(sorted(ids), ["us_bills:119/hr/21", "us_divisions:senate-119-2-2"])

    def test_scores_are_written_once_and_rescore_requeues(self):
        conn = store()
        bill(conn, "119/hr/21", "Born-Alive", [1], "Received in the Senate.", "2026-10-06")

        class R:
            id, score, why_it_matters = "us_bills:119/hr/21", 3, "Why."
        self.assertEqual(ust.apply(conn, [R()]), 1)
        self.assertEqual(ust.pending(conn), [])
        self.assertEqual(ust.rescore(conn, "119/hr/21"), 1)
        self.assertEqual(len(ust.pending(conn)), 1)

    def test_an_amendment_votes_purpose_reaches_the_judge(self):
        conn = store()
        vote(conn, "house-119-1-245", "house", 245, "2025-09-10", "119/hr/3838", "H R 3838", [3], [3])
        conn.execute("UPDATE us_divisions SET amendment_text='to prohibit gender transition "
                     "procedures' WHERE division_key='house-119-1-245'")
        (item,) = ust.pending(conn)
        self.assertIn("Amendment: to prohibit gender transition procedures", item.text)

    def test_the_estimate_is_dollars_not_zero(self):
        self.assertGreater(ust.estimate_usd(769), 1.0)
        self.assertLess(ust.estimate_usd(769), 5.0)


if __name__ == "__main__":
    unittest.main()
