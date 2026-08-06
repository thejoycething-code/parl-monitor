"""MP vote tracker: the accuracy guardrails that protect its credibility."""

import importlib.util
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, members

spec = importlib.util.spec_from_file_location(
    "mvt", os.path.join(ROOT, "tools", "make_vote_tracker.py"))
mvt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mvt)


def fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return db.init_db(conn)


PAYLOAD = {
    "DivisionId": 900, "Title": "A Bill: Third Reading", "Date": "2025-06-20T00:00:00",
    "AyeCount": 2, "NoCount": 1,
    "Ayes": [{"MemberId": 1, "Party": "Labour"}, {"MemberId": 2, "Party": "Conservative"}],
    "Noes": [{"MemberId": 3, "Party": "Conservative"}],
    "AyeTellers": [{"MemberId": 4, "Party": "Labour"}],
    "NoTellers": [],
    "NoVoteRecorded": [{"MemberId": 5, "Party": "Deputy Speaker"},
                       {"MemberId": 6, "Party": "Labour"}],
}

CFG = {
    "issues": [{"id": "iss", "name": "An issue", "area": 2, "bill": "A Bill",
                "note": "n", "status": "s"},
               {"id": "unused", "name": "Not shown", "area": 1, "bill": "B",
                "note": "n", "status": "s"}],
    "divisions": [{"id": 900, "issue": "iss", "stage": "Third Reading",
                   "stage_group": "Third Reading", "landmark": True,
                   "signed_off": False, "our_side": "no", "short": "Third Reading",
                   "context": "", "meaning_aye": "aye means", "meaning_no": "no means"}],
}


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_conn()
        for mid, name, party, since in (
                (1, "Aye MP", "Labour", "2024-07-04"),
                (3, "No MP", "Conservative", "2024-07-04"),
                (4, "Teller MP", "Labour", "2024-07-04"),
                (5, "Deputy MP", "Labour", "2024-07-04"),
                (6, "Silent MP", "Labour", "2024-07-04"),
                (7, "New MP", "Labour", "2025-05-01"),        # by-election
                (8, "Speaker MP", "Speaker", "2024-07-04"),
                (9, "Abstentionist MP", "Sinn Féin", "2024-07-04")):
            members.cache_put(self.conn, members.Member(
                id=mid, name=name, party=party, seat="Seat", house="Commons",
                since=since, list_as=name))
        self.conn.execute("UPDATE members SET current_mp = 1")
        self.conn.commit()
        self.dataset, self.missing = mvt.build(self.conn, CFG, {900: PAYLOAD})
        self.by_name = {m["name"]: m for m in self.dataset["members"]}

    def test_every_vote_code_is_carried_including_tellers_and_no_record(self):
        self.assertEqual(self.by_name["Aye MP"]["votes"], {900: "A"})
        self.assertEqual(self.by_name["No MP"]["votes"], {900: "N"})
        self.assertEqual(self.by_name["Teller MP"]["votes"], {900: "TA"})
        # No vote recorded is stored as such: it is NOT an abstention, because
        # the Commons does not record abstentions.
        self.assertEqual(self.by_name["Silent MP"]["votes"], {900: "X"})

    def test_deputy_speaker_detected_from_the_payload(self):
        self.assertEqual(self.by_name["Deputy MP"]["role"], "deputy")

    def test_speaker_and_sinn_fein_roles_from_party(self):
        self.assertEqual(self.by_name["Speaker MP"]["role"], "speaker")
        self.assertEqual(self.by_name["Abstentionist MP"]["role"], "sf")

    def test_by_election_member_keeps_a_start_date_after_the_division(self):
        # The view renders "Not yet an MP" from this; without the date it
        # would wrongly read as a member who chose not to vote.
        self.assertEqual(self.by_name["New MP"]["since"], "2025-05-01")
        self.assertEqual(self.by_name["New MP"]["votes"], {})

    def test_unused_issues_are_not_shipped(self):
        self.assertEqual([i["id"] for i in self.dataset["issues"]], ["iss"])

    def test_division_carries_meaning_and_sign_off_state(self):
        d = self.dataset["divisions"][0]
        self.assertEqual((d["ayes"], d["noes"], d["passed"]), (2, 1, True))
        self.assertEqual(d["meaning_aye"], "aye means")
        self.assertFalse(d["signed_off"])
        self.assertEqual(d["url"],
                         "https://votes.parliament.uk/Votes/Commons/Division/900")

    def test_labour_co_op_normalised_but_party_kept_otherwise(self):
        members.cache_put(self.conn, members.Member(
            id=10, name="Co-op MP", party="Labour (Co-op)", seat="S",
            house="Commons", since="2024-07-04", list_as="Co-op MP"))
        self.conn.execute("UPDATE members SET current_mp = 1")
        dataset, _ = mvt.build(self.conn, CFG, {900: PAYLOAD})
        self.assertEqual(
            next(m for m in dataset["members"] if m["name"] == "Co-op MP")["party"],
            "Labour")

    def test_missing_payload_is_reported_not_silently_dropped(self):
        dataset, missing = mvt.build(self.conn, CFG, {})
        self.assertEqual(missing, [900])
        self.assertEqual(dataset["divisions"], [])


class MemberParsingTests(unittest.TestCase):
    def test_since_takes_the_later_of_the_two_api_dates(self):
        """Continuously-serving and returning members carry the two dates the
        other way round; the later one starts the current period in both."""
        value = {"id": 1, "nameDisplayAs": "A MP", "nameListAs": "MP, A",
                 "latestParty": {"name": "Labour"},
                 "latestHouseMembership": {
                     "membershipFrom": "Seat", "house": 1,
                     "membershipStartDate": "2019-12-12T00:00:00",
                     "membershipStatus": {"statusStartDate": "2024-07-04T00:00:00"}}}
        self.assertEqual(members.parse_member(value).since, "2024-07-04")
        value["latestHouseMembership"]["membershipStartDate"] = "2025-05-01T00:00:00"
        self.assertEqual(members.parse_member(value).since, "2025-05-01")

    def test_seeding_from_a_division_does_not_blank_a_known_start_date(self):
        conn = fresh_conn()
        members.cache_put(conn, members.Member(1, "A", "Lab", "S", "Commons",
                                               since="2024-07-04", list_as="A"))
        members.cache_put(conn, members.Member(1, "A", "Lab", "S", "Commons"))
        self.assertEqual(members.cache_get(conn, 1).since, "2024-07-04")


if __name__ == "__main__":
    unittest.main()
