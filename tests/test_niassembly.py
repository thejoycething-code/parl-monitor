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

    def test_series_from_reference_prefix_beats_the_flag(self):
        """AQO is the oral series. QOralAnswerRequested disagreed with the
        prefix on 2 of 20 real questions, so the prefix wins."""
        payload = {"QuestionsList": {"Question": [
            {"DocumentId": "1", "Reference": "AQO 3230/22-27",
             "TabledDate": "2026-02-26T00:00:00+00:00", "QuestionText": "x",
             "QOralAnswerRequested": "false"},
            {"DocumentId": "2", "Reference": "AQW 1/26",
             "TabledDate": "2026-02-26T00:00:00+00:00", "QuestionText": "y",
             "QOralAnswerRequested": "false"}]}}
        qs = {q.reference: q.series for q in niassembly.parse_questions(payload)}
        self.assertEqual(qs["AQO 3230/22-27"], "oral")
        self.assertEqual(qs["AQW 1/26"], "written")

    def test_series_falls_back_to_flag_when_reference_unreadable(self):
        payload = {"QuestionsList": {"Question": [
            {"DocumentId": "3", "Reference": "", "TabledDate": None,
             "QuestionText": "z", "QOralAnswerRequested": "true"}]}}
        self.assertEqual(niassembly.parse_questions(payload)[0].series, "oral")

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


DETAIL = {"QuestionsList": {"Question": {
    "DocumentId": "491849", "Reference": "AQW 49327/22-27",
    "TablerName": "Mr Jon Burrows", "TablerTitle": "MLA - North Antrim",
    "TablerPersonId": "9509", "TabledDate": "2026-06-22T00:00:00+01:00",
    "AnsweredOnDate": "2026-07-06T00:00:00+01:00",
    "QuestionText": "To ask the Minister of Justice ...",
    "MinisterTitle": "Minister of Justice",
    "Department": "Department of Justice",
    "AnswerPlainText": "The Northern Ireland Prison Service informs the "
                       "Home Office of all custodial sentences."}}}

MEMBERS = {"AllMembersList": {"Member": [
    {"PersonId": "5797", "MemberName": "Aiken, Steve OBE",
     "MemberFullDisplayName": "Dr Steve Aiken OBE",
     "PartyName": "Ulster Unionist Party", "ConstituencyName": "South Antrim"},
]}}

VOTING = {"MemberVoting": {"Member": [
    {"DocumentID": "493329", "PersonID": "5307", "MemberName": "Mr Andy Allen MBE",
     "Vote": "AYE", "Designation": "Unionist", "VoteInVacancy": "false"},
    {"DocumentID": "493329", "PersonID": "5308", "MemberName": "Ms B Example",
     "Vote": "NO", "Designation": "Nationalist", "VoteInVacancy": "false"},
]}}


class QuestionDetailTests(unittest.TestCase):
    def test_attribution_minister_and_answer(self):
        d = niassembly.parse_question_detail(DETAIL)
        self.assertEqual(d.tabler, "Mr Jon Burrows")
        self.assertEqual(d.tabler_person_id, "9509")
        self.assertEqual(d.minister, "Minister of Justice")
        self.assertEqual(d.answered, datetime.date(2026, 7, 6))
        self.assertIn("Prison Service", d.answer)

    def test_constituency_split_off_the_title(self):
        self.assertEqual(
            niassembly.parse_question_detail(DETAIL).constituency, "North Antrim")

    def test_missing_question_returns_none(self):
        """A bad documentId answers 200 with a null list, not an error."""
        self.assertIsNone(
            niassembly.parse_question_detail({"QuestionsList": None}))


class MemberTests(unittest.TestCase):
    def test_roster_carries_party_and_seat(self):
        m = niassembly.parse_members(MEMBERS)[0]
        self.assertEqual(m.person_id, "5797")
        self.assertEqual(m.party, "Ulster Unionist Party")
        self.assertEqual(m.constituency, "South Antrim")


