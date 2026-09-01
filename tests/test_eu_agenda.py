"""EU plenary forward look, phase 2b (Caroline's 1-2 month ask lands
here): the EP publishes each sitting's foreseen agenda weeks ahead;
every EN label is taxonomy-matched, matches surface dated, the rest are
counted per sitting -- never dropped, never printed 65-deep either.

Shapes from the live probe: foreseen-activities answers 204 with an
EMPTY body for far-future sittings, and some 404 instead -- both mean
"agenda not yet published", neither is a gap.
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
from src.http import FetchError


def _load():
    spec = importlib.util.spec_from_file_location(
        "eu_agenda", os.path.join(ROOT, "tools", "eu_agenda.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


eua = _load()

MEETINGS = {"data": [
    {"activity_id": "MTG-PL-2026-09-14", "activity_date": "2026-09-14"},
    {"activity_id": "MTG-PL-2026-10-20", "activity_date": "2026-10-20"},
    {"activity_id": "MTG-PL-2026-12-14", "activity_date": "2026-12-14"},
    {"activity_id": "MTG-PL-2026-08-01", "activity_date": "2026-08-01"},
]}

FORESEEN = {"data": [
    {"activity_id": "MTG-PL-2026-09-14-OJ-ITM-D-2",
     "activity_date": "2026-09-14",
     "had_activity_type": "def/ep-activities/PLENARY_DEBATE",
     "activity_label": {"en": "Findings of the Special Committee on the "
                              "European Democracy Shield"}},
    {"activity_id": "MTG-PL-2026-09-14-OJ-ITM-D-3",
     "activity_date": "2026-09-14",
     "had_activity_type": "def/ep-activities/PLENARY_VOTE",
     "activity_label": {"en": "Carbon Border Adjustment Mechanism"}},
]}


class FakeClient:
    def get_json(self, url, feed, slug, archive=True):
        if "meetings?year" in url.replace("%3F", "?") or "year=" in url:
            return MEETINGS
        if "MTG-PL-2026-09-14" in url:
            return FORESEEN
        if "MTG-PL-2026-10-20" in url:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        raise ValueError("empty 204 body")


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return conn


class AgendaTests(unittest.TestCase):
    def test_horizon_matching_and_quiet_unpublished_agendas(self):
        conn = store()
        total, ours, gaps = eua.pull(conn, FakeClient(), "2026-09-01",
                                     log=lambda *a: None)
        # 14 Sep inside horizon and published; 20 Oct 404s quietly; 14 Dec
        # is beyond 60 days and 1 Aug is past -- neither even fetched.
        self.assertEqual((total, ours, gaps), (2, 1, 0))
        row = conn.execute("SELECT * FROM eu_agenda WHERE areas != '[]'"
                           ).fetchone()
        self.assertIn("Democracy Shield", row["label"])
        self.assertEqual(json.loads(row["areas"]), [7])
        self.assertEqual(row["activity_type"], "PLENARY_DEBATE")

    def test_coming_up_counts_the_unmatched_rather_than_dropping_them(self):
        conn = store()
        eua.pull(conn, FakeClient(), "2026-09-01", log=lambda *a: None)
        matched, per_day = eua.coming_up(conn, "2026-09-01")
        self.assertEqual(len(matched), 1)
        self.assertEqual(per_day, {"2026-09-14": 2})

    def test_the_tool_writes_eu_agenda_only(self):
        src = open(os.path.join(ROOT, "tools", "eu_agenda.py"),
                   encoding="utf-8").read()
        self.assertNotIn("INSERT INTO items", src)
        self.assertNotIn("INTO mp_events", src)


if __name__ == "__main__":
    unittest.main()
