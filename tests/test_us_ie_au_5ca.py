"""The US, Irish and Australian 5CA (tools/us_5ca.py, ie_5ca.py, au_5ca.py and
src/readings5ca.py). Small in-memory stores; no network."""

import csv
import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import au_store, db, ie_store, us_store  # noqa: E402
from src import readings5ca as r5  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


us5, ie5, au5 = _load("us_5ca"), _load("ie_5ca"), _load("au_5ca")


def signed(entries):
    return {k: {kk: vv for kk, vv in e.items() if kk != "draft"} for k, e in entries.items()}


def read_csv(path):
    with open(path, encoding="utf-8") as h:
        return list(csv.reader(h))


# --- the US -------------------------------------------------------------------

US_MEMBERS = [("A1", "Ally", "R", "TX", "1"), ("O1", "Opp", "D", "CA", "2"),
              ("M1", "Missed", "R", "OH", "3"), ("G1", "Gone", "R", "FL", "4"),
              ("C1", "Cosponsor", "R", "UT", "1")]
US_DIVS = [
    # key, date, bill, question, own_areas, areas
    ("house-119-1-26", "2025-01-23", "119/hr/21", "On Motion to Recommit", "[1]", "[1]"),
    ("house-119-1-27", "2025-01-23", "119/hr/21", "On Passage", "[1]", "[1]"),
    ("house-119-1-90", "2025-03-11", "119/hr/1968", "On Passage", "[]", "[1, 2]"),
    ("house-119-1-99", "2025-06-01", "119/hr/50", "On Passage", "[1]", "[1]"),
    ("house-119-2-1", "2026-09-16", None, "Quorum", "[]", "[]"),
]
US_VOTES = {
    "house-119-1-26": {"A1": "Nay", "O1": "Yea", "M1": "Nay", "G1": "Nay"},
    "house-119-1-27": {"A1": "Yea", "O1": "Nay", "M1": "Yea", "G1": "Yea"},
    "house-119-1-90": {"A1": "Yea", "O1": "Nay", "M1": "Yea", "G1": "Yea"},
    "house-119-1-99": {"A1": "Yea", "O1": "Nay", "M1": "Not Voting", "G1": "Yea"},
    "house-119-2-1": {"A1": "Yea", "O1": "Yea", "M1": "Yea", "C1": "Yea"},   # Gone has left
}
US_ENTRIES = {
    "house-119-1-26": {"key": "house-119-1-26", "placeable": False, "reason": "MTR", "draft": True},
    "house-119-1-27": {"key": "house-119-1-27", "yea": 2, "nay": -2, "why_yea": "for born-alive",
                       "why_nay": "against", "draft": True},
    "house-119-1-99": {"key": "house-119-1-99", "yea": 2, "nay": -2, "why_yea": "later",
                       "why_nay": "later against", "draft": True},
}
US_BILLS = {"119/hr/21": {"key": "119/hr/21", "sponsored": 2, "cosponsored": 1,
                          "why_sponsored": "introduced", "why_cosponsored": "cosponsored",
                          "draft": True}}


def us_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    us_store.ensure_schema(conn)
    for bio, name, party, state, district in US_MEMBERS:
        conn.execute("INSERT INTO us_members (bioguide, name, party, state, district, chamber) "
                     "VALUES (?,?,?,?,?, 'house')", (bio, name, party, state, district))
    for key, date, bill, q, own, areas in US_DIVS:
        _c, cong, sess, roll = key.split("-")
        conn.execute("INSERT INTO us_divisions (division_key, chamber, congress, session, roll, date, "
                     "bill_key, question, result, yeas, nays, own_areas, areas) "
                     "VALUES (?, 'house', ?,?,?,?,?,?, 'Passed', 1, 1, ?, ?)",
                     (key, int(cong), int(sess), int(roll), date, bill, q, own, areas))
        for bio, pos in US_VOTES[key].items():
            conn.execute("INSERT INTO us_votes VALUES (?,?,?,?,?)", (key, bio, pos, "R", "TX"))
    conn.execute("INSERT INTO us_bills (bill_key, congress, bill_type, number, title, sponsor, "
                 "introduced, areas) VALUES ('119/hr/21', 119, 'hr', 21, 'Born-Alive', 'A1', "
                 "'2025-01-03', '[1]')")
    conn.execute("INSERT INTO us_bills (bill_key, congress, bill_type, number, title, sponsor, "
                 "introduced, areas, triage_score) VALUES ('119/hr/12', 119, 'hr', 12, 'WHPA', 'O1', "
                 "'2025-01-03', '[1]', 3)")
    conn.execute("INSERT INTO us_cosponsors VALUES ('119/hr/21', 'C1', '2025-01-05', NULL, 1)")
    conn.execute("INSERT INTO us_cosponsors VALUES ('119/hr/21', 'O1', '2025-01-05', '2025-02-01', 0)")
    conn.commit()
    return conn


