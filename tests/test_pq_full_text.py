"""PQ full text (Christopher, 2026-09-06: "Build it").

The search endpoint returns questions cut at ~255 characters and no
answer; the detail endpoint returns both. Every reader of a PQ row --
5CA quotes, the roll, the stance judge, a retag -- reads the archive, so
the archive has to hold what the ingest matched against.
"""

import gzip
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import stance
from src.ingest import pqs


class FakeClient:
    def __init__(self, payload):
        self.payload, self.calls = payload, []

    def get_json(self, url, feed, slug, **kw):
        self.calls.append((url, feed, slug))
        return self.payload


FULL = "To ask the Secretary of State for Education, what assessment he has made of the syllabuses for religious education in place in England."


class DetailFetchTests(unittest.TestCase):
    def test_the_detail_endpoint_is_one_question_by_id(self):
        c = FakeClient({"value": {"id": 1270851, "uin": "1", "heading": "Religion: Education",
                                  "questionText": FULL, "answerText": "The Department...",
                                  "askingMemberId": 5, "answeringBodyName": "DfE",
                                  "dateTabled": "2026-03-01", "dateAnswered": "2026-03-08",
                                  "house": "Commons"}})
        q = pqs.fetch_question(c, 1270851)
        url, feed, slug = c.calls[0]
        self.assertTrue(url.endswith("/questions/1270851"))
        self.assertEqual((feed, slug), ("pq", "detail-1270851"),
                         "the archive must be pq_detail-<id>.json.gz, inside the pq_* glob")
        self.assertEqual(q.question_text, FULL)
        self.assertEqual(q.answer_text, "The Department...")

    def test_a_failed_detail_fetch_keeps_the_stub_row(self):
        class Boom:
            def get_json(self, *a, **k):
                raise RuntimeError("503")
        stub = pqs.parse_question({"id": 9, "uin": "9", "heading": "H",
                                   "questionText": "To ask...", "answerText": None})
        got = pqs.complete(Boom(), stub, log=lambda *a: None)
        self.assertIs(got, stub, "a missing answer must never lose the row")


class TextMapTests(unittest.TestCase):
    def setUp(self):
        self.raw = tempfile.mkdtemp()
        day = os.path.join(self.raw, "2026-09-06"); os.makedirs(day)
        def write(name, payload):
            with gzip.open(os.path.join(day, name), "wb") as fh:
                fh.write(json.dumps(payload).encode("utf-8"))
        write("pq_search-religion.json.gz", {"results": [{"value": {
            "id": 1270851, "heading": "Religion: Education",
            "questionText": FULL[:60]}}]})
        write("pq_detail-1270851.json.gz", {"value": {
            "id": 1270851, "heading": "Religion: Education",
            "questionText": FULL, "answerText": "Local syllabuses are agreed..."}})

    def test_the_fuller_text_wins_and_the_answer_rides_along(self):
        texts = stance.build_text_map(self.raw)
        text = texts["pq:1270851"]
        self.assertIn("religious education in place in England", text,
                      "the stub, not the detail, was used")
        self.assertIn("Answer: Local syllabuses", text,
                      "the ingest matched on the answer; the archive must carry it")

    def test_order_of_files_does_not_matter(self):
        """glob order is filesystem order; the longer text must win either way."""
        texts = stance.build_text_map(self.raw)
        self.assertGreater(len(texts["pq:1270851"]), len(FULL))


class BackfillTests(unittest.TestCase):
    def test_archived_ids_are_skipped(self):
        spec = importlib.util.spec_from_file_location(
            "bf", os.path.join(ROOT, "tools", "backfill_pq_text.py"))
        bf = importlib.util.module_from_spec(spec); spec.loader.exec_module(bf)
        raw = tempfile.mkdtemp(); day = os.path.join(raw, "2026-09-06"); os.makedirs(day)
        open(os.path.join(day, "pq_detail-42.json.gz"), "wb").close()
        self.assertEqual(bf.archived_ids(raw), {"42"})

    def test_it_never_opens_the_store_for_writing(self):
        src = open(os.path.join(ROOT, "tools", "backfill_pq_text.py"), encoding="utf-8").read()
        for verb in ("INSERT", "UPDATE", "DELETE", "init_db", "commit("):
            self.assertNotIn(verb, src, verb)


class RetagGuardTests(unittest.TestCase):
    def test_the_guard_is_about_coverage_not_a_flat_refusal(self):
        src = open(os.path.join(ROOT, "tools", "retag_passages.py"), encoding="utf-8").read()
        self.assertIn("def pq_detail_coverage", src)
        self.assertIn("share < 0.95", src)

    def test_coverage_is_the_share_of_ledger_ids_with_a_detail_file(self):
        spec = importlib.util.spec_from_file_location(
            "rp", os.path.join(ROOT, "tools", "retag_passages.py"))
        rp = importlib.util.module_from_spec(spec); spec.loader.exec_module(rp)
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE mp_events (member_id, date, kind, ref, line, areas, excerpt)")
        for ref in ("pq:1", "pq:2", "pq:3", "pq:4"):
            conn.execute("INSERT INTO mp_events VALUES (1,'2026-01-01','pq',?, 'x', '[1]', '')", (ref,))
        raw = tempfile.mkdtemp(); day = os.path.join(raw, "d"); os.makedirs(day)
        for i in ("1", "2", "3"):
            open(os.path.join(day, "pq_detail-%s.json.gz" % i), "wb").close()
        self.assertAlmostEqual(rp.pq_detail_coverage(conn, raw), 0.75)


if __name__ == "__main__":
    unittest.main()
