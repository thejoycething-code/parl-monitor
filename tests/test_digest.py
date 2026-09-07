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
                       "## EDMs", "## Scotland, Wales and Northern Ireland", "## Statements",
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
    def test_top_lines_capped_at_six_demoting_low_scores_first(self):
        """The cap demotes by triage score now that tags are retired: a
        score-3 line must survive a crowd of score-1s. Six lines since
        2026-08-31 (Christopher: the RE Core Syllabus consultation must
        render the week the devolved fix landed; the Slack summary
        already quoted up to six)."""
        lines = ([digest.Line("campaign trigger", 3)]
                 + [digest.Line("background %d" % i, 1) for i in range(6)]
                 + [digest.Line("digest-worthy", 2)])
        e = base_edition(top_lines=lines)
        md = digest.render(e)
        self.assertIn("campaign trigger", md)
        self.assertIn("digest-worthy", md)
        self.assertEqual(md.count("- background"), 4)


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


class EditionNumberTests(unittest.TestCase):
    """The header number is 1 + editions BEFORE this week -- order-
    independent, so a re-render of week 3 says Edition 3 whether its own
    row exists yet or not. Bare COUNT(*) said 'Edition 1' in every file
    header (the hardcode) and drifted by call order (the Monday path);
    both published 2026 editions carry the wrong header as a result."""

    def _conn(self):
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE editions (week_commencing TEXT PRIMARY "
                     "KEY, generated_at TEXT, mode TEXT, path TEXT)")
        for w in ("2026-08-03", "2026-08-10", "2026-08-17"):
            conn.execute("INSERT INTO editions VALUES (?, '', 'recess', '')",
                         (w,))
        return conn

    def test_re_render_keeps_its_number(self):
        import run_monday
        self.assertEqual(run_monday.edition_number(self._conn(),
                                                   "2026-08-17"), 3)

    def test_a_new_week_advances(self):
        import run_monday
        conn = self._conn()
        self.assertEqual(run_monday.edition_number(conn, "2026-08-24"), 4)
        conn.execute("INSERT INTO editions VALUES ('2026-08-24', '', "
                     "'normal', '')")
        self.assertEqual(run_monday.edition_number(conn, "2026-08-24"), 4,
                         "inserting this week's own row must not inflate "
                         "the number")


class SectionWindowTests(unittest.TestCase):
    """Dated sections render only within a window before the edition's
    Monday (Christopher, 2026-08-23). Without one every scored item
    re-rendered in every edition forever -- the 17 Aug edition showed PQ
    answers from 28 July. Questions and statements get [Monday-7, Monday);
    EDMs get [Monday-60, Monday) because they gather signatures over
    weeks. A Monday-morning event rolls forward, never shows twice, and a
    dateless row cannot prove it is fresh."""

    def _store(self, feed, dates):
        import sqlite3
        from src import db as _db
        conn = _db.init_db(sqlite3.connect(":memory:"))
        conn.row_factory = sqlite3.Row
        for iid, when in dates:
            conn.execute(
                "INSERT INTO items (id, captured_at, source_feed, item_type, "
                "title, url, event_date, issue_areas, triage_score, extra) "
                "VALUES (?, '', ?, ?, ?, '', ?, '[7]', 2, ?)",
                (iid, feed, feed, iid, when,
                 '{{"member": "A Member", "heading": "{0}"}}'.format(iid)))
        return conn

    def _render(self, feed, dates):
        import run_weekly
        edition = digest.Edition(week_commencing="2026-08-17", number=3,
                                 mode="recess")
        run_weekly.sections_from_store(self._store(feed, dates), edition)
        return edition

    def test_pqs_render_the_preceding_week_only(self):
        e = self._render("pq", (("pq:old", "2026-07-28"),
                                ("pq:in-window", "2026-08-11"),
                                ("pq:window-edge-monday", "2026-08-17"),
                                ("pq:no-date", None)))
        self.assertEqual([r["heading"] for r in e.pq_rows],
                         ["pq:in-window"],
                         "28 July is stale, a Monday answer rolls forward, "
                         "and a dateless row cannot prove it is fresh")

    def test_statements_get_the_same_week(self):
        e = self._render("wms", (("wms:old", "2026-08-09"),
                                 ("wms:in-window", "2026-08-12"),
                                 ("wms:no-date", None)))
        self.assertEqual([l.text for l in e.statements], ["wms:in-window"])

    def test_edms_get_sixty_days(self):
        e = self._render("edm", (("edm:too-old", "2026-06-17"),
                                 ("edm:weeks-old-still-shown", "2026-07-01"),
                                 ("edm:fresh", "2026-08-12")))
        self.assertEqual([l.text for l in e.edms],
                         ["edm:weeks-old-still-shown", "edm:fresh"],
                         "an EDM gathering signatures stays on the monitor "
                         "for 60 days; 18 June has aged out")


