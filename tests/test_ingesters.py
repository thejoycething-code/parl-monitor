"""Ingester tests against live-probed fixtures in data/raw/2026-08-01/.

Covers members, PQs, EDMs, SIs, divisions, What's On, consultations, WMS and
legislation. Acceptance-aligned assertions where the live data supports them
(SI laid date 9.7, division #51 9.7, SEND/EOTAS consultation 9.8, member
resolution 9.5, s.22 in force 9.3).
"""

import datetime
import gzip
import json
import os
import re
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, members
from src.ingest import (pqs, edms, sis, divisions, whatson, consultations, wms,
                        legislation, hansard, upr, ohchr_calls,
                        un_calendar)

RAW = os.path.join(ROOT, "data", "raw", "2026-08-01")


def load_json(slug):
    with gzip.open(os.path.join(RAW, slug + ".json.gz"), "rb") as h:
        return json.loads(h.read().decode("utf-8"))


def load_text(slug):
    with gzip.open(os.path.join(RAW, slug + ".json.gz"), "rb") as h:
        return h.read().decode("utf-8")


class MembersTests(unittest.TestCase):
    def test_resolves_snowden_to_fylde(self):  # acceptance 9.5
        m = members.parse_member(load_json("members_detail-5072").get("value"))
        self.assertEqual((m.id, m.name, m.party, m.seat), (5072, "Mr Andrew Snowden", "Conservative", "Fylde"))

    def test_cache_round_trip(self):
        conn = db.init_db(db.connect(":memory:"))
        try:
            m = members.parse_member(load_json("members_detail-5072").get("value"))
            self.assertIsNone(members.cache_get(conn, 5072))
            members.cache_put(conn, m)
            self.assertEqual(members.cache_get(conn, 5072).seat, "Fylde")
        finally:
            conn.close()


class PqTests(unittest.TestCase):
    def test_parses_and_stores_date_tabled(self):
        qs = pqs.parse_response(load_json("pq_search-pathways"))
        self.assertEqual(len(qs), 6)
        q = qs[0]
        self.assertTrue(q.uin and q.date_tabled)
        # Deep link needs dateTabled (handoff 4.2 / pilot gap 4).
        self.assertEqual(
            q.url,
            "https://questions-statements.parliament.uk/written-questions/detail/%s/%s"
            % (q.date_tabled.isoformat(), q.uin),
        )

    def test_since_filters_by_answer_date(self):
        qs = pqs.parse_response(load_json("pq_search-pathways"))
        recent = pqs.since(qs, datetime.date(2026, 7, 30))
        self.assertTrue(all(q.date_answered >= datetime.date(2026, 7, 30) for q in recent))
        self.assertLessEqual(len(recent), len(qs))


class EdmTests(unittest.TestCase):
    def test_parses_link_and_signature_count(self):
        rows = edms.parse_response(load_json("edm_search-assisted-dying"))
        self.assertTrue(rows)
        e = rows[0]
        self.assertEqual(e.url, "https://edm.parliament.uk/early-day-motion/%s" % e.id)
        self.assertIsNotNone(e.signature_count)

    def test_signature_delta_across_editions(self):
        conn = db.init_db(db.connect(":memory:"))
        try:
            e = edms.parse_response(load_json("edm_search-assisted-dying"))[0]
            edms.record_signatures(conn, e, "2026-07-27")
            bumped = edms.EDM(**{**e.__dict__, "signature_count": e.signature_count + 3})
            edms.record_signatures(conn, bumped, "2026-08-03")
            self.assertEqual(edms.signature_delta(conn, e.id, "2026-08-03", "2026-07-27"), 3)
        finally:
            conn.close()


class SiTests(unittest.TestCase):
    def test_cwsa_establishment_regs_laid_2026_05_20(self):  # acceptance 9.7
        rows = sis.parse_response(load_json("si_search-childrens-wellbeing"))
        self.assertTrue(rows)
        si = rows[0]
        self.assertIn("Establishment", si.name)
        self.assertEqual(si.laid_date, datetime.date(2026, 5, 20))


