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
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, members
from src.ingest import pqs, edms, sis, divisions, whatson, consultations, wms, legislation

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


class DivisionTests(unittest.TestCase):
    def test_division_51_369_102_and_entity_match(self):  # acceptance 9.7
        rows = divisions.parse_commons_response(load_json("division_commons-2026-07-08"))
        by_number = {d.number: d for d in rows}
        d51 = by_number[51]
        self.assertEqual((d51.aye_count, d51.no_count), (369, 102))
        # Entity match, not keyword (handoff 4.6).
        matched = divisions.matches_watchlist(d51.title, ["Children's Wellbeing and Schools"])
        self.assertEqual(matched, ["Children's Wellbeing and Schools"])


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
