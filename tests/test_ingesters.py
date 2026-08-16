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
                        legislation, hansard, upr, ohchr_calls)

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
