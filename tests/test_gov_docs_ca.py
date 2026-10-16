"""Canada's gov_docs reader (src/gov_doc_sources/ca.py) on fixtures captured live
on 16 October 2026: the Consulting with Canadians register (open.canada.ca CSV),
the Canada Gazette mirror (ca_gazette_items rows) and the News Centre feed."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, gov_docs as G  # noqa: E402
from src.gov_doc_sources import ca  # noqa: E402

TODAY = "2026-10-16"
FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs", "ca")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


class FakeClient:
    def __init__(self):
        self.urls = []

    def get_text(self, url, feed, slug, *a, **kw):
        self.urls.append(url)
        if url == ca.CWC_CSV:
            return fixture("current_consultations_open.csv")
        if url.startswith("https://api.io.canada.ca/io-server/gc/news/en/v2"):
            return fixture("news.xml")
        raise AssertionError("unexpected URL " + url)


def load_gazette(conn):
    ca_store.ensure_schema(conn)
    data = json.loads(fixture("ca_gazette_rows.json"))
    for table, rows in (("ca_gazette_items", data["items"]), ("ca_gazette_issues", data["issues"])):
        for r in rows:
            cols = list(r)
            conn.execute("INSERT INTO {0} ({1}) VALUES ({2})".format(
                table, ",".join(cols), ",".join("?" * len(cols))), [r[c] for c in cols])
    conn.commit()


class ParseTests(unittest.TestCase):
    def test_cwc(self):
        got = ca.parse_cwc(fixture("current_consultations_open.csv"))
        self.assertEqual(len(got), 20)
        sdg = [e for e in got if "Sustainable Development Goals" in e["title"]][0]
        self.assertEqual(sdg["doc_type"], "consultation")
        self.assertEqual(sdg["closing_date"], "2026-12-18")
        self.assertEqual(sdg["body"], "Employment and Social Development Canada")
        self.assertEqual(sdg["status"], "Open")
        self.assertTrue(sdg["doc_id"].startswith("cwc:esdc-edsc/"))
        self.assertTrue(sdg["url"].startswith("https://www.canada.ca/"), sdg["url"])
        self.assertEqual({e["status"] for e in got}, {"Open", "Planned", "Closed"})
        for e in got:
            self.assertNotIn("safelinks", e["url"])
            self.assertNotIn("adobecqms", e["url"])

    def test_news(self):
        got = ca.parse_news(fixture("news.xml"))
        self.assertEqual(len(got), 20)
        self.assertTrue(all(e["doc_type"] == "press_release" and e["published"] for e in got))
        self.assertTrue(all(e["url"].startswith("https://www.canada.ca/en/") for e in got))
        self.assertTrue(all(e["body"] for e in got))

    def test_demojibake(self):
        self.assertEqual(ca.demojibake("Companiesâ€™ Creditors"), "Companies’ Creditors")
        self.assertEqual(ca.demojibake("Montréal"), "Montréal")

    def test_gazette_mirror_types(self):
        conn = db.init_db(db.connect(":memory:"))
        load_gazette(conn)
        res = ca.mirror_gazette(conn, "ca", TODAY)
        self.assertFalse(res.gaps)
        by = {e["title"]: e for e in res.entries}
        irpr = by["Regulations Amending the Immigration and Refugee Protection Regulations"]
        self.assertEqual(irpr["doc_type"], "regulation_draft")
        self.assertEqual(irpr["closing_date"], "2026-09-14")
        self.assertEqual(irpr["body"], "Canada Border Services Agency")
        plumbing = [e for t, e in by.items() if t.startswith("Guidance on Residential Premise Plumbing")][0]
        self.assertEqual(plumbing["doc_type"], "consultation")       # "within 60 days after publication"
        self.assertEqual(plumbing["closing_date"], "2026-11-25")
        self.assertTrue(any("Companies’" in t for t in by))      # mojibake repaired
        iran = [e for t, e in by.items() if t.startswith("Special Economic Measures (Iran)")]
        self.assertTrue(iran and all(e["doc_type"] == "regulation" for e in iran))
        # commission notices (charity revocations) are out of scope
        self.assertFalse(any(t.startswith("Revocation of registration of charities") for t in by))


class CollectTests(unittest.TestCase):
    def test_collect(self):
        conn = db.init_db(db.connect(":memory:"))
        load_gazette(conn)
        client = FakeClient()
        listed, kept, gaps = G.collect(conn, "ca", client, TODAY, log=lambda *a: None)
        self.assertEqual(gaps, 0)
        rows = {r["doc_id"]: dict(r) for r in conn.execute("SELECT * FROM gov_docs WHERE cc='ca'")}
        sdg = [r for k, r in rows.items() if k.startswith("cwc:esdc-edsc/")]
        self.assertEqual(len(sdg), 1)
        self.assertEqual(sdg[0]["closing_date"], "2026-12-18")
        self.assertIn(7, json.loads(sdg[0]["areas"]))
        irpr = [r for r in rows.values() if r["title"].startswith("Regulations Amending the Immigration")]
        self.assertEqual(len(irpr), 1)
        self.assertEqual(irpr[0]["doc_type"], "regulation_draft")
        self.assertEqual(irpr[0]["closing_date"], "2026-09-14")
        ebola = [r for r in rows.values() if "Ebola" in r["title"]]
        self.assertTrue(ebola and all(r["doc_type"] == "regulation" and r["tier"] == 1 for r in ebola))
        # no news release on these fixtures reaches tier 1: the precision gate keeps none
        self.assertFalse([k for k in rows if k.startswith("news:")])
        deadlines = G.deadline_rows(conn, "ca", TODAY, "2027-12-31")
        self.assertEqual([d["doc_id"] for d in deadlines], [sdg[0]["doc_id"]])
        runs = {r[0]: r[1:] for r in conn.execute(
            "SELECT source, ok, listed, kept FROM gov_doc_runs WHERE cc='ca'")}
        self.assertEqual(set(runs), {"cwc", "gazette", "news"})
        self.assertTrue(all(ok == 1 for ok, _, _ in runs.values()))
        self.assertEqual(kept, len(rows))

    def test_gazette_missing_table_is_a_gap(self):
        conn = db.init_db(db.connect(":memory:"))
        conn.execute("DROP TABLE IF EXISTS ca_gazette_items")
        res = ca.mirror_gazette(conn, "ca", TODAY)
        self.assertTrue(res.gaps)


if __name__ == "__main__":
    unittest.main()
