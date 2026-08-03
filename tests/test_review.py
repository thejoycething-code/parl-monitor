"""Review-file round-trip tests (handoff sections 7, 8)."""

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, review


def seed(conn, item_id, feed, title, score, tier=1, areas=(2,), terms=("assisted dying",)):
    conn.execute(
        "INSERT INTO items (id, captured_at, source_feed, item_type, title, issue_areas, "
        "matched_terms, tier, triage_score) VALUES (?, '2026-08-01', ?, 'x', ?, ?, ?, ?, ?)",
        (item_id, feed, title, json.dumps(list(areas)), json.dumps(list(terms)), tier, score),
    )
    conn.commit()


class GenerateTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        self.conn.close()

    def test_only_score_2_plus_items_appear(self):
        seed(self.conn, "a:1", "pq", "Included", 2)
        seed(self.conn, "b:2", "pq", "Background only", 1, tier=2)
        path, count = review.generate_review_file(self.conn, "2026-08-03", os.path.join(self.dir, "r.md"))
        with open(path) as h:
            text = h.read()
        self.assertEqual(count, 1)
        self.assertIn("### item: a:1", text)
        self.assertNotIn("b:2", text)

    def test_file_has_editable_fields_and_context(self):
        seed(self.conn, "a:1", "edm", "EDM 603", 2)
        path, _ = review.generate_review_file(self.conn, "2026-08-03", os.path.join(self.dir, "r.md"))
        with open(path) as h:
            text = h.read()
        for expected in ("PRIORITY:", "OWNER:", "WHY:", "matched: assisted dying", "feed: edm"):
            self.assertIn(expected, text)

    def test_already_reviewed_items_excluded(self):
        seed(self.conn, "a:1", "pq", "Done", 2)
        self.conn.execute("UPDATE items SET priority_tag='NOTE' WHERE id='a:1'")
        _, count = review.generate_review_file(self.conn, "2026-08-03", os.path.join(self.dir, "r.md"))
        self.assertEqual(count, 0)


class ParseApplyTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        self.conn.close()

    def _write(self, body):
        path = os.path.join(self.dir, "r.md")
        with open(path, "w", encoding="utf-8") as h:
            h.write(body)
        return path

    def test_round_trip_writes_edits_back(self):
        seed(self.conn, "a:1", "pq", "Item A", 2)
        seed(self.conn, "b:2", "edm", "Item B", 2)
        path = self._write(
            "### item: a:1\nPRIORITY: ACT\nOWNER: Christopher\nWHY: Vote Thursday decides the supporter email.\n"
            "\n### item: b:2\nPRIORITY: NOTE\nOWNER: \nWHY: Signatories logged to profiles.\n")
        kept, dropped = review.apply_review(self.conn, review.parse_review_file(path))
        self.assertEqual((kept, dropped), (2, 0))
        row = self.conn.execute("SELECT priority_tag, owner, why_it_matters FROM items WHERE id='a:1'").fetchone()
        self.assertEqual(row["priority_tag"], "ACT")
        self.assertEqual(row["owner"], "Christopher")
        self.assertEqual(row["why_it_matters"], "Vote Thursday decides the supporter email.")
        self.assertIsNone(
            self.conn.execute("SELECT owner FROM items WHERE id='b:2'").fetchone()["owner"])

    def test_blank_priority_drops_item(self):
        seed(self.conn, "a:1", "pq", "Item A", 2)
        path = self._write("### item: a:1\nPRIORITY: \nOWNER: \nWHY: \n")
        kept, dropped = review.apply_review(self.conn, review.parse_review_file(path))
        self.assertEqual((kept, dropped), (0, 1))
        self.assertIsNone(
            self.conn.execute("SELECT priority_tag FROM items WHERE id='a:1'").fetchone()["priority_tag"])

    def test_invalid_priority_is_dropped_not_written(self):
        seed(self.conn, "a:1", "pq", "Item A", 2)
        path = self._write("### item: a:1\nPRIORITY: URGENT\nOWNER: X\nWHY: y\n")
        kept, dropped = review.apply_review(self.conn, review.parse_review_file(path))
        self.assertEqual((kept, dropped), (0, 1))

    def test_ids_with_colons_parse(self):
        seed(self.conn, "consultation:/government/consultations/send-reform", "consultation", "SEND", 2)
        path = self._write("### item: consultation:/government/consultations/send-reform\n"
                           "PRIORITY: WATCH\nOWNER: \nWHY: Closes 18 September.\n")
        edits = review.parse_review_file(path)
        self.assertEqual(edits[0]["id"], "consultation:/government/consultations/send-reform")
        self.assertEqual(review.apply_review(self.conn, edits), (1, 0))

    def test_draft_defaults_promote_unreviewed(self):
        seed(self.conn, "a:1", "pq", "Tier one item", 2, tier=1)
        seed(self.conn, "b:2", "pq", "Tier two item", 2, tier=2)
        promoted = review.apply_draft_defaults(self.conn)
        self.assertEqual(promoted, 2)
        tags = {r["id"]: r["priority_tag"] for r in
                self.conn.execute("SELECT id, priority_tag FROM items").fetchall()}
        self.assertEqual(tags["a:1"], "WATCH")
        self.assertEqual(tags["b:2"], "NOTE")

    def test_discards_logged(self):
        review.log_discards(self.conn, "2026-08-03", [("x:1", "Noise", '["care"]')])
        row = self.conn.execute("SELECT edition, item_id FROM discards").fetchone()
        self.assertEqual((row["edition"], row["item_id"]), ("2026-08-03", "x:1"))


if __name__ == "__main__":
    unittest.main()
