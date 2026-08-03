"""Triage tests: stub scoring, batching, live-parse via mock transport."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import triage


def item(id, tier, areas, watchlist=False):
    return triage.TriageItem(id=id, title=id, text="", tier=tier, issue_areas=areas, watchlist_hit=watchlist)


class StubTests(unittest.TestCase):
    def test_stub_scoring_rules(self):
        results = triage.score_stub([
            item("a", 1, [2]),            # tier-1 -> 2
            item("b", 2, [5]),            # tier-2 -> 1
            item("c", None, [], True),    # watchlist-only -> 2
        ])
        by_id = {r.id: r for r in results}
        self.assertEqual(by_id["a"].score, 2)
        self.assertEqual(by_id["b"].score, 1)
        self.assertEqual(by_id["c"].score, 2)
        self.assertTrue(all(r.stub and r.why_it_matters == "" for r in results))

    def test_partition(self):
        results = [
            triage.TriageResult("a", 3, [2], "x"),
            triage.TriageResult("b", 2, [5], "y"),
            triage.TriageResult("c", 1, [], ""),
            triage.TriageResult("d", 0, [], ""),
        ]
        review, background, discards = triage.partition(results)
        self.assertEqual([r.id for r in review], ["a", "b"])
        self.assertEqual([r.id for r in background], ["c"])
        self.assertEqual([r.id for r in discards], ["d"])

    def test_dispatch_defaults_to_stub(self):
        os.environ.pop("TRIAGE", None)
        results = triage.triage([item("a", 1, [2])])
        self.assertTrue(results[0].stub)


class LiveTests(unittest.TestCase):
    def test_batches_of_twenty_and_parses_reply(self):
        calls = []

        def fake_transport(payload, api_key):
            calls.append(payload)
            # Echo a valid scored array for each item in the batch.
            import json
            sent = json.loads(payload["messages"][0]["content"])
            arr = [{"id": s["id"], "score": 3, "areas": [2], "why_it_matters": "test line"} for s in sent]
            return {"content": [{"type": "text", "text": json.dumps(arr)}]}

        items = [item("i%d" % n, 2, [2]) for n in range(45)]
        results = triage.score_live(items, api_key="k", transport=fake_transport)
        self.assertEqual(len(results), 45)
        self.assertEqual([len(c) for c in [__import__("json").loads(p["messages"][0]["content"]) for p in calls]],
                         [20, 20, 5])  # 45 -> three batches
        self.assertEqual(results[0].score, 3)
        self.assertEqual(results[0].why_it_matters, "test line")

    def test_live_requires_api_key(self):
        with self.assertRaises(RuntimeError):
            triage.score_live([item("a", 2, [2])], api_key=None, transport=lambda p, k: {})

    def test_model_is_corrected_id(self):
        self.assertEqual(triage.TRIAGE_MODEL, "claude-sonnet-5")


if __name__ == "__main__":
    unittest.main()
