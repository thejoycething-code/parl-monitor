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
