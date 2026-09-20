"""A drain's wall clock (src/drain.py) and the two drains that carry it."""

import importlib.util
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, drain  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BudgetTests(unittest.TestCase):
    def test_exhaustion_is_read_off_the_injected_clock(self):
        t = [100.0]
        b = drain.Budget(30, clock=lambda: t[0])
        self.assertFalse(b.exhausted())
        t[0] = 129.9
        self.assertFalse(b.exhausted())
        t[0] = 130.0
        self.assertTrue(b.exhausted())
        self.assertIn("time budget (30s) reached after 7 question fetches", b.disclose("question fetches", 7))
        self.assertIn("disclosed, not silent", b.disclose("x", 0))

    def test_the_default_is_a_step_not_a_job(self):
        self.assertLessEqual(drain.DEFAULT_S, 600)


class Listing:
    """Serves a listing of stubs and counts detail fetches."""

    def __init__(self, idents):
        self.idents, self.details = idents, 0

    def get_json(self, url, feed, slug, archive=True):
        if "offset=" in url or "limit=1000" in url:
            return {"data": [{"identifier": i} for i in self.idents]}
        self.details += 1
        return {"data": [{"title_dcterms": {"en": "Abortion access in Poland"},
                          "document_date": "2026-09-01", "creator": ["person/1"]}]}


class DrainClockTests(unittest.TestCase):
    """19 Sept 2026: the EU weekly was cancelled twice at the written-question
    drain. A count cap bounds the API; only a clock bounds the job."""

    def test_the_question_drain_stops_on_the_clock_and_says_so(self):
        eup = _load("eu_pqs")
        conn = sqlite3.connect(":memory:"); conn.row_factory = sqlite3.Row; db.init_db(conn)
        client = Listing(["E-%06d/2026" % i for i in range(1, 6)])
        logged = []
        eup.THROTTLE_S = 0
        new, ours, gaps = eup.pull(conn, client, "2026-09-19", log=logged.append, budget_s=0)
        self.assertEqual((new, client.details), (0, 0), "an exhausted clock fetches nothing")
        self.assertTrue(any("time budget" in l and "disclosed, not silent" in l for l in logged), logged)

    def test_with_time_the_question_drain_runs_as_before(self):
        eup = _load("eu_pqs")
        conn = sqlite3.connect(":memory:"); conn.row_factory = sqlite3.Row; db.init_db(conn)
        client = Listing(["E-%06d/2026" % i for i in range(1, 4)])
        eup.THROTTLE_S = 0
        new, ours, gaps = eup.pull(conn, client, "2026-09-19", log=lambda *a: None, budget_s=600)
        self.assertEqual((new, ours, client.details), (3, 3, 3))

    def test_the_committee_drain_carries_the_same_clock(self):
        cm = _load("eu_committees")
        conn = sqlite3.connect(":memory:"); conn.row_factory = sqlite3.Row; db.init_db(conn)
        prefix = sorted(cm.COMMITTEES)[0]
        client = Listing(["%s-AM-%d" % (prefix, i) for i in range(1, 4)])
        logged = []
        cm.THROTTLE_S = 0
        cm.pull_docs(conn, client, "2026-09-19", log=logged.append, budget_s=0)
        self.assertEqual(client.details, 0)
        self.assertTrue(any("time budget" in l for l in logged), logged)


if __name__ == "__main__":
    unittest.main()
