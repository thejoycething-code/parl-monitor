"""The Canadian petitions judge (tools/ca_triage.py). No network: the transport is faked."""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, triage  # noqa: E402


def _load():
    spec = importlib.util.spec_from_file_location("ca_triage", os.path.join(ROOT, "tools", "ca_triage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ct = _load()


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return ca_store.ensure_schema(conn)


def petition(conn, pid, areas, presented, prayer="We call on the House to protect life."):
    conn.execute("INSERT INTO ca_petitions (petition_id, presented_number, category, keywords, "
                 "prayer, presented, areas, tier, first_seen, last_seen) "
                 "VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (pid, pid, "Justice", json.dumps(["Euthanasia"]), prayer, presented,
                  areas, 2, "2026-09-27", "2026-09-27"))
    conn.commit()


def fake_transport(scores):
    """Reply with a fixed score per id, in the Messages API shape."""
    def transport(payload, key):
        batch = json.loads(payload["messages"][0]["content"])
        rows = [{"id": b["id"], "score": scores.get(b["id"], 2), "areas": b["candidate_areas"],
                 "why_it_matters": "Because."} for b in batch]
        return {"content": [{"type": "text", "text": json.dumps(rows)}], "model": "claude-sonnet-5",
                "usage": {"input_tokens": 100, "output_tokens": 20}, "stop_reason": "end_turn"}
    return transport


class FrameTests(unittest.TestCase):
    def test_the_frame_is_canadian_and_keeps_the_rubric(self):
        self.assertNotIn("CitizenGO UK's parliamentary monitor", ct.SYSTEM_PROMPT_CA)
        self.assertIn("House of Commons and Senate of Canada", ct.SYSTEM_PROMPT_CA)
        self.assertIn("MAID", ct.SYSTEM_PROMPT_CA)
        self.assertIn("presenting a petition does not mean endorsing it", ct.SYSTEM_PROMPT_CA)
        self.assertIn("Score 0 = irrelevant to every area", ct.SYSTEM_PROMPT_CA)


class PendingTests(unittest.TestCase):
    def test_newest_first_and_migration_only_left_out(self):
        conn = store()
        petition(conn, "431-00001", "[2]", "2020-02-01")
        petition(conn, "451-00100", "[2]", "2026-09-01")
        petition(conn, "451-00101", "[11]", "2026-09-02")
        petition(conn, "451-00102", "[]", "2026-09-03")
        ids = [i.id for i in ct.pending(conn)]
        self.assertEqual(ids, ["ca_petitions:451-00100", "ca_petitions:431-00001"])

    def test_the_prayer_is_what_the_judge_reads(self):
        conn = store()
        petition(conn, "451-00100", "[2]", "2026-09-01", prayer="Keep MAID closed to mental illness.")
        item = ct.pending(conn)[0]
        self.assertIn("Keep MAID closed", item.text)
        self.assertIn("Euthanasia", item.title)


class JudgeTests(unittest.TestCase):
    def test_scores_and_spend_are_recorded(self):
        conn = store()
        for n in range(6):
            petition(conn, "451-%05d" % n, "[2]", "2026-09-%02d" % (n + 1))
        items = ct.pending(conn)
        scored, gaps = ct.judge(conn, items, "k", "2026-09-27", log=lambda *a: None,
                                transport=fake_transport({"ca_petitions:451-00005": 3}))
        self.assertEqual((scored, gaps), (6, 0))
        self.assertEqual(conn.execute("SELECT triage_score FROM ca_petitions WHERE "
                                      "petition_id='451-00005'").fetchone()[0], 3)
        self.assertEqual(ct.pending(conn), [], "scored once, ever")
        passes = {r[0] for r in conn.execute("SELECT pass_name FROM api_spend")}
        self.assertEqual(passes, {"ca-triage"})

    def test_a_refusing_row_is_left_for_next_run_not_stubbed(self):
        conn = store()
        petition(conn, "451-00001", "[2]", "2026-09-01")

        def broken(payload, key):
            return {"content": [{"type": "text", "text": "not json"}], "usage": {}, "model": "m"}

        scored, gaps = ct.judge(conn, ct.pending(conn), "k", "2026-09-27", log=lambda *a: None,
                                transport=broken)
        self.assertEqual((scored, gaps), (0, 1))
        self.assertIsNone(conn.execute("SELECT triage_score FROM ca_petitions").fetchone()[0])

    def test_rescore_requeues_one_row(self):
        conn = store()
        petition(conn, "451-00001", "[2]", "2026-09-01")
        ct.judge(conn, ct.pending(conn), "k", "2026-09-27", log=lambda *a: None,
                 transport=fake_transport({}))
        self.assertEqual(ct.rescore(conn, "451-00001"), 1)
        self.assertEqual(len(ct.pending(conn)), 1)

    def test_the_run_is_capped_inside_the_weekly_wall(self):
        self.assertLess(ct.BUDGET_S, 45 * 60)


if __name__ == "__main__":
    unittest.main()
