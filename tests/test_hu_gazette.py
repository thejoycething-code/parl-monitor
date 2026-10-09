"""Hungary phase 0: the Magyar Közlöny collector (tools/hu_gazette.py,
src/hu_store.py) and the Hungarian edition (src/editions/hu.py).

Fixtures under tests/fixtures/hu/ are real responses saved on 9 October 2026:
the RSS feed trimmed to four items (three Magyar Közlöny issues and one
Hivatalos Értesítő), page 12 of the front-page listing (early June 2026) and
the whole of Magyar Közlöny No. 92 of 2026, which promulgated the seventeenth
amendment to the Fundamental Law. No network."""
import gzip
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import hu_gazette as hg  # noqa: E402
from src import country_edition as ce, db, hu_store, sv_pdf  # noqa: E402
from src.editions import hu  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "hu")
AMENDMENT = "Magyarország Alaptörvényének tizenhetedik módosítása (2026. július 13.)"


def fixture(name):
    with open(os.path.join(FIX, name), "rb") as fh:
        data = fh.read()
    return gzip.decompress(data) if name.endswith(".gz") else data


class FakeClient:
    """Serves the feed and one PDF for every issue; records what was asked."""

    def __init__(self, feed=None, listing=None, pdf=None):
        self.feed = feed if feed is not None else fixture("feed.xml").decode("utf-8")
        self.listing = listing
        self.pdf = pdf if pdf is not None else fixture("mk-2026-092.pdf.gz")
        self.asked = []

    def get_text(self, url, feed, slug, **kw):
        self.asked.append(url)
        if url.endswith("/feed"):
            return self.feed
        return self.listing or ""

    def get_bytes(self, url, feed, slug, **kw):
        self.asked.append(url)
        return self.pdf


class FeedAndListing(unittest.TestCase):
    def test_feed_keeps_magyar_kozlony_issues_only(self):
        got = hg.parse_feed(fixture("feed.xml").decode("utf-8"))
        self.assertEqual([(i["year"], i["serial"]) for i in got],
                         [(2026, 151), (2026, 150), (2026, 149)])
        self.assertEqual(got[0]["date"], "2026-10-09")
        self.assertTrue(got[0]["pdf_url"].startswith("https://magyarkozlony.hu/hivatalos-lapok/"))
        self.assertTrue(got[0]["pdf_url"].endswith("/letoltes"))

    def test_listing_rows(self):
        got = hg.parse_listing(fixture("listing-p12.html.gz").decode("utf-8"))
        serials = [i["serial"] for i in got]
        self.assertIn(64, serials)
        self.assertIn(62, serials)
        row = next(i for i in got if i["serial"] == 62)
        self.assertEqual(row["date"], "2026-06-01")
        self.assertTrue(row["pdf_url"].endswith("/letoltes"))
        self.assertEqual(len(serials), len(set(serials)))


class ContentsPage(unittest.TestCase):
    def test_real_issue_with_an_amendment(self):
        entries = hg.contents_entries(sv_pdf.pdf_lines(fixture("mk-2026-092.pdf.gz"), max_pages=8))
        self.assertEqual(entries, [(AMENDMENT, AMENDMENT, 3414)])
        self.assertEqual(hu_store.classify_designation(AMENDMENT)[0], "fundamental_law")

    def test_layouts_measured_across_the_term(self):
        lines = [
            "MAGYAR KÖZLÖNY\t45. szám", "MAGYARORSZÁG HIVATALOS LAPJA", "2026. május 12., kedd",
            # the title's first letter lands left of the tab
            "76/2026. (V. 12.) KE határozat M\tiniszterek kinevezéséről\t2596",
            "109/2026. (VII. 17.) Korm. rendelet A\t honvédek jogállásáról szóló rendelet módosításáról\t3371",
            # a wrapped title line citing another designation is not an entry
            "10/2026. (X. 8.) HM rendelet\tA hivatásos és a szerződéses katonai szolgálatra való egészségi,",
            "keretszabályairól szóló 9/2024. (VI. 28.) HM rendelet módosításáról\t5009",
            # no tab before the page number
            "10/2026. (IX. 29.) MEKH rendelet A\t B3 alkategóriájú hulladéklerakóban",
            "módosításáról 4758",
            "2026. évi LVI. törvény\tEgyes törvényeknek a javítóintézetek gyermekvédelmi rendszerbe",
            "történő visszaintegrálásával összefüggő módosításáról\t4776",
            "Magyarország Alaptörvénye", "(egységes szerkezetben) 4872",
        ]
        got = hg.contents_entries([lines, ["4756\tMAGYAR KÖZLÖNY • 2026. évi 141. szám", "noise"]])
        self.assertEqual(got[0], ("76/2026. (V. 12.) KE határozat", "Miniszterek kinevezéséről", 2596))
        self.assertEqual(got[1][1], "A honvédek jogállásáról szóló rendelet módosításáról")
        self.assertEqual(got[2][0], "10/2026. (X. 8.) HM rendelet")
        self.assertTrue(got[2][1].endswith("HM rendelet módosításáról"))
        self.assertEqual(got[2][2], 5009)
        self.assertEqual(got[3][2], 4758)
        self.assertEqual(got[4][0], "2026. évi LVI. törvény")
        self.assertEqual(got[5], (hg.CONSOLIDATED, hg.CONSOLIDATED, 4872))
        self.assertEqual(len(got), 6)

    def test_designations(self):
        self.assertEqual(hu_store.classify_designation("2026. évi LVI. törvény"),
                         ("act", "LVI/2026", None))
        self.assertEqual(hu_store.classify_designation("22/2026. (V. 27.) OGY határozat")[0],
                         "ogy_resolution")
        self.assertEqual(hu_store.classify_designation("225/2026. (X. 6.) Korm. rendelet")[0],
                         "gov_decree")
        self.assertEqual(hu_store.classify_designation("1324/2026. (X. 8.) Korm. határozat")[0],
                         "gov_resolution")
        self.assertEqual(hu_store.classify_designation("25/2026. (X. 8.) BM rendelet"),
                         ("ministerial_decree", "25/2026", "BM"))
        self.assertEqual(hu_store.classify_designation("8/2026. (X. 8.) AB határozat")[0],
                         "ab_decision")
        self.assertEqual(hu_store.classify_designation("252/2026. (X. 8.) KE határozat")[0],
                         "ke_decision")
        self.assertEqual(hu_store.roman("LVI"), 56)


