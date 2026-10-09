"""Taxonomy v1.19 (Christopher, 9 October 2026): the five NDAA amendment
votes whose purposes matched nothing once phase 1b stopped them inheriting
their bill's areas. The purposes are the real BILLSTATUS texts as stored."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import filter as filt  # noqa: E402

TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])

PURPOSES = {
    # H.R. 3838 (NDAA FY2026), 2025
    246: ("Amendment prohibits the Department of Defense from covering or furnishing "
          "gender-related medical treatment under TRICARE.", 3),
    247: ("Amendment prohibits the Superintendent of a Service Academy from allowing a cadet or "
          "midshipman who is male from participating in an athletic program or activity that is "
          "designated exclusively for females.", 5),
    248: ("An amendment numbered 16 printed in Part A of House Report 119-255 to prohibit the "
          "Secretary of Defense from soliciting information through a form or survey regarding the "
          "gender identity of an individual", 5),
    # H.R. 8800 (NDAA FY2027), 2026
    267: ("Amendment prohibits gender-related medical care under TRICARE and prevents TRICARE from "
          "covering certain gender-related medical procedures and treatments.", 3),
    268: ("Amendment prohibits male participation in female sports at Department of Defense "
          "Education Activity schools.", 5),
}


class NdaaTermTests(unittest.TestCase):
    def test_each_purpose_lands_in_its_area(self):
        for roll, (text, area) in PURPOSES.items():
            self.assertIn(area, filt.filter_item(TAX, WL, text).issue_areas, roll)

    def test_the_guards_hold(self):
        self.assertEqual(filt.filter_item(TAX, WL, "A survey of schools; gender identity").issue_areas,
                         [])
        self.assertEqual(filt.filter_item(
            TAX, WL, "Parking bays designated exclusively for females").issue_areas, [])


if __name__ == "__main__":
    unittest.main()
