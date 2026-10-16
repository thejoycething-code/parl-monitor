"""Belgium's regional forward agendas (src/regional_agendas/be.py): parsers
on trimmed live captures of 16 October 2026, an end-to-end collect with
FakeClient, and a dead host. No network; no pypdf needed (the PDF readers
are tested on their extracted text, and pdf_text is replaced in the
end-to-end test)."""
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import regional_agenda as ra  # noqa: E402
from src.regional_agendas import be  # noqa: E402
from tests.test_regional_agenda import FakeClient, load_fixture, store  # noqa: E402


def fx(name):
    return load_fixture("be", name)


def ctx(today="2026-10-16", days=56):
    import datetime
    until = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    return ra.Ctx(today, until, log=lambda *a: None)


class VlaamsParlementTest(unittest.TestCase):
    def meetings(self):
        return (be.parse_vl_meetings(json.loads(fx("vl_komende_plen.json"))) +
                be.parse_vl_meetings(json.loads(fx("vl_komende_comm.json"))))

    def test_meetings(self):
        ms = {m["id"]: m for m in self.meetings()}
        plen = ms["2078871"]
        self.assertEqual((plen["date"], plen["time"], plen["body"], plen["plenary"]),
                         ("2026-10-21", "14:00", "Plenaire vergadering", True))
        self.assertTrue(plen["agenda_url"].endswith("/verg/2078871/agd?aanpassingen=nee"))
        wel = ms["2078232"]
        self.assertFalse(wel["plenary"])
        self.assertTrue(wel["body"].startswith("Commissie voor Welzijn, Volksgezondheid"))
        self.assertFalse(ra.is_committee(plen["body"]))
        self.assertTrue(ra.is_committee(wel["body"]))

    def test_plenary_agenda_merges_debate_and_vote(self):
        plen = [m for m in self.meetings() if m["id"] == "2078871"][0]
        items = be.parse_vl_agenda(json.loads(fx("vl_agd_2078871.json.gz")), plen)
        refs = [i["reference"] for i in items]
        self.assertEqual(len(refs), len(set(refs)))       # 925 debated and voted: one item
        first = items[0]
        self.assertTrue(first["business"].startswith("Ontwerp van decreet over de subsidiëring"))
        self.assertEqual(first["reference"], "925 (2025-2026)")
        self.assertIn("Hoofdelijke stemming", first["detail"])
        self.assertEqual(first["meeting_id"], "vl-2078871")
        self.assertTrue(any(i["business"].startswith("Verslag van het verzoekschrift")
                            for i in items))

    def test_committee_agenda_questions(self):
        wel = [m for m in self.meetings() if m["id"] == "2078232"][0]
        items = be.parse_vl_agenda(json.loads(fx("vl_agd_2078232.json.gz")), wel)
        qs = [i for i in items if i["business"].startswith("Vraag om uitleg")]
        self.assertGreater(len(qs), 10)
        self.assertTrue(any("spermadonoren" in i["business"] for i in qs))
        self.assertEqual(ra.item_type(qs[0]["business"], True), "committee business")
        self.assertTrue(any(i["business"].startswith("Regeling van de werkzaamheden")
                            for i in items))


class WalloniaTest(unittest.TestCase):
    def test_agenda(self):
        ms = be.parse_pw_agenda(json.loads(fx("pw_agenda_2026_10.json")))
        plen = [m for m in ms if m["plenary"]][0]
        self.assertEqual((plen["date"], plen["time"], plen["body"]),
                         ("2026-10-14", "14:00", "Séance plénière"))
        self.assertTrue(plen["odj"].startswith("https://nautilus.parlement-wallon.be/"))
        self.assertEqual(be.parse_pw_agenda(json.loads(fx("pw_agenda_empty.json"))), [])

    def test_plenary_order_of_the_day(self):
        m = {"id": "31811", "date": "2026-10-14", "time": "14:00", "body": "Séance plénière",
             "plenary": True, "odj": "https://x/odjs.pdf"}
        items = be.parse_pw_odjs(fx("pw_odjs_20261014.txt"), m)
        self.assertEqual(len(items), 7)
        self.assertTrue(items[0]["business"].startswith("Projet de décret modifiant l'article 35sexies"))
        self.assertEqual(items[0]["reference"], "Doc. 664 (2026-2027)")
        self.assertEqual(items[1]["business"], "Proposition de décret visant à améliorer la "
                         "visibilité des offres d'emploi disponibles en Wallonie")
        self.assertTrue(all(i["lang"] == "taxonomy-fr.yaml" for i in items))

    def test_committee_order_of_the_day(self):
        m = {"id": "31808", "date": "2026-10-13", "time": "09:30", "body": "Commission de la santé",
             "plenary": False, "odj": "https://x/odjc33.pdf"}
        items = be.parse_pw_odjc(fx("pw_odjc33.txt.gz"), m)
        self.assertTrue(any(i["business"].startswith("Pétition pour l'instauration") for i in items))
        qs = [i for i in items if i["item_type"] == "questions"]
        self.assertGreater(len(qs), 20)
        self.assertTrue(qs[0]["business"].startswith("Interpellation de Madame Valérie DEJARDIN"))
        self.assertIn("sur l'annonce de la Conférence permanente", qs[0]["business"])


