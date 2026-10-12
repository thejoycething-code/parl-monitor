"""CH6 (Chris, 10 October 2026): Italy's list on the Swiss Italian texts
(tools/ch_rollcalls.py, src/ch_store.py). No network: business_it.json.gz is
a trim of the Italian Business pages read live on 10 October 2026."""

import gzip
import importlib.util
import json
import os
import re
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ch_store, db  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "ch")


def _load():
    spec = importlib.util.spec_from_file_location(
        "ch_rollcalls_it", os.path.join(ROOT, "tools", "ch_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


chr_ = _load()
TAX = chr_.Taxonomies()


def italian_rows():
    with gzip.open(os.path.join(FIX, "business_it.json.gz"), "rt", encoding="utf-8") as fh:
        return json.load(fh)["d"]


def store():
    return db.init_db(sqlite3.connect(":memory:"))


def business(bid, title, text="", btype="Mo."):
    return {"ID": bid, "BusinessShortNumber": ch_store.short_number(bid),
            "BusinessTypeAbbreviation": btype, "Title": title, "Description": None,
            "SubmittedText": text, "SubmittedBy": "Muster Hans", "BusinessStatusText": "Erledigt",
            "BusinessStatusDate": "/Date(1790899200000)/", "SubmissionDate": "/Date(1757289600000)/",
            "SubmissionCouncilAbbreviation": "NR", "SubmissionLegislativePeriod": 52,
            "ResponsibleDepartmentAbbreviation": "EDI", "TagNames": "Gesundheit",
            "Modified": "/Date(1790899200000)/"}


class FakeClient:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get_json(self, url, feed, slug, timeout=None, archive=True):
        self.calls.append(url)
        for needle, answer in self.routes.items():
            if needle in url:
                if answer is None:
                    raise FetchError(url, feed, slug, 1, "HTTP Error 503")
                return answer(url) if callable(answer) else answer
        raise FetchError(url, feed, slug, 1, "404")


def by_id(rows):
    return {r["ID"]: r for r in rows}


class ItalianTaxonomyTests(unittest.TestCase):
    def test_the_italian_list_loads_for_ch_without_italy_only_terms(self):
        self.assertIsNotNone(TAX.it)
        terms = {t for tiers in TAX.it.terms.values() for compiled in tiers.values()
                 for t, *_ in compiled}
        self.assertIn("aborto", terms)
        self.assertNotIn("legge 194", terms)       # [only: it]
        self.assertNotIn("otto per mille", terms)  # [only: it]

    def test_an_italian_title_alone_puts_a_business_on_our_ground(self):
        rows = by_id(italian_rows())
        it = chr_.parse_business(rows[20243038])
        de = chr_.parse_business(business(20243038, "Irgendein Titel ohne Treffer"))
        conn = store()
        areas = chr_.store_business(conn, TAX, de, None, "2026-10-10", it=it)
        self.assertIn(7, areas)
        row = conn.execute("SELECT title_it, areas_it, terms_it, tier_it, areas FROM "
                           "ch_businesses WHERE business_id=20243038").fetchone()
        self.assertTrue(row[0].startswith("Respingere il progetto CA+"))
        self.assertEqual(json.loads(row[1]), [7])
        self.assertIn("OMS", json.loads(row[2]))
        self.assertEqual(row[3], 1)                # 'Regolamento sanitario internazionale'

    def test_a_german_and_french_refresh_keeps_the_italian_result(self):
        rows = by_id(italian_rows())
        conn = store()
        de = chr_.parse_business(business(20252031, "Ein Titel ohne Treffer"))
        chr_.store_business(conn, TAX, de, None, "2026-10-10",
                            it=chr_.parse_business(rows[20252031]))
        before = conn.execute("SELECT areas, matched_terms FROM ch_businesses").fetchone()
        self.assertIn(6, json.loads(before[0]))    # 'smartphone' with 'scuole'
        chr_.store_business(conn, TAX, de, None, "2026-10-11")   # no Italian record
        after = conn.execute("SELECT areas, matched_terms, title_it FROM ch_businesses").fetchone()
        self.assertEqual(after[:2], before)
        self.assertEqual(after[2], "Divieto degli smartphone nelle scuole")

    def test_the_italian_list_is_never_run_on_a_votes_own_text(self):
        # 'IVG' is the Italian list's tier-1 abortion term and the German
        # abbreviation of the Invalidity Insurance Act; 'aborto' is plainly
        # Italian. Neither reaches a vote through the Italian list.
        vote = {"subject": "Änderung des IVG; aborto", "meaning_yes": "", "meaning_no": ""}
        without = chr_.Taxonomies(de=TAX.de, fr=TAX.fr)
        without.it = None
        self.assertEqual(chr_.classify_own(TAX, vote), chr_.classify_own(without, vote))
        self.assertNotIn("aborto", chr_.classify_own(TAX, vote)[1])


class ItalianPassTests(unittest.TestCase):
    def _pull(self, it_answer):
        conn = store()
        de_rows = [business(20243038, "Ein Titel ohne Treffer"),
                   business(20267999, "Eine Fragestunde-Frage", btype="Fra.")]
        client = FakeClient({"Language%20eq%20'DE'": {"d": de_rows},
                             "Language%20eq%20'FR'": {"d": []},
                             "Language%20eq%20'IT'": it_answer})
        read, ours = chr_.pull_businesses(conn, client, TAX, "2026-10-10",
                                          log=lambda *a: None)
        return conn, client, read, ours

    def test_the_legislature_pass_reads_three_languages(self):
        conn, client, read, ours = self._pull({"d": italian_rows()})
        self.assertEqual(len(client.calls), 3)
        self.assertEqual((read, ours), (2, 1))
        got = dict(conn.execute("SELECT business_id, title_it FROM ch_businesses"))
        self.assertTrue(got[20243038])
        # Published in one language only: marked, so it is not asked again.
        self.assertEqual(got[20267999], "")
        self.assertEqual(chr_.fill_italian(conn, client, TAX, "2026-10-10",
                                           log=lambda *a: None), (0, 0))

    def test_a_refused_italian_pass_is_not_fatal(self):
        conn, _client, read, ours = self._pull(None)
        self.assertEqual((read, ours), (2, 0))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ch_businesses WHERE title_it IS NULL"
                                      ).fetchone()[0], 2)

    def test_fill_italian_reads_by_id_forty_to_a_request(self):
        conn = store()
        rows = by_id(italian_rows())
        ids = list(range(20100001, 20100001 + 45)) + [20244323]
        for bid in ids:
            chr_.store_business(conn, TAX, chr_.parse_business(business(bid, "Ohne Treffer")),
                                None, "2026-10-10")
        client = FakeClient({"Business?": lambda url: {"d": [
            rows[int(i)] for i in re.findall(r"ID%20eq%20(\d+)", url) if int(i) in rows]}})
        got, gaps = chr_.fill_italian(conn, client, TAX, "2026-10-10", log=lambda *a: None)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual((got, gaps), (1, 0))
        areas = conn.execute("SELECT areas FROM ch_businesses WHERE business_id=20244323"
                             ).fetchone()[0]
        self.assertEqual(json.loads(areas), [7])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ch_businesses WHERE title_it IS NULL"
                                      ).fetchone()[0], 0)


class SchemaTests(unittest.TestCase):
    def test_an_old_store_gains_the_italian_columns(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE ch_businesses (business_id INTEGER PRIMARY KEY, title_de TEXT)")
        ch_store.ensure_schema(conn)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(ch_businesses)")}
        self.assertTrue({"title_it", "areas_it", "terms_it", "tier_it"} <= cols)


if __name__ == "__main__":
    unittest.main()
