"""The action-window rule (docs/parl-monitor-devolved-fix.md, 2026-08-31).

Jurisdiction was a proxy for actionability: everything in the devolved
stores was unbriefable by construction. The rule replaces that with three
conditions on the ITEM -- open response window, taxonomy score at the
unchanged threshold, response open to us -- and everything failing them
stays exactly where it was: watching brief, recorded, not briefed.
"""

import datetime
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import actionable, db, digest

TODAY = "2026-08-31"


def store(rows):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    for r in rows:
        conn.execute(
            "INSERT INTO dg_consultations (key, nation, title, url, summary, "
            "opened, closes, areas, tier, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)", r)
    conn.commit()
    return conn


def row(key, closes, areas="[6]", nation="ni", title=None, summary="",
        first_seen="2026-08-22", opened="2026-07-01", tier=1):
    return (key, nation, title or key, "https://x/" + key, summary,
            opened, closes, areas, tier, first_seen, TODAY)


class ActionWindowTests(unittest.TestCase):
    def test_an_open_dated_consultation_on_our_ground_is_actionable(self):
        conn = store([row("re-syllabus", "2026-09-30")])
        got = actionable.devolved_actionable(conn, TODAY)
        self.assertEqual([c["key"] for c in got], ["re-syllabus"])
        self.assertEqual(got[0]["nation_label"], "N. Ireland")

    def test_closing_today_is_still_open(self):
        # A response can still be filed on the closing day. The Scottish
        # justice consultation closed on the very day Edition 5 generated;
        # the rule must not write off the last day.
        conn = store([row("justice", TODAY, nation="scotland", areas="[5]")])
        self.assertEqual(len(actionable.devolved_actionable(conn, TODAY)), 1)

    def test_past_its_deadline_it_is_no_longer_actionable(self):
        conn = store([row("justice", "2026-08-31")])
        self.assertEqual(actionable.devolved_actionable(conn, "2026-09-01"), [])

    def test_no_stated_closing_date_is_not_an_open_window(self):
        conn = store([row("vision", None)])
        self.assertEqual(actionable.devolved_actionable(conn, TODAY), [])

    def test_the_taxonomy_threshold_is_exactly_the_existing_one(self):
        # No areas, no promotion -- and a hidden-area-only match (migration)
        # is treated as no match, the same as everywhere else.
        conn = store([row("plain", "2026-09-30", areas="[]"),
                      row("migration-only", "2026-09-30", areas="[11]")])
        self.assertEqual(actionable.devolved_actionable(conn, TODAY), [])

    def test_invited_only_consultations_are_not_open_to_us(self):
        conn = store([row("closed-door", "2026-09-30",
                          summary="Participation is by invitation only.")])
        self.assertEqual(actionable.devolved_actionable(conn, TODAY), [])

    def test_late_detection_flags_under_21_days_first_seen(self):
        self.assertTrue(actionable.late_detection("2026-08-22", "2026-08-31"))
        self.assertTrue(actionable.late_detection("2026-08-22", "2026-09-11"))
        self.assertFalse(actionable.late_detection("2026-08-22", "2026-09-12"))
        self.assertFalse(actionable.late_detection(None, "2026-09-12"))

    def test_reporting_only_stores_are_never_read(self):
        # Condition (1) excludes items that only report something. The rule
        # enforces that structurally: this module reads dg_consultations
        # and nothing else -- no sp_/sd_/ni_ table, no items, no mp_events.
        with open(os.path.join(ROOT, "src", "actionable.py"),
                  encoding="utf-8") as fh:
            src = fh.read()
        for table in ("sp_", "sd_items", "ni_items", "mp_events",
                      "FROM items"):
            self.assertNotIn('"{0}'.format(table), src)
        self.assertIn("dg_consultations", src)


class EditionRenderTests(unittest.TestCase):
    def _edition(self, consultations, late=0):
        e = digest.Edition(week_commencing=TODAY, number=5, mode="normal")
        e.devolved = {"consultations": consultations, "bills": [],
                      "divisions": []}
        e.late_detections = late
        e.board_rows = []
        return e

    def test_the_subheading_no_longer_asserts_non_actionability(self):
        text = digest.render_devolved(self._edition([{
            "title": "T", "url": "u", "nation": "N. Ireland",
            "closes": "2026-09-30 (30 days)", "actionable": True,
            "late": False}]))
        self.assertIn("Items with an open response window are briefed "
                      "and appear in Top lines", text)
        self.assertNotIn("not because it asks anything of us", text)

    def test_the_table_says_briefed_or_watching_and_flags_late(self):
        text = digest.render_devolved(self._edition([
            {"title": "A", "url": "u", "nation": "Scotland",
             "closes": "2026-08-31 (0 days)", "actionable": True,
             "late": True},
            {"title": "B", "url": "u", "nation": "Wales",
             "closes": "no date published", "actionable": False,
             "late": False}]))
        self.assertIn("| Briefed · late detection |", text)
        self.assertIn("| Watching |", text)

    def test_the_footer_counts_late_detections(self):
        e = self._edition([], late=2)
        out = digest.render(e)
        self.assertIn("Late detection: 2 items first surfaced under 21 days "
                      "before the deadline.", out)
        e2 = self._edition([], late=0)
        self.assertNotIn("Late detection", digest.render(e2))


class BriefSubjectTests(unittest.TestCase):
    def test_an_actionable_devolved_consultation_becomes_a_subject(self):
        import make_briefs as mb
        conn = store([row("re", "2026-09-30",
                          title="Consultation on the RE Core Syllabus")])
        subs = mb.subjects(conn, today=TODAY)
        ours = [s for s in subs if s.get("nation")]
        self.assertEqual(len(ours), 1)
        s = ours[0]
        # same kind and slug scheme as a Westminster consultation item
        self.assertEqual(s["kind"], "consultation")
        self.assertEqual(s["slug"], "consultation-consultation-on-the-re-core-syllabus")
        self.assertEqual(s["deadline"], "2026-09-30")
        self.assertEqual(s["nation"], "N. Ireland")
        # and the Westminster urgency banding applies unchanged
        self.assertEqual(
            mb.urgency_of(s, datetime.date.fromisoformat(TODAY)),
            "Urgent Campaign (30 days to 2026-09-30)")

    def test_everything_failing_the_window_stays_a_watching_brief(self):
        import make_briefs as mb
        conn = store([row("closed", "2026-08-01"),        # window shut
                      row("undated", None),               # no window
                      row("offside", "2026-09-30", areas="[]")])  # no score
        self.assertEqual([s for s in mb.subjects(conn, today=TODAY)
                          if s.get("nation")], [])

    def test_the_5ca_carries_the_marker_not_an_empty_grid(self):
        with open(os.path.join(ROOT, "tools", "make_briefs.py"),
                  encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("5CA not available for devolved items - populate", src)
        self.assertIn('False if s.get("nation")', src)


if __name__ == "__main__":
    unittest.main()
