"""Austria's government consultations and publications reader
(src/gov_doc_sources/at.py) on fixtures captured live on 16 October 2026
(tests/fixtures/gov_docs/at/). The Begutachtung mirror reads country_petitions
rows as the pulled store held them (country_petitions_me.json, read 11 October
2026) plus one made-up draft on our ground, labelled as such."""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs as G, petitions  # noqa: E402
from src.gov_doc_sources import at  # noqa: E402
from tests.test_gov_docs_de import FakeClient  # noqa: E402

TODAY = "2026-10-16"
FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs", "at")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as h:
        return h.read()


def page_for(url_part):
    m = json.loads(fixture("manifest.json"))
    return fixture(next(v for k, v in m.items() if url_part in k))


MADE_UP = {"cc": "at", "item_id": "me:XXVIII/ME/999", "source": "me", "kind": "consultation",
           "title": "Fortpflanzungsmedizingesetz, Änderung (TEST ROW, not a real draft)",
           "status": "Begutachtung läuft", "opened": "2026-10-01", "closes": "2026-11-20",
           "body": "Bundesministerium für Justiz",
           "url": "https://www.parlament.gv.at/gegenstand/XXVIII/ME/999", "last_seen": "2026-10-11"}


def load_petitions(conn, extra=()):
    petitions.ensure_schema(conn)
    rows = json.loads(fixture("country_petitions_me.json")) + list(extra)
    for r in rows:
        cols = ",".join(r)
        conn.execute("INSERT OR REPLACE INTO country_petitions ({0}) VALUES ({1})".format(
            cols, ",".join("?" * len(r))), list(r.values()))
    conn.commit()


class ParserTests(unittest.TestCase):
    def test_draft_kind(self):
        self.assertEqual(at.draft_kind("Wehrdienstreformgesetz – WDRG"), "bill_draft")
        self.assertEqual(at.draft_kind("Verordnung der Bundesministerin für Gesundheit über X"),
                         "regulation_draft")

    def test_ministerrat_index_and_sittings(self):
        gov = at.parse_mr_index(fixture("bka_ministerraete.html"))
        self.assertEqual(gov, at.BKA + "/medien/ministerraete/ministerraete-seit-maerz-2025.html")
        s = at.parse_sittings(fixture("bka_ministerraete_regierung.html"))
        self.assertEqual(s[0]["label"], "66. Ministerrat am 14. Oktober 2026")
        self.assertEqual(s[0]["date"], "2026-10-14")

    def test_sitting_papers_leave_annexes_out(self):
        papers = at.parse_sitting(page_for("66-mr-14-okt"))
        nums = [p[0] for p in papers]
        self.assertIn("66/5", nums)
        self.assertTrue(all(not p[1].startswith(("Beilage", "Vorblatt", "Erläuterungen")) for p in papers))
        self.assertTrue(papers[0][2].endswith("_mrv.pdf"))
        self.assertFalse(papers[0][1].endswith("66/5"))

    def test_cards(self):
        cards = at.parse_cards(fixture("soz_news_2026.html"), at.SOZ)
        self.assertEqual(len(cards), 6)
        self.assertRegex(cards[0]["date"], r"^2026-10-\d\d$")
        self.assertTrue(cards[0]["url"].startswith(at.SOZ + "/Services/Aktuelles/"))

    def test_years_span_the_window(self):
        self.assertEqual(at._years("2026-10-16"), [2026])
        self.assertEqual(at._years("2027-01-20"), [2027, 2026])


class CollectTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))
        load_petitions(self.conn, [MADE_UP])
        self.client = FakeClient(FIX)
        self.listed, self.kept, self.gaps = G.collect(self.conn, "at", self.client, TODAY,
                                                      log=lambda *a: None)

    def row(self, doc_id):
        r = self.conn.execute("SELECT * FROM gov_docs WHERE cc='at' AND doc_id=?", (doc_id,)).fetchone()
        return dict(r) if r else None

    def test_counts(self):
        self.assertEqual(self.gaps, 0)
        self.assertEqual(self.kept, 3)
        listed = {r[0]: r[1] for r in self.conn.execute(
            "SELECT source, listed FROM gov_doc_runs WHERE cc='at'")}
        self.assertEqual(listed["me"], 12)

    def test_mirrored_draft_with_its_frist(self):
        r = self.row("me:XXVIII/ME/999")
        self.assertEqual(r["doc_type"], "bill_draft")
        self.assertEqual(r["closing_date"], "2026-11-20")
        self.assertEqual(r["body"], "Bundesministerium für Justiz")
        self.assertIn(10, json.loads(r["areas"]))
        got = G.deadline_rows(self.conn, "at", TODAY, "2027-12-31")
        self.assertEqual([d["doc_id"] for d in got], ["me:XXVIII/ME/999"])
        # the real drafts of 11 October are off our ground and not stored
        self.assertIsNone(self.row("me:XXVIII/ME/142"))

    def test_ministerrat_paper_and_news(self):
        r = self.row("mr:64/13")
        self.assertEqual(r["doc_type"], "publication")
        self.assertEqual(r["published"], "2026-09-30")
        self.assertEqual(r["body"], "Bundesregierung (Ministerrat)")
        self.assertIn(12, json.loads(r["areas"]))
        n = self.row("bka:2026-09/integrationsministerin-bauer-duerfen-beim-religionsunterricht-nicht-"
                     "auf-einem-auge-blind-sein")
        self.assertEqual(n["doc_type"], "press_release")
        self.assertEqual(n["tier"], 1)

    def test_mirror_gap_when_the_petitions_step_has_not_run(self):
        conn = db.init_db(db.connect(":memory:"))
        petitions.ensure_schema(conn)
        res = at.mirror_me(conn, "at", TODAY)
        self.assertEqual(res.entries, [])
        self.assertTrue(res.gaps)


if __name__ == "__main__":
    unittest.main()
