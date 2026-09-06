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

# THE RECALL CASE. The stub does NOT match on its own -- the phrase that
# tags it sits past the ~255-character cut -- and since 2026-09-06 the
# detail is fetched BEFORE the filter runs, so this question is kept.
STUB = "To ask the Secretary of State for Education, what assessment he has made of the adequacy of"
FULL = STUB + " the syllabuses for religious education in place in England."


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

    def test_a_question_matching_only_in_its_full_text_is_kept(self):
        client = FakeClient()
        run_weekly._store_pq_questions(client, self.conn, self.tax, self.wl, self.since,
                                       "2026-09-07", [question(1270851, STUB)])
        self.assertEqual(client.calls, [("pq", "detail-1270851")],
                         "exactly one detail fetch, archived as pq_detail-<id>")
        # the stub alone would NOT have matched: prove the premise
        self.assertFalse(filt.filter_item(self.tax, self.wl, "Religion: Education",
                                          STUB, "").matched())
        row = self.conn.execute("SELECT extra FROM items WHERE id = 'pq:1270851'").fetchone()
        self.assertIsNotNone(row, "the question was not stored")
        self.assertIn("in place in England", row["extra"],
                      "the stored text is the stub, not the full question")

    def test_an_unmatched_question_costs_one_call_and_no_row(self):
        """Every result in the window is fetched; only matches are stored."""
        class Potholes(FakeClient):
            def get_json(self, url, feed, slug, **kw):
                self.calls.append((feed, slug))
                return {"value": {"id": 7, "uin": "U7", "heading": "Roads: Repairs",
                                  "questionText": "To ask about potholes on the A38.",
                                  "answerText": "Resurfacing is scheduled.",
                                  "askingMemberId": None, "answeringBodyName": "DfT",
                                  "dateTabled": "2026-09-01", "dateAnswered": "2026-09-04",
                                  "house": "Commons"}}
        client = Potholes()
        run_weekly._store_pq_questions(client, self.conn, self.tax, self.wl, self.since,
                                       "2026-09-07", [question(7, "To ask about potholes on the A38.",
                                                                heading="Roads: Repairs")])
        self.assertEqual(client.calls, [("pq", "detail-7")])
        self.assertIsNone(self.conn.execute("SELECT 1 FROM items WHERE id='pq:7'").fetchone())

    def test_a_failed_detail_fetch_falls_back_to_filtering_the_stub(self):
        """A flaky API narrows recall for a week; it must not crash the sweep
        or lose a question whose STUB matches."""
        class Boom(FakeClient):
            def get_json(self, url, feed, slug, **kw):
                raise RuntimeError("503")
        matching_stub = "To ask the Secretary of State for Education about religious education"
        run_weekly._store_pq_questions(Boom(), self.conn, self.tax, self.wl, self.since,
                                       "2026-09-07", [question(1270851, matching_stub)])
        self.assertIsNotNone(self.conn.execute(
            "SELECT 1 FROM items WHERE id='pq:1270851'").fetchone(),
            "the stub matched; a failed detail fetch must not lose the row")


if __name__ == "__main__":
    unittest.main()
