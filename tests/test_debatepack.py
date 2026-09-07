"""The debate pack (Christopher, 2026-09-07)."""

import datetime
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import debatepack as dp  # noqa: E402

PAYLOAD = {"Items": [
    {"ItemType": "Timestamp", "Value": "16:30:00"},
    {"ItemType": "Contribution", "AttributedTo": "Sir Roger Gale (in the Chair)", "Value": "Order.", "MemberId": 1, "ExternalId": "c0"},
    {"ItemType": "Contribution", "AttributedTo": "Dave Robertson (Lichfield) (Lab)", "MemberId": 5001, "ExternalId": "c1",
     "Timecode": "2026-09-07T16:31:10", "Value": "I beg to move that this House has considered e-petition 763161. Surrogacy law is outdated. Intended parents should be recognised from birth."},
    {"ItemType": "Contribution", "AttributedTo": "Sir Roger Gale (in the Chair)", "Value": "I call Danny Kruger.", "MemberId": 1, "ExternalId": "c2"},
    {"ItemType": "Contribution", "AttributedTo": "Danny Kruger (East Wiltshire) (Con)", "MemberId": 4858, "ExternalId": "c3",
     "Timecode": "2026-09-07T16:40:02", "Value": "Commercial surrogacy treats children as commodities. The law must protect the child first."},
    {"ItemType": "Timestamp", "Value": "16:52:00"},
    {"ItemType": "Contribution", "AttributedTo": "The Minister of State, Ministry of Justice (Sarah Sackman)", "MemberId": 9, "ExternalId": "c4",
     "Value": "The Government has no plans to legislate on surrogacy in this Session."},
    {"ItemType": "Contribution", "AttributedTo": "Danny Kruger (East Wiltshire) (Con)", "MemberId": 4858, "ExternalId": "c5",
     "Timecode": "2026-09-07T17:05:00", "Value": "Will the Minister rule out commercial surrogacy?"},
]}


class ContributionTests(unittest.TestCase):
    def test_clocks_interpolate_from_timestamps_and_timecodes(self):
        rows = dp.contributions(PAYLOAD, "2026-09-07")
        by = {r["ext_id"]: r for r in rows}
        self.assertEqual(by["c0"]["start"].strftime("%H:%M:%S"), "16:30:00")      # from the Timestamp item
        self.assertEqual(by["c1"]["start"].strftime("%H:%M:%S"), "16:31:10")      # its own Timecode
        self.assertEqual(by["c2"]["start"].strftime("%H:%M:%S"), "16:31:10")      # inherits the last clock
        self.assertEqual(by["c4"]["start"].strftime("%H:%M:%S"), "16:52:00")
        # c1 is 22 words: ~8s + 6s room -> ends 16:31:24, well before the next clock (16:40:02)
        self.assertEqual(by["c1"]["end"].strftime("%H:%M:%S"), "16:31:24")
        # a long speech is capped by the next clock, never credited with the gap
        long_row = dict(PAYLOAD["Items"][2], Value=" ".join(["word"] * 5000), ExternalId="cL")
        rows2 = dp.contributions({"Items": [PAYLOAD["Items"][0], long_row, PAYLOAD["Items"][4]]}, "2026-09-07")
        self.assertEqual(rows2[0]["end"].strftime("%H:%M:%S"), "16:40:02")
        self.assertEqual(by["c1"]["start"].tzinfo.key, "Europe/London")

    def test_attributed_parses_name_seat_party_and_flags_the_chair(self):
        rows = dp.contributions(PAYLOAD, "2026-09-07")
        k = next(r for r in rows if r["ext_id"] == "c3")
        self.assertEqual((k["name"], k["seat"], k["party"], k["chair"]), ("Danny Kruger", "East Wiltshire", "Con", False))
        self.assertTrue(next(r for r in rows if r["ext_id"] == "c0")["chair"])

    def test_speakers_group_by_member_and_exclude_the_chair(self):
        sp = dp.speakers(dp.contributions(PAYLOAD, "2026-09-07"))
        names = {s["name"]: s for s in sp}
        self.assertNotIn("Sir Roger Gale", names)
        self.assertEqual(names["Danny Kruger"]["count"], 2)
        self.assertEqual(len(names["Danny Kruger"]["spans"]), 2)                  # both contributions carry a clock
        self.assertEqual(names["Danny Kruger"]["seconds"], (5 + 6) + (2 + 6))       # 13 and 7 words at 2.5/s, +6s room each
        self.assertEqual(dp.minister(dp.contributions(PAYLOAD, "2026-09-07"))["ext_id"], "c4")


class ChecklistTests(unittest.TestCase):
    def test_parse_yes_no_and_blank(self):
        path = os.path.join(tempfile.mkdtemp(), "checklist.md")
        open(path, "w").write("### speaker: 4858\n- x\nONSIDE: yes\n\n### speaker: 5001\nONSIDE: No\n\n### speaker: 9\nONSIDE: \n")
        self.assertEqual(dp.parse_checklist(path), {"4858": "yes", "5001": "no"})