class BillOfTests(unittest.TestCase):
    """bill_of is the grouping key for divisions, so its edge cases matter."""

    def test_strips_amendment_stage_ref_day_and_proposer(self):
        self.assertEqual(niassembly.bill_of(
            "Amendment 97 - Consideration Stage: Justice Bill "
            "(NIA Bill 7/22-27) (Day 4) [Mr Timothy Gaston]"), "Justice Bill")

    def test_unclosed_bracket_from_100_char_truncation(self):
        """The API cuts DivisionSubject at 100 chars, losing the closing ']'.

        Without handling this, one bill grows a different fake suffix per
        amendment and the grouping shatters.
        """
        self.assertEqual(niassembly.bill_of(
            "Amendment 91 - Consideration Stage: Justice Bill "
            "(NIA Bill 7/22-27) (Day 4) [Minister of Justice - D"),
            "Justice Bill")

    def test_newline_inside_subject(self):
        self.assertEqual(niassembly.bill_of(
            "Moving Beyond the Windsor Framework\n - Amendment 1: Motion "
            "Amendment 1"), "Moving Beyond the Windsor Framework")

    def test_hash_prefix_and_bare_motion(self):
        self.assertEqual(
            niassembly.bill_of("-#1 The Irish Government's Failure to Cooperate"),
            "The Irish Government's Failure to Cooperate")

    def test_unclosed_paren_cut_mid_word(self):
        """"(NIA Bil" -- the cap can cut inside the word, so matching the
        literal "NIA Bill" is not enough. Any unclosed trailing paren goes."""
        self.assertEqual(niassembly.bill_of(
            "Amendment 1 - Consideration Stage: School Uniforms (Guidelines "
            "and Allowances) Bill (NIA Bil"),
            "School Uniforms (Guidelines and Allowances) Bill")

    def test_unclosed_paren_that_is_part_of_the_name_survives(self):
        """REGRESSION. Stripping every unclosed paren cut this to "Inquiry"
        and silently lost two watched divisions (37 -> 35). Only the "(NIA..."
        reference is furniture; other unclosed parens are name."""
        self.assertEqual(niassembly.bill_of(
            "Amendment 9 - Further Consideration Stage: Inquiry (Mother and "
            "Baby Institutions, Magdalene Laundrie"),
            "Inquiry (Mother and Baby Institutions, Magdalene Laundrie")

    def test_truncated_and_untruncated_forms_group(self):
        a = niassembly.bill_of("Amendment 1 - Consideration Stage: School "
                               "Uniforms (Guidelines and Allowances) Bill (NIA Bil")
        b = niassembly.bill_of("Consideration Stage: School Uniforms (Guidelines "
                               "and Allowances) Bill (NIA Bill 12/22-27)")
        self.assertEqual(a, b)

    def test_inner_parentheses_are_kept(self):
        """"(Mother and Baby Institutions...)" is part of the name, not furniture."""
        self.assertEqual(niassembly.bill_of(
            "Amendment 9 - Further Consideration Stage: Inquiry (Mother and "
            "Baby Institutions, Magdalene Laundries) Bill (NIA Bill 3/22-27)"),
            "Inquiry (Mother and Baby Institutions, Magdalene Laundries) Bill")

    def test_two_forms_of_one_bill_group_together(self):
        a = niassembly.bill_of("Amendment 1 - Consideration Stage: Justice Bill "
                               "(NIA Bill 7/22-27) (Day 1) [Ms Emma Sheerin]")
        b = niassembly.bill_of("Amendment 91 - Consideration Stage: Justice Bill "
                               "(NIA Bill 7/22-27) (Day 4) [Minister of Justice - D")
        self.assertEqual(a, b)


class BillMatchesTests(unittest.TestCase):
    """The watch list is matched by prefix because truncation cuts suffixes."""

    FULL = "Inquiry (Mother and Baby Institutions, Magdalene Laundries) Bill"

    def test_two_truncations_of_one_bill_both_match(self):
        """The real failure: exact matching found NEITHER of these."""
        for stored in ("Inquiry (Mother and Baby Institutions, Magdalene Laundrie",
                       "Inquiry (Mother and Baby Institutions, Magdalene Laundries and W"):
            self.assertTrue(niassembly.bill_matches(stored, self.FULL), stored)

    def test_exact_name_still_matches(self):
        self.assertTrue(niassembly.bill_matches("Justice Bill", "Justice Bill"))

    def test_different_bills_do_not_match(self):
        self.assertFalse(niassembly.bill_matches(
            "Sign Language Bill", "Justice Bill"))
        self.assertFalse(niassembly.bill_matches(
            "Education Inspections Bill", "Dilapidation Bill"))

    def test_short_stem_is_refused(self):
        """A short prefix would claim everything starting with the same word."""
        self.assertFalse(niassembly.bill_matches(
            "The", "The Executive's Multi-Year Budget"))
        self.assertFalse(niassembly.bill_matches(
            "Justice Bill", "Just"))

    def test_case_and_whitespace_insensitive(self):
        self.assertTrue(niassembly.bill_matches(
            "  justice   bill ", "Justice Bill"))

    def test_empty_never_matches(self):
        self.assertFalse(niassembly.bill_matches("", "Justice Bill"))
        self.assertFalse(niassembly.bill_matches("Justice Bill", ""))


