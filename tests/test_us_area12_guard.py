"""Taxonomy v1.18: "human trafficking" does not file a US border-enforcement
bill under area 12 (Christopher, 9 October 2026).

tests/fixtures/us_area12/bills.json holds eight real BILLSTATUS records of
the 119th Congress as tools/us_rollcalls.py stored them (titles, CRS subject
terms, CRS summary), read from the store on 9 October 2026.
"""

import importlib.util
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import filter as filt  # noqa: E402

spec = importlib.util.spec_from_file_location("us_rollcalls",
                                              os.path.join(ROOT, "tools", "us_rollcalls.py"))
ur = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ur)

TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
with open(os.path.join(ROOT, "tests", "fixtures", "us_area12", "bills.json"), encoding="utf-8") as fh:
    BILLS = json.load(fh)


def areas(key):
    return ur.classify_bill(TAX, ur.empty_watchlist(), BILLS[key]).issue_areas


class Area12GuardTests(unittest.TestCase):
    def test_border_enforcement_bills_leave_area_12(self):
        for key in ("119/hr/4371",    # Kayla Hamilton Act
                    "119/s/2",        # Secure America Act
                    "119/s/1071"):    # NDAA FY2026
            self.assertNotIn(12, areas(key), key)
            self.assertIn(11, areas(key), key)

    def test_genuine_trafficking_bills_stay(self):
        for key in ("119/hr/1503",    # Stop Forced Organ Harvesting Act
                    "119/hr/1379",    # Trafficking Survivors Relief Act
                    "119/hr/6227",    # Human Trafficking Survivor Tax Relief Act
                    "119/s/2647",     # International Trafficking Victims Protection Reauth.
                    "119/hr/2851"):   # WISE Act: survivors inside immigration enforcement
            self.assertIn(12, areas(key), key)

    def test_the_veto_is_company_not_the_word(self):
        wl = ur.empty_watchlist()
        self.assertEqual(filt.filter_item(TAX, wl, "A bill to combat human trafficking").issue_areas,
                         [12])
        self.assertNotIn(12, filt.filter_item(
            TAX, wl, "Border security and unlawful immigration; human trafficking").issue_areas)


if __name__ == "__main__":
    unittest.main()
