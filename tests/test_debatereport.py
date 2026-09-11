"""The debate report (Christopher, 2026-09-09): 500-1000 words, social copy, approval DM.

The checks matter more than the generation: the writer is a language model, and the four
ways its output could embarrass us are wrong length, an invented link, a quote that is
not really in the speeches, and a member we never confirmed reading as one of ours.
"""

import json
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


class ProvisionalTests(unittest.TestCase):
    """A blank checklist on the evening of the debate: the pass read may stand in for a
    DRAFT, the draft says so everywhere, and nothing clears it but the checklist."""

    BLANK = [dict(SPEECHES[0], confirmed=""), dict(SPEECHES[1], confirmed="")]

    def test_brief_is_unchanged_unless_asked(self):
        self.assertFalse(any(s["confirmed_onside"] for s in dr.speaker_brief(self.BLANK)))
        prov = dr.speaker_brief(self.BLANK, provisional=True)
        self.assertEqual([s["name"] for s in prov if s["confirmed_onside"]], ["Steve Yemm"])

    def test_a_checklist_no_is_never_overridden(self):
        said_no = [dict(SPEECHES[0], confirmed="no")]
        self.assertFalse(dr.speaker_brief(said_no, provisional=True)[0]["confirmed_onside"])

    def test_generate_refuses_a_blank_checklist_unless_provisional(self):
        with self.assertRaises(SystemExit) as caught:
            dr.generate(META, self.BLANK, "key", transport=lambda p, k: {})
        self.assertIn("--provisional", str(caught.exception))
        sent = {}
        reply = {"content": [{"type": "text", "text": "<<<REPORT>>>\nr\n<<<SOCIAL>>>\ns\n<<<SUMMARY>>>\nx"}]}

        def transport(payload, key):
            sent.update(payload)
            return reply
        dr.generate(META, self.BLANK, "key", transport=transport, log=lambda *_a: None, provisional=True)
        user = json.loads(sent["messages"][0]["content"])
        self.assertTrue(user["debate"]["provisional"])
        self.assertEqual(user["debate"]["onside_count"], 1)

    def test_provisional_with_nobody_read_with_us_still_refuses(self):
        nobody = [dict(SPEECHES[1], confirmed="")]
        with self.assertRaises(SystemExit):
            dr.generate(META, nobody, "key", transport=lambda p, k: {}, provisional=True)

    def test_the_dm_says_provisional_and_does_not_offer_publish_as_the_next_step(self):
        text = dr.approval_dm(META, {"REPORT": "x", "SUMMARY": "s"}, [], [], "p", provisional=True)
        self.assertTrue(text.startswith("*PROVISIONAL"))
        self.assertIn("checklist.md", text)
        self.assertIn("refuses a provisional report", text)
        plain = dr.approval_dm(META, {"REPORT": "x", "SUMMARY": "s"}, [], [], "p")
        self.assertNotIn("PROVISIONAL", plain)

    def test_publish_blockers(self):
        self.assertEqual(dr.publish_blockers({}), [])
        self.assertEqual(len(dr.publish_blockers({"problems": ["x"]})), 1)
        self.assertEqual(dr.publish_blockers({"problems": ["x"]}, force=True), [])
        self.assertEqual(len(dr.publish_blockers({"provisional": True}, force=True)), 1)


class CheckerNormalisationTests(unittest.TestCase):
    """Two false alarms from the 11 September 2026 report."""

    def test_inner_quote_marks_do_not_break_a_verbatim_quote(self):
        hansard = "The soft language of “assisted dying” is misleading the public, because it obscures the reality."
        report = "The soft language of 'assisted dying' is misleading the public, because it obscures the reality."
        self.assertEqual(dr._norm(hansard), dr._norm(report))
        self.assertIn("don't", dr._norm("Don't"))       # a real apostrophe survives

    def test_the_headline_is_not_a_named_thing(self):
        md = "# MPs Vote Down Assisted Dying Bill At Second Reading\n\nThe Human Fertilisation and Embryology Act 2008 was cited."
        ents = dr.named_entities(md)
        self.assertTrue(any(e.endswith("Human Fertilisation and Embryology Act 2008") for e in ents), ents)
        self.assertFalse(any("Vote Down" in e for e in ents), ents)

    def test_a_quote_from_deep_in_a_long_speech_is_checked_against_the_whole_speech(self):
        long_speech = " ".join("word%d." % i for i in range(1200)) + " The tail sentence that matters here is this one."
        sp = [{"name": "Long Speaker", "party": "Con", "seat": "S", "confirmed": "yes", "pass_read": "With us",
               "contributions": [{"at": "10:00:00", "words": 1210, "url": "https://hansard.parliament.uk/x", "text": long_speech}]}]
        speakers = dr.speaker_brief(sp)
        self.assertLess(len(speakers[0]["text"].split()), 1000)          # the writer still gets the cut
        report = 'Long Speaker said: "The tail sentence that matters here is this one."'
        self.assertEqual([p for p in dr.check({"REPORT": report, "SOCIAL": ""}, speakers) if "verbatim" in p], [])
        payload = dr.build_payload({}, speakers)
        self.assertNotIn("full_text", payload["messages"][0]["content"])


