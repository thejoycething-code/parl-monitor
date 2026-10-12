"""The Federal Register collector (tools/us_federal_register.py).

No network. tests/fixtures/us_fr/documents.json is nine real results from
federalregister.gov/api/v1/documents.json, fetched 9 October 2026: two
executive orders on our ground, the noise the taxonomy v1.18 vetoes were
written for (a pollutant 'surrogate', a wildlife contraceptive, 'unborn'
livestock), an immigration rule carrying the CFR's foster-care boilerplate,
and rules and proposed rules on and off our ground.
"""

import datetime
import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "us_fr", "documents.json")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fr = _load("us_federal_register")
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))


def page():
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


class FakeClient:
    """Answers every documents query with the fixture page; records URLs."""

    def __init__(self, pages=None):
        self.urls, self.pages = [], pages

    def get_json(self, url, feed, slug, timeout=None, archive=True):
        self.urls.append(url)
        if self.pages:
            return self.pages.pop(0)
        return page()


def store():
    return db.init_db(sqlite3.connect(":memory:"))


def docs():
    return {r["document_number"]: fr.parse_document(r) for r in page()["results"]}


class ParseTests(unittest.TestCase):
    def test_an_executive_order_keeps_its_number_and_subtype(self):
        d = docs()["2025-02194"]
        self.assertEqual(d["doc_type"], "Presidential Document")
        self.assertEqual(d["subtype"], "Executive Order")
        self.assertEqual(d["eo_number"], "14187")
        self.assertIsNone(d["abstract"])

    def test_a_proposed_rule_keeps_its_comment_deadline_and_link(self):
        d = docs()["2026-20329"]
        self.assertEqual(d["doc_type"], "Proposed Rule")
        self.assertEqual(d["comments_close_on"], "2026-11-04")
        self.assertIn("regulations.gov", d["comment_url"])
        self.assertTrue(d["agencies"])


class ClassifyTests(unittest.TestCase):
    wl = fr.empty_watchlist()

    def areas(self, number):
        return fr.classify(TAX, self.wl, docs()[number]).issue_areas

    def test_executive_orders_on_our_ground_match_on_the_title(self):
        self.assertIn(1, self.areas("2025-02175"))          # Enforcing the Hyde Amendment
        self.assertIn(3, self.areas("2025-02194"))          # chemical and surgical mutilation

    def test_a_pollutant_surrogate_is_not_surrogacy(self):
        self.assertEqual(self.areas("2025-10992"), [])

    def test_a_wildlife_contraceptive_is_not_area_1(self):
        self.assertEqual(self.areas("2026-20219"), [])

    def test_unborn_livestock_is_not_area_1(self):
        self.assertEqual(self.areas("2026-13878"), [])

    def test_the_cfr_foster_care_boilerplate_on_an_immigration_rule_is_dropped(self):
        d = docs()["2026-13392"]
        self.assertIn("Adoption and foster care", d["topics"])
        self.assertNotIn("Adoption and foster care", fr.classified_topics(d["topics"]))
        self.assertFalse(fr.on_our_ground(self.areas("2026-13392")))

    def test_the_boilerplate_term_is_kept_without_its_immigration_company(self):
        self.assertEqual(fr.classified_topics(["Adoption and foster care", "Grant programs"]),
                         ["Adoption and foster care", "Grant programs"])

    def test_a_child_welfare_proposed_rule_is_on_our_ground(self):
        self.assertIn(6, self.areas("2026-20329"))

    def test_an_airworthiness_directive_is_not(self):
        self.assertEqual(self.areas("2026-20701"), [])


class PullTests(unittest.TestCase):
    def test_the_first_run_starts_at_the_inauguration_and_stores_everything(self):
        conn = store()
        client = FakeClient()
        read, ours, gaps = fr.pull(conn, client, "2026-10-09", tax=TAX, log=lambda *a: None)
        self.assertEqual((read, gaps), (9, 0))
        self.assertIn("2025-01-20", client.urls[0])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM us_fr_documents").fetchone()[0], 9)
        # Hyde, mutilation, child welfare, Title IX recodification
        self.assertEqual(ours, 4)

    def test_a_later_run_reads_from_the_latest_date_less_the_overlap(self):
        conn = store()
        fr.pull(conn, FakeClient(), "2026-10-09", tax=TAX, log=lambda *a: None)
        latest = conn.execute("SELECT MAX(publication_date) FROM us_fr_documents").fetchone()[0]
        expect = (datetime.date.fromisoformat(latest)
                  - datetime.timedelta(days=fr.OVERLAP_DAYS)).isoformat()
        self.assertEqual(fr.start_date(conn), expect)

    def test_a_rerun_restamps_and_keeps_the_score(self):
        conn = store()
        fr.pull(conn, FakeClient(), "2026-10-01", tax=TAX, log=lambda *a: None)
        conn.execute("UPDATE us_fr_documents SET triage_score=3 WHERE document_number='2025-02175'")
        fr.pull(conn, FakeClient(), "2026-10-09", tax=TAX, log=lambda *a: None)
        row = conn.execute("SELECT triage_score, first_seen, last_seen FROM us_fr_documents "
                           "WHERE document_number='2025-02175'").fetchone()
        self.assertEqual(row, (3, "2026-10-01", "2026-10-09"))

    def test_a_window_over_the_api_cap_is_split(self):
        big = dict(page(), count=fr.API_CAP + 1)
        client = FakeClient(pages=[big, page(), page()])
        out = fr.fetch_window(client, "2025-01-20", "2025-12-31", log=lambda *a: None)
        self.assertEqual(len(client.urls), 3)
        self.assertEqual(len(out), 18)

    def test_a_failed_fetch_is_a_gap_not_an_empty_week(self):
        from src.http import FetchError

        class Down:
            def get_json(self, *a, **k):
                raise FetchError("u", "f", "s", 3, "timed out")
        conn = store()
        self.assertEqual(fr.pull(conn, Down(), "2026-10-09", tax=TAX, log=lambda *a: None),
                         (0, 0, 1))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed=?",
                                      (fr.FEED,)).fetchone()[0], 1)

    def test_reclassify_is_offline_and_idempotent(self):
        conn = store()
        fr.pull(conn, FakeClient(), "2026-10-09", tax=TAX, log=lambda *a: None)
        self.assertEqual(fr.reclassify(conn, TAX, log=lambda *a: None), 0)


if __name__ == "__main__":
    unittest.main()
