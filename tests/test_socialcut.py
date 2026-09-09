"""The social cut (Christopher, 2026-09-08): sequence file, caption cards, crop, timing, ASS."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import socialcut as sc  # noqa: E402

SEQ = """# Sequence: surrogacy, 7 Sept

## Shivani Raja MP
party: Conservative · Leicester East
> A child cannot consent to a surrogacy arrangement.
> They cannot understand the promises adults have made.

## Jonathan Hinder MP
party: Labour · Pendle and Clitheroe
crop: left
> Pregnant women are not factories. Babies are not goods to be ordered.

## Nobody Here
party: none
"""


class SequenceTests(unittest.TestCase):
    def test_entries_in_file_order_with_party_crop_and_joined_passage(self):
        entries = sc.parse_sequence(SEQ)
        self.assertEqual([e["name"] for e in entries], ["Shivani Raja MP", "Jonathan Hinder MP"])   # the entry with no passage is dropped
        self.assertEqual(entries[0]["party"], "Conservative · Leicester East")
        self.assertEqual(entries[0]["crop"], "centre")
        self.assertEqual(entries[1]["crop"], "left")
        self.assertEqual(entries[0]["passage"], "A child cannot consent to a surrogacy arrangement. They cannot understand the promises adults have made.")

    def test_slug(self):
        self.assertEqual(sc.slug("Dr Neil Shastri-Hurst MP"), "dr-neil-shastri-hurst-mp")


class CaptionTests(unittest.TestCase):
    def test_short_sentence_is_one_card_of_one_or_two_lines(self):
        cards = sc.chunk_caption("Pregnant women are not factories.")
        self.assertEqual(len(cards), 1)
        self.assertLessEqual(len(cards[0]), 2)
        self.assertEqual(" ".join(cards[0]), "Pregnant women are not factories.")

    def test_cards_never_exceed_two_lines_of_thirty_characters(self):
        text = ("We must also speak for the child who cannot speak for his or herself, and protect the woman "
                "who carries and gives birth to that child. Compensation for genuine expenses of carrying a baby is one thing.")
        cards = sc.chunk_caption(text)
        for card in cards:
            self.assertLessEqual(len(card), 2, card)
            for line in card:
                self.assertLessEqual(len(line), 30, line)
        self.assertEqual(" ".join(" ".join(c) for c in cards), text)     # nothing lost, nothing reordered

    def test_gilberts_sentence_makes_two_line_cards_not_three(self):
        cards = sc.chunk_caption("50% of responses to the Law Commission’s consultation called for a total ban on surrogacy in the UK. I fully support that ban.")
        for card in cards:
            self.assertLessEqual(len(card), 2, card)
            for line in card:
                self.assertLessEqual(len(line), 30, line)
        self.assertEqual(" ".join(cards[-1]), "I fully support that ban.")

    def test_a_long_sentence_breaks_at_its_clauses(self):
        cards = sc.chunk_caption("We must also speak for the child who cannot speak for his or herself, and protect the woman who carries and gives birth to that child.")
        texts = [" ".join(c) for c in cards]
        self.assertTrue(any(t.endswith("herself,") for t in texts), texts)      # a card ends where the comma is
        for card in cards:
            self.assertLessEqual(len(card), 2, card)

    def test_no_card_is_left_holding_two_orphaned_words(self):
        for text in ("Compensation for genuine expenses of carrying a baby is one thing.",
                     "and protect the woman who carries and gives birth to that child.",
                     "which I believe should never be reduced to questions around contract and individual choice or intention."):
            cards = sc.chunk_caption(text)
            self.assertGreater(len(cards), 1)
            for card in cards:
                self.assertGreaterEqual(len(" ".join(card)), 20, (text, card))

    def test_a_card_never_crosses_a_sentence_boundary(self):
        cards = sc.chunk_caption("A child cannot consent. They cannot understand the promises adults have made.")
        self.assertEqual(" ".join(cards[0]), "A child cannot consent.")

    def test_card_times_follow_the_transcript_by_position(self):
        words = [("a", 0.0, 0.2), ("child", 0.2, 0.5), ("cannot", 0.5, 0.9), ("consent.", 0.9, 1.4),
                 ("they", 1.8, 2.0), ("cannot", 2.0, 2.3), ("understand.", 2.3, 2.9)]
        passage = "A child cannot consent. They cannot understand."
        cards = [["A child cannot consent."], ["They cannot understand."]]
        times = sc.card_times(words, cards, passage)
        self.assertEqual(times[0], (0.0, 1.4))
        self.assertEqual(times[1], (1.8, 2.9))


class DraftTests(unittest.TestCase):
    QUOTES = """# Quotes: Surrogacy (2026-09-07)

