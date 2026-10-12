"""What's On committee events reach the filter with their committee name.

Found 2026-10-12: the Committee field arrives as {'Id', 'Description', ...}
with no Name, so the Joint Committee on the Draft Conversion Practices Bill
(meeting 12 and 15 Oct) was filtered as an empty string and never shown.
The same day's Courts and Tribunals Bill remaining stages (clause 17 repeals
the presumption of parental involvement) had no taxonomy term in its title.
"""

import datetime
import os
import unittest

from src import filter as filt
from src.ingest import whatson

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load():
    return (filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml")),
            filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml")))


class CommitteeEventTest(unittest.TestCase):
    ROW = {"Id": 1, "StartDate": "2026-10-12T00:00:00", "StartTime": "16:00",
           "House": "Joint", "Category": "Private Meeting", "Type": "Select & Joint Committees",
           "Description": None,
           "Committee": {"Id": 851, "Description": "Draft Conversion Practices Bill (Joint Committee)",
                         "Category": 2, "IsLords": True, "IsCommons": True}}

    def test_committee_description_is_read(self):
        e = whatson.parse_event(self.ROW)
        self.assertIn("Draft Conversion Practices Bill", whatson.event_text(e))
        self.assertIn("Draft Conversion Practices Bill", whatson.event_label(e))

    def test_conversion_practices_committee_matches(self):
        tax, wl = load()
        e = whatson.parse_event(self.ROW)
        self.assertTrue(filt.filter_item(tax, wl, whatson.event_text(e)).matched())

    def test_name_still_wins_over_description(self):
        self.assertEqual(whatson._text({"Name": "A", "Description": "B"}), "A")


class WatchedBillTest(unittest.TestCase):
    def test_courts_and_tribunals_remaining_stages_matches(self):
        tax, wl = load()
        r = filt.filter_item(tax, wl, "Remaining stages of the Courts and Tribunals bill Legislation")
        self.assertTrue(r.matched())


if __name__ == "__main__":
    unittest.main()
