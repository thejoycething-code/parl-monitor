"""NI Assembly Hansard: windowing a division to its amendment's wording.

Fixtures are trimmed from the two real responses captured 2026-08-18, with real
ComponentIds, real RelatedItemIds and real amendment numbers, because the whole
module rests on two exact key relationships and a fabricated id would prove
nothing about either.
"""

from __future__ import annotations

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import filter as filt
from src.ingest import ni_hansard as H

WHEN = datetime.date(2026, 6, 30)


def comp(cid, kind, text, parent=None, related=None, type_id="", level="level 3"):
    row = {"ComponentId": cid, "ComponentType": kind, "ComponentText": text,
           "ComponentTypeId": type_id, "ComponentHeader": level}
    # ParentComponentId and RelatedItemId are ABSENT on most components -- the
    # API omits the keys entirely rather than sending null -- so the fixtures
    # omit them too and the parser must cope.
    if parent is not None:
        row["ParentComponentId"] = parent
    if related is not None:
        row["RelatedItemId"] = related
    return row


# Justice Bill, 2026-06-30. Amendment 97 is "Accommodation of women prisoners"
# (area 5); amendment 86 is "Minimum age of criminal responsibility" (nothing).
JUSTICE = {"AllHansardComponentsList": {"HansardComponent": [
    comp("5652764", "Header", "Justice Bill: Consideration Stage",
         related="410219", type_id="0", level="level 3"),
    comp("5652900", "Procedure Line", "Amendment No 86 proposed:", type_id="8"),
    comp("5652901", "Bill Text",
         "Before clause 24 insert&#8212; &quot; Minimum age of criminal "
         "responsibility A24. No child under 14 may be convicted.",
         type_id="12"),
    comp("5652903", "Procedure Line",
         "Question put, That amendment No 86 be made.", type_id="8"),
    comp("5652904", "Division", "The Assembly divided:",
         parent="5652764", related="490049", type_id="7"),
    comp("5652935", "Procedure Line",
         "Amendment No 97 proposed on 15 June 2026:", type_id="8"),
    comp("5652936", "Bill Text",
         "After clause 30 insert&#8212; &quot; Accommodation of women prisoners "
         "30A. In providing accommodation, regard must be had to the Equality "
         "Act 2010.", type_id="12"),
    comp("5652939", "Procedure Line",
         "Question put, That amendment No 97 be made.", type_id="8"),
    comp("5652941", "Division", "The Assembly divided:",
         parent="5652764", related="493329", type_id="7"),
]}}