class SiDetailTests(unittest.TestCase):
    def test_detail_carries_text_link_enabling_act_and_tracker_url(self):
        si = sis.parse_si_detail(load_json("si_detail-G6pPGK1m"))
        self.assertEqual(si.text_link, "https://www.legislation.gov.uk/ukdsi/2026/9780348283426")
        self.assertEqual(si.enabling_acts, ["Children's Wellbeing and Schools Act 2026"])
        self.assertEqual(si.tracker_url,
                         "https://statutoryinstruments.parliament.uk/instrument/G6pPGK1m")


class SiStatusTests(unittest.TestCase):
    def test_draft_affirmative_journey(self):
        self.assertEqual(
            sis.status_line("Draft affirmative", "2026-05-20", "2026-07-08"),
            "Laid 2026-05-20; Commons approved 2026-07-08; awaiting the Lords")
        self.assertEqual(
            sis.status_line("Draft affirmative", "2026-05-20"),
            "Laid 2026-05-20; awaiting approval by both Houses")
        self.assertEqual(
            sis.status_line("Draft affirmative", "2026-05-20", "2026-07-08", "2026-09-01"),
            "Laid 2026-05-20; made 2026-09-01")

    def test_unknown_procedure_reports_facts_only(self):
        self.assertEqual(sis.status_line("Made negative", "2026-08-28"), "Laid 2026-08-28")
        self.assertEqual(sis.status_line(None), "status not yet recorded")


class DivisionTests(unittest.TestCase):
    def test_division_51_369_102_and_entity_match(self):  # acceptance 9.7
        rows = divisions.parse_commons_response(load_json("division_commons-2026-07-08"))
        by_number = {d.number: d for d in rows}
        d51 = by_number[51]
        self.assertEqual((d51.aye_count, d51.no_count), (369, 102))
        # Entity match, not keyword (handoff 4.6).
        matched = divisions.matches_watchlist(d51.title, ["Children's Wellbeing and Schools"])
        self.assertEqual(matched, ["Children's Wellbeing and Schools"])
        # Public page, never the JSON API endpoint.
        self.assertEqual(d51.url, "https://votes.parliament.uk/Votes/Commons/Division/2402")


class WhatsOnTests(unittest.TestCase):
    def test_empty_week_is_recess(self):  # acceptance 9.4
        events = whatson.parse_response(load_json("whatson_week-2026-08-03"))
        self.assertEqual(events, [])
        self.assertTrue(whatson.is_recess(events))

    def test_format_time_to_template_style(self):
        self.assertEqual(whatson.format_time("11:30"), "11.30am")
        self.assertEqual(whatson.format_time("09:30"), "9.30am")
        self.assertEqual(whatson.format_time("14:00"), "2.00pm")
        self.assertEqual(whatson.format_time("10:00 am"), "10.00am")

    def test_sequenced_business_has_no_time(self):
        # StartTime is '' (never null) for chamber business that runs in Order
        # Paper sequence; it must not be reported as a time still to be announced.
        self.assertIsNone(whatson.format_time(""))
        self.assertIsNone(whatson.format_time(None))

    def test_event_label_marks_sequenced_business(self):
        rows = load_json("whatson_range-2026-07-06-2026-07-12")
        events = whatson.parse_response(rows)
        tmr = [e for e in events if whatson._text(e.description) == "Mental capacity (duty to assess)"]
        self.assertEqual(len(tmr), 1)
        label = whatson.event_label(tmr[0])
        self.assertTrue(label.startswith("after other business, Commons Ten Minute Rule Motion."), label)
        self.assertNotIn("TBA", label)

    def test_event_label_uses_real_time_when_present(self):
        rows = load_json("whatson_range-2026-07-06-2026-07-12")
        timed = [e for e in whatson.parse_response(rows) if e.start_time == "11:30"]
        self.assertTrue(timed)
        self.assertTrue(whatson.event_label(timed[0]).startswith("11.30am, "))

    def test_event_label_collapses_double_spaces(self):
        rows = load_json("whatson_range-2026-07-06-2026-07-12")
        cwsa = [e for e in whatson.parse_response(rows)
                if "Establishment of Schools" in whatson._text(e.description)]
        self.assertTrue(cwsa)
        self.assertNotIn("  ", whatson.event_label(cwsa[0]))

    def test_range_chunked_to_four_weeks(self):
        chunks = whatson.date_chunks(datetime.date(2026, 8, 3), datetime.date(2026, 9, 13))
        self.assertGreaterEqual(len(chunks), 2)  # 6 weeks -> multiple chunks
        for start, end in chunks:
            self.assertLessEqual((end - start).days, 27)


