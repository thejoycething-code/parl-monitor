"""The 2026-09-02 gap builds: Strasbourg watch, EP written questions, and
the cross-parliament synthesis. Council votes are NOT here and cannot be:
the upstream dataset is officially discontinued and the site is
challenge-walled -- recorded in the spec, not worked around silently.
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

from src import across, db


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


courts = _load("eu_courts")
pqs = _load("eu_pqs")


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return conn


class CourtsTests(unittest.TestCase):
    def test_hudoc_grammar_is_bare_terms_never_fulltext_field(self):
        src = open(os.path.join(ROOT, "tools", "eu_courts.py"),
                   encoding="utf-8").read()
        self.assertNotIn("fulltext:", src.replace(
            "the fulltext: field syntax silently", ""))
        self.assertIn('contentsitename:ECHR', src)

    def test_matched_judgments_store_with_case_link(self):
        conn = store()

        class C:
            def get_json(self, url, feed, slug, archive=True):
                return {"results": [{"columns": {
                    "itemid": "001-1", "docname": "CASE OF X v. POLAND "
                    "surrogacy parenthood", "doctype": "HEJUD",
                    "appno": "1/26", "conclusion": "Violation of Art 8",
                    "kpdate": "2026-07-02T00:00:00", "respondent": "POL"}}]}
        seen, stored, gaps = courts.pull(conn, C(), "2026-09-02",
                                         log=lambda *a: None)
        self.assertEqual(gaps, 0)
        self.assertGreaterEqual(stored, 1)
        row = conn.execute("SELECT * FROM eu_judgments").fetchone()
        self.assertEqual(row["url"], "https://hudoc.echr.coe.int/eng?i=001-1")
        self.assertTrue(json.loads(row["areas"]))


class PqTests(unittest.TestCase):
    def test_cap_and_newest_first_are_structural(self):
        src = open(os.path.join(ROOT, "tools", "eu_pqs.py"),
                   encoding="utf-8").read()
        self.assertIn("FETCH_CAP", src)
        self.assertIn("reverse=True", src)
        self.assertIn("disclosed, not silent", src)


class AcrossTests(unittest.TestCase):
    def test_an_area_needs_two_jurisdictions_to_render(self):
        conn = store()
        conn.execute("INSERT INTO items (id, captured_at, source_feed, "
                     "item_type, title, issue_areas, tier) VALUES "
                     "('x', '2026-09-01', 'pq', 'q', 'Abortion time limit "
                     "question', '[1]', 1)")
        conn.execute("INSERT INTO dg_consultations (key, nation, title, "
                     "areas, closes, first_seen, last_seen) VALUES "
                     "('s:1', 'scotland', 'Abortion law reform', '[1]', "
                     "'2026-10-01', 'x', 'x')")
        conn.execute("INSERT INTO eu_ecis (reg_num, title, status, areas, "
                     "first_seen, last_seen) VALUES ('E1', 'Ban conversion "
                     "practices', 'ONGOING', '[4]', 'x', 'x')")
        conn.commit()
        themes = across.collect(conn, "2026-09-02")
        md = across.render(themes, {1: "Abortion", 4: "Conversion practices"})
        self.assertIn("**Abortion** (2 jurisdictions)", md)
        self.assertIn("Westminster: Abortion time limit question", md)
        self.assertIn("Scotland: Abortion law reform", md)
        # conversion practices is EU-only -> must NOT render
        self.assertNotIn("Conversion practices", md)

    def test_tier2_westminster_noise_stays_out(self):
        conn = store()
        conn.execute("INSERT INTO items (id, captured_at, source_feed, "
                     "item_type, title, issue_areas, tier, triage_score) "
                     "VALUES ('n', '2026-09-01', 'pq', 'q', 'Charity "
                     "fundraiser mentioning hospice', '[2]', 2, 1)")
        conn.commit()
        themes = across.collect(conn, "2026-09-02")
        self.assertNotIn(2, themes)

    def test_nothing_crossing_renders_nothing(self):
        self.assertIsNone(across.render({1: {"EU": [("x", "")]}},
                                        {1: "Abortion"}))


if __name__ == "__main__":
    unittest.main()
