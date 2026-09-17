import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import alignment  # noqa: E402

SPEECHES = """# Speeches

## Lauren Edwards (Lab, Rochester and Strood)

**Pass read:** Against us — Moves the Bill.

*09:37:00, 2000 words · [Hansard](https://e/1)*

I beg to move, That the Bill be now read a Second time. It is a privilege to open this debate on a matter of conscience for every Member of this House and beyond.

## Alison McGovern

**Pass read:** Neutral or unclear — Minister.

*14:05:00, 900 words · [Hansard](https://e/2)*

I thank all Members who have spoken today with such care and respect for one another across these Benches and I turn now to the substance of the points raised.
"""


def pack(tmp, alignment=None):
    state = {"event_start": "2026-09-11T08:34:44+00:00", "manifest": "https://x/m.m3u8"}
    if alignment:
        state["alignment"] = alignment
    json.dump(state, open(os.path.join(tmp, "pack.json"), "w"))
    open(os.path.join(tmp, "speeches.md"), "w").write(SPEECHES)


def fake_probe(offset, closer_offset=None):
    def probe(manifest, a, b, out):
        # the words are heard `offset` seconds later than Hansard's clock says
        base = a + 30.0 + (offset if a < 5000 or closer_offset is None else closer_offset)
        text = "I beg to move That the Bill be now read a Second time It is a privilege to open this debate on a matter of conscience for every Member" \
            if a < 5000 else "I thank all Members who have spoken today with such care and respect for one another across these Benches and I turn now"
        return [(w, base + i * 0.4, base + i * 0.4 + 0.3) for i, w in enumerate(text.split())]
    return probe


COMMITTEE = """# Speeches

## The Chair

**Pass read:** Neutral or unclear — Procedural.

*14:01:53, 103 words · clock · [Hansard](https://e/0)*

We are now sitting in public and the proceedings are being broadcast. As no Members wish to make a declaration of interest in connection with the Bill, we will now hear from our witnesses, starting with Dr Madeleine Sumption.

## Matt Vickers (Con, Stockton West)

**Pass read:** With us — Tighter controls.

*14:02:26, 65 words · clock · [Hansard](https://e/1)*

Dr Sumption, looking at the evidence rather than at the Government's intentions, which provisions in the Bill are likely to reduce arrivals or increase removals, and which have the weakest evidence base behind them, and the same question to you Mr Mehmet if I may, and then a second question on returns agreements and their record.

## Ben Goldsborough (Lab, South Norfolk)

**Pass read:** With us — Confidence.

*16:56:29, 70 words · clock · [Hansard](https://e/2)*

One piece of evidence that we were given earlier was that, as much as modern slavery legislation is a good thing for the United Kingdom, we have not necessarily been pulling our weight as we go forward, and I am interested to hear from the panel what progress you think the Bill makes on that front and where it falls short.

## Tom Gordon (LD, Harrogate and Knaresborough)

**Pass read:** Neutral or unclear — Technical.

*17:00:23, 159 words · [Hansard](https://e/3)*

I have a quite technical question. I sit on the Joint Committee on Human Rights, and when we were dealing with the Northern Ireland Troubles Bill, one of the issues I asked the then Secretary of State about was compatibility with the convention and how the Government had satisfied itself on that point.
"""


def committee_probe(manifest, a, b, out):
    """Hears Vickers and Goldsborough 4s late; never the Chair's tidied words, never Gordon (interpolated 90s off)."""
    heard = {2: "Dr Sumption looking at the evidence rather than at the Government's intentions which provisions in the Bill are likely to reduce arrivals",
             3: "One piece of evidence that we were given earlier was that as much as modern slavery legislation is a good thing for the United Kingdom"}
    at = a + 30.0
    for secs, text in ((51.0, heard[2]), (10494.0, heard[3])):          # 14:02:26 and 16:56:29 against a 14:01:35 BST start
        if abs(at - secs) < 1.0:
            return [(w, secs + 4.0 + i * 0.4, secs + 4.3 + i * 0.4) for i, w in enumerate(text.split())]
    return [("chatter", at, at + 0.3)] * 40