class ConsultationTests(unittest.TestCase):
    def test_send_eotas_consultation_captured(self):  # acceptance 9.8
        rows = consultations.parse_response(load_json("consultation_govuk-open-200"))
        match = [c for c in rows if c.title == "SEND reform: education otherwise than at school"]
        self.assertEqual(len(match), 1)
        c = match[0]
        self.assertEqual(c.end_date, datetime.date(2026, 9, 18))
        self.assertTrue(c.url.startswith("https://www.gov.uk/"))


class WmsTests(unittest.TestCase):
    def test_parses_and_dedupes(self):
        rows = wms.parse_response(load_json("wms_from-2026-07-20"))
        self.assertTrue(rows)
        keys = [(s.title, s.made_when) for s in rows]
        self.assertEqual(len(keys), len(set(keys)))  # dedupe held


class LegislationTests(unittest.TestCase):
    def test_locates_abortion_section_by_title(self):  # acceptance 9.3
        entries = legislation.parse_contents(load_text("legislation_ukpga-2026-20-contents"))
        hits = legislation.locate_sections(entries, "Removal of women from the criminal law related to abortion")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].number, "241")

    def test_section_241_in_force_at_royal_assent(self):  # acceptance 9.3
        status = legislation.section_in_force(load_text("legislation_ukpga-2026-20-section-241"), "241")
        self.assertTrue(status.in_force)
        self.assertEqual(status.note, "in force at royal assent")

    def test_section_242_exists_in_contents(self):  # acceptance 9.3
        entries = legislation.parse_contents(load_text("legislation_ukpga-2026-20-contents"))
        self.assertTrue(any(e.number == "242" for e in entries))


if __name__ == "__main__":
    unittest.main()


class HansardSpokenFormTests(unittest.TestCase):
    """The sweep list is hyphenated for the Written Questions API; Hansard is
    a different API and the hyphens were costing hits (2026-08-17:
    "abortion-clinics" 0, "abortion clinics" 3)."""

    def test_hyphens_relax_to_spaces(self):
        self.assertEqual(hansard.spoken_form("abortion-clinics"), "abortion clinics")
        self.assertEqual(hansard.spoken_form("puberty-suppressing-hormones"),
                         "puberty suppressing hormones")

    def test_untouched_when_already_spoken(self):
        self.assertEqual(hansard.spoken_form("surrogacy"), "surrogacy")
        self.assertEqual(hansard.spoken_form("anti-Muslim hostility"),
                         "anti Muslim hostility")

    def test_exceptions_are_left_alone(self):
        with mock.patch.object(hansard, "NO_RELAX", frozenset({"single-sex"})):
            self.assertEqual(hansard.spoken_form("single-sex"), "single-sex")


class UprTests(unittest.TestCase):
    """UPR Info ingester, against fixtures probed live on 2026-08-16."""

    def setUp(self):
        self.page = load_json("upr_search-right-to-life-p0")
        self.recs = upr.parse_response(self.page)

    def test_parses_the_fields_that_make_a_recommendation_readable(self):
        r = self.recs[0]
        self.assertTrue(r.id)
        self.assertTrue(r.text)
        self.assertTrue(r.state_under_review)
        self.assertTrue(r.recommending_state)
        self.assertIn(r.response, ("Supported", "Noted", "Not Supported"))
        self.assertTrue(r.url.startswith("https://upr-info-database.uwazi.io/entity/"))

    def test_noted_and_not_supported_both_count_as_refused(self):
        """`response` has THREE values. Treating it as accepted/not would
        misfile one of them, and 'Noted' is the diplomatic form of refusal --
        the whole point of the dataset."""
        self.assertTrue(upr.Recommendation(id="1", text="", state_under_review="X",
                                           recommending_state="Y", response="Noted").refused)
        self.assertTrue(upr.Recommendation(id="2", text="", state_under_review="X",
                                           recommending_state="Y", response="Not Supported").refused)
        self.assertFalse(upr.Recommendation(id="3", text="", state_under_review="X",
                                            recommending_state="Y", response="Supported").refused)

    def test_issues_are_multivalued_and_include_off_topic_tags(self):
        """The UN's "Right to life" is largely DEATH PENALTY work. The issue
        filter narrows the field; the taxonomy still decides relevance."""
        all_issues = {i for r in self.recs for i in r.issues}
        self.assertIn("Right to life", all_issues)
        self.assertTrue(any(len(r.issues) > 1 for r in self.recs),
                        "issues is a multi-value field")

    def test_by_state_tallies_support_against_refusal(self):
        tally = upr.by_state(self.recs)
        self.assertTrue(tally)
        for state, row in tally.items():
            self.assertEqual(row["supported"] + row["refused"],
                             sum(1 for r in self.recs if r.state_under_review == state))

    def test_thesaurus_ids_are_full_uuids(self):
        """An abbreviated id returns totalRows=0 with HTTP 200 -- a silent
        empty result that reads as "nobody raised this issue" (observed while
        building this, 2026-08-16)."""
        class FakeClient:
            def get_json(self, url, feed, slug):
                return load_json("upr_thesauri")
        ids = upr.fetch_issue_ids(FakeClient())
        self.assertIn("Right to life", ids)
        self.assertEqual(len(ids["Right to life"]), 36, "must be a full UUID")