class NormalModeFullRenderTests(unittest.TestCase):
    """The 31 Aug edition is the first NORMAL-mode render since the
    editorial loop retired (What's On confirmed live 2026-08-24: 96 chamber
    events that week). Recess mode has three weeks of production evidence;
    this pins the sitting-week assembly before it runs for real: every
    section present and ordered, no tags or owners anywhere, the EDM cap."""

    def _full_edition(self):
        e = digest.Edition(week_commencing="2026-08-31", number=5,
                           mode="normal")
        e.top_lines = [digest.Line("Both Houses return", 3)]
        e.week_ahead = [digest.Line("TIA Bill second reading approaches", 2,
                                    date="2026-09-11")]
        e.votes = [digest.Line("A division on our ground", 2,
                               url="https://votes.parliament.uk/x")]
        e.pq_rows = [{"member": "A Member", "party": "Con", "seat": "Seat",
                      "house": "Commons", "heading": "A question",
                      "department": "DfE", "url": "https://q/1",
                      "date": "2026-08-27", "tag": 2, "why": "",
                      "area": 6, "area_label": "Parental rights"}]
        e.deadlines = [{"type": "Consultation", "title": "A consultation",
                        "url": "https://c/1", "why": "",
                        "deadline": "2026-09-18"}]
        e.edms = [digest.Line("EDM %d" % i, 2) for i in range(7)]
        e.statements = [digest.Line("A written statement", 2)]
        e.board_rows = [live_row(4157, "TIA Bill", "2026-09-11")]
        e.mp_notes = [digest.Line("An MP note", 2)]
        return e

    def test_all_sitting_week_sections_render_in_order(self):
        md = digest.render(self._full_edition())
        order = ["## Top lines", "## Week ahead", "## Votes and amendments",
                 "## Written questions",
                 "## Consultations and calls for evidence",
                 "## EDMs and petitions", "## Statements and announcements",
                 "## Active bills board", "## Parliamentarians on our issues"]
        positions = [md.index(h) for h in order]
        self.assertEqual(positions, sorted(positions),
                         "sitting-week sections out of order")
        self.assertNotIn("| RECESS", md)

    def test_no_editorial_markup_survives_anywhere(self):
        md = digest.render(self._full_edition())
        for marker in ("[ACT]", "[WATCH]", "[NOTE]", "Owner:"):
            self.assertNotIn(marker, md)

    def test_edm_cap_holds(self):
        md = digest.render(self._full_edition())
        self.assertEqual(sum(1 for i in range(7) if "EDM %d" % i in md), 5,
                         "EDMs cap at 5 in the section")


class DevolvedSectionTests(unittest.TestCase):
    """Devolved matters in the published edition (Christopher, 2026-08-24).

    The watching-brief SEPARATION is unchanged: sp_*/sd_*/ni_* still never
    write items or mp_events. This section is a READ at render time, so a
    devolved tool still cannot inject anything into the Westminster flow --
    only the display changed.
    """

    PAYLOAD = {
        "consultations": [{"title": "Protections in the justice system",
                           "url": "https://c/1", "nation": "Scotland",
                           "closes": "2026-08-31 (7 days)"}],
        "bills": [{"title": "A Scottish Bill", "where": "Holyrood",
                   "stage": "Stage 3", "date": "2026-03-17"}],
        "divisions": [{"dated": "2026-03-17", "title": "Holyrood: a vote",
                       "result": "Defeated"}],
    }

    def test_absent_when_there_is_nothing(self):
        e = base_edition()
        e.devolved = {"consultations": [], "bills": [], "divisions": []}
        self.assertIsNone(digest.render_devolved(e))
        self.assertNotIn("## Scotland, Wales and Northern Ireland", digest.render(e))

    def test_renders_at_the_very_bottom(self):
        e = base_edition(mp_notes=[digest.Line("An MP note", 2)])
        e.devolved = self.PAYLOAD
        md = digest.render(e)
        self.assertIn("## Scotland, Wales and Northern Ireland", md)
        self.assertGreater(md.index("## Scotland, Wales and Northern Ireland"),
                           md.index("## Parliamentarians on our issues"),
                           "Devolved belongs at the very bottom, after the "
                           "Westminster sections")

    def test_bottom_in_sitting_weeks_too(self):
        e = digest.Edition(week_commencing="2026-08-31", number=5,
                           mode="normal")
        e.board_rows = [live_row(4157, "TIA Bill", "2026-09-11")]
        e.statements = [digest.Line("A statement", 2)]
        e.devolved = self.PAYLOAD
        md = digest.render(e)
        self.assertGreater(md.index("## Scotland, Wales and Northern Ireland"),
                           md.index("## Statements and announcements"))

    def test_deadlines_lead(self):
        e = base_edition()
        e.devolved = self.PAYLOAD
        out = digest.render_devolved(e)
        self.assertLess(out.index("Open government consultations"),
                        out.index("Bills on our ground"))
        self.assertIn("2026-08-31 (7 days)", out)


