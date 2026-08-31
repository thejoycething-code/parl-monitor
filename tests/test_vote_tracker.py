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


class OfficialRecordUrlTests(unittest.TestCase):
    """The official-record link must point at the division's OWN house.
    Hardcoded /Commons/, a Lords division's link landed on whatever
    unrelated Commons division shared its number -- Lord Alton's
    assisted-dying rows pointed at other business entirely (Christopher,
    2026-08-31)."""

    def test_a_lords_division_links_to_the_lords_record(self):
        conn = fresh_conn()
        members.cache_put(conn, members.Member(
            id=1, name="Aye MP", party="Labour", seat="Seat",
            house="Commons", since="2024-07-04", list_as="Aye MP"))
        conn.execute("UPDATE members SET current_mp = 1")
        conn.commit()
        import copy
        cfg = copy.deepcopy(CFG)
        cfg["divisions"][0]["house"] = "lords"
        dataset, _ = mvt.build(conn, cfg, {900: PAYLOAD})
        self.assertEqual(dataset["divisions"][0]["url"],
                         "https://votes.parliament.uk/Votes/Lords/Division/900")
        cfg["divisions"][0]["house"] = "commons"
        dataset, _ = mvt.build(conn, cfg, {900: PAYLOAD})
        self.assertEqual(dataset["divisions"][0]["url"],
                         "https://votes.parliament.uk/Votes/Commons/Division/900")


class PartyHistoryTests(unittest.TestCase):
    """The shipped spell history (2026-08-31): collapsed, and kept past the
    last division, because the page now DISPLAYS it as well as whipping by
    it. Kruger's card says Reform UK over votes cast as a Conservative; the
    "Conservative until 15 Sep 2025" line is built from these spells."""

    def build_with(self, spells, division_date="2019-12-20"):
        # The division is backdated so the spells under test all POSTDATE
        # the earliest tracked division: spells ending before it are dropped
        # before the collapse ever sees them, deliberately -- a party held
        # before any tracked vote makes no claim the page needs to qualify.
        conn = fresh_conn()
        members.cache_put(conn, members.Member(
            id=1, name="Aye MP", party=spells[-1][0], seat="Seat",
            house="Commons", since="2024-07-04", list_as="Aye MP"))
        conn.execute("UPDATE members SET current_mp = 1")
        for party, started, ended in spells:
            conn.execute(
                "INSERT INTO member_party (member_id, party, started, ended) "
                "VALUES (1, ?, ?, ?)", (party, started, ended))
        conn.commit()
        payload = dict(PAYLOAD, Date=division_date + "T00:00:00")
        dataset, _ = mvt.build(conn, CFG, {900: payload})
        return dataset["members"][0]["parties"]

    def test_same_party_re_elections_collapse_to_one_spell(self):
        # Parliament records each Parliament separately, so nearly every
        # member has one spell per election of the SAME party. Shipped raw,
        # every display would re-derive "did anything change".
        got = self.build_with([("Conservative", "2019-12-12", "2024-05-30"),
                               ("Conservative", "2024-07-04", "2025-09-15"),
                               ("Reform UK", "2025-09-15", None)])
        self.assertEqual(got, [["Conservative", "2019-12-12", "2025-09-15"],
                               ["Reform UK", "2025-09-15", None]])

    def test_a_switch_after_the_last_tracked_division_still_ships(self):
        # The division is 2025-06-20. The old filter dropped spells starting
        # later as unable to touch a division -- true for the whip, wrong
        # for the display: the member whose card most needs the note is the
        # one who crossed the floor after the last vote.
        got = self.build_with([("Conservative", "2024-07-04", "2025-09-15"),
                               ("Reform UK", "2025-09-15", None)])
        self.assertEqual([p[0] for p in got], ["Conservative", "Reform UK"])

    def test_a_spell_ending_before_the_earliest_division_is_dropped(self):
        # A party held before any tracked vote qualifies nothing on the
        # page; the note it would generate is noise, so it never ships.
        got = self.build_with([("Labour", "1997-05-01", "2005-05-05"),
                               ("Conservative", "2024-07-04", None)])
        self.assertEqual([p[0] for p in got], ["Conservative"])

    def test_a_genuine_change_between_divisions_is_never_collapsed(self):
        got = self.build_with([("Labour", "2024-07-04", "2025-01-01"),
                               ("Independent", "2025-01-01", "2025-03-01"),
                               ("Labour", "2025-03-01", None)])
        self.assertEqual([p[0] for p in got],
                         ["Labour", "Independent", "Labour"])


