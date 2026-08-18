"""Northern Ireland Assembly ingester.

Fixtures are trimmed from live responses captured 2026-08-18.
"""

from __future__ import annotations

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingest import niassembly


QUESTIONS = {"QuestionsList": {"Question": [
    {"DocumentId": "21109", "Reference": "AQW 4832/08",
     "TabledDate": "2008-03-07T00:00:00+00:00",
     "QuestionText": "To ask the Minister to detail the number of teenage "
                     "women who travelled to England to have an abortion.",
     "QOralAnswerRequested": "false"},
    {"DocumentId": "99001", "Reference": "AQO 1234/26",
     "TabledDate": "2026-06-04T00:00:00+01:00",
     "QuestionText": "To ask the Minister about abortion services.",
     "QOralAnswerRequested": "true"},
]}}

MOTIONS = {"PlenaryList": {"Plenary": [
    {"DocumentID": "448545", "MotionCategory": "Private Members' Motion",
     "Title": "Rural Transport Needs", "TabledDate": "2025-09-08T00:00:00+01:00",
     "MotionTablers": "Ms Kellie Armstrong (APNI) / Mr Danny Donnelly (APNI) "
                      "/ Mr Peter McReynolds (APNI) "},
]}}

DIARY = {"BusinessDiary": {"DiaryItem": [
    {"EventId": "19841", "EventDate": "2026-08-20T00:00:00+01:00",
     "EventType": "Committee Meeting", "LocationRoom": "Room 30",
     "OrganisationName": "Windsor Framework Democratic Scrutiny Committee"},
]}}


class ParseQuestionTests(unittest.TestCase):
    def test_fields_and_newest_first(self):
        qs = niassembly.parse_questions(QUESTIONS)
        self.assertEqual(len(qs), 2)
        self.assertEqual(qs[0].reference, "AQO 1234/26")   # newest first
        self.assertEqual(qs[0].tabled, datetime.date(2026, 6, 4))
        self.assertTrue(qs[0].oral)
        self.assertFalse(qs[1].oral)
        self.assertEqual(qs[0].id, "ni-question:99001")
        self.assertIn("99001", qs[0].url)

    def test_since_filters_client_side(self):
        """The endpoint has no date parameter, so the window is applied here."""
        qs = niassembly.parse_questions(QUESTIONS, since=datetime.date(2020, 1, 1))
        self.assertEqual([q.reference for q in qs], ["AQO 1234/26"])

    def test_undated_row_is_kept_not_dropped(self):
        payload = {"QuestionsList": {"Question": [
            {"DocumentId": "5", "Reference": "AQW 1/26", "TabledDate": None,
             "QuestionText": "x"}]}}
        qs = niassembly.parse_questions(payload, since=datetime.date(2020, 1, 1))
        self.assertEqual(len(qs), 1, "an undated question must not vanish")
        self.assertIsNone(qs[0].tabled)

    def test_single_row_collapsed_to_object(self):
        """The API returns a bare object, not a list, for a one-row result."""
        payload = {"QuestionsList": {"Question": {
            "DocumentId": "7", "Reference": "AQW 9/26",
            "TabledDate": "2026-01-05T00:00:00+00:00", "QuestionText": "y"}}}
        self.assertEqual(len(niassembly.parse_questions(payload)), 1)

    def test_empty_and_missing_envelopes(self):
        self.assertEqual(niassembly.parse_questions({}), [])
        self.assertEqual(niassembly.parse_questions(None), [])
        self.assertEqual(
            niassembly.parse_questions({"QuestionsList": {"Question": None}}), [])


class ParseMotionTests(unittest.TestCase):
    def test_tablers_split_with_party(self):
        m = niassembly.parse_motions(MOTIONS)[0]
        self.assertEqual(m.id, "ni-motion:448545")
        self.assertEqual(
            m.tablers,
            [("Ms Kellie Armstrong", "APNI"), ("Mr Danny Donnelly", "APNI"),
             ("Mr Peter McReynolds", "APNI")])

    def test_parties_deduplicated_in_order(self):
        payload = {"PlenaryList": {"Plenary": [dict(
            MOTIONS["PlenaryList"]["Plenary"][0],
            MotionTablers="Mr A Smith (DUP) / Ms B Jones (SF) / Mr C Bell (DUP)")]}}
        self.assertEqual(niassembly.parse_motions(payload)[0].parties,
                         ["DUP", "SF"])

    def test_missing_tablers_is_empty_not_error(self):
        payload = {"PlenaryList": {"Plenary": [dict(
            MOTIONS["PlenaryList"]["Plenary"][0], MotionTablers=None)]}}
        self.assertEqual(niassembly.parse_motions(payload)[0].tablers, [])


class ParseDiaryTests(unittest.TestCase):
    def test_fields_and_chronological(self):
        d = niassembly.parse_diary(DIARY)[0]
        self.assertEqual(d.starts, datetime.date(2026, 8, 20))
        self.assertEqual(d.event_type, "Committee Meeting")
        self.assertEqual(d.id, "ni-diary:19841")

    def test_sorted_earliest_first(self):
        payload = {"BusinessDiary": {"DiaryItem": [
            {"EventId": "2", "EventDate": "2026-09-01T00:00:00+01:00",
             "EventType": "Plenary", "OrganisationName": "Assembly"},
            {"EventId": "1", "EventDate": "2026-08-20T00:00:00+01:00",
             "EventType": "Plenary", "OrganisationName": "Assembly"}]}}
        self.assertEqual([d.event_id for d in niassembly.parse_diary(payload)],
                         ["1", "2"])


class FetchContractTests(unittest.TestCase):
    class _Boom:
        def get_json(self, *a, **k):
            raise RuntimeError("timed out")

    def test_short_term_rejected_without_a_request(self):
        """The endpoint needs 3+ chars; spending a request to be told is waste."""
        class _Never:
            def get_json(self, *a, **k):
                raise AssertionError("should not have been called")
        found, err = niassembly.fetch_questions(_Never(), "ab")
        self.assertEqual(found, [])
        self.assertIn("3 characters", err)

    def test_error_is_returned_not_raised(self):
        """One failed term must not lose the other thirty-nine."""
        found, err = niassembly.fetch_questions(self._Boom(), "abortion")
        self.assertEqual(found, [])
        self.assertIn("timed out", err)


class SeparationTests(unittest.TestCase):
    """NI must not be able to reach the published Slack digest."""

    def test_ni_pull_never_writes_to_items(self):
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "tools", "ni_pull.py")
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("INTO items", source)
        self.assertNotIn("UPDATE items", source)
        self.assertIn("ni_items", source)


if __name__ == "__main__":
    unittest.main()
