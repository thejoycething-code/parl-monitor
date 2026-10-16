"""Colombia gov_docs reader (src/gov_doc_sources/co.py): SUCOP draft
regulations mirrored from country_petitions. Fixture: four rows of the
petitions step's store (captured 16 October 2026 from the pulled store, last
read 15 October), tests/fixtures/gov_docs/co/country_petitions-sucop.json."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from src import db, gov_docs as G  # noqa: E402
from src.gov_doc_sources import co  # noqa: E402
from gov_docs_latam_helpers import load_petitions  # noqa: E402

TODAY = "2026-10-16"


class NoFetch:
    def __getattr__(self, name):
        raise AssertionError("a mirror must not fetch")


class MirrorTests(unittest.TestCase):
    def test_collect(self):
        conn = db.init_db(db.connect(":memory:"))
        load_petitions(conn, "co", "country_petitions-sucop.json")
        listed, kept, gaps = G.collect(conn, "co", NoFetch(), TODAY, log=lambda *a: None)
        self.assertEqual((listed, gaps), (4, 0))
        rows = {r["doc_id"]: dict(r) for r in conn.execute("SELECT * FROM gov_docs WHERE cc='co'")}
        self.assertIn("sucop:PN-2026-33672", rows)               # LGBTIQ+ journalists' protocol
        r = rows["sucop:PN-2026-33698"]                           # press freedom protocol
        self.assertEqual(r["doc_type"], "regulation_draft")
        self.assertEqual(r["closing_date"], "2026-10-30")
        self.assertEqual(r["published"], "2026-10-07")
        self.assertIn(7, json.loads(r["areas"]))
        self.assertNotIn("sucop:PN-2026-33765", rows)            # traffic in a national park
        due = G.deadline_rows(conn, "co", TODAY, "2026-12-31")
        self.assertEqual([d["closing_date"] for d in due], ["2026-10-30"] * len(due))
        self.assertGreaterEqual(len(due), 2)

    def test_empty_table_is_a_gap(self):
        conn = db.init_db(db.connect(":memory:"))
        listed, kept, gaps = G.collect(conn, "co", NoFetch(), TODAY, log=lambda *a: None)
        self.assertEqual((listed, kept, gaps), (0, 0, 1))
        self.assertEqual(co.CC, "co")


if __name__ == "__main__":
    unittest.main()