class ReadingsCoreTests(unittest.TestCase):
    def test_draft_outranks_everything(self):
        self.assertEqual(r5.status({"placeable": False, "draft": True}), "draft")
        self.assertEqual(r5.status({"yea": 2, "draft": True}), "draft")
        self.assertEqual(r5.status({"placeable": False}), "unplaceable")
        self.assertEqual(r5.status({"read_first": "x"}), "unread")
        self.assertEqual(r5.status({"yea": 2}), "confirmed")
        self.assertEqual(r5.status(None), "none")

    def test_a_draft_value_is_never_applied(self):
        self.assertEqual(r5.value({"yea": 2, "draft": True}, "yea"), (None, None))
        self.assertEqual(r5.value({"yea": 2, "why_yea": "w"}, "yea"), (2, "w"))

    def test_readings_line_says_plainly_when_nothing_is_signed(self):
        self.assertIn("NO SIGNED READINGS", r5.readings_line(0, 3, "Abortion"))
        self.assertNotIn("NO SIGNED", r5.readings_line(2, 1, "Abortion"))

    def test_sign_keys_removes_only_the_ticked_drafts_and_keeps_comments(self):
        text = ("# header comment\ndivisions:\n  - key: \"a\"\n    yea: 2\n    draft: true\n"
                "  - key: \"b\"\n    yea: 1\n    draft: true  # still a draft\n")
        new, done = r5.sign_keys(text, {"a"}, "2026-10-09")
        self.assertEqual(done, ["a"])
        self.assertIn("# header comment", new)
        self.assertIn('signed: "2026-10-09"', new)
        import yaml
        cfg = yaml.safe_load(new)["divisions"]
        self.assertNotIn("draft", cfg[0])
        self.assertTrue(cfg[1]["draft"])

    def test_ticked_keys_reads_the_checkboxes(self):
        doc = "### [x] `a` T\n\n### [ ] `b` U\n### [X] `c` V\n"
        self.assertEqual(r5.ticked_keys(doc), ["a", "c"])

    def test_sign_from_doc_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            stance = os.path.join(tmp, "s.yaml")
            with open(stance, "w") as h:
                h.write("divisions:\n  - key: \"k1\"\n    title: \"T\"\n    yea: 2\n    nay: -2\n"
                        "    draft: true\n")
            doc = os.path.join(tmp, "d.md")
            entries = r5.load_stance(stance)
            with open(doc, "w") as h:
                h.write(r5.signoff_markdown("T", "intro", {"yea": "Yea", "nay": "Nay"},
                                            entries, {}, "s.yaml").replace("[ ]", "[x]"))
            self.assertEqual(r5.sign_from_doc(stance, doc, today="2026-10-09", log=lambda *a: 0), ["k1"])
            self.assertEqual(r5.status(r5.load_stance(stance)["k1"]), "confirmed")