class DivisionTests(unittest.TestCase):
    RAW = {"DivisionList": {"Division": [
        {"EventID": "19798", "DocumentID": "493329",
         "DivisionSubject": "Amendment 97 - Consideration Stage: Justice Bill "
                            "(NIA Bill 7/22-27) (Day 4) [Mr Timothy Gaston]",
         "DivisionDate": "2026-06-30T12:27:10.957+01:00",
         "DivisonType": "Simple Majority"},
        {"EventID": "19700", "DocumentID": "490000",
         "DivisionSubject": "Consideration Stage: Sign Language Bill",
         "DivisionDate": "2026-05-01T10:00:00+01:00",
         "DivisonType": "Cross-Community"},
    ]}}

    def test_parses_and_derives_bill(self):
        ds = niassembly.parse_divisions(self.RAW)
        self.assertEqual(ds[0].bill, "Justice Bill")
        self.assertEqual(ds[0].id, "ni-division:493329")

    def test_misspelled_divison_type_is_read(self):
        """Their field is 'DivisonType'. Reading only the correct spelling
        would blank the column and hide cross-community votes."""
        ds = niassembly.parse_divisions(self.RAW)
        self.assertEqual(ds[0].kind, "Simple Majority")
        self.assertTrue(ds[1].cross_community)
        self.assertFalse(ds[0].cross_community)

    def test_correct_spelling_also_read(self):
        payload = {"DivisionList": {"Division": [
            {"DocumentID": "1", "DivisionSubject": "x",
             "DivisionDate": "2026-01-01T00:00:00+00:00",
             "DivisionType": "Cross-Community"}]}}
        self.assertTrue(niassembly.parse_divisions(payload)[0].cross_community)


class MemberVotingTests(unittest.TestCase):
    def test_votes_normalised_with_designation(self):
        vs = niassembly.parse_member_voting(VOTING)
        self.assertEqual([v.vote for v in vs], ["aye", "no"])
        self.assertEqual(vs[0].designation, "Unionist")
        self.assertEqual(vs[1].designation, "Nationalist")

    def test_unknown_vote_kept_verbatim_not_guessed(self):
        """Coercing an unrecognised value would put words in a member's mouth."""
        payload = {"MemberVoting": {"Member": [
            {"DocumentID": "1", "PersonID": "2", "MemberName": "X",
             "Vote": "RECUSED", "Designation": "Other"}]}}
        self.assertEqual(niassembly.parse_member_voting(payload)[0].vote,
                         "recused")

    def test_error_returned_not_raised(self):
        class _Boom:
            def get_json(self, *a, **k):
                raise RuntimeError("500")
        votes, err = niassembly.fetch_member_voting(_Boom(), "1")
        self.assertEqual(votes, [])
        self.assertIn("500", err)


class SeparationTests(unittest.TestCase):
    """NI must not be able to reach the published Slack digest."""

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _source(self, name):
        with open(os.path.join(self.ROOT, "tools", name), encoding="utf-8") as fh:
            return fh.read()

    def test_ni_tools_never_write_to_published_tables(self):
        """`items` feeds the Slack edition and `mp_events` feeds the 5CA.

        NI is a watching brief, so neither may be written by an NI tool. This
        is the structural guarantee, asserted rather than trusted.
        """
        for name in ("ni_pull.py", "ni_divisions.py"):
            source = self._source(name)
            for table in ("items", "mp_events"):
                for verb in ("INTO {0}", "UPDATE {0}", "INTO  {0}"):
                    self.assertNotIn(verb.format(table), source,
                                     "{0} must not write {1}".format(name, table))

    def test_ni_pull_writes_its_own_tables(self):
        source = self._source("ni_pull.py")
        self.assertIn("ni_items", source)
        self.assertIn("ni_members", source)

    def test_ni_divisions_writes_its_own_tables(self):
        source = self._source("ni_divisions.py")
        self.assertIn("ni_divisions", source)
        self.assertIn("ni_votes", source)


if __name__ == "__main__":
    unittest.main()