class UprHarvestTests(unittest.TestCase):
    """Harvest mechanics: quoting, and refusing to guess."""

    def test_needs_an_issue_or_a_term(self):
        with self.assertRaises(ValueError):
            upr.fetch_recommendations(None)

    def test_search_term_is_passed_through_quoted(self):
        """Quoting is load-bearing: unquoted "sexuality education" returns
        10,000 rows (the whole database), quoted returns 228."""
        seen = {}

        class FakeClient:
            def get_json(self, url, feed, slug):
                seen["url"] = url
                return {"rows": [], "totalRows": 0}

        upr.fetch_recommendations(FakeClient(), search_term='"sexuality education"')
        self.assertIn("searchTerm=", seen["url"])
        self.assertIn("%22sexuality+education%22", seen["url"])
        self.assertNotIn("filters=", seen["url"])


class OhchrCallsTests(unittest.TestCase):
    """OHCHR calls for input, against a fixture captured live 2026-08-17."""

    def setUp(self):
        self.calls = ohchr_calls.parse_calls(load_text("ohchr_calls-for-input"))

    def test_parses_every_call_on_the_page(self):
        """15 call links on the page, 15 parsed. A deadline feed that quietly
        drops rows is worse than none: the missing one is the closed door."""
        html = load_text("ohchr_calls-for-input")
        links = set(re.findall(r'href="(/en/calls-for-input/[^"#?]+)"', html))
        parsed = {c.url.replace(ohchr_calls.BASE, "") for c in self.calls}
        self.assertEqual(len(parsed), len(links))
        self.assertFalse(links - parsed)

    def test_reads_deadlines_and_sorts_by_them(self):
        self.assertTrue(self.calls)
        for call in self.calls:
            self.assertIsInstance(call.deadline, datetime.date)
        self.assertEqual(self.calls, sorted(self.calls, key=lambda c: c.deadline))

    def test_open_calls_respects_a_horizon(self):
        day = datetime.date(2026, 8, 17)
        self.assertGreater(len(ohchr_calls.open_calls(self.calls, today=day)),
                           len(ohchr_calls.open_calls(self.calls, today=day, horizon_days=30)))

    def test_titles_come_from_the_url_slug(self):
        """The slug survives layout changes; the visible title markup has not."""
        titles = [c.title for c in self.calls]
        self.assertTrue(any("Child rights" in t for t in titles))
        self.assertFalse(any("<" in t for t in titles), "no markup should leak in")