class ExactKeyTests(unittest.TestCase):
    """The two relationships the whole module rests on."""

    def setUp(self):
        self.sitting = H.parse_sitting(JUSTICE, WHEN)

    def test_a_division_names_its_own_division_by_related_item_id(self):
        """Verified 7 of 7 on 2026-06-30 and 139 of 139 across every date."""
        self.assertEqual(set(self.sitting.anchors()), {"490049", "493329"})

    def test_the_window_is_the_parent_header_not_the_nearest_one(self):
        """REGRESSION. A backward scan for the nearest preceding Header put
        2026-04-20 division 477724 (Hospital Parking Charges, Final Stage) under
        a Marriage and Civil Partnership motion and classified it area 9 on
        'civil partnership'. The parent pointer resolves it."""
        payload = {"AllHansardComponentsList": {"HansardComponent": [
            comp("100", "Header", "Hospital Parking Charges Bill: Final Stage",
                 related="410000", type_id="0"),
            comp("101", "Plenary Item Text",
                 "That the Hospital Parking Charges Bill do now pass."),
            comp("200", "Header",
                 "That the Second Stage of the Marriage and Civil Partnership "
                 "Bill be agreed", related="420000", type_id="0"),
            comp("300", "Procedure Line", "Question put.", type_id="8"),
            # Parent is the FIRST header, though the nearest preceding is the second.
            comp("301", "Division", "The Assembly divided:",
                 parent="100", related="477724", type_id="7"),
        ]}}
        ev, gaps = H.evidence_for(H.parse_sitting(payload, WHEN), ["477724"])
        self.assertEqual(gaps, [])
        self.assertEqual(ev[0].item_id, "410000")
        self.assertIn("Hospital Parking", ev[0].item_name)
        self.assertNotIn("Marriage", ev[0].item_name)

    def test_component_header_is_a_level_marker_not_a_scope(self):
        """Its values across a whole sitting are 'level 1/2/3' and a time."""
        self.assertEqual({c.level for c in self.sitting.components}, {"level 3"})

    def test_related_item_id_is_polymorphic_by_component_type(self):
        """A PersonId on a Speaker row must never be read as a division."""
        payload = {"AllHansardComponentsList": {"HansardComponent": [
            comp("1", "Header", "X", related="410219", type_id="0"),
            comp("2", "Speaker (MlaName)", "Mr Frew:", related="137", type_id="2"),
            comp("3", "Division", "divided", parent="1", related="493329",
                 type_id="7"),
        ]}}
        self.assertEqual(set(H.parse_sitting(payload, WHEN).anchors()),
                         {"493329"})

    def test_component_type_ids_pair_with_their_names(self):
        """Guards an upstream rename, the DivisonType lesson."""
        seen = {c.kind: c.type_id for c in self.sitting.components if c.type_id}
        for kind, type_id in H.TYPE_IDS.items():
            if kind in seen:
                self.assertEqual(seen[kind], type_id, kind)

    def test_missing_parent_and_related_keys_do_not_crash(self):
        payload = {"AllHansardComponentsList": {"HansardComponent": [
            comp("1", "Spoken Text", "hello")]}}
        s = H.parse_sitting(payload, WHEN)
        self.assertEqual(s.components[0].parent_id, "")
        self.assertEqual(s.components[0].related_id, "")

    def test_a_single_component_collapses_to_a_bare_object(self):
        payload = {"AllHansardComponentsList": {"HansardComponent":
                   comp("1", "Header", "X", related="1", type_id="0")}}
        self.assertEqual(len(H.parse_sitting(payload, WHEN).components), 1)

    def test_out_of_order_components_are_refused_not_windowed(self):
        """Document order is load-bearing and nothing guarantees it."""
        payload = {"AllHansardComponentsList": {"HansardComponent": [
            comp("500", "Header", "X", related="1", type_id="0"),
            comp("100", "Division", "divided", parent="500", related="9",
                 type_id="7"),
        ]}}
        ev, gaps = H.evidence_for(H.parse_sitting(payload, WHEN), ["9"])
        self.assertEqual(ev, [])
        self.assertIn("order", gaps[0])


class BillAmendmentTests(unittest.TestCase):
    def setUp(self):
        self.sitting = H.parse_sitting(JUSTICE, WHEN)
        self.ev, self.gaps = H.evidence_for(self.sitting, ["493329", "490049"])
        self.by_doc = {e.doc_id: e for e in self.ev}

    def test_amendment_text_is_paired_with_its_number(self):
        self.assertEqual(self.gaps, [])
        self.assertEqual(self.by_doc["493329"].amendment_no, 97)
        self.assertIn("Accommodation of women",
                      self.by_doc["493329"].amendment_text)
        self.assertEqual(self.by_doc["490049"].amendment_no, 86)
        self.assertIn("Minimum age", self.by_doc["490049"].amendment_text)

    def test_entities_are_decoded_and_markup_stripped(self):
        text = self.by_doc["493329"].amendment_text
        self.assertNotIn("&quot;", text)
        self.assertNotIn("&#8212;", text)
        self.assertNotIn("<", text)

    def test_the_question_line_sets_on_amendment(self):
        self.assertTrue(self.by_doc["493329"].on_amendment)
        self.assertIn("Question put", self.by_doc["493329"].question)

    def test_source_is_amendment_text(self):
        self.assertEqual(self.by_doc["493329"].source, H.AMENDMENT_TEXT)

    def test_a_bill_amendment_carries_no_motion_context(self):
        """Self-contained, so a broad motion cannot lend it areas."""
        _title, body = self.by_doc["493329"].classify_fields
        self.assertIn("Accommodation of women", body)
        self.assertNotIn("That this Assembly", body)


