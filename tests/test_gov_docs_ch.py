"""Switzerland's government consultations and publications reader
(src/gov_doc_sources/ch.py) on fixtures captured live on 16 October 2026
(tests/fixtures/gov_docs/ch/). The Vernehmlassungen mirror reads
country_petitions rows as the pulled store held them
(country_petitions_vl.json, read 12 October 2026) plus one made-up
consultation on our ground, labelled as such."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs as G, petitions  # noqa: E402
from src.gov_doc_sources import ch  # noqa: E402
from tests.test_gov_docs_de import FakeClient  # noqa: E402

TODAY = "2026-10-16"
FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs", "ch")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as h:
        return h.read()


MADE_UP = {"cc": "ch", "item_id": "vl:proj/2026/999/cons_1", "source": "vl", "kind": "consultation",
           "title": "Änderung der Verordnung über die Fortpflanzungsmedizin (TEST ROW, not real)",
           "status": "Vernehmlassung läuft", "opened": "2026-09-20", "closes": "2026-12-20",
           "body": "Bundesverwaltung",
           "url": "https://www.fedlex.admin.ch/eli/dl/proj/2026/999/cons_1/de", "last_seen": "2026-10-12"}


def load_petitions(conn, extra=()):
    petitions.ensure_schema(conn)
    rows = json.loads(fixture("country_petitions_vl.json")) + list(extra)
    for r in rows:
        conn.execute("INSERT OR REPLACE INTO country_petitions ({0}) VALUES ({1})".format(
            ",".join(r), ",".join("?" * len(r))), list(r.values()))
    conn.commit()


class ParserTests(unittest.TestCase):
    def test_nsb(self):
        got = ch.parse_nsb(fixture("nsb.xml"))
        self.assertEqual(len(got), 21)
        e = next(x for x in got if x["doc_id"] == "nsb:bpqJWbpGwV43")
        self.assertEqual(e["body"], "Der Schweizerische Bundesrat")
        self.assertEqual(e["published"], "2026-09-02")
        self.assertEqual(e["url"], "https://www.admin.ch/de/newnsb/bpqJWbpGwV43")
        self.assertTrue(any(x["doc_type"] == "statistics" for x in got))

    def test_as_types(self):
        got = ch.parse_as(json.loads(fixture("fedlex_as.json")))
        kinds = {e["status"]: e["doc_type"] for e in got}
        self.assertEqual(kinds.get("Verordnung des Bundesrates"), "regulation")
        self.assertTrue(all(e["doc_id"].startswith("as:oc/") for e in got))
        self.assertTrue(all(e["url"].endswith("/de") for e in got))
        raw = len(json.loads(fixture("fedlex_as.json"))["results"]["bindings"])
        self.assertLess(len(got), raw)          # corrections and treaty texts left out

    def test_draft_kind(self):
        self.assertEqual(ch.draft_kind("Änderung der Verordnung über die Nationalbibliothek"),
                         "regulation_draft")
        self.assertEqual(ch.draft_kind("Änderung des Energiegesetzes"), "bill_draft")


class CollectTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))
        load_petitions(self.conn, [MADE_UP])
        self.client = FakeClient(FIX)
        self.listed, self.kept, self.gaps = G.collect(self.conn, "ch", self.client, TODAY,
                                                      log=lambda *a: None)

    def row(self, doc_id):
        r = self.conn.execute("SELECT * FROM gov_docs WHERE cc='ch' AND doc_id=?", (doc_id,)).fetchone()
        return dict(r) if r else None

    def test_counts(self):
        self.assertEqual(self.gaps, 0)
        self.assertEqual(self.kept, 3)
        listed = {r[0]: r[1] for r in self.conn.execute(
            "SELECT source, listed FROM gov_doc_runs WHERE cc='ch'")}
        self.assertEqual(listed["vl"], 29)

    def test_mirrored_consultation_with_its_deadline(self):
        r = self.row("vl:proj/2026/999/cons_1")
        self.assertEqual(r["doc_type"], "regulation_draft")
        self.assertEqual(r["closing_date"], "2026-12-20")
        self.assertIn(10, json.loads(r["areas"]))
        got = G.deadline_rows(self.conn, "ch", TODAY, "2027-12-31")
        self.assertEqual([d["doc_id"] for d in got], ["vl:proj/2026/999/cons_1"])

    def test_press_release_on_our_ground(self):
        r = self.row("nsb:bpqJWbpGwV43")
        self.assertEqual(r["doc_type"], "press_release")
        self.assertEqual(r["tier"], 1)
        self.assertEqual(sorted(json.loads(r["areas"])), [4, 5])


if __name__ == "__main__":
    unittest.main()
