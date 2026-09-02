"""ECI watch (2026-09-02, from Christopher's "something must be missing"):
the citizens' instrument, taxonomy-matched, supporter deltas tracked.
First live pull found both million-signature ECIs on our ground (the
conversion-practices ban and My Voice, My Choice) plus a live digital-ID
initiative -- the gap was real.
"""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db


def _load():
    spec = importlib.util.spec_from_file_location(
        "eu_eci", os.path.join(ROOT, "tools", "eu_eci.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


eci = _load()

ENTRIES = {"entries": [
    {"pubRegNum": "ECI(2026)000001", "status": "ONGOING",
     "title": "My Voice, My Choice: For Safe And Accessible Abortion",
     "totalSupporters": 1124513, "supportLink": "https://eci.example/1"},
    {"pubRegNum": "ECI(2026)000002", "status": "ONGOING",
     "title": "European Public Social Network",
     "totalSupporters": 30, "supportLink": "https://eci.example/2"},
]}


class FakeClient:
    def __init__(self, bump=0):
        self.bump = bump

    def get_json(self, url, feed, slug, archive=True):
        # A real ECI holds ONE status; returning the same entries for both
        # status queries double-upserts within a single pull and wipes the
        # delta (how the first version of this test misled itself).
        if "ANSWERED" in url:
            return {"entries": []}
        import copy
        d = copy.deepcopy(ENTRIES)
        d["entries"][0]["totalSupporters"] += self.bump
        return d


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return conn


class EciTests(unittest.TestCase):
    def test_taxonomy_matches_and_offside_is_kept_unmatched(self):
        conn = store()
        n, ours, gaps = eci.pull(conn, FakeClient(), "2026-09-02",
                                 log=lambda *a: None)
        self.assertEqual(gaps, 0)
        row = conn.execute("SELECT * FROM eu_ecis WHERE reg_num = "
                           "'ECI(2026)000001'").fetchone()
        self.assertTrue(json.loads(row["areas"]))
        other = conn.execute("SELECT areas FROM eu_ecis WHERE reg_num = "
                             "'ECI(2026)000002'").fetchone()
        self.assertEqual(json.loads(other["areas"]), [])

    def test_supporter_delta_survives_the_upsert(self):
        conn = store()
        eci.pull(conn, FakeClient(), "2026-09-02", log=lambda *a: None)
        eci.pull(conn, FakeClient(bump=40000), "2026-09-09",
                 log=lambda *a: None)
        row = conn.execute("SELECT supporters, prev_supporters FROM eu_ecis "
                           "WHERE reg_num = 'ECI(2026)000001'").fetchone()
        self.assertEqual(row["supporters"] - row["prev_supporters"], 40000)

    def test_writes_eu_ecis_only(self):
        src = open(os.path.join(ROOT, "tools", "eu_eci.py"),
                   encoding="utf-8").read()
        self.assertNotIn("INSERT INTO items", src)
        self.assertNotIn("INTO mp_events", src)


if __name__ == "__main__":
    unittest.main()
