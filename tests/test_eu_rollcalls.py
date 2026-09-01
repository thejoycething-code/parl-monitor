"""EU roll calls, phase 2d: collected, never judged. eu_divisions has no
our_side column BY DESIGN -- verdicts are signed off per division by
Christopher (the Lords inversion lesson), and the eventual EU 5CA builds
on this data only after that flow exists.
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
        "eu_rollcalls", os.path.join(ROOT, "tools", "eu_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


eur = _load()

MEETINGS = {"data": [
    {"activity_id": "MTG-PL-2026-07-09", "activity_date": "2026-07-09"}]}
RESULTS = {"data": [
    {"activity_id": "V1", "had_activity_type": "def/ep-activities/PLENARY_VOTE_RESULTS",
     "activity_label": {"en": "Ongoing persecution of Christians in Nigeria"},
     "consists_of": ["eli/dl/event/MTG-PL-2026-07-09-DEC-195719"]},
    {"activity_id": "V2", "had_activity_type": "def/ep-activities/PLENARY_VOTE_RESULTS",
     "activity_label": {"en": "Common agricultural policy transition"},
     "consists_of": ["eli/dl/event/MTG-PL-2026-07-09-DEC-195720"]},
    {"activity_id": "R1", "had_activity_type": "def/ep-activities/REQUEST_VOTE_ROLLCALL",
     "activity_label": {"en": "noise entry the type filter must drop"}},
]}
EVENT = {"data": [{
    "number_of_votes_favor": 2, "number_of_votes_against": 1,
    "number_of_votes_abstention": 0,
    "had_voter_favor": ["person/1", "person/2"],
    "had_voter_against": ["person/3"],
    "had_voter_abstention": []}]}
MEPS = {"data": [{"id": "person/1", "identifier": "1", "label": "A MEP"}]}


class FakeClient:
    def __init__(self):
        self.event_calls = 0

    def get_json(self, url, feed, slug, archive=True):
        if "meps" in url:
            return MEPS
        if "meetings?year" in url or "year=" in url:
            return MEETINGS
        if "vote-results" in url:
            return RESULTS
        if "/events/" in url:
            self.event_calls += 1
            return EVENT
        raise AssertionError(url)


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return conn


class RollCallTests(unittest.TestCase):
    def test_only_matched_votes_cost_an_event_fetch(self):
        conn = store()
        client = FakeClient()
        seen, matched, gaps = eur.pull(conn, client, "2026-09-01",
                                       log=lambda *a: None)
        self.assertEqual((seen, matched, gaps), (2, 1, 0))
        self.assertEqual(client.event_calls, 1,
                         "the CAP vote must not cost a roll-call fetch")
        row = conn.execute("SELECT * FROM eu_divisions").fetchone()
        self.assertEqual(json.loads(row["areas"]), [8])
        self.assertEqual((row["favor"], row["against"]), (2, 1))
        votes = {r["person_id"]: r["position"] for r in
                 conn.execute("SELECT * FROM eu_votes")}
        self.assertEqual(votes, {"1": "favor", "2": "favor", "3": "against"})

    def test_no_verdict_column_exists_to_be_wrongly_filled(self):
        conn = store()
        cols = [c[1] for c in conn.execute("PRAGMA table_info(eu_divisions)")]
        for banned in ("our_side", "verdict", "good", "meaning_aye"):
            self.assertNotIn(banned, cols)

    def test_roster_upserts(self):
        conn = store()
        n = eur.refresh_roster(conn, FakeClient(), "2026-09-01",
                               log=lambda *a: None)
        self.assertEqual(n, 1)
        self.assertEqual(conn.execute("SELECT name FROM eu_meps").fetchone()[0],
                         "A MEP")

    def test_the_tool_writes_eu_tables_only(self):
        src = open(os.path.join(ROOT, "tools", "eu_rollcalls.py"),
                   encoding="utf-8").read()
        self.assertNotIn("INSERT INTO items", src)
        self.assertNotIn("INTO mp_events", src)


if __name__ == "__main__":
    unittest.main()
