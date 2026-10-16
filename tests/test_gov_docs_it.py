"""Italy's gov_docs reader (src/gov_doc_sources/it.py): the Gazzetta
Ufficiale's Serie Generale (fixtures captured live on 16 October 2026) and
the ParteciPa mirror of country_petitions."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs as G  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.gov_doc_sources import it  # noqa: E402

TODAY = "2026-10-16"
FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs", "it")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


PAGES = {
    it.GU_30: "gu-30giorni.html",
    it.GU_ISSUE.format("2026-10-15", "240"): "gu-sg-2026-10-15-240.html",
}


class FakeClient:
    """Serves the 30-day list and issue 240; older issues answer 404."""

    def get_text(self, url, feed, slug, *args, **kwargs):
        if url in PAGES:
            return fixture(PAGES[url])
        raise FetchError(url, feed, slug, 1, Exception("HTTP Error 404: Not Found"))


def store():
    conn = db.init_db(db.connect(":memory:"))
    conn.execute(
        "INSERT INTO country_petitions (cc, item_id, source, kind, title, summary, status, opened, "
        "closes, body, url, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("it", "partecipa:linee-guida-educazione-affettivita", "partecipa", "consultation",
         "Linee guida per l'educazione sessuale e all'affettività nelle scuole",
         "Consultazione pubblica del Ministero dell'Istruzione e del Merito", "aperta",
         "2026-10-01", "2026-11-15", "Governo (ParteciPa)",
         "https://partecipa.gov.it/processes/linee-guida-educazione-affettivita", TODAY, TODAY))
    conn.execute(
        "INSERT INTO country_petitions (cc, item_id, source, kind, title, opened, closes, body, "
        "url, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("it", "partecipa:recepimento-direttiva-qualita-aria", "partecipa", "consultation",
         "Decreto di recepimento della nuova direttiva sulla qualità dell'aria (UE) 2024/2881",
         "2026-10-02", "2026-10-20", "Governo (ParteciPa)",
         "https://partecipa.gov.it/processes/recepimento-direttiva-qualita-aria", TODAY, TODAY))
    conn.commit()
    return conn


class GazzettaTests(unittest.TestCase):
    def test_issue_list(self):
        issues = it.parse_issue_list(fixture("gu-30giorni.html"))
        self.assertEqual(issues[0], ("2026-10-15", "240"))
        self.assertEqual(len(issues), 25)
        self.assertEqual(len(set(issues)), len(issues))

    def test_issue(self):
        got = it.parse_issue(fixture("gu-sg-2026-10-15-240.html"), "2026-10-15")
        self.assertEqual(len(got), 12)
        dl = got[0]
        self.assertEqual(dl["doc_id"], "gu:26G00202")
        self.assertEqual(dl["doc_type"], "law")
        self.assertTrue(dl["title"].startswith("DECRETO LEGISLATIVO 25 settembre 2026, n. 184: Recepimento"))
        self.assertEqual(dl["body"], "Governo (Consiglio dei Ministri)")
        self.assertEqual(dl["url"], "https://www.gazzettaufficiale.it/eli/id/2026/10/15/26G00202/sg")
        self.assertNotIn("26G00202", dl["summary"])
        dpcm = got[1]
        self.assertEqual((dpcm["doc_type"], dpcm["body"]),
                         ("regulation", "Presidenza del Consiglio dei Ministri"))
        self.assertTrue(any(e["body"] == "Ministero dell'Economia e delle Finanze" for e in got))
        # ESTRATTI, SUNTI E COMUNICATI are notices, not read
        self.assertFalse(any("Comunicati" in (e["status"] or "") for e in got))


class FailLoudTests(unittest.TestCase):
    def test_an_unreadable_issue_is_a_gap(self):
        got = it.fetch_gu(FakeClient(), TODAY)
        self.assertEqual(len(got.entries), 12)
        self.assertEqual(len(got.gaps), 24)              # the 24 older issues answered 404


class CollectTests(unittest.TestCase):
    def test_collect(self):
        conn = store()
        keep, it.GU_ISSUES_MAX = it.GU_ISSUES_MAX, 1        # the newest issue only
        try:
            listed, kept, gaps = G.collect(conn, "it", FakeClient(), TODAY, log=lambda *a: None)
        finally:
            it.GU_ISSUES_MAX = keep
        # 12 acts from issue 240, and the mirror's 2 consultations
        self.assertEqual(listed, 14)
        self.assertEqual(gaps, 0)
        rows = {r["doc_id"]: dict(r) for r in conn.execute("SELECT * FROM gov_docs WHERE cc='it'")}
        self.assertEqual(kept, len(rows))
        sex_ed = rows["partecipa:linee-guida-educazione-affettivita"]
        self.assertEqual(sex_ed["doc_type"], "consultation")
        self.assertEqual(sex_ed["closing_date"], "2026-11-15")
        self.assertTrue(json.loads(sex_ed["areas"]))
        self.assertNotIn("partecipa:recepimento-direttiva-qualita-aria", rows)   # not our ground
        due = G.deadline_rows(conn, "it", TODAY, "2026-12-31")
        self.assertEqual([d["doc_id"] for d in due], ["partecipa:linee-guida-educazione-affettivita"])

    def test_mirror_without_rows_is_quiet(self):
        conn = db.init_db(db.connect(":memory:"))
        got = it.mirror_partecipa(conn, "it", TODAY)
        self.assertEqual((got.entries, got.gaps), ([], []))


if __name__ == "__main__":
    unittest.main()
