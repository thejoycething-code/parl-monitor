"""The Canadian 5CA (tools/ca_5ca.py). No network."""

import csv
import json
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

    def test_a_confirmed_entry_may_score_one_side_only(self):
        """commons-44-1-640 scores the Yea and leaves the Nay blank on purpose."""
        entries = dict(ENTRIES)
        entries["commons-44-1-646"] = {"key": "commons-44-1-646", "yea": -2, "why_yea": "for expansion"}
        rows, _ = rows_by_id(store(), entries=entries)
        self.assertIn("this side carries no value", " ".join(rows["2"]["comments"]))
        self.assertEqual(rows["2"]["column"], "--", "placed by its other votes, unharmed")

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

    def _pet(self, conn, pid, mp, prayer, when, sigs=10, score=None, why=None):
        conn.execute("INSERT INTO ca_petitions (petition_id, presented_number, category, prayer, "
                     "presented, mp_person_id, areas, signatures, triage_score, why_it_matters, "
                     "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                     (pid, pid, "Justice", prayer, when, mp, "[2]", sigs, score, why,
                      "2026-09-27", "2026-09-27"))

    def test_identical_petitions_are_one_line_with_a_count(self):
        """One MP presented the same MAID petition three times."""
        conn = store()
        for i, when in enumerate(("2026-02-01", "2026-03-01", "2026-04-01")):
            self._pet(conn, "451-0000%d" % i, "5", "Keep  MAID closed to mental illness.", when,
                      score=3, why="Repeal MAID MI-SUMC.")
        self._pet(conn, "451-00009", "5", "Protect conscience rights.", "2026-05-01")
        self._pet(conn, "451-00010", "1", "keep maid closed to mental illness.", "2026-05-02")
        conn.commit()
        rows, _ = rows_by_id(conn)
        lines = [l for l in rows["5"]["comments"] if "PETITION" in l]
        self.assertEqual(len(lines), 2, "one line per distinct text")
        maid = next(l for l in lines if "3 copies" in l)
        self.assertIn("3 copies, 2026-02-01 to 2026-04-01", maid)
        self.assertIn("30 signatures", maid)
        self.assertIn("also presented by 1 other MP(s)", maid)
        self.assertIn("judge 3", maid)
        self.assertIn("does not imply endorsement", maid)
        self.assertEqual(rows["5"]["column"], "0", "still evidence, never direction")

    def test_a_petition_the_judge_scored_zero_is_counted_not_listed(self):
        conn = store()
        self._pet(conn, "451-00050", "5", "Fund nuclear waste research.", "2026-05-01", score=0)
        conn.commit()
        rows, _ = rows_by_id(conn)
        joined = " ".join(rows["5"]["comments"])
        self.assertNotIn("451-00050", joined)
        self.assertIn("PETITIONS NOT LISTED: 1 presented that the judge scored 0", joined)

    def test_a_single_petition_keeps_its_own_number(self):
        conn = store()
        self._pet(conn, "451-00042", "5", "Protect conscience rights.", "2026-05-01")
        conn.commit()
        rows, _ = rows_by_id(conn)
        self.assertIn("PETITION 451-00042", " ".join(rows["5"]["comments"]))

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
    def test_the_real_stance_file_is_confirmed_and_the_senate_report_unscored(self):
        """Christopher, 2 October 2026: "Confirm the readings and leave the
        Senate report unscored." No draft remains, and the RIDR report on C-9
        is evidence only."""
        entries = list(c5.load_stance(section="divisions").values()) + \
            list(c5.load_stance(section="bills").values())
        self.assertGreater(len(entries), 20)
        confirmed_2_oct = ("commons-44-1-377", "commons-44-1-423", "commons-44-1-641", "commons-44-1-646",
                           "commons-44-1-640", "commons-44-1-874", "commons-44-1-609", "commons-45-1-86",
                           "commons-45-1-93", "commons-45-1-92", "commons-45-1-167", "senate-45-1-700362",
                           "senate-45-1-700344")
        divs = c5.load_stance(section="divisions")
        self.assertEqual([k for k in confirmed_2_oct if c5.status(divs[k]) != "confirmed"], [])
        # The 2010-2024 landmarks drafted on 3 October are drafts until he confirms.
        self.assertEqual(c5.status(divs["commons-41-1-466"]), "confirmed")   # 3 Oct 2026
        ridr = c5.load_stance(section="divisions")["senate-45-1-699935"]
        self.assertEqual(c5.status(ridr), "unplaceable")

    def test_the_read_first_entries_are_confirmed_with_their_text(self):
        """Drafted 2 October 2026 ("Draft the 10 'read first' readings") and
        confirmed the same day ("Confirm all the readings, score the C-279
        definition separately"): Motions 1-8 (642) stay evidence only, the
        definition of gender identity (643) is scored on its own at +/-1."""
        divs = c5.load_stance(section="divisions")
        read = ("commons-41-1-642", "commons-41-1-643", "commons-41-2-235",
                "senate-42-1-457865", "commons-44-1-853")
        self.assertEqual([k for k, e in divs.items() if c5.status(e) == "unread"], [])
        # Drafts remain only from 8 October 2026 (tested below); these are not among them.
        self.assertEqual([k for k in read if divs[k].get("draft")], [])
        for k in read:
            e = divs[k]
            self.assertTrue(e.get("text") and e.get("moved_by")
                            and e.get("source") and e.get("lobbies"), k)
        self.assertEqual(c5.status(divs["commons-41-1-642"]), "unplaceable")
        self.assertEqual({c5.status(divs[k]) for k in read[1:]}, {"confirmed"})
        self.assertEqual(c5.vote_stance(divs["commons-41-1-643"], "Yea")[0], -1)
        self.assertEqual(c5.vote_stance(divs["commons-41-1-643"], "Nay")[0], 1)

    def test_c11_scores_only_the_speech_amendments(self):
        """Christopher, 3 October 2026: "C-11, the Online Streaming Act, is on
        our ground but only score amendments specifically related to speech."
        Every 44-1 C-11 division has an entry; only the four Senate
        speech amendments carry values, and they are drafts until he
        confirms them. Each carries the text it was read from."""
        divs = c5.load_stance(section="divisions")
        speech = ("senate-44-1-598845", "senate-44-1-605567", "senate-44-1-598337", "senate-44-1-598860")
        evidence = ("commons-44-1-86", "commons-44-1-87", "commons-44-1-88", "commons-44-1-89",
                    "commons-44-1-149", "commons-44-1-150", "commons-44-1-158", "commons-44-1-159",
                    "commons-44-1-160", "commons-44-1-163", "commons-44-1-164", "commons-44-1-291",
                    "commons-44-1-292", "senate-44-1-579724", "senate-44-1-590158", "senate-44-1-597012",
                    "senate-44-1-598556", "senate-44-1-598861", "senate-44-1-604953", "senate-44-1-605386",
                    "senate-44-1-605586", "senate-44-1-605960")
        # Confirmed by Christopher, 3 October 2026 ("Confirm all the readings").
        self.assertEqual([k for k in speech if c5.status(divs.get(k)) != "confirmed"], [])
        self.assertEqual([k for k in evidence if c5.status(divs.get(k)) != "unplaceable"], [])
        for k in speech:
            self.assertTrue(divs[k].get("text") and divs[k].get("moved_by") and divs[k].get("source"), k)
        # Only the one whose sole effect is user uploads reaches +2.
        # "score Plett at +1" (Christopher, 3 October 2026).
        self.assertEqual(divs["senate-44-1-598845"]["yea"], 1)
        self.assertEqual({divs[k]["yea"] for k in speech[1:]}, {1})

    def test_the_8_october_readings_are_drafts_with_their_text(self):
        """Christopher, 8 October 2026: draft readings for every federal
        division with areas and no entry. All are drafts until he confirms;
        every one with values carries the text it was read from, its mover
        and its source; migration (area 11) is never placed."""
        divs = c5.load_stance(section="divisions")
        new = {k: e for k, e in divs.items() if e.get("draft")}
        self.assertEqual(len(new), 215)
        valued = [k for k, e in new.items() if c5.status(e) == "draft"]
        self.assertEqual(len(valued), 52)
        for k in valued:
            e = new[k]
            self.assertTrue(e.get("text") and e.get("moved_by") and e.get("source")
                            and e.get("lobbies") and e.get("dated") and e.get("result"), k)
            self.assertTrue(all(abs(e[s]) <= 2 for s in ("yea", "nay") if s in e), k)
            for s in ("yea", "nay"):
                if s in e:
                    self.assertTrue(e.get("why_" + s), k)
        unplaceable = [e for e in new.values() if c5.status(e) == "unplaceable"]
        self.assertEqual(len(unplaceable), 163)
        self.assertTrue(all(e.get("reason") for e in unplaceable))
        self.assertEqual(sum(1 for e in unplaceable if "excluded_from_5ca" in e["reason"]), 143)
        # C-16 (2026) is not our ground (Christopher, 2 October 2026).
        for k in ("commons-45-1-134", "commons-45-1-135", "commons-45-1-136", "commons-45-1-137",
                  "commons-45-1-153", "senate-45-1-702758"):
            self.assertEqual(c5.status(divs[k]), "unplaceable", k)
        # The mental-illness vote is clause-specific and full strength.
        self.assertEqual((divs["commons-43-2-71"]["yea"], divs["commons-43-2-71"]["nay"]), (2, -2))
        # A losing lobby of allies and opponents together carries no value.
        self.assertNotIn("nay", divs["commons-42-1-75"])
        self.assertNotIn("nay", divs["commons-42-1-76"])


