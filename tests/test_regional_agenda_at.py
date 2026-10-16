"""Austria's Landtage forward agendas (src/regional_agendas/at.py) on trimmed
live captures of 16 October 2026 (tests/fixtures/regional_agenda/at/). No
network."""
import json
import os
import sys
import unittest
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import regional_agenda as ra  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.regional_agendas import at  # noqa: E402
from tests.test_regional_agenda import FakeClient, load_fixture, store  # noqa: E402

TODAY, UNTIL = "2026-10-16", "2026-12-11"


def fx(name):
    return load_fixture("at", name)


def ctx():
    return ra.Ctx(TODAY, UNTIL, log=lambda *a: None)


def infodat_url(committees, page=1):
    return at.WIEN_INFODAT + urllib.parse.urlencode(
        {"committees": committees, "sessionDayFrom": TODAY, "sessionDayTo": UNTIL, "page": page})


def not_found(url):
    return FetchError(url, at.FEED, "x", 1, "HTTP Error 404: Not Found")


class ParserTest(unittest.TestCase):
    def test_wien_dates_and_infodat(self):
        landtag = at.parse_wien_dates(fx("wien_termine.html"), "Landtag")
        self.assertEqual(landtag[:3], [("2026-10-20", None), ("2026-11-19", None),
                                       ("2026-12-09", None)])
        gr = at.parse_wien_dates(fx("wien_termine.html"), "Gemeinderat")
        self.assertIn(("2026-12-15", "Voranschlag 2027"), gr)
        rows, last = at.parse_infodat(fx("wien_infodat_L.html"))
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[0][:3], ("Antwort", "2026-10-20", "201830"))
        # Written answers are not agenda business: the sittings stay TBA.
        items = at.wien_items(landtag, rows, "Landtag", ctx())
        self.assertTrue(items)
        self.assertTrue(all(i["business"] == "" for i in items))
        self.assertEqual([i["dated"] for i in items], ["2026-10-20", "2026-11-19", "2026-12-09"])

    def test_noe(self):
        self.assertEqual(at.parse_noe_dates(fx("noe_sitzungen.html.gz"))[:3],
                         ["2026-10-22", "2026-11-19", "2026-12-17"])
        items = at.parse_noe_sitting(fx("noe_2026-10-22.html"), "2026-10-22")
        self.assertEqual(len(items), 15)
        law = items[3]
        self.assertEqual(law["item_order"], 4)
        self.assertEqual(law["item_time"], "13:00")
        self.assertEqual(law["reference"], "Ltg.-1097/XX-2026")
        self.assertIn("Gemeindeverbandsgesetz", law["business"])
        self.assertIn("Kommunal-Ausschusses", law["detail"])
        self.assertEqual(ra.item_type(law["business"]), "bill stage")

    def test_ooe_dates(self):
        dates = at.parse_ooe_dates(fx("ooe_termine.html"))
        self.assertIn(("2026-11-12", None), dates)
        self.assertIn(("2026-12-01", "Budgetlandtag"), dates)

    def test_stmk(self):
        meetings = at.stmk_meetings(json.loads(fx("stmk_next.json")))
        self.assertEqual(meetings[1][1:], ("2026-10-20", "10:00", "PARLIAMENT",
                                           "23. Landtagssitzung", "APPROVED"))
        plenary = at.parse_stmk_meeting(fx("stmk_meeting_plenary.html"), "u", "2026-10-20",
                                        "PARLIAMENT")
        self.assertEqual(len(plenary), 28)
        self.assertEqual(plenary[0]["reference"], "EZ 1725/1")
        self.assertTrue(plenary[0]["business"].startswith("Aktuelle Stunde: Drohende Kürzungen"))
        self.assertTrue(plenary[1]["business"].endswith("(zurückgezogen)"))
        self.assertTrue(all(i["body"] == "Landtag" for i in plenary))
        committee = at.parse_stmk_meeting(fx("stmk_meeting_committee.html"), "c", "2026-10-16",
                                          "COMMITTEE")
        self.assertEqual(len(committee), 1)
        self.assertEqual(committee[0]["body"], "Ausschuss für Europa und Gesellschaft")
        self.assertEqual(committee[0]["item_time"], "10:00")

    def test_sbg_tir_vbg(self):
        sbg = at.parse_sbg_dates(fx("sbg_termine.html"))
        self.assertIn(("2026-11-04", "Landtag", None), sbg)
        self.assertIn(("2026-11-25", "Ausschüsse", "Landesvoranschlag 2027"), sbg)
        self.assertEqual(at.parse_tir_next(fx("tir_landtag.html"), "chste Landtagssitzung"),
                         ["2026-11-04", "2026-11-05"])     # 6 November is the reserve day
        self.assertEqual(at.parse_tir_next(fx("tir_ausschuss.html"), "chsten Ausschusssitzungen"),
                         ["2026-10-21", "2026-10-22", "2026-10-23"])
        self.assertEqual(at.parse_vbg(fx("vbg_tagesordnungen.html")),
                         [("2026-11-18", "Landtag"), ("2026-11-04", "Ausschüsse"),
                          ("2026-11-11", "Ausschüsse")])

    def test_bgld(self):
        dates = at.parse_bgld_dates(fx("bgld_termine_2026.html"))
        self.assertIn(("2026-10-22", "10:00", "Landtag"), dates)
        self.assertIn(("2026-11-04", "14:00", "Ausschüsse"), dates)
        index = dict(at.parse_bgld_index(fx("bgld_index.html.gz")))
        self.assertIn("2026-09-24", index)
        items = at.parse_bgld_agenda(fx("bgld_to21.html"), "2026-09-24")
        self.assertEqual(len(items), 22)
        self.assertEqual(items[0]["business"], "Fragestunde")
        self.assertEqual(items[2]["reference"], "Zahl 2100-0526")
        self.assertIn("Antidiskriminierungsgesetz", items[2]["business"])