class USTests(unittest.TestCase):
    def rows(self, entries=US_ENTRIES, bills=US_BILLS):
        rows, divisions, latest = us5.build_rows(us_conn(), 1, "house", entries, bills,
                                                 today="2026-10-09")
        return {r["person_id"]: r for r in rows}, divisions, latest

    def test_drafts_place_nobody(self):
        rows, _, latest = self.rows()
        self.assertTrue(all(r["column"] == "0" for r in rows.values()))
        self.assertIsNone(latest)
        self.assertIn("reading DRAFT", " ".join(rows["A1"]["comments"]))

    def test_signed_votes_place_and_the_absence_rule_caps(self):
        rows, _, latest = self.rows(signed(US_ENTRIES), signed(US_BILLS))
        self.assertEqual(rows["A1"]["column"], "++")
        self.assertEqual(rows["O1"]["column"], "--")
        self.assertEqual(latest["division_key"], "house-119-1-99")
        self.assertEqual(rows["M1"]["column"], "+")             # Not Voting on the latest
        self.assertTrue(rows["M1"]["capped"])

    def test_cosponsorship_places_only_when_signed_and_a_withdrawal_never(self):
        rows, _, _ = self.rows(signed(US_ENTRIES), signed(US_BILLS))
        self.assertEqual(rows["C1"]["column"], "+")
        self.assertIn("a bill cosponsored", rows["C1"]["based_on"])
        self.assertTrue(any("WITHDREW" in c for c in rows["O1"]["comments"]))
        rows, _, _ = self.rows(signed(US_ENTRIES), US_BILLS)
        self.assertEqual(rows["C1"]["column"], "0")

    def test_an_unread_bill_is_one_evidence_line(self):
        rows, _, _ = self.rows()
        line = [c for c in rows["O1"]["comments"] if "no reading" in c and "SPONSORED" in c]
        self.assertEqual(len(line), 1)
        self.assertIn("H.R. 12", line[0])

    def test_a_borrowed_area_roll_call_is_left_off_unless_its_bill_is_read(self):
        _, divisions, _ = self.rows()
        keys = {d["division_key"] for d in divisions}
        self.assertNotIn("house-119-1-90", keys)                # omnibus passage, borrowed area
        self.assertIn("house-119-1-26", keys)
        bills = dict(US_BILLS, **{"119/hr/1968": {"key": "119/hr/1968", "sponsored": 0}})
        _, divisions, _ = self.rows(US_ENTRIES, bills)
        self.assertIn("house-119-1-90", {d["division_key"] for d in divisions})

    def test_a_former_member_who_voted_is_listed_not_counted(self):
        rows, _, _ = self.rows()
        self.assertFalse(rows["G1"]["sitting"])
        self.assertIn("[FORMER]", rows["G1"]["decision_maker"])

    def test_the_sheet_ends_saying_no_reading_is_signed(self):
        with tempfile.TemporaryDirectory() as tmp:
            names = {1: "Abortion"}
            path = us5.run(us_conn(), 1, "house", US_ENTRIES, US_BILLS, names, tmp, log=lambda *a: 0)
            rows = read_csv(path)
            self.assertTrue(rows[-1][0].startswith("NO SIGNED READINGS for Abortion: 3 drafted"))
            self.assertTrue(rows[-2][0].startswith("Totals - 4 sitting"))
            path = us5.run(us_conn(), 1, "house", signed(US_ENTRIES), US_BILLS, names, tmp,
                           log=lambda *a: 0)
            self.assertTrue(read_csv(path)[-1][0].startswith("Readings for Abortion: 3 signed"))


# --- Ireland --------------------------------------------------------------------

