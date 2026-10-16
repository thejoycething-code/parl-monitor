"""Croatia's gov_docs reader (src/gov_doc_sources/hr.py) on replies captured
live on 16 October 2026 (tests/fixtures/gov_docs/hr/): the data.gov.hr
package of the e-Savjetovanja register and its JSON (trimmed to a spread of
rows), the Narodne novine index CSV for 2026 (trimmed to issues 76, 77, 100,
103, 116 and 117) and the gazette API's JSON-LD for each issue's first act."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs as G  # noqa: E402
from src.gov_doc_sources import hr  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs", "hr")
TODAY = "2026-10-16"


def text(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def js(name):
    return json.loads(text(name))


class FakeClient:
    def __init__(self):
        self.asked = []

    def get_json(self, url, feed, slug, **kw):
        self.asked.append(url)
        if "package_show" in url:
            return js("esav_package.json")
        if url.endswith("/download/data.json"):
            return js("esav_data.json")
        raise FetchError(url, "test", slug, 1, "no fixture")

    def get_text(self, url, feed, slug, **kw):
        self.asked.append(url)
        if "get_index_file.aspx?year=2026" in url:
            return text("nn_index_2026.csv")
        raise FetchError(url, "test", slug, 1, "no fixture")

    def post_json(self, url, body, feed, slug, **kw):
        req = json.loads(body)
        self.asked.append("{0} {1}".format(url, req["number"]))
        name = "nn_act_{0}.json".format(req["number"])
        if url == hr.NN_API_ACT and os.path.exists(os.path.join(FIX, name)):
            return js(name)
        raise FetchError(url, "test", slug, 1, "no fixture")


class ESavjetovanjaTest(unittest.TestCase):
    def test_package_gives_json_resource(self):
        url, modified = hr.parse_ckan_package(js("esav_package.json"))
        self.assertTrue(url.endswith("/download/data.json"))
        self.assertEqual(modified, "2026-10-10")

    def test_kinds(self):
        self.assertEqual(hr.esav_kind("Zakon", "Nacrt prijedloga zakona o osiguranju"), "bill_draft")
        self.assertEqual(hr.esav_kind("Pravilnik", "Prijedlog pravilnika"), "regulation_draft")
        self.assertEqual(hr.esav_kind("Ostalo", "Savjetovanje o Nacrtu prijedloga zakona o PDV-u"),
                         "bill_draft")
        self.assertEqual(hr.esav_kind("Ostalo", "Standard rada psihologa"), "consultation")
        self.assertIsNone(hr.esav_kind(
            "Procjena ucinaka propisa", "Obrazac iskaza o procjeni učinaka propisa za Nacrt"))
        self.assertIsNone(hr.esav_kind("Zakon", "Obrazac iskaza o procjeni učinaka propisa"))
        self.assertIsNone(hr.esav_kind("Obrazac zakonodavnih aktivnosti", "Obrazac zakonodavnih aktivnosti"))

    def test_parse(self):
        got = {e["doc_id"]: e for e in hr.parse_esavjetovanja(js("esav_data.json"))}
        e = got["esav:10109"]
        self.assertEqual(e["doc_type"], "regulation_draft")
        self.assertEqual(e["closing_date"], "2026-08-13")
        self.assertEqual(e["body"], "Ministarstvo rada, mirovinskoga sustava, obitelji i socijalne politike")
        bill = got["esav:10289"]
        self.assertEqual((bill["doc_type"], bill["published"], bill["closing_date"]),
                         ("bill_draft", "2026-09-09", "2026-10-24"))
        self.assertNotIn("esav:10290", got)          # the impact-assessment form
        self.assertNotIn("esav:10293", got)          # the legislative-plan form
        self.assertEqual(got["esav:10282"]["doc_type"], "consultation")


class NarodneNovineTest(unittest.TestCase):
    def test_index(self):
        rows = hr.parse_nn_index(text("nn_index_2026.csv"))
        first = rows[0]
        self.assertEqual((first["issue"], first["year"], first["act"]), (76, 2026, "898"))
        r = [x for x in rows if x["act"] == "1379"][0]
        self.assertEqual((r["vrsta"], r["body"]), ("uredba", "Vlada Republike Hrvatske"))
        self.assertEqual(r["url"], "https://narodne-novine.nn.hr/eli/sluzbeni/2026/116/1379")

    def test_scope(self):
        self.assertEqual(hr.nn_kind("zakon", "Hrvatski sabor"), "law")
        self.assertEqual(hr.nn_kind("pravilnik", "Ministarstvo unutarnjih poslova"), "regulation")
        self.assertEqual(hr.nn_kind("odluka", "Vlada Republike Hrvatske"), "regulation")
        self.assertIsNone(hr.nn_kind("odluka", "Ustavni sud Republike Hrvatske"))
        self.assertIsNone(hr.nn_kind("odluka", "Hrvatska narodna banka"))
        self.assertIsNone(hr.nn_kind("rješenje", "Vlada Republike Hrvatske"))
        self.assertIsNone(hr.nn_kind("presuda", "VISOKI UPRAVNI SUD REPUBLIKE HRVATSKE"))
        self.assertIsNone(hr.nn_kind("uputa", "DRŽAVNO IZBORNO POVJERENSTVO REPUBLIKE HRVATSKE"))

    def test_act_date(self):
        self.assertEqual(hr.parse_nn_act_date(js("nn_act_117.json")), "2026-10-14")
        self.assertEqual(hr.parse_nn_act_date(js("nn_act_77.json")), "2026-07-15")
        self.assertIsNone(hr.parse_nn_act_date({"x": []}))

    def test_fetch_stops_at_window(self):
        client = FakeClient()
        got = hr.fetch_narodne_novine(client, TODAY, log=lambda *a: None)
        self.assertEqual(got.gaps, [])
        asked = [a for a in client.asked if a.startswith(hr.NN_API_ACT)]
        self.assertEqual(asked[-1], hr.NN_API_ACT + " 77")     # 76 never asked
        ids = {e["doc_id"]: e for e in got.entries}
        e = ids["nn:2026/116/1379"]
        self.assertEqual((e["doc_type"], e["published"], e["body"]),
                         ("regulation", "2026-10-12", "Vlada Republike Hrvatske"))
        self.assertEqual(ids["nn:2026/77/900"]["published"], "2026-07-15")
        self.assertEqual(ids["nn:2026/77/900"]["doc_type"], "law")
        self.assertNotIn("nn:2026/117/1403", ids)               # a court judgment
        self.assertFalse(any(k.startswith("nn:2026/76/") for k in ids))


class CollectTest(unittest.TestCase):
    def test_collect(self):
        conn = db.init_db(db.connect(":memory:"))
        listed, kept, gaps = G.collect(conn, "hr", FakeClient(), TODAY, log=lambda *a: None)
        self.assertEqual(gaps, 0)
        rows = {r["doc_id"]: dict(r) for r in conn.execute("SELECT * FROM gov_docs WHERE cc='hr'")}
        # the family-ministry procurement rule: 'obitelj*' (area 9), a deadline type
        self.assertIn("esav:10109", rows)
        self.assertEqual(rows["esav:10109"]["closing_date"], "2026-08-13")
        self.assertEqual(json.loads(rows["esav:10109"]["areas"]), [9])
        # a made decree on family houses matches tier 2 only: not a deadline
        # type, so the precision gate leaves it out
        self.assertFalse(any(k.startswith("nn:") for k in rows))
        runs = {r["source"]: dict(r) for r in conn.execute("SELECT * FROM gov_doc_runs")}
        self.assertEqual(runs["esav"]["ok"], 1)
        self.assertIn("snapshot of 2026-10-10", runs["esav"]["note"])
        self.assertGreater(runs["nn"]["listed"], 10)

    def test_stale_snapshot_is_a_gap(self):
        got = hr.fetch_esavjetovanja(FakeClient(), "2026-12-15", log=lambda *a: None)
        self.assertTrue(got.gaps and "last refreshed 2026-10-10" in got.gaps[0])


if __name__ == "__main__":
    unittest.main()
