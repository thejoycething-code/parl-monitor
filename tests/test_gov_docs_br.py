"""Brazil gov_docs reader (src/gov_doc_sources/br.py): federal legislation
from the Senate's documented Dados Abertos service, and the Brasil
Participativo mirror. Fixtures captured live on 16 October 2026 and trimmed
(tests/fixtures/gov_docs/br/): each 2026 list (LEI, LCP, MPV, EMC, DEC) cut
to the norms the tests use plus six others, and four Brasil Participativo
rows the petitions step stored."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from src import db, gov_docs as G  # noqa: E402
from src.gov_doc_sources import br  # noqa: E402
from gov_docs_latam_helpers import fixture, load_petitions  # noqa: E402

TODAY = "2026-10-16"


class FakeClient:
    def __init__(self):
        self.urls = []

    def get_json(self, url, feed, slug, **kw):
        self.urls.append(url)
        for code, _, _ in br.TYPES:
            if url == br.API.format(2026, code):
                return json.loads(fixture("br", "lista-{0}-2026.json".format(code)))
        raise AssertionError("unexpected " + url)


class ParseTests(unittest.TestCase):
    def test_list(self):
        got = {e["doc_id"]: e for e in br.parse_list(json.loads(fixture("br", "lista-MPV-2026.json")), "MPV")}
        mp = got["legis:MPV-1394-2026-09-25"]
        self.assertEqual(mp["title"], "Medida Provisória nº 1.394 de 25/09/2026")
        self.assertEqual(mp["doc_type"], "law")
        self.assertEqual(mp["published"], "2026-09-25")
        self.assertTrue(mp["summary"].startswith("Proíbe a exploração"))
        self.assertTrue(mp["url"].startswith("https://legis.senado.leg.br/norma/"))
        dec = br.parse_list(json.loads(fixture("br", "lista-DEC-2026.json")), "DEC")
        self.assertTrue(all(e["doc_type"] == "regulation" for e in dec))

    def test_years(self):
        self.assertEqual(br.years("2026-10-16"), [2026])
        self.assertEqual(br.years("2027-02-01"), [2027, 2026])


class CollectTests(unittest.TestCase):
    def test_collect(self):
        conn = db.init_db(db.connect(":memory:"))
        load_petitions(conn, "br", "country_petitions-bp.json")
        client = FakeClient()
        listed, kept, gaps = G.collect(conn, "br", client, TODAY, log=lambda *a: None)
        self.assertEqual(gaps, 0)
        self.assertEqual(len(client.urls), len(br.TYPES))
        rows = {r["doc_id"]: dict(r) for r in conn.execute("SELECT * FROM gov_docs WHERE cc='br'")}
        # on our ground (area 14, gambling): the provisional measure banning fixed-odds betting,
        # its decree and the law on the Federal Police fund's betting receipts
        self.assertEqual(set(rows), {"legis:MPV-1394-2026-09-25", "legis:DEC-13128-2026-09-28",
                                     "legis:LEI-15480-2026-07-30"})
        self.assertEqual(json.loads(rows["legis:MPV-1394-2026-09-25"]["areas"]), [14])
        self.assertEqual(rows["legis:MPV-1394-2026-09-25"]["tier"], 1)
        # the four consultations were listed (mirrored) but none is on our ground
        bp = conn.execute("SELECT listed, kept FROM gov_doc_runs WHERE cc='br' AND source='bp'").fetchone()
        self.assertEqual(tuple(bp), (4, 0))


if __name__ == "__main__":
    unittest.main()