class UpcomingIssueTests(unittest.TestCase):
    """An issue with no divisions ships only when marked `upcoming` -- the
    2026 Bill's card (Christopher, 2026-08-31: "two separate Bills")."""

    def build(self, extra_issue):
        conn = fresh_conn()
        members.cache_put(conn, members.Member(
            id=1, name="Aye MP", party="Labour", seat="Seat",
            house="Commons", since="2024-07-04", list_as="Aye MP"))
        conn.execute("UPDATE members SET current_mp = 1")
        conn.commit()
        import copy
        cfg = copy.deepcopy(CFG)
        cfg["issues"].append(extra_issue)
        dataset, _ = mvt.build(conn, cfg, {900: PAYLOAD})
        return {i["id"] for i in dataset["issues"]}

    def test_an_upcoming_issue_ships_without_divisions(self):
        got = self.build({"id": "fresh", "name": "Fresh Bill", "area": 2,
                          "bill": "A Bill", "upcoming": True})
        self.assertIn("fresh", got)

    def test_a_division_less_issue_without_the_flag_still_does_not(self):
        # The old rule stands for everything else: an issue nothing uses is
        # dead config, not a card.
        got = self.build({"id": "dormant", "name": "Dormant", "area": 2,
                          "bill": "B Bill"})
        self.assertNotIn("dormant", got)


