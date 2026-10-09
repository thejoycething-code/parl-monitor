"""A judge reply that is not a list of score objects (9 October 2026: one
item, us_bills:119/s/48, came back as strings and crashed the US weekly)."""

import json
import unittest

from src import triage


def _reply(text):
    return {"content": [{"type": "text", "text": text}], "stop_reason": "end_turn"}


class ReplyShapeTests(unittest.TestCase):
    def test_a_single_object_is_one_score(self):
        out = triage._parse_reply(_reply(json.dumps({"id": "a", "score": 2, "why_it_matters": "x"})))
        self.assertEqual([(r.id, r.score) for r in out], [("a", 2)])

    def test_strings_are_skipped_beside_real_scores(self):
        text = json.dumps(["note", {"id": "a", "score": 1, "why_it_matters": "y"}])
        self.assertEqual([r.id for r in triage._parse_reply(_reply(text))], ["a"])

    def test_a_list_of_strings_is_a_plain_error_not_an_attribute_error(self):
        with self.assertRaises(ValueError):
            triage._parse_reply(_reply('["S. 48", "abortion"]'))


class WeeklyJudgeIsGapSafeTests(unittest.TestCase):
    def test_the_judge_and_the_edition_cannot_stop_the_publish(self):
        with open("jobs/us-weekly.sh", encoding="utf-8") as fh:
            script = fh.read()
        for step in ("tools/us_triage.py --limit", "tools/us_monitor.py --edition --dm"):
            line = next(l for l in script.splitlines() if step in l)
            nxt = script.splitlines()[script.splitlines().index(line) + 1]
            self.assertIn("|| echo", line + nxt, step)
        self.assertGreater(script.rindex("db_state.py --push"), script.rindex("us_triage.py --limit"))


if __name__ == "__main__":
    unittest.main()
