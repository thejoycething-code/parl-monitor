"""retag_passages.py must not clear PQ tags from a truncated archive.

Measured 2026-09-06: data/raw holds ~300 characters per PQ (median 251,
max 339). Re-deriving areas from that snippet would have CLEARED 34
previously tagged rows -- 23 of them "Religion: Education" and "Sikhs:
Curriculum" tagged via "religious education", 20 ending mid-sentence.
Re-derivation is authoritative only when it reads at least what the
ingest read; for PQs it reads less.
"""

import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PqArchiveTests(unittest.TestCase):
    def setUp(self):
        self.src = open(os.path.join(ROOT, "tools", "retag_passages.py"),
                        encoding="utf-8").read()

    def test_pq_apply_is_refused_while_coverage_is_short(self):
        """Since 2026-09-06 the archive can hold full text (pqs.fetch_question);
        the refusal is now conditional on how much of the ledger has it."""
        self.assertIn('if kind == "pq" and "--force" not in sys.argv:', self.src)
        self.assertIn("REFUSING to apply for kind=pq", self.src)
        self.assertIn("pq_detail_coverage(conn)", self.src)

    def test_the_refusal_comes_after_the_dry_run_report(self):
        """The dry run must still show what WOULD happen; only the write
        is refused."""
        self.assertLess(self.src.index("dry run; re-run with --apply"),
                        self.src.index("REFUSING to apply for kind=pq"))

    def test_cleared_rows_are_counted_on_their_own_line(self):
        """Previously tagged rows that would lose everything were lumped in
        with untagged name-only captures, so the one number that can take
        a row off a 5CA sheet was invisible."""
        self.assertIn("previously tagged rows that would be CLEARED", self.src)


if __name__ == "__main__":
    unittest.main()
