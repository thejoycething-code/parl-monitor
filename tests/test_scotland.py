"""Scottish Parliament ingester tests (handoff 4.11, acceptance 9.2)."""

import datetime
import gzip
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.ingest import scotland

RAW = os.path.join(ROOT, "data", "raw", "2026-08-01")
SLUG = "assisted-dying-for-terminally-ill-adults-scotland-bill"


def load_text(slug):
    with gzip.open(os.path.join(RAW, slug + ".json.gz"), "rb") as h:
        return h.read().decode("utf-8")


def load_json(slug):
    with gzip.open(os.path.join(RAW, slug + ".json.gz"), "rb") as h:
        return json.loads(h.read().decode("utf-8"))


class StatusParsingTests(unittest.TestCase):
    def test_assisted_dying_bill_fell_2026_03_17(self):  # acceptance 9.2
        status, date, stage = scotland.parse_status(load_text("scotland_bill-" + SLUG))
        self.assertEqual(status, scotland.FELL)
        self.assertEqual(date, datetime.date(2026, 3, 17))
        self.assertEqual(stage, "Stage 3")

    def test_closed_note_format(self):
        status, date, stage = scotland.parse_status(load_text("scotland_bill-" + SLUG))
        bill = scotland.HolyroodBill(SLUG, "Assisted Dying (Scotland) Bill", status, date, stage, [2])
        self.assertEqual(bill.closed_note(), "Fell on 2026-03-17 at Stage 3")
        self.assertTrue(bill.is_terminal)

    def test_does_not_mistake_motion_status_for_bill_status(self):
        # The page carries "Current status: Taken in the Chamber on Tuesday, 13
        # May 2025" for a MOTION. The bill status must not come from that line.
        text = scotland.strip_html(load_text("scotland_bill-" + SLUG))
        self.assertIn("Current status:", text)          # the trap is present
        _, date, _ = scotland.parse_status(load_text("scotland_bill-" + SLUG))
        self.assertNotEqual(date, datetime.date(2025, 5, 13))

    def test_royal_assent_and_passed_shapes(self):
        self.assertEqual(
            scotland.parse_status("<p>The Bill received Royal Assent on 4 June 2026.</p>")[:2],
            (scotland.ASSENT, datetime.date(2026, 6, 4)))
        self.assertEqual(
            scotland.parse_status("<p>The Bill was passed on 2 February 2026.</p>")[:2],
            (scotland.PASSED, datetime.date(2026, 2, 2)))

    def test_live_bill_has_no_terminal_status(self):
        status, date, _ = scotland.parse_status("<p>This bill is at Stage 1.</p>")
        self.assertEqual(status, scotland.LIVE)
        self.assertIsNone(date)
        bill = scotland.HolyroodBill("x", "X", status, date, None, [])
        self.assertFalse(bill.is_terminal)
        self.assertIsNone(bill.closed_note())

    def test_html_entities_decoded(self):
        self.assertIn("Member's bill", scotland.strip_html(load_text("scotland_bill-" + SLUG)))


class ApiIndexTests(unittest.TestCase):
    def test_index_is_identity_only_and_finds_the_bill(self):
        index = load_json("scotland_bills-api")
        self.assertGreater(len(index), 400)
        hits = scotland.find_in_index(index, "Assisted Dying for Terminally Ill Adults")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["ID"], 445)
        # No status field exists on the API rows; status must come from the page.
        self.assertNotIn("status", {k.lower() for k in hits[0]})

    def test_bill_url(self):
        bill = scotland.HolyroodBill(SLUG, "X", scotland.FELL, None, None, [2])
        self.assertEqual(bill.url, "https://www.parliament.scot/bills-and-laws/bills/s6/" + SLUG)


if __name__ == "__main__":
    unittest.main()