class CollectTest(unittest.TestCase):
    def pages(self):
        noe_next = "{0}/sitzungen/XX/2026-11-19".format(at.NOE)
        return {
            at.WIEN_DATES: fx("wien_termine.html"),
            infodat_url("L"): fx("wien_infodat_L.html"),
            at.NOE + "/sitzungen": fx("noe_sitzungen.html.gz"),
            at.NOE + "/sitzungen/XX/2026-10-22": fx("noe_2026-10-22.html"),
            noe_next: not_found(noe_next),
            at.STMK_NEXT: json.loads(fx("stmk_next.json")),
            at.STMK_MEETING.format("b9343e15-f5d4-4cad-9d46-b8158ac2d53c"):
                fx("stmk_meeting_plenary.html"),
            at.STMK_MEETING.format("c5c6fcd4-eb8e-486a-ac6d-61d0a8f6e6b6"):
                fx("stmk_meeting_committee.html"),
            at.SBG_DATES: fx("sbg_termine.html"),
        }

    def test_collect_and_dead_host(self):
        conn = store()
        regions = ["wien", "noe", "stmk", "sbg", "ktn"]
        s = ra.collect(conn, "at", FakeClient(self.pages()), TODAY, days=56, regions=regions,
                       log=lambda *a: None)
        self.assertEqual(sorted(s["read"]), ["noe", "sbg", "stmk", "wien"])
        self.assertEqual(s["blocked"], ["ktn"])
        rows = {r["region"]: r for r in conn.execute(
            "SELECT region, COUNT(*) n, SUM(item_type = 'to be announced') tba FROM regional_agenda "
            "GROUP BY region")}
        # NÖ: 15 points on 22 October, TBA for 19 November (404); 17 December is
        # beyond the window.
        self.assertEqual((rows["noe"]["n"], rows["noe"]["tba"]), (16, 1))
        # Steiermark: 28 plenary points + the committee day's 1 + 4 TBA meetings.
        self.assertEqual(rows["stmk"]["tba"], 4)
        self.assertEqual(rows["wien"]["tba"], 3)
        self.assertGreater(s["tba"], 0)

        # Dead host: NÖ answers 503 for everything; its rows are kept, a gap recorded.
        pages = self.pages()
        for k in [k for k in pages if k.startswith(at.NOE)]:
            del pages[k]
        s2 = ra.collect(conn, "at", FakeClient(pages), "2026-10-17", days=55, regions=["noe"],
                        log=lambda *a: None)
        self.assertEqual(s2["gap"], ["noe"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM regional_agenda WHERE region='noe'")
                         .fetchone()[0], 16)
        gaps = [r[0] for r in conn.execute("SELECT detail FROM gaps WHERE feed='at-regional-agenda'")]
        self.assertTrue(any("stored rows kept" in g for g in gaps))

    def test_partial_failure_keeps_failed_sitting(self):
        pages = self.pages()
        pages[at.STMK_MEETING.format("b9343e15-f5d4-4cad-9d46-b8158ac2d53c")] = FetchError(
            "u", at.FEED, "s", 3, "HTTP Error 500")
        read = at.read_stmk(FakeClient(pages), ctx())
        self.assertTrue(read.gaps)
        self.assertNotIn(ra.window(TODAY, UNTIL), read.units)
        self.assertIn(ra.meeting("c5c6fcd4-eb8e-486a-ac6d-61d0a8f6e6b6"), read.units)


if __name__ == "__main__":
    unittest.main()
