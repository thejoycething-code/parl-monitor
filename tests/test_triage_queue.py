"""Pending-queue triage pass tests: NULL-score ingest, session queue round-trip,
watchlist floor, and discard logging."""

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, review, triage

WATCHLIST = os.path.join(ROOT, "config", "watchlist.yaml")


def seed_pending(conn, item_id, title, tier, areas=(2,), terms=("palliative care",)):
    conn.execute(
        "INSERT INTO items (id, captured_at, source_feed, item_type, title, issue_areas, "
        "matched_terms, tier, triage_score) VALUES (?, '2026-08-01', 'pq', 'x', ?, ?, ?, ?, NULL)",
        (item_id, title, json.dumps(list(areas)), json.dumps(list(terms)), tier),
    )
    conn.commit()


class PendingPassTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))
        self.wl = filt.load_watchlist(WATCHLIST)

    def tearDown(self):
        self.conn.close()

    def test_pending_items_marks_watchlist_hits(self):
        seed_pending(self.conn, "a:1", "SPUC briefing", 2, terms=("SPUC",))
        seed_pending(self.conn, "b:2", "Palliative care debate", 2)
        by_id = {i.id: i for i in triage.pending_items(self.conn, self.wl)}
        self.assertTrue(by_id["a:1"].watchlist_hit)
        self.assertFalse(by_id["b:2"].watchlist_hit)

    def test_tier2_items_reach_the_scoring_pass(self):
        # Regression: tier-2 matches were silently dropped before any triage ran.
        seed_pending(self.conn, "c:3", "Child protection framework", 2, areas=(6,), terms=("child protection",))
        self.assertEqual(len(triage.pending_items(self.conn, self.wl)), 1)

    def test_apply_scores_enforces_watchlist_floor_and_logs_discards(self):
        seed_pending(self.conn, "a:1", "Watchlist item scored low", 2, terms=("SPUC",))
        seed_pending(self.conn, "b:2", "Irrelevant item", 2)
        items = triage.pending_items(self.conn, self.wl)
        results = [triage.TriageResult("a:1", 1, [2], "x"),   # floor lifts to 2
                   triage.TriageResult("b:2", 0, [], "")]     # discard
        scored, discards = triage.apply_scores(self.conn, items, results)
        self.assertEqual(scored, 2)
        self.assertEqual([d[0] for d in discards], ["b:2"])
        rows = {r["id"]: r["triage_score"] for r in
                self.conn.execute("SELECT id, triage_score FROM items")}
        self.assertEqual(rows["a:1"], 2)
        self.assertEqual(rows["b:2"], 0)

    def test_queue_file_round_trip(self):
        seed_pending(self.conn, "a:1", "Hospice funding PQ", 2)
        seed_pending(self.conn, "b:2", "Noise item", 2, terms=("care",))
        tmp = os.path.join(tempfile.mkdtemp(), "queue.md")
        path, count = triage.generate_queue_file(self.conn, self.wl, "2026-08-03", tmp)
        self.assertEqual(count, 2)
        with open(path, encoding="utf-8") as h:
            text = h.read()
        self.assertIn("### item: a:1", text)
        self.assertIn("SCORE: ", text)
        self.assertIn("triage layer of CitizenGO", text)  # rubric embedded

        # Simulate a session scoring the file.
        text = text.replace("### item: a:1\n- tier: 2 | candidate areas: 2 | watchlist hit: no\n"
                            "- title: Hospice funding PQ\nSCORE: \nWHY: ",
                            "### item: a:1\n- tier: 2 | candidate areas: 2 | watchlist hit: no\n"
                            "- title: Hospice funding PQ\nSCORE: 2\nWHY: Hospice funding gap is the positive-agenda flank.")
        text = text.replace("SCORE: \nWHY: ", "SCORE: 0\nWHY: ", 1)  # b:2 discarded
        with open(path, "w", encoding="utf-8") as h:
            h.write(text)

        results = triage.parse_queue_file(path)
        self.assertEqual({r.id: r.score for r in results}, {"a:1": 2, "b:2": 0})
        items = triage.pending_items(self.conn, self.wl)
        triage.apply_scores(self.conn, items, results)
        row = self.conn.execute("SELECT triage_score, why_it_matters FROM items WHERE id='a:1'").fetchone()
        self.assertEqual(row["triage_score"], 2)
        self.assertIn("positive-agenda", row["why_it_matters"])

    def test_unscored_items_stay_pending(self):
        seed_pending(self.conn, "a:1", "Left blank", 2)
        tmp = os.path.join(tempfile.mkdtemp(), "queue.md")
        path, _ = triage.generate_queue_file(self.conn, self.wl, "2026-08-03", tmp)
        results = triage.parse_queue_file(path)  # nothing filled in
        self.assertEqual(results, [])
        self.assertIsNone(
            self.conn.execute("SELECT triage_score FROM items WHERE id='a:1'").fetchone()["triage_score"])


if __name__ == "__main__":
    unittest.main()
