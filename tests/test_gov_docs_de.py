"""Germany's government consultations and publications reader
(src/gov_doc_sources/de.py) on fixtures captured live on 16 October 2026
(tests/fixtures/gov_docs/de/, trimmed; manifest.json maps each URL to its file)."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs as G  # noqa: E402
from src.gov_doc_sources import de  # noqa: E402
from src.http import FetchError  # noqa: E402

TODAY = "2026-10-16"
FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs", "de")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as h:
        return h.read()


class FakeClient:
    """Serves the captured replies by URL; anything else is a FetchError."""

    def __init__(self, fix=FIX):
        self.fix = fix
        with open(os.path.join(fix, "manifest.json"), encoding="utf-8") as h:
            self.manifest = json.load(h)
        self.asked = []

    def get_text(self, url, feed, slug, **kw):
        self.asked.append(url)
        if url not in self.manifest:
            raise FetchError("no fixture for " + url)
        with open(os.path.join(self.fix, self.manifest[url]), encoding="utf-8") as h:
            return h.read()

    def get_json(self, url, feed, slug, **kw):
        return json.loads(self.get_text(url, feed, slug))


def page_for(url_part):
    m = json.loads(fixture("manifest.json"))
    return fixture(next(v for k, v in m.items() if url_part in k))


class ParserTests(unittest.TestCase):
    def test_rss_items(self):
        items = de.rss_items(fixture("bmj_gesetzgebung.xml"))
        self.assertEqual(len(items), 6)
        first = items[0]
        self.assertTrue(first["link"].startswith("https://www.bmjv.de/SharedDocs/Gesetzgebungsverfahren/"))
        self.assertRegex(first["published"], r"^2026-\d\d-\d\d$")
        self.assertNotIn("&#", first["title"])

    def test_rss_date_any_zone(self):
        self.assertEqual(de.rss_date("Mon, 12 Oct 2026 09:43:00 +0200"), "2026-10-12")
        self.assertEqual(de.rss_date("Thu, 15 Oct 2026 00:00:00 CET"), "2026-10-15")
        self.assertEqual(de.rss_date("2026-10-16"), "2026-10-16")

    def test_deadline_from_a_press_release(self):
        when, procs = de.parse_bmj_press(page_for("1012_Schoeffen"))
        self.assertEqual(when, "2026-11-06")
        self.assertEqual(procs, ["https://www.bmjv.de/SharedDocs/Gesetzgebungsverfahren/DE/"
                                 "2026_Aenderung_ehrenamtl_Richter_Ausbildung.html"])
        self.assertEqual(de.deadline("haben Gelegenheit, bis 6. November 2026 schriftlich Stellung "
                                     "zu nehmen"), "2026-11-06")
        self.assertIsNone(de.deadline("Das Gesetz tritt am 1. Januar 2027 in Kraft."))

    def test_procedure_page(self):
        d = de.parse_bmj_procedure(page_for("2026_Aenderung_ehrenamtl_Richter_Ausbildung"))
        self.assertEqual(d["status"], "Entwurf")
        self.assertEqual(d["stage"], "Referentenentwurf")
        self.assertEqual(d["published"], "2026-10-12")
        self.assertIn("Schöffenrecht", d["summary"])
        self.assertNotIn("Weitere Details", d["summary"])

    def test_regulation_or_law(self):
        self.assertTrue(de.is_regulation("Dritte Verordnung zur Änderung der Apothekenbetriebsordnung"))
        self.assertTrue(de.is_regulation("Verordnung zur elektronischen Aktenführung nach dem IRG-Gesetz"))
        self.assertFalse(de.is_regulation("Gesetz zur Änderung der Approbationsordnung und Verordnung"))
        self.assertEqual(de.draft_type("Gesetz zur Stärkung der nationalen Suizidprävention"), "bill_draft")

    def test_bmfsfj_law_listing(self):
        laws = de.parse_bmfsfj_laws(fixture("bmfsfj_gesetze.html"))
        self.assertEqual(len(laws), 3)
        self.assertEqual(laws[0]["tagline"], "Gesetzgebungsvorgang")
        self.assertTrue(laws[0]["url"].startswith(de.BMFSFJ + "/bmbfsfj/ministerium/gesetze/"))
        d = de.parse_bmfsfj_page(page_for("strukturreform-der-kinder-und-jugendhilfe"))
        self.assertEqual(d["published"], "2026-10-08")

    def test_bmg_listing_and_detail(self):
        laws = de.parse_bmg_laws(fixture("bmg_gesetze.html"))
        self.assertEqual(len(laws), 3)
        self.assertEqual(laws[0]["date"], "2026-10-14")
        d = de.parse_bmg_detail(page_for("detail/notfallreform"))
        self.assertEqual(d["category"], "Laufendes Verfahren")
        self.assertEqual(d["long_title"], "Gesetz zur Reform der Notfallversorgung")
        self.assertTrue(d["stage"].startswith("Bundestag, 2./3. Lesung"))
        e = de.bmg_law_entry(laws[0], d)
        self.assertEqual(e["doc_type"], "bill_draft")
        self.assertEqual(de.bmg_law_entry(laws[0], dict(d, category="Verordnung"))["doc_type"], "regulation")


class CollectTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))
        self.client = FakeClient()
        self.listed, self.kept, self.gaps = G.collect(self.conn, "de", self.client, TODAY,
                                                      log=lambda *a: None)

    def row(self, doc_id):
        r = self.conn.execute("SELECT * FROM gov_docs WHERE cc='de' AND doc_id=?", (doc_id,)).fetchone()
        return dict(r) if r else None

    def test_counts_and_no_gaps(self):
        self.assertEqual(self.gaps, 0)
        self.assertEqual(self.listed, 32)
        self.assertEqual(self.kept, 3)
        runs = {r[0]: r[1] for r in self.conn.execute(
            "SELECT source, ok FROM gov_doc_runs WHERE cc='de'")}
        self.assertEqual(runs, {"bmj": 1, "bmfsfj": 1, "bmg": 1, "breg": 1})

    def test_referentenentwurf_with_its_deadline(self):
        r = self.row("bmj:2026_Gewaltschutzgesetz")
        self.assertEqual(r["doc_type"], "bill_draft")
        self.assertEqual(r["closing_date"], "2026-10-30")
        self.assertEqual(r["status"], "Entwurf; Referentenentwurf")
        self.assertEqual(r["body"], de.BODY_BMJ)
        self.assertIn(5, json.loads(r["areas"]))

    def test_deadline_rows(self):
        got = G.deadline_rows(self.conn, "de", TODAY, "2027-12-31")
        self.assertEqual([r["doc_id"] for r in got], ["bmj:2026_Gewaltschutzgesetz"])

    def test_press_releases_need_tier_1(self):
        r = self.row("bmfsfj:291412")
        self.assertEqual(r["doc_type"], "press_release")
        self.assertEqual(r["tier"], 1)
        self.assertEqual(r["body"], de.BODY_BMFSFJ)
        # an off-ground draft is read but not stored
        self.assertIsNone(self.row("bmj:2026_Aenderung_ehrenamtl_Richter_Ausbildung"))

    def test_only_fixture_urls_were_asked(self):
        self.assertTrue(set(self.client.asked) <= set(self.client.manifest))


if __name__ == "__main__":
    unittest.main()