class BrusselsTest(unittest.TestCase):
    def test_agenda_two_weeks(self):
        ms = be.parse_bru_agenda(fx("bru_agenda.html"), "2026-10-16")
        self.assertFalse(any(m["body"].startswith("Bureau") for m in ms))
        plen = [m for m in ms if m["key"] == "35176"][0]
        self.assertEqual((plen["date"], plen["time"], plen["body"], plen["assemblies"]),
                         ("2026-10-16", "08:30", "Séance plénière", ["PRB", "ARCCC"]))
        cocom = [m for m in ms if m["assemblies"] == ["ARCCC"]]
        self.assertEqual(cocom[0]["body"], "Commission de la Santé et de l'Aide aux personnes")
        self.assertIn("2026-10-21", [m["date"] for m in ms])        # next week

    def test_committee_convocation(self):
        m = {"date": "2026-10-20", "time": "09:00", "body": "Commission Affaires intérieures",
             "key": "35256"}
        items = be.parse_bru_convocation(fx("bru_convoc_35256.txt"), m, "bru")
        self.assertTrue(items[0]["business"].startswith("Demande d'explications de Fouad Ahidar"))
        self.assertEqual(items[0]["reference"], "22995")
        self.assertTrue(items[1]["business"].startswith("Demande d'explications jointe de Joëlle"))
        self.assertTrue(any(i["business"].startswith("Question orale de Zakia") for i in items))
        self.assertEqual(items[0]["meeting_id"], "bru-35256")

    def test_plenary_convocation(self):
        m = {"date": "2026-10-16", "time": "08:30", "body": "Séance plénière", "key": "35176"}
        items = be.parse_bru_convocation(fx("bru_convoc_35176.txt"), m, "bru")
        refs = [i["reference"] for i in items if i["reference"]]
        self.assertIn("A-326/1 – 2026/2027", refs)
        self.assertTrue(items[0]["business"].startswith("PROPOSITION D’ORDONNANCE"))
        self.assertFalse(any("RAPPORTEUSE" in i["business"] for i in items))
        self.assertIn("Questions d’actualité", [i["business"] for i in items])


class FwbCocofTest(unittest.TestCase):
    def test_index(self):
        idx = be.parse_fwb_index(fx("fwb_agenda.html"))
        kinds = {k for _, k, _ in idx}
        self.assertEqual(kinds, {"seances-plenieres", "commissions-permanentes"})
        self.assertIn(("https://www.pfwb.be/agendas/seances-plenieres-2026-10-21-001865201",
                       "seances-plenieres", "2026-10-21"), idx)

    def test_committee_meeting(self):
        url = "https://www.pfwb.be/agendas/commissions-permanentes-2026-10-20-001864902"
        items = be.parse_fwb_meeting(fx("fwb_com_20261020.html.gz"), url, "2026-10-20")
        self.assertTrue(items[0]["body"].startswith("Commission de la Culture"))
        self.assertEqual(items[0]["item_time"], "10:00")
        bill = [i for i in items if i["reference"] == "Doc. 324 (2026-2027)"][0]
        self.assertTrue(bill["business"].startswith("Projet de décret de la Communauté française"))
        self.assertTrue(any(i["business"].startswith("Question orale de Mme Barbara Trachte")
                            for i in items))

    def test_plenary_meeting(self):
        url = "https://www.pfwb.be/agendas/seances-plenieres-2026-10-21-001865201"
        items = be.parse_fwb_meeting(fx("fwb_plen_20261021.html"), url, "2026-10-21")
        self.assertEqual(items[0]["body"], "Séance plénière")
        self.assertEqual([i["reference"] for i in items[:3]],
                         ["Doc. 321 (2026-2027)", "Doc. 318 (2026-2027)", "Doc. 275 (2025-2026)"])
        self.assertTrue(items[2]["business"].startswith("Proposition de résolution relative"))

    def test_cocof(self):
        ms = be.parse_cocof_month(fx("cocof_2026_10.html"))
        m = [x for x in ms if x["date"] == "2026-10-20"][0]
        self.assertEqual(m["time"], "14:30")
        conv = be.parse_cocof_event(fx("cocof_event.html"))
        self.assertIn("/agenda/convocations/", conv)
        items = be.parse_cocof_convocation(fx("cocof_convocation.html"), m)
        self.assertEqual(len(items), 1)
        self.assertIn("droits liés à la grossesse", items[0]["business"])
        self.assertEqual(items[0]["reference"], "Proposition - 52 (2025 - 2026) - N° 1")


