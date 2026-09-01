"""EU triage (Christopher, 2026-09-01: "Triage the EU items"): the same
judge Westminster items get, over every taxonomy-matched EU row. Scored
once, ever; stub fallback without a key; spend recorded.
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

from src import db, triage


def _load():
    spec = importlib.util.spec_from_file_location(
        "eu_triage", os.path.join(ROOT, "tools", "eu_triage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


eut = _load()


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    eut.ensure_columns(conn)
    conn.execute("INSERT INTO eu_consultations (key, title, summary, areas, "
                 "tier, first_seen, last_seen) VALUES ('1', 'Fitness check "
                 "on abortion access', 'framework text', '[1]', 1, "
                 "'2026-09-01', '2026-09-01')")
    conn.execute("INSERT INTO eu_divisions (vote_id, label, areas, tier, "
                 "first_seen, last_seen) VALUES ('D1', 'ePrivacy scanning "
                 "derogation', '[6]', 2, '2026-09-01', '2026-09-01')")
    conn.execute("INSERT INTO eu_texts (identifier, title, areas, tier, "
                 "first_seen, last_seen) VALUES ('TA-1', 'CAP transition', "
                 "'[]', NULL, '2026-09-01', '2026-09-01')")
    conn.commit()
    return conn


class TriageTests(unittest.TestCase):
    def test_only_matched_rows_are_judged(self):
        conn = store()
        items = eut.pending(conn)
        self.assertEqual(sorted(i.id for i in items),
                         ["eu_consultations:1", "eu_divisions:D1"])

    def test_stub_scores_apply_and_never_rescore(self):
        conn = store()
        results = triage.score_stub(eut.pending(conn))
        eut.apply(conn, results)
        row = conn.execute("SELECT triage_score FROM eu_consultations "
                           "WHERE key='1'").fetchone()
        self.assertEqual(row["triage_score"], 2)   # tier 1 -> 2 in the stub
        self.assertEqual(eut.pending(conn), [],
                         "scored once, ever: nothing left to judge")

    def test_scores_land_on_the_right_table_and_key(self):
        conn = store()
        eut.apply(conn, [triage.TriageResult(
            id="eu_divisions:D1", score=3, areas=[6],
            why_it_matters="Scanning precedent.")])
        row = conn.execute("SELECT triage_score, why_it_matters FROM "
                           "eu_divisions WHERE vote_id='D1'").fetchone()
        self.assertEqual((row["triage_score"], row["why_it_matters"]),
                         (3, "Scanning precedent."))


if __name__ == "__main__":
    unittest.main()
