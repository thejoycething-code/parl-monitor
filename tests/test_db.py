"""Schema creation tests (handoff section 5)."""

import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

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


class GapPersistenceTests(unittest.TestCase):
    """A gap must be queryable afterwards, and countable correctly.

    Christopher, 2026-08-29. The Senedd tools wrote gaps to the table, the
    Holyrood tools kept a private copy of the same helper, and the NI tools
    collected gaps in a list and only PRINTED them -- so a run log was the
    only record NI ever left. All three now write through src.db.

    And the write is idempotent per day. It was not: on 2026-08-28 the
    Senedd weekly ran five times against a WAF-blocked host, and 11 real
    gaps became 50 rows, so the table answered "how bad was that day" five
    times worse than the truth.
    """

    def _conn(self):
        conn = db.init_db(db.connect(":memory:"))
        return conn

    def test_a_gap_is_stored_and_printed(self):
        conn = self._conn()
        db.record_gap(conn, "test-feed", "the source did not answer")
        rows = conn.execute("SELECT feed, detail FROM gaps").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(tuple(rows[0]), ("test-feed", "the source did not answer"))

    def test_the_same_gap_twice_in_a_day_is_one_row(self):
        conn = self._conn()
        for _ in range(4):
            db.record_gap(conn, "test-feed", "identical failure")
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0], 1)

    def test_the_same_gap_on_another_day_is_its_own_row(self):
        """Idempotency must not hide a failure that recurs next week."""
        conn = self._conn()
        db.record_gap(conn, "test-feed", "identical failure", edition="2026-08-28")
        db.record_gap(conn, "test-feed", "identical failure", edition="2026-09-04")
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0], 2)

    def test_a_collected_list_persists_whole(self):
        conn = self._conn()
        n = db.record_gaps(conn, "ni-classify", ["one", "two", "three"])
        self.assertEqual(n, 3)
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0], 3)

    def test_every_nation_persists_its_gaps(self):
        """NI printed and stored nothing; that is the fault being fixed."""
        import glob
        for tool in ("ni_pull", "ni_divisions", "ni_classify",
                     "sp_pull", "sp_divisions", "sp_committees",
                     "sd_pull", "sd_divisions", "sd_committees", "sd_bills"):
            path = os.path.join(ROOT, "tools", tool + ".py")
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            self.assertTrue(
                "record_gap" in src or "INTO gaps" in src,
                "{0} reports gaps without persisting them".format(tool))

    def test_no_writer_can_duplicate(self):
        import glob
        for path in glob.glob(os.path.join(ROOT, "tools", "*.py")) + \
                [os.path.join(ROOT, "src", "digest.py")]:
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            self.assertNotIn(
                "INSERT INTO gaps", src,
                "{0}: use INSERT OR IGNORE, the index forbids duplicates"
                .format(os.path.basename(path)))
