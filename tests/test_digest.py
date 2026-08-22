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
        for present in ("## Top lines", "## Active bills board",
                        "## Consultations and calls for evidence", "## Parliamentarians on our issues"):
            self.assertIn(present, md)
        for absent in ("## Week ahead", "## Votes", "## Written questions",
                       "## EDMs", "## Devolved", "## Statements",
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
        self.assertIn("## Active bills board", md)
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


class PqSectionTests(unittest.TestCase):
    """Christopher, 2026-08-05: group by topic, repeat the header on every
    table, link out for the rest, cap nothing."""

    def _edition(self):
        ed = digest.Edition(week_commencing="2026-08-10", number=3, mode="normal")
        ed.pq_rows = [
            {"member": "Lord Jackson of Peterborough", "party": "Con", "seat": "peer",
             "house": "Lords", "heading": "Islamophobia Definition Working Group",
             "department": "Home Office", "url": "https://q/1", "date": "2026-07-31",
             "tag": "WATCH", "why": "Cross-House pressure building",
             "area": 7, "area_label": "Free speech online safety"},
            {"member": "Baroness Owen of Alderley Edge", "party": "Con", "seat": "peer",
             "house": "Lords", "heading": "Internet: Compensation",
             "department": "DSIT", "url": "https://q/2", "date": "2026-07-30",
             "tag": "NOTE", "why": "", "area": 7,
             "area_label": "Free speech online safety"},
            {"member": "Lord Cameron of Lochiel", "party": "Con", "seat": "peer",
             "house": "Lords", "heading": "Deportation", "department": "Home Office",
             "url": "https://q/3", "date": "2026-08-03", "tag": "NOTE", "why": "",
             "area": 11, "area_label": "Migration"},
        ]
        return ed

    def test_one_table_per_area_each_with_its_own_header(self):
        out = digest.render_pqs(self._edition())
        self.assertEqual(out.count("| Member | Question | Asked of | Answered |"), 2)
        self.assertIn("**Free speech online safety** (2)", out)
        self.assertIn("**Migration** (1)", out)

    def test_biggest_group_leads_and_rows_carry_member_and_department(self):
        out = digest.render_pqs(self._edition())
        self.assertLess(out.index("Free speech"), out.index("Migration"))
        self.assertIn("Lord Jackson of Peterborough (Con, peer)", out)
        self.assertIn("| Home Office |", out)
        self.assertIn("[Islamophobia Definition Working Group](https://q/1)", out)
        self.assertIn("31 Jul", out)

    def test_total_declared_and_companion_page_linked(self):
        out = digest.render_pqs(self._edition())
        self.assertIn("3 questions matched our areas this week", out)
        self.assertIn("questions.html", out)

    def test_nothing_is_capped(self):
        ed = self._edition()
        ed.pq_rows = ed.pq_rows * 20          # 60 questions
        out = digest.render_pqs(ed)
        self.assertEqual(out.count("https://q/1"), 20)

    def test_no_rows_no_section(self):
        ed = digest.Edition(week_commencing="2026-08-10", number=3, mode="normal")
        self.assertIsNone(digest.render_pqs(ed))


class ValidationTests(unittest.TestCase):
    def test_no_line_carries_editorial_markup(self):
        """The editorial loop is retired (Christopher, 2026-08-21): no
        [ACT]/[WATCH]/[NOTE] brackets, no owners, no refusal. He creates
        Asana tasks himself from what the monitor surfaces."""
        e = base_edition(top_lines=[digest.Line("Do this", 3,
                                                owner="Christopher")])
        md = digest.render(e)
        self.assertIn("- Do this", md)
        self.assertNotIn("[ACT]", md)
        self.assertNotIn("Owner:", md)

    def test_validate_never_refuses(self):
        e = base_edition(top_lines=[digest.Line("Do this", 3)])
        self.assertIsNone(digest.validate(e))


class CapTests(unittest.TestCase):
    def test_top_lines_capped_at_five_demoting_low_scores_first(self):
        """The cap demotes by triage score now that tags are retired: a
        score-3 line must survive a crowd of score-1s."""
        lines = ([digest.Line("campaign trigger", 3)]
                 + [digest.Line("background %d" % i, 1) for i in range(6)]
                 + [digest.Line("digest-worthy", 2)])
        e = base_edition(top_lines=lines)
        md = digest.render(e)
        self.assertIn("campaign trigger", md)
        self.assertIn("digest-worthy", md)
        self.assertEqual(md.count("- background"), 3)


class FooterVersionTests(unittest.TestCase):
    """The footer sat at v0.2 while the taxonomy was on v0.4, on a page
    partners read (found 2026-08-05). It is now read, never written."""

    def test_version_comes_from_the_edition(self):
        e = base_edition(taxonomy_version="0.4")
        self.assertIn("taxonomy v0.4", digest.render(e))

    def test_absent_version_omits_the_claim_entirely(self):
        md = digest.render(base_edition())
        self.assertIn("CitizenGO issue taxonomy with human review", md)
        self.assertNotIn("v0.2", md)


class FooterTests(unittest.TestCase):
    def test_gaps_disclosed_in_footer(self):
        e = base_edition(gaps=[("pq", "PATHWAYS sweep failed after retries")])
        md = digest.render(e)
        self.assertIn("Coverage gaps this edition", md)
        self.assertIn("PATHWAYS sweep failed after retries", md)

    def test_no_gaps_message(self):
        self.assertIn("No coverage gaps", digest.render(base_edition()))


class SiTableTests(unittest.TestCase):
    def test_si_table_names_instrument_procedure_and_status(self):
        e = base_edition(si_rows=[{
            "name": "CWSA (Establishment of Schools) Regulations 2026",
            "url": "https://statutoryinstruments.parliament.uk/instrument/G6pPGK1m",
            "why": "First implementing regulations.",
            "procedure": "Draft affirmative",
            "act": "Children's Wellbeing and Schools Act 2026",
            "status": "Laid 2026-05-20; Commons approved 2026-07-08; awaiting the Lords",
            "division": {"result": "369 to 102", "date": "2026-07-08",
                         "url": "https://votes.parliament.uk/Votes/Commons/Division/2402"},
            "text_link": "https://www.legislation.gov.uk/ukdsi/2026/9780348283426",
        }])
        md = digest.render(e)
        self.assertIn("| Instrument | Procedure | Status |", md)
        self.assertIn("[CWSA (Establishment of Schools) Regulations 2026](https://statutoryinstruments.parliament.uk/instrument/G6pPGK1m)", md)
        self.assertIn("Under the Children's Wellbeing and Schools Act 2026.", md)
        self.assertIn("| Draft affirmative |", md)
        self.assertIn("awaiting the Lords", md)
        self.assertIn("[Commons vote 369 to 102](https://votes.parliament.uk/Votes/Commons/Division/2402)", md)

class MpSectionTests(unittest.TestCase):
    """V1: one line per member, merged; votes ledgered but never listed."""

    def _ev(self, mid, name, kind, line, date="2026-08-01", party="Con", seat="Somewhere"):
        return {"member_id": mid, "name": name, "kind": kind, "line": line,
                "date": date, "party": party, "seat": seat, "house": "Commons", "ref": "x"}

    def test_one_line_per_member_with_merge_and_counts(self):
        events = [
            self._ev(1, "Lord Pearson of Rannoch", "debate", "Anti-Muslim hostility"),
            self._ev(1, "Lord Pearson of Rannoch", "debate", "Anti-Muslim hostility"),
            self._ev(2, "Lord Black of Brentwood", "debate", "Age assurance rollout"),
        ]
        lines = digest.mp_lines_from_events(events)
        self.assertEqual(len(lines), 2)
        self.assertIn("**Lord Pearson of Rannoch (Con, Somewhere)**: **DEBATE** Anti-Muslim hostility (x2)", lines[0])

    def test_votes_are_excluded_from_the_section(self):
        events = [self._ev(1, "A Member", "vote", "Voted No: TIA Bill")]
        self.assertEqual(digest.mp_lines_from_events(events), [])

    def test_cap_with_overflow_line(self):
        events = [self._ev(i, "Member %d" % i, "debate", "Q%d" % i) for i in range(15)]
        lines = digest.mp_lines_from_events(events, max_members=12)
        self.assertEqual(len(lines), 13)
        self.assertIn("...and 3 more members active this week", lines[-1])

    def test_unresolved_member_still_renders(self):
        events = [self._ev(999, None, "debate", "A question", party=None, seat=None)]
        lines = digest.mp_lines_from_events(events)
        self.assertIn("Member 999", lines[0])


if __name__ == "__main__":
    unittest.main()
