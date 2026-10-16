"""Australia's gov_docs reader (src/gov_doc_sources/au.py) on fixtures captured
live on 16 October 2026: the Department of Health's Citizen Space hub and the
Federal Register of Legislation's search API.

Nothing on these fixtures is on our ground: the live run of 16 October kept
none (61 consultations and 407 made instruments in the window; the instruments
that match at all are migration instruments, area 11, stored never counted).
The collect test says so, and checks the gate with one on-ground title run
through the same parser."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs as G  # noqa: E402
from src.gov_doc_sources import au  # noqa: E402

TODAY = "2026-10-16"
START = G.window_start(TODAY)
FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs", "au")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


class FakeClient:
    def __init__(self, extra_open=()):
        self.urls = []
        self.extra_open = list(extra_open)

    def get_json(self, url, feed, slug, *a, **kw):
        self.urls.append(url)
        if url == au.HEALTH.format("open"):
            return fixture("health_open.json") + self.extra_open
        if url == au.HEALTH.format("closed"):
            return fixture("health_closed.json")
        if url.startswith(au.FRL + "/titles/search("):
            if "$skip=0" in url:
                return fixture("frl_page0.json")
            return {"@odata.count": 760, "value": []}
        raise AssertionError("unexpected URL " + url)


class ParseTests(unittest.TestCase):
    def test_citizen_space(self):
        got = au.parse_citizen_space(fixture("health_open.json"))
        self.assertEqual(len(got), 6)
        ndis = [e for e in got if e["title"] == "Disability Safeguards Consultation"][0]
        self.assertEqual(ndis["doc_type"], "consultation")
        self.assertEqual(ndis["closing_date"], "2026-10-30")
        self.assertTrue(ndis["body"].startswith("Department of Health, Disability and Ageing ("))
        self.assertTrue(ndis["url"].startswith("https://consultations.health.gov.au/"))
        self.assertEqual(ndis["status"], "Open")
        self.assertTrue(ndis["summary"])
        closed = au.parse_citizen_space(fixture("health_closed.json"))
        self.assertTrue(all(e["status"] == "Closed" for e in closed))

    def test_frl_made_only(self):
        reply = fixture("frl_page0.json")
        got = au.parse_frl(reply, START)
        ids = [e["doc_id"] for e in got]
        self.assertTrue(ids)
        self.assertTrue(all(i.startswith("frl:F2026") for i in ids), ids)   # compilations of old titles out
        self.assertTrue(all(e["doc_type"] == "regulation" and e["published"] >= START for e in got))
        self.assertTrue(all(e["body"] for e in got))
        mig = [e for e in got if e["title"].startswith("Migration")]
        self.assertTrue(mig and all(e["body"] == "Department of Home Affairs" for e in mig))
        self.assertTrue(got[0]["url"].endswith("/asmade/text"))

    def test_frl_url(self):
        url = au.frl_url("2026-07-16", TODAY, 500)
        self.assertIn("registrationdate%282026-07-16%2C2026-10-16%29", url)
        self.assertIn("$orderby=id", url)
        self.assertIn("$skip=500", url)


class CollectTests(unittest.TestCase):
    def test_collect_keeps_nothing_on_these_fixtures(self):
        conn = db.init_db(db.connect(":memory:"))
        listed, kept, gaps = G.collect(conn, "au", FakeClient(), TODAY, log=lambda *a: None)
        self.assertEqual(gaps, 0)
        self.assertGreater(listed, 10)
        self.assertEqual(kept, 0)
        runs = {r[0]: r[1:] for r in conn.execute(
            "SELECT source, ok, listed, kept FROM gov_doc_runs WHERE cc='au'")}
        self.assertEqual(set(runs), {"health", "frl"})
        self.assertTrue(all(ok == 1 for ok, _, _ in runs.values()))

    def test_collect_keeps_an_open_consultation_on_our_ground(self):
        # One activity in the hub's own shape (the fixture's first row, retitled):
        # the gate keeps a consultation on any visible match, with its closing date.
        row = dict(fixture("health_open.json")[0], id="test-row", title="Consultation on voluntary "
                   "assisted dying and palliative care", enddate="2026/11/30", startdate="2026/10/01")
        conn = db.init_db(db.connect(":memory:"))
        G.collect(conn, "au", FakeClient(extra_open=[row]), TODAY, log=lambda *a: None)
        got = conn.execute("SELECT doc_id, doc_type, closing_date, areas FROM gov_docs").fetchall()
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][1:3], ("consultation", "2026-11-30"))
        self.assertTrue(json.loads(got[0][3]))
        self.assertEqual(len(G.deadline_rows(conn, "au", TODAY, "2027-12-31")), 1)

    def test_frl_dedupes_titles(self):
        res = au.fetch_frl(FakeClient(), TODAY, lambda *a: None)
        ids = [e["doc_id"] for e in res.entries]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertFalse(res.gaps)


if __name__ == "__main__":
    unittest.main()
