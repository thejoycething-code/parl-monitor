"""Full speeches as 16:9 clips (Christopher, 2026-09-11): the plan, the trim anchors,
the landscape track. Nothing here touches the network or ffmpeg."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import speechcut as spc, socialcut as sc  # noqa: E402

STATE = {"event_start": "2026-09-07T15:30:00+00:00",
         "speakers": [{"name": "Shivani Raja", "spans": [["2026-09-07T16:41:00+01:00", "2026-09-07T16:48:00+01:00"],
                                                         ["2026-09-07T17:14:01+01:00", "2026-09-07T17:14:44+01:00"]]},
                      {"name": "Dave Robertson", "spans": [["2026-09-07T16:30:00+01:00", "2026-09-07T16:35:00+01:00"]]}]}
LONG = " ".join(["Surrogacy asks a child to live with promises adults made before it was born."] * 20)
SPEECHES = [
    {"name": "Shivani Raja", "party": "Con", "seat": "Leicester East", "confirmed": "", "pass_read": "With us",
     "contributions": [{"at": "16:41:12", "words": 260, "url": "u", "text": LONG},
                       {"at": "17:14:01", "words": 30, "url": "u", "text": "A short intervention that is not a speech."}]},
    {"name": "Dave Robertson", "party": "Lab", "seat": "Lichfield", "confirmed": "no", "pass_read": "Against us",
     "contributions": [{"at": "16:30:00", "words": 735, "url": "u", "text": LONG}]},
]


class PlanTests(unittest.TestCase):
    def test_onside_speeches_are_matched_to_the_nearest_span_and_interventions_skipped(self):
        todo = spc.plan(STATE, SPEECHES, lambda s: s["pass_read"].startswith("With us") and s["confirmed"] != "no")
        self.assertEqual([(s["name"], c["at"]) for s, c, _sp in todo], [("Shivani Raja", "16:41:12")])
        span = todo[0][2]
        self.assertEqual(span, (11 * 60.0, 18 * 60.0))       # 15:30Z is 16:30 London, so 16:41 London is 660s in

    def test_a_speech_with_no_span_near_its_time_is_reported_not_guessed(self):
        state = dict(STATE, speakers=[{"name": "Shivani Raja", "spans": [["2026-09-07T18:00:00+01:00", "2026-09-07T18:05:00+01:00"]]}])
        todo = spc.plan(state, SPEECHES, lambda s: s["name"] == "Shivani Raja")
        self.assertEqual(len(todo), 1)
        self.assertIsNone(todo[0][2])

    def test_only_filters_by_name_with_or_without_mp(self):
        todo = spc.plan(STATE, SPEECHES, lambda s: True, only=["dave robertson"])
        self.assertEqual([s["name"] for s, _c, _sp in todo], ["Dave Robertson"])
        todo = spc.plan(STATE, SPEECHES, lambda s: True, only=["Shivani Raja MP"])
        self.assertEqual([s["name"] for s, _c, _sp in todo], ["Shivani Raja"])


class NumberingAndReportTests(unittest.TestCase):
    """A re-cut of one speaker (12 Sept 2026, Bradley) keeps the clip number from the
    full run and rewrites only that speaker's lines in speeches-cut.md."""

    def test_clip_numbers_come_from_the_wider_plan(self):
        full = spc.plan(STATE, SPEECHES, lambda s: True)
        numbers = spc.clip_numbers(full)
        self.assertEqual(numbers[("Shivani Raja", "16:41:12")], 1)      # speeches.md order, not clock order
        self.assertEqual(numbers[("Dave Robertson", "16:30:00")], 2)

    def test_partial_report_keeps_the_other_speakers_lines(self):
        import tempfile
        d = tempfile.mkdtemp()
        raja, dave = SPEECHES[0], SPEECHES[1]
        spc.write_report(d, [(dave, dave["contributions"][0], (0, 10, 10.0, 0.9, 0.9), "clips/final/speech-01-dave.mp4"),
                             (raja, raja["contributions"][0], (0, 10, 10.0, 0.9, 0.9), "clips/final/speech-02-raja.mp4")])
        spc.write_report(d, [(raja, raja["contributions"][0], (0, 900, 900.0, 0.8, 0.8), "clips/final/speech-02-raja.mp4")], keep_others=True)
        lines = [ln for ln in open(os.path.join(d, "speeches-cut.md")).read().splitlines() if ln.startswith("* ")]
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("* Dave Robertson"))
        self.assertIn("900 s", lines[1])
        self.assertNotIn("10 s", lines[1])


class ForgetTests(unittest.TestCase):
    def test_a_changed_span_drops_the_part_transcript_with_the_window(self):
        import tempfile
        hd = tempfile.mkdtemp(); tag = "02-dame-karen-bradley-100400"
        for n in ("-window.mp4", "-window.mp4.json", "-window.wav", "-window.words.json", "-part.wav", "-part.words.json", ".ass", ".mp4"):
            open(os.path.join(hd, tag + n), "w").write("x")
        spc.forget(hd, tag)                       # a wider tail margin: the window only
        self.assertCountEqual(os.listdir(hd), [tag + ".ass", tag + ".mp4", tag + "-part.wav", tag + "-part.words.json"])
        spc.forget(hd, tag, part_too=True)        # a different span: the part's transcript too
        self.assertEqual(sorted(os.listdir(hd)), [tag + ".mp4"])


