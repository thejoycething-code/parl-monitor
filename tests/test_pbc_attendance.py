"""PBC attendance: the roster parser and the name resolution.

The roster at the head of each Public Bill Committee sitting is the only
official attendance record a bill committee has. The dagger convention is
load-bearing -- a row without one is a member who was APPOINTED but absent
that day -- so the parser must carry the mark through, not just the names.
"""

import importlib.util
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, members

spec = importlib.util.spec_from_file_location(
    "pbc", os.path.join(ROOT, "tools", "pull_pbc_attendance.py"))
pbc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pbc)


def item(value):
    return {"ItemType": "Contribution", "Value": value}


# Verbatim shapes from the Terminally Ill Adults Bill (First sitting),
# 2025-01-21, including the two awkward rows: a minister whose <em> carries
# an office instead of a constituency, and a chair line where only some of
# the panel attended.
ROSTER = [
    item('<span id="1" class="column-number"></span>'),
    item("The Committee consisted of the following Members:"),
    item("<em>Chairs:</em> Peter Dowd, † Sir Roger Gale, Carolyn Harris"),
    item("† Abbott, Jack <em>(Ipswich)</em> (Lab/Co-op)"),
    item("† Opher, Dr Simon <em>(Stroud)</em> (Lab)"),
    item("† Kinnock, Stephen <em>(Minister for Care)</em>"),
    item("† Saville Roberts, Liz <em>(Dwyfor Meirionnydd)</em> (PC)"),
    item("Campbell, Juliet <em>(Broxtowe)</em> (Lab)"),   # appointed, absent
    item("Lynn Gardner, Lucinda Maer, <em>Committee Clerks</em>"),
    item("† attended the Committee"),
    item("Public Bill Committee"),                        # past the roster
]


class RosterParserTests(unittest.TestCase):
    def setUp(self):
        self.rows = pbc.parse_roster(ROSTER)
        self.by_name = {name: (role, attended)
                        for name, role, attended in self.rows}

    def test_a_dagger_means_attended_and_its_absence_means_absent(self):
        self.assertEqual(self.by_name["Jack Abbott"], ("member", True))
        self.assertEqual(self.by_name["Juliet Campbell"], ("member", False))

    def test_surname_first_rows_are_turned_back_into_names(self):
        self.assertIn("Liz Saville Roberts", self.by_name)   # two-word surname

    def test_a_minister_is_a_member_like_any_other(self):
        # Their <em> carries an office where everyone else has a seat; the
        # office is annotation, not name, and must not leak into either.
        self.assertEqual(self.by_name["Stephen Kinnock"], ("member", True))

    def test_chairs_carry_their_own_attendance(self):
        self.assertEqual(self.by_name["Sir Roger Gale"], ("chair", True))
        self.assertEqual(self.by_name["Peter Dowd"], ("chair", False))

    def test_clerks_are_nobody_s_attendance(self):
        self.assertNotIn("Lynn Gardner", self.by_name)

    def test_nothing_past_the_legend_is_read(self):
        self.assertNotIn("Public Bill Committee",
                         [name for name, _, _ in self.rows])

    def test_a_transcript_without_a_roster_says_so(self):
        # None, not []: "no roster block" and "an empty roster" are
        # different failures, and the caller records a gap for the first.
        self.assertIsNone(pbc.parse_roster([item("Second Reading debate")]))


class SittingIndexTests(unittest.TestCase):
    class FakeRaw:
        meta = {
            "a": {"debate": "A Bill (First sitting)", "debate_id": "d1",
                  "date": "2025-01-21"},
            "b": {"debate": "A Bill (Twenty First sitting)", "debate_id": "d2",
                  "date": "2025-03-11"},
            # Hansard's own typo, seen on the Terminally Ill Adults Bill:
            # "(Nineteeth sitting)". The pattern must not require correct
            # spelling of the ordinal, only the word "sitting".
            "c": {"debate": "A Bill (Nineteeth sitting)", "debate_id": "d3",
                  "date": "2025-03-05"},
            "d": {"debate": "A Bill: Second Reading", "debate_id": "d4",
                  "date": "2024-11-29"},
            "e": {"debate": "Another Bill (First sitting)", "debate_id": "d5",
                  "date": "2025-01-21"},
        }

    def test_only_this_bill_s_sittings_match(self):
        got = pbc.sittings_from_archive(self.FakeRaw(), "A Bill")
        self.assertEqual(set(got), {"d1", "d2", "d3"})
        self.assertEqual(got["d1"], ("2025-01-21", "First sitting"))


class ResolveTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        db.init_db(self.conn)
        for mid, name, list_as in ((1, "Danny Kruger", "Kruger, Danny"),
                                   (2, "Dr Simon Opher", "Opher, Dr Simon"),
                                   (3, "John Smith", None),
                                   (4, "John Smith", None)):
            members.cache_put(self.conn, members.Member(
                id=mid, name=name, party="X", seat="Seat", house="Commons",
                since="2024-07-04", list_as=list_as))
        self.index = pbc.resolve(self.conn)

    def test_honourifics_do_not_block_a_match(self):
        self.assertEqual(self.index[pbc.norm("Dr Simon Opher")], 2)
        self.assertEqual(self.index[pbc.norm("Simon Opher")], 2)

    def test_list_as_is_unfolded_from_surname_first(self):
        self.assertEqual(self.index[pbc.norm("Danny Kruger")], 1)

    def test_two_members_with_one_name_resolve_to_no_claim(self):
        # Guessing between them would put one member's attendance on the
        # other's record. NULL and a printed warning is the honest answer.
        self.assertIsNone(self.index[pbc.norm("John Smith")])


class StoreShapeTests(unittest.TestCase):
    def test_the_table_is_created_by_init_db_not_the_tool(self):
        # The sp_scored lesson: a table the tool creates exists only where
        # the tool has run. init_db must know it, so the CI store and every
        # fresh test connection agree on the schema.
        conn = sqlite3.connect(":memory:")
        db.init_db(conn)
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(committee_attendance)")]
        self.assertEqual(cols, ["bill", "debate_id", "sitting", "date",
                                "member_id", "name", "role", "attended"])

    def test_no_page_reads_the_table_yet(self):
        """COLLECTED BUT NOT DISPLAYED (Christopher, 2026-08-31). When a
        page starts reading committee_attendance, this test should be
        replaced by tests of what it shows."""
        for fname in ("make_vote_tracker.py", "make_msp_votes.py"):
            path = os.path.join(ROOT, "tools", fname)
            with open(path, encoding="utf-8") as fh:
                self.assertNotIn("committee_attendance", fh.read(),
                                 "{0} reads the attendance table; the "
                                 "collect-only decision has been overtaken "
                                 "-- update this test deliberately".format(fname))


if __name__ == "__main__":
    unittest.main()
