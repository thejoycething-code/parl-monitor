"""Italy's regional forward agendas (src/regional_agendas/it.py): parsers on
trimmed live captures of 16 October 2026, an end-to-end collect with
FakeClient, and a dead host. No network; no pypdf needed."""
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import regional_agenda as ra  # noqa: E402
from src.regional_agendas import it  # noqa: E402
from tests.test_regional_agenda import FakeClient, load_fixture, store  # noqa: E402


def fx(name):
    return load_fixture("it", name)


class LazioTest(unittest.TestCase):
    def test_home_agenda(self):
        es = it.parse_laz_home(fx("laz_home.html"), "2026-10-16")
        self.assertEqual(len(es), 9)
        self.assertEqual((es[0]["date"], es[0]["time"], es[0]["cid"]), ("2026-10-19", "10:00", "4"))
        self.assertTrue(es[0]["body"].startswith("IV Commissione - Bilancio"))
        self.assertIn("Sanità", [e for e in es if e["cid"] == "7"][0]["body"])

    def test_committee_sittings(self):
        s = it.parse_laz_committee(fx("laz_comm_7.html"), "VII Commissione", "2026-10-16", "7")
        items = s[("2026-10-20", "14:00")]
        self.assertEqual(len(items), 2)
        self.assertTrue(items[1]["business"].startswith("proposta di legge regionale n. 287"))
        self.assertEqual(items[1]["item_order"], 2)
        self.assertEqual(items[0]["meeting_id"], "laz-7-2026-10-20-63")


class CampaniaSiciliaTest(unittest.TestCase):
    def test_campania(self):
        ss = it.parse_cam_list(fx("cam_odg.html"))
        self.assertEqual(len(ss), 1)
        self.assertEqual((ss[0]["date"], ss[0]["title"], ss[0]["id"]),
                         ("2026-11-11", "Seduta Monotematica", "36095"))
        items = it.parse_cam_convocation(fx("cam_conv_36095.txt"), ss[0])
        self.assertEqual(len(items), 2)
        self.assertIn("Aree interne della Campania", items[0]["business"])
        self.assertEqual(items[0]["item_time"], "12:30")

    def test_sicilia(self):
        dates = it.parse_ars_dates(fx("sic_commissione.html"))
        self.assertIn("2026-10-20", dates)
        self.assertIn("2026-10-21", dates)
        frag = json.loads(fx("sic_commissione_20261020.json"))["html"]
        got = it.parse_ars_day(frag, "2026-10-20", "commissione")
        # 'I - Affari Istituzionali' is cancelled ('disdetta'): dropped
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0]["body"].startswith("Commissione d'inchiesta e vigilanza"))
        self.assertEqual((got[0]["item_time"], got[0]["business"]), ("12:00", ""))
        frag = json.loads(fx("sic_commissione_20261021.json"))["html"]
        self.assertEqual(it.parse_ars_day(frag, "2026-10-21", "commissione"), [])


class EmrToscanaTest(unittest.TestCase):
    def test_ics(self):
        evs = it.parse_ics(fx("emr_agenda.ics"))
        aula = [e for e in evs if e["start"].startswith("20261020")][0]
        self.assertTrue(aula["summary"].startswith("Due giorni di Aula: progetti di legge su cultura"))
        self.assertEqual(it.emr_body(aula["summary"]), "Aula")
        self.assertEqual(it.emr_body("Progetti di legge su celiachia e interrogazioni in "
                                     "Commissione Salute"), "Commissione Salute")
        self.assertEqual(it.emr_body("In Commissione cultura discussione"), "Commissione Cultura")

    def test_toscana(self):
        cal = it.parse_tos_calendar(fx("tos_prox.html"))
        self.assertEqual(cal[0], ("2026-10-20", "seduta pomeridiana del consiglio regionale"))
        self.assertIn("2027-01-12", [d for d, _ in cal])
        date, time, items = it.parse_tos_odg(fx("tos_odg.html.gz"))
        self.assertEqual((date, time), ("2026-10-20", "14:30"))
        self.assertTrue(items[0]["business"].startswith("Interrogazione n. 131: In merito alle azioni"))
        self.assertTrue(any("niqab" in i["business"] for i in items))
        pdl = [i for i in items if i["reference"] == "Pdl 54"][0]
        self.assertIn("ARPAT", pdl["business"])
        self.assertTrue(pdl["detail"].startswith("PRIMA"))