class UnCalendarTests(unittest.TestCase):
    """HRC session calendar, fixture captured live 2026-08-17."""

    def setUp(self):
        self.sessions = un_calendar.parse_hrc_sessions(load_text("uncal_hrc-sessions"))

    def test_parses_sessions_with_date_ranges(self):
        self.assertTrue(self.sessions)
        s63 = next(s for s in self.sessions if s.number == 63)
        self.assertEqual(s63.starts, datetime.date(2026, 9, 7))
        self.assertEqual(s63.ends, datetime.date(2026, 10, 9))

    def test_ordinals_are_right(self):
        """"63th session" is how the first version read."""
        self.assertIn("63rd session", next(s for s in self.sessions if s.number == 63).name)
        self.assertEqual(un_calendar._ordinal_suffix(61), "st")
        self.assertEqual(un_calendar._ordinal_suffix(62), "nd")
        self.assertEqual(un_calendar._ordinal_suffix(12), "th")

    def test_past_sessions_are_returned_not_dropped(self):
        """Keeping them is what lets 'nothing announced yet' be told apart
        from 'the page changed and nothing parsed'."""
        self.assertTrue([s for s in self.sessions if s.ends < datetime.date(2026, 1, 1)])

    def test_a_session_under_way_counts_as_upcoming(self):
        mid = datetime.date(2026, 9, 20)          # inside the 63rd
        live = un_calendar.upcoming(self.sessions, today=mid)
        self.assertIn(63, [s.number for s in live])
        self.assertTrue(next(s for s in live if s.number == 63).starts <= mid)


class TreatyDeadlineTests(unittest.TestCase):
    """Treaty body reporting deadlines, fixture captured live 2026-08-17."""

    def setUp(self):
        self.rows = un_calendar.parse_treaty_deadlines(load_text("uncal_tb-calendar"))

    def test_parses_country_treaty_and_due_date(self):
        self.assertTrue(self.rows)
        row = self.rows[0]
        self.assertTrue(row.country and row.treaty)
        self.assertIsInstance(row.due, datetime.date)
        self.assertEqual(self.rows, sorted(self.rows, key=lambda r: r.due))

    def test_undated_and_headerless_rows_are_skipped(self):
        """A row with no due date would sit in a deadline feed forever."""
        for row in self.rows:
            self.assertIsNotNone(row.due)
            self.assertNotIn(row.country, ("", "&nbsp;"))

    def test_only_our_committees_are_flagged(self):
        """CRPD was flagged at first and dropped: its calendar is dominated by
        general disability reporting, and it supplied most of the hits."""
        self.assertTrue(any(r.treaty == "CEDAW" for r in self.rows))
        for row in self.rows:
            if row.treaty in ("CAT", "CERD", "CED", "CRPD"):
                self.assertFalse(row.ours, "%s should not be flagged" % row.treaty)
            if row.treaty in ("CEDAW", "CRC", "CCPR"):
                self.assertTrue(row.ours)


class CswAndGaTests(unittest.TestCase):
    """CSW and General Assembly session windows, fixtures 2026-08-17."""

    def test_csw_range_is_written_in_prose(self):
        """"from 8 to 19 March 2027" -- the first version matched only
        dashes and silently found nothing."""
        s = un_calendar.parse_csw_range(load_text("uncal_csw-71"), 71)
        self.assertIsNotNone(s)
        self.assertEqual((s.starts, s.ends),
                         (datetime.date(2027, 3, 8), datetime.date(2027, 3, 19)))
        self.assertIn("71st session", s.name)

    def test_csw_returns_none_rather_than_guessing(self):
        self.assertIsNone(un_calendar.parse_csw_range("<p>no dates here</p>", 99))

    def test_ga_session_window(self):
        ga = un_calendar.parse_ga_session(load_text("uncal_ga-81"), 81)
        self.assertIsNotNone(ga)
        self.assertEqual(ga.starts, datetime.date(2026, 9, 8))
        self.assertEqual(ga.ends, datetime.date(2027, 9, 7))

    def test_ga_session_number_is_derived_from_the_year(self):
        """Session N opens in September of year N + 1945; hardcoding it would
        rot every September."""
        self.assertEqual(2026 - un_calendar.GA_EPOCH, 81)
        self.assertEqual(2027 - un_calendar.GA_EPOCH, 82)