class FootageTests(unittest.TestCase):
    def test_window_url_is_utc_with_padding_applied_by_download(self):
        start = datetime.datetime(2026, 9, 7, 16, 31, 10, tzinfo=dp.LONDON)      # BST
        end = datetime.datetime(2026, 9, 7, 16, 40, 2, tzinfo=dp.LONDON)
        url = dp.window_url("https://x/index.m3u8", start, end)
        self.assertEqual(url, "https://x/index.m3u8?start=2026-09-07T15:31:10Z&end=2026-09-07T15:40:02Z")

    def test_event_discovery_and_offset_link(self):
        html = ('<a href="/Event/Index/0b25fa79-40b6-40c2-8daf-39c8c660a065">x</a> Monday 7 September 2026 2.33 pm BSL - House of Commons'
                '<a href="/Event/Index/298d5452-e524-4de5-b556-9ef1a433f8f0">y</a> Monday 7 September 2026 4.30 pm Westminster Hall')
        ev = dp.todays_events(html)
        self.assertEqual(dp.pick_event(ev, "Westminster Hall"), "298d5452-e524-4de5-b556-9ef1a433f8f0")
        self.assertIsNone(dp.pick_event(ev, "House of Commons"))                  # BSL feed excluded
        es = datetime.datetime(2026, 9, 7, 15, 15, tzinfo=datetime.timezone.utc)
        start = datetime.datetime(2026, 9, 7, 16, 31, 10, tzinfo=dp.LONDON)
        self.assertTrue(dp.offset_link("g", start, es).endswith("?in=00:16:10"))
        self.assertEqual(dp.event_guid("https://parliamentlive.tv/Event/Index/298d5452-e524-4de5-b556-9ef1a433f8f0?in=1"),
                         "298d5452-e524-4de5-b556-9ef1a433f8f0")


class PackTests(unittest.TestCase):
    def test_pack_files_and_the_check_gates_the_quotes(self):
        rows = dp.contributions(PAYLOAD, "2026-09-07")
        sp = dp.speakers(rows)
        folder = tempfile.mkdtemp()
        directions = {"4858": {"stance": 2, "why": "Opposes commercial surrogacy."}, "5001": {"stance": -1, "why": "Wants recognition from birth."}}
        import re
        patterns = [re.compile(r"surrogac", re.I)]
        meta = {"title": "Surrogacy", "house": "Commons", "date": "2026-09-07", "ext_id": "E1"}
        dp.write_pack(folder, meta, sp, directions, {}, dp.minister(rows), patterns, guid="g",
                      event_start=datetime.datetime(2026, 9, 7, 15, 15, tzinfo=datetime.timezone.utc))
        for name in ("roundup.md", "checklist.md", "quotes.md", "shotlist.csv", "README.md"):
            self.assertTrue(os.path.exists(os.path.join(folder, name)), name)
        roundup = open(os.path.join(folder, "roundup.md")).read()
        self.assertIn("**The minister's line**", roundup)
        self.assertIn("| [Danny Kruger (Con, East Wiltshire)]", roundup)
        self.assertIn("With us, strongly", roundup)
        quotes = open(os.path.join(folder, "quotes.md")).read()
        self.assertIn("UNCONFIRMED", quotes)
        self.assertIn("Danny Kruger", quotes)
        self.assertNotIn("## Dave Robertson", quotes)                             # the pass read him against
        checklist = open(os.path.join(folder, "checklist.md")).read()
        self.assertIn("### speaker: 4858", checklist)
        self.assertIn("ONSIDE: ", checklist)
        # a human confirms Robertson and rejects Kruger: the quotes follow the human, not the pass
        open(os.path.join(folder, "checklist.md"), "w").write("### speaker: 5001\nONSIDE: yes\n\n### speaker: 4858\nONSIDE: no\n")
        conf = dp.parse_checklist(os.path.join(folder, "checklist.md"))
        dp.write_pack(folder, meta, sp, directions, conf, dp.minister(rows), patterns, guid="g",
                      event_start=datetime.datetime(2026, 9, 7, 15, 15, tzinfo=datetime.timezone.utc))
        quotes = open(os.path.join(folder, "quotes.md")).read()
        self.assertIn("## Dave Robertson", quotes)
        self.assertNotIn("## Danny Kruger", quotes)
        shot = open(os.path.join(folder, "shotlist.csv")).read()
        self.assertIn('Danny Kruger,Con,East Wiltshire,"With us, strongly",no,16:40:02,2026-09-07T15:40:02Z,2026-09-07T15:40:13Z,11', shot)
        self.assertIn("Sarah Sackman,,,Not read", shot)                              # the minister by name, not by office
        self.assertIn("?in=00:25:02", shot)
        self.assertIn("checklist.md", open(os.path.join(folder, "README.md")).read())
        self.assertIn("Parliamentary Recording Unit", open(os.path.join(folder, "README.md")).read())

    def test_footage_is_ignored_by_git(self):
        self.assertIn("data/packs/*/clips/", open(os.path.join(ROOT, ".gitignore")).read())


if __name__ == "__main__":
    unittest.main()