class CanvasBodyTests(unittest.TestCase):
    def test_preview_says_what_it_is_and_does_not_claim_approval(self):
        body = dr.canvas_body(META, "Report text.", preview=True, provisional=True, problems=["x"])
        self.assertTrue(body.startswith("> PREVIEW"))
        self.assertIn(dr.PROVISIONAL_NOTE, body)
        self.assertIn("Checks that failed: x", body)
        self.assertNotIn("approved by hand", body)
        self.assertIn("Report text.", body)

    def test_published_body_is_the_report_alone_with_the_approved_footer(self):
        body = dr.canvas_body(META, "Report text.")
        self.assertTrue(body.startswith("Report text."))
        self.assertIn("approved by hand", body)
        self.assertNotIn("PREVIEW", body)
        self.assertIn(META["hansard_url"], body)

    def test_summaries_differ(self):
        self.assertIn("--publish", dr.canvas_summary(META, preview=True))
        self.assertIn("Recording Unit", dr.canvas_summary(META))


class QuotationExtractionTests(unittest.TestCase):
    """Straight quotes carry no open/close distinction, so a naive pairing reads the
    PROSE BETWEEN two quotations as a quotation. On the first real report (2026-09-10)
    that gave four false alarms, three of them markdown links, against two genuine
    paraphrases -- and a check that cries wolf stops being read."""

    def test_a_markdown_link_between_two_quotes_is_not_a_quotation(self):
        md = ('He said "the first real quotation here is long enough to count", and then '
              '[Rachel Taylor](https://hansard.parliament.uk/x) spoke; "the second real '
              'quotation is also long enough to count" was hers.')
        got = dr.quotations(md)
        self.assertEqual(len(got), 2, got)
        self.assertTrue(all("](" not in q for q in got))

    def test_curly_and_straight_quotes_are_both_found(self):
        md = ('She said “this curly quotation is quite long enough to count” and '
              '"this straight quotation is also comfortably past the floor".')
        self.assertEqual(len(dr.quotations(md)), 2)

    def test_the_forty_character_floor_is_deliberate(self):
        """Short quoted fragments are usually a word or a phrase, not a claim about what
        someone said, and checking them against the speeches produces noise."""
        self.assertEqual(dr.quotations('He called it "a market in all but name".'), [])

    def test_short_fragments_are_not_treated_as_quotations(self):
        self.assertEqual(dr.quotations('He said "too short".'), [])

    def test_a_real_paraphrase_is_still_caught(self):
        speakers = [{"name": "T", "party": "Lab", "seat": "S", "confirmed_onside": True, "pass_read": "",
                     "hansard_url": "", "words": 10,
                     "text": "The proposals recommend tipping the balance of power away from the birth mother."}]
        report = " ".join(["word"] * 600) + ' She said the proposals "tip the balance of power away from the birth mother".'
        problems = dr.check({"REPORT": report}, speakers)
        self.assertTrue(any("not found verbatim" in p for p in problems), problems)


