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
        # c2 (the Chair, no clock) starts when c1 is estimated to end: 22 words -> 8s + 6s room after 16:31:10
        self.assertEqual(by["c2"]["start"].strftime("%H:%M:%S"), "16:31:24")
        self.assertEqual(by["c4"]["start"].strftime("%H:%M:%S"), "16:52:00")
        # c1 is 22 words: ~8s + 6s room -> ends 16:31:24, well before the next clock (16:40:02)
        self.assertEqual(by["c1"]["end"].strftime("%H:%M:%S"), "16:31:24")
        # a long speech is capped by the next clock, never credited with the gap
        long_row = dict(PAYLOAD["Items"][2], Value=" ".join(["word"] * 5000), ExternalId="cL")
        rows2 = dp.contributions({"Items": [PAYLOAD["Items"][0], long_row, PAYLOAD["Items"][4]]}, "2026-09-07")
        self.assertEqual(rows2[0]["end"].strftime("%H:%M:%S"), "16:40:02")
        self.assertEqual(by["c1"]["start"].tzinfo.key, "Europe/London")

    def test_a_second_contribution_without_a_clock_follows_the_first_not_overlaps_it(self):
        """Jonathan Hinder spoke twice from 17:22 with one clock; his second
        contribution began after his first ended, not at the same instant."""
        payload = {"Items": [
            {"ItemType": "Contribution", "AttributedTo": "Jonathan Hinder (Pendle) (Lab)", "MemberId": 1, "ExternalId": "h1",
             "Timecode": "2026-09-07T17:22:00", "Value": " ".join(["word"] * 250)},
            {"ItemType": "Contribution", "AttributedTo": "Someone Else (Here) (Con)", "MemberId": 2, "ExternalId": "x1",
             "Value": " ".join(["word"] * 50)},
            {"ItemType": "Contribution", "AttributedTo": "Jonathan Hinder (Pendle) (Lab)", "MemberId": 1, "ExternalId": "h2",
             "Value": " ".join(["word"] * 300)}]}
        rows = {r["ext_id"]: r for r in dp.contributions(payload, "2026-09-07")}
        self.assertEqual(rows["h1"]["start"].strftime("%H:%M:%S"), "17:22:00")
        self.assertEqual(rows["x1"]["start"].strftime("%H:%M:%S"), "17:23:46")   # 250 words / 2.5 = 100s, +6 room
        self.assertEqual(rows["h2"]["start"].strftime("%H:%M:%S"), "17:24:12")   # 50 words = 20s, +6
        self.assertLess(rows["h1"]["end"], rows["h2"]["start"])

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


class ApplyReadsNewSpeakersTests(unittest.TestCase):
    def test_a_reading_is_cached_against_the_words_it_saw(self):
        """Jim Shannon: read on a 53-word intervention, kept when his 1,000-word speech landed."""
        src = open(os.path.join(ROOT, "tools", "debate_pack.py"), encoding="utf-8").read()
        self.assertIn('s["words"] > d["words"] * 1.5 + 40', src)
        self.assertIn('got[key_]["words"] = s["words"]', src)

    def test_apply_does_not_force_no_read(self):
        src = open(os.path.join(ROOT, "tools", "debate_pack.py"), encoding="utf-8").read()
        block = src[src.index("def apply(args):"):src.index("def download(args):")]
        self.assertIn("no_read=args.no_read", block)
        self.assertNotIn("no_read=True", block)


class FindDebateRetryTests(unittest.TestCase):
    def test_an_empty_tree_is_retried_before_it_is_believed(self):
        """Hansard answered with and without the new section within a minute."""
        calls = {"n": 0}

        class Client:
            def get_json(self, url, feed, slug, archive=True):
                if "sectionsforday" in url:
                    return ["WestHall"]
                calls["n"] += 1
                if calls["n"] < 2:
                    return [{"Title": "Westminster Hall", "SectionTreeItems": []}]
                return [{"Title": "Westminster Hall", "SectionTreeItems": [
                    {"Title": "Surrogacy Law and Legal Parenthood", "ExternalId": "1DE0", "HRSTag": "hs_2WestHallDebate"}]}]
        slept = []
        out = dp.find_debate(Client(), "2026-09-07", "surrogacy", "Commons", attempts=3, pause=1, sleep=slept.append)
        self.assertEqual(out, [("Surrogacy Law and Legal Parenthood", "WestHall", "1DE0")])
        self.assertEqual(slept, [1])


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


