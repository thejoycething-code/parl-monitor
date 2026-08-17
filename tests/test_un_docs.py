"""UN documents by symbol: existence, enumeration, honesty about titles."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.ingest import un_docs


class FakeClient:
    """Serves PDF bytes for listed symbols, the not-found page otherwise."""

    def __init__(self, existing):
        self.existing = set(existing)
        self.asked = []
        self.ranges = []

    def get_bytes(self, url, feed, slug, timeout=None, first_bytes=None):
        self.asked.append(slug)
        self.ranges.append(first_bytes)
        symbol = slug.replace("-", "/")
        return b"%PDF-1.7 ..." if symbol in self.existing else b"<!doctype html>..."


class UnDocsTests(unittest.TestCase):
    def test_direct_true_is_in_the_url(self):
        """Without it docs.un.org serves a 4KB redirect shell, which is why
        this source was written off before the Journal config named it."""
        self.assertIn("?direct=true", un_docs.doc_url("A/C.3/81/L.1"))
        self.assertIn("/en/A/C.3/81/L.1", un_docs.doc_url("A/C.3/81/L.1"))

    def test_existence_is_decided_by_content_not_status(self):
        """A missing symbol still answers 200, with an HTML not-found page."""
        client = FakeClient(["A/C.3/81/L.1"])
        self.assertTrue(un_docs.head(client, "A/C.3/81/L.1").is_document)
        self.assertFalse(un_docs.head(client, "A/C.3/81/L.9").is_document)

    def test_only_a_range_is_fetched(self):
        """Downloading whole PDFs to read five bytes cost ~300KB per symbol."""
        client = FakeClient([])
        un_docs.head(client, "A/C.3/81/L.1")
        self.assertEqual(client.ranges, [64])

    def test_enumeration_survives_a_gap_in_the_numbering(self):
        """Withdrawn or renumbered drafts leave holes; stopping at the first
        one would silently truncate the set."""
        client = FakeClient(["A/C.3/81/L.1", "A/C.3/81/L.2", "A/C.3/81/L.5"])
        found, _checked = un_docs.enumerate_drafts(
            client, un_docs.THIRD_COMMITTEE_DRAFTS, 81, max_n=20, stop_after_misses=5)
        self.assertEqual([d.symbol for d in found],
                         ["A/C.3/81/L.1", "A/C.3/81/L.2", "A/C.3/81/L.5"])

    def test_enumeration_stops_instead_of_walking_to_max(self):
        client = FakeClient(["A/C.3/81/L.1"])
        _found, checked = un_docs.enumerate_drafts(
            client, un_docs.THIRD_COMMITTEE_DRAFTS, 81, max_n=120, stop_after_misses=3)
        self.assertLess(checked, 10, "should stop after the misses run on")


if __name__ == "__main__":
    unittest.main()


class DraftParsingTests(unittest.TestCase):
    """First-page parsing, against text extracted from real documents."""

    RESOLUTION = """United Nations A/C.3/80/L.20
General Assembly
Distr.: Limited
22 October 2025
Original: English
25-17035 (E)
Eightieth session
Third Committee
Agenda item 67
Promotion and protection of the rights of children
Andorra, Antigua and Barbuda, Argentina, Austria, Bahamas (The),
"""

    DECISION = """United Nations A/C.3/80/L.60
General Assembly
Distr.: Limited
16 November 2025
Eightieth session
Third Committee
Agenda item 121
Revitalization of the work of the General Assembly
Draft decision submitted by the Chair of the Committee
"""

    ORG_OF_WORK = """United Nations A/C.3/80/L.1
General Assembly
4 September 2025
Third Committee
Organization of the work of the Third Committee
Note by the Secretariat
"""

    def test_agenda_item_and_subject(self):
        d = un_docs.parse_draft("A/C.3/80/L.20", self.RESOLUTION)
        self.assertEqual(d.agenda_item, 67)
        self.assertEqual(d.subject, "Promotion and protection of the rights of children")
        self.assertEqual(d.dated, "22 October 2025")

    def test_a_sponsor_list_ends_the_subject(self):
        """Subjects wrap over two lines, so the parser reads on -- but a run
        of comma-separated country names is a sponsor list, not a subject."""
        d = un_docs.parse_draft("A/C.3/80/L.20", self.RESOLUTION)
        self.assertNotIn("Andorra", d.subject)

    def test_draft_kind_is_read_when_stated(self):
        d = un_docs.parse_draft("A/C.3/80/L.60", self.DECISION)
        self.assertEqual(d.kind, "decision")
        self.assertEqual(d.subject, "Revitalization of the work of the General Assembly")

    def test_l1_is_the_programme_of_work_not_a_draft(self):
        """L.1 of a session is the Organization of Work note, and its annex is
        the committee's dated agenda."""
        d = un_docs.parse_draft("A/C.3/80/L.1", self.ORG_OF_WORK)
        self.assertIsNone(d.agenda_item)
        self.assertTrue(d.is_programme_of_work)


