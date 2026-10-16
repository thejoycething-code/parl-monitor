"""Germany's Landtage forward agendas (src/regional_agendas/de.py), on
trimmed live captures of 16 October 2026. No network."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from src import regional_agenda as ra  # noqa: E402
from src.regional_agendas import de  # noqa: E402
from test_regional_agenda import FakeClient, load_fixture, store  # noqa: E402


def fx(name):
    return load_fixture("de", name)


def ctx(today="2026-10-16", days=56):
    import datetime
    until = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    return ra.Ctx(today, until, log=lambda *a: None)


class SplitterTest(unittest.TestCase):
    def test_bayern_plenary_pdf_text(self):
        tops = de.split_tops(fx("by-pl90.txt"), default_date="2026-10-20")
        self.assertEqual(len(tops), 15)
        self.assertEqual([o for _, o, _ in tops][:3], ["1", "2", "3"])
        self.assertEqual({d for d, _, _ in tops}, {"2026-10-20"})
        self.assertEqual(de.business_of(tops[4][2]),
                         "Wahl einer Vizepräsidentin oder eines Vizepräsidenten des Bayerischen Landtags")
        self.assertEqual(de.ref_of(tops[2][2]), "Drs. 19/13421")
        # 'Beginn ca. 15:15 Uhr' and 'anschließend' are layout, not business
        self.assertNotIn("Beginn", de.business_of(tops[2][2]))

    def test_bw_date_and_private_names(self):
        tops = de.split_tops(fx("bw-pl.txt"))
        # the '(Meldefrist: Montag, 19. Oktober ...)' line is not a sitting day
        self.assertEqual({d for d, _, _ in tops}, {"2026-10-21"})
        self.assertIn("Haushaltsjahr 2027", de.business_of(tops[2][2]))
        self.assertEqual(de.ref_of(tops[2][2]), "Drs. 18/700")
        objections = [b for _, _, b in tops if "Wahlprüfungsausschusses" in b][0]
        self.assertNotIn("Herrn", de.unname(objections))
        self.assertNotIn("X. Y.", de.unname(objections))

    def test_niedersachsen_two_day_plenary_with_time_column(self):
        tops = de.split_tops(fx("ni-pl.txt"))
        self.assertEqual(tops[0][1:], ("1", "Mitteilungen der Präsidentin"))
        self.assertEqual(tops[0][0], "2026-10-07")
        self.assertIn("Abschließende Beratung", tops[3][2])
        self.assertEqual(de.ref_of(tops[3][2]), "Drs. 19/9898")

    def test_niedersachsen_committee_and_others(self):
        tops = de.split_tops(fx("ni-a.txt"))
        self.assertEqual(len(tops), 6)
        self.assertEqual(tops[0][0], "2026-10-29")
        sh = de.split_tops(fx("sh-pl.txt"))
        self.assertEqual(sh[0][0], "2026-11-11")
        self.assertEqual(de.ref_of(sh[5][2]), "Drs. 20/4909")      # a bare '20/4909'
        th = de.split_tops(fx("th-pl.txt"))
        self.assertEqual(th[0][0], "2026-10-07")
        self.assertTrue(th[1][2].startswith("Thüringer Gesetz zur Reform der Gefangenenvergütung"))
        mv = de.split_tops(fx("mv-pl.txt"))
        self.assertEqual(len(mv), 10)
        self.assertEqual(mv[0][0], "2026-10-20")

    def test_despace_and_day_heading(self):
        self.assertEqual(de.day_heading("D i e n s t a g , 20. Oktober 2026 14:00 Uhr"), "2026-10-20")
        self.assertEqual(de.day_heading("am Mittwoch, den 11. November 2026"), "2026-11-11")


class ParserTest(unittest.TestCase):
    def test_nrw(self):
        days = de.parse_nw_month(fx("nw-month-2026-11.html.gz"))
        self.assertEqual(days["2026-11-24"], "Plenar")
        self.assertEqual(len(days), 17)
        evs = de.parse_nw_day(fx("nw-day-2026-10-15.html.gz"))
        self.assertEqual(evs[-1]["body"], "Plenum")
        self.assertTrue(evs[-1]["to_url"].endswith("/PT18-133.html"))
        plen = de.parse_nw_day(fx("nw-day-2026-11-25.html"))
        self.assertEqual(plen, [{"date": "2026-11-25", "time": "10:00", "body": "Plenum",
                                 "kind": "Plenarsitzung", "to_url": None}])
        to = de.parse_nw_to(fx("nw-to-E18-1922.html"))
        self.assertEqual([o for o, _ in to], ["1", "2"])
        pt = de.parse_nw_to(fx("nw-to-PT18-133.html.gz"))
        self.assertEqual(de.ref_of(pt[1][1]), "Drs. 18/21599")

    def test_bayern_list(self):
        rows = de.parse_by_list(fx("by-list.html.gz"))
        self.assertEqual(len(rows), 26)
        pl = [r for r in rows if r["code"] == "PL"]
        self.assertEqual({r["date"] for r in pl}, {"2026-10-15", "2026-10-20"})
        self.assertEqual(rows[0]["wp"], "19")
        self.assertTrue(any(r["nachtrag"] == "1" for r in rows))

    def test_calendars(self):
        bw = de.bw_calendar(de.ics_events(fx("bw.ics")))
        self.assertEqual(bw[0], ("2026-10-21", "09:30", "Plenum"))
        self.assertIn(("2026-11-12", "10:00", "Ausschuss für Finanzen"), bw)
        self.assertEqual(len(de.parse_bw_to_page(fx("bw-to.html"))), 1)
        be = de.ics_events(fx("be-pl.ics"))
        self.assertEqual([e["date"] for e in be if e.get("summary") == "Plenarsitzung"],
                         ["2026-10-29", "2026-11-12", "2026-11-26", "2026-12-10"])
        th = de.parse_th_invitations(fx("th-dates.html.gz"))
        self.assertEqual(th[1][0], "2026-10-07")          # 'vom 07.10. bis 09.10.2026'
        self.assertEqual(de.parse_st_dates(fx("st-dates.html"))[-5:],
                         ["2026-11-18", "2026-11-19", "2026-12-15", "2026-12-16", "2026-12-17"])
        sh = de.parse_sh_cal(json.loads(fx("sh-cal.json.gz")))
        self.assertIn(("2026-10-27", "10:00", "Petitionsausschuss",
                       "/kalender/Sitzung-Petitionsausschuss-00048/"), sh)
        self.assertEqual(de.parse_sh_to_list(fx("sh-to.html"))[0][:2], ("47", "2026-11-11"))

    def test_feeds_and_pages(self):
        bb = de.rss_items(fx("bb-rss-a.xml"))
        self.assertEqual(de.rss_date(bb[0]["pubDate"]), ("2026-11-10", "13:30"))
        self.assertEqual(de.bb_body(bb[0]["title"], False), "Petitionsausschusses")
        self.assertEqual(de.parse_bb_detail(fx("bb-termin-46045.html")),
                         [("1", "Beratung von Petitionen"), ("2", "Verschiedenes")])
        ni = de.rss_items(fx("ni-rss-a.xml"))
        self.assertEqual(ni[0]["title"], "Ausschuss für Wissenschaft und Kultur")
        he = de.parse_he_list(fx("he-ausschuss-0.html.gz"))
        self.assertEqual(he[0], ("2026-10-19", "Ausschuss für Wissenschaft und Kultur",
                                 "/termine/ausschuss-fuer-wissenschaft-und-kultur-30-sitzung", "09:00"))
        self.assertEqual(len(de.parse_he_termin(fx("he-termin-wka30.html.gz"))), 3)
        hb = de.parse_hb_tops(fx("hb-tops.html.gz"))
        self.assertEqual(hb[0], ("1", "Genehmigung der Tagesordnung"))
        rp = de.parse_rp(json.loads(fx("rp-meetings.json.gz")))
        arv = [r for r in rp if r["id"] == "arv-24773"][0]
        self.assertEqual((arv["date"], arv["time"]), ("2026-10-22", "14:30"))
        self.assertTrue(arv["agenda_url"].endswith("rechtsa-e-3-19.pdf"))
        sn = de.parse_sn_list(fx("sn-pl.html.gz"), True)
        self.assertEqual(sn[0], ("2026-09-17", "Plenum", "2553"))

    def test_hamburg_list_and_state(self):
        rows = de.parse_hh_list(fx("hh-list.html.gz"), "2026-10-16")
        self.assertEqual(len(rows), 50)
        self.assertEqual(rows[-1]["date"], "2027-01-07")    # the year rolls over
        hh = [r for r in rows if r["to_url"]]
        self.assertEqual(hh[0]["body"], "Haushaltsausschuss")
        import base64, gzip
        state = de.hh_state(100)
        raw = gzip.decompress(base64.urlsafe_b64decode(state + "=" * (-len(state) % 4)))
        self.assertEqual(json.loads(raw)["hitsPerPage"], 100)

    def test_merge_drops_covered_tba(self):
        items = [ra.item("2026-11-11", "Gesetz", "Plenum", meeting_id="a")]
        tbas = [de.tba("2026-11-11", "Plenum", "x"), de.tba("2026-11-12", "Plenum", "y"),
                de.tba("2026-11-12", "Plenum", "z")]
        out = de.merge(items, tbas)
        self.assertEqual([(i["dated"], i["business"]) for i in out],
                         [("2026-11-11", "Gesetz"), ("2026-11-12", "")])


class CollectTest(unittest.TestCase):
    def _nrw_pages(self):
        pages = {de.NW_MONTH.format(2026, 10): fx("nw-month-2026-10.html.gz"),
                 de.NW_MONTH.format(2026, 11): fx("nw-month-2026-11.html.gz"),
                 de.NW_MONTH.format(2026, 12): "<table></table>"}
        empty = '<section class="l-container e-event-container"></section>'
        for d in list(de.parse_nw_month(pages[de.NW_MONTH.format(2026, 11)])) + ["2026-10-16"]:
            pages[de.NW_DAY.format(d.replace("-", ""))] = empty
        pages[de.NW_DAY.format("20261125")] = fx("nw-day-2026-11-25.html")
        day16 = fx("nw-day-2026-10-15.html.gz").replace("2026-10-15", "2026-10-16")
        pages[de.NW_DAY.format("20261016")] = day16
        pages[de.NW_HOST + "/home/der-landtag/tagesordnungen/WP18/1900/E18-1926.html"] = \
            fx("nw-to-E18-1922.html")
        pages[de.NW_HOST + "/home/der-landtag/tagesordnungen/WP18/100/PT18-133.html"] = \
            fx("nw-to-PT18-133.html.gz")
        return pages

    def test_nrw_end_to_end(self):
        conn = store()
        s = ra.collect(conn, "de", FakeClient(self._nrw_pages()), "2026-10-16", days=56,
                       regions=["NW", "SL"], log=lambda *a: None)
        self.assertEqual(s["read"], ["NW"])
        self.assertEqual(s["no-route"], ["SL"])
        rows = [dict(r) for r in conn.execute("SELECT * FROM regional_agenda WHERE region='NW'")]
        plen16 = [r for r in rows if r["dated"] == "2026-10-16" and r["body"] == "Plenum"]
        self.assertEqual(len(plen16), 18)
        self.assertTrue(any(r["reference"] == "Drs. 18/21599" for r in plen16))
        tba = [r for r in rows if r["item_type"] == ra.TBA]
        self.assertIn("2026-11-25", {r["dated"] for r in tba})
        self.assertEqual({r["source"] for r in rows},
                         {"landtag.nrw.de Kalender + Tagesordnungen (HTML)"})

    def test_nrw_agenda_failure_keeps_that_day(self):
        pages = self._nrw_pages()
        conn = store()
        ra.collect(conn, "de", FakeClient(pages), "2026-10-16", days=56, regions=["NW"],
                   log=lambda *a: None)
        before = conn.execute("SELECT COUNT(*) FROM regional_agenda WHERE dated='2026-10-16'").fetchone()[0]
        del pages[de.NW_HOST + "/home/der-landtag/tagesordnungen/WP18/100/PT18-133.html"]
        s = ra.collect(conn, "de", FakeClient(pages), "2026-10-16", days=56, regions=["NW"],
                       log=lambda *a: None)
        self.assertEqual(s["read"], ["NW"])
        after = conn.execute("SELECT COUNT(*) FROM regional_agenda WHERE dated='2026-10-16'").fetchone()[0]
        self.assertGreaterEqual(after, before)            # the plenary items were kept
        gaps = [r[0] for r in conn.execute("SELECT detail FROM gaps")]
        self.assertTrue(any("PT18-133" in g for g in gaps), gaps)

    def test_dead_host_is_a_gap_and_rows_kept(self):
        conn = store()
        ra.collect(conn, "de", FakeClient(self._nrw_pages()), "2026-10-16", days=56,
                   regions=["NW"], log=lambda *a: None)
        n = conn.execute("SELECT COUNT(*) FROM regional_agenda").fetchone()[0]
        s = ra.collect(conn, "de", FakeClient({}), "2026-10-17", days=56, regions=["NW"],
                       log=lambda *a: None)
        self.assertEqual(s["gap"], ["NW"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM regional_agenda").fetchone()[0], n)
        run = conn.execute("SELECT status FROM regional_agenda_runs WHERE region='NW' "
                           "AND run_date='2026-10-17'").fetchone()
        self.assertEqual(run[0], "gap")

    def test_bayern_pdf_route_end_to_end(self):
        listing = fx("by-list.html.gz")
        pages = {de.BY_LIST: listing}
        pl90 = de.BY_PDF.format(code="PL", date="20.10.2026", nr="90", nt="0", wp="19")
        for r in de.parse_by_list(listing):
            d = r["date"]
            url = de.BY_PDF.format(code=r["code"], date="{0}.{1}.{2}".format(d[8:], d[5:7], d[:4]),
                                   nr=r["nr"], nt=r["nachtrag"], wp=r["wp"])
            pages[url] = b"Tagesordnung\n1. Verschiedenes\n"
        pages[pl90] = fx("by-pl90.txt").encode("utf-8")
        old = de.pdf_text
        de.pdf_text = lambda data: data.decode("utf-8")
        try:
            read = de.read_by(FakeClient(pages), ctx())
        finally:
            de.pdf_text = old
        plen = [i for i in read.items if i["body"] == "Plenum"]
        self.assertEqual(len(plen), 15)
        self.assertEqual(plen[0]["meeting_id"], "by:19:PL:90")
        self.assertFalse(read.gaps)
        self.assertTrue(all(i["dated"] >= "2026-10-16" for i in read.items))

    def test_hessen_end_to_end(self):
        pages = {
            de.HE_LIST.format("plenarsitzungen-7", 0): fx("he-plenum-0.html.gz"),
            de.HE_LIST.format("ausschusssitzungen-10", 0): fx("he-ausschuss-0.html.gz"),
            de.HE_LIST.format("ausschusssitzungen-10", 1): "<p>keine Termine</p>",
            de.HE_HOST + "/termine/ausschuss-fuer-wissenschaft-und-kultur-30-sitzung":
                fx("he-termin-wka30.html.gz"),
        }
        for r in de.parse_he_list(fx("he-ausschuss-0.html.gz"))[1:]:
            pages[de.HE_HOST + r[2]] = "<main><h1>Termin</h1></main>"
        read = de.read_he(FakeClient(pages), ctx())
        named = [i for i in read.items if i["business"]]
        self.assertEqual(len(named), 3)
        self.assertEqual(named[0]["reference"], "Drs. 21/5354")
        plen = [i for i in read.items if i["body"] == "Plenum"]
        self.assertEqual(len(plen), 6)            # 10-12 Nov, 8-10 Dec: booked, no agenda yet

    def test_modules_regions(self):
        self.assertEqual(sorted(de.REGIONS), sorted(
            "BW BY BE BB HB HH HE MV NI NW RP SL SN ST SH TH".split()))
        self.assertEqual(de.REGIONS["SL"].status, "no-route")


if __name__ == "__main__":
    unittest.main()
