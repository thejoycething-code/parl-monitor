"""Issue pages (Christopher, 2026-09-07: "Build the issue pages")."""

import datetime
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, issuepages  # noqa: E402

TODAY = datetime.date(2026, 9, 7)


def _conn():
    conn = db.init_db(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    from src import stance
    stance.ensure_table(conn)
    conn.execute("INSERT INTO bills_board (bill_id, title, house, stage, next_key_date, what_next, areas, status) VALUES "
                 "(4157, 'Terminally Ill Adults (End of Life) Bill', 'Commons', '2nd reading', '2026-09-11', 'Awaiting 2nd reading', '[2]', 'live')")
    conn.execute("INSERT INTO items (id, captured_at, source_feed, item_type, title, url, event_date, issue_areas, triage_score, why_it_matters) VALUES "
                 "('pq:1', '2026-09-06', 'pq', 'question', 'PQ 1: Hospices', 'u', '2026-09-03', '[2]', 2, 'Money for the alternative.')")
    conn.execute("INSERT INTO items (id, captured_at, source_feed, item_type, title, url, event_date, issue_areas, triage_score) VALUES "
                 "('pq:2', '2026-09-06', 'pq', 'question', 'Background', 'u', '2026-09-03', '[2]', 1)")
    conn.execute("INSERT INTO members VALUES (4858, 'Danny Kruger', 'Conservative', 'East Wiltshire', 'Commons', 1, NULL, NULL, NULL)")
    conn.execute("INSERT INTO members VALUES (4923, 'Kim Leadbeater', 'Labour', 'Spen Valley', 'Commons', 1, NULL, NULL, NULL)")
    rows = [(4858, '2026-06-20', 'debate', 'hansard:a', 'Spoke: Terminally Ill Adults (End of Life) Bill', '[2]'),
            (4923, '2026-06-20', 'debate', 'hansard:b', 'Spoke: Terminally Ill Adults (End of Life) Bill', '[2]'),
            (4858, '2026-06-20', 'vote', 'div:c2071:no', 'Voted No: Terminally Ill Adults (End of Life) Bill: Third Reading', '[2]'),
            (4923, '2026-06-20', 'vote', 'div:c2071:aye', 'Voted Aye: Terminally Ill Adults (End of Life) Bill: Third Reading', '[2]'),
            (4858, '2026-05-18', 'edm', 'edm:65859', 'Sponsored EDM: Hospice funding (re: hospice)', '[2]'),
            (4858, '2026-08-28', 'pq', 'pq:9', 'Hospices: Funding', '[2]'),
            (4858, '2025-01-01', 'pq', 'pq:old', 'Old question', '[2]')]
    conn.executemany("INSERT INTO mp_events (member_id, date, kind, ref, line, areas) VALUES (?,?,?,?,?,?)", rows)
    conn.execute("INSERT INTO stance VALUES ('hansard:a', -2, 'w', 'm', 't')")
    conn.execute("INSERT INTO stance VALUES ('hansard:b', 2, 'w', 'm', 't')")
    conn.execute("INSERT INTO pq_link VALUES ('9', '12345', '2026-08-20')")
    conn.execute("INSERT INTO petitions (id, action, url, state, signatures, areas, matched, tier, milestone, first_seen, last_seen) VALUES "
                 "(1, 'Fund hospices', 'https://petition.parliament.uk/petitions/1', 'open', 9000, '[2]', '[]', 1, '1,000 to a response', 'x', 'x')")
    return conn


class CollectTests(unittest.TestCase):
    def test_everything_on_the_area_is_gathered(self):
        d = issuepages.collect(_conn(), 2, today=TODAY)
        self.assertEqual([b["bill_id"] for b in d["bills"]], [4157])
        self.assertEqual([i["id"] for i in d["items"]], ["pq:1"])                 # score 1 stays out
        self.assertEqual(len(d["debates"]), 1)
        self.assertEqual((d["debates"][0]["speakers"], d["debates"][0]["with"], d["debates"][0]["against"]), (2, 1, 1))
        self.assertEqual((d["divisions"][0]["ayes"], d["divisions"][0]["noes"]), (1, 1))
        self.assertEqual(d["divisions"][0]["url"], "https://votes.parliament.uk/Votes/Commons/Division/2071")
        self.assertEqual(d["motions"][0]["url"], "https://edm.parliament.uk/early-day-motion/65859")
        self.assertEqual(d["questions"][0]["url"], "https://questions-statements.parliament.uk/written-questions/detail/2026-08-20/12345")
        self.assertEqual(d["questions_total"], 1)                                  # the 2025 question is outside the window
        self.assertEqual(d["petitions"][0]["where"], "Westminster")
        months = {m["month"]: m for m in d["months"]}
        self.assertEqual((months["2026-06"]["debate"], months["2026-06"]["vote"]), (2, 2))

    def test_another_area_is_empty(self):
        d = issuepages.collect(_conn(), 1, today=TODAY)
        self.assertEqual((d["bills"], d["items"], d["debates"], d["divisions"]), ([], [], [], []))


class BuildTests(unittest.TestCase):
    def test_pages_and_index_are_written_and_migration_has_none(self):
        out = tempfile.mkdtemp()
        names = {1: "Abortion", 2: "Assisted dying", 11: "Migration"}
        paths = issuepages.build(out, _conn(), names, today=TODAY, raw=None)
        self.assertEqual(sorted(os.path.basename(p) for p in paths), ["issue-abortion.html", "issue-assisted-dying.html", "issues.html"])
        page = open(os.path.join(out, "issue-assisted-dying.html"), encoding="utf-8").read()
        for s in ("Bills on the board", "In the editions (1)", "Activity by month", "Debates (1)", "Divisions (1)",
                  "Early day motions (1)", "Written questions (1, most recent 1)", "Petitions (1)", "Money for the alternative."):
            self.assertIn(s, page, s)
        index = open(os.path.join(out, "issues.html"), encoding="utf-8").read()
        self.assertIn('href="/issue-assisted-dying.html"', index)
        self.assertNotIn("Migration", index)

    def test_the_publish_builds_them_and_the_nav_links_them(self):
        src = open(os.path.join(ROOT, "run_monday.py"), encoding="utf-8").read()
        self.assertIn("_issuepages.build(", src)
        self.assertIn('<a href="/issues.html">Issue pages</a>', open(os.path.join(ROOT, "src", "partner.py"), encoding="utf-8").read())
        wf = open(os.path.join(ROOT, ".github", "workflows", "monday-publish.yml"), encoding="utf-8").read()
        self.assertIn("partner_site/issue-*.html", wf)


if __name__ == "__main__":
    unittest.main()