def ie_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    ie_store.ensure_schema(conn)
    for code, name, party, end in [("T1", "Toibin", "Aontu", None), ("C1", "Cairns", "SD", None),
                                   ("A1", "Away", "FF", None), ("S1", "Staon", "SF", None),
                                   ("X1", "Ex", "FG", "2025-01-01")]:
        conn.execute("INSERT INTO ie_members (member_code, name, house, party, represents, start_date, "
                     "end_date) VALUES (?,?, 'dail', ?, 'Meath', '2024-11-29', ?)", (code, name, party, end))
    conn.execute("INSERT INTO ie_divisions (division_key, chamber, house_key, date, debate_title, "
                 "subject, outcome, ta, nil, staon, own_areas, areas) VALUES "
                 "('dail/34/2026-06-17/vote_149', 'dail', 'dail/34', '2026-06-17', 'Three Day Wait Bill', "
                 "'Question put:', 'Carried', 1, 1, 1, '[]', '[1]')")
    for code, pos in [("C1", "Yes"), ("T1", "No"), ("S1", "Abstain")]:
        conn.execute("INSERT INTO ie_votes VALUES ('dail/34/2026-06-17/vote_149', ?, ?, 'x')", (code, pos))
    conn.execute("INSERT INTO ie_bills (bill_key, year, number, title, source, areas) VALUES "
                 "('2026/40', 2026, 40, 'Reproductive Rights', 'Private Member', '[1]')")
    conn.execute("INSERT INTO ie_sponsors (bill_key, sponsor, member_code, name) VALUES "
                 "('2026/40', 'C1', 'C1', 'Cairns')")
    conn.execute("INSERT INTO ie_bills (bill_key, year, number, title, source, areas) VALUES "
                 "('2026/74', 2026, 74, 'Gov bill', 'Government', '[1]')")
    conn.execute("INSERT INTO ie_sponsors (bill_key, sponsor, member_code, name) VALUES "
                 "('2026/74', 'A1', 'A1', 'Away')")
    conn.commit()
    return conn


IE_ENTRIES = {"dail/34/2026-06-17/vote_149": {"key": "dail/34/2026-06-17/vote_149", "yea": -2,
                                              "nay": 2, "why_yea": "abolish", "why_nay": "keep",
                                              "draft": True}}
IE_BILLS = {"2026/40": {"key": "2026/40", "sponsored": -2, "why_sponsored": "x", "draft": True}}


class IETests(unittest.TestCase):
    def rows(self, entries, bills):
        rows, _, latest = ie5.build_rows(ie_conn(), 1, "dail", entries, bills, today="2026-10-09")
        return {r["person_id"]: r for r in rows}, latest

    def test_drafts_place_nobody(self):
        rows, _ = self.rows(IE_ENTRIES, IE_BILLS)
        self.assertTrue(all(r["column"] == "0" for r in rows.values()))

    def test_nil_is_the_nay_side_and_staon_has_no_direction(self):
        rows, latest = self.rows(signed(IE_ENTRIES), signed(IE_BILLS))
        self.assertEqual(rows["T1"]["column"], "++")
        self.assertEqual(rows["C1"]["column"], "--")
        self.assertEqual(rows["S1"]["column"], "0")
        self.assertTrue(any("abstention recorded" in c for c in rows["S1"]["comments"]))
        self.assertEqual(latest["division_key"], "dail/34/2026-06-17/vote_149")

    def test_a_member_who_held_the_seat_and_did_not_vote_is_listed(self):
        rows, _ = self.rows(IE_ENTRIES, IE_BILLS)
        self.assertTrue(any("NO RECORDED VOTE" in c for c in rows["A1"]["comments"]))
        self.assertNotIn("X1", rows)

    def test_only_a_private_members_bill_is_sponsorship_evidence(self):
        rows, _ = self.rows(IE_ENTRIES, IE_BILLS)
        self.assertTrue(any("SPONSORED 2026/40" in c for c in rows["C1"]["comments"]))
        self.assertFalse(any("2026/74" in c for c in rows["A1"]["comments"]))


# --- Australia ------------------------------------------------------------------

