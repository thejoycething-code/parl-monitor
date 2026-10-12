"""Markdown bold becomes real Sheets bold; the RF4 block overflows.

Christopher, 12 October 2026 (filling the Anita Meston brief): Sheets shows
"**What:**" literally, so the publisher strips the asterisks and sets bold
through textFormatRuns, whose startIndex counts UTF-16 code units.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import publish_briefs_to_drive as pb


class BoldRunsTest(unittest.TestCase):

    def test_plain_text_is_untouched(self):
        self.assertEqual(pb.bold_runs("no bold here"), ("no bold here", None))
        self.assertEqual(pb.bold_runs(""), ("", None))
        self.assertEqual(pb.bold_runs(None), (None, None))

    def test_labels_become_bold_runs_and_lose_their_asterisks(self):
        text, runs = pb.bold_runs("**What:** a sacking.\n**Who:** a teacher.")
        self.assertEqual(text, "What: a sacking.\nWho: a teacher.")
        self.assertEqual(runs, [
            {"startIndex": 0, "format": {"bold": True}},
            {"startIndex": 5, "format": {"bold": False}},
            {"startIndex": 17, "format": {"bold": True}},
            {"startIndex": 21, "format": {"bold": False}}])

    def test_euro_sign_counts_one_code_unit(self):
        text, runs = pb.bold_runs("€1,417 raised: **median**")
        self.assertEqual(text, "€1,417 raised: median")
        # The euro sign is one UTF-16 unit (three UTF-8 bytes): a byte count
        # would put the run at 17.
        self.assertEqual(runs, [{"startIndex": 15, "format": {"bold": True}}])

    def test_astral_characters_count_two_code_units(self):
        text, runs = pb.bold_runs("\U0001F4E2 **Now**")
        self.assertEqual(text, "\U0001F4E2 Now")
        self.assertEqual(runs[0]["startIndex"], 3)

    def test_no_run_starts_at_the_end_of_the_text(self):
        _, runs = pb.bold_runs("**All bold**")
        self.assertEqual(runs, [{"startIndex": 0, "format": {"bold": True}}])


class RichTextRequestsTest(unittest.TestCase):

    def test_values_are_cleaned_and_cells_located(self):
        updates = [{"range": "'AA Classical Series'!B12",
                    "values": [["**What:** x"]]},
                   {"range": "'AA Classical Series'!A20",
                    "values": [["plain", "**b**"], ["", ""]]}]
        reqs = pb.rich_text_requests(updates, {"AA Classical Series": 7})
        self.assertEqual(updates[0]["values"], [["What: x"]])
        self.assertEqual(updates[1]["values"][0], ["plain", "b"])
        starts = [r["updateCells"]["start"] for r in reqs]
        self.assertEqual(starts, [
            {"sheetId": 7, "rowIndex": 11, "columnIndex": 1},
            {"sheetId": 7, "rowIndex": 19, "columnIndex": 1}])
        cell = reqs[0]["updateCells"]["rows"][0]["values"][0]
        self.assertEqual(cell["userEnteredValue"], {"stringValue": "What: x"})

    def test_rf4_block_overflows_from_header_to_total_rows(self):
        req = pb.rf4_overflow_request(7, 30, 39)["repeatCell"]
        self.assertEqual(req["range"], {"sheetId": 7, "startRowIndex": 29,
                                        "endRowIndex": 39,
                                        "startColumnIndex": 0,
                                        "endColumnIndex": 7})
        self.assertEqual(req["cell"]["userEnteredFormat"]["wrapStrategy"],
                         "OVERFLOW_CELL")


if __name__ == "__main__":
    unittest.main()
