"""Ledger foundations for 5CA: per-event issue areas + EDM co-signatories."""

import json
import os
import sqlite3
import sys
import unittest
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import db, digest, intel
from src.ingest import edms


def fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return db.init_db(conn)


class AreasOnEventsTests(unittest.TestCase):
    def test_areas_stored_and_read_back(self):
        conn = fresh_conn()
        intel.record_event(conn, 42, "2026-08-01", "pq", "pq:1", "Asylum Hotels", areas=[11, 7])
        row = intel.member_timeline(conn, 42)[0]
        self.assertEqual(json.loads(row["areas"]), [7, 11])  # sorted on write

    def test_rerun_stamps_areas_onto_pre_areas_rows(self):
        """The retro-stamping mechanism: a backfill re-run must upgrade rows
        recorded before the areas column existed, without duplicating them."""
        conn = fresh_conn()
        intel.record_event(conn, 42, "2026-08-01", "pq", "pq:1", "Asylum Hotels")
        intel.record_event(conn, 42, "2026-08-01", "pq", "pq:1", "Asylum Hotels", areas=[11])
        rows = intel.member_timeline(conn, 42)
        self.assertEqual(len(rows), 1)
        self.assertEqual(json.loads(rows[0]["areas"]), [11])

    def test_legacy_table_without_areas_column_is_migrated(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE mp_events (member_id INTEGER, date TEXT, "
                     "kind TEXT, ref TEXT, line TEXT)")
        db.init_db(conn)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(mp_events)")}
        self.assertIn("areas", cols)

    def test_area_activity_aggregates_per_member(self):
        conn = fresh_conn()
        intel.record_event(conn, 1, "2026-08-01", "pq", "pq:1", "A", areas=[11])
        intel.record_event(conn, 1, "2026-08-02", "pq", "pq:2", "B", areas=[11, 2])
        intel.record_event(conn, 2, "2026-08-01", "edm", "edm:9", "C", areas=[7])
        intel.record_event(conn, 3, "2026-08-01", "pq", "pq:3", "D")  # no areas: excluded
        self.assertEqual(intel.area_activity(conn), {1: {11: 2, 2: 1}, 2: {7: 1}})


class SignatoryCaptureTests(unittest.TestCase):
    PAYLOAD = {"Response": {"Id": 66191, "Sponsors": [
        {"MemberId": 5244, "SponsoringOrder": 1, "IsWithdrawn": False,
         "Member": {"Name": "Chris Hinchliff", "Party": "Labour",
                    "Constituency": "North East Hertfordshire"}},
        {"MemberId": 5319, "SponsoringOrder": 2, "IsWithdrawn": False,
         "Member": {"Name": "Ann Other", "Party": "Independent",
                    "Constituency": "Somewhere"}},
        {"MemberId": 5400, "SponsoringOrder": 3, "IsWithdrawn": True,
         "Member": {"Name": "Gone Away", "Party": "Labour", "Constituency": "X"}},
    ]}}

    def test_parse_sponsors_shapes_and_flags(self):
        sponsors = edms.parse_sponsors(self.PAYLOAD)
        self.assertEqual(len(sponsors), 3)
        self.assertEqual(sponsors[0].order, 1)
        self.assertEqual(sponsors[1].name, "Ann Other")
        self.assertEqual(sponsors[1].seat, "Somewhere")
        self.assertTrue(sponsors[2].withdrawn)

    def test_parse_sponsors_empty_response(self):
        self.assertEqual(edms.parse_sponsors({"Response": None}), [])


class WeeklySectionBulkKindsTests(unittest.TestCase):
    def _event(self, kind, mid=1):
        return {"member_id": mid, "kind": kind, "line": "L", "name": "N",
                "party": "P", "seat": "S"}

    def test_signatures_and_votes_never_listed(self):
        lines = digest.mp_lines_from_events(
            [self._event("edm-signed"), self._event("vote", 2)])
        self.assertEqual(lines, [])

    def test_debates_still_listed(self):
        """Questions moved to their own section; debates remain the substance
        of this one (Christopher, 2026-08-05)."""
        lines = digest.mp_lines_from_events([self._event("debate")])
        self.assertEqual(len(lines), 1)
        self.assertIn("**DEBATE** L", lines[0])

    def test_questions_not_listed_here(self):
        self.assertEqual(digest.mp_lines_from_events([self._event("pq")]), [])


class AreaNamesTests(unittest.TestCase):
    def test_names_from_generated_taxonomy(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "config", "taxonomy.yaml")
        names = intel.area_names(path)
        self.assertEqual(names[11], "Migration")
        self.assertEqual(names[2], "Assisted dying")


if __name__ == "__main__":
    unittest.main()


class LockedDatabaseTests(unittest.TestCase):
    """The 2017 Hansard backfill died with 'database is locked' beside the PQ backfill
    (2026-09-08). A write now waits out a neighbour's transaction instead."""

    def setUp(self):
        import tempfile
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "t.db")
        db.init_db(db.connect(self.path)).close()

    def _open(self):
        conn = sqlite3.connect(self.path, timeout=0, check_same_thread=False)   # no busy wait: the retry must do the work
        conn.row_factory = sqlite3.Row
        return conn

    def test_record_event_waits_for_a_neighbours_transaction_to_finish(self):
        import threading
        holder = self._open()
        holder.execute("BEGIN IMMEDIATE")                  # holds the reserved lock
        holder.execute("INSERT INTO members (id, name) VALUES (1, 'A')")
        writer = self._open()
        threading.Timer(0.6, holder.commit).start()        # released while the writer is retrying
        waits = []
        real_sleep = intel.time.sleep                     # the patch below replaces the module's sleep itself
        with unittest.mock.patch.object(intel.time, "sleep", side_effect=lambda s: (waits.append(s), real_sleep(min(s, 0.3)))):
            intel.record_event(writer, 7, "2019-07-09", "debate", "hansard:X", "Spoke: test", areas=[1])
        self.assertTrue(waits, "the write should have had to wait at least once")
        self.assertEqual(writer.execute("SELECT count(*) FROM mp_events WHERE ref='hansard:X'").fetchone()[0], 1)
        holder.close(); writer.close()

    def test_gives_up_after_the_last_attempt_and_leaves_the_error_visible(self):
        holder = self._open()
        holder.execute("BEGIN IMMEDIATE")
        holder.execute("INSERT INTO members (id, name) VALUES (2, 'B')")
        writer = self._open()
        with unittest.mock.patch.object(intel.time, "sleep"):
            with self.assertRaises(sqlite3.OperationalError):
                intel.write_with_retry(writer, lambda: (writer.execute("INSERT INTO members (id, name) VALUES (3, 'C')"), writer.commit()), attempts=3)
        holder.rollback(); holder.close(); writer.close()

    def test_other_errors_are_not_retried(self):
        conn = self._open()
        calls = []

        def bad():
            calls.append(1)
            conn.execute("INSERT INTO no_such_table VALUES (1)")
        with self.assertRaises(sqlite3.OperationalError):
            intel.write_with_retry(conn, bad)
        self.assertEqual(len(calls), 1)
        conn.close()