class MotionAmendmentTests(unittest.TestCase):
    """The 'beg to move' opener, and the duplicate-number hazard."""

    # Two different motions on one day, each with an 'amendment No 1'. Left
    # unscoped this is a silent mis-attribution.
    TWO_MOTIONS = {"AllHansardComponentsList": {"HansardComponent": [
        comp("5124005", "Header", "A5 Western Transport Corridor Scheme",
             related="448608", type_id="0"),
        comp("5124010", "Plenary Item Text",
             "That this Assembly notes the A5 scheme."),
        comp("5124020", "Spoken Text", "I beg to move amendment No 1:"),
        comp("5124021", "Plenary Item Text",
             "Leave out all after &quot;Assembly&quot; and insert: "
             "acknowledges the Minister for Infrastructure."),
        comp("5124030", "Procedure Line",
             "Question put, That amendment No 1 be made.", type_id="8"),
        comp("5124031", "Division", "divided", parent="5124005",
             related="449971", type_id="7"),
        comp("5124185", "Header", "Hate: Executive Approach",
             related="448609", type_id="0"),
        comp("5124190", "Plenary Item Text",
             "That this Assembly condemns the continued high level of hate."),
        comp("5124200", "Spoken Text", "I beg to move amendment No 1:"),
        comp("5124201", "Plenary Item Text",
             "Leave out all after &quot;Northern Ireland&quot; and insert: "
             "notes the recent Executive commitment on conversion therapy."),
        comp("5124210", "Procedure Line",
             "Question put, That amendment No 1 be made.", type_id="8"),
        comp("5124211", "Division", "divided", parent="5124185",
             related="449970", type_id="7"),
    ]}}

    def setUp(self):
        self.sitting = H.parse_sitting(self.TWO_MOTIONS,
                                       datetime.date(2025, 9, 22))
        self.ev, self.gaps = H.evidence_for(self.sitting, ["449971", "449970"])
        self.by_doc = {e.doc_id: e for e in self.ev}

    def test_beg_to_move_is_recognised_as_an_opener(self):
        """It arrives as Spoken Text, not a Procedure Line. Omitting it left
        the two 'Hate: Executive Approach' divisions unexplained."""
        self.assertEqual(self.gaps, [])
        self.assertEqual(self.by_doc["449971"].source, H.AMENDMENT_TEXT)

    def test_duplicate_amendment_numbers_resolve_to_different_motions(self):
        """Both are 'amendment No 1'; only the header scoping separates them."""
        self.assertEqual(self.by_doc["449971"].amendment_no, 1)
        self.assertEqual(self.by_doc["449970"].amendment_no, 1)
        self.assertIn("Minister for Infrastructure",
                      self.by_doc["449971"].amendment_text)
        self.assertIn("conversion therapy",
                      self.by_doc["449970"].amendment_text)
        self.assertNotEqual(self.by_doc["449971"].item_id,
                            self.by_doc["449970"].item_id)

    def test_a_motion_amendment_carries_its_motion_as_context(self):
        """"Leave out all after X and insert" is a diff, meaningless alone."""
        _title, body = self.by_doc["449970"].classify_fields
        self.assertIn("conversion therapy", body)
        self.assertIn("condemns the continued high level", body)


