"""Board snapshot persistence: movement markers must work across editions.

Regression for the everything-stays-NEW-forever bug: render never persisted
board_snapshot, so no later edition had anything to diff against.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import board, db


def live_row(bill_id=4157, stage="2nd reading", nkd="2026-09-11"):
    return board.BoardRow(bill_id, "TIA Bill", None, "Commons", stage, nkd,
                          "live", board.NEW, areas="2")


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))

    def tearDown(self):
        self.conn.close()

    def test_first_edition_is_new_and_persists(self):
        row = live_row()
        board.apply_snapshots(self.conn, [row], "2026-08-03")
        self.assertEqual(row.transition, board.NEW)
        stored = self.conn.execute(
            "SELECT board_snapshot FROM bills_board WHERE bill_id=4157").fetchone()
        self.assertIn('"edition": "2026-08-03"', stored["board_snapshot"])

    def test_unchanged_next_edition(self):
        board.apply_snapshots(self.conn, [live_row()], "2026-08-03")
        row = live_row()
        board.apply_snapshots(self.conn, [row], "2026-08-10")
        self.assertEqual(row.transition, board.UNCHANGED)
        self.assertEqual(row.movement, "no change")

    def test_moved_next_edition_on_date_change(self):
        board.apply_snapshots(self.conn, [live_row(nkd="2026-09-11")], "2026-08-03")
        row = live_row(nkd="2026-09-18")  # sitting slipped a week
        board.apply_snapshots(self.conn, [row], "2026-08-10")
        self.assertEqual(row.transition, board.MOVED)
        self.assertEqual(row.movement, "▲ moved")

    def test_moved_next_edition_on_stage_change(self):
        board.apply_snapshots(self.conn, [live_row(stage="2nd reading")], "2026-08-03")
        row = live_row(stage="Committee stage")
        board.apply_snapshots(self.conn, [row], "2026-08-10")
        self.assertEqual(row.transition, board.MOVED)

    def test_same_edition_rerender_is_idempotent(self):
        # Edition 1 then edition 2 (moved), then edition 2 re-rendered twice:
        # the marker must stay MOVED, not decay to UNCHANGED.
        board.apply_snapshots(self.conn, [live_row(nkd="2026-09-11")], "2026-08-03")
        for _ in range(3):
            row = live_row(nkd="2026-09-18")
            board.apply_snapshots(self.conn, [row], "2026-08-10")
            self.assertEqual(row.transition, board.MOVED)

    def test_first_edition_rerender_stays_new(self):
        for _ in range(2):
            row = live_row()
            board.apply_snapshots(self.conn, [row], "2026-08-03")
            self.assertEqual(row.transition, board.NEW)

    def test_closed_rows_untouched(self):
        row = board.BoardRow(3938, "CPA", None, "Unassigned", "Royal Assent", "-",
                             "closed", board.ROYAL_ASSENT, closed_note="RA")
        board.apply_snapshots(self.conn, [row], "2026-08-03")
        self.assertEqual(row.transition, board.ROYAL_ASSENT)
        self.assertIsNone(self.conn.execute(
            "SELECT board_snapshot FROM bills_board WHERE bill_id=3938").fetchone())


class StaleClosureTests(unittest.TestCase):
    """Closures render only while the terminal event is fresh (Chris, 2026-08-03)."""

    def _closure(self, bill_id, closed_date=None, note=""):
        return board.BoardRow(bill_id, "A Bill", None, "Commons", "Stage", "-",
                              "closed", board.FALLEN, closed_note=note,
                              closed_date=closed_date)

    def test_months_old_closures_are_stale(self):
        import datetime, run_weekly
        week = datetime.date(2026, 8, 3)
        rows = [
            self._closure(3774, "2026-04-24"),                       # fell in April
            self._closure(3938, "2026-04-29"),                       # RA in April
            self._closure(-445, None, "Fell on 2026-03-17 at Stage 3"),  # date only in note
            self._closure(5000, "2026-07-20"),                       # fell 2 weeks ago: fresh
            self._closure(5001, None, "no date recorded"),           # unknown: fresh by policy
        ]
        fresh, stale = run_weekly.split_stale_closures(rows, week)
        self.assertEqual(sorted(r.bill_id for r in stale), [-445, 3774, 3938])
        self.assertEqual(sorted(r.bill_id for r in fresh), [5000, 5001])

    def test_window_is_configurable(self):
        import datetime, run_weekly
        week = datetime.date(2026, 8, 3)
        rows = [self._closure(1, "2026-07-20")]  # 14 days before the week
        fresh, stale = run_weekly.split_stale_closures(rows, week, fresh_days=7)
        self.assertEqual([r.bill_id for r in stale], [1])


class AnnotatedLineTests(unittest.TestCase):
    def test_opaque_heading_gets_matched_term(self):
        from src import intel
        self.assertEqual(
            intel.annotated_line("Home Office: Written Questions", ['"asylum hotel*"']),
            "Home Office: Written Questions (re: asylum hotel)")

    def test_self_explanatory_heading_left_alone(self):
        from src import intel
        self.assertEqual(
            intel.annotated_line("Anti-Muslim Hostility", ["anti-Muslim hostility"]),
            "Anti-Muslim Hostility")

    def test_no_terms_no_change(self):
        from src import intel
        self.assertEqual(intel.annotated_line("A heading", []), "A heading")


if __name__ == "__main__":
    unittest.main()
