"""Treaty body general comments: how a treaty gets reinterpreted."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.ingest import treaty_comments as tc

LISTING = """
<table>
<tr><th>Title</th><th>Document type</th><th>Treaty</th><th>COUNTRY</th></tr>
<tr><td>General recommendation No. 40 on equal and inclusive rep</td>
    <td>General Comment/recommendation</td><td>CEDAW</td><td>&nbsp;</td></tr>
<tr><td>Joint general recommendation No. 38 (2025) of the Co</td>
    <td>General Comment/recommendation</td><td>CERD</td><td>&nbsp;</td></tr>
<tr><td>Concluding observations on the report of Chad</td>
    <td>Concluding Observations</td><td>CRC</td><td>Chad</td></tr>
</table>
"""


class TreatyCommentTests(unittest.TestCase):
    def setUp(self):
        self.rows = tc.parse_general_comments(LISTING)

    def test_only_general_comments_are_kept(self):
        """Filtering on the document-type column means a reordered table
        yields nothing rather than nonsense."""
        self.assertEqual(len(self.rows), 2)
        self.assertNotIn("Chad", " ".join(r.title for r in self.rows))

    def test_number_and_year_are_read_from_the_title(self):
        cedaw = next(r for r in self.rows if r.treaty == "CEDAW")
        self.assertEqual(cedaw.symbol, "CEDAW/GC/40")
        cerd = next(r for r in self.rows if r.treaty == "CERD")
        self.assertEqual(cerd.year, "2025")

    def test_ours_is_decided_by_committee_not_by_being_a_comment(self):
        """The listing truncates titles, so keyword matching missed all ten
        real rows. CEDAW, CRC and CCPR are our ground by definition -- but
        CERD and CMW are not, and an earlier display marked every comment as
        ours."""
        self.assertTrue(next(r for r in self.rows if r.treaty == "CEDAW").ours)
        self.assertFalse(next(r for r in self.rows if r.treaty == "CERD").ours)

    def test_empty_parse_is_distinguishable_from_no_comments(self):
        self.assertEqual(tc.parse_general_comments("<table></table>"), [])
