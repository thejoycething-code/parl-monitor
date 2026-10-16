"""Belgium's gov_docs reader (src/gov_doc_sources/be.py) on replies captured
live on 16 October 2026 (tests/fixtures/gov_docs/be/, scripts and images
stripped): the belgium.be news overview and one consultation's page, the
FPS Health news (two pages), the FPS Justice RSS and the IEFH news page."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs as G  # noqa: E402
from src.gov_doc_sources import be  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs", "be")
TODAY = "2026-10-16"


def text(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


class FakeClient:
    """Serves fixtures by URL substring (first match wins)."""

    def __init__(self, routes):
        self.routes = routes
        self.asked = []

    def get_text(self, url, feed, slug, **kw):
        self.asked.append(url)
        for key, value in self.routes:
            if key in url:
                return text(value)
        raise FetchError(url, "test", "x", 1, "no fixture")


ROUTES = [
    ("donnez_votre_avis_sur_le_projet_de_cinquieme_plan", "portal_item_pop.html"),
    ("belgium.be/fr/actualites/overview", "portal_overview.html"),
    ("health.belgium.be/fr/news?page=1", "health_news_1.html"),
    ("health.belgium.be/fr/news", "health_news_0.html"),
    ("justice.belgium.be/fr/news/rss", "justice_rss.xml"),
    ("igvm-iefh.belgium.be/fr/actualite", "iefh_actualite.html"),
]


class PortalTest(unittest.TestCase):
    def test_overview(self):
        got = be.parse_portal(text("portal_overview.html"))
        self.assertEqual(len(got), 10)
        kinds = {e["title"][:30]: e["doc_type"] for e in got}
        self.assertEqual(got[0]["doc_type"], "consultation")
        self.assertEqual(got[0]["published"], "2026-08-04")
        self.assertIn("consultation_outcome", kinds.values())
        self.assertIn("publication", kinds.values())

    def test_item_period_and_body(self):
        opened, closes, body, desc = be.parse_portal_item(text("portal_item_pop.html"))
        self.assertEqual((opened, closes), ("2026-08-17", "2026-10-15"))
        self.assertEqual(body, "SPF Santé publique, Sécurité de la chaîne alimentaire et Environnement")
        self.assertIn("polluants organiques persistants", desc)


class FeedsTest(unittest.TestCase):
    def test_health(self):
        got = be.parse_health(text("health_news_0.html"))
        self.assertEqual(len(got), 12)
        self.assertEqual(got[0]["doc_type"], "press_release")
        self.assertEqual(got[0]["body"], be.HEALTH_BODY)
        self.assertTrue(all(e["published"] for e in got))
        self.assertTrue(got[0]["url"].startswith(be.HEALTH + "/fr/actualites/"))

    def test_justice(self):
        got = be.parse_justice_rss(text("justice_rss.xml"))
        self.assertEqual(len(got), 10)
        self.assertEqual(got[0]["published"], "2026-10-14")
        self.assertTrue(got[0]["url"].startswith("https://justice.belgium.be/fr/"))

    def test_iefh(self):
        got = be.parse_iefh(text("iefh_actualite.html"))
        self.assertEqual(len(got), 15)
        self.assertEqual(len({e["doc_id"] for e in got}), 15)
        self.assertEqual(got[0]["doc_type"], "press_release")
        hate = [e for e in got if e["title"].startswith("Discours de haine, maternité")]
        self.assertEqual(hate[0]["published"], "2026-06-24")


class CollectTest(unittest.TestCase):
    def collect(self, window_days=G.WINDOW_DAYS):
        conn = db.init_db(db.connect(":memory:"))
        client = FakeClient(ROUTES)
        got = G.collect(conn, "be", client, TODAY, log=lambda *a: None, window_days=window_days)
        return conn, client, got

    def test_collect(self):
        conn, client, (listed, kept, gaps) = self.collect()
        self.assertEqual(gaps, 0)
        self.assertGreater(listed, 30)
        runs = {r[0]: r[1:] for r in conn.execute(
            "SELECT source, ok, listed, kept FROM gov_doc_runs WHERE cc='be'")}
        self.assertEqual(set(runs), {"portal", "health", "justice", "iefh"})
        self.assertTrue(all(r[0] == 1 for r in runs.values()))
        # only the one consultation announced in the window had its page read
        items = [u for u in client.asked if "/fr/actualites/20" in u]
        self.assertEqual(len(items), 1)
        # the POP consultation (closed 15 October) is environmental: not stored
        self.assertFalse(conn.execute("SELECT 1 FROM gov_docs WHERE source='portal'").fetchall())

    def test_collect_on_ground(self):
        # a wider window takes in the IEFH's 24 June release on hate speech
        conn, _client, (_listed, kept, _gaps) = self.collect(window_days=120)
        rows = [dict(r) for r in conn.execute("SELECT * FROM gov_docs WHERE cc='be'")]
        self.assertEqual(kept, len(rows))
        hate = [r for r in rows if r["title"].startswith("Discours de haine, maternité")]
        self.assertEqual(len(hate), 1)
        self.assertEqual(hate[0]["doc_type"], "press_release")
        self.assertEqual(hate[0]["tier"], 1)
        self.assertEqual(hate[0]["body"], be.IEFH_BODY)
        self.assertIn(7, G.loads(hate[0]["areas"]))


if __name__ == "__main__":
    unittest.main()
