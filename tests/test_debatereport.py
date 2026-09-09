"""The debate report (Christopher, 2026-09-09): 500-1000 words, social copy, approval DM.

The checks matter more than the generation: the writer is a language model, and the four
ways its output could embarrass us are wrong length, an invented link, a quote that is
not really in the speeches, and a member we never confirmed reading as one of ours.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import debatereport as dr  # noqa: E402

SPEECHES = [
    {"name": "Steve Yemm", "party": "Lab", "seat": "Mansfield", "confirmed": "yes",
     "pass_read": "With us", "contributions": [
         {"at": "16:58:00", "words": 40, "url": "https://hansard.parliament.uk/Commons/2026-09-07/debates/D1/#contribution-A",
          "text": "In our society, some things should never be reduced to questions of contract, "
                  "individual choice or intention, and motherhood is certainly one of them."},
         {"at": "17:12:40", "words": 8, "url": "https://hansard.parliament.uk/Commons/2026-09-07/debates/D1/#contribution-B",
          "text": "Does my hon. Friend agree?"}]},
    {"name": "Rachel Taylor", "party": "Lab", "seat": "North Warwickshire", "confirmed": "no",
     "pass_read": "Against us", "contributions": [
         {"at": "17:18:17", "words": 20, "url": "https://hansard.parliament.uk/Commons/2026-09-07/debates/D1/#contribution-C",
          "text": "To suggest that the concept of consent can be questioned after consent has been given is dangerous."}]},
]
META = {"title": "Surrogacy Law and Legal Parenthood", "date": "2026-09-07", "house": "Commons",
        "hansard_url": "https://hansard.parliament.uk/Commons/2026-09-07/debates/D1/"}


class BriefTests(unittest.TestCase):
    def test_only_the_longest_contribution_per_speaker_is_sent(self):
        got = dr.speaker_brief(SPEECHES)
        self.assertEqual([s["name"] for s in got], ["Steve Yemm", "Rachel Taylor"])
        self.assertIn("motherhood is certainly one of them", got[0]["text"])
        self.assertNotIn("Does my hon. Friend agree", got[0]["text"])   # the intervention is not sent
        self.assertTrue(got[0]["confirmed_onside"])
        self.assertFalse(got[1]["confirmed_onside"])

    def test_payload_states_the_counts_each_way(self):
        p = dr.build_payload(META, dr.speaker_brief(SPEECHES))
        import json
        body = json.loads(p["messages"][0]["content"])
        self.assertEqual(body["debate"]["onside_count"], 1)
        self.assertEqual(body["debate"]["other_count"], 1)
        self.assertIn("VERBATIM", p["system"])


class SplitTests(unittest.TestCase):
    def test_three_sections_split_apart(self):
        reply = "<<<REPORT>>>\nThe report body.\n<<<SOCIAL>>>\n## Lead post\nx\n<<<SUMMARY>>>\nOne line.\nTwo."
        got = dr.split_sections(reply)
        self.assertEqual(got["REPORT"], "The report body.")
        self.assertIn("Lead post", got["SOCIAL"])
        self.assertTrue(got["SUMMARY"].startswith("One line."))

    def test_a_missing_marker_is_none_not_a_guess(self):
        got = dr.split_sections("<<<REPORT>>>\nonly the report")
        self.assertEqual(got["REPORT"], "only the report")
        self.assertIsNone(got["SOCIAL"])
        self.assertIsNone(got["SUMMARY"])


class WordCountTests(unittest.TestCase):
    def test_link_targets_and_furniture_do_not_count(self):
        md = "> [Steve Yemm](https://hansard.parliament.uk/x) said three words"
        self.assertEqual(dr.word_count(md), 5)      # Steve Yemm said three words


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.speakers = dr.speaker_brief(SPEECHES)
        self.body = " ".join(["word"] * 600)

    def _sections(self, report):
        return {"REPORT": report, "SOCIAL": "x", "SUMMARY": "y"}

    def test_a_good_report_passes(self):
        report = self.body + ' Yemm said: "In our society, some things should never be reduced to questions of contract, individual choice or intention, and motherhood is certainly one of them."'
        self.assertEqual(dr.check(self._sections(report), self.speakers), [])

    def test_too_short_is_caught(self):
        problems = dr.check(self._sections("Three words only"), self.speakers)
        self.assertTrue(any("outside 500-1000" in p for p in problems), problems)

    def test_an_invented_link_is_caught(self):
        report = self.body + " [source](https://citizengo.org/en-gb/made-up-page)"
        self.assertTrue(any("invented or off-list link" in p for p in dr.check(self._sections(report), self.speakers)))

    def test_a_hansard_link_that_was_supplied_is_allowed(self):
        report = self.body + " [Steve Yemm](https://hansard.parliament.uk/Commons/2026-09-07/debates/D1/#contribution-A)"
        self.assertEqual([p for p in dr.check(self._sections(report), self.speakers) if "link" in p], [])

    def test_a_quote_that_is_not_in_the_speeches_is_caught(self):
        report = self.body + ' He said: "Surrogacy should be banned outright tomorrow and the industry shut down for good."'
        self.assertTrue(any("not found verbatim" in p for p in dr.check(self._sections(report), self.speakers)))

    def test_a_paraphrased_quote_is_caught_even_when_close(self):
        # the real words are "some things should never be reduced to questions of contract"
        report = self.body + ' He said: "some things must never be reduced to matters of contract and individual choice."'
        self.assertTrue(any("not found verbatim" in p for p in dr.check(self._sections(report), self.speakers)))

    def test_a_member_who_is_not_onside_reading_as_ours_is_caught(self):
        report = self.body + " Rachel Taylor warned that the change would strip safeguards from women."
        self.assertTrue(any("not confirmed onside" in p for p in dr.check(self._sections(report), self.speakers)))

    def test_no_report_section_is_the_only_complaint(self):
        self.assertEqual(dr.check({"REPORT": None}, self.speakers), ["no REPORT section in the reply"])


class ApprovalDmTests(unittest.TestCase):
    def test_the_dm_asks_and_never_claims_to_have_published(self):
        sections = {"REPORT": " ".join(["word"] * 700), "SUMMARY": "Eight MPs spoke against.\n8 against, 4 for."}
        reels = [{"name": "Jim Shannon", "party": "DUP", "duration": 57.0}]
        text = dr.approval_dm(META, sections, reels, [], "data/packs/x")
        self.assertIn("ready for approval", text)
        self.assertIn("Eight MPs spoke against.", text)
        self.assertIn("Jim Shannon", text)
        self.assertIn("--publish", text)
        self.assertIn("Nothing reaches the channel", text)
        self.assertNotIn("published to", text.lower())

    def test_failed_checks_are_named_in_the_dm(self):
        text = dr.approval_dm(META, {"REPORT": "x", "SUMMARY": "s"}, [], ["report is 220 words, outside 500-1000"], "p")
        self.assertIn("Checks that failed", text)
        self.assertIn("220 words", text)

    def test_a_clean_run_says_so(self):
        text = dr.approval_dm(META, {"REPORT": "x", "SUMMARY": "s"}, [], [], "p")
        self.assertIn("All automatic checks passed", text)


class GenerateTests(unittest.TestCase):
    def test_it_refuses_when_nobody_is_confirmed_onside(self):
        nobody = [dict(s, confirmed="no") for s in SPEECHES]
        with self.assertRaises(SystemExit) as caught:
            dr.generate(META, nobody, "key", transport=lambda p, k: {})
        self.assertIn("confirmed onside", str(caught.exception))

    def test_usage_is_recorded_and_sections_returned(self):
        import sqlite3
        from src import db
        conn = db.init_db(sqlite3.connect(":memory:"))
        reply = {"model": "claude-sonnet-5", "usage": {"input_tokens": 12000, "output_tokens": 1200},
                 "content": [{"type": "text", "text": "<<<REPORT>>>\n" + " ".join(["word"] * 700) +
                              "\n<<<SOCIAL>>>\nposts\n<<<SUMMARY>>>\nline one\nline two"}]}
        sections, problems, usage = dr.generate(META, SPEECHES, "key", conn=conn,
                                                transport=lambda p, k: reply, log=lambda *_a: None)
        self.assertEqual(usage["input_tokens"], 12000)
        self.assertEqual(dr.word_count(sections["REPORT"]), 700)
        self.assertEqual(problems, [])
        row = conn.execute("SELECT pass_name, calls, input_tokens FROM api_spend").fetchone()
        self.assertEqual((row[0], row[1], row[2]), ("debate-report", 1, 12000))


if __name__ == "__main__":
    unittest.main()
