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
