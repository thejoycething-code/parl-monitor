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
