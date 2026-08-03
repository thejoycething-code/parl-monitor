"""Schema creation tests (handoff section 5)."""

import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import db


class InitDbTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")

    def tearDown(self):
        self.conn.close()

    def _table_names(self):
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return {r["name"] for r in rows}

    def test_creates_every_table(self):
        db.init_db(self.conn)
        self.assertEqual(set(db.TABLES), self._table_names())

    def test_init_is_idempotent(self):
        db.init_db(self.conn)
        db.init_db(self.conn)  # must not raise
        self.assertEqual(set(db.TABLES), self._table_names())

    def test_items_has_date_tabled_column(self):
        # Required for PQ deep links (handoff section 4.2 / pilot gap #4).
        db.init_db(self.conn)
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(items)")}
        self.assertIn("date_tabled", cols)
        self.assertIn("raw_path", cols)

    def test_bills_board_has_snapshot_and_session_columns(self):
        db.init_db(self.conn)
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(bills_board)")}
        self.assertIn("board_snapshot", cols)  # movement marker
        self.assertIn("session_ids", cols)     # prorogation-fall detection
        self.assertIn("closed_edition", cols)  # one-closing-entry guard

    def test_edm_signatures_composite_key(self):
        db.init_db(self.conn)
        self.conn.execute(
            "INSERT INTO edm_signatures (edm_id, edition, count) VALUES (603, '2026-08-03', 6)"
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO edm_signatures (edm_id, edition, count) VALUES (603, '2026-08-03', 7)"
            )


if __name__ == "__main__":
    unittest.main()