class MergeTests(unittest.TestCase):
    """Bradley's speech, five contributions with interventions between: one clip."""

    def test_consecutive_contributions_within_the_gap_merge_into_one_speech(self):
        placed = [({"at": "10:04:00", "words": 477, "text": "A"}, (2040.0, 2200.0)),
                  ({"at": "10:07:14", "words": 28, "text": "b"}, (2234.0, 2250.0)),
                  ({"at": "10:10:35", "words": 390, "text": "C"}, (2435.0, 2560.0)),
                  ({"at": "12:00:00", "words": 300, "text": "D"}, (9000.0, 9200.0))]
        merged = spc.merge_speech(placed)
        self.assertEqual(len(merged), 2)
        c, span = merged[0]
        self.assertEqual((c["words"], c["merged"], c["text"]), (895, 3, "A b C"))
        self.assertEqual(span, (2040.0, 2560.0))
        self.assertEqual(merged[1][0]["text"], "D")

    def test_plan_merges_and_then_applies_the_word_floor(self):
        state = {"event_start": "2026-09-07T15:30:00+00:00",
                 "speakers": [{"name": "Long Talker", "spans": [["2026-09-07T16:40:00+01:00", "2026-09-07T16:43:00+01:00"],
                                                                ["2026-09-07T16:44:00+01:00", "2026-09-07T16:47:00+01:00"]]}]}
        speeches = [{"name": "Long Talker", "party": "Con", "seat": "S", "confirmed": "yes", "pass_read": "With us",
                     "contributions": [{"at": "16:40:00", "words": 100, "url": "u", "text": "one " * 100},
                                       {"at": "16:44:00", "words": 100, "url": "u", "text": "two " * 100}]}]
        todo = spc.plan(state, speeches, lambda s: True)
        self.assertEqual(len(todo), 1)                     # 100 + 100 words, merged, clears the 120 floor together
        self.assertEqual(todo[0][1]["merged"], 2)
        self.assertEqual(todo[0][2], (600.0, 1020.0))


class TrimTests(unittest.TestCase):
    def words(self, text, t0=30.0, per=0.35):
        out, t = [], t0
        for w in text.split():
            out.append((w, t, t + per)); t += per + 0.05
        return out

    def test_trim_anchors_on_first_and_last_hansard_words(self):
        text = " ".join("word%d" % i for i in range(120))
        words = [("noise", 0.0, 0.3), ("before", 0.4, 0.7)] + self.words(text, 30.0) + [("after", 999.0, 999.3)]
        start, end, r1, r2 = spc.trim_bounds(words, text, file_start=0.0, span=(0.0, 1000.0))
        self.assertAlmostEqual(start, 30.0 - 0.05, places=2)
        last_end = words[-2][2]
        self.assertAlmostEqual(end, last_end + spc.TAIL, places=2)
        self.assertGreater(r1, 0.9); self.assertGreater(r2, 0.9)

    def test_unplaceable_ends_fall_back_to_the_hansard_span(self):
        words = self.words("completely different words here " * 30)
        text = " ".join("target%d" % i for i in range(100))
        notes = []
        start, end, r1, r2 = spc.trim_bounds(words, text, file_start=100.0, span=(125.0, 400.0), log=notes.append)
        self.assertEqual((start, end), (25.0, 300.0))
        self.assertIsNone(r1); self.assertIsNone(r2)
        self.assertTrue(notes and "Hansard time" in notes[0])


class TrackTests(unittest.TestCase):
    def test_landscape_track_is_1920x1080_with_the_caption_low_centre(self):
        item = {"name": "Shivani Raja MP", "party": "Conservative · Leicester East", "duration": 40.0,
                "cards": [(["Surrogacy asks a child to live", "with promises adults made"], 1.0, 4.0)]}
        ass = spc.ass_landscape(item)
        self.assertIn("PlayResX: 1920", ass); self.assertIn("PlayResY: 1080", ass)
        self.assertIn("pos(960,985)", ass)
        self.assertIn("Shivani Raja MP", ass)
        # the vertical track is unchanged by the refactor
        v = sc.ass_track([item])
        self.assertIn("PlayResX: 1080", v); self.assertIn("pos(540,1600)", v); self.assertIn("pos(60,1290)", v)

    def test_srt_has_one_cue_per_card(self):
        item = {"name": "X", "party": "", "duration": 10.0, "cards": [(["a", "b"], 0.0, 2.0), (["c"], 2.5, 4.0)]}
        s = spc.srt(item)
        self.assertIn("1\n00:00:00,000 --> 00:00:02,000\na\nb", s)
        self.assertIn("2\n00:00:02,500 --> 00:00:04,000\nc", s)

    def test_caption_cards_fit_the_wider_frame(self):
        cards = sc.chunk_caption(LONG, max_chars=spc.CAPTION_MAX_CHARS)
        self.assertTrue(all(len(l) <= spc.CAPTION_MAX_CHARS for c in cards for l in c), cards[:3])


if __name__ == "__main__":
    unittest.main()


class TailAfterHeadTests(unittest.TestCase):
    def test_the_tail_is_searched_only_after_the_head(self):
        from src import speechcut as spc
        closing = "and that is why I will not give way and I will vote against this Bill today because it is not safe for the people I represent"
        opening = "I have struggled with this vote perhaps more than any other in Parliament since I was elected to this House to speak for my constituents"
        middle = "the committee heard evidence from many witnesses about palliative care and about coercion and about capacity"
        # the same closing is heard BEFORE the speech (a previous speaker) and again at its true end
        seq = (closing + " " + opening + " " + middle + " " + closing).split()
        words = [(w, 1.0 * i, 1.0 * i + 0.8) for i, w in enumerate(seq)]
        text = " ".join([opening, middle, closing])
        start, end, r1, r2 = spc.trim_bounds(words, text, 0.0, (0.0, len(seq)))
        self.assertIsNotNone(r1); self.assertIsNotNone(r2)
        self.assertGreater(end, start)
        self.assertGreater(end, words[len(seq) - 3][1])           # the SECOND closing, at the true end
