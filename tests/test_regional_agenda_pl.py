"""Poland's regional forward agendas (src/regional_agendas/pl.py) on trimmed
live captures of 16 October 2026 (tests/fixtures/regional_agenda/pl/:
scripts, styles and page heads dropped, big pages gzipped; the .docx agendas
keep only word/document.xml). No network."""
import datetime
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import regional_agenda as ra  # noqa: E402
from src.http import RobotsRefused  # noqa: E402
from src.regional_agendas import pl  # noqa: E402
from tests.test_regional_agenda import FIX, FakeClient, load_fixture, store  # noqa: E402

TODAY = "2026-10-16"


def fx(name):
    path = os.path.join(FIX, "pl", name)
    return load_fixture("pl", name + ".gz" if os.path.exists(path + ".gz") else name)


def fj(name):
    return json.loads(fx(name))


def fb(name):
    with open(os.path.join(FIX, "pl", name), "rb") as fh:
        return fh.read()


def ctx(today=TODAY, days=56):
    until = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    return ra.Ctx(today, until, log=lambda *a: None)


class HelpersTest(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(pl.pl_date("XXXIII-26 października2026 r."), "2026-10-26")
        self.assertEqual(pl.pl_date("w dniu 20 października 2026 r. (wtorek)"), "2026-10-20")
        self.assertEqual(pl.pl_date("Porządek posiedzenia KSR 21.10.2026"), "2026-10-21")
        self.assertEqual(pl.pl_date("xxix-sesja-22-wrzesnia-2026-r"), "2026-09-22")
        self.assertEqual(pl.pl_date("Sesja XXXI - 26 pa&#378;dziernika 2026"), "2026-10-26")
        self.assertEqual(pl.pl_time("o godzinie 8:00 w sali"), "08:00")
        self.assertEqual(pl.pl_time("godz. 15.00"), "15:00")

    def test_agenda_point(self):
        self.assertEqual(pl.agenda_point(
            "w sprawie nadania Statutu Wojewódzkiemu Ośrodkowi Medycyny Pracy w Gdańsku – projekt "
            "uchwały przedstawia Pan Leszek Bonna - Wicemarszałek Województwa Pomorskiego; druk nr  471; "),
            ("w sprawie nadania Statutu Wojewódzkiemu Ośrodkowi Medycyny Pracy w Gdańsku", "druk nr 471"))
        self.assertEqual(pl.agenda_point("4.2. zmieniająca uchwałę w sprawie WPF (Druk Nr 4.2);"),
                         ("zmieniająca uchwałę w sprawie WPF", "druk nr 4.2"))

    def test_points_items_parent(self):
        items = pl.points_items(["Otwarcie.", "Przyjęcie uchwał:", "w sprawie A; druk nr 1;",
                                 "w sprawie B; druk nr 2;", "Wolne wnioski."],
                                "2026-10-26", "Plenary", "m1", "u")
        self.assertEqual([i["business"] for i in items],
                         ["Otwarcie.", "Przyjęcie uchwał: w sprawie A", "Przyjęcie uchwał: w sprawie B",
                          "Wolne wnioski."])
        self.assertEqual([i["item_order"] for i in items], [1, 2, 3, 4])
        self.assertEqual(items[1]["reference"], "druk nr 1")


class ParsersTest(unittest.TestCase):
    def test_mz(self):
        tt = pl.parse_mz_timetable(fx("mz-term.html"))
        self.assertIn(("2026-10-27", None), tt)
        self.assertIn(("2026-12-15", None), tt)
        self.assertNotIn("2024-10-29", [d for d, _ in tt])          # 'nie odbyła się'
        folders = pl.parse_mz_year(fx("mz-year-2026.html"))
        self.assertTrue(folders["2026-09-22"].endswith("/2026/xxix-sesja-22-wrzesnia-2026-r/"))
        pts = pl.parse_mz_agenda(fx("mz-agenda.html"))
        self.assertEqual(pts[0], "Otwarcie posiedzenia.")
        self.assertIn("druk nr 576", pts[2])
        planned = pl.parse_mz_planned(fx("mz-planned.html"))
        body, dated, tm, url, pts = planned[0]
        self.assertEqual((body, dated, tm), ("Komisja Kultury i Dziedzictwa Narodowego", "2026-10-19", "12:30"))
        self.assertEqual(len(pts), 4)
        self.assertTrue(pts[0].startswith("Pierwsze czytanie projektu uchwały"))

    def test_sl(self):
        rows = pl.parse_sl_drafts(fx("sl-drafts-2026-10.html"))
        self.assertEqual(rows[0][:2], ("2026-10-19", "XXXI"))
        self.assertIn("%5Epa%C5%BAdziernik", pl.sl_month_url(2026, 10))

    def test_ma(self):
        rows = pl.parse_ma_committees(fj("ma-committees.json"))
        self.assertIn(("2947908", "2026-10-21", "11:00",
                       "Komisja Ochrony Zdrowia, Komisja Polityki Prorodzinnej i Społecznej"),
                      [r[:4] for r in rows])
        pts = pl.parse_madkom_agenda(fj("ma-article.json")["content"])
        self.assertEqual(pts[0], "Otwarcie posiedzenia.")
        self.assertEqual(pts[1], "Opiniowanie projektów uchwał.")
        self.assertTrue(any("Młoda Małopolska" in p for p in pts))
        self.assertEqual(pts[-1], "Zamknięcie posiedzenia.")

    def test_pm(self):
        sessions = pl.parse_pm_sessions(fj("pm-materials.json")["content"])
        dated, label, link = sessions[0]
        self.assertEqual(dated, "2026-10-26")
        self.assertIn("porzadek+obrad.docx", link)
        data = fb("pm-agenda.docx")
        self.assertEqual(pl.docx_time(data), "11:00")
        items = pl.points_items(pl.docx_points(data), dated, "Plenary", "m", link)
        self.assertEqual(items[0]["business"], "Otwarcie obrad Sejmiku.")
        e65 = [i for i in items if "E65" in i["business"]][0]
        self.assertEqual(e65["reference"], "druk nr 473")
        self.assertNotIn("przedstawia", e65["business"])

    def test_ds(self):
        rows = pl.parse_ds_sittings(fj("ds-sittings.json")["content"])
        self.assertIn(("2026-10-29", "XXXI", None), rows)
        self.assertIn(("2026-09-30", "XXX", "11:00"), rows)
        com = pl.parse_ds_committees(fj("ds-committees.json")["content"])
        self.assertIn(("Komisja Budżetu i Finansów", "2026-09-28", "14:00",
                       "sala 1222 Dolnośląski Urząd Wojewódzki",
                       "https://bip.dolnyslask.pl/Download/get/id,242300.html"), com)
        self.assertNotIn("Komisja Rewizyjna", [c[0] for c in com])   # no date set

    def test_pk(self):
        sittings = pl.parse_pk_sittings(fx("pk-sittings.html"))
        self.assertEqual(sittings[0][0], "2026-10-26")
        link = pl.parse_pk_materials(fx("pk-sitting.html"))
        self.assertIn("01._porz%C4%85dek_obrad_XXXIII_sesji.docx", link)
        data = fb("pk-agenda.docx")
        self.assertEqual(pl.docx_time(data), "13:00")
        pts = pl.docx_points(data)
        self.assertEqual((pts[0], pts[-1]), ("Otwarcie sesji.", "Zamknięcie sesji."))
        com = pl.parse_pk_committees(fx("pk-committees.html"))
        body, dated, tm, url, pts = com[0]
        self.assertEqual((body, dated, tm), ("Komisji Głównej", "2026-10-16", "08:00"))
        self.assertEqual(pts[0], "Przyjęcie Protokołu nr 33/2026.")

    def test_kp(self):
        idx = pl.parse_kp_index(fx("kp-index.html"))
        self.assertEqual(idx[0][0], "2026-09-28")
        pts = pl.parse_kp_agenda(fx("kp-agenda.html"))
        self.assertTrue(pts[0].startswith("Otwarcie sesji"))
        self.assertIn("stwierdzenie quorum", pts[1])                # nested list kept in its parent
        self.assertTrue(any("druk nr 61/26" in p for p in pts))

    def test_ld(self):
        rows = pl.parse_ld_list(fx("ld-sittings.html"))
        self.assertEqual(rows[0][0], "2026-10-20")
        self.assertIn("17916", rows[0][2])
        tm, pts = pl.parse_ld_item(fx("ld-item.html"))
        self.assertEqual(tm, "15:00")
        items = pl.points_items(pts, "2026-10-20", "Plenary", "m", "u")
        self.assertEqual(len(items), 19)
        self.assertTrue(items[3]["business"].startswith("Rozpatrzenie projektów uchwał: w sprawie zmian budżetu"))

    def test_wn_zp(self):
        sittings = pl.parse_wn_category(fx("wn-sittings.html"))
        self.assertEqual(pl.pl_date(sittings[0][1]), "2026-09-29")
        months = pl.parse_wn_category(fx("wn-committees.html"))
        self.assertIn("październik 2026", months[0][1])
        self.assertEqual(pl.parse_wn_attachments(fx("wn-committee-month.html")),
                         [("KROWROŚiGW", "2026-10-16"), ("KSR", "2026-10-21")])
        zp = pl.parse_zp_sittings(fx("zp-sittings.html"))
        self.assertEqual(zp[0][:2], ("2026-10-22", "XX sesja Sejmiku - 22 października 2026 r."))


class CollectTest(unittest.TestCase):
    def pages(self):
        return {
            pl.madkom_article_url(pl.PM, pl.PM_MATERIALS): fj("pm-materials.json"),
            "https://bip.pomorskie.eu/e,pobierz,get.html?id=159745&file=porzadek+obrad.docx": fb("pm-agenda.docx"),
            pl.PK_SITTINGS: fx("pk-sittings.html"),
            "https://sejmik.podkarpackie.pl/prace-sejmiku/sesje/xxxiii-26-pazdziernika2026-r": fx("pk-sitting.html"),
            "https://sejmik.podkarpackie.pl/images/sesje_7/33/01._porz%C4%85dek_obrad_XXXIII_sesji.docx":
                fb("pk-agenda.docx"),
            pl.PK_COMMITTEES: fx("pk-committees.html"),
            pl.ZP_SITTINGS: fx("zp-sittings.html"),
        }

    def test_end_to_end_then_dead_host(self):
        conn = store()
        client = FakeClient(self.pages())
        s = ra.collect(conn, "pl", client, TODAY, regions=["pm", "pk", "zp", "op"], log=lambda *a: None)
        self.assertEqual(sorted(s["read"]), ["pk", "pm", "zp"])
        self.assertEqual(s["no-route"], ["op"])
        per = s["per_region"]
        self.assertEqual(per["pm"]["rows"], 13)
        self.assertEqual(per["zp"]["rows"], 1)
        self.assertEqual(s["tba"], 1)                              # Zachodniopomorskie's sitting
        rows = conn.execute("SELECT business, item_time, reference FROM regional_agenda "
                            "WHERE region='pk' AND body='Plenary' ORDER BY item_order").fetchall()
        self.assertEqual(tuple(rows[0]), ("Otwarcie sesji.", "13:00", None))
        n_pk = conn.execute("SELECT COUNT(*) FROM regional_agenda WHERE region='pk'").fetchone()[0]

        # next run: the Joomla host is down (whole region a gap, rows kept);
        # Pomorskie's agenda refused by robots.txt (partial: a gap, sitting rows kept)
        pages = self.pages()
        del pages[pl.PK_SITTINGS]
        pages["https://bip.pomorskie.eu/e,pobierz,get.html?id=159745&file=porzadek+obrad.docx"] = RobotsRefused(
            "u", "f", "s", "robots.txt disallows /e,pobierz")
        s2 = ra.collect(conn, "pl", FakeClient(pages), "2026-10-17", regions=["pm", "pk"],
                        log=lambda *a: None)
        self.assertEqual(s2["gap"], ["pk"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM regional_agenda WHERE region='pk'").fetchone()[0],
                         n_pk)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM regional_agenda WHERE region='pm'").fetchone()[0],
                         13)
        gaps = [r[0] for r in conn.execute("SELECT detail FROM gaps").fetchall()]
        self.assertTrue(any("PL pk" in g for g in gaps))
        self.assertTrue(any("Pomorskie" in g for g in gaps))

    def test_every_region_declared(self):
        self.assertEqual(len(pl.REGIONS), 16)
        read = [c for c, r in pl.REGIONS.items() if r.reader]
        self.assertEqual(len(read), 10)


if __name__ == "__main__":
    unittest.main()