class DevolvedPayloadTests(unittest.TestCase):
    def test_a_stage_name_is_not_liveness(self):
        """sp_bills still says 'Stage 3' for bills that passed in 2011 and
        2014. Only a bill whose stage MOVED inside the last year is current
        business -- the first build of this surfaced a 2010 palliative care
        bill as though it were live."""
        import sqlite3
        import run_weekly
        from src import db as _db
        conn = _db.init_db(sqlite3.connect(":memory:"))
        conn.row_factory = sqlite3.Row
        for title, stage, dated in (("Old passed bill", "Stage 3", "2014-02-04"),
                                    ("Current bill", "Stage 3", "2026-03-17")):
            conn.execute(
                "INSERT INTO sp_bills (bill_id, reference, name, person_id, "
                "latest_stage, latest_stage_date, areas, first_seen, "
                "last_seen) VALUES (?,?,?,?,?,?,?,?,?)",
                (title, "SP", title, "1", stage, dated, '[2]', "", ""))
        out = run_weekly.devolved_from_store(conn, "2026-08-24")
        self.assertEqual([b["title"] for b in out["bills"]], ["Current bill"])


class FurtherAfieldTests(unittest.TestCase):
    """Week ahead answers 'what happens now'; Further afield answers 'what is
    coming while there is still time to act' (Christopher, 2026-08-24). It is
    a sub-block of Week ahead, not a competing heading."""

    def _edition(self):
        e = digest.Edition(week_commencing="2026-08-31", number=5,
                           mode="normal")
        e.board_rows = [live_row(4157, "TIA Bill", "2026-09-11")]
        e.week_ahead = [digest.Line("Commons: this week", 2,
                                    date="2026-09-02")]
        e.further_ahead = [digest.Line("Commons: three weeks out", 2,
                                       date="2026-09-18"),
                           digest.Line("Lords: a fortnight out", 2,
                                       date="2026-09-11")]
        return e

    def test_it_sits_inside_week_ahead_not_as_its_own_heading(self):
        md = digest.render(self._edition())
        self.assertIn("## Week ahead", md)
        self.assertIn("**Further afield** (next 8 weeks)", md)
        self.assertNotIn("## Further afield", md)
        self.assertLess(md.index("Commons: this week"),
                        md.index("Further afield"))

    def test_dates_ascend_and_match_the_week_ahead_format(self):
        """Since 2026-09-07 both blocks are the same five-column table and
        dates print as a reader writes them, not as ISO."""
        out = digest.render_further_ahead(self._edition().further_ahead)
        self.assertLess(out.index("Fri 11 Sep"), out.index("Fri 18 Sep"))
        self.assertIn("| When | What | Where | Why it matters | Sources |", out)
        self.assertNotIn("2026-09-11", out)

    def test_nothing_further_means_no_block(self):
        self.assertIsNone(digest.render_further_ahead([]))

    def test_week_ahead_empty_but_further_populated_still_renders(self):
        """A recess-edge week can have nothing in the week itself and plenty
        coming: the section must not vanish and take the forward view with
        it."""
        e = self._edition()
        e.week_ahead = []
        md = digest.render(e)
        self.assertIn("## Week ahead", md)
        self.assertIn("Further afield", md)
        self.assertIn("Nothing on our ground in the chamber this week", md)