class BoardNextTests(unittest.TestCase):
    """The forward look (2026-08-31): an issue naming a board_id gets the
    bills board's next date attached, so "what happens next" tracks the
    weekly board refresh instead of a hand-edited status line."""

    def build_with(self, row, board_id=4157):
        conn = fresh_conn()
        members.cache_put(conn, members.Member(
            id=1, name="Aye MP", party="Labour", seat="Seat",
            house="Commons", since="2024-07-04", list_as="Aye MP"))
        conn.execute("UPDATE members SET current_mp = 1")
        if row:
            conn.execute(
                "INSERT INTO bills_board (bill_id, title, house, stage, "
                "next_key_date, what_next, status) VALUES (?,?,?,?,?,?,?)", row)
        conn.commit()
        import copy
        cfg = copy.deepcopy(CFG)
        cfg["issues"][0]["board_id"] = board_id
        cfg["issues"][0]["action"] = {"url": "https://citizengo.org/x",
                                      "label": "Sign"}
        dataset, _ = mvt.build(conn, cfg, {900: PAYLOAD})
        return dataset["issues"][0]

    def test_a_live_bill_with_a_real_date_ships_the_forward_look(self):
        issue = self.build_with(
            (4157, "A Bill", "Commons", "2nd reading", "2026-09-11", None, "live"))
        self.assertEqual(issue["next"], {"stage": "2nd reading",
                                         "house": "Commons",
                                         "date": "2026-09-11"})

    def test_what_next_outranks_the_stage_when_the_board_has_it(self):
        issue = self.build_with(
            (4157, "A Bill", "Commons", "2nd reading", "2026-09-11",
             "Second Reading debate", "live"))
        self.assertEqual(issue["next"]["stage"], "Second Reading debate")

    def test_a_closed_bill_ships_nothing(self):
        # Its story belongs to the editorial status line; a forward date on
        # a fallen bill would be a promise the order paper does not make.
        issue = self.build_with(
            (4157, "A Bill", "Lords", "Committee stage", "TBA", None, "closed"))
        self.assertNotIn("next", issue)

    def test_tba_is_the_board_s_honest_unknown_and_ships_nothing(self):
        issue = self.build_with(
            (4157, "A Bill", "Commons", "2nd reading", "TBA", None, "live"))
        self.assertNotIn("next", issue)

    def test_a_missing_board_row_ships_nothing_and_does_not_crash(self):
        issue = self.build_with(None)
        self.assertNotIn("next", issue)

    # ---- the action dies only when the Bill has (Christopher, 2026-08-31:
    # "the petition only dies once the Bill has") ---------------------------
    def test_the_action_ships_while_the_bill_is_live(self):
        issue = self.build_with(
            (4157, "A Bill", "Commons", "2nd reading", "2026-09-11", None, "live"))
        self.assertEqual(issue["action"]["label"], "Sign")

    def test_the_action_retires_when_the_bill_falls(self):
        # Gated in the builder, not the template, so a retired button
        # leaves the payload too -- no dead petition link ships to 1,144
        # member pages waiting for a template check to hide it.
        issue = self.build_with(
            (4157, "A Bill", "Lords", "Committee stage", "TBA", None, "closed"))
        self.assertNotIn("action", issue)

    def test_royal_assent_also_retires_it(self):
        # An enacted Bill is beyond stopping: not "died", but the petition's
        # object is gone either way, and a stop-the-Bill button on an Act
        # would mislead. Both closed outcomes retire the button.
        issue = self.build_with(
            (4157, "An Act", "Unassigned", "Royal Assent", "TBA", None, "closed"))
        self.assertNotIn("action", issue)

    # ---- the tracking mark (Christopher, 2026-08-31) ---------------------
    def test_a_shipped_action_carries_the_monitor_utms(self):
        # "All petition UTMs from the parliamentary monitor should include
        # cgo-monitor somewhere" -- and in the CAMPAIGN value too
        # (Christopher, 2026-08-31), so a campaign-level report shows the
        # monitor without joining on source. The issue id rides behind the
        # prefix to say which card converted.
        issue = self.build_with(
            (4157, "A Bill", "Commons", "2nd reading", "2026-09-11", None, "live"))
        self.assertEqual(issue["action"]["url"],
                         "https://citizengo.org/x?utm_source=cgo-monitor"
                         "&utm_medium=referral&utm_campaign=cgo-monitor-iss")

    def test_a_hand_tuned_url_with_its_own_utms_is_left_alone(self):
        conn = fresh_conn()
        members.cache_put(conn, members.Member(
            id=1, name="Aye MP", party="Labour", seat="Seat",
            house="Commons", since="2024-07-04", list_as="Aye MP"))
        conn.execute("UPDATE members SET current_mp = 1")
        conn.commit()
        import copy
        cfg = copy.deepcopy(CFG)
        cfg["issues"][0]["action"] = {
            "url": "https://citizengo.org/x?utm_source=cgo-monitor-special",
            "label": "Sign"}
        dataset, _ = mvt.build(conn, cfg, {900: PAYLOAD})
        self.assertEqual(dataset["issues"][0]["action"]["url"],
                         "https://citizengo.org/x?utm_source=cgo-monitor-special")

    def test_a_missing_board_row_KEEPS_the_action(self):
        # The first cut retired it here, which meant a board hiccup -- or
        # the gap between a bill falling and its successor being re-pointed
        # -- silently pulled a live petition from every page. Absence of
        # evidence is not a death certificate: the button stays until the
        # board records the Bill's end.
        issue = self.build_with(None)
        self.assertEqual(issue["action"]["label"], "Sign")

    def test_an_issue_without_a_board_id_keeps_its_action(self):
        # Nothing to gate on: the config documents that an ungated action
        # always ships, and the builder must not invent a gate.
        conn = fresh_conn()
        members.cache_put(conn, members.Member(
            id=1, name="Aye MP", party="Labour", seat="Seat",
            house="Commons", since="2024-07-04", list_as="Aye MP"))
        conn.execute("UPDATE members SET current_mp = 1")
        conn.commit()
        import copy
        cfg = copy.deepcopy(CFG)
        cfg["issues"][0]["action"] = {"url": "https://citizengo.org/x",
                                      "label": "Sign"}
        dataset, _ = mvt.build(conn, cfg, {900: PAYLOAD})
        self.assertEqual(dataset["issues"][0]["action"]["label"], "Sign")


if __name__ == "__main__":
    unittest.main()
