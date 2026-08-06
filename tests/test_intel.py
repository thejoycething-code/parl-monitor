"""Ledger foundations for 5CA: per-event issue areas + EDM co-signatories."""

import json
import os
import sqlite3
import sys
import unittest

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