class NamedEntityTests(unittest.TestCase):
    """The first real report (2026-09-10) wrote "Human Fertilehood and Embryology Act
    2008" for "Human Fertilisation and Embryology Act 2008". Every other check passed
    it: a garbled statute name is not a quote, not a link, and not a length problem."""

    SPEAKERS = [{"name": "A", "party": "Lab", "seat": "S", "confirmed_onside": True, "pass_read": "",
                 "hansard_url": "", "words": 30,
                 "text": "Under the Human Fertilisation and Embryology Act 2008 the surrogate is the "
                         "legal mother, and the Law Commission has proposed reform."}]

    def test_a_garbled_statute_name_is_caught(self):
        report = " ".join(["word"] * 600) + " Under the Human Fertilehood and Embryology Act 2008 the surrogate is the mother."
        problems = dr.check({"REPORT": report}, self.SPEAKERS)
        self.assertTrue(any("named thing not found" in p and "Fertilehood" in p for p in problems), problems)

    def test_a_correct_statute_name_passes(self):
        report = " ".join(["word"] * 600) + " Under the Human Fertilisation and Embryology Act 2008 the surrogate is the mother."
        self.assertEqual([p for p in dr.check({"REPORT": report}, self.SPEAKERS) if "named thing" in p], [])

    def test_a_body_named_in_the_speeches_passes(self):
        report = " ".join(["word"] * 600) + " The Law Commission proposed reform."
        self.assertEqual([p for p in dr.check({"REPORT": report}, self.SPEAKERS) if "named thing" in p], [])

    def test_link_targets_are_not_scanned_for_names(self):
        report = " ".join(["word"] * 600) + " [A](https://hansard.parliament.uk/Commons/Act2008/Committee)"
        self.assertEqual([p for p in dr.check({"REPORT": report}, self.SPEAKERS) if "named thing" in p], [])


class ElisionTests(unittest.TestCase):
    """An ellipsis inside one sentence is ordinary journalism. Checking the whole span
    verbatim would flag every properly elided quote, so each side is checked separately."""

    SPEAKERS = [{"name": "A", "party": "DUP", "seat": "S", "confirmed_onside": True, "pass_read": "",
                 "hansard_url": "", "words": 40,
                 "text": "An important distinction must be made between the women who voluntarily agree "
                         "to carry a child for someone they know, perhaps with reasonable expenses "
                         "being covered, and the wholly exploitative system whereby a womb is bought."}]

    def test_a_properly_elided_quote_passes(self):
        report = (" ".join(["word"] * 600) + ' He said "an important distinction must be made between the '
                  'women who voluntarily agree to carry a child for someone they know...and the wholly '
                  'exploitative system whereby a womb is bought."')
        self.assertEqual([p for p in dr.check({"REPORT": report}, self.SPEAKERS) if "verbatim" in p], [])

    def test_an_elision_hiding_invented_words_is_still_caught(self):
        report = (" ".join(["word"] * 600) + ' He said "an important distinction must be made between the '
                  'women who voluntarily agree...and the surrogacy industry should be shut down entirely."')
        self.assertTrue(any("verbatim" in p for p in dr.check({"REPORT": report}, self.SPEAKERS)))


class SelectionTests(unittest.TestCase):
    """Who the writer is shown when the debate is bigger than the brief (2026-09-11)."""

    def speeches(self):
        def one(name, party, confirmed, *words):
            return {"name": name, "party": party, "seat": "Seat", "confirmed": confirmed, "pass_read": "",
                    "contributions": [{"at": "10:00:00", "words": w, "url": "https://hansard.parliament.uk/x#%s%d" % (name, i),
                                       "text": " ".join(["word"] * w)} for i, w in enumerate(words)]}
        sp = [one("Opener", "Lab", "no", *([60] * 10))]          # 600 words in ten interrupted pieces
        sp += [one("Onside %02d" % i, "Con", "yes", 100 + i) for i in range(20)]
        sp += [one("Long Against", "LD", "no", 900), one("Alison McGovern", "", "no", 80)]
        sp += [one("Short Against %d" % i, "Lab", "no", 30) for i in range(6)]
        return sp

    def test_the_opener_and_the_minister_are_always_in(self):
        picked = dr._select(self.speeches(), 16, provisional=False)
        names = [s["name"] for s in picked]
        self.assertEqual(len(names), 16)
        self.assertEqual(names[0], "Opener")                       # speaking order is kept
        self.assertIn("Alison McGovern", names)                    # attributed by office: no party
        self.assertIn("Long Against", names)

    def test_onside_speakers_rank_by_all_their_words(self):
        picked = dr._select(self.speeches(), 16, provisional=False)
        ours = [s["name"] for s in picked if s["confirmed"] == "yes"]
        self.assertEqual(len(ours), 16 - 2 - 5)                    # room after the two pinned and the five others
        self.assertIn("Onside 19", ours)
        self.assertNotIn("Onside 00", ours)

    def test_a_small_debate_is_sent_whole(self):
        self.assertEqual(len(dr._select(SPEECHES, 16, provisional=False)), 2)
