"""The additive Canadian retag (tools/ca_retag.py). No network."""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, filter as filt  # noqa: E402

spec = importlib.util.spec_from_file_location("ca_retag", os.path.join(ROOT, "tools", "ca_retag.py"))
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)
TAX = filt.load_taxonomy(rt.TAXONOMY)
WL = filt.load_watchlist(rt.WATCHLIST)


def store():
    conn = sqlite3.connect(":memory:")
    db.init_db(conn)
    return ca_store.ensure_schema(conn)


class RetagTests(unittest.TestCase):
    def test_a_petition_gains_an_area_and_keeps_the_ones_it_had(self):
        conn = store()
        conn.execute("INSERT INTO ca_petitions (petition_id, category, keywords, prayer, areas, "
                     "matched_terms, tier) VALUES (?,?,?,?,?,?,?)",
                     ("e-4000", "Foreign affairs", json.dumps(["China"]),
                      "We call on the Government to act against forced organ harvesting in China.",
                      json.dumps([7]), json.dumps(["kept term"]), 2))
        changes = rt.retag(conn, TAX, WL)
        self.assertEqual([(c[0], c[1], c[2]) for c in changes], [("ca_petitions", "e-4000", [13])])
        areas, terms = conn.execute("SELECT areas, matched_terms FROM ca_petitions").fetchone()
        self.assertEqual(json.loads(areas), [7, 13], "7 was earned from text the retag may not see")
        self.assertIn("kept term", json.loads(terms))

    def test_nothing_is_ever_removed(self):
        conn = store()
        conn.execute("INSERT INTO ca_bills (bill_key, parliament, session, number, long_title, "
                     "areas, tier) VALUES ('45-1/C-2', 45, 1, 'C-2', 'An Act about fisheries', "
                     "'[2]', 1)")
        self.assertEqual(rt.retag(conn, TAX, WL), [])
        self.assertEqual(conn.execute("SELECT areas FROM ca_bills").fetchone()[0], "[2]")

    def test_a_senate_vote_is_read_with_its_bills_long_title(self):
        """ca_rollcalls.reclassify reads the subject alone, which is why it is not used."""
        conn = store()
        conn.execute("INSERT INTO ca_bills (bill_key, parliament, session, number, long_title) "
                     "VALUES ('45-1/S-9', 45, 1, 'S-9', 'An Act to amend the Criminal Code "
                     "(medical assistance in dying)')")
        conn.execute("INSERT INTO ca_divisions (division_key, chamber, parliament, session, number, "
                     "subject, bill_number, areas) VALUES ('senate-45-1-7', 'senate', 45, 1, 7, "
                     "'Third reading of Bill S-9', 'S-9', '[]')")
        added = {c[1]: c[2] for c in rt.retag(conn, TAX, WL)}
        self.assertIn(2, added.get("senate-45-1-7", []))

    def test_a_dry_run_writes_nothing(self):
        conn = store()
        conn.execute("INSERT INTO ca_speeches (speech_id, sitting_key, text, subject, areas) "
                     "VALUES ('1', '45-1-1', 'Forced organ harvesting must end.', 'Petitions', '[]')")
        self.assertEqual(len(rt.retag(conn, TAX, WL, dry_run=True)), 1)
        self.assertEqual(conn.execute("SELECT areas FROM ca_speeches").fetchone()[0], "[]")


if __name__ == "__main__":
    unittest.main()