*Whole sentences...*

## Jim Shannon (DUP, Strangford)

> Commercial surrogacy is illegal in the UK but permitted abroad.

— [Hansard](https://example)

> A second quote that must not be used.

## Rebecca Smith (Con, South West Devon)

> The legal process provides important protections.

## Nobody Quoted (Lab, Nowhere)
"""

    def test_draft_takes_first_quote_per_confirmed_speaker_in_speaking_order_and_parses_back(self):
        text = sc.draft_sequence(self.QUOTES, "Surrogacy", "2026-09-07")
        entries = sc.parse_sequence(text)
        self.assertEqual([e["name"] for e in entries], ["Jim Shannon MP", "Rebecca Smith MP"])
        self.assertEqual(entries[0]["party"], "DUP · Strangford")
        self.assertEqual(entries[1]["party"], "Conservative · South West Devon")
        self.assertEqual(entries[0]["passage"], "Commercial surrogacy is illegal in the UK but permitted abroad.")
        self.assertIn("DRAFT", text)

    def test_draft_with_nothing_confirmed_says_what_to_do(self):
        text = sc.draft_sequence("# Quotes\n", "X", "2026-01-01")
        self.assertEqual(sc.parse_sequence(text), [])
        self.assertIn("checklist.md", text)


class GeometryTests(unittest.TestCase):
    def test_crop_anchors_and_pixel_centres(self):
        self.assertEqual(sc.crop_x("centre"), 656)
        self.assertEqual(sc.crop_x("left"), 464)
        self.assertEqual(sc.crop_x("right"), 848)
        self.assertEqual(sc.crop_x("810"), 506)
        self.assertEqual(sc.crop_x("0"), 0)             # clamped to the frame
        self.assertEqual(sc.crop_x("1900"), 1920 - 608)
        self.assertEqual(sc.crop_x("nonsense"), 656)

    def test_cut_bounds_hard_in_between_touching_words_and_a_tail(self):
        words = [("but", 13.66, 13.74), ("pregnant", 13.74, 13.98), ("women", 13.98, 14.2), ("ordered.", 19.0, 19.5)]
        start, end = sc.cut_bounds(words, 1, 3)
        self.assertAlmostEqual(start, 13.74, places=2)          # midpoint of a gap of zero is the boundary itself
        self.assertAlmostEqual(end, 19.5 + sc.TAIL, places=2)
        start2, _ = sc.cut_bounds([("parliament.", 10.6, 10.62)] + words[1:], 1, 3)
        self.assertAlmostEqual(start2, 13.69, places=2)         # a real gap before: a hair early


class TrackTests(unittest.TestCase):
    def test_every_caption_is_centred_on_the_same_point_and_plates_carry_brand_colours(self):
        items = [{"name": "Shivani Raja MP", "party": "Conservative · Leicester East", "duration": 6.8,
                  "cards": [(["A child cannot consent to", "a surrogacy arrangement."], 0.4, 3.2), (["They cannot understand the", "promises adults have made."], 3.7, 6.4)]},
                 {"name": "Jim Shannon MP", "party": "DUP · Strangford", "duration": 7.5, "cards": [(["Paying a woman for carrying", "a baby is quite another."], 3.9, 7.0)]}]
        ass = sc.ass_track(items)
        captions = [l for l in ass.splitlines() if ",Caption," in l]
        self.assertEqual(len(captions), 3)
        for l in captions:
            self.assertIn("\\pos(540,1600)", l)
        self.assertEqual(captions[2].split(",")[1], "0:00:10.60")          # second item's card starts at 6.8 + 3.9 - 0.1
        self.assertIn("\\1c&HF48542&", ass)                              # principal blue plate
        self.assertIn("\\1c&H242120&", ass)                              # ink strip
        self.assertEqual(ass.count(",Name,"), 2)
        self.assertIn("Helvetica Neue", ass)

    def test_colours(self):
        self.assertEqual(sc.ass_colour("#4285F4"), "&H00F48542&")
        self.assertEqual(sc.override_colour("#202124"), "&H242120&")


if __name__ == "__main__":
    unittest.main()


class ReelLengthTests(unittest.TestCase):
    """Christopher, 2026-09-09: reels above 30s, below 60s, longer for a very good
    speech. The edition's text quotes stay sized in characters; a reel is watched."""

    def setUp(self):
        import re
        self.patterns = [re.compile(r"surrogac|surrogate|motherhood", re.I)]

    def _speech(self, n, on_topic_every=1):
        out = []
        for i in range(n):
            topic = "surrogacy" if i % on_topic_every == 0 else "housing"
            out.append("Sentence number %d concerns %s and the protections that the law provides for women." % (i, topic))
        return " ".join(out)

    def test_a_passage_clears_thirty_seconds(self):
        got = sc.reel_passage(self._speech(20), self.patterns)
        self.assertIsNotNone(got)
        self.assertGreaterEqual(sc.spoken_seconds(got), 30.0)

    def test_a_thin_speech_stops_at_sixty_seconds(self):
        # one on-topic sentence in five: not a "very good speech", so the cap holds
        got = sc.reel_passage(self._speech(40, on_topic_every=5), self.patterns)
        self.assertIsNotNone(got)
        self.assertLessEqual(sc.spoken_seconds(got), sc.REEL_CAP_S + 0.01)

    def test_a_speech_thick_with_our_issue_may_run_past_sixty(self):
        got = sc.reel_passage(self._speech(40), self.patterns, target_s=80.0)
        self.assertGreater(sc.spoken_seconds(got), sc.REEL_CAP_S)
        self.assertLessEqual(sc.spoken_seconds(got), sc.REEL_HARD_CAP_S)

    def test_too_short_to_be_a_reel_returns_none(self):
        self.assertIsNone(sc.reel_passage("Surrogacy matters.", self.patterns))

    def test_off_topic_speech_returns_none(self):
        self.assertIsNone(sc.reel_passage(self._speech(20).replace("surrogacy", "housing"), self.patterns))

    def test_it_refuses_a_passage_that_would_misrepresent_the_member(self):
        # quotes.usable rejects a concession that never turns; the reel must too
        text = "I accept that surrogacy brings joy to many families who have waited years for a child. " * 6
        got = sc.reel_passage(text, self.patterns)
        self.assertIsNone(got)

    def test_real_speech_yields_a_reel_length_passage(self):
        yemm = ("It is a pleasure to serve under your chairmanship this afternoon, Mr Pritchard. "
                "The question before us is not whether intended parents are real parents, nor whether they should "
                "ultimately receive legal recognition; the question is whether the woman who has carried and given "
                "birth to a child should lose her legal status as that child's mother from the moment of birth. "
                "I do not believe that she should. In our society, some things should never be reduced to questions "
                "of contract, individual choice or intention, and motherhood is certainly one of them. "
                "Pregnancy cannot simply be a service provided by one person for another, a woman's body cannot "
                "merely be the means by which someone else's parental intentions are fulfilled and the relationship "
                "created through nine months of pregnancy and childbirth cannot be written off because an agreement "
                "was reached beforehand.")
        got = sc.reel_passage(yemm, self.patterns)
        self.assertIsNotNone(got)
        self.assertGreaterEqual(sc.spoken_seconds(got), 30.0)
        self.assertLessEqual(sc.spoken_seconds(got), sc.REEL_HARD_CAP_S)
        self.assertNotIn("pleasure to serve", got)       # the courtesy opener is stripped


class SpeechesParsingTests(unittest.TestCase):
    """A minister's heading carries no (Party, Seat). Requiring it let her section leak
    into the speaker above and her 'Neutral' reading overwrite his confirmed 'yes'
    (Shastri-Hurst, 2026-09-09) -- a confirmed onside speaker dropped in silence."""

    MD = """# Speeches

## Dr Neil Shastri-Hurst (Con, Solihull West and Shirley)

**Pass read:** With us — Stresses protecting child and surrogate mother.  ·  **confirmed: yes**

*17:36:00, 979 words · [Hansard](https://e/1)*

Nobody doubts the love that such parents have for their children.

## Dame Diana Johnson

**Pass read:** Neutral or unclear — Ministerial summary, no clear stance.  ·  **confirmed: no**

*17:46:00, 974 words · [Hansard](https://e/2)*

It is always a pleasure to serve under your chairmanship.
"""

    def test_a_minister_without_party_and_seat_is_her_own_speaker(self):
        sp = sc.parse_speeches(self.MD)
        self.assertEqual([s["name"] for s in sp], ["Dr Neil Shastri-Hurst", "Dame Diana Johnson"])
        self.assertEqual(sp[0]["confirmed"], "yes")
        self.assertEqual(sp[0]["party"], "Con")
        self.assertEqual(sp[1]["confirmed"], "no")
        self.assertEqual(sp[1]["party"], "")
        self.assertIn("Nobody doubts", sp[0]["contributions"][0]["text"])
        self.assertNotIn("pleasure to serve", sp[0]["contributions"][0]["text"])

    def test_the_first_reading_in_a_section_wins(self):
        sp = sc.parse_speeches(self.MD)
        self.assertTrue(sp[0]["pass_read"].startswith("With us"))
