"""Member records on our ground for MSPs, MSs and MLAs (Christopher, 2026-10-09).

Small real rows: the divisions, references and member names are the store's
own (S6M-21005, the Senedd's 623756 assisted dying motion and its LCM family,
the Assembly's Justice Bill amendment 97), with the real stance files, so a
reading signed in config/ is what these tests read.
"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, devolved_intel as di  # noqa: E402

NOW = "2026-10-09T00:00:00"


def store():
    tmp = tempfile.mkdtemp()
    conn = db.init_db(db.connect(os.path.join(tmp, "t.db")))
    return conn


def scotland_rows(conn):
    for pid, name, pref, party in (("2615", "Adam, George", "George", "Scottish National Party"),
                                   ("4934", "McArthur, Liam", "Liam", "Scottish Liberal Democrats"),
                                   ("5612", "Briggs, Miles", "Miles", "Scottish Conservative and Unionist Party"),
                                   ("9999", "Absent, Ann", "Ann", "Scottish Labour")):
        conn.execute("INSERT INTO sp_members (person_id, name, preferred_name, is_current, party, "
                     "constituency, first_seen, last_seen) VALUES (?,?,?,1,?,?,?,?)",
                     (pid, name, pref, party, "Somewhere", NOW, NOW))
    divs = (("m9165", "S6M-21005", "Assisted Dying for Terminally Ill Adults (Scotland) Bill",
             "2026-03-17", 57, 69, "Defeated", '[2]', 1),
            # tier 2 only: counted nowhere on a member page
            ("m9361", "S7M-01264.2", "Scotland's Right to Decide", "2026-09-22", 91, 12,
             "Carried", '[9]', 2),
            # migration only: collated, never our ground
            ("m9291", "S7M-00469.5", "Achieving a Sustainable Prison Population", "2026-06-10",
             60, 50, "Carried", '[11]', 1))
    for key, ref, title, dated, f, a, res, areas, tier in divs:
        conn.execute("INSERT INTO sp_divisions (key, reference, title, dated, vote_for, vote_against, "
                     "result, source, areas, tier, first_seen, last_seen) "
                     "VALUES (?,?,?,?,?,?,?,'votesmotion',?,?,?,?)",
                     (key, ref, title, dated, f, a, res, areas, tier, NOW, NOW))
    for key in ("m9165", "m9361", "m9291"):
        for pid, vote in (("2615", "No"), ("4934", "Yes"), ("5612", "Abstain"), ("9999", "Not Voted")):
            conn.execute("INSERT INTO sp_votes (division_key, person_id, vote, party, shares_party) "
                         "VALUES (?,?,?,?,?)", (key, pid, vote, "x", "Yes"))
    items = (("sp-question:S6W-38001", "question", "S6W-38001", "Assisted dying", "To ask the Scottish "
              "Government what assessment it has made of palliative care capacity.", "2025-06-01",
              "5612", '[2]', 1),
             ("sp-question:S6W-38002", "question", "S6W-38002", "Hospice fundraising",
              "To ask about hospice fundraising.", "2025-06-02", "5612", '[2]', 2),
             ("sp-motion:500001", "motion", "S6M-17000", "Opposing Assisted Suicide",
              "That the Parliament opposes assisted suicide.", "2025-05-01", "2615", '[2]', 1))
    for iid, kind, ref, title, body, dated, msp, areas, tier in items:
        conn.execute("INSERT INTO sp_items (id, kind, reference, title, body, dated, msp_id, areas, tier, "
                     "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (iid, kind, ref, title, body, dated, msp, areas, tier, NOW, NOW))
    conn.execute("INSERT INTO sp_supports (motion_uid, person_id, lodged, fetched_at) VALUES "
                 "('500001', '5612', '2025-05-02', ?)", (NOW,))
    conn.execute("INSERT INTO sp_events (key, person_id, dated, heading, areas, excerpt, first_seen, "
                 "last_seen) VALUES ('orc1', '4934', '2026-03-17', 'Assisted Dying Bill: Stage 3', '[2]', "
                 "'I commend the Bill to the Parliament.', ?, ?)", (NOW, NOW))
    conn.commit()


class ScotlandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = store()
        scotland_rows(cls.conn)
        cls.p = di.build("scotland", cls.conn)

    def votes(self, pid):
        return [i for i in self.p[pid]["areas"]["2"]["items"] if i["k"] == "vote"]

    def test_a_signed_reading_carries_its_direction_for_the_lobby(self):
        v = self.votes("2615")[0]
        self.assertEqual((v["v"], v["rs"], v["dir"]), ("No", "signed", 2))
        self.assertIn("defeat", v["why"])
        v = self.votes("4934")[0]
        self.assertEqual((v["v"], v["rs"], v["dir"]), ("Yes", "signed", -2))

    def test_an_abstention_is_a_position_without_a_direction(self):
        v = self.votes("5612")[0]
        self.assertEqual((v["v"], v["rs"]), ("Abstain", "no-position"))
        self.assertNotIn("dir", v)

    def test_not_voted_is_counted_never_listed(self):
        block = self.p["9999"]["areas"]["2"]
        self.assertEqual(block["n"], {"absent": 1})
        self.assertEqual(block["items"], [])

    def test_tier_two_and_migration_stay_off_the_page(self):
        for pid in ("2615", "4934"):
            self.assertEqual(set(self.p[pid]["areas"]), {"2"})
        self.assertEqual(self.p["5612"]["areas"]["2"]["n"].get("pq"), 1)   # tier-2 question dropped

    def test_questions_and_motions_are_one_line_and_a_link(self):
        items = {i["k"]: i for i in self.p["5612"]["areas"]["2"]["items"]}
        self.assertTrue(items["pq"]["u"].endswith("question?ref=S6W-38001"))
        self.assertNotIn("answer", items["pq"])
        self.assertEqual(items["signed"]["u"],
                         "https://www.parliament.scot/chamber-and-committees/votes-and-motions/S6M-17000")
        lodged = [i for i in self.p["2615"]["areas"]["2"]["items"] if i["k"] == "motion"][0]
        self.assertEqual(lodged["rs"], "awaiting")         # no reading in sp_stance.yaml

    def test_placement_is_the_5ca_sheets_own(self):
        self.assertEqual(self.p["2615"]["place"], {"2": "++"})
        self.assertEqual(self.p["4934"]["place"], {"2": "--"})
        self.assertEqual(self.p["5612"]["place"], {})

    def test_a_speech_quotes_one_line(self):
        spoke = [i for i in self.p["4934"]["areas"]["2"]["items"] if i["k"] == "spoke"][0]
        self.assertEqual(spoke["q"], "I commend the Bill to the Parliament.")

    def test_members_narrows_to_the_page(self):
        self.assertEqual(set(di.build("scotland", self.conn, members=["2615"])), {"2615"})


class WalesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn = store()
        for pid, name in (("uk.org.publicwhip/person/11170", "Adam Price"),
                          ("uk.org.publicwhip/person/25000", "Darren Millar")):
            conn.execute("INSERT INTO sd_members (person_id, name, party, post, start_date, captured_at) "
                         "VALUES (?,?,?,?,?,?)", (pid, name, "x", "Seat", "2026-05-08", NOW))
        for key, title, dated, areas in (("623756", "Member Debate under SO 11.21(iv): assisted dying",
                                          "2024-10-23", "[2]"),
                                         ("751826", "TIA Bill LCM: amendment 1", "2026-02-24", "[2]")):
            conn.execute("INSERT INTO sd_divisions (key, meeting_id, dated, title, total_for, total_against, "
                         "total_abstain, result, areas, tier, first_seen, last_seen) "
                         "VALUES (?,14144,?,?,19,26,9,'Motion rejected',?,1,?,?)",
                         (key, dated, title, areas, NOW, NOW))
        for key in ("623756", "751826"):
            conn.execute("INSERT INTO sd_votes VALUES (?, '1', 'Adam Price', 'For')", (key,))
            conn.execute("INSERT INTO sd_votes VALUES (?, '2', 'Darren Millar', 'Against')", (key,))
        conn.execute("INSERT INTO sd_items (id, kind, reference, member_name, dated, body, areas, tier, "
                     "first_seen, last_seen) VALUES ('sd-question:100032', 'question', 'WQ100032', "
                     "'Darren Millar', '2025-01-01', 'Will the Cabinet Secretary make a statement on "
                     "assisted dying?', '[2]', 1, ?, ?)", (NOW, NOW))
        conn.commit()
        cls.p = di.build("wales", conn)

    def test_signed_and_not_placeable_readings(self):
        price = {i["t"][:16]: i for i in self.p["uk.org.publicwhip/person/11170"]["areas"]["2"]["items"]}
        self.assertEqual((price["Member Debate un"]["rs"], price["Member Debate un"]["dir"]),
                         ("signed", -1))
        self.assertEqual(price["TIA Bill LCM: am"]["rs"], "not-placeable")
        self.assertNotIn("dir", price["TIA Bill LCM: am"])

    def test_votes_join_by_name_and_place(self):
        self.assertEqual(self.p["uk.org.publicwhip/person/25000"]["place"], {"2": "+"})
        pq = [i for i in self.p["uk.org.publicwhip/person/25000"]["areas"]["2"]["items"] if i["k"] == "pq"][0]
        self.assertEqual(pq["u"], "https://record.senedd.wales/WrittenQuestion/100032")


class NiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn = store()
        for pid, name in (("8542", "Mr Timothy Gaston"), ("8098", "Ms Sian Mulholland")):
            conn.execute("INSERT INTO ni_members (person_id, name, display_name, party, constituency, "
                         "first_seen, last_seen) VALUES (?,?,?,?,?,?,?)",
                         (pid, name, name, "x", "North Antrim", NOW, NOW))
        for doc, subject, dated in (("493329", "Amendment 97 - Consideration Stage: Justice Bill", "2026-06-30"),
                                    ("496429", "Second Stage: Conversion Practices (Criminalisation) Bill",
                                     "2026-09-28")):
            conn.execute("INSERT INTO ni_divisions (doc_id, subject, dated, areas, first_seen, last_seen) "
                         "VALUES (?,?,?,?,?,?)", (doc, subject, dated, "[4]" if doc == "496429" else "[5]",
                                                  NOW, NOW))
            conn.execute("INSERT INTO ni_votes VALUES (?, '8542', 'Mr Timothy Gaston', 'aye', 'Unionist', ?)",
                         (doc, NOW))
            conn.execute("INSERT INTO ni_votes VALUES (?, '8098', 'Ms Sian Mulholland', 'no', 'Other', ?)",
                         (doc, NOW))
        conn.commit()
        cls.p = di.build("ni", conn)

    def test_signed_direction_and_awaiting(self):
        g5 = self.p["8542"]["areas"]["5"]["items"][0]
        self.assertEqual((g5["v"], g5["rs"], g5["dir"]), ("Aye", "signed", 2))
        g4 = self.p["8542"]["areas"]["4"]["items"][0]
        self.assertEqual(g4["rs"], "awaiting")
        self.assertTrue(g4["u"].endswith("documentId=496429"))
        self.assertEqual(self.p["8098"]["place"].get("5"), "--")


class ReadingTests(unittest.TestCase):
    def test_reading_statuses(self):
        self.assertEqual(di.reading(None, "aye", "why_aye")[0], "awaiting")
        self.assertEqual(di.reading({"draft": True, "aye": 2}, "aye", "why_aye")[0], "awaiting")
        self.assertEqual(di.reading({"title": "x"}, "aye", "why_aye")[0], "not-placeable")
        self.assertEqual(di.reading({"aye": 2}, "no", "why_no")[0], "awaiting")
        self.assertEqual(di.reading({"aye": 2}, None, None)[0], "no-position")
        self.assertEqual(di.division_status({"aye": 1, "no": -1}), "signed")
        self.assertEqual(di.division_status({"title": "LCM"}), "not-placeable")
        self.assertEqual(di.division_status({"draft": True, "aye": 1}), "awaiting")


if __name__ == "__main__":
    unittest.main()
