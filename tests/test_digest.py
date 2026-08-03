"""Digest renderer tests (handoff section 8, digest-template.md)."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import board, digest


def live_row(bill_id, title, nkd, areas="2"):
    return board.BoardRow(bill_id, title, "s", "Commons", "2nd reading", nkd, "live", board.NEW, areas=areas)


def base_edition(**kw):
    e = digest.Edition(week_commencing="2026-08-03", number=1, mode="recess")
    e.board_rows = [live_row(4157, "TIA Bill", "2026-09-11")]
    for k, v in kw.items():
        setattr(e, k, v)
    return e


class RecessRenderTests(unittest.TestCase):
    def test_recess_renders_allowed_sections_only(self):
        e = base_edition(
            top_lines=[digest.Line(digest.recess_line({"Commons": "2026-09-01", "Lords": "2026-09-01"}), "NOTE")],
            deadlines=[{"type": "Consultation", "title": "A consultation",
                        "url": "https://x", "why": "", "deadline": "2026-09-18"}],
            mp_notes=[digest.Line("An MP note", "NOTE")],
        )
        md = digest.render(e)
        for present in ("## 1. Top lines", "## 9. Active bills board",
                        "## 5. Consultations and calls for evidence", "## 10. MP intelligence"):
            self.assertIn(present, md)
        for absent in ("## 2. Week ahead", "## 4. Votes", "## 5. Written questions",
                       "## 8. EDMs", "## 9. Devolved", "## 10. Statements",
                       "Return dates below", "**Return dates:**"):
            self.assertNotIn(absent, md)
        # The single top line carries recess + return dates + deadlines note.
        self.assertEqual(md.count("Both Houses return 2026-09-01"), 1)

    def test_recess_line_combines_or_splits_dates(self):
        self.assertEqual(
            digest.recess_line({"Commons": "2026-09-01", "Lords": "2026-09-01"}),
            "Recess: neither House sits this week. Both Houses return 2026-09-01. Deadlines still apply.")
        split = digest.recess_line({"Commons": "2026-09-01", "Lords": "2026-09-08"})
        self.assertIn("Commons returns 2026-09-01", split)
        self.assertIn("Lords returns 2026-09-08", split)
        self.assertIn(
            "Deadlines still apply",
            digest.recess_line({}))

    def test_board_always_renders_even_when_empty_elsewhere(self):
        md = digest.render(base_edition())
        self.assertIn("## 9. Active bills board", md)
        self.assertIn("bills/4157", md)

    def test_westminster_rows_use_bills_parliament_uk(self):
        md = digest.render(base_edition())
        self.assertIn("(https://bills.parliament.uk/bills/4157)", md)

    def test_holyrood_row_uses_its_own_url(self):
        url = "https://www.parliament.scot/bills-and-laws/bills/s6/some-bill"
        e = base_edition(board_rows=[board.BoardRow(
            -445, "A Scottish Bill", None, "Holyrood", "Stage 3", "-", "closed",
            board.FALLEN, closed_note="Fell on 2026-03-17 at Stage 3", areas="2", url=url)])
        md = digest.render(e)
        self.assertIn("({0})".format(url), md)
        self.assertNotIn("bills.parliament.uk/bills/-445", md)

    def test_no_em_dashes(self):
        e = base_edition(
            board_rows=[live_row(4157, "TIA Bill", "2026-09-11"),
                        board.BoardRow(3774, "Old TIA", "s", "Lords", "Committee", "-",
                                       "closed", board.FALLEN, closed_note="Fell", areas="2")],
            return_dates={"Commons": "2026-09-01"},
        )
        self.assertNotIn("—", digest.render(e))  # em dash


class ValidationTests(unittest.TestCase):
    def test_act_without_owner_refused(self):
        e = base_edition(top_lines=[digest.Line("Do this", "ACT")])
        with self.assertRaises(digest.DigestError):
            digest.render(e)

    def test_act_with_owner_renders(self):
        e = base_edition(top_lines=[digest.Line("Do this", "ACT", owner="Christopher")])
        self.assertIn("Owner: Christopher", digest.render(e))


class CapTests(unittest.TestCase):
    def test_top_lines_capped_at_five_demoting_notes_first(self):
        lines = ([digest.Line("act", "ACT", owner="C")]
                 + [digest.Line("note %d" % i, "NOTE") for i in range(6)]
                 + [digest.Line("watch", "WATCH")])
        e = base_edition(top_lines=lines)
        md = digest.render(e)
        # ACT and WATCH survive; only 3 of the 6 NOTEs fit within the cap of 5.
        self.assertIn("act", md)
        self.assertIn("watch", md)
        self.assertEqual(md.count("**[NOTE]** note"), 3)


class FooterTests(unittest.TestCase):
    def test_gaps_disclosed_in_footer(self):
        e = base_edition(gaps=[("pq", "PATHWAYS sweep failed after retries")])
        md = digest.render(e)
        self.assertIn("Coverage gaps this edition", md)
        self.assertIn("PATHWAYS sweep failed after retries", md)

    def test_no_gaps_message(self):
        self.assertIn("No coverage gaps", digest.render(base_edition()))


if __name__ == "__main__":
    unittest.main()