class ClipRouteTests(unittest.TestCase):
    """The live stream honours a time window; the archive recording ignores it."""

    def test_format_selector_is_a_height_cap_whatever_was_written(self):
        self.assertEqual(dp.format_selector("1300"), "bv*[height<=576]+ba/b[height<=576]/b")
        self.assertEqual(dp.format_selector("576p"), "bv*[height<=576]+ba/b[height<=576]/b")
        self.assertEqual(dp.format_selector("1080"), "bv*[height<=1080]+ba/b[height<=1080]/b")

    def test_window_probe_tells_live_from_archive(self):
        start = datetime.datetime(2026, 9, 7, 15, 41, tzinfo=datetime.timezone.utc); end = start + datetime.timedelta(seconds=30)
        live = {"m": "v.m3u8", "v": "#EXTINF:6.0,\nseg1\n#EXTINF:6.0,\nseg2\n#EXTINF:6.0,\nseg3\n#EXTINF:6.0,\nseg4\n#EXTINF:6.0,\nseg5\n"}
        archive = {"m": "v.m3u8", "v": "".join("#EXTINF:6.0,\nseg\n" for _ in range(1600))}
        fetch_live = lambda u: live["v"] if u.endswith("v.m3u8") else live["m"]
        fetch_arch = lambda u: archive["v"] if u.endswith("v.m3u8") else archive["m"]
        self.assertTrue(dp.window_is_honoured("https://x/index.m3u8", start, end, fetch=fetch_live))
        self.assertFalse(dp.window_is_honoured("https://x/index.m3u8", start, end, fetch=fetch_arch))

    def test_archive_route_cuts_by_offset_from_the_recording_start(self):
        calls = []
        real = dp.subprocess.run
        dp.subprocess.run = lambda cmd, **kw: calls.append(cmd) or type("R", (), {"returncode": 0})()
        try:
            es = datetime.datetime(2026, 9, 7, 15, 30, tzinfo=datetime.timezone.utc)
            start = datetime.datetime(2026, 9, 7, 16, 41, 0, tzinfo=dp.LONDON); end = start + datetime.timedelta(seconds=100)
            dp.download_clip("https://x/vod.m3u8", start, end, "out.mp4", "yt-dlp", None, "576", guid="G", event_start=es, windowed=False)
        finally:
            dp.subprocess.run = real
        cmd = calls[0]
        self.assertIn("--download-sections", cmd)
        i = cmd.index("--download-sections")
        self.assertEqual(cmd[i + 1], "*00:10:55-00:12:44")        # 16:41:00 BST = 15:41Z = 660s after 15:30Z; -5s pad, +4s pad
        self.assertEqual(cmd[-1], "https://parliamentlive.tv/Event/Index/G")
        self.assertIn("bv*[height<=576]+ba/b[height<=576]/b", cmd)


class ArchiveSearchTests(unittest.TestCase):
    """Christopher, 2026-09-07: "Build the parliamentlive.tv date lookup for archived sittings." """

    HTML = ('<div class="col-md-12 search-item"><a href="https://parliamentlive.tv/Event/Index/c2efa0c9-da5f-4018-b0c0-1a974c5b8286">'
            '<img alt="House of Commons"></a><h5>House of Commons</h5> Friday 20 June 2025 9.34am</div>'
            '<div class="col-md-12 search-item"><a href="/Event/Index/11111111-2222-3333-4444-555555555555"><img alt="Westminster Hall"></a>'
            '<h5>Westminster Hall</h5> 9.30am</div>')

    def test_results_parse_to_guid_and_venue(self):
        ev = dp.search_events_html(self.HTML)
        self.assertEqual([g for g, _ in ev], ["c2efa0c9-da5f-4018-b0c0-1a974c5b8286", "11111111-2222-3333-4444-555555555555"])
        self.assertEqual(dp.pick_event(ev, "House of Commons"), "c2efa0c9-da5f-4018-b0c0-1a974c5b8286")
        self.assertEqual(dp.pick_event(ev, "Westminster Hall"), "11111111-2222-3333-4444-555555555555")

    def test_search_url_carries_the_date_twice_and_the_house(self):
        seen = []
        dp.search_events("2025-06-20", "Commons", fetch=lambda u: seen.append(u) or "")
        self.assertIn("Start=2025-06-20&End=2025-06-20", seen[0])
        self.assertIn("House=Commons", seen[0])


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
        speeches = open(os.path.join(folder, "speeches.md")).read()
        self.assertIn("## Danny Kruger (Con, East Wiltshire)", speeches)
        self.assertIn("Commercial surrogacy treats children as commodities.", speeches)   # the words, in full
        self.assertIn("**Pass read:** With us, strongly", speeches)
        for name in ("roundup.md", "checklist.md", "speeches.md", "quotes.md", "shotlist.csv", "README.md"):
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

    def test_new_speakers_are_appended_to_an_existing_checklist_without_losing_answers(self):
        rows = dp.contributions(PAYLOAD, "2026-09-07")
        sp = dp.speakers(rows)
        folder = tempfile.mkdtemp()
        meta = {"title": "Surrogacy", "house": "Commons", "date": "2026-09-07", "ext_id": "E1"}
        dp.write_pack(folder, meta, sp[:1], {}, {}, None, [])                # first tranche: one speaker
        path = os.path.join(folder, "checklist.md")
        text = open(path).read().replace("ONSIDE: \n", "ONSIDE: yes\n", 1)
        open(path, "w").write(text)                                          # a human answers
        dp.write_pack(folder, meta, sp, {}, dp.parse_checklist(path), None, [])   # second tranche: everyone
        text = open(path).read()
        import re
        self.assertEqual(len(re.findall(r"^### speaker: ", text, re.M)), len(sp))   # the header text mentions the marker too
        self.assertIn("ONSIDE: yes", text)                                   # the answer survived

    def test_footage_is_ignored_by_git(self):
        self.assertIn("data/packs/*/clips/", open(os.path.join(ROOT, ".gitignore")).read())


if __name__ == "__main__":
    unittest.main()