class NoTextTests(unittest.TestCase):
    def test_a_missing_amendment_is_no_text_never_the_item_text(self):
        """A motion's areas standing in for the amendment that guts it is the
        unmarked-fallback bug this codebase keeps designing out."""
        payload = {"AllHansardComponentsList": {"HansardComponent": [
            comp("1", "Header", "Some Motion", related="1", type_id="0"),
            comp("2", "Plenary Item Text",
                 "That this Assembly supports abortion law reform."),
            comp("3", "Procedure Line",
                 "Question put, That amendment No 4 be made.", type_id="8"),
            comp("4", "Division", "divided", parent="1", related="999",
                 type_id="7"),
        ]}}
        ev, gaps = H.evidence_for(H.parse_sitting(payload, WHEN), ["999"])
        self.assertEqual(ev[0].source, H.NO_TEXT)
        self.assertEqual(ev[0].amendment_text, "")
        self.assertEqual(len(gaps), 1)
        self.assertIn("999", gaps[0])
        # classify_fields must expose nothing, so the motion cannot be scored
        # as though it were the amendment.
        self.assertEqual(ev[0].classify_fields[1], "")

    def test_an_empty_amendment_body_is_never_labelled_amendment_text(self):
        """REGRESSION, and the exact bug this module exists to prevent. An
        empty amendment body left classify_fields returning the MOTION under an
        amendment label: division 476834 classified area 5 off its motion while
        reporting source=amendment-text."""
        payload = {"AllHansardComponentsList": {"HansardComponent": [
            comp("1", "Header", "Waste and Inefficiency in Government",
                 related="475390", type_id="0"),
            comp("2", "Plenary Item Text",
                 "That this Assembly notes concerns about transgender guidance."),
            comp("3", "Spoken Text", "I beg to move the following amendment:"),
            comp("4", "Plenary Item Text", "   "),      # empty after cleaning
            comp("5", "Procedure Line",
                 "Question put, That the amendment be made.", type_id="8"),
            comp("6", "Division", "divided", parent="1", related="476834",
                 type_id="7"),
        ]}}
        ev, _gaps = H.evidence_for(H.parse_sitting(payload, WHEN), ["476834"])
        self.assertNotEqual(ev[0].source, H.AMENDMENT_TEXT)
        self.assertEqual(ev[0].amendment_text, "")
        self.assertEqual(ev[0].classify_fields[1], "",
                         "the motion must not be classifiable as the amendment")

    def test_a_single_unnumbered_amendment_is_taken_despite_a_subject_hint(self):
        """Hansard numbers neither the proposal nor the question when a motion
        drew one amendment, while the subject still says 'Amendment 1'. Making
        the hint disqualify this case left 21 divisions unexplained."""
        payload = {"AllHansardComponentsList": {"HansardComponent": [
            comp("1", "Header", "Legacy Cases: Irish Government",
                 related="1", type_id="0"),
            comp("2", "Plenary Item Text", "That this Assembly condemns X."),
            comp("3", "Spoken Text", "I beg to move the following amendment:"),
            comp("4", "Plenary Item Text",
                 "Leave out all after &quot;State&quot; and insert: continued "
                 "to advance conversion therapy concerns."),
            comp("5", "Procedure Line",
                 "Question put, That the amendment be made.", type_id="8"),
            comp("6", "Division", "divided", parent="1", related="484989",
                 type_id="7"),
        ]}}
        ev, gaps = H.evidence_for(H.parse_sitting(payload, WHEN), ["484989"],
                                  hints={"484989": 1})
        self.assertEqual(gaps, [])
        self.assertEqual(ev[0].source, H.AMENDMENT_TEXT)
        self.assertIn("conversion therapy", ev[0].amendment_text)

    def test_a_whole_question_vote_is_item_text(self):
        payload = {"AllHansardComponentsList": {"HansardComponent": [
            comp("1", "Header", "Hunting with Dogs Bill: Second Stage",
                 related="1", type_id="0"),
            comp("2", "Plenary Item Text",
                 "That the Second Stage of the Hunting with Dogs Bill be agreed."),
            comp("3", "Procedure Line", "Question put.", type_id="8"),
            comp("4", "Division", "divided", parent="1", related="777",
                 type_id="7"),
        ]}}
        ev, gaps = H.evidence_for(H.parse_sitting(payload, WHEN), ["777"])
        self.assertEqual(gaps, [])
        self.assertFalse(ev[0].on_amendment)
        self.assertEqual(ev[0].source, H.ITEM_ONLY)
        self.assertIn("Hunting with Dogs", ev[0].classify_fields[1])

    def test_a_division_absent_from_hansard_is_a_gap(self):
        ev, gaps = H.evidence_for(H.parse_sitting(JUSTICE, WHEN), ["000000"])
        self.assertEqual(ev, [])
        self.assertIn("000000", gaps[0])


