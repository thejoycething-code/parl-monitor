"""SK6 (Chris, 10 October 2026): Slovak bill documents, read where a title
only says which act a print amends (tools/sk_rollcalls.py, src/sk_store.py).
No network: print-9-1218.html and its two .docx documents were read live on
10 October 2026 (tlač 1218, an amendment to the Family Act 36/2005 whose
documents say it bans corporal punishment of children)."""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, sk_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "sk")
TODAY = "2026-10-10"


def _load():
    spec = importlib.util.spec_from_file_location(
        "sk_rollcalls_docs", os.path.join(ROOT, "tools", "sk_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


skr = _load()
TAX = skr.load_taxonomy()
WL = skr.empty_watchlist()
QUIET = dict(log=lambda *_: None)
TITLE_1218 = ("Návrh poslancov Národnej rady Slovenskej republiky Ondreja PROSTREDNÍKA a Lucie "
              "PLAVÁKOVEJ na vydanie zákona, ktorým sa mení zákon č. 36/2005 Z. z. o rodine a o "
              "zmene a doplnení niektorých zákonov v znení neskorších predpisov")


def blob(name):
    with open(os.path.join(FIX, name), "rb") as fh:
        return fh.read()


def store():
    return db.init_db(sqlite3.connect(":memory:"))


def add_bill(conn, tlac, title, type_id=1, delivered="2026-03-23"):
    b = {"term": 9, "tlac": tlac, "od_id": None, "type_id": type_id, "type_name": "Návrh zákona",
         "title": title, "delivered": delivered}
    skr.store_bill(conn, b, skr.classify_bill(TAX, WL, b), TODAY)


class FakeClient:
    def __init__(self, pages=None, docs=None):
        self.pages = pages or {}
        self.docs = docs or {}
        self.asked = []

    def get_text(self, url, feed, slug, **kw):
        self.asked.append(slug)
        if slug not in self.pages or self.pages[slug] is None:
            raise FetchError(url, feed, slug, 1, "timed out")
        return self.pages[slug]

    def get_bytes(self, url, feed, slug, **kw):
        self.asked.append(slug)
        if slug not in self.docs or self.docs[slug] is None:
            raise FetchError(url, feed, slug, 1, "HTTP Error 500")
        return self.docs[slug]


def client_1218(doc_answer=None):
    return FakeClient(
        pages={"print-9-1218": blob("print-9-1218.html").decode("utf-8")},
        docs={"doc-586024": blob("doc-586024.docx"),
              "doc-586025": doc_answer if doc_answer is not None else blob("doc-586025.docx")})


class ParseTests(unittest.TestCase):
    def test_the_print_page_lists_its_documents_by_category(self):
        docs = skr.parse_print_page(blob("print-9-1218.html").decode("utf-8"))
        wanted = skr.wanted_documents(docs)
        self.assertEqual([(d["id"], d["category"]) for d in wanted],
                         [(586024, "Návrh zákona"), (586025, "Dôvodová správa")])
        self.assertTrue(all(d["fmt"] == "docx" for d in wanted))
        self.assertTrue(any(d["category"] not in skr.DOC_CATEGORIES for d in docs))

    def test_word_and_unknown_formats(self):
        text = skr.document_text(blob("doc-586025.docx"), "docx")
        self.assertIn("36/2005", text)
        self.assertEqual(skr.document_text(b"\xd0\xcf\x11\xe0old .doc", "doc"), "")
        self.assertEqual(skr.document_text(b"", "pdf"), "")

    def test_which_prints_are_read(self):
        conn = store()
        add_bill(conn, "1218", TITLE_1218)
        add_bill(conn, "53", "Vládny návrh zákona o ochrane spotrebiteľa")       # names its subject
        add_bill(conn, "100", "Návrh na voľbu predsedov výborov", type_id=4)
        add_bill(conn, "733", "Vládny návrh ústavného zákona, ktorým sa mení a dopĺňa Ústava "
                              "Slovenskej republiky")
        add_bill(conn, "1500", "Vládny návrh zákona, ktorým sa mení zákon č. 595/2003 Z. z. o "
                               "dani z príjmov", delivered="2026-09-01")
        keys = [r[0] for r in skr.document_candidates(conn, 9)]
        # On our ground first (the Family Act by number, tlač 733 watched),
        # then the amending bill off our ground, though it is newer.
        self.assertEqual(keys, ["9/1218", "9/733", "9/1500"])


class ReadTests(unittest.TestCase):
    def test_the_documents_add_what_the_title_hides(self):
        conn = store()
        add_bill(conn, "1218", TITLE_1218)
        before = json.loads(conn.execute("SELECT areas FROM sk_bills").fetchone()[0])
        self.assertEqual(before, [9])                  # the Family Act's number, from the title
        read, gained, gaps = skr.read_documents(conn, client_1218(), TODAY, 9, TAX, WL, **QUIET)
        self.assertEqual((read, gained, gaps), (1, 1, 0))
        row = conn.execute("SELECT areas, doc_areas, doc_terms, docs_read, doc_ids, tier "
                           "FROM sk_bills").fetchone()
        self.assertEqual(json.loads(row[0]), [6, 9])
        self.assertIn(6, json.loads(row[1]))
        self.assertIn("telesn* tresta*", json.loads(row[2]))
        self.assertEqual(row[3], TODAY)
        self.assertEqual([d["id"] for d in json.loads(row[4])], [586024, 586025])

    def test_a_title_re_read_keeps_the_document_areas(self):
        conn = store()
        add_bill(conn, "1218", TITLE_1218)
        skr.read_documents(conn, client_1218(), TODAY, 9, TAX, WL, **QUIET)
        add_bill(conn, "1218", TITLE_1218)             # next week's pull_bills
        self.assertEqual(json.loads(conn.execute("SELECT areas FROM sk_bills").fetchone()[0]),
                         [6, 9])
        skr.reclassify(conn, TAX, **QUIET)
        self.assertEqual(json.loads(conn.execute("SELECT areas FROM sk_bills").fetchone()[0]),
                         [6, 9])

    def test_votes_inherit_and_queue_positions(self):
        conn = store()
        add_bill(conn, "1218", TITLE_1218)
        conn.execute("INSERT INTO sk_divisions (voting_id, term, bill_key, name, is_secret, areas) "
                     "VALUES (1, 9, '9/1218', 'Hlasovanie o návrhu zákona ako o celku.', 0, '[9]')")
        skr.read_documents(conn, client_1218(), TODAY, 9, TAX, WL, **QUIET)
        self.assertEqual(json.loads(conn.execute("SELECT areas FROM sk_divisions").fetchone()[0]),
                         [6, 9])
        self.assertEqual([r["voting_id"] for r in skr.pending_positions(conn, 9)], [1])

    def test_a_print_is_read_once(self):
        conn = store()
        add_bill(conn, "1218", TITLE_1218)
        skr.read_documents(conn, client_1218(), TODAY, 9, TAX, WL, **QUIET)
        again = client_1218()
        self.assertEqual(skr.read_documents(conn, again, TODAY, 9, TAX, WL, **QUIET), (0, 0, 0))
        self.assertEqual(again.asked, [])

    def test_a_refused_page_or_document_is_a_gap_and_retried(self):
        conn = store()
        add_bill(conn, "1218", TITLE_1218)
        self.assertEqual(skr.read_documents(conn, FakeClient(), TODAY, 9, TAX, WL, **QUIET),
                         (0, 0, 1))
        client = client_1218()
        client.docs["doc-586025"] = None
        self.assertEqual(skr.read_documents(conn, client, TODAY, 9, TAX, WL, **QUIET), (0, 0, 1))
        self.assertIsNone(conn.execute("SELECT docs_read FROM sk_bills").fetchone()[0])
        self.assertEqual(skr.read_documents(conn, client_1218(), TODAY, 9, TAX, WL, **QUIET),
                         (1, 1, 0))

    def test_an_unreadable_document_is_noted_not_retried(self):
        conn = store()
        add_bill(conn, "1218", TITLE_1218)
        read, gained, gaps = skr.read_documents(conn, client_1218(b"PK not a zip"), TODAY, 9, TAX,
                                                WL, **QUIET)
        self.assertEqual((read, gaps), (1, 0))
        notes = json.loads(conn.execute("SELECT doc_ids FROM sk_bills").fetchone()[0])
        self.assertTrue(any("unreadable" in n for n in notes))

    def test_the_cap(self):
        conn = store()
        add_bill(conn, "1218", TITLE_1218)
        self.assertEqual(skr.read_documents(conn, client_1218(), TODAY, 9, TAX, WL, limit=0,
                                            **QUIET), (0, 0, 0))


class SchemaTests(unittest.TestCase):
    def test_an_old_store_gains_the_columns(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE sk_bills (bill_key TEXT PRIMARY KEY, term INTEGER, tlac TEXT)")
        conn.execute("CREATE TABLE sk_divisions (voting_id INTEGER PRIMARY KEY, bill_key TEXT)")
        conn.execute("CREATE TABLE sk_votes (voting_id INTEGER, mp_id INTEGER)")
        sk_store.ensure_schema(conn)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(sk_bills)")}
        self.assertTrue({"docs_read", "doc_ids", "doc_areas", "doc_terms", "doc_excerpt"} <= cols)

    def test_the_weekly_keeps_its_hour(self):
        with open(os.path.join(ROOT, "jobs", "sk-weekly.sh"), encoding="utf-8") as fh:
            job = fh.read()
        self.assertIn("--doc-budget-seconds 600 --budget-seconds 2100", job)


if __name__ == "__main__":
    unittest.main()
