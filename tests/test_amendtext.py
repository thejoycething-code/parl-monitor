"""The country-neutral half of amendment text (src/amendtext.py, 16 October 2026).

A fake reader over an in-memory store: the cache, the match, the ledger gate
(a tier-1 term in the purpose applies; one only in the body is stored for
review), the weekly re-apply after a collector reset the areas, and the
fail-loud gap for a text that cannot be read. The country readers have their
own tests with fixtures from live captures.
"""

import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import amendtext as at, db, filter as filt  # noqa: E402

def taxonomy():
    import yaml
    import tempfile
    raw = {"version": "t", "areas": {"1_abortion": {"tier1": ["abortion"], "tier2": ["family planning"]},
                                      "9_marriage": {"tier1": ["marriage"], "tier2": []}}}
    path = os.path.join(tempfile.mkdtemp(), "tax.yaml")
    with open(path, "w") as fh:
        yaml.safe_dump(raw, fh)
    return filt.load_taxonomy(path)


class FakeReader(at.Reader):
    cc, table, key_col = "xx", "xx_divisions", "division_key"

    def __init__(self, texts):
        self.texts, self.calls = texts, 0

    def taxonomy(self):
        return taxonomy(), filt.Watchlist(entities=[], bill_titles=[], act_shorts=[]), None

    def candidates(self, conn):
        return [dict(r) for r in conn.execute("SELECT division_key AS key, date, title, areas FROM xx_divisions")]

    def refs(self, row):
        return [row["title"].split()[-1]] if row["title"].startswith("Amendment") else []

    def fetch(self, row, refs):
        self.calls += 1
        got = self.texts.get(row["key"])
        if got is None:
            return at.unreadable(refs, "no such amendment {0}".format(refs[0]))
        return at.Lookup("ok", refs=refs, texts=[at.entry(refs[0], "amendment", refs[0], None, *got)])


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    conn.execute("CREATE TABLE xx_divisions (division_key TEXT PRIMARY KEY, date TEXT, title TEXT, "
                 "areas TEXT, matched_terms TEXT, tier INTEGER)")
    rows = [("v1", "2026-10-01", "Amendment 12", "[]"),
            ("v2", "2026-10-01", "Amendment 13", "[11]"),
            ("v3", "2026-10-02", "Amendment 14", "[]"),
            ("v4", "2026-10-02", "Final vote", "[]")]
    conn.executemany("INSERT INTO xx_divisions (division_key, date, title, areas) VALUES (?,?,?,?)", rows)
    return conn


TEXTS = {
    # purpose names abortion: the ledger opens
    "v1": ("Removes the abortion time limit.", "In section 1, leave out ..."),
    # abortion only in the body, as a cited statute: review only
    "v2": ("Extends the register of offenders.", "offences listed in the schedule, including abortion offences"),
}


class AmendTextTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        self.reader = FakeReader(TEXTS)

    def run_once(self, **kw):
        return {o.key: o for o in at.run(self.conn, self.reader, log=lambda *a: None, **kw)}

    def test_gate_applies_purpose_match_only(self):
        out = self.run_once()
        self.assertNotIn("v4", out)                      # not an amendment vote
        self.assertTrue(out["v1"].ledger)
        self.assertEqual(out["v1"].areas, [1])
        self.assertFalse(out["v2"].ledger)               # body only: gated
        self.assertEqual(out["v2"].areas, [1])
        row = self.conn.execute("SELECT areas, matched_terms, tier FROM xx_divisions "
                                "WHERE division_key='v1'").fetchone()
        self.assertEqual(json.loads(row[0]), [1])
        self.assertEqual(json.loads(row[1]), ["abortion"])
        self.assertEqual(row[2], 1)
        self.assertEqual(json.loads(self.conn.execute(
            "SELECT areas FROM xx_divisions WHERE division_key='v2'").fetchone()[0]), [11])
        saved = self.conn.execute("SELECT ledger, match_source FROM amendment_text "
                                  "WHERE cc='xx' AND division_key='v2'").fetchone()
        self.assertEqual(tuple(saved), (0, "amendment text"))

    def test_fail_loud_and_retry(self):
        out = self.run_once()
        self.assertEqual(out["v3"].status, "unreadable")
        self.assertIn("could not read amendment text (no such amendment 14)", out["v3"].gap)
        gaps = [r[0] for r in self.conn.execute("SELECT detail FROM gaps WHERE feed='xx-amendment-text'")]
        self.assertTrue(any("v3" in g for g in gaps))
        # failures are not cached: a second run asks again; successes are not re-fetched
        calls = self.reader.calls
        self.run_once()
        self.assertEqual(self.reader.calls - calls, 1)

    def test_reapply_after_collector_reset(self):
        self.run_once()
        self.conn.execute("UPDATE xx_divisions SET areas='[]', matched_terms='[]', tier=NULL "
                          "WHERE division_key='v1'")
        calls = self.reader.calls
        out = self.run_once()
        self.assertTrue(out["v1"].cached and out["v1"].changed)
        self.assertEqual(self.reader.calls - calls, 1)   # only v3, the failure, again
        self.assertEqual(json.loads(self.conn.execute(
            "SELECT areas FROM xx_divisions WHERE division_key='v1'").fetchone()[0]), [1])

    def test_limit_leaves_rest_for_next_run(self):
        out = self.run_once(limit=1)
        self.assertEqual(sorted(o.status for o in out.values()), ["ok", "skipped", "skipped"])

    def test_no_apply(self):
        self.run_once(apply=False)
        self.assertEqual(self.conn.execute(
            "SELECT areas FROM xx_divisions WHERE division_key='v1'").fetchone()[0], "[]")


if __name__ == "__main__":
    unittest.main()
