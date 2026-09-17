"""The two-tab 5CA page: results board + chamber on top, the sheets behind a tab."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import stance  # noqa: E402
import make_5ca_web as web  # noqa: E402

COLS = list(stance.COLUMNS)


class SplitDecisionMakerTests(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(web.split_decision_maker("Jim Shannon (Democratic Unionist Party, Strangford)"),
                         ("Jim Shannon", "Democratic Unionist Party", "Strangford"))

    def test_nested_parenthesis_in_the_party(self):
        """43 Labour Co-op members used to ship as party 'Co-op)'."""
        self.assertEqual(web.split_decision_maker("Rachael Maskell (Labour (Co-op), York Central)"),
                         ("Rachael Maskell", "Labour (Co-op)", "York Central"))

    def test_seat_with_a_comma(self):
        self.assertEqual(web.split_decision_maker("Pamela Nash (Labour, Motherwell, Wishaw and Carluke)"),
                         ("Pamela Nash", "Labour", "Motherwell, Wishaw and Carluke"))

    def test_peer_with_party_only(self):
        self.assertEqual(web.split_decision_maker("Lord Alton of Liverpool (Crossbench)"),
                         ("Lord Alton of Liverpool", "Crossbench", ""))

    def test_no_suffix(self):
        self.assertEqual(web.split_decision_maker("Somebody"), ("Somebody", "", ""))


class MoveEntriesTests(unittest.TestCase):
    def test_kinds_and_membership(self):
        moves = [(1, "0", "++", stance.MOVED_UP, "2026-09-12"),
                 (2, "+", "--", stance.MOVED_DOWN, "2026-09-12"),
                 (3, "0", "++", stance.REASSESSED, "2026-09-12"),
                 (4, None, "++", stance.NEW, "2026-09-12"),
                 (5, "0", "++", stance.MOVED_UP, "2026-09-12")]  # 5 not on this sheet
        placed = {"1": [], "2": [], "3": [], "4": []}
        self.assertEqual(web.move_entries(moves, COLS, placed),
                         [[1, 2, "M"], [2, 1, "M"], [3, 2, "R"], [4, -1, "N"]])


class DatasetTests(unittest.TestCase):
    def test_partner_drops_tiers_flags_moves_and_since(self):
        members = [{"i": 1, "n": "A", "p": "Labour", "s": "X"}]
        placements = {"2": {"1": [0, 5, 0, 0, 3]}}
        internal, partner = web.build_datasets(members, placements, ["why"],
                                               {"2": [[1, 2, "M"]]}, "2026-09-10")
        i, p = json.loads(internal), json.loads(partner)
        self.assertEqual(i["placements"]["2"]["1"], [0, 5, 0, 0, 3])
        self.assertEqual(i["moves"], {"2": [[1, 2, "M"]]})
        self.assertEqual(i["since"], "2026-09-10")
        self.assertEqual(p["placements"]["2"]["1"], [0, 5, -1, -1])
        self.assertEqual(p["reasons"], [])
        self.assertEqual(p["moves"], {})
        self.assertIsNone(p["since"])
        self.assertEqual(p["members"], members, "the public record is shared")


class TemplateTests(unittest.TestCase):
    def test_two_tabs_results_first(self):
        self.assertLess(web.PAGE.index('data-tab="results"'), web.PAGE.index('data-tab="sheets"'))
        self.assertIn('id="pane-results" ', web.PAGE.replace('class="pane on" id="pane-results">',
                                                             'id="pane-results" '))
        self.assertIn('id="hemi"', web.PAGE)
        self.assertIn('id="seatbar"', web.PAGE)

    def test_only_real_moves_count_as_change(self):
        """A re-assessment is us, not the member: it must never feed the chips."""
        self.assertIn('if (kind !== "M" || from < 0', web.PAGE)
        self.assertIn("re-assessed by us on the same evidence (not counted)", web.PAGE)

    def test_majority_line_is_a_commons_thing(self):
        self.assertIn('const commons = HOUSE === "Commons"', web.PAGE)
        self.assertIn("__HOUSE__", web.PAGE)

    def test_house_placeholder_is_filled_for_both_houses(self):
        for house in ("Commons", "Lords"):
            self.assertNotIn("__HOUSE__", web.PAGE.replace("__HOUSE__", house))


if __name__ == "__main__":
    unittest.main()
