"""Hungary's gov_docs reader (src/gov_doc_sources/hu.py): kormany.hu's draft
legislation (Jogszabálytervezetek) from the document-groups JSON its pages
load, captured live on 16 October 2026 (tests/fixtures/gov_docs/hu/, page 1
trimmed to 34 of 100 drafts, page 2 to 4 drafts published before the
window), and the Magyar Közlöny mirror over hu_gazette_entries rows."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs as G  # noqa: E402
from src.gov_doc_sources import hu  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs", "hu")
TODAY = "2026-10-16"
SLUG = "tarsadalmi-egyeztetes-a-gyermeket-nevelo-csaladok-otthonfelujitasi-tamogatasarol-szolo-518-2020-xi-25-korm-rendelet-modositasarol"


def js(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


class FakeClient:
    def __init__(self):
        self.asked = []

    def get_json(self, url, feed, slug, **kw):
        self.asked.append(url)
        for page in (1, 2):
            if url == hu.DRAFTS % page:
                return js("drafts_p{0}.json".format(page))
        raise FetchError(url, "test", slug, 1, "no fixture")


ISSUES = [("2026/140", 2026, 140, "2026-09-18", "https://magyarkozlony.hu/dokumentumok/aaa/megtekintes"),
          ("2026/100", 2026, 100, "2026-08-20", "https://magyarkozlony.hu/dokumentumok/bbb/megtekintes"),
          ("2026/60", 2026, 60, "2026-06-01", "https://magyarkozlony.hu/dokumentumok/ccc/megtekintes")]
ENTRIES = [
    ("151/2026. (IX. 18.) Korm. rendelet", "2026/140", "2026-09-18", 3, "gov_decree", "Korm.",
     "A bevett egyház és annak belső egyházi jogi személye által fenntartott köznevelési és "
     "szakképző intézményeket érintő 2026. évi egyszeri kiegészítő költségvetési támogatásról"),
    ("1/2026. (IX. 18.) VTM rendelet", "2026/140", "2026-09-18", 9, "ministerial_decree", "VTM",
     "A fejezeti kezelésű előirányzatok kezeléséről"),
    ("1300/2026. (IX. 18.) Korm. határozat", "2026/140", "2026-09-18", 12, "gov_resolution", "Korm.",
     "A családok támogatásáról"),
    ("Magyarország Alaptörvényének tizenhetedik módosítása (2026. július 13.)", "2026/100",
     "2026-08-20", 1, "fundamental_law", None, "Magyarország Alaptörvényének tizenhetedik módosítása"),
    ("2026. évi XX. törvény", "2026/60", "2026-06-01", 1, "act", None, "A házasság védelméről"),
]


def gazette_conn():
    conn = db.init_db(db.connect(":memory:"))
    conn.executemany("INSERT INTO hu_gazette_issues (issue_key, year, serial, date, url) VALUES (?,?,?,?,?)",
                     ISSUES)
    conn.executemany("INSERT INTO hu_gazette_entries (entry_key, issue_key, date, page, type, issuer, title) "
                     "VALUES (?,?,?,?,?,?,?)", ENTRIES)
    conn.commit()
    return conn


class DraftsTest(unittest.TestCase):
    def test_kind(self):
        self.assertEqual(hu.draft_kind(
            "Társadalmi egyeztetés a nemzeti köznevelésről szóló törvény végrehajtásáról szóló "
            "229/2012. (VIII. 28.) Korm. rendelet módosításáról", ""), "regulation_draft")
        self.assertEqual(hu.draft_kind(
            "Társadalmi egyeztetés egyes magánjogi nyilvántartásokat érintő törvények módosításáról", ""),
            "bill_draft")
        self.assertEqual(hu.draft_kind("Társadalmi egyeztetés az ügynökakták nyilvánosságra hozataláról",
                                       "A törvényjavaslat célja ..."), "bill_draft")
        self.assertEqual(hu.draft_kind("Társadalmi egyeztetés a Sportoló Nemzet Program kapcsán", ""),
                         "consultation")

    def test_parse(self):
        got, dates = hu.parse_drafts(js("drafts_p1.json"))
        self.assertEqual(len(got), len(dates))
        e = {x["doc_id"]: x for x in got}["te:" + SLUG]
        self.assertEqual(e["doc_type"], "regulation_draft")
        self.assertEqual((e["published"], e["closing_date"]), ("2026-10-12", "2026-10-20"))
        self.assertEqual(e["body"], "Vidék- és Településfejlesztési Minisztérium")
        self.assertEqual(e["url"], "https://kormany.hu/dokumentumtar/" + SLUG)
        self.assertTrue(e["summary"])
        self.assertNotIn("<p>", e["summary"])

    def test_fetch_stops_after_window(self):
        client = FakeClient()
        got = hu.fetch_tarsadalmi_egyeztetes(client, TODAY, log=lambda *a: None)
        self.assertEqual(client.asked, [hu.DRAFTS % 1, hu.DRAFTS % 2])
        self.assertEqual(got.gaps, [])
        self.assertEqual(len(got.entries), 38)


class MirrorTest(unittest.TestCase):
    def test_mirror(self):
        got = hu.mirror_gazette(gazette_conn(), "hu", TODAY)
        ids = {e["doc_id"]: e for e in got.entries}
        self.assertEqual(set(ids), {"mk:151/2026. (IX. 18.) Korm. rendelet",
                                    "mk:1/2026. (IX. 18.) VTM rendelet",
                                    "mk:Magyarország Alaptörvényének tizenhetedik módosítása (2026. július 13.)"})
        e = ids["mk:151/2026. (IX. 18.) Korm. rendelet"]
        self.assertEqual((e["doc_type"], e["body"], e["published"]), ("regulation", "Kormány", "2026-09-18"))
        self.assertEqual(e["url"], "https://magyarkozlony.hu/dokumentumok/aaa/megtekintes")
        alt = ids["mk:Magyarország Alaptörvényének tizenhetedik módosítása (2026. július 13.)"]
        self.assertEqual((alt["doc_type"], alt["body"]), ("law", "Országgyűlés"))
        self.assertIn("HU4", alt["refs"])

    def test_empty_table_is_a_gap(self):
        got = hu.mirror_gazette(db.init_db(db.connect(":memory:")), "hu", TODAY)
        self.assertEqual(got.entries, [])
        self.assertTrue(got.gaps)


class CollectTest(unittest.TestCase):
    def test_collect(self):
        conn = gazette_conn()
        listed, kept, gaps = G.collect(conn, "hu", FakeClient(), TODAY, log=lambda *a: None)
        self.assertEqual(gaps, 0)
        rows = {r["doc_id"]: dict(r) for r in conn.execute("SELECT * FROM gov_docs WHERE cc='hu'")}
        self.assertIn("te:" + SLUG, rows)
        self.assertEqual(rows["te:" + SLUG]["closing_date"], "2026-10-20")
        bill = rows["te:tarsadalmi-egyeztetes-egyes-maganjogi-nyilvantartasokat-erinto-torvenyek-modositasarol"]
        self.assertEqual(bill["doc_type"], "bill_draft")
        # the gazette: the church-schools decree on our ground (tier 1), the
        # Fundamental Law amendment watched through HU4, the plain VTM decree not
        self.assertIn("mk:151/2026. (IX. 18.) Korm. rendelet", rows)
        alt = rows["mk:Magyarország Alaptörvényének tizenhetedik módosítása (2026. július 13.)"]
        self.assertIn("HU4", json.loads(alt["watch_keys"]))
        self.assertNotIn("mk:1/2026. (IX. 18.) VTM rendelet", rows)
        dl = G.deadline_rows(conn, "hu", TODAY, "2027-10-16")
        self.assertTrue(dl and all(r["closing_date"] >= TODAY for r in dl))
        self.assertTrue(all(r["doc_type"] in G.DEADLINE_TYPES for r in dl))


if __name__ == "__main__":
    unittest.main()