class ClassificationTests(unittest.TestCase):
    """Why this diverges from retag_passages.py, in assertions."""

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def setUp(self):
        self.tax = filt.load_taxonomy(
            os.path.join(self.ROOT, "config", "taxonomy.yaml"))
        self.wl = filt.load_watchlist(
            os.path.join(self.ROOT, "config", "watchlist.yaml"))
        ev, _ = H.evidence_for(H.parse_sitting(JUSTICE, WHEN), ["493329"])
        self.amendment = ev[0]

    def test_filter_item_keeps_a_tier_two_amendment_that_the_passage_gate_drops(self):
        """The gate in match_passages keeps only tier-1-or-watchlist passages.
        Right for one stray term in a 3,000-word speech; wrong here, because an
        amendment IS the whole document and it is short. Measured: the gate
        drops amendment 97 (area 5, 'Equality Act 2010') and amendment 73
        (area 7, 'blasphemy') -- precisely the interesting ones."""
        _title, body = self.amendment.classify_fields
        kept = filt.filter_item(self.tax, self.wl, body)
        gated, _terms, _ex = filt.aggregate_passages(
            filt.match_passages(self.tax, self.wl, body))
        self.assertIn(5, kept.issue_areas)
        self.assertEqual(gated, [],
                         "if the gate starts keeping this, re-read the comment "
                         "in tools/ni_classify.py before simplifying it away")

    def test_the_discriminating_result(self):
        """Amendment 97 is ours; 86 on the same day is not. Classifying the
        whole sitting day instead returned 8 of 11 areas and was useless."""
        ev, _ = H.evidence_for(H.parse_sitting(JUSTICE, WHEN),
                               ["493329", "490049"])
        got = {}
        for e in ev:
            _t, body = e.classify_fields
            got[e.amendment_no] = filt.filter_item(
                self.tax, self.wl, body).issue_areas
        self.assertIn(5, got[97])
        self.assertEqual(got[86], [], "minimum age of criminal responsibility "
                                      "is youth justice, not our ground")


class FetchContractTests(unittest.TestCase):
    def test_error_is_returned_not_raised(self):
        """One failed date must not lose the other fifty-three."""
        class _Boom:
            def get_json(self, *a, **k):
                raise RuntimeError("500")
        sitting, err = H.fetch_sitting(_Boom(), "2026-06-30")
        self.assertIsNone(sitting)
        self.assertIn("500", err)


class SeparationTests(unittest.TestCase):
    """ni_classify.py must not be able to reach the Slack digest."""

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_ni_classify_writes_only_its_own_table(self):
        with open(os.path.join(self.ROOT, "tools", "ni_classify.py"),
                  encoding="utf-8") as fh:
            source = fh.read()
        for table in ("items", "mp_events"):
            for verb in ("INTO {0}", "UPDATE {0}"):
                self.assertNotIn(verb.format(table), source)
        self.assertIn("UPDATE ni_divisions", source)

    def test_every_ni_tool_is_guarded_by_the_glob(self):
        """The old guards named files in a tuple, so a NEW ni_* tool was born
        unprotected. Enumerate instead."""
        import glob
        tools = glob.glob(os.path.join(self.ROOT, "tools", "ni_*.py"))
        self.assertTrue(tools)
        for path in tools:
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
            for table in ("items", "mp_events"):
                for verb in ("INTO {0}", "UPDATE {0}"):
                    self.assertNotIn(verb.format(table), source,
                                     os.path.basename(path))


if __name__ == "__main__":
    unittest.main()
