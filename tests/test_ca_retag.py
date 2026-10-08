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
        # floor=0: the stored 7 is deliberately one the re-match cannot see.
        changes = rt.retag(conn, TAX, WL, log=lambda *a: None, floor=0)
        self.assertEqual([(c[0], c[1], c[2]) for c in changes], [("ca_petitions", "e-4000", [13])])
        areas, terms = conn.execute("SELECT areas, matched_terms FROM ca_petitions").fetchone()
        self.assertEqual(json.loads(areas), [7, 13], "7 was earned from text the retag may not see")
        self.assertIn("kept term", json.loads(terms))

    def test_nothing_is_ever_removed(self):
        conn = store()
        conn.execute("INSERT INTO ca_bills (bill_key, parliament, session, number, long_title, "
                     "areas, tier) VALUES ('45-1/C-2', 45, 1, 'C-2', 'An Act about fisheries', "
                     "'[2]', 1)")
        self.assertEqual(rt.retag(conn, TAX, WL, log=lambda *a: None, floor=0), [])
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
        added = {c[1]: c[2] for c in rt.retag(conn, TAX, WL, log=lambda *a: None)}
        self.assertIn(2, added.get("senate-45-1-7", []))

    def test_a_gated_table_that_does_not_reproduce_its_tags_writes_nothing(self):
        """The trust check: stored areas the re-match cannot reproduce mean
        the retag is not reading what the collector read."""
        conn = store()
        for n in range(3):
            conn.execute("INSERT INTO ca_bills (bill_key, parliament, session, number, long_title, "
                         "areas) VALUES (?, 45, 1, ?, 'An Act about fisheries', '[4]')",
                         ("45-1/C-%d" % n, "C-%d" % n))
        conn.execute("INSERT INTO ca_petitions (petition_id, category, keywords, prayer, areas) "
                     "VALUES ('e-1', 'Foreign affairs', '[]', 'End forced organ harvesting.', '[]')")
        with self.assertRaises(rt.Untrusted):
            rt.retag(conn, TAX, WL, log=lambda *a: None)
        self.assertEqual(conn.execute("SELECT areas FROM ca_petitions").fetchone()[0], "[]")

    def test_the_gazette_is_reported_not_gated(self):
        conn = store()
        conn.execute("INSERT INTO ca_gazette_items (item_key, issue_key, title, excerpt, areas, "
                     "matched_on) VALUES ('u', 'p2-2020-01-01', 'Regulations Amending X', "
                     "'a passage of the body', '[4]', 'body')")
        said = []
        rt.retag(conn, TAX, WL, log=said.append)
        self.assertTrue(any("reported, not gated" in m for m in said))

    def test_a_dry_run_writes_nothing(self):
        conn = store()
        conn.execute("INSERT INTO ca_speeches (speech_id, sitting_key, text, subject, areas) "
                     "VALUES ('1', '45-1-1', 'Forced organ harvesting must end.', 'Petitions', '[]')")
        self.assertEqual(len(rt.retag(conn, TAX, WL, dry_run=True, log=lambda *a: None)), 1)
        self.assertEqual(conn.execute("SELECT areas FROM ca_speeches").fetchone()[0], "[]")


if __name__ == "__main__":
    unittest.main()



class BillKeyRetagTests(unittest.TestCase):
    """3 Oct 2026: the v1.15 Canadian retag refused (ca_divisions 91.8%)
    because the collectors honour a watched bill KEY and the retag did not."""

    def test_the_retag_applies_bill_key_areas(self):
        src = open(os.path.join(ROOT, "tools", "ca_retag.py"), encoding="utf-8").read()
        body = src[src.index("def _rows("):src.index("ca_bills", src.index("def _rows(") + 400)]
        self.assertIn("add_bill_key_areas", body)


