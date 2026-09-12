import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, livedebate as ld  # noqa: E402


class WobbleTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(sqlite3.connect(":memory:"))
        self.conn.execute("CREATE TABLE IF NOT EXISTS stance (ref TEXT PRIMARY KEY, stance INTEGER, why TEXT, model TEXT, scored_at TEXT)")
        rows = [(1, "2025-06-20", "vote", "div:c2071:aye", "Voted Aye: TIA Third Reading", "[2]"),
                (2, "2025-06-20", "vote", "div:c2071:no", "Voted No: TIA Third Reading", "[2]"),
                (3, "2025-06-20", "vote", "div:c2071:aye", "Voted Aye: TIA Third Reading", "[2]")]
        self.conn.executemany("INSERT INTO mp_events (member_id, date, kind, ref, line, areas) VALUES (?,?,?,?,?,?)", rows)
        self.conn.executemany("INSERT INTO stance VALUES (?,?,?,?,?)", [("div:c2071:aye", -2, "w", "m", "d"), ("div:c2071:no", 2, "w", "m", "d")])
        self.conn.commit()
        self.state = {"speakers": [{"name": "Marie Goldman", "key": "1"}, {"name": "Danny Kruger", "key": "2"}, {"name": "Kim Leadbeater", "key": "3"}]}
        self.speeches = [
            {"name": "Marie Goldman", "party": "LD", "seat": "Chelmsford", "pass_read": "Neutral or unclear — asked about safeguards", "contributions": [{"words": 60}]},
            {"name": "Danny Kruger", "party": "Con", "seat": "x", "pass_read": "Against us — praises the Bill", "contributions": [{"words": 500}]},
            {"name": "Kim Leadbeater", "party": "Lab", "seat": "x", "pass_read": "Against us — moves the Bill", "contributions": [{"words": 900}]},
        ]

    def test_a_supporter_reading_unclear_is_a_wobble_and_an_opponent_reading_against_is_a_slip(self):
        found = ld.wobbles(self.conn, self.state, self.speeches, 2)
        self.assertEqual([(f["name"], f["kind"]) for f in found], [("Marie Goldman", "WOBBLE"), ("Danny Kruger", "SLIP")])
        text = ld.dm_text({"title": "TIA"}, self.speeches, found, as_of="12:30")
        self.assertIn("Marie Goldman (LD)", text); self.assertIn("Supporters sounding like opponents", text)
        self.assertIn("3 speakers so far: 0 read with us, 2 against, 1 unclear", text)

    def test_a_member_with_no_scored_vote_is_not_flagged(self):
        speeches = [{"name": "New Member", "party": "Lab", "seat": "x", "pass_read": "With us", "contributions": [{"words": 300}]}]
        state = {"speakers": [{"name": "New Member", "key": "99"}]}
        self.assertEqual(ld.wobbles(self.conn, state, speeches, 2), [])


if __name__ == "__main__":
    unittest.main()
