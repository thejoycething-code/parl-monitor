"""Letters from the President of the General Assembly (13 October 2026).

The 7 October 2026 letter named the 12 October vote on the pandemic
declaration five days ahead; nothing read these letters.
"""

import datetime
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import filter as filt  # noqa: E402
from src.ingest import pga_letters  # noqa: E402
from tests.un_fixtures import fixture_json, fixture_text, un_filter  # noqa: E402


class PgaLetterTests(unittest.TestCase):
    """Step 2: the PGA's letters to member states, where dates appear first."""

    def setUp(self):
        self.letters = pga_letters.parse_letters(fixture_text("pga-letters-81.html.gz"))
        self.pandemic = [l for l in self.letters if "pandemic" in l.title
                         and l.dated == datetime.date(2026, 10, 7)][0]

    def test_every_letter_on_the_listing_is_parsed_once(self):
        self.assertEqual(len(self.letters), 16)
        self.assertEqual(len({l.url for l in self.letters}), 16)
        self.assertEqual(self.letters[0].dated, datetime.date(2026, 10, 9),
                         "newest first")

    def test_the_7_october_letter(self):
        l = self.pandemic
        self.assertTrue(l.title.startswith("Submission of the political declaration on "
                                           "pandemic prevention, preparedness and response"))
        self.assertNotIn("→", l.title)
        self.assertTrue(l.pdf.endswith("PGA81-Letter-Pandemic-Prevention-Declaration-7-October-2026.pdf"))
        self.assertEqual(l.addressee, "To all Permanent Representatives and Permanent Observers")

    def test_the_title_alone_names_the_vote_date(self):
        self.assertEqual(self.pandemic.announced, (datetime.date(2026, 10, 12),))
        self.assertIn("adoption", self.pandemic.signals)
        self.assertIn("political declaration", self.pandemic.signals)

    def test_the_title_is_on_our_ground(self):
        tax, wl = un_filter()
        self.assertIn(7, filt.filter_item(tax, wl, self.pandemic.match_text).issue_areas)

    def test_the_body_names_the_draft_and_the_plenary(self):
        l = self.pandemic
        l.body = pga_letters.parse_letter_body(fixture_text("pga-letter-pandemic-7oct.html.gz"))
        pga_letters.annotate(l)
        self.assertIn("A/81/L.6", l.symbols)
        self.assertIn("plenary", l.signals)
        self.assertEqual(l.next_date, datetime.date(2026, 10, 12))
        self.assertNotIn(datetime.date(2026, 9, 25), l.announced,
                         "the high-level meeting already held is history, not a signal")

    def test_dates_without_a_year_and_past_dates(self):
        got = pga_letters.announced_dates(
            "dated 6 October, held on 25 September 2026, meeting on 12 October and 15 January",
            datetime.date(2026, 12, 20))
        self.assertEqual(got, (datetime.date(2027, 1, 15),))

    def test_a_challenge_page_is_blocked_not_empty(self):
        """A challenge must be 'could not read', never 'no letters'."""
        with self.assertRaises(pga_letters.BlockedError):
            pga_letters.parse_letters("<html><title>Just a moment...</title></html>")

    def test_session_number_turns_in_september(self):
        self.assertEqual(pga_letters.session_for(datetime.date(2026, 10, 13)), 81)
        self.assertEqual(pga_letters.session_for(datetime.date(2027, 8, 31)), 81)
        self.assertEqual(pga_letters.session_for(datetime.date(2027, 9, 1)), 82)

    def test_fetch_reads_recent_bodies_and_honours_the_crawl_delay(self):
        listing = fixture_text("pga-letters-81.html.gz")
        page = fixture_text("pga-letter-pandemic-7oct.html.gz")

        class Client:
            def __init__(self):
                self.throttles, self.urls = {}, []

            def set_host_throttle(self, host, seconds):
                self.throttles[host] = seconds

            def get_text(self, url, feed, slug, **kw):
                self.urls.append(url)
                if url.endswith("/documents/letters/"):
                    return listing
                if "pandemic-prevention-declaration" in url:
                    return page
                raise RuntimeError("HTTP 404")

        client = Client()
        letters, failures = pga_letters.fetch_letters(
            client, today=datetime.date(2026, 10, 8), body_days=3)
        self.assertEqual(client.throttles, {"www.un.org": 10})
        self.assertEqual(client.urls[0], "https://www.un.org/pga/81/documents/letters/")
        # 5-8 October: five letter pages asked for (the 9 October one is
        # after "today"); four 404 here and are named, not dropped.
        self.assertEqual(len(client.urls), 1 + 5)
        self.assertEqual(len(failures), 4)
        l = [l for l in letters if "pandemic-prevention-declaration" in l.url][0]
        self.assertIn("A/81/L.6", l.symbols)


if __name__ == "__main__":
    unittest.main()
