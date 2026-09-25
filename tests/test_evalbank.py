"""The judge evaluation corpus (Christopher, 2026-09-07)."""

import json
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


class SampleExcludesCollatedOnlyTests(unittest.TestCase):
    """A reviewer's time is the scarcest thing in the corpus.

    The first German sample put four of ten verdicts on migration items --
    Ukraine deportations, asylum benefits, Afghan deportation rules, half-year
    figures. Migration is collated and never campaigned, so it renders
    nowhere: those four verdicts would have bought a surface that does not
    exist, and the labelled corpus would have skewed to the one area we never
    act on.

    Not bad luck. 241 of 659 banked German verdicts are migration-only, so a
    stratified sample lands four in ten there BY CONSTRUCTION.
    """

    def _bank(self, conn, item_id, areas, score=2):
        evalbank.ensure_table(conn)
        conn.execute(
            "INSERT INTO judge_verdicts (week, item_id, feed, title, tier, "
            "candidate_areas, watchlist_hit, score, why, areas, model, "
            "prompt_sha, mode, captured_at) VALUES "
            "('2026-09-21',?,?,?,1,?,0,?,'why',?,'m','sha','live','2026-09-21')",
            (item_id, item_id.split(":")[0], "Titel " + item_id,
             json.dumps(areas), score, json.dumps(areas)))
        conn.commit()

    def test_a_migration_only_verdict_is_left_out(self):
        import tempfile
        conn = _conn() if "_conn" in globals() else db.init_db(
            db.connect(":memory:"))
        self._bank(conn, "de_vorgaenge:1", [11])
        self._bank(conn, "de_vorgaenge:2", [1])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "s.md")
            written, n = evalbank.write_sample(conn, "2026-09-21", path,
                                               exclude_hidden=True)
            body = open(written, encoding="utf-8").read()
        self.assertIn("de_vorgaenge:2", body)
        self.assertNotIn("de_vorgaenge:1", body)
        self.assertEqual(n, 1)

    def test_an_item_that_merely_touches_migration_is_kept(self):
        """The rule suppresses migration-ONLY, never an item that also sits
        on ground we campaign on -- the same rule the edition applies."""
        import tempfile
        conn = db.init_db(db.connect(":memory:"))
        self._bank(conn, "de_vorgaenge:3", [11, 12])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "s.md")
            written, n = evalbank.write_sample(conn, "2026-09-21", path,
                                               exclude_hidden=True)
        self.assertEqual(n, 1)

    def test_it_is_opt_in_so_westminsters_corpus_is_unchanged(self):
        """Westminster's corpus is already part-labelled; changing sample
        composition mid-corpus would make before and after less comparable.
        That is a call for whoever owns it, not a side effect of a German
        fix."""
        import tempfile
        conn = db.init_db(db.connect(":memory:"))
        self._bank(conn, "pq:1", [11])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "s.md")
            written, n = evalbank.write_sample(conn, "2026-09-21", path)
        self.assertEqual(n, 1, "the default must not filter")

    def test_the_german_tool_asks_for_the_exclusion(self):
        import inspect
        import importlib.util as iu
        spec = iu.spec_from_file_location(
            "de_judge_eval", os.path.join(ROOT, "tools", "de_judge_eval.py"))
        mod = iu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertIn("exclude_hidden=True", inspect.getsource(mod))


