"""Slovakia's gov_docs reader (src/gov_doc_sources/sk.py) on replies captured
live on 16 October 2026 (tests/fixtures/gov_docs/sk/): Slov-Lex
eLegislatíva's filter of the materials changed in the window (trimmed to 41
of 585) and of the preliminary information notices (trimmed to 7 of 116),
and the detail of each process then open for comment."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs as G  # noqa: E402
from src.gov_doc_sources import sk  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs", "sk")
TODAY = "2026-10-16"


def js(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


class FakeClient:
    def __init__(self):
        self.asked = []

    def post_json(self, url, body, feed, slug, **kw):
        req = json.loads(body)
        self.asked.append((url, req))
        if not url.startswith(sk.API + "/legislativne-materialy/filter?page=1"):
            raise FetchError(url, "test", slug, 1, "no fixture")
        return js("filter_pi.json" if req.get("typKod") == "PredbeznaInfo" else "filter_lp.json")

    def get_json(self, url, feed, slug, **kw):
        self.asked.append((url, None))
        number = url.split("/legislativne-materialy/", 1)[-1]
        name = "detail_{0}.json".format(number.replace("/", "-"))
        if os.path.exists(os.path.join(FIX, name)):
            return js(name)
        raise FetchError(url, "test", slug, 1, "no fixture")


def rows(name):
    return {m["cisloLegislativnehoMaterialu"]: m for m in sk.parse_filter(js(name))[1]}


class ParseTest(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(sk.doc_kind("Zákon", "MPK", "LP", "2026-10-30"), "bill_draft")
        self.assertEqual(sk.doc_kind("Zákon", "VYHLASENE_V_ZBIERKE", "LP", "2026-04-10"), "law")
        self.assertEqual(sk.doc_kind("Poslanecký návrh zákona", "MPK", "LP", "x"), "bill_draft")
        self.assertEqual(sk.doc_kind("Vyhláška", "MPK", "LP", "x"), "regulation_draft")
        self.assertEqual(sk.doc_kind("Opatrenie", "VYHLASENE_V_ZBIERKE", "LP", None), "regulation")
        self.assertEqual(sk.doc_kind("Nelegislatívny všeobecný materiál", "MPK", "LP", "x"), "consultation")
        self.assertEqual(sk.doc_kind("Nelegislatívny všeobecný materiál", "ROKOVANIE_VLADA", "LP", None),
                         "publication")
        self.assertEqual(sk.doc_kind("Informatívny materiál na rokovanie vlády SR", "X", "LP", None), "report")
        self.assertEqual(sk.doc_kind("Predbežná informácia", "VYJADRENIA", "PI", "x"), "consultation")
        self.assertIsNone(sk.doc_kind("Akt EÚ", "PROCES_UKONCENY", "LPEU", None))
        self.assertIsNone(sk.doc_kind("Akt medzinárodného práva", "ROKOVANIE_NRSR", "LP", "x"))

    def test_filter_reply(self):
        total, got = sk.parse_filter(js("filter_lp.json"))
        self.assertEqual(total, len(got))
        m = rows("filter_lp.json")["LP/2026/531"]
        self.assertEqual((m["stadium"]["hodnota"], m["datumUkonceniaPkMpk"]), ("MPK", "2026-10-26"))

    def test_entry_without_detail(self):
        e = sk.material_entry(rows("filter_lp.json")["LP/2026/500"])
        self.assertEqual(e["doc_type"], "regulation_draft")
        self.assertEqual(e["body"], "Ministerstva dopravy Slovenskej republiky")
        self.assertEqual(e["closing_date"], "2026-10-19")
        self.assertEqual(e["url"],
                         "https://www.slov-lex.sk/elegislativa/legislativne-procesy/SK/LP/2026/500")
        law = sk.material_entry(rows("filter_lp.json")["LP/2026/134"])
        self.assertEqual((law["doc_type"], law["closing_date"]), ("law", None))
        mp = sk.material_entry(rows("filter_lp.json")["LP/2026/255"])
        self.assertEqual(mp["body"], sk.MPS)

    def test_entry_with_detail(self):
        e = sk.material_entry(rows("filter_lp.json")["LP/2026/531"], js("detail_LP-2026-531.json"))
        self.assertEqual(e["body"], "Ministerstvo práce, sociálnych vecí a rodiny Slovenskej republiky")
        self.assertTrue(e["summary"].startswith("Oblasť: "))
        pi = sk.material_entry(rows("filter_pi.json")["PI/2026/245"], js("detail_PI-2026-245.json"))
        self.assertEqual((pi["doc_type"], pi["closing_date"], pi["body"]),
                         ("consultation", "2026-10-29",
                          "Ministerstvo životného prostredia Slovenskej republiky"))


class CollectTest(unittest.TestCase):
    def test_collect(self):
        client = FakeClient()
        conn = db.init_db(db.connect(":memory:"))
        listed, kept, gaps = G.collect(conn, "sk", client, TODAY, log=lambda *a: None)
        self.assertEqual(gaps, 0)
        filters = [req for url, req in client.asked if req is not None]
        self.assertEqual(filters[0], {"datumZmenyOd": "2026-07-16"})
        details = [url for url, req in client.asked if req is None]
        self.assertTrue(all("/LP/" in u or "/PI/" in u for u in details))
        self.assertNotIn(sk.DETAIL.format("LP/2026/255"), details)   # closed: no detail read
        got = {r["doc_id"]: dict(r) for r in conn.execute("SELECT * FROM gov_docs WHERE cc='sk'")}
        for key in ("lp:LP/2026/531", "lp:LP/2026/511", "lp:LP/2026/357", "lp:PI/2026/226"):
            self.assertIn(key, got)
        self.assertEqual(got["lp:LP/2026/511"]["doc_type"], "regulation_draft")
        self.assertEqual(got["lp:LP/2026/357"]["doc_type"], "bill_draft")
        far = "2027-10-16"
        dl = [r["doc_id"] for r in G.deadline_rows(conn, "sk", TODAY, far)]
        self.assertEqual(dl, ["lp:LP/2026/531", "lp:LP/2026/511"])
        self.assertFalse(any(k.startswith("lp:LPEU") for k in got))


if __name__ == "__main__":
    unittest.main()