class WeekAheadTableTests(unittest.TestCase):
    """Christopher, 2026-09-07: "Go for pick C. With that option keep the
    why it matters but remove the score." Option C is a table: When, What,
    Where, Why it matters, Sources. Before it every line was the judge's
    why-line alone -- no time, no venue, no petition or Bill named, no
    link -- and every event printed twice."""

    SURROGACY = {"event_id": 56333, "start_time": "16:30", "end_time": "18:00",
                 "house": "Commons", "type": "Westminster Hall",
                 "description": "e-petition 763161 relating to surrogacy law and legal parenthood",
                 "members": ["Dave Robertson"], "bill_id": None,
                 "title": "4.30pm, Commons Westminster Hall debate. e-petition 763161 ..."}

    def _line(self, why="Could shape law legitimising commercial surrogacy.", **over):
        ev = dict(self.SURROGACY, **over)
        return digest.Line(why, 3, date="2026-09-07", event=ev,
                           url="https://whatson.parliament.uk/event/cal56333")

    def test_one_row_carries_when_what_where_why_and_sources(self):
        out = digest.render_week_ahead([self._line()], "2026-09-07")
        self.assertIn("| Mon 7 Sep \u00b7 4.30\u20136.00pm | **e-petition 763161 relating to "
                      "surrogacy law and legal parenthood \u2014 led by Dave Robertson** "
                      "| Commons, Westminster Hall | Could shape law legitimising "
                      "commercial surrogacy. | [petition](https://petition.parliament.uk"
                      "/petitions/763161) \u00b7 [What's On](https://whatson.parliament.uk"
                      "/event/cal56333) |", out)

    def test_the_score_badge_is_gone(self):
        """The why-line stays; the 1/2/3 in front of it does not."""
        out = digest.render_week_ahead([self._line()], "2026-09-07")
        self.assertNotIn("| 3 ", out)
        self.assertNotIn("**3**", out)
        self.assertNotIn("(3)", out)

    def test_the_same_event_judged_twice_prints_once(self):
        """THE BUG. Items were keyed on a per-process string hash, so two
        Sunday pulls stored one debate twice and the judge wrote two
        why-lines for it. The first is kept."""
        out = digest.render_week_ahead(
            [self._line(), self._line(why="A second verdict on the same debate.")],
            "2026-09-07")
        self.assertEqual(out.count("763161"), 2)  # once in What, once in the petition link
        self.assertNotIn("A second verdict", out)

    def test_last_week_is_not_ahead(self):
        """Friday 4 September sat under 'Week ahead' on Monday 7 September.
        It belongs with the votes."""
        stale = digest.Line("Old business", 2, date="2026-09-04",
                            event=dict(self.SURROGACY, event_id=1, description="Old business"))
        out = digest.render_week_ahead([stale, self._line()], "2026-09-07")
        self.assertNotIn("Old business", out)
        self.assertIn("Mon 7 Sep", out)

    def test_a_sequenced_item_says_so_and_a_bill_links_to_its_page(self):
        ev = dict(self.SURROGACY, event_id=55683, start_time="", end_time="",
                  description="Terminally Ill Adults (End of Life) Bill: Second Reading",
                  house="Commons", type="Main Chamber", bill_id=4157,
                  members=["Lauren Edwards"])
        line = digest.Line("The decisive Commons moment.", 3, date="2026-09-11",
                           event=ev, url="https://whatson.parliament.uk/event/cal55683")
        out = digest.render_week_ahead([line], "2026-09-07")
        self.assertIn("| Fri 11 Sep \u00b7 after other business |", out)
        self.assertIn("[Bill](https://bills.parliament.uk/bills/4157)", out)
        self.assertIn("led by Lauren Edwards", out)

    def test_rows_stored_before_the_change_still_make_a_row(self):
        """The store already holds this week's events with only the diary
        label; the table must degrade to the same shape from that label."""
        line = digest.Line("Watch for chilling effects on speech.", 3, date="2026-09-07",
                           event={"title": "6.00pm, Commons Westminster Hall debate. "
                                           "e-petition 746640 relating to misogyny"})
        out = digest.render_week_ahead([line], "2026-09-07")
        self.assertIn("| Mon 7 Sep \u00b7 6.00pm | **e-petition 746640 relating to misogyny** "
                      "| Commons Westminster Hall debate | Watch for chilling effects on speech. "
                      "| [petition](https://petition.parliament.uk/petitions/746640) |", out)

    def test_an_empty_diary_renders_nothing(self):
        self.assertIsNone(digest.render_week_ahead([], "2026-09-07"))

    def test_a_bill_without_a_billid_is_linked_through_the_board(self):
        """What's On leaves BillId empty on Private Members' Bill entries;
        the board knows the Bill by title."""
        line = digest.Line("Decisive.", 3, date="2026-09-11",
                           event={"title": "9.30am, Commons Private Members' Bills. "
                                           "Terminally Ill Adults (End of Life) Bill: Second Reading"})
        out = digest.render_week_ahead([line], "2026-09-07",
                                       bill_ids={"Terminally Ill Adults (End of Life) Bill": 4157})
        self.assertIn("[Bill](https://bills.parliament.uk/bills/4157)", out)

    def test_rows_within_a_day_run_by_the_clock(self):
        """Legacy rows carry the clock only in the label; 4.30pm still
        precedes 6.00pm and sequenced business comes last."""
        mk = lambda label: digest.Line("why", 2, date="2026-09-07", event={"title": label})
        out = digest.render_week_ahead([mk("6.00pm, Commons WH. Second"),
                                        mk("after other business, Commons Main. Third"),
                                        mk("4.30pm, Commons WH. First")], "2026-09-07")
        self.assertLess(out.index("First"), out.index("Second"))
        self.assertLess(out.index("Second"), out.index("Third"))
