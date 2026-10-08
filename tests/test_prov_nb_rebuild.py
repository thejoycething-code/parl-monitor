"""New Brunswick Hansards cut off inside their closing cross-reference table
(9 October 2026, Christopher: "Yes to both"). legnb.ca serves dozens of them;
the objects before the table are intact, so prov_fetch.rebuild_cut_xref
rebuilds the table, and prov_nb_hansard takes the result only when its last
page reaches the adjournment. A record cut short in its TEXT stays a gap."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.ingest import prov_nb_hansard as h  # noqa: E402
from src.prov_fetch import Unreadable, rebuild_cut_xref  # noqa: E402


def pdf(last_line, free_entries=400):
    """A two-page PDF whose closing xref carries many free entries, as
    legnb.ca's do, so it can be cut inside that table."""
    pages = [b"Madam Speaker: Good afternoon.", last_line.encode()]
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>"]
    for i, text in enumerate(pages):
        page_no, content_no = 3 + 2 * i, 4 + 2 * i
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents %d 0 R "
                    b"/Resources << /Font << /F1 7 0 R >> >> >>" % content_no)
        stream = b"BT /F1 12 Tf 72 720 Td (" + text + b") Tj ET"
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out, offsets = b"%PDF-1.7\n", []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % n + body + b"\nendobj\n"
    xref = b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1 + free_entries)
    xref += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    xref += b"0000000000 65535 f \n" * free_entries
    return out, out + xref + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objs) + 1 + free_entries, len(out))


class RebuildTests(unittest.TestCase):
    def test_a_file_cut_inside_its_table_reads_to_the_adjournment(self):
        body, whole = pdf("(The House adjourned at 6 p.m.)")
        cut = whole[:len(body) + 2000]                   # inside the free entries
        self.assertNotIn(b"%%EOF", cut[-2048:])
        self.assertIsNotNone(rebuild_cut_xref(cut))
        text = " ".join(f[3] for f in h.fragments(cut))
        self.assertIn("adjourned", text)

    def test_a_rebuilt_file_that_stops_before_the_adjournment_stays_a_gap(self):
        body, whole = pdf("Mr. Speaker: I move the debate be adjourned to Tuesday next.")
        # "adjourned" alone is not the close: the House itself must adjourn.
        with self.assertRaises(Unreadable) as ctx:
            h.fragments(whole[:len(body) + 2000])
        self.assertIn("does not reach the adjournment", str(ctx.exception))

    def test_a_file_cut_inside_its_text_is_not_rebuilt(self):
        body, _ = pdf("(The House adjourned at 6 p.m.)")
        self.assertIsNone(rebuild_cut_xref(body[:len(body) // 2]))
        with self.assertRaises(Unreadable):
            h.fragments(body[:len(body) // 2])

    def test_a_whole_file_is_left_alone(self):
        _, whole = pdf("(The House adjourned at 6 p.m.)")
        self.assertIsNone(rebuild_cut_xref(whole))

    def test_the_french_close_counts(self):
        self.assertTrue(h.ADJOURNED.search("(La séance est levée à 18 h.)"))
        self.assertTrue(h.ADJOURNED.search("the House is now adjourned."))


if __name__ == "__main__":
    unittest.main()
