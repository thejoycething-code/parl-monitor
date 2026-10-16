"""Australia's state forward agendas (src/regional_agendas/au.py): each
parser over a trimmed live capture of 16 October 2026, end-to-end collects
with FakeClient (the PDF and Word readers patched to the captures' text),
and a dead host. No network."""
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import regional_agenda as ra  # noqa: E402
from src.regional_agendas import au  # noqa: E402
from tests.test_regional_agenda import FakeClient, load_fixture, store  # noqa: E402


def fx(name):
    return load_fixture("au", name)


def quiet(*a, **k):
    pass


class VictoriaTest(unittest.TestCase):
    def test_calendar(self):
        sittings, hearings = au.parse_vic_calendar(json.loads(fx("vic_cal_2026.json")))
        self.assertIn(("2026-09-24", "Legislative Assembly"), sittings)
        self.assertIn(("2026-09-24", "Legislative Council"), sittings)
        self.assertIn(("2026-05-05", "Legislative Assembly"), sittings)
        self.assertNotIn(("2026-05-05", "Legislative Council"), sittings)     # Assembly only
        self.assertIn(("2026-08-14", "Legislative Council"), sittings)
        self.assertEqual(len(hearings), 48)
        self.assertEqual(hearings[-1], ("2026-08-03", "Inquiry into the Early Childhood Education and "
                                                      "Care Sector in Victoria"))

    def test_reader(self):
        pages = {au.VIC_CAL.format("2026"): json.loads(fx("vic_cal_2026.json"))}
        conn = store()
        s = ra.collect(conn, "au", FakeClient(pages), "2026-09-01", days=28, regions=["vic"], log=quiet)
        self.assertEqual(s["read"], ["vic"])
        rows = [dict(r) for r in conn.execute("SELECT * FROM regional_agenda")]
        tba = [r for r in rows if r["item_type"] == ra.TBA]
        self.assertEqual(len(tba), 12)              # 8, 9, 10, 22, 23, 24 Sept, both Houses
        # Today, nothing sits before the election: an honest empty read.
        pages[au.VIC_CAL.format("2026")] = json.loads(fx("vic_cal_2026.json"))
        conn = store()
        s = ra.collect(conn, "au", FakeClient(pages), "2026-10-16", days=56, regions=["vic"], log=quiet)
        self.assertEqual(s["read"], ["vic"])
        self.assertEqual(s["rows"], 0)

    def test_next_year_not_out(self):
        pages = {au.VIC_CAL.format("2026"): json.loads(fx("vic_cal_2026.json")),
                 au.VIC_CAL.format("2027"): json.loads(fx("vic_cal_2027_none.json"))}
        conn = store()
        s = ra.collect(conn, "au", FakeClient(pages), "2026-12-01", days=56, regions=["vic"], log=quiet)
        self.assertEqual(s["read"], ["vic"])


class SouthAustraliaTest(unittest.TestCase):
    def test_house_of_assembly(self):
        items = au.parse_sa_notice_paper(fx("sa_ha_notice_paper.txt.gz"), "House of Assembly")
        dates = {i["dated"] for i in items}
        self.assertIn("2026-10-27", dates)
        self.assertIn("2026-11-25", dates)
        first = items[0]
        self.assertEqual(first["dated"], "2026-10-27")
        self.assertTrue(first["business"].startswith("Report of the Auditor-General 2025-26 (Treasurer)"))
        bill = [i for i in items if i["reference"] == "Bill No 22"][0]
        self.assertEqual(bill["business"], "Statutes Amendment (Attorney -General’s Portfolio) Bill (No 22) "
                                           "(Minister for Infrastructure and Transport) – in Committee – clause 5")
        self.assertTrue(bill["detail"].startswith("Orders of the Day:"))
        # Questions on notice and the bill index are not business.
        self.assertFalse(any("QUESTION" in (i["detail"] or "") for i in items))
        self.assertEqual(len([i for i in items if i["dated"] == "2026-10-27"]), 13)

    def test_legislative_council(self):
        items = au.parse_sa_notice_paper(fx("sa_lc_notice_paper.txt.gz"), "Legislative Council")
        self.assertEqual([i["reference"] for i in items[:5]],
                         ["Bill No 38", "Bill No 29", "Bill No 31", "Bill No 37", "Bill No 39"])
        self.assertEqual(items[5]["dated"], "2026-10-28")
        self.assertEqual(items[5]["reference"], "Notice of Motion 1")

    def test_reader(self):
        lib = json.loads(fx("sa_lib_6.json"))
        lc_lib = {"files": [{"id": "lc-id", "fileName": "LCNP.pdf"}]}
        link = au.SA_LINK
        pages = {au.SA_LIB: None,
                 link.format("6", lib["files"][1]["id"]): {"downloadLink": "https://blob/ha"},
                 link.format("1", "lc-id"): {"downloadLink": "https://blob/lc"},
                 "https://blob/ha": b"%PDF-ha", "https://blob/lc": b"%PDF-lc"}
        texts = {b"%PDF-ha": fx("sa_ha_notice_paper.txt.gz"), b"%PDF-lc": fx("sa_lc_notice_paper.txt.gz")}

        class Client(FakeClient):
            def post_json(self, url, body, feed, slug, **kw):
                return lib if json.loads(body)["controlId"] == "6" else lc_lib

        with mock.patch("src.prov_fetch.pdf_text", side_effect=lambda raw: texts[raw]):
            conn = store()
            s = ra.collect(conn, "au", Client(pages), "2026-10-16", days=56, regions=["sa"], log=quiet)
        self.assertEqual(s["read"], ["sa"])
        bodies = {r[0] for r in conn.execute("SELECT body FROM regional_agenda")}
        self.assertEqual(bodies, {"House of Assembly", "Legislative Council"})
        self.assertFalse(conn.execute("SELECT 1 FROM regional_agenda WHERE dated < '2026-10-16'").fetchall())
        ours = conn.execute("SELECT COUNT(*) FROM regional_agenda WHERE areas != '[]'").fetchone()[0]
        self.assertGreater(ours, 0)


