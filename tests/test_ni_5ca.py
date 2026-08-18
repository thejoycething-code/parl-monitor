"""The NI 5CA sheet: placement only from human-confirmed meaning lines.

The rule under test is the no-scoring boundary: a Claude-drafted reading in
config/ni_stance.yaml must be able to render evidence WITHOUT moving a single
MLA into a column. Fixtures use the real doc_ids and the real amendment
readings so the tests double as documentation of the three live divisions.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from src import db
import ni_5ca

GASTON_97 = {"doc_id": "493329", "bill": "Justice Bill", "amendment": 97,
             "aye": 2, "why_aye": "single-sex accommodation",
             "no": -2, "why_no": "against the safeguard"}


def seed(conn):
    conn.execute("INSERT INTO ni_members (person_id, name, display_name, "
                 "party, constituency, first_seen, last_seen) VALUES "
                 "('5340','Beattie','Mr Doug Beattie MC','Ulster Unionist "
                 "Party','Upper Bann','2026-08-18','2026-08-18')")
    conn.execute("INSERT INTO ni_members (person_id, name, display_name, "
                 "party, constituency, first_seen, last_seen) VALUES "
                 "('5797','Aiken','Dr Steve Aiken OBE','Ulster Unionist "
                 "Party','South Antrim','2026-08-18','2026-08-18')")
    conn.execute("INSERT INTO ni_divisions (doc_id, subject, bill, dated, "
                 "kind, areas, amendment_no, watched, first_seen, last_seen) "
                 "VALUES ('493329','Amendment 97 ...','Justice Bill',"
                 "'2026-06-30','Simple Majority','[5]',97,1,"
                 "'2026-08-18','2026-08-18')")
    conn.execute("INSERT INTO ni_votes (doc_id, person_id, member, vote, "
                 "designation, captured_at) VALUES ('493329','5340',"
                 "'Mr Doug Beattie MC','aye','Unionist','2026-08-18')")
    conn.commit()


class LoadStanceTests(unittest.TestCase):
    def _load(self, text):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
            fh.write(text)
            path = fh.name
        try:
            return ni_5ca.load_stance(path)
        finally:
            os.unlink(path)

    def test_unquoted_no_key_is_normalised(self):
        """YAML 1.1 parses a bare `no:` key as boolean False. An edit that
        drops the quotes must not silently lose the no-lobby meaning."""
        entries = self._load(
            "divisions:\n  - doc_id: '1'\n    aye: 2\n    no: -2\n")
        self.assertEqual(entries["1"]["no"], -2)

    def test_quoted_no_key_also_works(self):
        entries = self._load(
            "divisions:\n  - doc_id: '1'\n    aye: 2\n    \"no\": -2\n")
        self.assertEqual(entries["1"]["no"], -2)

    def test_missing_file_is_empty_not_an_error(self):
        self.assertEqual(ni_5ca.load_stance("/nonexistent/ni_stance.yaml"), {})


class VoteStanceTests(unittest.TestCase):
    def test_a_draft_entry_places_nobody(self):
        """The no-scoring boundary: a Claude-drafted reading renders evidence
        but must never move an MLA into a column."""
        entry = dict(GASTON_97, draft=True)
        self.assertEqual(ni_5ca.vote_stance(entry, "aye"), (None, None))
        self.assertEqual(ni_5ca.vote_stance(entry, "no"), (None, None))

    def test_a_confirmed_entry_scores_both_lobbies(self):
        self.assertEqual(ni_5ca.vote_stance(GASTON_97, "aye"),
                         (2, "single-sex accommodation"))
        self.assertEqual(ni_5ca.vote_stance(GASTON_97, "no"),
                         (-2, "against the safeguard"))

    def test_an_abstention_is_not_a_direction(self):
        self.assertEqual(ni_5ca.vote_stance(GASTON_97, "abstain"), (None, None))


class PlaceTests(unittest.TestCase):
    def test_most_directional_wins(self):
        column, conflict, decided = ni_5ca.place(
            [(1, "2026-01-01", "a"), (2, "2025-01-01", "b")])
        self.assertEqual(column, "++")
        self.assertFalse(conflict)
        self.assertEqual(decided[2], "b")

    def test_conflict_is_flagged_never_averaged(self):
        """+2 and -1 is a flagged ++, not a quiet +0.5 -- the stance.py
        discipline: the tool will not cancel a vote against a vote."""
        column, conflict, _ = ni_5ca.place(
            [(2, "2026-01-01", "a"), (-1, "2026-02-01", "b")])
        self.assertEqual(column, "++")
        self.assertTrue(conflict)

    def test_no_scored_votes_is_the_zero_column(self):
        self.assertEqual(ni_5ca.place([]), ("0", False, None))


class BuildRowsTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))
        seed(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_draft_yields_evidence_but_no_placement(self):
        rows = ni_5ca.build_rows(self.conn, 5,
                                 {"493329": dict(GASTON_97, draft=True)})
        beattie = next(r for r in rows if "Beattie" in r["decision_maker"])
        self.assertEqual(beattie["column"], "0")
        self.assertEqual(beattie["n_events"], 1)
        self.assertIn("DRAFT", " | ".join(beattie["comments"]))

    def test_confirmed_entry_places_the_voter(self):
        rows = ni_5ca.build_rows(self.conn, 5, {"493329": GASTON_97})
        beattie = next(r for r in rows if "Beattie" in r["decision_maker"])
        self.assertEqual(beattie["column"], "++")
        self.assertEqual(beattie["designation"], "Unionist")
        self.assertIn("single-sex accommodation",
                      " | ".join(beattie["comments"]))

    def test_a_non_voter_reads_no_recorded_activity(self):
        rows = ni_5ca.build_rows(self.conn, 5, {"493329": GASTON_97})
        aiken = next(r for r in rows if "Aiken" in r["decision_maker"])
        self.assertEqual(aiken["column"], "0")
        self.assertEqual(aiken["comments"],
                         ["No recorded activity on this area"])

    def test_a_question_is_evidence_but_never_places(self):
        self.conn.execute(
            "INSERT INTO ni_items (id, kind, reference, title, dated, areas, "
            "tabler_person_id, first_seen, last_seen) VALUES "
            "('ni-question:1','question','AQW 1/26','On single-sex wards',"
            "'2026-01-01','[5]','5797','2026-08-18','2026-08-18')")
        self.conn.commit()
        rows = ni_5ca.build_rows(self.conn, 5, {})
        aiken = next(r for r in rows if "Aiken" in r["decision_maker"])
        self.assertEqual(aiken["column"], "0",
                         "activity is not direction; a question must not place")
        self.assertIn("activity, not direction",
                      " | ".join(aiken["comments"]))

    def test_wrong_area_contributes_nothing(self):
        rows = ni_5ca.build_rows(self.conn, 1, {"493329": GASTON_97})
        beattie = next(r for r in rows if "Beattie" in r["decision_maker"])
        self.assertEqual((beattie["column"], beattie["n_events"]), ("0", 0))


if __name__ == "__main__":
    unittest.main()
