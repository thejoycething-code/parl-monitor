import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, members  # noqa: E402
import since_last_vote as slv  # noqa: E402


class DriftTests(unittest.TestCase):
    def test_a_supporter_whose_words_since_are_not_hostile_drifts_towards_us(self):
        conn = db.init_db(sqlite3.connect(":memory:"))
        conn.execute("CREATE TABLE IF NOT EXISTS stance (ref TEXT PRIMARY KEY, stance INTEGER, why TEXT, model TEXT, scored_at TEXT)")
        members.cache_put(conn, members.Member(id=1, name="Wobbler", party="Lab", seat="S", house="Commons", since="2024-07-04"))
        members.cache_put(conn, members.Member(id=2, name="Firm", party="Con", seat="T", house="Commons", since="2024-07-04"))
        conn.execute("UPDATE members SET current_mp = 1")
        ev = [(1, "2025-06-20", "vote", "div:c2071:aye", "Voted Aye: TIA 3R", "[2]"), (1, "2026-03-01", "debate", "hansard:a", "Spoke on palliative care", "[2]"),
              (1, "2026-07-01", "pq", "pq:1", "Asked about hospices", "[2]"), (2, "2025-06-20", "vote", "div:c2071:no", "Voted No: TIA 3R", "[2]")]
        conn.executemany("INSERT INTO mp_events (member_id, date, kind, ref, line, areas) VALUES (?,?,?,?,?,?)", ev)
        conn.executemany("INSERT INTO stance VALUES (?,?,?,?,?)", [("div:c2071:aye", -2, "", "m", "d"), ("div:c2071:no", 2, "", "m", "d"),
                                                                    ("hansard:a", 1, "", "m", "d"), ("pq:1", 0, "", "m", "d")])
        conn.commit()
        rows = slv.drift(conn, 2)
        self.assertEqual([r["name"] for r in rows], ["Wobbler"])           # Firm said nothing since
        self.assertEqual(rows[0]["n_since"], 2); self.assertAlmostEqual(rows[0]["drift"], 2.5)
        text = slv.digest(rows, 2)
        self.assertIn("drifting towards us (1)", text); self.assertIn("Wobbler (Lab, S) — voted against us on 2025-06-20", text)


if __name__ == "__main__":
    unittest.main()
