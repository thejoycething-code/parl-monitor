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


if __name__ == "__main__":
    unittest.main()
