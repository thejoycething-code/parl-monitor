"""GA plenary draft resolutions, A/81/L.n (13 October 2026).

A/81/L.6, the political declaration on pandemic prevention, preparedness
and response, was dated 5 October 2026; only Third Committee and HRC drafts
were walked.
"""

import datetime
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import filter as filt  # noqa: E402
from src.ingest import un_docs  # noqa: E402
from tests.un_fixtures import fixture_json, fixture_text, un_filter  # noqa: E402


class GaPlenaryDraftTests(unittest.TestCase):
    """Step 3: GA plenary drafts (A/81/L.n), walked like A/C.3/81/L.n."""

    def test_the_pattern(self):
        self.assertEqual(un_docs.GA_PLENARY_DRAFTS.format(session=81, n=6), "A/81/L.6")

    def test_walk_uses_the_same_existence_test(self):
        class Client:
            def get_bytes(self, url, feed, slug, first_bytes=None, **kw):
                symbol = slug.replace("-", "/")
                return b"%PDF-1.7" if symbol in {"A/81/L.1", "A/81/L.3", "A/81/L.6"} else b"<!doctype"
        found, checked = un_docs.enumerate_drafts(
            Client(), un_docs.GA_PLENARY_DRAFTS, 81, max_n=30, stop_after_misses=5)
        self.assertEqual([d.symbol for d in found], ["A/81/L.1", "A/81/L.3", "A/81/L.6"])
        self.assertEqual(checked, 11)

    def test_a_presidents_draft_has_its_own_title(self):
        """No sponsor list: the title follows 'submitted by the President'."""
        d = un_docs.parse_draft("A/81/L.6", fixture_text("a-81-l-6-page1.txt"))
        self.assertEqual(d.agenda_item, 129)
        self.assertEqual(d.subject, "Global health and foreign policy")
        self.assertEqual(d.title, "Political declaration on pandemic prevention, "
                                  "preparedness and response")
        self.assertEqual(d.kind, "resolution")
        self.assertEqual(d.dated, "5 October 2026")

    def test_title_stops_at_the_body_with_its_comma(self):
        d = un_docs.parse_draft("A/81/L.3", fixture_text("a-81-l-3-page1.txt"))
        self.assertEqual(d.title, "United Nations Declaration on Sea Level Rise")

    def test_the_pandemic_draft_is_our_ground_and_the_sea_level_one_is_not(self):
        tax, wl = un_filter()
        l6 = un_docs.parse_draft("A/81/L.6", fixture_text("a-81-l-6-page1.txt"))
        l3 = un_docs.parse_draft("A/81/L.3", fixture_text("a-81-l-3-page1.txt"))
        self.assertEqual(filt.filter_item(tax, wl, l6.classify_on).issue_areas, [7])
        self.assertEqual(filt.filter_item(tax, wl, l3.classify_on).issue_areas, [])

    def test_the_agenda_item_title_alone_would_have_missed_it(self):
        tax, wl = un_filter()
        self.assertEqual(filt.filter_item(tax, wl, "Global health and foreign policy").issue_areas, [])


if __name__ == "__main__":
    unittest.main()
