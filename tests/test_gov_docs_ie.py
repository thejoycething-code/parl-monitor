"""Ireland's gov_docs reader (src/gov_doc_sources/ie.py) on fixtures captured
live on 16 October 2026 from the electronic Irish Statute Book: the 2026 SI
list (trimmed to its first rows and the tail from S.I. 330) and two SI pages.

The live run kept nothing: the three SIs whose titles match (S.I. 350 to 352,
data protection regulations for the Commission of Investigation into
historical child sexual abuse in schools) match at tier 2, and a made
regulation needs tier 1. The collect test asserts exactly that."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs as G  # noqa: E402
from src.gov_doc_sources import ie  # noqa: E402

TODAY = "2026-10-16"
FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs", "ie")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


class FakeClient:
    def __init__(self):
        self.urls = []

    def get_text(self, url, feed, slug, *a, **kw):
        self.urls.append(url)
        if url == ie.YEAR_LIST.format(2026):
            return fixture("si-2026-list.html")
        if url.startswith(ie.ISB + "/eli/2026/si/"):
            # the three titles on our ground are S.I. 350-352, one ministerial
            # regulation each; the captured 350 stands in for all three
            return fixture("si-2026-350.html")
        raise AssertionError("unexpected URL " + url)


class ParseTests(unittest.TestCase):
    def test_year_list(self):
        rows = ie.parse_year_list(fixture("si-2026-list.html"))
        self.assertEqual(rows[0][0], 1)
        nums = [r[0] for r in rows]
        self.assertIn(515, nums)
        linked = {r[0]: r[2] for r in rows}
        self.assertTrue(linked[500])
        self.assertFalse(linked[506])          # PDF only, no HTML page yet
        self.assertEqual(dict((r[0], r[1]) for r in rows)[500][:30], "Planning and Development (Shor")

    def test_si_page_with_note(self):
        got = ie.parse_si_page(fixture("si-2026-500.html"))
        self.assertEqual(got["published"], "2026-10-02")          # notified in Iris Oifigiuil
        self.assertEqual(got["body"], "Minister for Housing, Local Government and Heritage")
        self.assertTrue(got["summary"].startswith("These Regulations amend Articles 22 and 33"))

    def test_si_page_without_note(self):
        got = ie.parse_si_page(fixture("si-2026-350.html"))
        self.assertEqual(got["published"], "2026-07-24")
        self.assertEqual(got["body"], "Minister for Education and Youth")
        self.assertTrue(got["summary"].startswith("in exercise of the powers"))


class CollectTests(unittest.TestCase):
    def test_collect(self):
        conn = db.init_db(db.connect(":memory:"))
        client = FakeClient()
        listed, kept, gaps = G.collect(conn, "ie", client, TODAY, log=lambda *a: None)
        self.assertEqual(gaps, 0)
        pages = [u for u in client.urls if u.endswith("/made/en/html")]
        self.assertEqual(sorted(pages), [ie.SI_PAGE.format(2026, n) for n in (350, 351, 352)])
        self.assertEqual(listed, 3)
        self.assertEqual(kept, 0)          # tier 2 ('child sexual abuse'): a regulation needs tier 1
        run = conn.execute("SELECT ok, listed, kept, note FROM gov_doc_runs WHERE cc='ie'").fetchone()
        self.assertEqual(tuple(run[:3]), (1, 3, 0))
        self.assertIn("3 titles on our ground", run[3])

    def test_classified_entries(self):
        res = ie.fetch_isb(FakeClient(), TODAY, lambda *a: None)
        taxes, wl = G.taxonomies("ie"), G.watchlist("ie")
        got = [G.classify(e, taxes, wl) for e in res.entries]
        self.assertEqual(len(got), 3)
        for e in got:
            self.assertEqual(e["doc_type"], "regulation")
            self.assertEqual(e["published"], "2026-07-24")
            self.assertIn(6, e["areas"])
            self.assertEqual(e["tier"], 2)
            self.assertFalse(G.on_ground(e))


if __name__ == "__main__":
    unittest.main()