def au_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    au_store.ensure_schema(conn)
    for pid, name, party in [("1", "Aye One", "LP"), ("2", "No Two", "ALP"), ("3", "Paired Three", "LP")]:
        conn.execute("INSERT INTO au_members (person_id, name, party, house, electorate, current) "
                     "VALUES (?,?,?, 'senate', 'NSW', 1)", (pid, name, party))
        conn.execute("INSERT INTO au_offices (office_id, person_id, house, from_date, to_date) "
                     "VALUES (?, ?, 'senate', '2022-07-01', '9999-12-31')", ("lord/" + pid, pid))
    for key, date in [("senate-2025-07-31-13", "2025-07-31"), ("senate-2026-07-01-16", "2026-07-01")]:
        conn.execute("INSERT INTO au_divisions (division_key, chamber, date, number, minor_heading, "
                     "question, ayes, noes, pairs, own_areas, areas) VALUES (?, 'senate', ?, 1, "
                     "'Sex Discrimination Bill; First Reading', 'q', 1, 1, 1, '[5]', '[5]')", (key, date))
    votes = {"senate-2025-07-31-13": {"1": "Aye", "2": "No", "3": "Aye"},
             "senate-2026-07-01-16": {"1": "Aye", "2": "No", "3": "Paired"}}
    for key, vs in votes.items():
        for pid, pos in vs.items():
            conn.execute("INSERT INTO au_votes (division_key, person_id, position, party) "
                         "VALUES (?,?,?, 'x')", (key, pid, pos))
    conn.commit()
    return conn


AU_ENTRIES = {k: {"key": k, "yea": 2, "nay": -2, "why_yea": "y", "why_nay": "n", "draft": True}
              for k in ("senate-2025-07-31-13", "senate-2026-07-01-16")}


class AUTests(unittest.TestCase):
    def rows(self, entries):
        rows, _, latest = au5.build_rows(au_conn(), 5, "senate", entries, today="2026-10-09")
        return {r["person_id"]: r for r in rows}, latest

    def test_drafts_place_nobody(self):
        rows, _ = self.rows(AU_ENTRIES)
        self.assertTrue(all(r["column"] == "0" for r in rows.values()))

    def test_a_pair_places_nobody_and_caps_a_double_plus(self):
        rows, latest = self.rows(signed(AU_ENTRIES))
        self.assertEqual(rows["1"]["column"], "++")
        self.assertEqual(rows["2"]["column"], "--")
        self.assertEqual(rows["3"]["column"], "+")
        self.assertTrue(rows["3"]["capped"])
        self.assertIn("paired", rows["3"]["comments"][0])


# --- the real stance files and their sign-off guides ----------------------------

class RealStanceFileTests(unittest.TestCase):
    FILES = [("us", us5, True), ("ie", ie5, True), ("au", au5, False)]

    def test_every_entry_is_an_unsigned_draft_with_its_meaning(self):
        for cc, mod, _bills in self.FILES:
            entries = r5.load_stance(mod.STANCE_PATH, "divisions")
            bills = r5.load_stance(mod.STANCE_PATH, "bills")
            self.assertTrue(entries, cc)
            for key, e in list(entries.items()) + list(bills.items()):
                self.assertEqual(r5.status(e), "draft", (cc, key))
                self.assertTrue(e.get("drafted"), (cc, key))
            for key, e in entries.items():
                self.assertTrue(e.get("aye_means"), (cc, key))
                has = any(e.get(k) is not None for k in r5.VALUE_KEYS)
                self.assertTrue(has or e.get("placeable") is False or e.get("read_first"), (cc, key))
                if e.get("placeable") is False:
                    self.assertTrue(e.get("reason"), (cc, key))

    def test_the_cosponsorship_value_never_reaches_double_plus(self):
        for key, e in r5.load_stance(us5.STANCE_PATH, "bills").items():
            self.assertLessEqual(abs(e.get("cosponsored") or 0), 1, key)

    def test_the_signoff_guides_are_in_step_with_the_stance_files(self):
        for cc, mod, has_bills in self.FILES:
            entries = r5.load_stance(mod.STANCE_PATH, "divisions")
            bills = r5.load_stance(mod.STANCE_PATH, "bills") if has_bills else {}
            with open(mod.DOC_PATH, encoding="utf-8") as h:
                doc = h.read()
            for key in list(entries) + list(bills):
                self.assertIn("### [ ] `{0}`".format(key), doc, (cc, key))


if __name__ == "__main__":
    unittest.main()