if __name__ == "__main__":
    unittest.main()


class RoxannesLawSheetTests(unittest.TestCase):
    """40-3/C-510 (coerced abortion) after its reviewed area correction: its
    division is on the abortion sheet and not on the MAID sheet."""

    def test_c510_lands_on_area_1_not_area_2(self):
        spec = importlib.util.spec_from_file_location("ca_rollcalls", os.path.join(ROOT, "tools", "ca_rollcalls.py"))
        ro = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ro)
        from src import filter as filt
        tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist-ca.yaml"))
        subject = "2nd reading of Bill C-510, An Act to amend the Criminal Code (coercion)"
        areas = ro.classify_division(tax, wl, subject, 40, 3, "C-510").issue_areas
        conn = store(divisions=[("commons-40-3-151", "2010-12-15T15:05:00", subject, json.dumps(areas))],
                     votes={"commons-40-3-151": {"1": "Yea", "2": "Nay"}})
        entry = {"commons-40-3-151": {"key": "commons-40-3-151", "yea": 2, "nay": -1,
                                      "why_yea": "for", "why_nay": "against"}}
        self.assertEqual(areas, [1])
        rows1, divs1, _ = c5.build_rows(conn, 1, "commons", entry, {}, today="2026-10-08")
        rows2, divs2, _ = c5.build_rows(conn, 2, "commons", entry, {}, today="2026-10-08")
        self.assertEqual([d["division_key"] for d in divs1], ["commons-40-3-151"])
        self.assertEqual(divs2, [])
        self.assertTrue(any("C-510" in c for c in {r["person_id"]: r for r in rows1}["1"]["comments"]))
        self.assertFalse(any("C-510" in c for r in rows2 for c in r["comments"]))