class AnswerKindTests(unittest.TestCase):
    """Christopher, 2026-09-25: "add answer_kind to the verdict bank."

    The edition ROUTES on this label -- "restated" demotes a reply to one
    line under "Asked, but not answered" -- so an unchecked judge here does
    not misplace an answer, it hides one.
    """

    def _row(self, conn, kind, score=2):
        items = _items(1)
        results = _results(items, [score])
        results[0].answer_kind = kind
        evalbank.bank(conn, "2026-09-21", items, results, "m", "live", "P")
        return items[0].id

    def test_the_bank_records_what_the_judge_called_the_reply(self):
        conn = _conn()
        self._row(conn, "restated")
        got = conn.execute("SELECT answer_kind FROM judge_verdicts").fetchone()
        self.assertEqual(got["answer_kind"], "restated")

    def test_a_rescore_without_a_kind_does_not_blank_one(self):
        """The score prompt returns no answer_kind. Re-running it must not
        erase the labels a reviewer is being measured against."""
        conn = _conn()
        item_id = self._row(conn, "figures")
        items = [i for i in _items(1)]
        results = _results(items, [3])          # no answer_kind on these
        evalbank.bank(conn, "2026-09-21", items, results, "m", "live", "P")
        got = conn.execute("SELECT score, answer_kind FROM judge_verdicts "
                           "WHERE item_id = ?", (item_id,)).fetchone()
        self.assertEqual(got["score"], 3, "the score should have updated")
        self.assertEqual(got["answer_kind"], "figures", "the kind should not")

    def test_the_sample_asks_for_a_kind_and_shows_the_reply(self):
        """A KIND line with no answer above it asks a reviewer to judge
        something they cannot see."""
        import tempfile
        conn = _conn()
        item_id = self._row(conn, "restated")
        conn.execute(
            "INSERT INTO items (id, captured_at, source_feed, item_type, title, "
            "url, extra) VALUES (?, '', 'pq', 'question', 't', '', ?)",
            (item_id, '{"question_text": "what steps she is taking.", '
                      '"answer_text": "The Department remains committed."}'))
        conn.commit()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "judge-sample-2026-09-21.md")
            evalbank.write_sample(conn, "2026-09-21", path)
            text = open(path).read()
        self.assertIn("- answered: The Department remains committed.", text)
        self.assertIn("- judge kind: restated", text)
        self.assertIn("KIND: ", text)

    def test_an_unknown_kind_from_a_reviewer_is_discarded(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "judge-sample-2026-09-21.md")
            with open(path, "w") as fh:
                fh.write("### item: pq:1\nVERDICT: 2\nKIND: waffle\nNOTE: \n")
            _week, rows = evalbank.parse_sample(path)
        self.assertEqual(rows[0][3], None, "an unrecognised word is no label")

    def test_a_kind_alone_counts_and_does_not_blank_the_score(self):
        """A reviewer correcting only the label should not have to restate a
        score they agree with, and a blank must not read as agreement."""
        import tempfile
        conn = _conn()
        item_id = self._row(conn, "restated")
        conn.execute("UPDATE judge_verdicts SET human_score = 3 WHERE item_id = ?",
                     (item_id,))
        conn.commit()
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "judge-sample-2026-09-21.md"), "w") as fh:
                fh.write("### item: {0}\nVERDICT: \nKIND: figures\nNOTE: \n".format(item_id))
            evalbank.ingest_samples(conn, tmp)
        got = conn.execute("SELECT human_score, human_answer_kind FROM "
                           "judge_verdicts WHERE item_id = ?", (item_id,)).fetchone()
        self.assertEqual(got["human_answer_kind"], "figures")
        self.assertEqual(got["human_score"], 3, "the score must survive")

    def test_demotion_is_counted_apart_from_plain_disagreement(self):
        """judge=restated, human=figures HIDES an answer. The reverse only
        takes space. The report must not average them into one number."""
        rows = [{"answer_kind": "restated", "human_answer_kind": "figures"},
                {"answer_kind": "restated", "human_answer_kind": "restated"},
                {"answer_kind": "figures", "human_answer_kind": "restated"},
                {"answer_kind": "position", "human_answer_kind": "position"}]
        st = evalbank.kind_stats(rows)
        self.assertEqual(st["n"], 4)
        self.assertEqual(st["wrongly_demoted"], 1)
        self.assertEqual(st["wrongly_kept"], 1)
        self.assertAlmostEqual(st["exact"], 0.5)

    def test_unlabelled_is_reported_as_unchecked_not_as_agreement(self):
        conn = _conn()
        self._row(conn, "restated")
        text = evalbank.report(conn)
        self.assertIn("## Answer kind", text)
        self.assertIn("No reviewer has labelled a kind yet", text)
        self.assertIn("not the same as agreeing", text)


class EvalLoopIsScheduledTests(unittest.TestCase):
    """Wired into the Monday publish on 2026-09-25, at Christopher's
    request. Until then judge_eval.py was in no workflow at all: the sample
    was written and the report regenerated only when somebody remembered.
    A bank nobody samples is a corpus that stops growing, and since the
    edition ROUTES on answer_kind an unchecked judge quietly hides answers.
    """

    def _publish(self):
        return open(os.path.join(ROOT, ".github", "workflows",
                                 "monday-publish.yml"), encoding="utf-8").read()

    def test_the_monday_publish_runs_the_eval_loop(self):
        src = self._publish()
        for action in ("judge_eval.py ingest", "judge_eval.py sample",
                       "judge_eval.py report --write"):
            self.assertIn(action, src,
                          "{0} is not in the Monday publish".format(action))

    def test_ingest_runs_before_sample_and_report(self):
        """A checklist filled in during the week must be read BEFORE
        anything measures agreement, or the report describes last week's
        corpus while handing out this week's sample."""
        src = self._publish()
        self.assertLess(src.index("judge_eval.py ingest"),
                        src.index("judge_eval.py sample"))
        self.assertLess(src.index("judge_eval.py sample"),
                        src.index("judge_eval.py report"))

    def test_the_loop_runs_before_the_store_is_published(self):
        """ingest writes human verdicts INTO the store. After the push they
        would sit in a store the next run replaces."""
        src = self._publish()
        self.assertLess(src.index("judge_eval.py ingest"),
                        src.index("db_state.py --push"))

    def test_the_committed_paths_cover_what_the_loop_writes(self):
        src = self._publish()
        commit = src[src.index("name: Commit state"):]
        for path in ("reviews/", "docs/judge-eval.md"):
            self.assertIn(path, commit,
                          "{0} is written by the eval loop and never "
                          "committed".format(path))

    def test_a_filled_checklist_is_never_overwritten(self):
        """Harmless while a human ran sample deliberately; now the Monday
        publish runs it, and a second run in the same week would blank a
        reviewer's work."""
        import importlib.util as iu
        import inspect
        spec = iu.spec_from_file_location(
            "judge_eval", os.path.join(ROOT, "tools", "judge_eval.py"))
        mod = iu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        src = inspect.getsource(mod.main)
        self.assertIn("already has", src)
        self.assertIn("parse_sample(target)", src)

    def test_rescore_is_NOT_scheduled(self):
        """Every other action reads the store. rescore SPENDS, asks before
        it does, and stays a human decision."""
        self.assertNotIn("judge_eval.py rescore", self._publish())


if __name__ == "__main__":
    unittest.main()
