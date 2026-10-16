"""The shared government consultations and publications layer (src/gov_docs.py,
tools/country_gov_docs.py) and the US Federal Register mirror (16 October 2026)."""

import json
import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs as G  # noqa: E402
from src.gov_doc_sources import us  # noqa: E402

TODAY = "2026-10-16"


def store():
    return db.init_db(db.connect(":memory:"))


def fake_module(fetch, code="x", taxonomies=(("taxonomy.yaml", None),)):
    return types.SimpleNamespace(CC="zz", TAXONOMIES=taxonomies,
                                 SOURCES=(G.Source(code=code, name="Test source", fetch=fetch),))


class HelperTests(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(G.iso("2026-11-04T12:00:00Z"), "2026-11-04")
        self.assertEqual(G.iso("4.11.2026"), "2026-11-04")
        self.assertEqual(G.iso("04/11/2026"), "2026-11-04")
        self.assertIsNone(G.iso("31.02.2026"))
        self.assertEqual(G.long_date("bis 4. November 2026"), "2026-11-04")
        self.assertEqual(G.long_date("hasta el 4 de noviembre de 2026"), "2026-11-04")
        self.assertEqual(G.long_date("jusqu'au 4 decembre 2026"), "2026-12-04")
        self.assertEqual(G.long_date("1 março 2026"), "2026-03-01")

    def test_entry_refuses_an_unknown_type(self):
        with self.assertRaises(ValueError):
            G.entry("x", "1", "T", "memo")

    def test_entry_shape(self):
        e = G.entry("bmj", "abc", "  Entwurf  eines\nGesetzes ", "bill_draft", published="1.10.2026",
                    closing_date="2026-11-01", summary="x" * 5000)
        self.assertEqual(e["doc_id"], "bmj:abc")
        self.assertEqual(e["title"], "Entwurf eines Gesetzes")
        self.assertEqual(e["published"], "2026-10-01")
        self.assertEqual(len(e["summary"]), G.SUMMARY_CAP)

    def test_window(self):
        old = G.entry("x", "1", "T", "consultation", published="2026-01-01", closing_date="2026-11-01")
        self.assertTrue(G.in_window(old, TODAY))           # still open
        stale = G.entry("x", "2", "T", "publication", published="2026-01-01")
        self.assertFalse(G.in_window(stale, TODAY))
        recent = G.entry("x", "3", "T", "publication", published="2026-09-01")
        self.assertTrue(G.in_window(recent, TODAY))


class GateTests(unittest.TestCase):
    def setUp(self):
        self.taxes = G.taxonomies("us")
        self.wl = {}

    def test_consultation_kept_on_any_match_publication_needs_tier_1(self):
        c = G.classify(G.entry("x", "1", "Consultation on relationships and sex education in schools",
                               "consultation"), self.taxes, self.wl)
        self.assertTrue(c["areas"])
        self.assertTrue(G.on_ground(c))
        p = dict(c, doc_type="publication", tier=2)
        self.assertFalse(G.on_ground(p))
        self.assertTrue(G.on_ground(dict(p, tier=1)))

    def test_migration_alone_is_not_our_ground(self):
        self.assertFalse(G.on_ground({"areas": [11], "doc_type": "consultation", "tier": 1}))

    def test_watched_is_kept(self):
        e = G.classify(G.entry("x", "K-1", "Unrelated title", "publication"), self.taxes, {"K-1": {}})
        self.assertEqual(e["watch_keys"], ["K-1"])
        self.assertTrue(G.on_ground(e))

    def test_preclassified_is_kept_as_it_is(self):
        e = G.entry("fr", "1", "Unrelated title", "regulation", classified=("[1, 6]", '["abortion"]', 1))
        got = G.classify(e, self.taxes, self.wl)
        self.assertEqual(got["areas"], [1, 6])
        self.assertEqual(got["tier"], 1)


class CollectTests(unittest.TestCase):
    def test_collect_stores_what_is_on_our_ground_and_records_the_run(self):
        def fetch(client, today, log):
            return G.fetched([
                G.entry("x", "a", "Consultation on assisted dying for terminally ill adults", "consultation",
                        body="Ministry", published="2026-10-01", closing_date="2026-11-20", url="https://e/a"),
                G.entry("x", "b", "Road haulage permits", "consultation", published="2026-10-01",
                        closing_date="2026-11-20"),
            ], note="2 listed")
        conn = store()
        listed, kept, gaps = G.collect(conn, "zz", None, TODAY, log=lambda *a: None, mod=fake_module(fetch))
        self.assertEqual((listed, kept, gaps), (2, 1, 0))
        row = conn.execute("SELECT * FROM gov_docs").fetchone()
        self.assertEqual((row["cc"], row["doc_id"], row["closing_date"], row["body"]),
                         ("zz", "x:a", "2026-11-20", "Ministry"))
        run = conn.execute("SELECT ok, listed, kept FROM gov_doc_runs").fetchone()
        self.assertEqual(tuple(run), (1, 2, 1))
        dl = G.deadline_rows(conn, "zz", TODAY, "2026-12-31")
        self.assertEqual([d["doc_id"] for d in dl], ["x:a"])
        self.assertEqual(G.deadline_rows(conn, "zz", TODAY, "2026-11-01"), [])
        self.assertIn("Test source: read 2026-10-16, 2 listed, 1 on our ground",
                      G.coverage_lines(conn, "zz", mod=fake_module(fetch))[0])

    def test_a_rerun_keeps_first_seen_and_a_known_closing_date(self):
        calls = []

        def fetch(client, today, log):
            calls.append(today)
            close = "2026-11-20" if len(calls) == 1 else None
            return G.fetched([G.entry("x", "a", "Consultation on abortion services", "consultation",
                                      published="2026-10-01", closing_date=close)])
        conn = store()
        mod = fake_module(fetch)
        G.collect(conn, "zz", None, TODAY, log=lambda *a: None, mod=mod)
        G.collect(conn, "zz", None, "2026-10-23", log=lambda *a: None, mod=mod)
        r = conn.execute("SELECT first_seen, last_seen, closing_date FROM gov_docs").fetchone()
        self.assertEqual(tuple(r), (TODAY, "2026-10-23", "2026-11-20"))

    def test_a_failed_source_is_a_gap_not_a_crash(self):
        def fetch(client, today, log):
            raise RuntimeError("boom")
        conn = store()
        listed, kept, gaps = G.collect(conn, "zz", None, TODAY, log=lambda *a: None, mod=fake_module(fetch))
        self.assertEqual((listed, kept, gaps), (0, 0, 1))
        self.assertEqual(conn.execute("SELECT feed FROM gaps").fetchone()[0], "zz-govdocs-x")
        self.assertEqual(conn.execute("SELECT ok FROM gov_doc_runs").fetchone()[0], 0)

    def test_an_empty_answer_is_a_gap(self):
        conn = store()
        _l, _k, gaps = G.collect(conn, "zz", None, TODAY, log=lambda *a: None,
                                 mod=fake_module(lambda c, t, l: G.fetched([])))
        self.assertEqual(gaps, 1)
        line = G.coverage_lines(conn, "zz")[0]
        self.assertIn("gap: answered but nothing parsed", line)

    def test_every_reader_module_imports_and_declares_sources(self):
        for cc in G.countries():
            mod = G.module(cc)
            self.assertTrue(mod.SOURCES, cc)
            for s in mod.SOURCES:
                self.assertTrue(s.fetch or s.mirror, (cc, s.code))
                self.assertNotIn(":", s.code)
            self.assertTrue(G.taxonomies(cc, mod=mod), cc)


class RobotsTests(unittest.TestCase):
    """A reader fetches through the guarded client: a disallowed page is a gap."""

    def run_with(self, robots):
        from tests.robots_fakes import guarded_api

        class Inner:
            asked = []

            def get_text(self, url, feed, slug, *a, **kw):
                self.asked.append(url)
                return "Consultation on abortion services|2026-11-30"

        inner = Inner()
        inner.asked = []
        client, _ = guarded_api(inner, {"ex.gov": robots}, "country-gov-docs")

        def fetch(client, today, log):
            title, close = client.get_text("https://ex.gov/consultations", "f", "s").split("|")
            return G.fetched([G.entry("x", "1", title, "consultation", published=today,
                                      closing_date=close)])
        conn = store()
        got = G.collect(conn, "zz", client, TODAY, log=lambda *a: None, mod=fake_module(fetch))
        return got, inner, conn

    def test_disallowed_is_a_gap_and_never_fetched(self):
        (listed, kept, gaps), inner, conn = self.run_with("User-agent: *\nDisallow: /consultations\n")
        self.assertEqual((listed, kept, gaps), (0, 0, 1))
        self.assertEqual(inner.asked, [])
        self.assertIn("robots.txt disallows", conn.execute("SELECT detail FROM gaps").fetchone()[0])

    def test_allowed_is_read(self):
        (listed, kept, gaps), inner, _ = self.run_with(404)
        self.assertEqual((listed, kept, gaps), (1, 1, 0))
        self.assertEqual(inner.asked, ["https://ex.gov/consultations"])


class UsMirrorTests(unittest.TestCase):
    def test_proposed_rules_become_deadlines(self):
        conn = store()
        rows = [
            ("2026-20277", "Proposed Rule", None, "Federal Scholarship Tax Credit", "abs", "Proposed rule.",
             json.dumps(["Treasury Department"]), "2026-10-02", "2026-12-01", "https://fr/a", "[6]",
             '["scholarship"]', 2),
            ("2026-1", "Rule", None, "Hospice wage index", None, "Final rule.", "[]", "2026-09-01", None,
             None, "[2]", "[]", 2),
            ("2026-2", "Rule", None, "Recodification of Title IX Rules", None, "Final rule.", "[]",
             "2026-09-01", None, None, "[5]", "[]", 1),
            ("2025-1", "Proposed Rule", None, "Old", None, None, "[]", "2025-01-01", "2025-02-01", None,
             "[1]", "[]", 1),
        ]
        conn.executemany("INSERT INTO us_fr_documents (document_number, doc_type, subtype, title, abstract, "
                         "action, agencies, publication_date, comments_close_on, html_url, areas, "
                         "matched_terms, tier) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        G.collect(conn, "us", None, TODAY, log=lambda *a: None)
        got = {r["doc_id"]: dict(r) for r in conn.execute("SELECT * FROM gov_docs WHERE cc='us'")}
        self.assertEqual(set(got), {"fr:2026-20277", "fr:2026-2"})
        self.assertEqual(got["fr:2026-20277"]["doc_type"], "regulation_draft")
        self.assertEqual(got["fr:2026-20277"]["closing_date"], "2026-12-01")
        self.assertEqual(got["fr:2026-20277"]["body"], "Treasury Department")
        self.assertEqual(got["fr:2026-2"]["doc_type"], "regulation")
        self.assertEqual([d["doc_id"] for d in G.deadline_rows(conn, "us", TODAY, "2026-12-31")],
                         ["fr:2026-20277"])

    def test_an_empty_mirror_is_a_gap(self):
        conn = store()
        _l, _k, gaps = G.collect(conn, "us", None, TODAY, log=lambda *a: None)
        self.assertEqual(gaps, 1)


if __name__ == "__main__":
    unittest.main()