class UprSessionTests(unittest.TestCase):
    """UPR working group sessions, from UPR Info (fixture 2026-08-17).

    OHCHR's own UPR pages sit behind a Cloudflare bot challenge, so the
    schedule is taken from UPR Info instead -- routed around, not defeated.
    """

    def setUp(self):
        self.sessions = un_calendar.parse_upr_sessions(load_text("uncal_upr-sessions"))

    def test_parses_the_published_schedule(self):
        self.assertGreater(len(self.sessions), 50)
        s53 = next(s for s in self.sessions if s.number == 53)
        self.assertEqual((s53.starts.year, s53.starts.month), (2026, 11))

    def test_month_precision_is_declared_not_faked(self):
        """The source publishes "Session 53 - November 2026" and no day, so
        nothing downstream may print one."""
        s53 = next(s for s in self.sessions if s.number == 53)
        self.assertTrue(s53.approximate)
        self.assertEqual(s53.when, "November 2026")
        self.assertNotIn("2026-11-01", s53.when)

    def test_month_end_is_the_last_day_not_the_28th(self):
        for s in self.sessions:
            nxt = s.ends + datetime.timedelta(days=1)
            self.assertEqual(nxt.day, 1, "ends should be the last day of its month")

    def test_precise_sessions_still_render_a_range(self):
        hrc = un_calendar.parse_hrc_sessions(load_text("uncal_hrc-sessions"))
        s63 = next(s for s in hrc if s.number == 63)
        self.assertFalse(s63.approximate)
        self.assertIn(" to ", s63.when)


class JournalMeetingTests(unittest.TestCase):
    """UN Journal GlobalCalendar: the Third Committee's item-level schedule.

    Found by reading the Journal web app rather than guessing: its runtime
    config names the API base and the bundle names the endpoints. The POST
    needs ISO DATETIMES -- plain dates return 400 "Incorrect parameters".
    """

    # Shaped like the real payload: an OFFICIAL committee meeting is filed
    # under organ "General Assembly" with the committee only in
    # relatedOrganizations, while the rows whose organ IS the committee are
    # its informal notices.
    PAYLOAD = [{"group": "official", "organGroup": [{"organ": "General Assembly",
                "meetings": [
                    {"title": "<p>5th plenary meeting</p>", "type": "Official",
                     "primaryOrgan": "General Assembly",
                     "relatedOrganizations": [{"value": "Third Committee"}],
                     "startDate": "2025-10-07T10:00:00"},
                    {"title": "1st plenary meeting", "type": "Official",
                     "primaryOrgan": "General Assembly",
                     "relatedOrganizations": [{"value": "Fourth Committee"}],
                     "startDate": "2025-10-07T15:00:00"},
                ]}]}]

    def test_official_meetings_are_found_via_related_organizations(self):
        """Filtering on organ alone kept 36 informal notices and dropped all
        55 official meetings -- backwards, since the official ones matter."""
        got = un_calendar.parse_journal_meetings(self.PAYLOAD, organ_filter="Third")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].kind, "Official")
        self.assertNotIn("<p>", got[0].title)

    def test_the_committee_is_displayed_not_its_parent(self):
        """The row says organ "General Assembly"; showing that would mislead."""
        got = un_calendar.parse_journal_meetings(self.PAYLOAD, organ_filter="Third")
        self.assertEqual(got[0].organ, "Third Committee")

    def test_keeps_time_of_day(self):
        got = un_calendar.parse_journal_meetings(self.PAYLOAD, organ_filter="Third")
        self.assertEqual(got[0].starts, datetime.datetime(2025, 10, 7, 10, 0))

    def test_unparseable_dates_are_skipped(self):
        bad = [{"organGroup": [{"organ": "Third Committee",
                "meetings": [{"title": "x", "startDate": "not-a-date"}]}]}]
        self.assertEqual(un_calendar.parse_journal_meetings(bad), [])

    def test_out_of_range_is_a_horizon_not_an_error(self):
        """A 400 means the range reaches past the last published Journal
        issue, which is a limit to report rather than a fault to raise."""
        class Failing:
            def post_json(self, *a, **k):
                raise RuntimeError("HTTP 400: Incorrect parameters")
        rows, why = un_calendar.fetch_journal_meetings(Failing(), days=400)
        self.assertEqual(rows, [])
        self.assertIn("near-term", why)