class CommitteeAnchorTests(unittest.TestCase):
    """17 Sept 2026: the Chair's tidied opener and an interpolated closer both failed;
    Vickers, timed by Hansard, was heard within seconds."""

    def test_candidates_skip_the_chair_and_put_hansard_timed_first(self):
        from src import socialcut as sc
        state = {"event_start": "2026-09-15T13:01:35+00:00"}
        c = alignment.anchor_candidates(state, sc.parse_speeches(COMMITTEE))
        self.assertTrue(c["opener"][0][0].startswith("opener Matt Vickers"))           # not the Chair
        self.assertTrue(c["closer"][0][0].startswith("closer Ben Goldsborough"))       # clocked beats the later interpolated Gordon
        self.assertTrue(c["closer"][1][0].startswith("closer Tom Gordon"))
        self.assertEqual(alignment.anchors(state, sc.parse_speeches(COMMITTEE))[0][0][:19], "opener Matt Vickers")

    def test_the_check_passes_on_the_first_candidate_heard(self):
        tmp = tempfile.mkdtemp()
        json.dump({"event_start": "2026-09-15T13:01:35+00:00", "manifest": "https://x/m.m3u8"}, open(os.path.join(tmp, "pack.json"), "w"))
        open(os.path.join(tmp, "speeches.md"), "w").write(COMMITTEE)
        logged = []
        rec = alignment.check(tmp, ff=None, probe=committee_probe, log=logged.append)
        self.assertTrue(rec["ok"], rec["summary"])
        self.assertEqual([round(a["offset_s"]) for a in rec["anchors"]], [4, 4])
        self.assertIn("opener Matt Vickers", rec["summary"]); self.assertIn("closer Ben Goldsborough", rec["summary"])


class AlignmentTests(unittest.TestCase):
    def test_anchors_are_the_opener_and_the_closer_in_sitting_seconds(self):
        tmp = tempfile.mkdtemp(); pack(tmp)
        from src import socialcut as sc
        a = alignment.anchors(json.load(open(tmp + "/pack.json")), sc.parse_speeches(SPEECHES))
        self.assertEqual([round(x[1]) for x in a], [136, 16216])       # 09:37:00 and 14:05:00 London against a 09:34:44 BST start
        self.assertTrue(a[0][0].startswith("opener Lauren Edwards"))

    def test_a_small_offset_passes_and_is_recorded(self):
        tmp = tempfile.mkdtemp(); pack(tmp)
        rec = alignment.check(tmp, ff=None, probe=fake_probe(3.0), log=lambda *_a: None)
        self.assertTrue(rec["ok"])
        self.assertTrue(all(abs(x["offset_s"] - 3.0) < 0.5 for x in rec["anchors"]))
        self.assertEqual(json.load(open(tmp + "/pack.json"))["alignment"]["ok"], True)

    def test_a_large_offset_stops_the_run(self):
        tmp = tempfile.mkdtemp(); pack(tmp)
        with self.assertRaises(SystemExit) as caught:
            alignment.check(tmp, ff=None, probe=fake_probe(600.0), log=lambda *_a: None)
        self.assertIn("FAILED", str(caught.exception))
        self.assertFalse(json.load(open(tmp + "/pack.json"))["alignment"]["ok"])

    def test_hansards_own_clock_noise_passes_when_the_anchors_agree(self):
        """11 Sept 2026 as measured: opener +27.7 s, closer +10.5 s. Same stream clock,
        two rough Hansard times; the windows absorb it, so the cut goes ahead."""
        tmp = tempfile.mkdtemp(); pack(tmp)
        rec = alignment.check(tmp, ff=None, probe=fake_probe(27.7, closer_offset=10.5), log=lambda *_a: None)
        self.assertTrue(rec["ok"])
        self.assertAlmostEqual(rec["drift_s"], 17.2, places=0)

    def test_anchors_that_drift_apart_stop_the_run_even_when_each_is_near(self):
        tmp = tempfile.mkdtemp(); pack(tmp)
        with self.assertRaises(SystemExit) as caught:
            alignment.check(tmp, ff=None, probe=fake_probe(-20.0, closer_offset=20.0), log=lambda *_a: None)
        self.assertIn("drift", str(caught.exception))

    def test_a_fresh_passing_record_is_not_remeasured(self):
        import datetime
        tmp = tempfile.mkdtemp()
        pack(tmp, {"measured_at": datetime.datetime.now().isoformat(timespec="seconds"), "ok": True, "summary": "fine", "anchors": []})
        calls = []
        rec = alignment.check(tmp, ff=None, probe=lambda *a: calls.append(a) or [], log=lambda *_a: None)
        self.assertEqual(calls, []); self.assertEqual(rec["summary"], "fine")


if __name__ == "__main__":
    unittest.main()
