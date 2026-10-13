"""GA plenaries and high-level meetings from the UN Journal (13 October 2026).

The monitor missed the 12 October 2026 plenary vote on the political
declaration on pandemic prevention, preparedness and response because only
the GA session window was read, never its plenaries.
"""

import datetime
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import filter as filt  # noqa: E402
from src.ingest import un_calendar  # noqa: E402
from tests.un_fixtures import fixture_json, fixture_text, un_filter  # noqa: E402


class GaPlenaryTests(unittest.TestCase):
    """Step 1: GA plenaries and high-level meetings from the Journal."""

    def setUp(self):
        self.meetings = un_calendar.parse_ga_plenaries(
            fixture_json("journal-ga-2026-10-01.json"))

    def test_plenaries_kept_consultations_dropped(self):
        titles = [m.title for m in self.meetings]
        self.assertIn("18th plenary meeting", titles)
        self.assertIn("19th plenary meeting", titles)
        self.assertFalse(any(t.lower().startswith("informal consultations") for t in titles),
                         "a mission's informal consultations carry no agenda")

    def test_the_12_october_plenary_is_listed_with_its_id(self):
        m = [m for m in self.meetings if m.title == "18th plenary meeting"][0]
        self.assertEqual(m.starts, datetime.datetime(2026, 10, 12, 10, 0))
        self.assertEqual(m.id, "f0bd129c-9251-4047-b00c-cccb49848b30")
        self.assertIn("/meeting/officials/f0bd129c", m.url)
        self.assertIn("2026-10-12", m.url)

    def test_agenda_names_the_draft_symbol(self):
        agenda, programme, symbols = un_calendar.parse_meeting_detail(
            fixture_json("journal-meeting-18th-plenary.json"))
        self.assertIn("Global health and foreign policy - Item 129", agenda)
        self.assertIn("A/81/L.6", symbols)
        self.assertIn("Letters from the President of the General Assembly", programme)
        self.assertNotIn("<p", agenda)
        self.assertNotIn("&ldquo;", programme)

    def test_agenda_alone_does_not_match_without_the_draft(self):
        """'Global health and foreign policy' is not our ground by itself:
        the plenary surfaces through the draft it acts on (step 3), or the
        PGA letter that names it (step 2). Recorded so nobody 'fixes' this
        by adding the agenda item title to the taxonomy."""
        tax, wl = un_filter()
        agenda, _p, _s = un_calendar.parse_meeting_detail(
            fixture_json("journal-meeting-18th-plenary.json"))
        self.assertNotIn(7, filt.filter_item(tax, wl, "18th plenary meeting", agenda).issue_areas)

    def test_fetch_reads_each_plenarys_agenda(self):
        payload = fixture_json("journal-ga-2026-10-01.json")
        detail = fixture_json("journal-meeting-18th-plenary.json")

        class Client:
            def __init__(self):
                self.posts, self.gets = [], []

            def post_json(self, url, body, feed, slug, headers=None):
                self.posts.append((url, json.loads(body), slug))
                return payload

            def get_text(self, url, feed, slug, headers=None, **kw):
                self.gets.append(url)
                if url.endswith("f0bd129c-9251-4047-b00c-cccb49848b30"):
                    return json.dumps(detail)
                raise RuntimeError("HTTP 404")

        client = Client()
        meetings, why, failures = un_calendar.fetch_ga_plenaries(
            client, start=datetime.date(2026, 10, 1), days=13)
        self.assertIsNone(why)
        self.assertEqual(client.posts[0][1]["organs"], [un_calendar.GENERAL_ASSEMBLY])
        self.assertTrue(client.posts[0][2].startswith("journal-ga-"))
        m = [m for m in meetings if m.id.startswith("f0bd129c")][0]
        self.assertIn("A/81/L.6", m.symbols)
        # The other plenaries' details 404 here: kept, and named as failures.
        self.assertEqual(len(failures), len(meetings) - 1)
        self.assertTrue(all("agenda not read" in f for f in failures))

    def test_out_of_range_is_a_horizon(self):
        class Failing:
            def post_json(self, *a, **k):
                raise RuntimeError("HTTP 400: Incorrect parameters")
        meetings, why, failures = un_calendar.fetch_ga_plenaries(Failing(), days=400)
        self.assertEqual((meetings, failures), ([], []))
        self.assertIn("near-term", why)


if __name__ == "__main__":
    unittest.main()