class SponsorWrapTests(unittest.TestCase):
    """Where the draft's OWN title begins, across the shapes the PDF produces.

    Each of these silently fell back to the agenda-item title in an earlier
    version. That matters most for the HRC, whose item 3 is an omnibus
    ("Promotion and protection of all human rights, civil, political...")
    covering most thematic resolutions, so the item title says nothing about
    the text being voted on.
    """

    def parse(self, text):
        return un_docs.parse_draft("A/HRC/58/L.9", text)

    def test_phrase_split_across_lines(self):
        """"... and Ukraine* : draft" / "resolution" -- the phrase itself wraps."""
        d = self.parse("Agenda item 4\nHuman rights situations that require attention\n"
                       "Albania, Belgium and Ukraine* : draft\nresolution\n"
                       "58/... Promotion and protection of human rights in Nicaragua\n"
                       "The Human Rights Council,\n")
        self.assertEqual(d.kind, "resolution")
        self.assertEqual(d.title, "Promotion and protection of human rights in Nicaragua")

    def test_single_sponsor_with_footnote_asterisk(self):
        """"Ghana:* draft resolution" -- the asterisk sits inside the colon."""
        d = self.parse("Agenda item 10\nTechnical assistance\n"
                       "Ghana:* draft resolution\n"
                       "58/... Technical assistance and capacity-building for Mali\n"
                       "The Human Rights Council,\n")
        self.assertEqual(d.kind, "resolution")
        self.assertIn("Mali", d.title)

    def test_amendment_names_the_draft_it_attacks(self):
        """Amendments are how language is inserted or stripped, so the target
        matters as much as the text."""
        d = self.parse("Agenda item 3\nPromotion and protection of all human rights\n"
                       "Belarus,* Eritrea* :\namendment to draft resolution A/HRC/58/L.7\n"
                       "58/... Question of the realization in all countries\n"
                       "After paragraph 21, insert a new paragraph\n")
        self.assertEqual(d.kind, "amendment")
        self.assertEqual(d.amends, "A/HRC/58/L.7")
        self.assertIn("realization", d.title)

    def test_topic_prefers_the_specific_title(self):
        d = self.parse("Agenda item 3\nPromotion and protection of all human rights\n"
                       "Ghana:* draft resolution\n58/... Freedom of religion or belief\n"
                       "The Human Rights Council,\n")
        self.assertEqual(d.topic, "Freedom of religion or belief")
        self.assertNotEqual(d.topic, d.subject)


class AmendmentInstructionTests(unittest.TestCase):
    """An amendment's operative text is where the contested language is."""

    BURUNDI = ("Agenda item 67\nPromotion and protection of the rights of children\n"
               "Burundi: amendment to revised draft resolution A/C.3/80/L.20/Rev.1\n"
               "Rights of the child\n"
               "1. In operative paragraph 13, delete “sexual and reproductive "
               "health,”. 2. In operative paragraphs 27 and 43, delete "
               "“sexual and reproductive”.\n")

    def setUp(self):
        self.draft = un_docs.parse_draft("A/C.3/80/L.64", self.BURUNDI)

    def test_revised_targets_are_recognised(self):
        """"amendment to REVISED draft resolution" -- a pattern expecting only
        "amendment to draft resolution" silently dropped four amendments to
        session 80's children's rights resolution."""
        self.assertEqual(self.draft.kind, "amendment")
        self.assertEqual(self.draft.amends, "A/C.3/80/L.20/Rev.1")

    def test_title_stays_clean(self):
        self.assertEqual(self.draft.title, "Rights of the child")

    def test_instruction_is_kept_separately(self):
        self.assertIn("sexual and reproductive", self.draft.instruction)
        self.assertNotIn("sexual and reproductive", self.draft.title)

    def test_classify_on_includes_the_instruction(self):
        """Title alone reads as children's rights; the instruction is what
        makes it an abortion-language fight."""
        self.assertIn("Rights of the child", self.draft.classify_on)
        self.assertIn("sexual and reproductive", self.draft.classify_on)
