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


class TokenBudgetTests(unittest.TestCase):
    """The live classifier ran out of room and nobody noticed.

    2026-08-29, found by rehearsing the Sunday pull before it ran
    unattended. max_tokens was a flat 1500 for a batch of TWENTY items,
    each needing an id, a score, an area list and a why_it_matters
    sentence -- about 60 tokens apiece with no headroom. The reply stopped
    mid-sentence, json.loads failed on the unterminated string at character
    1153, the whole batch was lost, and the run fell back to the stub.

    No test caught it because every test uses the injectable transport, and
    a stub reply is never truncated. Only a real call is.
    """

    def _items(self, n):
        from src.triage import TriageItem
        return [TriageItem(id=str(i), title="t", text="x", tier=1,
                           issue_areas=[1], watchlist_hit=False)
                for i in range(n)]

    def test_the_budget_scales_with_the_batch(self):
        from src.triage import _build_payload
        one = _build_payload(self._items(1))["max_tokens"]
        twenty = _build_payload(self._items(20))["max_tokens"]
        self.assertGreater(twenty, one)
        self.assertGreater(twenty, 1500, "the cap that truncated the reply")

    def test_a_full_batch_gets_room_for_a_sentence_each(self):
        from src.triage import _build_payload, BATCH_SIZE
        budget = _build_payload(self._items(BATCH_SIZE))["max_tokens"]
        self.assertGreaterEqual(budget / BATCH_SIZE, 120,
                                "not enough room per item to finish a sentence")

    def test_thinking_cannot_starve_the_reply(self):
        """14 Sept 2026: a batch of twenty was given 3,600 tokens; the model spent
        3,595 of them thinking and the run fell back to the stub. The payload now
        asks for low effort and keeps thousands of tokens of headroom."""
        from src.triage import _build_payload, BATCH_SIZE
        payload = _build_payload(self._items(BATCH_SIZE))
        self.assertEqual(payload["output_config"], {"effort": "low"})
        self.assertGreaterEqual(payload["max_tokens"] - 160 * BATCH_SIZE, 3600,
                                "headroom must exceed the thinking that emptied the budget on 14 Sept")
        self.assertGreaterEqual(_build_payload(self._items(1))["max_tokens"], 6000)

    def test_a_fenced_or_prefixed_reply_still_parses(self):
        from src.triage import _parse_reply
        body = '[{"id": "1", "score": 2, "areas": ["x"], "why_it_matters": "w"}]'
        for text in (body, "```json\n" + body + "\n```", "Here are the scores:\n" + body):
            out = _parse_reply({"stop_reason": "end_turn", "content": [{"type": "text", "text": text}]})
            self.assertEqual((out[0].id, out[0].score), ("1", 2))

    def test_truncation_says_what_happened(self):
        """"Unterminated string starting at: line 7 column 10" reads like a
        malformed response. The response was fine; there was no room left."""
        from src.triage import _parse_reply
        reply = {"stop_reason": "max_tokens",
                 "content": [{"text": '[{"id": "1", "score": 3, "why_it_ma'}]}
        with self.assertRaises(ValueError) as caught:
            _parse_reply(reply)
        self.assertIn("max_tokens", str(caught.exception))

    def test_a_complete_reply_still_parses(self):
        from src.triage import _parse_reply
        reply = {"stop_reason": "end_turn",
                 "content": [{"text": '[{"id":"1","score":3,"areas":[2],'
                                      '"why_it_matters":"because"}]'}]}
        out = _parse_reply(reply)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].score, 3)


class EvidenceTextTests(unittest.TestCase):
    """Until 2026-09-07 the judge saw a title and nothing else."""

    def test_extra_fields_reach_the_judge_in_order(self):
        import json
        from src.triage import evidence_text
        text = evidence_text(json.dumps({"excerpt": "sex means biological sex", "court": "Supreme Court",
                                         "minister_line": "The Government will not appeal."}))
        self.assertEqual(text, "excerpt: sex means biological sex | minister line: The Government will not appeal.")

    def test_no_extra_is_an_empty_string(self):
        from src.triage import evidence_text
        self.assertEqual(evidence_text(None), "")
        self.assertEqual(evidence_text("not json"), "")