class CollectTest(unittest.TestCase):
    PAGES = {
        be.VL_LIST.format("plen"): fx("vl_komende_plen.json"),
        be.VL_LIST.format("comm"): fx("vl_komende_comm.json"),
        "https://ws.vlpar.be/e/opendata/verg/2078871/agd?aanpassingen=nee": fx("vl_agd_2078871.json.gz"),
        "https://ws.vlpar.be/e/opendata/verg/2078232/agd?aanpassingen=nee": fx("vl_agd_2078232.json.gz"),
        "https://ws.vlpar.be/e/opendata/verg/2074868/agd?aanpassingen=nee": fx("vl_agd_2074868.json"),
        be.BRU_AGENDA: fx("bru_agenda.html"),
        be.FWB_AGENDA: fx("fwb_agenda.html"),
        "https://www.pfwb.be/agendas/commissions-permanentes-2026-10-20-001864902":
            fx("fwb_com_20261020.html.gz"),
        "https://www.pfwb.be/agendas/seances-plenieres-2026-10-21-001865201":
            fx("fwb_plen_20261021.html"),
    }

    def setUp(self):
        be._BRU_CACHE.clear()

    def test_collect_end_to_end_and_dead_host(self):
        pages = dict(self.PAGES)
        texts = {}
        for key in ("35256", "35176"):
            url = be.BRU_CONVOC.format(key)
            pages[url] = ("PDF:" + key).encode()
            texts[("PDF:" + key).encode()] = fx("bru_convoc_{0}.txt".format(key))
        client = FakeClient(pages)
        conn = store()
        with mock.patch.object(be, "pdf_text", side_effect=lambda b: texts.get(b)):
            s = ra.collect(conn, "be", client, "2026-10-16", days=28, regions=["vl", "bru", "fwb"],
                           log=lambda *a: None)
        self.assertEqual(s["read"], ["vl", "bru", "fwb"])   # fwb and bru read in part
        self.assertEqual(s["gap"], [])
        rows = conn.execute("SELECT * FROM regional_agenda").fetchall()
        by = {}
        for r in rows:
            by.setdefault(r["region"], []).append(r)
        self.assertGreater(len(by["vl"]), 20)
        # convocations that failed are gaps, not placeholders
        self.assertEqual({r["meeting_id"] for r in by["bru"]}, {"bru-35256", "bru-35176"})
        bru_named = [r for r in by["bru"] if r["meeting_id"] == "bru-35256"]
        self.assertTrue(bru_named and all(r["lang"] == "taxonomy-fr.yaml" for r in bru_named))
        self.assertIn("fwb", by)
        gaps = [r[0] for r in conn.execute("SELECT detail FROM gaps WHERE feed='be-regional-agenda'")]
        self.assertTrue(any("FWB meeting" in g for g in gaps))
        n_vl = len(by["vl"])

        # The Flemish service goes down: its rows are kept, a gap is recorded.
        dead = FakeClient({})
        s2 = ra.collect(conn, "be", dead, "2026-10-17", days=28, regions=["vl"],
                        log=lambda *a: None)
        self.assertEqual(s2["gap"], ["vl"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM regional_agenda WHERE region='vl'")
                         .fetchone()[0], n_vl)

    def test_blocked_and_no_route_declared(self):
        self.assertEqual(be.REGIONS["pdg"].status, "blocked")
        self.assertEqual(be.REGIONS["vgc"].status, "no-route")
        conn = store()
        s = ra.collect(conn, "be", FakeClient({}), "2026-10-16", regions=["pdg", "vgc"],
                       log=lambda *a: None)
        self.assertEqual((s["blocked"], s["no-route"]), (["pdg"], ["vgc"]))


if __name__ == "__main__":
    unittest.main()
