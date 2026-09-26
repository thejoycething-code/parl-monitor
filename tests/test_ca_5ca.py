"""The Canadian 5CA (tools/ca_5ca.py). No network."""

import csv
import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db  # noqa: E402


def _load():
    spec = importlib.util.spec_from_file_location("ca_5ca", os.path.join(ROOT, "tools", "ca_5ca.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


c5 = _load()

# Four MPs. Ally voted for C-314 and for the C-62 delay; Opponent against both;
# Missed voted for C-314 and then missed the later decisive division; Gone
# voted and has left the House.
MEMBERS = [("1", "Ally Member", "Conservative", "Riding One", 1),
           ("2", "Opponent Member", "Liberal", "Riding Two", 1),
           ("3", "Missed Member", "Conservative", "Riding Three", 1),
           ("4", "Gone Member", "Conservative", "Riding Four", 0),
           ("5", "Silent Member", "Liberal", "Riding Five", 1)]
DIVISIONS = [
    # key, date, subject, areas
    ("commons-44-1-423", "2023-10-18T18:00:00", "2nd reading of Bill C-314", "[2]"),
    ("commons-44-1-646", "2024-02-15T18:00:00", "3rd reading of Bill C-62", "[2]"),
    ("commons-44-1-900", "2024-06-01T18:00:00", "A later decisive MAID vote", "[2]"),
]
VOTES = {
    "commons-44-1-423": {"1": "Yea", "2": "Nay", "3": "Yea", "4": "Yea"},
    "commons-44-1-646": {"1": "Yea", "2": "Nay", "3": "Yea"},
    "commons-44-1-900": {"1": "Yea", "2": "Nay", "4": "Paired"},
}
ENTRIES = {
    "commons-44-1-423": {"key": "commons-44-1-423", "yea": 2, "nay": -2,
                         "why_yea": "for the exclusion", "why_nay": "against it"},
    "commons-44-1-646": {"key": "commons-44-1-646", "yea": 1, "nay": -2,
                         "why_yea": "for the delay", "why_nay": "against the delay"},
    "commons-44-1-900": {"key": "commons-44-1-900", "yea": 2, "nay": -2,
                         "why_yea": "for", "why_nay": "against"},
}


def store(divisions=DIVISIONS, votes=VOTES):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    ca_store.ensure_schema(conn)
    for pid, name, party, riding, sitting in MEMBERS:
        conn.execute("INSERT INTO ca_members (person_id, name, party, constituency, province, sitting) "
                     "VALUES (?,?,?,?,?,?)", (pid, name, party, riding, "Alberta", sitting))
    for key, date, subject, areas in divisions:
        _, parl, sess, number = key.split("-")
        conn.execute("INSERT INTO ca_divisions (division_key, chamber, parliament, session, number, "
                     "date, subject, result, areas, positions_fetched) VALUES (?,?,?,?,?,?,?,?,?,1)",
                     (key, "commons", int(parl), int(sess), int(number), date, subject, "Agreed To", areas))
        for pid, pos in votes.get(key, {}).items():
            conn.execute("INSERT INTO ca_votes (division_key, person_id, position, party) VALUES (?,?,?,?)",
                         (key, pid, pos, "x"))
    conn.commit()
    return conn


def rows_by_id(conn, entries=ENTRIES, bills=None, area=2, chamber="commons"):
    rows, _, latest = c5.build_rows(conn, area, chamber, entries, bills or {}, today="2026-09-26")
    return {r["person_id"]: r for r in rows}, latest


class StatusTests(unittest.TestCase):
    def test_draft_unread_and_unplaceable_place_nobody(self):
        self.assertEqual(c5.status({"yea": 2, "nay": -2, "draft": True}), "draft")
        self.assertEqual(c5.status({"read_first": "x", "draft": True}), "unread",
                         "no values: deleting the draft flag must not confirm nothing")
        self.assertEqual(c5.status({"placeable": False, "reason": "unanimous"}), "unplaceable")
        self.assertEqual(c5.status({"yea": 2, "nay": -2}), "confirmed")
        self.assertEqual(c5.vote_stance({"yea": 2, "nay": -2, "draft": True}, "Yea"), (None, None))


class PlacementTests(unittest.TestCase):
    def test_a_draft_file_places_nobody(self):
        drafts = {k: dict(v, draft=True) for k, v in ENTRIES.items()}
        rows, _ = rows_by_id(store(), entries=drafts)
        self.assertTrue(all(r["column"] == "0" for r in rows.values()))
        self.assertIn("reading DRAFT -- not placed", " ".join(rows["1"]["comments"]))

    def test_confirmed_readings_place_by_the_strongest_vote(self):
        rows, _ = rows_by_id(store())
        self.assertEqual(rows["1"]["column"], "++")
        self.assertEqual(rows["2"]["column"], "--")

    def test_missing_the_latest_decisive_division_caps_at_plus(self):
        """The Westminster lesson of 21 September 2026."""
        rows, latest = rows_by_id(store())
        self.assertEqual(latest["division_key"], "commons-44-1-900")
        self.assertEqual(rows["3"]["column"], "+")
        self.assertTrue(rows["3"]["capped"])
        self.assertTrue(rows["3"]["comments"][0].startswith("CAPPED at +"))

    def test_a_plus_one_vote_is_not_decisive(self):
        """Missing C-62's delay (+1) must not cap a C-314 Yea voter."""
        divisions = DIVISIONS[:2]
        votes = {"commons-44-1-423": {"1": "Yea", "3": "Yea", "2": "Nay"},
                 "commons-44-1-646": {"1": "Yea", "2": "Nay"}}
        rows, latest = rows_by_id(store(divisions, votes))
        self.assertEqual(latest["division_key"], "commons-44-1-423")
        self.assertEqual(rows["3"]["column"], "++")

    def test_a_paired_vote_is_no_direction(self):
        rows, _ = rows_by_id(store())
        self.assertIn("[no direction recorded]", " ".join(rows["4"]["comments"]))

    def test_a_former_member_who_voted_is_listed_and_labelled(self):
        rows, _ = rows_by_id(store())
        self.assertIn("[FORMER]", rows["4"]["decision_maker"])
        self.assertFalse(rows["4"]["sitting"])

    def test_a_sitting_member_with_no_row_did_not_vote(self):
        rows, _ = rows_by_id(store())
        self.assertIn("NO RECORDED VOTE", " ".join(rows["3"]["comments"]))
        self.assertEqual(rows["5"]["column"], "0")

    def test_a_sign_conflict_is_flagged_never_averaged(self):
        votes = dict(VOTES, **{"commons-44-1-646": {"1": "Yea", "2": "Yea", "3": "Yea"}})
        rows, _ = rows_by_id(store(votes=votes))
        self.assertEqual(rows["2"]["column"], "--", "-2 and +1 is a flagged -2, not -0.5")
        self.assertTrue(rows["2"]["comments"][0].startswith("MIXED RECORD"))

    def test_bill_sponsorship_places_only_when_confirmed(self):
        conn = store()
        conn.execute("INSERT INTO ca_bills (bill_key, parliament, session, number, long_title, "
                     "areas, sponsor_person_id) VALUES ('44-1/C-314', 44, 1, 'C-314', 'MAID bill', '[2]', '5')")
        draft = {"44-1/C-314": {"key": "44-1/C-314", "sponsored": 2, "draft": True, "why_sponsored": "x"}}
        rows, _ = rows_by_id(conn, bills=draft)
        self.assertEqual(rows["5"]["column"], "0")
        confirmed = {"44-1/C-314": {"key": "44-1/C-314", "sponsored": 2, "why_sponsored": "x"}}
        rows, _ = rows_by_id(conn, bills=confirmed)
        self.assertEqual(rows["5"]["column"], "++")

    def test_speeches_and_petitions_are_evidence_never_direction(self):
        conn = store()
        conn.execute("INSERT INTO ca_speeches (speech_id, sitting_key, date, subject, person_id, "
                     "areas, excerpt) VALUES ('s1', '45-1-142', '2026-09-23', 'Criminal Code', '5', '[2]', 'MAID must stop')")
        conn.execute("INSERT INTO ca_petitions (petition_id, presented_number, category, mp_person_id, "
                     "areas, signatures, presented) VALUES ('451-01196', '451-01196', 'Justice', '5', '[2]', 42, '2026-09-24')")
        rows, _ = rows_by_id(conn)
        joined = " ".join(rows["5"]["comments"])
        self.assertIn("SPEECH", joined)
        self.assertIn("does not imply endorsement", joined)
        self.assertEqual(rows["5"]["column"], "0")

    def test_comments_are_newest_first(self):
        rows, _ = rows_by_id(store())
        dates = [c5._line_date(c) for c in rows["1"]["comments"] if c5._line_date(c)]
        self.assertEqual(dates, sorted(dates, reverse=True))


class SheetTests(unittest.TestCase):
    def test_totals_count_sitting_members_only(self):
        rows, _ = rows_by_id(store())
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sheet.csv")
            tally = c5.write_sheet(path, list(rows.values()))
            last = list(csv.reader(open(path)))[-1]
        self.assertEqual(tally["++"], 1, "Gone Member voted Yea on C-314 and is not counted")
        self.assertIn("4 sitting decision-makers (1 former listed, not counted)", last[0])

    def test_the_lobby_check_applies_only_to_a_plus_two_side(self):
        conn = store()
        rows, _, latest = c5.build_rows(conn, 2, "commons", ENTRIES, {}, today="2026-09-26")
        votes_for = {"1": ("Yea", "x"), "2": ("Nay", "x")}
        pp, lobby, value = c5.lobby_check(rows, latest, ENTRIES, votes_for)
        self.assertEqual((pp, lobby, value), (1, 1, 2))


class SenateTests(unittest.TestCase):
    def test_seated_senators_come_from_the_latest_details_page(self):
        conn = store()
        conn.execute("INSERT INTO ca_divisions (division_key, chamber, parliament, session, number, "
                     "date, subject, result, areas, positions_fetched) VALUES "
                     "('senate-45-1-1', 'senate', 45, 1, 1, '2026-06-04', 'Combatting Hate Act – C-9 – Third Reading', "
                     "'Adopted', '[8]', 1)")
        for pid, name, pos in (("senator-1", "Martin, Yonah", "Nay"), ("senator-2", "Pate, Kim", "Yea"),
                               ("senator-3", "Absent, Anne", "Did not vote")):
            conn.execute("INSERT INTO ca_senators (person_id, name, affiliation, province) VALUES (?,?,?,?)",
                         (pid, name, "C", "BC"))
            conn.execute("INSERT INTO ca_votes (division_key, person_id, position, party) VALUES (?,?,?,?)",
                         ("senate-45-1-1", pid, pos, "C"))
        conn.execute("INSERT INTO ca_senators (person_id, name, affiliation, province) VALUES "
                     "('senator-9', 'Retired, Rob', 'C', 'BC')")
        entries = {"senate-45-1-1": {"key": "senate-45-1-1", "yea": -2, "nay": 1,
                                     "why_yea": "passed it", "why_nay": "opposed it"}}
        rows, _ = rows_by_id(conn, entries=entries, area=8, chamber="senate")
        self.assertEqual(rows["senator-1"]["column"], "+")
        self.assertEqual(rows["senator-2"]["column"], "--")
        self.assertIn("DID NOT VOTE", " ".join(rows["senator-3"]["comments"]))
        self.assertNotIn("senator-9", rows, "not seated, no vote on the area: stays off")


class StanceFileTests(unittest.TestCase):
    def test_the_real_stance_file_loads_and_nothing_in_it_is_confirmed_yet(self):
        """Every Canadian reading is a Claude draft until Christopher confirms
        it. If this starts failing because an entry lost its draft flag, check
        that a HUMAN removed it -- then update this test."""
        entries = list(c5.load_stance(section="divisions").values()) + \
            list(c5.load_stance(section="bills").values())
        self.assertGreater(len(entries), 20)
        self.assertEqual([e["key"] for e in entries if c5.status(e) == "confirmed"], [])


if __name__ == "__main__":
    unittest.main()
