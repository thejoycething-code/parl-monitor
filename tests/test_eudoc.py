"""Reading an adopted text's body. Nothing here touches the network."""

import io
import os
import sys
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import eudoc  # noqa: E402


def docx(paragraphs):
    buf = io.BytesIO()
    body = "".join("<w:p><w:r><w:t>{0}</w:t></w:r></w:p>".format(p) for p in paragraphs)
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w:document><w:body>" + body + "</w:body></w:document>")
    return buf.getvalue()


class DocTests(unittest.TestCase):
    def test_the_distribution_url_is_built_from_the_identifier(self):
        self.assertEqual(
            eudoc.url_for("TA-10-2026-0313"),
            "https://data.europarl.europa.eu/distribution/doc/TA-10-2026-0313_en.docx")
        self.assertTrue(eudoc.url_for("TA-10-2026-0313", "pdf").endswith(".pdf"))

    def test_paragraphs_come_back_in_order(self):
        blob = docx(["European Parliament", "Texts adopted", "A long operative paragraph here."])
        self.assertEqual(eudoc.paragraphs(blob)[-1], "A long operative paragraph here.")

    def test_word_field_codes_are_dropped(self):
        """Word leaves 'TC"(A10-0199/2026)" \\l3 MERGEFORMAT' in the run text; it is
        not prose and it matches nothing good."""
        blob = docx(['TC"(A10-0199/2026 - Rapporteur)" MERGEFORMAT', "Real prose in this paragraph."])
        self.assertEqual(eudoc.paragraphs(blob), ["Real prose in this paragraph."])

    def test_short_structural_lines_are_left_out_of_the_body(self):
        blob = docx(["P10_TA(2026)0313", "2024-2029",
                     "Calls on the Commission to set a minimum age for access to social media."])
        body = eudoc.body_text(blob)
        self.assertIn("minimum age", body)
        self.assertNotIn("2024-2029", body)

    def test_a_bot_wall_page_is_not_mistaken_for_a_text(self):
        with self.assertRaises(zipfile.BadZipFile):
            eudoc.paragraphs(b"<html><body>Access denied</body></html>")


if __name__ == "__main__":
    unittest.main()
