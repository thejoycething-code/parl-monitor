"""Selecting the best speeches (Christopher, 2026-09-11). No network."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import selectspeeches as sel, socialcut as sc  # noqa: E402

LONG = " ".join(["Surrogacy asks a child to live with promises adults made before it was born and that matters to this House."] * 30)
SPEECHES = [
    {"name": "Big Speaker", "party": "Con", "seat": "A", "confirmed": "yes", "pass_read": "With us",
     "contributions": [{"at": "10:00:00", "words": 570, "url": "https://hansard.parliament.uk/x/1", "text": LONG}]},
    {"name": "Intervener", "party": "Lab", "seat": "B", "confirmed": "yes", "pass_read": "With us",
     "contributions": [{"at": "10:05:00", "words": 40, "url": "u", "text": "A short intervention that is not a speech at all."}]},
    {"name": "Other Side", "party": "Lab", "seat": "C", "confirmed": "no", "pass_read": "Against us",
     "contributions": [{"at": "10:10:00", "words": 600, "url": "u", "text": LONG}]},
    {"name": "Unconfirmed", "party": "LD", "seat": "D", "confirmed": "", "pass_read": "With us, strongly",
     "contributions": [{"at": "10:20:00", "words": 600, "url": "u", "text": LONG}]},
]
META = {"title": "A Bill", "date": "2026-09-11", "house": "Commons"}


class CandidateTests(unittest.TestCase):
    def test_only_confirmed_onside_members_with_a_real_speech(self):
        c = sel.candidates(SPEECHES)
        self.assertEqual([x["name"] for x in c], ["Big Speaker"])        # not the intervener, not the other side, not the pass read
        self.assertLessEqual(len(c[0]["text"].split()), sel.WORDS_SHOWN)
        self.assertNotIn("full_text", json.dumps(sel.build_payload(META, c)["messages"][0]["content"]))


class VerifyTests(unittest.TestCase):
    def test_verbatim_passages_survive_paraphrases_are_dropped_unknown_names_refused(self):
        c = sel.candidates(SPEECHES)
        good = "Surrogacy asks a child to live with promises adults made before it was born and that matters to this House."
        rows = [{"name": "Big Speaker", "score": 9, "angle": "child", "why": "clear", "passage": good},
                {"name": "Nobody Here", "score": 8, "passage": good},
                ]
        ranked, problems = sel.verify(rows, c)
        self.assertEqual([r["name"] for r in ranked], ["Big Speaker"])
        self.assertEqual(ranked[0]["passage"], good)
        self.assertTrue(any("unknown speaker" in p for p in problems))
        ranked2, problems2 = sel.verify([{"name": "Big Speaker", "score": 7, "passage": "Surrogacy asks a child to accept promises."}], c)
        self.assertEqual(ranked2[0]["passage"], "")
        self.assertTrue(any("not verbatim" in p for p in problems2))

    def test_a_reply_cut_off_mid_array_keeps_the_complete_objects(self):
        cut = '[{"name":"A","score":9,"passage":"p"}, {"name":"B","score":8,"passage":"q"}, {"name":"C","sco'
        self.assertEqual([r["name"] for r in sel.parse_reply(cut)], ["A", "B"])

    def test_parse_reply_tolerates_a_code_fence(self):
        self.assertEqual(sel.parse_reply('Here you go:\n```json\n[{"name":"A","score":5}]\n```'), [{"name": "A", "score": 5}])
        self.assertEqual(sel.parse_reply("no json here"), [])


class BatchTests(unittest.TestCase):
    def test_the_judge_calls_once_per_batch_and_pools_the_scores(self):
        import sqlite3
        from src import db
        conn = db.init_db(sqlite3.connect(":memory:"))
        cands = [{"name": "S%d" % i, "party": "Lab", "seat": "x", "words": 300, "url": "", "text": "t", "full_text": "t"} for i in range(5)]
        calls = []
        def transport(payload, key):
            names = [s["name"] for s in json.loads(payload["messages"][0]["content"])["speakers"]]
            calls.append(names)
            return {"usage": {"input_tokens": 10, "output_tokens": 5}, "content": [{"type": "text", "text": json.dumps([{"name": n, "score": 5, "passage": ""} for n in names])}]}
        ranked, problems, usage, _raw = sel.judge(META, cands, "k", transport=transport, conn=conn, log=lambda *_a: None, batch=2)
        self.assertEqual(calls, [["S0", "S1"], ["S2", "S3"], ["S4"]])
        self.assertEqual(len(ranked), 5); self.assertEqual(usage["input_tokens"], 30)
        self.assertEqual(conn.execute("SELECT count(*) FROM api_spend").fetchone()[0], 3)


class JudgeAndWriteTests(unittest.TestCase):
    def test_judge_records_spend_and_sequence_uses_the_judges_passage_when_reel_length(self):
        import sqlite3
        from src import db
        conn = db.init_db(sqlite3.connect(":memory:"))
        c = sel.candidates(SPEECHES)
        passage = " ".join(["Surrogacy asks a child to live with promises adults made before it was born and that matters to this House."] * 6)
        reply = {"model": "claude-sonnet-5", "usage": {"input_tokens": 3000, "output_tokens": 400},
                 "content": [{"type": "text", "text": json.dumps([{"name": "Big Speaker", "score": 9, "angle": "the child", "why": "w", "passage": passage}])}]}
        ranked, problems, usage, _raw = sel.judge(META, c, "key", transport=lambda p, k: reply, conn=conn, log=lambda *_a: None)
        self.assertEqual(problems, [])
        self.assertEqual(conn.execute("SELECT pass_name FROM api_spend").fetchone()[0], "speech-pick")
        self.assertTrue(sc.REEL_FLOOR_S <= ranked[0]["seconds"] <= sc.REEL_HARD_CAP_S, ranked[0]["seconds"])
        seq = sel.sequence_md(META, ranked, 8, SPEECHES, [])
        entries = sc.parse_sequence(seq)
        self.assertEqual([e["name"] for e in entries], ["Big Speaker MP"])
        self.assertEqual(entries[0]["passage"], passage)
        md = sel.selection_md(META, ranked, problems, 8)
        self.assertIn("| 1 | **[Big Speaker]", md)

    def test_a_short_judge_passage_falls_back_to_reel_passage(self):
        import re
        c = sel.candidates(SPEECHES)
        ranked, _ = sel.verify([{"name": "Big Speaker", "score": 8, "passage": "Surrogacy asks a child to live with promises adults made before it was born and that matters to this House."}], c)
        seq = sel.sequence_md(META, ranked, 8, SPEECHES, [re.compile(r"surrogac", re.I)])
        e = sc.parse_sequence(seq)[0]
        self.assertGreaterEqual(sc.spoken_seconds(e["passage"]), sc.REEL_FLOOR_S)


if __name__ == "__main__":
    unittest.main()