class AreaCorrectionTests(unittest.TestCase):
    """Roxanne's Law (40-3/C-510, coerced abortion) was filed under area 2,
    assisted dying, on the word "coercion". A reviewed correction
    (config/ca_area_corrections.yaml) makes it area 1 and not area 2, on the
    bill and its divisions only (8 October 2026)."""

    SUBJECT = "2nd reading of Bill C-510, An Act to amend the Criminal Code (coercion)"

    def c510(self, conn, areas="[2]"):
        conn.execute("INSERT INTO ca_bills (bill_key, parliament, session, number, long_title, short_title, "
                     "areas, matched_terms, tier) VALUES ('40-3/C-510', 40, 3, 'C-510', "
                     "'An Act to amend the Criminal Code (coercion)', 'An Act to Prevent Coercion of "
                     "Pregnant Women to Abort (Roxanne''s Law)', ?, '[\"coercion\"]', 2)", (areas,))
        conn.execute("INSERT INTO ca_divisions (division_key, chamber, parliament, session, number, subject, "
                     "bill_number, areas, matched_terms, tier) VALUES ('commons-40-3-151', 'commons', 40, 3, "
                     "151, ?, 'C-510', ?, '[\"coercion\"]', 2)", (self.SUBJECT, areas))

    def test_the_classifier_files_it_under_abortion_only(self):
        ro = _load_tool("ca_rollcalls")
        self.assertEqual(ro.classify_division(TAX, WL, self.SUBJECT, 40, 3, "C-510").issue_areas, [1])
        # the same words on any other bill are untouched: "coercion" still reads area 2
        self.assertEqual(ro.classify_division(TAX, WL, self.SUBJECT, 41, 1, "C-510").issue_areas, [2])
        res = ca_store.correct_areas(filt.filter_item(TAX, WL, "An Act to amend the Criminal Code (coercion)"),
                                     40, 3, "C-510")
        self.assertEqual(res.issue_areas, [1])
        self.assertIn("corrected:40-3/C-510", res.watchlist_hits)

    def test_the_retag_corrects_the_stored_rows_and_nothing_else(self):
        conn = store()
        self.c510(conn)
        conn.execute("INSERT INTO ca_bills (bill_key, parliament, session, number, long_title, areas, tier) "
                     "VALUES ('45-1/C-260', 45, 1, 'C-260', 'An Act to amend the Criminal Code (medical "
                     "assistance in dying — protection against coercion)', '[2]', 1)")
        changes = rt.retag(conn, TAX, WL, log=lambda *a: None)
        self.assertEqual(sorted((c[0], c[1], c[2], c[4]) for c in changes),
                         [("ca_bills", "40-3/C-510", [1], [2]), ("ca_divisions", "commons-40-3-151", [1], [2])])
        got = dict(conn.execute("SELECT bill_key, areas FROM ca_bills").fetchall())
        self.assertEqual(got, {"40-3/C-510": "[1]", "45-1/C-260": "[2]"})
        self.assertEqual(conn.execute("SELECT areas FROM ca_divisions").fetchone()[0], "[1]")
        terms = json.loads(conn.execute("SELECT matched_terms FROM ca_divisions").fetchone()[0])
        self.assertIn("corrected:40-3/C-510", terms)
        # a second retag finds nothing to do
        self.assertEqual(rt.retag(conn, TAX, WL, log=lambda *a: None), [])

    def test_the_trust_check_does_not_count_a_corrected_area_as_lost(self):
        conn = store()
        self.c510(conn)
        conn.execute("INSERT INTO ca_divisions (division_key, chamber, parliament, session, number, subject, "
                     "areas) VALUES ('commons-44-1-646', 'commons', 44, 1, 646, '3rd reading of Bill C-62, An "
                     "Act to amend An Act to amend the Criminal Code (medical assistance in dying), No. 2', '[2]')")
        said = []
        rt.retag(conn, TAX, WL, dry_run=True, log=said.append)      # 1 of 2 would be under the floor
        self.assertTrue(any("ca_divisions" in m and "1/1" in m for m in said), said)


def _load_tool(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
