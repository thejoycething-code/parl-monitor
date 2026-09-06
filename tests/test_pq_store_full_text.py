"""run_weekly._store_pq_questions fetches the FULL question before storing.

The Sunday pull dispatched to prove this on 2026-09-06 was a no-op ("already
pulled ... use --force"), so the call site is pinned here instead: a matched
question triggers exactly one detail fetch, the stored row carries the full
text, and an unmatched question costs no call at all.
"""

import datetime
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import run_weekly
from src import db, filter as filt
from src.ingest import pqs

# The stub must MATCH on its own: the ingest filter runs on the search
# payload before any detail fetch, so a question whose only matching
# phrase is past the ~255-character cut is never fetched or stored. (That
# is a recall limit worth knowing about; it is not what this test pins.)
STUB = "To ask the Secretary of State for Education, what assessment he has made of religious education"
FULL = STUB + " syllabuses in place in England and the extent to which they reflect the principal religions."


class FakeClient:
    def __init__(self):
        self.calls = []

    def get_json(self, url, feed, slug, **kw):
        self.calls.append((feed, slug))
        qid = int(url.rsplit("/", 1)[1])
        return {"value": {"id": qid, "uin": "U%d" % qid, "heading": "Religion: Education",
                          "questionText": FULL, "answerText": "Locally agreed syllabuses...",
                          "askingMemberId": None, "answeringBodyName": "DfE",
                          "dateTabled": "2026-09-01", "dateAnswered": "2026-09-04",
                          "house": "Commons"}}


def question(qid, text, heading="Religion: Education"):
    return pqs.parse_question({"id": qid, "uin": "U%d" % qid, "heading": heading,
                               "questionText": text, "answerText": None,
                               "askingMemberId": None, "answeringBodyName": "DfE",
                               "dateTabled": "2026-09-01", "dateAnswered": "2026-09-04",
                               "house": "Commons"})


class StoreFullTextTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        db.init_db(self.conn)
        self.tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        self.wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
        self.since = datetime.date(2026, 8, 31)

    def test_a_matched_question_is_stored_in_full_after_one_detail_call(self):
        client = FakeClient()
        run_weekly._store_pq_questions(client, self.conn, self.tax, self.wl, self.since,
                                       "2026-09-07", [question(1270851, STUB)])
        self.assertEqual(client.calls, [("pq", "detail-1270851")],
                         "exactly one detail fetch, archived as pq_detail-<id>")
        row = self.conn.execute("SELECT extra FROM items WHERE id = 'pq:1270851'").fetchone()
        self.assertIsNotNone(row, "the question was not stored")
        self.assertIn("in place in England", row["extra"],
                      "the stored text is the stub, not the full question")

    def test_an_unmatched_question_costs_no_call(self):
        client = FakeClient()
        run_weekly._store_pq_questions(client, self.conn, self.tax, self.wl, self.since,
                                       "2026-09-07", [question(7, "To ask about potholes on the A38.",
                                                                heading="Roads: Repairs")])
        self.assertEqual(client.calls, [])
        self.assertIsNone(self.conn.execute("SELECT 1 FROM items WHERE id='pq:7'").fetchone())

    def test_a_failed_detail_fetch_still_stores_the_stub_row(self):
        class Boom(FakeClient):
            def get_json(self, url, feed, slug, **kw):
                raise RuntimeError("503")
        run_weekly._store_pq_questions(Boom(), self.conn, self.tax, self.wl, self.since,
                                       "2026-09-07", [question(1270851, STUB)])
        self.assertIsNotNone(self.conn.execute(
            "SELECT 1 FROM items WHERE id='pq:1270851'").fetchone(),
            "a missing answer must never lose the row")


if __name__ == "__main__":
    unittest.main()
