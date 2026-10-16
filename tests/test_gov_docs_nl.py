"""The Netherlands' government documents reader (src/gov_doc_sources/nl.py):
Kamerbrieven from the Tweede Kamer's OData and the Staatsblad, on fixtures
captured live on 16 October 2026."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs as G  # noqa: E402
from src.gov_doc_sources import nl  # noqa: E402

TODAY = "2026-10-16"
FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs", "nl")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


class FakeClient:
    """Serves the fixtures: the first Kamerbrieven page links a second; the
    Staatsblad day page lists 321 and 322; 312 and 294 exist, every other
    number is a 404 (so the walk spends its budget on misses, as it would on
    a gap in the sequence)."""

    def __init__(self, stb_today="staatsblad_today.html"):
        self.urls = []
        self.stb_today = stb_today

    def get_json(self, url, feed, slug, *a, **kw):
        self.urls.append(url)
        if url.startswith(nl.ODATA):
            if "skiptoken" in url:
                return json.loads(fixture("kamerbrieven_last.json"))
            reply = json.loads(fixture("kamerbrieven_p1.json"))
            reply["@odata.nextLink"] = nl.ODATA + "?$skiptoken=1"
            return reply
        raise AssertionError(url)

    def get_text(self, url, feed, slug, *a, **kw):
        self.urls.append(url)
        if url == nl.STB_TODAY:
            return fixture(self.stb_today) if self.stb_today else "<html>no publications</html>"
        name = url.rsplit("/", 1)[-1]
        if os.path.exists(os.path.join(FIX, name)):
            return fixture(name)
        raise Exception("fetch failed after 1 attempt(s) for x: {0} (HTTP Error 404: Not Found)".format(url))


class ParserTests(unittest.TestCase):
    def test_kamerbrieven(self):
        got = nl.parse_kamerbrieven(json.loads(fixture("kamerbrieven_p1.json")))
        self.assertEqual(len(got), 25)
        e = {x["doc_id"]: x for x in got}["kb:2026D51046"]
        self.assertEqual(e["title"], "Kabinetsreactie advies Gezondheidsraad Transgenderzorg voor Jongeren")
        self.assertEqual(e["doc_type"], "publication")
        self.assertTrue(e["body"].startswith("minister"))
        self.assertEqual(e["published"][:7], "2026-10")
        self.assertIn("2026D51046", e["url"])
        self.assertTrue(all(x["body"] for x in got))

    def test_kamerbrieven_url_is_a_window_filter(self):
        url = nl.kb_url(TODAY)
        self.assertIn("Datum%20ge%202026-07-16", url)
        self.assertIn("%27Brief%20regering%27", url)
        self.assertNotIn(" ", url)

    def test_staatsblad_day_page(self):
        self.assertEqual(nl.stb_numbers(fixture("staatsblad_today.html"), 2026), [321, 322])

    def test_staatsblad_item(self):
        e = nl.parse_stb(fixture("stb-2026-294.html"), 2026, 294)
        self.assertEqual(e["doc_id"], "stb:2026-294")
        self.assertEqual(e["doc_type"], "law")
        self.assertIn("conversiehandelingen", e["title"])
        self.assertEqual(e["published"][:4], "2026")
        self.assertTrue(e["body"].startswith("Ministerie van"))
        amvb = nl.parse_stb(fixture("stb-2026-321.html"), 2026, 321)
        self.assertEqual(amvb["doc_type"], "regulation")
        self.assertIn("AMvB", amvb["status"])
        self.assertIsNone(nl.parse_stb("<html></html>", 2026, 1))


class CollectTests(unittest.TestCase):
    def test_collect(self):
        conn = db.init_db(db.connect(":memory:"))
        client = FakeClient()
        listed, kept, gaps = G.collect(conn, "nl", client, TODAY, log=lambda *a: None)
        self.assertEqual(gaps, 0)
        rows = {r["doc_id"]: dict(r) for r in conn.execute("SELECT * FROM gov_docs WHERE cc='nl'")}
        # Kamerbrieven on our ground: tier 1 only (publications)
        self.assertIn("kb:2026D51046", rows)
        self.assertEqual(rows["kb:2026D51046"]["doc_type"], "publication")
        self.assertTrue(all(r["tier"] == 1 for k, r in rows.items() if k.startswith("kb:")))
        # Staatsblad: the conversion-practices act and the human trafficking act
        self.assertIn("stb:2026-294", rows)
        self.assertEqual(rows["stb:2026-294"]["doc_type"], "law")
        self.assertIn("stb:2026-312", rows)
        self.assertNotIn("stb:2026-322", rows)             # nuclear energy: not our ground
        # The walk is bounded by its page budget.
        stb_pages = [u for u in client.urls if "/stb-" in u]
        self.assertLessEqual(len(stb_pages), nl.STB_MAX_PAGES)
        self.assertTrue(any("skiptoken" in u for u in client.urls))   # paged by nextLink
        runs = {r[0]: r for r in conn.execute("SELECT source, ok, listed, kept FROM gov_doc_runs")}
        self.assertEqual(runs["kb"][1], 1)
        self.assertEqual(runs["stb"][1], 1)
        self.assertEqual(G.deadline_rows(conn, "nl", TODAY, "2027-12-31"), [])   # no consultations read

    def test_staatsblad_with_no_publication_today_probes_an_estimate(self):
        client = FakeClient(stb_today=None)
        got = nl.fetch_staatsblad(client, TODAY)
        # The estimate (day 289 x 1.12 = 323) is a 404; the probe walks down to 322.
        self.assertEqual(got.gaps, [])
        ids = [e["doc_id"] for e in got.entries]
        self.assertEqual(ids[0], "stb:2026-322")
        self.assertIn("stb:2026-294", ids)

    def test_unreadable_day_page_is_a_gap(self):
        class Broken(FakeClient):
            def get_text(self, url, *a, **kw):
                raise Exception("HTTP Error 503")
        got = nl.fetch_staatsblad(Broken(), TODAY)
        self.assertEqual(got.entries, [])
        self.assertTrue(got.gaps)


if __name__ == "__main__":
    unittest.main()