class Classification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tax = hg.load_taxonomy()

    def test_hu4_whatever_its_words(self):
        areas, terms, tier, rule, watched = hg.classify(self.tax, {}, AMENDMENT, AMENDMENT,
                                                        "fundamental_law")
        self.assertEqual((areas, rule), ([], "HU4"))

    def test_accents_fold(self):
        areas, terms, *_ = hg.classify(self.tax, {}, "x", "A SZUVERENITASVEDELMI HIVATAL "
                                       "megszuntetéséről".lower(), "act")
        self.assertIn(7, areas)

    def test_valas_is_not_valasztas(self):
        title = ("Bírósági ülnökök soron kívüli választása időpontjának kitűzéséről")
        self.assertEqual(hg.classify(self.tax, {}, "x", title, "ke_decision")[0], [])
        areas, terms, *_ = hg.classify(self.tax, {}, "x", "A válás utáni kapcsolattartásról", "act")
        self.assertIn(9, areas)

    def test_designation_alone_files_nothing(self):
        self.assertEqual(hg.classify(self.tax, {}, "7/2026. (V. 26.) NMHH rendelet",
                                     "A díjakról", "ministerial_decree")[0], [])

    def test_watchlist_by_key(self):
        wl = {"2026. évi XX. törvény": {"areas": [7], "why": "x"}}
        areas, _, tier, _, watched = hg.classify(self.tax, wl, "2026. évi XX. törvény",
                                                 "Egy semleges cím", "act")
        self.assertEqual((areas, watched, tier), ([7], True, 2))

    def test_the_seed_watchlist_parses(self):
        wl = hu_store.watchlist()
        self.assertIn(AMENDMENT, wl)
        self.assertIn("T/324", wl)


class Collecting(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        db.init_db(self.conn)
        self.tax = hg.load_taxonomy()

    def test_reads_new_issues_once(self):
        client = FakeClient()
        s = hg.collect(self.conn, client, "2026-10-09", "2026-10-09", self.tax, {})
        self.assertEqual((s["issues"], s["gaps"]), (3, 0))
        self.assertEqual(sum(u.endswith("/letoltes") for u in client.asked), 3)
        row = self.conn.execute("SELECT type, rule, page FROM hu_gazette_entries").fetchone()
        self.assertEqual(tuple(row), ("fundamental_law", "HU4", 3414))
        again = FakeClient()
        s = hg.collect(self.conn, again, "2026-10-09", "2026-10-09", self.tax, {})
        self.assertEqual(s["issues"], 0)
        self.assertEqual(again.asked, ["https://magyarkozlony.hu/feed"])

    def test_walks_the_listing_back_when_the_feed_does_not_reach(self):
        client = FakeClient(listing=fixture("listing-p12.html.gz").decode("utf-8"))
        hg.candidates(client, "2026-06-02", set())
        self.assertIn("https://magyarkozlony.hu?page=1", client.asked)

    def test_an_unreadable_pdf_is_a_gap(self):
        s = hg.collect(self.conn, FakeClient(pdf=b"%PDF-1.4 nothing"), "2026-10-09",
                       "2026-10-09", self.tax, {})
        self.assertEqual(s["gaps"], 3)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM hu_gazette_issues WHERE "
                                           "contents_ok=0").fetchone()[0], 3)

    def test_tables_are_declared(self):
        for t in hu_store.TABLES:
            self.assertIn(t, db.TABLES)