class MarcheTrentoCalabriaTest(unittest.TestCase):
    def test_marche(self):
        idx = it.parse_mar_index(fx("mar_index.html.gz"))
        self.assertEqual(idx[0], ("951", "2026-10-20"))
        date, time, items = it.parse_mar_odg(fx("mar_odg_951.html.gz"), "951")
        self.assertEqual((date, time), ("2026-10-20", "10:00"))
        self.assertGreater(len(items), 30)
        self.assertEqual(items[0]["reference"], "n. 472")
        self.assertEqual(items[0]["detail"], "Interrogazioni a risposta immediata")
        self.assertFalse(any(i["business"].startswith("IL PRESIDENTE") for i in items))

    def test_trento(self):
        cs = it.parse_tn(fx("tn_conv.html.gz"))
        council = [c for c in cs if c["body"] == "Consiglio provinciale"]
        self.assertEqual([(c["date"], c["time"]) for c in council],
                         [("2026-10-23", "09:30"), ("2026-10-23", "14:30")])
        self.assertTrue(all(c["url"].startswith(it.TN + "/_layouts/") for c in cs))

    def test_calabria(self):
        urls = it.parse_cal_home(fx("cal_home.html"))
        self.assertEqual(len(urls), 4)
        u = [x for x in urls if "Comm=Sesta" in x][0]
        items = it.parse_cal_odg(fx("cal_odg_sesta.html"), u)
        self.assertEqual(len(items), 3)
        self.assertEqual((items[0]["dated"], items[0]["item_time"]), ("2026-10-20", "11:00"))
        self.assertTrue(items[0]["body"].startswith("Sesta Commissione"))
        self.assertEqual(items[0]["reference"], "Proposta di Legge n.81/13^")
        self.assertNotIn("Relatore", items[0]["business"])


class CollectTest(unittest.TestCase):
    def test_collect_end_to_end_and_dead_host(self):
        pages = {
            it.LAZ: fx("laz_home.html"),
            it.LAZ_COMM.format("7"): fx("laz_comm_7.html"),
            it.LAZ_COMM.format("5"): fx("laz_comm_5.html"),
            it.TOS_PROX: fx("tos_prox.html"),
            it.TOS_ODG: fx("tos_odg.html.gz"),
            it.EMR_ICS: fx("emr_agenda.ics"),
            it.CAM_ODG: fx("cam_odg.html"),
            "https://www.cr.campania.it/crccmsintegrationservices/rest/services/documentale/"
            "prendiDocumento?id=292741": b"PDF",
        }
        client = FakeClient(pages)
        conn = store()
        with mock.patch.object(it, "pdf_text", return_value=fx("cam_conv_36095.txt")):
            s = ra.collect(conn, "it", client, "2026-10-16", days=56,
                           regions=["laz", "tos", "emr", "cam", "lom"], log=lambda *a: None)
        self.assertEqual(s["read"], ["laz", "tos", "emr", "cam"])
        self.assertEqual(s["blocked"], ["lom"])
        rows = {}
        for r in conn.execute("SELECT * FROM regional_agenda"):
            rows.setdefault(r["region"], []).append(r)
        # Lazio: the committees whose pages were not served are gaps; VII is read
        self.assertTrue(any(r["meeting_id"] == "laz-7-2026-10-20-63" and r["business"]
                            for r in rows["laz"]))
        tos = rows["tos"]
        self.assertTrue(any(json.loads(r["areas"]) for r in tos))       # the niqab motion
        self.assertTrue(any(r["item_type"] == ra.TBA and r["dated"] == "2026-11-03" for r in tos))
        self.assertEqual(len(rows["cam"]), 2)
        n_tos = len(tos)

        s2 = ra.collect(conn, "it", FakeClient({}), "2026-10-17", days=56, regions=["tos"],
                        log=lambda *a: None)
        self.assertEqual(s2["gap"], ["tos"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM regional_agenda WHERE region='tos'")
                         .fetchone()[0], n_tos)
        gaps = [r[0] for r in conn.execute("SELECT detail FROM gaps WHERE feed='it-regional-agenda'")]
        self.assertTrue(any("Toscana" in g and "stored rows kept" in g for g in gaps))

    def test_every_region_declared(self):
        self.assertEqual(len(it.REGIONS), 22)
        for code in ("lom", "ven", "pug", "bas"):
            self.assertEqual(it.REGIONS[code].status, "blocked")


if __name__ == "__main__":
    unittest.main()