class TasmaniaTest(unittest.TestCase):
    def test_sittings(self):
        s = au.parse_tas_sittings(fx("tas_sittings_2026.html"))
        # The cell's own day, not its link's phrase ('Tuesday 18 October 2026' for the 27th).
        self.assertIn(("2026-10-27", "House of Assembly"), s)
        self.assertIn(("2026-10-27", "Legislative Council"), s)
        self.assertIn(("2026-10-30", "Legislative Council"), s)
        self.assertNotIn(("2026-10-30", "House of Assembly"), s)
        self.assertNotIn(("2026-10-18", "House of Assembly"), s)

    def test_notice_paper(self):
        self.assertEqual(len(au.tas_notice_links(fx("tas_np_search_2026-10-27.html"), "2026-10-27")), 1)
        self.assertEqual(au.tas_notice_links(fx("tas_np_search_2026-10-27.html"), "2026-10-28"), [])
        items = au.parse_tas_notice_paper(json.loads(fx("tas_np52_27102026.json")))
        self.assertEqual(items[0]["reference"], "Notice of Motion 161")
        self.assertTrue(items[0]["business"].startswith("Notice of motion 161: That the House:"))
        conv = [i for i in items if i["reference"] == "Bill No. 45"][0]
        self.assertEqual(conv["business"], "Conversion Practices Prohibition Bill 2026 (No. 45): Second reading.")
        self.assertFalse(any("Read Third Time" in (i["detail"] or "") for i in items))   # papers issued cut
        self.assertEqual(len([i for i in items if i["dated"] == "2026-10-27"]), 33)

    def test_reader(self):
        search = au.TAS_SEARCH.format("27%20October%202026")
        docx = ("https://search.parliament.tas.gov.au/search/isysquery/8cd725b8-48f4-420e-8a9e-69d58797363f/"
                "3/doc/NP5227102026.docx")
        pages = {au.TAS_SITTINGS.format("2026"): fx("tas_sittings_2026.html"),
                 search: fx("tas_np_search_2026-10-27.html"), docx: b"PK-docx"}
        with mock.patch("src.au_states_votes.docx_paragraphs",
                        return_value=json.loads(fx("tas_np52_27102026.json"))):
            conn = store()
            s = ra.collect(conn, "au", FakeClient(pages), "2026-10-16", days=56, regions=["tas"], log=quiet)
        self.assertEqual(s["read"], ["tas"])
        rows = [dict(r) for r in conn.execute("SELECT * FROM regional_agenda")]
        oct27 = [r for r in rows if r["dated"] == "2026-10-27"]
        self.assertTrue(any(r["reference"] == "Bill No. 45" and json.loads(r["areas"]) for r in oct27))
        self.assertEqual([r["body"] for r in oct27 if r["item_type"] == ra.TBA], ["Legislative Council"])
        # The 28th and 29th searches found nothing (FakeClient: 503): partial gaps, region read.
        self.assertTrue(s["per_region"]["tas"]["status"] == "read")


class FailureTest(unittest.TestCase):
    def test_dead_host_keeps_rows(self):
        conn = store()
        pages = {au.VIC_CAL.format("2026"): json.loads(fx("vic_cal_2026.json"))}
        ra.collect(conn, "au", FakeClient(pages), "2026-09-01", days=28, regions=["vic"], log=quiet)
        n = conn.execute("SELECT COUNT(*) FROM regional_agenda").fetchone()[0]
        self.assertEqual(n, 12)
        s = ra.collect(conn, "au", FakeClient({}), "2026-09-02", days=28, regions=["vic", "nsw"], log=quiet)
        self.assertEqual(s["gap"], ["vic"])
        self.assertEqual(s["blocked"], ["nsw"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM regional_agenda").fetchone()[0], n)

    def test_every_region_declared(self):
        self.assertEqual(set(au.REGIONS), {"nsw", "vic", "qld", "wa", "sa", "tas", "act", "nt"})


if __name__ == "__main__":
    unittest.main()