def edition_store():
    conn = sqlite3.connect(":memory:")
    hu_store.ensure_schema(conn)
    conn.execute("INSERT INTO hu_gazette_issues (issue_key, year, serial, date, url, pdf_url, "
                 "contents_ok) VALUES ('2026/92', 2026, 92, '2026-10-06', 'https://x/92', 'p', 1)")
    rows = [
        (AMENDMENT, "fundamental_law", None, None, AMENDMENT, "[]", "[]", None, "HU4"),
        ("2026. évi LVI. törvény", "act", "LVI/2026", None,
         "Egyes törvényeknek a javítóintézetek gyermekvédelmi rendszerbe történő "
         "visszaintegrálásával összefüggő módosításáról", "[6]", '["gyermekvédel*"]', 2, None),
        ("255/2026. (X. 6.) KE határozat", "ke_decision", "255/2026", "KE",
         "A Médiatanács tagjának kinevezéséről", "[7]", '["Médiatanács*"]', 2, None),
        ("7/2026. (X. 6.) NMHH rendelet", "ministerial_decree", "7/2026", "NMHH",
         "A frekvencialekötés díjáról szóló NMHH rendelet módosításáról", "[7]", '["NMHH"]', 2,
         None),
        ("234/2026. (X. 6.) Korm. rendelet", "gov_decree", "234/2026", "Korm.",
         "A menedékjogról szóló törvény végrehajtásáról", "[11]", '["menedékjog*"]', 1, None),
        ("8/2026. (X. 6.) AB határozat", "ab_decision", "8/2026", "AB",
         "A gyülekezési jogról szóló törvény alaptörvény-ellenességének megállapításáról és "
         "megsemmisítéséről", "[7]", '["gyülekezési jog*"]', 1, None),
    ]
    for key, kind, number, issuer, title, areas, terms, tier, rule in rows:
        conn.execute("INSERT INTO hu_gazette_entries (entry_key, issue_key, date, page, type, "
                     "number, issuer, title, areas, matched_terms, tier, rule, watched, "
                     "last_seen) VALUES (?, '2026/92', '2026-10-06', 3414, ?, ?, ?, ?, ?, ?, ?, "
                     "?, 0, '2026-10-07')",
                     (key, kind, number, issuer, title, areas, terms, tier, rule))
    conn.commit()
    return conn


class HungaryEdition(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = edition_store()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def render(self):
        return ce.render(self.conn, hu.COUNTRY, "2026-10-07", "2026-09-30", directory=self.tmp)

    def test_laws_and_notices_with_english_takeaways(self):
        text = self.render()
        self.assertIn("## Laws", text)
        self.assertIn("## Gazette notices", text)
        self.assertIn("Act LVI of 2026 (Act 56), published in Magyar Közlöny No. 92 of "
                      "6 October 2026, page 3414. By its title: it amends existing law.", text)
        self.assertIn("Constitutional Court decision 8/2026", text)
        self.assertIn("it finds a provision or ruling contrary to the Fundamental Law and "
                      "annuls it", text)
        self.assertIn("*Egyes törvényeknek a javítóintézetek", text)     # verbatim Hungarian

    def test_hu4_amendment_is_shown_and_watched(self):
        text = self.render()
        self.assertIn("*" + AMENDMENT + "*", text)
        self.assertIn("**watched**", text)
        self.assertIn("seventeenth amendment to the Fundamental Law (paper T/324)", text)

    def test_appointments_noise_and_migration_left_out(self):
        text = self.render()
        self.assertNotIn("KE határozat", text)
        self.assertNotIn("frekvencia", text)
        self.assertIn("1 excluded title", text)
        self.assertNotIn("menedékjog", text)

    def test_standing_line_in_the_edition_the_quiet_week_and_the_dm(self):
        self.assertIn("await the Országgyűlés's API token (HU1)", self.render())
        quiet = ce.render(self.conn, hu.COUNTRY, "2026-12-01", "2026-11-24", directory=self.tmp)
        self.assertIn("A quiet week", quiet)
        self.assertIn("await the Országgyűlés's API token (HU1)", quiet)
        dm = ce.dm_summary(self.conn, hu.COUNTRY, "2026-10-07", "2026-09-30", directory=self.tmp)
        self.assertIn("API token (HU1)", dm)

    def test_no_em_dashes(self):
        self.assertNotIn("—", self.render())


if __name__ == "__main__":
    unittest.main()
