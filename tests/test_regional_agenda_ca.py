"""Canada's provincial forward agendas (src/regional_agendas/ca.py): each
parser over a trimmed live capture of 16 October 2026 (Quebec's populated
week is a Wayback Machine capture of 12 November 2025, labelled in the
file), an end-to-end collect with FakeClient, and a dead host. No network."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import regional_agenda as ra  # noqa: E402
from src.regional_agendas import ca  # noqa: E402
from tests.test_regional_agenda import FakeClient, load_fixture, store  # noqa: E402


def fx(name):
    return load_fixture("ca", name)


def quiet(*a, **k):
    pass


class OntarioTest(unittest.TestCase):
    def test_order_paper(self):
        items = ca.parse_on_orders(fx("on_orders_2026-10-27.html.gz"), "2026-10-27", "u")
        bills = [i for i in items if i["dated"] == "2026-10-27" and (i["reference"] or "").startswith("Bill")]
        self.assertGreater(len(bills), 80)
        first = items[0]
        self.assertEqual(first["reference"], "Bill 1")
        self.assertEqual(first["business"],
                         "Second Reading: Bill 1, An Act to perpetuate an ancient parliamentary right")
        self.assertIn("Hon. Doug Ford", first["detail"])
        gov = [i for i in items if (i["reference"] or "").startswith("Government Order")]
        self.assertEqual(len(gov), 9)
        # The ballot list reaches weeks ahead: dated items to 18 November.
        later = {i["dated"]: i for i in items if i["dated"] > "2026-10-27"}
        self.assertEqual(max(later), "2026-11-18")
        self.assertEqual(later["2026-10-28"]["reference"], "Bill 117")
        self.assertEqual(later["2026-10-29"]["reference"], "Motion 79")
        self.assertTrue(later["2026-10-29"]["business"].startswith(
            "Private members' public business: motion 79: That, in the opinion"))
        # No French text.
        self.assertFalse(any("Deuxième lecture" in i["business"] for i in items))

    def test_session_links_and_day_view(self):
        self.assertEqual(ca.on_order_papers(fx("on_session.html"), "2026-10-16", "2026-12-11"),
                         [("2026-10-27", "https://www.ola.org/en/legislative-business/house-documents/"
                                         "parliament-44/session-1/2026-10-27/orders-notices")])
        self.assertEqual(ca.on_order_papers(fx("on_session.html"), "2026-10-28", "2026-12-11"), [])
        ev = ca.parse_on_day(fx("on_day_2026-10-22.html"), "2026-10-22")
        self.assertEqual(ev, [("committee", "9 a.m.", "Standing Committee on Government Agencies",
                               "Review of Intended Appointments",
                               "Proceeding: Sub-committee Report and Public Hearings; Committee Room 151")])
        self.assertEqual(ca.parse_on_day(fx("on_day_2026-11-17.html"), "2026-11-17"),
                         [("house", "9 a.m.", "Legislative Assembly", "", None)])

    def test_collect_end_to_end(self):
        empty = "<div class='day_on_month'></div>"
        pages = {ca.ON_HOUSE_DOCS: fx("on_house_documents.html"),
                 ca.ON_HOUSE_DOCS + "/parliament-44/session-1": fx("on_session.html"),
                 "https://www.ola.org/en/legislative-business/house-documents/parliament-44/session-1/"
                 "2026-10-27/orders-notices": fx("on_orders_2026-10-27.html.gz")}
        for d in ca.weekdays("2026-10-20", "2026-10-30"):
            pages[ca.ON_DAY.format(d)] = empty
        pages[ca.ON_DAY.format("2026-10-22")] = fx("on_day_2026-10-22.html")
        # A sitting with no order paper yet: the 28th, as the 17 November page prints it.
        pages[ca.ON_DAY.format("2026-10-28")] = fx("on_day_2026-11-17.html")
        pages[ca.ON_DAY.format("2026-10-27")] = fx("on_day_2026-11-17.html")
        conn = store()
        s = ra.collect(conn, "ca", FakeClient(pages), "2026-10-20", days=10, regions=["on"], log=quiet)
        self.assertEqual(s["read"], ["on"])
        rows = [dict(r) for r in conn.execute("SELECT * FROM regional_agenda")]
        by_date = {}
        for r in rows:
            by_date.setdefault(r["dated"], []).append(r)
        # The 27th has its order paper, so no placeholder; the 28th has the
        # ballot item (Bill 117), so none either.
        self.assertFalse([r for r in by_date["2026-10-27"] if r["item_type"] == ra.TBA])
        self.assertTrue(any(r["reference"] == "Bill 117" for r in by_date["2026-10-28"]))
        self.assertTrue(any(r["body"] == "Standing Committee on Government Agencies" for r in rows))
        ours = [r for r in rows if json.loads(r["areas"])]
        self.assertTrue(any("Bill 137" == r["reference"] for r in ours))
        run = conn.execute("SELECT status, horizon FROM regional_agenda_runs WHERE region='on'").fetchone()
        self.assertEqual(run["status"], "read")


class QuebecTest(unittest.TestCase):
    def test_empty_live_week(self):
        start, end, rows, nxt = ca.parse_qc_week(fx("qc_week_live.html"))
        self.assertEqual((start, end, rows, nxt), ("2026-10-12", "2026-10-18", [], None))

    def test_populated_week(self):
        start, end, rows, nxt = ca.parse_qc_week(fx("qc_week_wayback_2025-11-10.html"))
        self.assertEqual(start, "2025-11-10")
        self.assertTrue(nxt.endswith("calendrier-travaux.html?Date=2025-11-17"))
        sittings = [r for r in rows if r[2] == "sitting"]
        self.assertEqual(len(sittings), 5)
        self.assertEqual(sittings[0][:3], ("2025-11-11", 1, "sitting"))
        self.assertEqual(sittings[0][5], "13 h 40 à 18 h 30")
        cmte = [r for r in rows if r[2] == "committee"]
        self.assertEqual(cmte[2][3], "Commission de la santé et des services sociaux")
        self.assertEqual(cmte[2][4], "Étude détaillée du projet de loi n° 103")
        priv = [r for r in cmte if r[3] == "Commission de l'administration publique"]
        self.assertIn("activité privée", priv[0][6])

    def test_reader_follows_weeks_and_classifies_in_french(self):
        page = fx("qc_week_wayback_2025-11-10.html")
        pages = {ca.QC_WEEK: page,
                 ca.QC_BASE + "/fr/travaux-parlementaires/calendrier-travaux.html?Date=2025-11-17":
                 fx("qc_week_live.html")}
        conn = store()
        s = ra.collect(conn, "ca", FakeClient(pages), "2025-11-10", days=14, regions=["qc"], log=quiet)
        self.assertEqual(s["read"], ["qc"])
        rows = [dict(r) for r in conn.execute("SELECT * FROM regional_agenda")]
        self.assertEqual(len([r for r in rows if r["item_type"] == ra.TBA]), 3)   # 11, 12, 13 Nov
        self.assertTrue(all(r["lang"] in (None, "taxonomy-qc.yaml+taxonomy.yaml") for r in rows))


class WesternProvincesTest(unittest.TestCase):
    def test_bc_calendar(self):
        days, note = ca.parse_bc_calendar(fx("bc_calendar.html.gz"))
        self.assertIn(("2026-05-28", "In Session"), days)
        self.assertFalse([d for d, _ in days if d > "2026-06-01"])
        self.assertIn("dissolved on September 22, 2026", note)
        self.assertTrue(any("Throne" in t for _, t in days))

    def test_ab_order_paper_and_committees(self):
        self.assertEqual(ca.ab_order_papers(fx("ab_order_papers.html"), "2026-10-16", "2026-12-11"),
                         [("2026-10-27", "https://docs.assembly.ab.ca/LADDAR_files/docs/houserecords/op/"
                                         "legislature_31/session_2/20261027_1200_01_op.pdf")])
        items = ca.parse_ab_order_paper(fx("ab_order_paper_2026-10-27.txt"), "2026-10-27")
        refs = [i["reference"] for i in items]
        self.assertEqual(refs[:6], ["Motion 29", "Motion 30", "Bill 205", "Bill 208", "Bill 212", "Bill 213"])
        self.assertEqual(items[2]["business"],
                         "Referred to the Standing Committee on Families and Communities: "
                         "Bill 205 Non-Disclosure Agreements Act")
        self.assertTrue(items[0]["business"].startswith("Government Motion 29: when further"))
        self.assertTrue(items[6]["business"].startswith("Motion 501: the Legislative Assembly"))
        self.assertFalse(any("WQ1" in (i["detail"] or "") for i in items))     # written questions left out
        cm = ca.parse_ab_committees(fx("ab_committees.html"))
        self.assertEqual(cm[2][:4], ("2026-10-27", "9 to 11:30 a.m.", "Standing Committee on Public Accounts",
                                     "Ministry Invited: Forestry and Parks"))
        self.assertEqual(cm[0][3], "")          # no business printed: to be announced

    def test_sk_days_and_orders(self):
        days = ca.parse_sk_days(json.loads(fx("sk_days.json")), "2026-10-16", "2026-12-11")
        self.assertEqual(min(days), "2026-10-27")
        self.assertEqual(days["2026-10-27"], 1)
        items = ca.parse_sk_orders(fx("sk_orders_2026-10-27.htm.gz"), "2026-10-27")
        self.assertEqual(items[0]["business"],
                         "First reading: Bill No. 627 – The Election (Fairness and Accountability) Amendment Act")
        self.assertEqual(items[1]["reference"], "Motion No. 2")
        self.assertTrue(items[1]["business"].startswith("Adjourned Debates: motion no. 2: That this Assembly"))
        self.assertEqual(items[2]["business"],
                         "Second Readings: Bill No. 607 – The Fransaskois Community Consultation Act")
        self.assertEqual(items[-2]["business"],
                         "Second Readings: Bill No. 629 – The Child and Family Services (Betty's Law) Amendment Act")
        self.assertEqual(len(items), 24)

    def test_sk_reader(self):
        pages = {ca.SK_DAYS: json.loads(fx("sk_days.json")),
                 ca.SK_DOCS.format("2026-10-16", "2026-12-11"): json.loads(fx("sk_docs.json")),
                 "https://docs.legassembly.sk.ca/legdocs/Assembly/Orders/30L2S/20261027Orders-HTML.htm":
                 fx("sk_orders_2026-10-27.htm.gz").encode("cp1252", "replace")}
        conn = store()
        s = ra.collect(conn, "ca", FakeClient(pages), "2026-10-16", days=56, regions=["sk"], log=quiet)
        self.assertEqual(s["read"], ["sk"])
        tba = conn.execute("SELECT dated FROM regional_agenda WHERE item_type=?", (ra.TBA,)).fetchall()
        self.assertEqual(len(tba), 24)                    # 25 sitting days less the 27th
        self.assertNotIn("2026-10-27", [r[0] for r in tba])

    def test_mb_papers(self):
        dated, orders = ca.parse_mb_order_paper(fx("mb_order_paper.txt"))
        self.assertEqual(dated, "2026-10-15")
        self.assertEqual(orders[0], ("Debate On Second Readings – Public Bills", "Bill", "207",
                                     "The Health System Governance and Accountability Amendment Act "
                                     "(Reporting When Timely Care Not Available)"))
        so = ca.parse_mb_sessional_order(fx("mb_sessional_order_2026.txt"))
        self.assertEqual([d for d, _b, _l in so],
                         ["2026-10-15", "2026-10-15", "2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29"])
        self.assertEqual(so[3][2], [("232", "The Autism Strategy Act")])
        cal = ca.parse_mb_notices_calendar(fx("mb_notices.html"))
        self.assertIn(("2026-10-16", "Social and Economic Development", "9:00 a.m",
                       "https://www.gov.mb.ca/legislature/committees/3rd_43rd/sed07.pdf"), cal)
        self.assertEqual(ca.parse_mb_notice(fx("mb_notice_sed07.txt")), [("232", "The Autism Strategy Act")])


class EasternAndNorthTest(unittest.TestCase):
    def test_nb_month(self):
        ev = ca.parse_nb_month(fx("nb_calendar_2026-10.html"))
        self.assertIn(("2026-10-20", "house", "Legislature 61-3 Daily Sitting 1", "1:00 PM",
                       "https://www.legnb.ca/en/calendar/events/673"), ev)
        self.assertEqual(ev[0][1:3], ("committee", "Standing Committee on Public Accounts"))

    def test_ns_feeds(self):
        cm = ca.parse_ns(fx("ns_committee.ics"), False)
        last = [i for i in cm if i["dated"] == "2026-10-20"][0]
        self.assertEqual(last["business"], "Building Homes for Veterans")
        self.assertEqual(last["body"], "Standing Committee on Veterans Affairs")
        self.assertEqual(last["item_time"], "1:00 PM")              # 16:00 UTC is 1 p.m. in Halifax
        self.assertNotIn("Paola", last["detail"] or "")             # witnesses' names not stored
        house = ca.parse_ns(fx("ns_house.ics"), True)
        self.assertTrue(all(i["business"] == "" for i in house))

    def test_nl_and_nt(self):
        items = ca.parse_numbered_paper(fx("nl_order_paper_26-09-17.txt"), "2026-09-17", ca.NL_BODY, "nl-op-")
        self.assertEqual(items[0]["business"], "Orders of the Day 1: Address in Reply.")
        self.assertTrue(items[1]["business"].startswith("Government Motions 1: this Honourable House endorse"))
        self.assertEqual(ca.nl_order_papers("", ca.NL_OPS + "ga51Session1/", fx("nl_session.html"),
                                            "2026-09-17", "2026-12-01"),
                         [("2026-09-17", ca.NL_OPS + "ga51Session1/26-09-17.pdf")])
        dated, orders = ca.parse_nt_orders(fx("nt_orders.txt"))
        self.assertEqual(dated, "2026-10-20")
        self.assertEqual([o["reference"] for o in orders],
                         ["Motion 81-20(1)", "Bill 3", "TD 445-20(1)", "TD 483-20(1)"])
        cm = ca.parse_nt_committees(fx("nt_committees.html"))
        self.assertEqual(cm[0][:4], ("2026-10-19", "10:30", "Social Development Committee",
                                     "Clause-by-Clause review of Bill 45 & 49"))

    def test_dead_host_keeps_rows(self):
        conn = store()
        pages = {ca.NS_ICAL.format("legislative-assembly"): fx("ns_house.ics"),
                 ca.NS_ICAL.format("committee"): fx("ns_committee.ics")}
        ra.collect(conn, "ca", FakeClient(pages), "2026-10-16", days=28, regions=["ns"], log=quiet)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM regional_agenda").fetchone()[0], 1)
        s = ra.collect(conn, "ca", FakeClient({}), "2026-10-17", days=28, regions=["ns", "pe", "nu"],
                       log=quiet)
        self.assertEqual(s["gap"], ["ns"])
        self.assertEqual(s["blocked"], ["pe"])
        self.assertEqual(s["no-route"], ["nu"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM regional_agenda").fetchone()[0], 1)
        gaps = [r[0] for r in conn.execute("SELECT detail FROM gaps WHERE feed='ca-regional-agenda'")]
        self.assertTrue(any("stored rows kept" in g for g in gaps))

    def test_every_region_declared(self):
        self.assertEqual(set(ca.REGIONS), {"on", "qc", "bc", "ab", "sk", "mb", "nb", "ns", "nl", "nt",
                                           "pe", "yt", "nu"})


if __name__ == "__main__":
    unittest.main()
