"""France's gov_docs reader (src/gov_doc_sources/fr.py) on replies captured
live on 16 October 2026 (tests/fixtures/gov_docs/fr/): the DILA JORF index
and one increment (trimmed to four sommaires), the environment ministry's
consultations listing, the social affairs ministries' RSS."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs as G  # noqa: E402
from src.gov_doc_sources import fr  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs", "fr")
TODAY = "2026-10-16"
TAR = "JORF_20261016-002645.tar.gz"


def text(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def blob(name):
    with open(os.path.join(FIX, name), "rb") as fh:
        return fh.read()


class FakeClient:
    """Serves fixtures by URL substring (first match wins)."""

    def __init__(self, routes):
        self.routes = routes
        self.asked = []

    def _find(self, url):
        self.asked.append(url)
        for key, value in self.routes:
            if key in url:
                return value
        raise FetchError(url, "test", "x", 1, "no fixture")

    def get_text(self, url, feed, slug, **kw):
        return text(self._find(url))

    def get_bytes(self, url, feed, slug, **kw):
        return blob(self._find(url))


ROUTES = [
    ("OPENDATA/JORF/JORF_", TAR),
    ("OPENDATA/JORF/", "jorf_index.html"),
    ("debut_listearticles=", "dd_list_stale.html"),
    ("liste-consultations", "dd_list_0.html"),
    ("solidarites.gouv.fr/rss.xml", "solidarites_rss.xml"),
]


class JorfTest(unittest.TestCase):
    def test_index_keeps_recent_small_increments(self):
        files = fr.parse_index(text("jorf_index.html"), TODAY)
        self.assertEqual(files, [(TAR, "2026-10-16")])   # the 4.8M evening one and 1 Sept are out

    def test_sommaires(self):
        xmls = fr.containers_from_tar(blob(TAR))
        self.assertEqual(len(xmls), 4)
        got = [e for raw in xmls for e in fr.parse_container(raw, G.window_start(TODAY))]
        by_id = {e["doc_id"]: e for e in got}
        # 16 October: arrêtés under their ministry, the nominations left out
        self.assertTrue(all(e["published"] for e in got))
        law = [e for e in got if e["doc_type"] == "law"]
        self.assertEqual(len(law), 1)
        self.assertTrue(law[0]["title"].startswith("LOI n° 2026-668 du 27 juillet 2026"))
        self.assertEqual(law[0]["published"], "2026-08-01")
        cncdh = [e for e in got if e["doc_type"] == "publication"]
        self.assertEqual(len(cncdh), 4)
        self.assertEqual(cncdh[0]["body"], "Commission nationale consultative des droits de l'homme")
        reg = [e for e in got if e["published"] == "2026-10-16"]
        self.assertEqual(len(reg), 32)
        self.assertTrue(all(e["doc_type"] == "regulation" for e in reg))
        self.assertIn("Ministère de la santé, des familles, de l'autonomie et des personnes handicapées",
                      {e["body"] for e in reg})
        self.assertFalse(any("délégation de signature" in e["title"] for e in reg))
        self.assertTrue(all(e["url"].startswith(fr.LEGIFRANCE + "JORFTEXT") for e in by_id.values()))
        # the 1 July issue is before the window
        self.assertFalse(any(e["published"] < "2026-07-16" for e in got))


class ConsultationsTest(unittest.TestCase):
    def test_listing(self):
        got = fr.parse_dd(text("dd_list_0.html"))
        self.assertGreaterEqual(len(got), 10)
        first = got[0]
        self.assertEqual(first["doc_id"], "dd:3464")
        self.assertEqual(first["doc_type"], "regulation_draft")
        self.assertEqual((first["published"], first["closing_date"]), ("2026-10-16", "2026-11-06"))
        self.assertEqual(first["body"], fr.DD_BODY)
        self.assertIn("Consultation en cours", first["status"])

    def test_kinds(self):
        self.assertEqual(fr.dd_kind("Projet d’arrêté modifiant ..."), "regulation_draft")
        self.assertEqual(fr.dd_kind("Projet d'ordonnance relative ..."), "bill_draft")
        self.assertEqual(fr.dd_kind("Synthèse des observations du public sur le décret ..."),
                         "consultation_outcome")
        self.assertEqual(fr.dd_kind("Méthode Label bas carbone"), "consultation")


class SolidaritesTest(unittest.TestCase):
    def test_rss(self):
        got = fr.parse_rss(text("solidarites_rss.xml"), "solidarites", fr.SOL_BODY)
        self.assertGreaterEqual(len(got), 11)
        sex = [e for e in got if "sextorsion" in e["title"].lower()]
        self.assertTrue(sex)
        self.assertEqual(sex[0]["doc_type"], "press_release")
        self.assertTrue(sex[0]["published"].startswith("2026-"))


class CollectTest(unittest.TestCase):
    def test_collect(self):
        conn = db.init_db(db.connect(":memory:"))
        client = FakeClient(ROUTES)
        listed, kept, gaps = G.collect(conn, "fr", client, TODAY, log=lambda *a: None)
        self.assertEqual(gaps, 0)
        self.assertGreater(listed, 60)
        rows = [dict(r) for r in conn.execute("SELECT * FROM gov_docs WHERE cc='fr'")]
        self.assertEqual(kept, len(rows))
        sex = [r for r in rows if r["doc_id"] == "solidarites:lutte-contre-la-sextorsion"]
        self.assertEqual(len(sex), 1)
        self.assertEqual(sex[0]["doc_type"], "press_release")
        self.assertEqual(sex[0]["tier"], 1)
        self.assertEqual(sex[0]["body"], fr.SOL_BODY)
        # arrêtés on concours and the environment ministry's consultations are off our ground
        self.assertFalse([r for r in rows if r["source"] in ("jorf", "dd")])
        runs = {r[0]: r[1:] for r in conn.execute(
            "SELECT source, ok, listed, kept FROM gov_doc_runs WHERE cc='fr'")}
        self.assertEqual(set(runs), {"jorf", "dd", "solidarites"})
        self.assertTrue(all(r[0] == 1 for r in runs.values()))
        self.assertGreater(runs["jorf"][1], 30)
        self.assertGreater(runs["dd"][1], 10)
        # the open consultations have their closing dates in the run (stored only on our ground)
        dd = fr.parse_dd(text("dd_list_0.html"))
        self.assertTrue(all(e["closing_date"] for e in dd if e["doc_type"] != "consultation_outcome"
                            and "en cours" in (e["status"] or "")))
        # two stale pages in a row end the listing
        self.assertTrue(any("debut_listearticles=11" in u for u in client.asked))
        self.assertFalse(any("debut_listearticles=33" in u for u in client.asked))


if __name__ == "__main__":
    unittest.main()
