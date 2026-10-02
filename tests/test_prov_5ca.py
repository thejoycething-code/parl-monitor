"""tools/prov_5ca.py and config/prov_stance.yaml. No network.

The stance file ships EMPTY: every provincial sheet is an evidence list
until Christopher confirms a reading. These tests confirm a reading only in
a temporary stance file, to show what a confirmation would do.
"""

import csv
import importlib.util
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import prov_names as pn, prov_store as ps  # noqa: E402
from src.ingest import prov_ab as ab  # noqa: E402
from tests.test_prov_ab import DATE, conn_with_terms, fx  # noqa: E402


def _load():
    spec = importlib.util.spec_from_file_location("prov_5ca", os.path.join(ROOT, "tools", "prov_5ca.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


p5 = _load()
NAMES = {3: "Gender medicine children"}


def store_proof(conn):
    """The 3 December 2024 V&P, stored as the collector stores it."""
    r = pn.Resolver.from_conn(conn, "ab")
    for d in ab.parse_vp(fx("ab_vp_20241203.txt"), r.surname_vocab()):
        votes, ok, note = ab.resolve_division(d, r, DATE, 31)
        bkey = ps.bill_key("ab", 31, 1, d["bill_number"])
        ps.store_division(conn, {
            "division_key": ps.division_key("ab", 31, 1, DATE, d["seq"]), "prov": "ab",
            "legislature": 31, "session": 1, "date": DATE, "seq": d["seq"], "kind": "recorded",
            "vote_on": d["vote_on"], "bill_key": bkey, "stage": d["stage"], "result": d["result"],
            "yeas": d["yeas"], "nays": d["nays"], "areas": [3] if bkey == "ab-31-1/26" else [],
            "positions_ok": 1 if ok else 0, "tally_note": note, "votes": votes})
    conn.execute("UPDATE prov_members SET sitting=1 WHERE prov='ab'")
    conn.execute("UPDATE prov_members SET sitting=0 WHERE prov='ab' AND member_key='0791'")
    conn.commit()


class StanceFileTests(unittest.TestCase):
    def test_the_shipped_stance_file_is_confirmed(self):
        """Christopher, 3 October 2026: "Confirm all the readings." No draft
        remains; read-first entries carry no values and place nobody."""
        entries = p5.load_stance(p5.STANCE_PATH, "divisions")
        self.assertGreater(len(entries), 10)
        # The read-first entries drafted on 2 October 2026 ("Draft the 10
        # 'read first' readings") were confirmed the same day ("Confirm all
        # the readings"): no draft remains, and each keeps the text it was
        # read from.
        read_2_oct = ["ab-31-1-2024-11-27-3", "ab-31-1-2024-11-27-4",
                      "ab-31-1-2024-11-27-5", "bc-43-2-2026-02-26-126.1"]
        self.assertEqual([k for k, e in entries.items() if p5.status(e) == "draft"], [])
        self.assertEqual([k for k, e in entries.items() if p5.status(e) == "unread"], [])
        self.assertEqual({p5.status(entries[k]) for k in read_2_oct}, {"confirmed"})
        self.assertEqual(p5.status(entries["sk-29-3-2023-10-19-6"]), "unplaceable")
        for k in read_2_oct + ["sk-29-3-2023-10-19-6"]:
            self.assertTrue(entries[k].get("text") and entries[k].get("moved_by")
                            and entries[k].get("source"), k)
        self.assertEqual(p5.status(entries["ab-31-1-2024-12-03-2"]), "confirmed")
        with open(p5.STANCE_PATH, encoding="utf-8") as fh:
            header = fh.read()
        self.assertIn("draft: true", header)
        self.assertIn("places NOBODY", header)

    def test_a_reading_can_state_its_own_area(self):
        src = open(p5.__file__, encoding="utf-8").read()
        self.assertIn('(entries.get(r["division_key"]) or {}).get("areas")', src)
        e = p5.load_stance(p5.STANCE_PATH, "divisions")["ab-31-1-2024-10-30-2"]
        self.assertEqual(e.get("areas"), [1])

    def test_status(self):
        self.assertEqual(p5.status({"key": "k", "yea": 2, "nay": -2, "draft": True}), "draft")
        self.assertEqual(p5.status({"key": "k", "yea": 2, "nay": -2}), "confirmed")
        self.assertEqual(p5.status({"key": "k", "placeable": False}), "unplaceable")
        self.assertEqual(p5.status({"key": "k", "read_first": "x"}), "unread")


class SheetTests(unittest.TestCase):
    def setUp(self):
        self.conn = conn_with_terms()
        store_proof(self.conn)
        self.key = "ab-31-1-2024-12-03-2"

    def test_with_no_reading_it_is_an_evidence_list(self):
        rows, trusted, untrusted, voice = p5.build_rows(self.conn, "ab", 3, {}, {})
        self.assertTrue(all(r["column"] == "0" for r in rows))
        smith = [r for r in rows if r["key"] == "0814"][0]
        self.assertTrue(any("VOTE YEA as United Conservative" in c and "no reading" in c
                            for c in smith["comments"]))
        notley = [r for r in rows if r["key"] == "0791"][0]
        self.assertIn("[FORMER]", notley["decision_maker"])

    def test_a_confirmed_reading_places_and_a_draft_does_not(self):
        reading = {self.key: {"key": self.key, "yea": 2, "nay": -2, "why_yea": "t", "why_nay": "t"}}
        rows, *_ = p5.build_rows(self.conn, "ab", 3, reading, {})
        col = {r["key"]: r["column"] for r in rows}
        self.assertEqual((col["0814"], col["0924"]), ("++", "++"))       # Smith, LaGrange
        self.assertEqual((col["0791"], col["0848"]), ("--", "--"))       # Notley, Gray
        draft = {self.key: dict(reading[self.key], draft=True)}
        rows, *_ = p5.build_rows(self.conn, "ab", 3, draft, {})
        self.assertTrue(all(r["column"] == "0" for r in rows))

    def test_an_untrusted_division_places_nobody_and_shows_no_positions(self):
        self.conn.execute("UPDATE prov_divisions SET positions_ok=0 WHERE division_key=?", (self.key,))
        reading = {self.key: {"key": self.key, "yea": 2, "nay": -2}}
        rows, trusted, untrusted, voice = p5.build_rows(self.conn, "ab", 3, reading, {})
        self.assertEqual([d["division_key"] for d in untrusted], [self.key])
        self.assertTrue(all(r["column"] == "0" for r in rows))
        self.assertFalse(any(self.key[-12:] in c for r in rows for c in r["comments"]))

    def test_voice_decisions_are_said_on_the_sheet(self):
        ps.store_division(self.conn, {"division_key": "ab-31-1-2024-11-27-v26-cw", "prov": "ab",
                                      "legislature": 31, "session": 1, "date": "2024-11-27",
                                      "kind": "voice", "bill_key": "ab-31-1/26",
                                      "stage": "Committee of the Whole", "areas": [3]})
        with tempfile.TemporaryDirectory() as out:
            path = p5.run(self.conn, "ab", 3, {}, {}, NAMES, out, log=lambda *a: None)
            with open(path, encoding="utf-8") as fh:
                rows = list(csv.reader(fh))
        self.assertTrue(rows[-1][0].startswith("Passed on voice, no member record: 2024-11-27 ab-31-1/26"))

    def test_consensus_legislatures_are_refused(self):
        self.assertEqual(p5.main(["--prov", "nt", "--area", "1"]), 1)


if __name__ == "__main__":
    unittest.main()
