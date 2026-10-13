"""Gaps the legislatures corrected, and the NB Hansard of 28 May 2026. No network.

* New Brunswick, 28 May 2026 (61-2, sitting 43): read at 1,257,984 bytes on
  8-9 October 2026, cut off with no %%EOF; legnb.ca replaced the file at
  13:42 GMT on 9 October with the complete 1,258,291 bytes (Last-Modified),
  after the day had left the weekly's 120-day owed window. A day stored
  unreadable is now read again when the server's file has changed
  (prov_nb_hansard.source_changed, prov_speeches.collect_days `recheck`).
* Newfoundland and Labrador, 3 October 2022: the prorogation day's Hansard is
  short and has no closing </html>, and is complete (NL Hansard, 9 October
  2026; config/prov_record.yaml `complete_records`).
* Manitoba, 10 May 2024 (vol_54c): no sitting (Manitoba Hansard, 9 October
  2026; `not_sittings`).
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, prov_classify as pc, prov_names as pn, prov_speeches as sp, prov_store as ps  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from src.prov_fetch import Context, Unreadable  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "prov")
NB_URL = "https://www.legnb.ca/content/house_business/61/2/hansard/43%202026-05-28b.pdf"
NL_URL = "https://www.assembly.nl.ca/HouseBusiness/Hansard/ga50session1/22-10-03.htm"
MB_URL = "https://www.gov.mb.ca/legislature/hansard/43rd_1st/vol_54c/summary_c.html"


def fx(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


class _Client:
    """Serves pages; a ranged request answers with the headers given."""
    user_agent = "CitizenGO-ParlMonitor/1.0 (contact: test)"
    throttle = 1.1

    def __init__(self, pages, headers=None, range_headers=None):
        self.pages, self.headers, self.range_headers = pages, headers or {}, range_headers or {}
        self.last_headers = {}
        self.asked = []

    def get_text(self, url, feed, slug, archive=True, fallback_encoding=None):
        self.asked.append(url)
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        self.last_headers = dict(self.headers)
        page = self.pages[url]
        return page.decode() if isinstance(page, bytes) else page

    def get_bytes(self, url, feed, slug, archive=True, first_bytes=None):
        self.asked.append((url, first_bytes))
        if first_bytes:
            self.last_headers = dict(self.range_headers)
            return b"%"
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        self.last_headers = dict(self.headers)
        page = self.pages[url]
        return page if isinstance(page, bytes) else page.encode()


ROBOTS = {"https://www.legnb.ca/robots.txt": "User-agent: *\nDisallow:\ncrawl-delay: 10\n",
          "https://www.assembly.nl.ca/robots.txt": "User-agent: *\nDisallow: /search\n",
          "https://www.gov.mb.ca/robots.txt": "User-agent: *\nDisallow:\n"}


def ctx_for(prov, pages, **kw):
    return Context(db.init_db(db.connect(":memory:")), _Client(dict(ROBOTS, **pages), **kw), prov,
                   feed="prov-{0}-speeches".format(prov), log=lambda *a: None, robots_cache_dir=None)


NB_DAY = {"key": "nb-61-2-2026-05-28", "date": "2026-05-28", "legislature": 61, "session": 2,
          "url": NB_URL, "document": NB_URL}
CUT = b"%PDF-1.6\n" + b"x" * 400


class NbHansardTests(unittest.TestCase):
    def test_an_unreadable_day_records_what_the_server_sent(self):
        from src.ingest import prov_nb_hansard as h
        ctx = ctx_for("nb", {NB_URL: CUT}, headers={"Content-Length": str(len(CUT)),
                                                    "last-modified": "Wed, 03 Jun 2026 15:00:00 GMT"})
        with self.assertRaises(Unreadable) as got:
            h.read_day(ctx, dict(NB_DAY))
        self.assertIn("no %%EOF marker in 409 bytes (served 409 bytes, Last-Modified Wed, 03 Jun 2026 "
                      "15:00:00 GMT)", str(got.exception))

    def test_a_short_read_against_its_content_length_is_said(self):
        from src.ingest import prov_nb_hansard as h
        ctx = ctx_for("nb", {})
        ctx.client.last_headers = {"Content-Length": "1258291"}
        self.assertEqual(h.served(ctx, len(CUT)), " (served 409 bytes, Content-Length 1,258,291)")

    def test_source_changed_by_size_or_date(self):
        from src.ingest import prov_nb_hansard as h
        old = "truncated PDF: no %%EOF marker in 1257984 bytes"
        now = {"Content-Range": "bytes 0-0/1258291", "Last-Modified": "Fri, 09 Oct 2026 13:42:21 GMT"}
        ctx = ctx_for("nb", {}, range_headers=now)
        self.assertTrue(h.source_changed(ctx, NB_DAY, old))
        self.assertIn((NB_URL, 1), ctx.client.asked)          # one byte, not the megabyte
        self.assertFalse(h.source_changed(ctx, NB_DAY, "truncated PDF: no %%EOF marker in 1258291 bytes"))
        self.assertTrue(h.source_changed(ctx, NB_DAY, "x (served 1,258,291 bytes, Last-Modified Thu, 08 Oct "
                                                      "2026 10:00:00 GMT)"))
        self.assertFalse(h.source_changed(ctx, NB_DAY, "x (served 1,258,291 bytes, Last-Modified Fri, 09 Oct "
                                                       "2026 13:42:21 GMT)"))
        # a note that records neither is never re-read on this account, and no request is made
        ctx.client.asked.clear()
        self.assertFalse(h.source_changed(ctx, NB_DAY, "PDF could not be read: boom"))
        self.assertEqual(ctx.client.asked, [])

    def test_a_server_that_ignores_the_range_gives_its_length(self):
        from src.ingest import prov_nb_hansard as h
        ctx = ctx_for("nb", {}, range_headers={"Content-Length": "1258291"})
        self.assertTrue(h.source_changed(ctx, NB_DAY, "truncated PDF: no %%EOF marker in 1257984 bytes"))

    def _stored_unreadable(self, ctx, note):
        sp.store_sitting(ctx.conn, "nb", dict(NB_DAY), {}, "unreadable", note)
        ctx.conn.commit()

    def test_the_weekly_reads_a_changed_day_before_its_window_again(self):
        ctx = ctx_for("nb", {})
        ctx.since = "2026-09-29"
        self._stored_unreadable(ctx, "truncated PDF: no %%EOF marker in 1257984 bytes")
        read = []

        def read_day(day):
            read.append(day["key"])
            return [], []
        stats = sp.collect_days(ctx, [dict(NB_DAY)], read_day, lambda d: pn.Resolver({}, []), None, None,
                                recheck=lambda day, note: "1257984" in note)
        self.assertEqual((read, stats.get("rechecked"), stats["days_read"]), (["nb-61-2-2026-05-28"], 1, 1))
        # read again: the stored note is the new reading's (an empty fake day), not the old gap
        self.assertIn("no speaker turns parsed",
                      ctx.conn.execute("SELECT note FROM prov_speech_sittings").fetchone()[0])

    def test_an_unchanged_or_failing_check_leaves_the_day(self):
        ctx = ctx_for("nb", {})
        ctx.since = "2026-09-29"
        self._stored_unreadable(ctx, "truncated PDF: no %%EOF marker in 1258291 bytes")
        read = []

        def boom(day, note):
            raise OSError("no answer")
        for recheck in (lambda day, note: False, boom, None):
            sp.collect_days(ctx, [dict(NB_DAY)], lambda d: read.append(d) or ([], []), lambda d: None, None,
                            None, recheck=recheck)
        self.assertEqual(read, [])
        # a day read cleanly is never rechecked
        sp.store_sitting(ctx.conn, "nb", dict(NB_DAY), {}, "ok", None)
        sp.collect_days(ctx, [dict(NB_DAY)], lambda d: read.append(d) or ([], []), lambda d: None, None, None,
                        recheck=lambda day, note: True)
        self.assertEqual(read, [])

    def test_the_tool_passes_the_readers_check(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import prov_speeches
        from src.ingest import prov_nb_hansard as h
        self.assertIs(prov_speeches.reader_for("nb"), h)
        self.assertTrue(callable(getattr(h, "source_changed", None)))

    def test_no_longer_a_known_gap(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import prov_collect
        self.assertFalse(prov_collect.known_gap("nb", "nb nb-61-2-2026-05-28: truncated PDF: no %%EOF marker in "
                                                      "1257984 bytes"))


class RangedRequestThrottleTests(unittest.TestCase):
    def test_a_ranged_check_waits_out_the_host_interval(self):
        slept, now = [], [100.0]

        class Resp:
            headers = {"Content-Range": "bytes 0-0/10"}
            status = 206

            def read(self):
                return b"%"

        class Opener:
            def open(self, request, timeout=None):
                return Resp()
        client = HttpClient(raw_dir="/tmp/unused", sleep=slept.append, clock=lambda: now[0], opener=Opener())
        client.set_host_throttle("www.legnb.ca", 10.0)
        client.get_bytes(NB_URL, "f", "s", first_bytes=1)
        client.get_bytes(NB_URL, "f", "s", first_bytes=1)
        self.assertEqual(slept, [10.0])
        self.assertEqual(client.last_headers["Content-Range"], "bytes 0-0/10")


class NlPrologationDayTests(unittest.TestCase):
    PAGE = fx("nl_hansard_221003.htm")

    def test_the_page_has_no_close_and_is_vouched_complete(self):
        self.assertNotIn("</html>", self.PAGE[-4000:].lower())
        fact = pn.reviewed_complete("nl", NL_URL, self.PAGE, "2022-10-03")
        self.assertIn("Lorie", fact["verified_against"])
        # only that record, that day, and while it still ends as quoted
        self.assertIsNone(pn.reviewed_complete("nl", NL_URL.replace("22-10-03", "22-10-04"), self.PAGE))
        self.assertIsNone(pn.reviewed_complete("nl", NL_URL, self.PAGE, "2022-10-04"))
        self.assertIsNone(pn.reviewed_complete("nl", NL_URL, self.PAGE[:-1500], "2022-10-03"))

    def test_speeches_read_the_day(self):
        from src.ingest import prov_nl_hansard as nh
        ctx = ctx_for("nl", {NL_URL: self.PAGE})
        day = {"key": "nl-50-1-2022-10-03", "date": "2022-10-03", "legislature": 50, "session": 1, "url": NL_URL}
        turns, problems = nh.read_day(ctx, day)
        self.assertEqual(problems, [])
        self.assertTrue(turns)
        # a page cut short elsewhere is still a gap
        ctx = ctx_for("nl", {NL_URL: self.PAGE[:-1500]})
        self.assertEqual(nh.read_day(ctx, day), (None, ["truncated Hansard (no closing </html>)"]))

    def test_the_vote_collector_reads_the_day(self):
        from src.ingest import prov_nl as nl
        ctx = ctx_for("nl", {NL_URL: self.PAGE})
        ctx.tax = pc.load_taxonomy()
        n, gaps = nl.read_sitting(ctx, 50, 1, {"date": "2022-10-03", "url": NL_URL, "part": None},
                                  nl.make_resolver(ctx.conn), pc.load_watchlist("nl"))
        self.assertEqual((n, gaps, ctx.gaps), (0, 0, []))
        self.assertTrue(ps.sitting_done(ctx.conn, NL_URL))

    def test_no_longer_a_known_gap(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import prov_collect
        self.assertFalse(prov_collect.known_gap("nl", "nl-50-1-2022-10-03: {0}: truncated Hansard (no closing "
                                                      "</html>)".format(NL_URL)))


class MbNotASittingTests(unittest.TestCase):
    DAY = {"key": "mb-43-1-2024-05-10-c", "date": "2024-05-10", "part": "c", "legislature": 43, "session": 1,
           "summary": MB_URL, "url": MB_URL, "pdfs": {}}

    def test_the_day_is_stored_as_no_sitting_without_a_fetch(self):
        from src.ingest import prov_mb_hansard as mh
        ctx = ctx_for("mb", {})
        stats = sp.collect_days(ctx, [dict(self.DAY)], lambda d: mh.read_day(ctx, d), lambda d: None, None, None)
        row = ctx.conn.execute("SELECT status, turns, note FROM prov_speech_sittings").fetchone()
        self.assertEqual((row[0], row[1]), ("ok", 0))
        self.assertIn("not a sitting day", row[2])
        self.assertIn("Todd LaRue", row[2])
        self.assertEqual((ctx.gaps, stats["day_gaps"], stats["no_sitting"]), ([], 0, 1))
        self.assertEqual(ctx.client.asked, [])

    def test_only_that_listing_on_that_day(self):
        self.assertIsNotNone(pn.reviewed_not_sitting("mb", "2024-05-10", MB_URL))
        self.assertIsNone(pn.reviewed_not_sitting("mb", "2024-05-09", MB_URL))
        self.assertIsNone(pn.reviewed_not_sitting("mb", "2024-05-10", MB_URL.replace("54c", "54b")))

    def test_no_longer_a_known_gap(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import prov_collect
        self.assertFalse(prov_collect.known_gap("mb", "mb mb-43-1-2024-05-10-c: the summary {0} links no HTML "
                                                      "transcript".format(MB_URL)))


if __name__ == "__main__":
    unittest.main()
