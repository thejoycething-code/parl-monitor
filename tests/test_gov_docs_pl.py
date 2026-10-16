"""Poland's government documents reader (src/gov_doc_sources/pl.py): the
Council of Ministers' list of legislative work (gov.pl CSV), the Dziennik
Ustaw and Monitor Polski (ELI API), and the Sejm's consultations mirrored
from country_petitions; fixtures captured live on 16 October 2026."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs as G, petitions  # noqa: E402
from src.gov_doc_sources import pl  # noqa: E402

TODAY = "2026-10-16"
FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs", "pl")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


class FakeClient:
    def __init__(self):
        self.calls = []

    def get_text(self, url, feed, slug, *a, **kw):
        self.calls.append((url, kw.get("archive", True)))
        if url == pl.WPLIP_PAGE:
            return fixture("wplip_page.html")
        if url.startswith(pl.GOV + "/register-file/"):
            return fixture("wplip.csv")
        raise AssertionError(url)

    def get_json(self, url, feed, slug, *a, **kw):
        self.calls.append((url, kw.get("archive", True)))
        if "publisher=DU" in url:
            return json.loads(fixture("eli_du.json"))
        if "publisher=MP" in url:
            return json.loads(fixture("eli_mp.json"))
        raise AssertionError(url)


def load_petitions(conn):
    petitions.ensure_schema(conn)
    for r in json.loads(fixture("country_petitions_rows.json")):
        cols = ",".join(r)
        conn.execute("INSERT INTO country_petitions ({0}) VALUES ({1})".format(
            cols, ",".join("?" * len(r))), list(r.values()))
    conn.commit()


class ParserTests(unittest.TestCase):
    def test_register_csv_link(self):
        self.assertEqual(pl.register_csv_url(fixture("wplip_page.html")),
                         "https://www.gov.pl/register-file/Rejestr_20874195.csv")
        self.assertIsNone(pl.register_csv_url("<html></html>"))

    def test_wplip(self):
        got = {e["doc_id"]: e for e in pl.parse_wplip(fixture("wplip.csv"))}
        self.assertEqual(len(got), 31)
        e = got["wplip:UD452"]
        self.assertEqual(e["doc_type"], "bill_draft")
        self.assertTrue(e["title"].startswith("Projekt ustawy o zmianie ustawy - Prawo oświatowe"))
        self.assertTrue(e["body"].startswith("ME ("))           # Education or Energy: person named
        self.assertTrue(e["published"].startswith("2026-"))
        self.assertIsNone(e["closing_date"])
        self.assertIn("planowane przyjęcie", e["status"])
        self.assertEqual(got["wplip:RD324"]["doc_type"], "regulation_draft")
        self.assertIn("publication", {x["doc_type"] for x in got.values()})

    def test_du(self):
        got = pl.parse_du(json.loads(fixture("eli_du.json")))
        types = {e["doc_type"] for e in got}
        self.assertEqual(types, {"law", "regulation"})            # Obwieszczenie etc. dropped
        e = got[0]
        self.assertTrue(e["doc_id"].startswith("du:DU/2026/"))
        self.assertTrue(e["url"].startswith("https://dziennikustaw.gov.pl/DU/2026/"))
        self.assertTrue(e["body"])

    def test_mp_keeps_only_government(self):
        got = pl.parse_mp(json.loads(fixture("eli_mp.json")))
        self.assertEqual(len(got), 4)
        self.assertTrue(all(e["body"] in ("RADA MINISTRÓW", "PREZ. RADY MINISTRÓW") for e in got))


class CollectTests(unittest.TestCase):
    def test_collect(self):
        conn = db.init_db(db.connect(":memory:"))
        load_petitions(conn)
        client = FakeClient()
        listed, kept, gaps = G.collect(conn, "pl", client, TODAY, log=lambda *a: None)
        self.assertEqual(gaps, 0)
        rows = {r["doc_id"]: dict(r) for r in conn.execute("SELECT * FROM gov_docs WHERE cc='pl'")}
        # the register: draft laws on our ground (any match: a deadline type)
        for k in ("wplip:UD452", "wplip:UD487", "wplip:RD324"):
            self.assertIn(k, rows)
        self.assertEqual(rows["wplip:UD452"]["doc_type"], "bill_draft")
        # the Sejm's consultations, with their end dates
        sejm = {k: r for k, r in rows.items() if k.startswith("sejm:")}
        self.assertEqual(len(sejm), 4)
        self.assertEqual(rows["sejm:RPW/33663/2026"]["closing_date"], "2026-11-07")
        self.assertTrue(all(r["doc_type"] == "bill_draft" for r in sejm.values()))
        open_rows = G.deadline_rows(conn, "pl", TODAY, "2027-12-31")
        self.assertEqual([r["doc_id"] for r in open_rows],
                         ["sejm:RPW/31346/2026", "sejm:RPW/31837/2026", "sejm:RPW/33663/2026"])
        # gazette rows need tier 1: the homeschooling regulation (tier 2) is not kept
        self.assertFalse([k for k in rows if k.startswith("du:")])
        # the 10 MB CSV is not archived
        self.assertIn((pl.GOV + "/register-file/Rejestr_20874195.csv", False), client.calls)
        runs = {r[0]: r[1] for r in conn.execute("SELECT source, ok FROM gov_doc_runs")}
        self.assertEqual(runs, {"wplip": 1, "du": 1, "mp": 1, "sejm": 1})

    def test_empty_mirror_is_a_gap(self):
        conn = db.init_db(db.connect(":memory:"))
        got = pl.mirror_sejm(conn, "pl", TODAY)
        self.assertEqual(got.entries, [])
        self.assertTrue(got.gaps)

    def test_page_without_csv_link_is_a_gap(self):
        class NoLink(FakeClient):
            def get_text(self, url, *a, **kw):
                return "<html>changed</html>"
        got = pl.fetch_wplip(NoLink(), TODAY)
        self.assertTrue(got.gaps)


if __name__ == "__main__":
    unittest.main()
