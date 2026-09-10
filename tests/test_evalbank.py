"""The judge evaluation corpus (Christopher, 2026-09-07)."""

import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, evalbank, triage  # noqa: E402


def _conn():
    conn = db.init_db(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    return conn


def _items(n, prefix="pq"):
    return [triage.TriageItem(id="{0}:{1}".format(prefix, i), title="Title {0}".format(i), text="", tier=1,
                              issue_areas=[2], watchlist_hit=False) for i in range(n)]


def _results(items, scores):
    return [triage.TriageResult(id=it.id, score=s, areas=[2], why_it_matters="because {0}".format(it.id))
            for it, s in zip(items, scores)]


class BankTests(unittest.TestCase):
    def test_bank_records_what_was_seen_and_said_with_prompt_and_model(self):
        conn = _conn()
        items = _items(3)
        n = evalbank.bank(conn, "2026-09-07", items, _results(items, [3, 1, 0]), "claude-sonnet-5", "live", "PROMPT")
        self.assertEqual(n, 3)
        row = conn.execute("SELECT * FROM judge_verdicts WHERE item_id='pq:0'").fetchone()
        self.assertEqual((row["score"], row["why"], row["model"], row["mode"], row["feed"]),
                         (3, "because pq:0", "claude-sonnet-5", "live", "pq"))
        self.assertEqual(row["prompt_sha"], evalbank.prompt_sha("PROMPT"))
        self.assertEqual(len(row["prompt_sha"]), 12)

    def test_rebanking_a_week_updates_rather_than_duplicates(self):
        conn = _conn()
        items = _items(2)
        evalbank.bank(conn, "2026-09-07", items, _results(items, [1, 1]), "m", "live", "P")
        evalbank.bank(conn, "2026-09-07", items, _results(items, [2, 2]), "m", "live", "P")
        self.assertEqual(conn.execute("SELECT COUNT(*), SUM(score) FROM judge_verdicts").fetchone()[:2], (2, 4))

    def test_export_writes_one_json_line_per_verdict(self):
        import json
        conn = _conn()
        items = _items(2)
        evalbank.bank(conn, "2026-09-07", items, _results(items, [2, 3]), "m", "live", "P")
        path, n = evalbank.export(conn, "2026-09-07", os.path.join(tempfile.mkdtemp(), "2026-09-07.jsonl"))
        lines = open(path, encoding="utf-8").read().splitlines()
        self.assertEqual((n, len(lines)), (2, 2))
        self.assertEqual(json.loads(lines[0])["item_id"], "pq:0")


    def test_restore_reloads_the_exports_and_never_overwrites_a_store_row(self):
        import json
        conn = _conn()
        items = _items(2)
        evalbank.bank(conn, "2026-09-07", items, _results(items, [2, 3]), "m", "live", "P")
        folder = tempfile.mkdtemp()
        evalbank.export(conn, "2026-09-07", os.path.join(folder, "2026-09-07.jsonl"))
        conn.execute("DELETE FROM judge_verdicts")
        conn.commit()
        self.assertEqual(evalbank.restore(conn, folder), 2)
        rows = conn.execute("SELECT item_id, score FROM judge_verdicts ORDER BY item_id").fetchall()
        self.assertEqual([tuple(r) for r in rows], [("pq:0", 2), ("pq:1", 3)])
        # a human label added since the export survives a second restore
        conn.execute("UPDATE judge_verdicts SET human_score = 1 WHERE item_id = 'pq:0'")
        conn.commit()
        self.assertEqual(evalbank.restore(conn, folder), 0)
        self.assertEqual(conn.execute("SELECT human_score FROM judge_verdicts WHERE item_id = 'pq:0'").fetchone()[0], 1)


class NoPollutionTests(unittest.TestCase):
    def test_an_in_memory_store_never_writes_the_repo_export(self):
        """A test item ("a:1") reached data/eval/2026-08-10.jsonl and was committed."""
        conn = _conn()
        items = _items(1)
        evalbank.bank(conn, "2026-08-10", items, _results(items, [2]), "m", "live", "P")
        self.assertEqual(evalbank.export(conn, "2026-08-10"), (None, 0))
        text = open(os.path.join(ROOT, "data", "eval", "2026-08-10.jsonl"), encoding="utf-8").read()
        self.assertNotIn('"item_id": "pq:0"', text)


class SampleTests(unittest.TestCase):
    def _bank(self, conn, scores, mode="live"):
        items = _items(len(scores))
        evalbank.bank(conn, "2026-09-07", items, _results(items, scores), "m", mode, "P")

    def test_sample_is_stratified_and_deterministic(self):
        conn = _conn()
        self._bank(conn, [0] * 30 + [1] * 30 + [2] * 30 + [3] * 3)
        rows = conn.execute("SELECT * FROM judge_verdicts").fetchall()
        a = evalbank.pick_sample(rows, 10, seed="2026-09-07")
        b = evalbank.pick_sample(rows, 10, seed="2026-09-07")
        self.assertEqual([r["item_id"] for r in a], [r["item_id"] for r in b])
        self.assertEqual(len(a), 10)
        for s in (0, 1, 2, 3):
            self.assertGreaterEqual(sum(1 for r in a if r["score"] == s), 2, "score {0} under-sampled".format(s))

    def test_the_file_reads_like_the_review_checklist_and_skips_stub_weeks(self):
        conn = _conn()
        self._bank(conn, [2, 3, 1, 0, 2])
        path, n = evalbank.write_sample(conn, "2026-09-07", os.path.join(tempfile.mkdtemp(), "judge-sample-2026-09-07.md"))
        text = open(path, encoding="utf-8").read()
        self.assertEqual(n, 5)
        self.assertIn("### item: pq:0", text)
        self.assertIn("- judge why: because pq:0", text)
        self.assertIn("VERDICT: ", text)
        self.assertIn("Do not edit the `### item:` id lines.", text)
        stub = _conn()
        self._bank(stub, [2, 2], mode="stub")
        self.assertEqual(evalbank.write_sample(stub, "2026-09-07", os.path.join(tempfile.mkdtemp(), "x.md")), (None, 0))

    def test_ingest_reads_explicit_verdicts_and_review_priorities(self):
        conn = _conn()
        self._bank(conn, [2, 3, 1])
        reviews = tempfile.mkdtemp()
        with open(os.path.join(reviews, "judge-sample-2026-09-07.md"), "w", encoding="utf-8") as fh:
            fh.write("# Judge sample\n\n### item: pq:0\n- title: Title 0\nVERDICT: 3\nNOTE: under-scored, a trigger\n\n"
                     "### item: pq:1\nVERDICT: \nNOTE: \n\n### item: pq:2\nVERDICT: 1\nNOTE: \n")
        with open(os.path.join(reviews, "review-2026-09-07.md"), "w", encoding="utf-8") as fh:
            fh.write("# Review\n\n### item: pq:1\nPRIORITY: WATCH\nOWNER: \nWHY: fine\n\n"
                     "### item: pq:0\nPRIORITY: NOTE\n")     # must NOT override the explicit 3
        explicit, implicit = evalbank.ingest_samples(conn, reviews, today="2026-09-14")
        self.assertEqual((explicit, implicit), (2, 1))
        rows = {r["item_id"]: r for r in conn.execute("SELECT * FROM judge_verdicts")}
        self.assertEqual((rows["pq:0"]["human_score"], rows["pq:0"]["human_source"], rows["pq:0"]["human_note"]),
                         (3, "sample", "under-scored, a trigger"))
        self.assertEqual((rows["pq:1"]["human_score"], rows["pq:1"]["human_source"]), (2, "review"))
        self.assertEqual(rows["pq:2"]["human_score"], 1)


class ReportTests(unittest.TestCase):
    def test_stats_and_matrix(self):
        rows = [{"score": s, "human_score": h} for s, h in ((3, 3), (2, 2), (2, 1), (1, 2), (0, 0), (3, 1))]
        s = evalbank.stats(rows)
        self.assertEqual(s["n"], 6)
        self.assertAlmostEqual(s["exact"], 3 / 6)
        self.assertAlmostEqual(s["within_one"], 5 / 6)
        self.assertEqual((s["over"], s["under"]), (2, 1))
        self.assertAlmostEqual(s["digest_precision"], 2 / 4)     # judge >=2: (3,3),(2,2),(2,1),(3,1) -> 2 right
        self.assertAlmostEqual(s["digest_recall"], 2 / 3)        # human >=2: (3,3),(2,2),(1,2) -> 2 caught
        self.assertEqual(s["matrix"][1][3], 1)                   # human 1, judge 3

    def test_report_with_and_without_labels(self):
        conn = _conn()
        items = _items(3)
        evalbank.bank(conn, "2026-09-07", items, _results(items, [3, 2, 1]), "m", "live", "P")
        text = evalbank.report(conn, today="2026-09-07")
        self.assertIn("No labelled verdicts yet", text)
        conn.execute("UPDATE judge_verdicts SET human_score = 3, human_source='sample', human_note='spot on' WHERE item_id='pq:0'")
        conn.execute("UPDATE judge_verdicts SET human_score = 1, human_source='sample' WHERE item_id='pq:1'")
        text = evalbank.report(conn, write_to=os.path.join(tempfile.mkdtemp(), "judge-eval.md"), today="2026-09-07")
        self.assertIn("| 2 | 50% | 100% | 1 | 0 | 50% | 100% |", text)
        self.assertIn("## Confusion matrix", text)
        self.assertIn("| 2026-09 | 2 |", text)
        self.assertIn("spot on", text)
        self.assertIn("## Prompt and model versions seen", text)

    def test_rescore_compares_then_and_now_without_touching_the_bank(self):
        conn = _conn()
        items = _items(2)
        evalbank.bank(conn, "2026-09-07", items, _results(items, [3, 1]), "m", "live", "P")
        conn.execute("UPDATE judge_verdicts SET human_score = 3, labelled_at='x'")

        def transport(payload, api_key):
            import json
            ids = [u["id"] for u in json.loads(payload["messages"][0]["content"])]
            return {"content": [{"text": json.dumps([{"id": i, "score": 3, "areas": [2], "why_it_matters": "w"} for i in ids])}],
                    "stop_reason": "end_turn", "usage": {}}
        out = evalbank.rescore(conn, "k", transport=transport)
        self.assertEqual((out["n"], out["same_as_banked"], out["agree_human_then"], out["agree_human_now"]), (2, 1, 1, 2))
        self.assertEqual(conn.execute("SELECT SUM(score) FROM judge_verdicts").fetchone()[0], 4)   # bank untouched


class WiringTests(unittest.TestCase):
    def test_the_pull_banks_and_the_publish_samples_ingests_and_reports(self):
        weekly = open(os.path.join(ROOT, "run_weekly.py"), encoding="utf-8").read()
        self.assertIn("evalbank.bank(conn, week_commencing, items, results", weekly)
        self.assertIn("evalbank.export(conn, week_commencing)", weekly)
        monday = open(os.path.join(ROOT, "run_monday.py"), encoding="utf-8").read()
        for call in ("evalbank.ingest_samples(", "evalbank.write_sample(", "evalbank.report("):
            self.assertIn(call, monday)
        wf = open(os.path.join(ROOT, ".github", "workflows", "monday-publish.yml"), encoding="utf-8").read()
        self.assertIn("docs/judge-eval.md", wf)

    def test_the_table_exists_and_is_watched(self):
        conn = _conn()
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("judge_verdicts", names)
        self.assertIn('("judge_verdicts", "captured_at"', open(os.path.join(ROOT, "tools", "coverage.py"), encoding="utf-8").read())

    def test_rescore_from_the_command_line_asks_before_spending(self):
        src = open(os.path.join(ROOT, "tools", "judge_eval.py"), encoding="utf-8").read()
        self.assertIn("SPENDS API funds", src)
        self.assertIn("--spend", src)


if __name__ == "__main__":
    unittest.main()