class HansardArchiveSlugTests(unittest.TestCase):
    """The archive filename must state the range that was actually searched.

    The weekly asks Hansard for ONE WEEK (week_start..week_end), but the slug
    used to record only start[:4]. A file called
    "hansard_search-digital-id-2026-s0.json.gz" reads as a whole-year search,
    and that is how 44 legitimate recess zeroes were misread as a broken sweep
    on 2026-08-20. Probing confirmed the sweep was fine: "assisted dying"
    returns 0 for 2026-08-24..30 and 47 for June 2026.
    """

    class _Client:
        def __init__(self):
            self.slugs = []

        def get_json(self, url, feed, slug):
            self.slugs.append(slug)
            return {"Results": []}

    def test_slug_carries_the_whole_range(self):
        client = self._Client()
        hansard.search_contributions(client, "digital ID",
                                     "2026-08-24", "2026-08-30")
        self.assertEqual(client.slugs,
                         ["search-digital ID-2026-08-24-to-2026-08-30-s0"])

    def test_two_weeks_in_one_year_do_not_share_a_slug(self):
        client = self._Client()
        hansard.search_contributions(client, "digital ID",
                                     "2026-08-17", "2026-08-23")
        hansard.search_contributions(client, "digital ID",
                                     "2026-08-24", "2026-08-30")
        self.assertEqual(len(set(client.slugs)), 2)


class HansardSweepTermsTests(unittest.TestCase):
    """The spoken sweep reused the PQ list and so never searched for 'abortion':
    37 of 38 abortion speeches on 9 July 2019 never reached the ledger (2026-09-08)."""

    def test_pq_terms_relaxed_then_extras_without_repeats(self):
        terms = hansard.sweep_terms({"pq_sweep_terms": ["abortion-clinics", "assisted-dying", "surrogacy"],
                                     "hansard_extra_terms": ["abortion", "assisted dying", "Surrogacy", "marriage"]})
        self.assertEqual(terms, ["abortion clinics", "assisted dying", "surrogacy", "abortion", "marriage"])

    def test_missing_extras_is_just_the_pq_list(self):
        self.assertEqual(hansard.sweep_terms({"pq_sweep_terms": ["home-education"]}), ["home education"])
        self.assertEqual(hansard.sweep_terms({}), [])

    def test_live_settings_now_search_for_the_plain_words(self):
        import yaml
        settings = yaml.safe_load(open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8"))
        terms = hansard.sweep_terms(settings)
        for word in ("abortion", "assisted dying", "free speech", "marriage", "gender recognition"):
            self.assertIn(word, terms)
        self.assertEqual(len(terms), len({t.lower() for t in terms}))


class HansardSplitSearchTests(unittest.TestCase):
    """The Hansard search API answers 500 for some term-and-window pairs; halving the
    window finds the slices that work (2026-09-08: 'home education' 2019 failed for the
    year and for July, answered for January-March)."""

    def _client(self, bad_ranges):
        from src.http import FetchError
        calls = []

        class C:
            def get_json(self, url, feed, slug):
                import re as _re
                a, b = _re.search(r"startDate=([\d-]+)&queryParameters.endDate=([\d-]+)", url).groups()
                calls.append((a, b))
                for ba, bb in bad_ranges:
                    if a <= ba and bb <= b:          # any window containing a bad day fails
                        raise FetchError(url, feed, slug, 1, "HTTP Error 500")
                return {"Results": [{"ContributionExtId": "x-%s" % a, "MemberId": 1, "SittingDate": a + "T00:00:00",
                                     "ContributionText": "abortion", "DebateSection": "D", "DebateSectionExtId": "s"}]}
        return C(), calls

    def test_a_bad_week_costs_a_week_not_the_year(self):
        client, calls = self._client([("2019-07-09", "2019-07-09")])
        logs = []
        got, gaps = hansard.search_contributions_split(client, "home education", "2019-01-01", "2019-12-31", log=logs.append)
        self.assertEqual(len(gaps), 1)
        a, b = gaps[0]
        self.assertLessEqual((__import__("datetime").date.fromisoformat(b) - __import__("datetime").date.fromisoformat(a)).days, 7)
        self.assertTrue(any(l.startswith("[gap] 'home education'") for l in logs))
        self.assertGreater(len(got), 5)                      # the rest of the year still arrived
        self.assertLess(len(calls), 40)                      # bisection, not a day-by-day crawl

    def test_a_good_window_is_one_call(self):
        client, calls = self._client([])
        got, gaps = hansard.search_contributions_split(client, "abortion", "2019-01-01", "2019-12-31")
        self.assertEqual((len(got), gaps, len(calls)), (1, [], 1))
