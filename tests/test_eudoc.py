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

    def test_the_preamble_citations_are_not_the_subject(self):
        """Every EP resolution opens "having regard to the Charter ... freedom of
        expression". Matching that filed a narco-trafficking resolution under free
        speech, on the strength of a citation (17 September 2026)."""
        blob = docx([
            "\u2013having regard to the Charter of Fundamental Rights of the European Union, "
            "in particular its articles on human dignity and freedom of expression,",
            "having regard to its resolution of 12 December 2023 on addictive design of online services,",
            "Calls on the Commission to set a minimum age for access to social media services."])
        body = eudoc.body_text(blob)
        self.assertNotIn("freedom of expression", body)
        self.assertNotIn("addictive design", body, "an em-dash-less citation counts too")
        self.assertIn("minimum age", body)

    def test_citations_can_be_kept_when_a_caller_wants_the_whole_text(self):
        blob = docx(["\u2013having regard to the Charter of Fundamental Rights and freedom of expression,"])
        self.assertIn("freedom of expression", eudoc.body_text(blob, drop_citations=False))

    def test_a_bot_wall_page_is_not_mistaken_for_a_text(self):
        with self.assertRaises(zipfile.BadZipFile):
            eudoc.paragraphs(b"<html><body>Access denied</body></html>")


if __name__ == "__main__":
    unittest.main()


RECORD = {"data": [{"identifier": "RC-B-10-2026-0404", "is_realized_by": [
    {"id": "eli/dl/doc/X/el", "is_embodied_by": [
        {"is_exemplified_by": "distribution/reds_iPlRe/X/X_el.docx"}]},
    {"id": "eli/dl/doc/X/en", "is_embodied_by": [
        {"is_exemplified_by": "distribution/reds_iPlRe/X/X_en.pdf"},
        {"is_exemplified_by": "distribution/reds_iPlRe/X/X_en.docx"}]}]}]}


class ShelfTests(unittest.TestCase):
    """Each document type has its own shelf (18 Sept 2026): the report on social
    media and young people was 404 at the adopted-texts path."""

    def test_reports_and_motions_have_their_own_shelves(self):
        self.assertEqual(eudoc.url_for("A-10-2026-0220"),
                         "https://data.europarl.europa.eu/distribution/reds_iPlRp/A-10-2026-0220/A-10-2026-0220_en.docx")
        self.assertEqual(eudoc.url_for("B-10-2026-0406"),
                         "https://data.europarl.europa.eu/distribution/reds_iPlRe/B-10-2026-0406/B-10-2026-0406_en.docx")
        self.assertEqual(eudoc.url_for("TA-10-2026-0313"),
                         "https://data.europarl.europa.eu/distribution/doc/TA-10-2026-0313_en.docx")

    def test_an_unknown_type_is_none_not_a_guess(self):
        self.assertIsNone(eudoc.url_for("RC-B-10-2026-0404"))
        self.assertIsNone(eudoc.url_for(""))

    def test_the_record_names_the_english_docx(self):
        self.assertEqual(eudoc.url_from_record(RECORD),
                         "https://data.europarl.europa.eu/distribution/reds_iPlRe/X/X_en.docx")
        self.assertEqual(eudoc.url_from_record(RECORD, fmt="pdf"),
                         "https://data.europarl.europa.eu/distribution/reds_iPlRe/X/X_en.pdf")
        self.assertIsNone(eudoc.url_from_record({"data": [{"is_realized_by": []}]}))

    def test_resolve_spends_a_call_only_when_the_shelf_is_unknown(self):
        calls = []

        def get_json(url):
            calls.append(url)
            return RECORD
        self.assertTrue(eudoc.resolve_url("A-10-2026-0220", get_json).endswith("A-10-2026-0220_en.docx"))
        self.assertEqual(calls, [])
        self.assertTrue(eudoc.resolve_url("RC-B-10-2026-0404", get_json).endswith("X_en.docx"))
        self.assertEqual(calls, [eudoc.DOCUMENT.format("RC-B-10-2026-0404")])


class NumberedTests(unittest.TestCase):
    def test_a_tab_keeps_the_number_apart_from_the_text(self):
        buf = io.BytesIO()
        body = ("<w:p><w:r><w:t>78.</w:t></w:r><w:r><w:tab/><w:t>Calls on the Commission</w:t></w:r></w:p>")
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("word/document.xml", "<w:document><w:body>" + body + "</w:body></w:document>")
        self.assertEqual(eudoc.paragraphs(buf.getvalue()), ["78. Calls on the Commission"])

    def test_numbered_reads_the_motion_and_not_the_explanatory_statement(self):
        paras = ["REPORT on things", "CONTENTS", "MOTION FOR A EUROPEAN PARLIAMENT RESOLUTION", "1. Stresses one;",
                 "A. whereas the first recital;", "AD. whereas access to health education;",
                 "78. Calls on the Commission;", "85. Highlights the importance;",
                 "EXPLANATORY STATEMENT", "1. The rapporteur believes;"]
        got = eudoc.numbered(paras)
        self.assertEqual(got["78"], "78. Calls on the Commission;")
        self.assertEqual(got["AD"], "AD. whereas access to health education;")
        self.assertEqual(got["1"], "1. Stresses one;", "the explanatory statement's own 1. must not win")

    def test_an_adopted_text_has_no_heading_and_is_read_whole(self):
        got = eudoc.numbered(["Texts adopted", "A. whereas x;", "1. Calls for y;"])
        self.assertEqual(sorted(got), ["1", "A"])
