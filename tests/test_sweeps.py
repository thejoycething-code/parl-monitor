"""PQ/EDM weekly sweep tests: gaps on failure, taxonomy filtering, signatures."""

import datetime
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import run_weekly
from src import db, filter as filt
from src.http import FetchError
from src.ingest import edms, pqs

WEEK = datetime.date(2026, 8, 3)
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))


def pq(id, heading, answered, tabled="2026-07-20", text=""):
    return pqs.WrittenQuestion(
        id=id, uin="HL%d" % id, heading=heading, question_text=text, answer_text="",
        asking_member_id=1, answering_body="X",
        date_tabled=datetime.date.fromisoformat(tabled),
        date_answered=datetime.date.fromisoformat(answered), house="Lords")


def edm(id, title, tabled, sigs=5):
    return edms.EDM(id=id, uin=str(id), title=title, motion_text="",
                    sponsor_name="A Member", sponsor_constituency="Someseat",
                    signature_count=sigs, date_tabled=datetime.date.fromisoformat(tabled))


class PqSweepTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))

    def tearDown(self):
        self.conn.close()

    def test_failed_term_lands_in_gaps_not_silently_dropped(self):
        def flaky(client, term):
            raise FetchError("u", "pq", term, 4, TimeoutError("slow"))

        with mock.patch.object(pqs, "fetch_questions", side_effect=flaky):
            run_weekly.sweep_pqs(None, self.conn, TAX, WL, WEEK, "2026-08-03", ["Cass Review"])
        gap = self.conn.execute("SELECT feed, detail FROM gaps").fetchone()
        self.assertEqual(gap["feed"], "pq")
        self.assertIn("Cass Review", gap["detail"])
        self.assertIn("4 attempts", gap["detail"])

    def test_loose_matches_filtered_and_relevant_stored_with_deep_link_fields(self):
        results = [
            pq(1, "British Steel: Jingye Group", "2026-08-01"),      # loose noise
            pq(2, "Abortion: safe access zones", "2026-08-01"),      # relevant
            pq(3, "Hospices: funding", "2026-05-01"),                # relevant but stale
        ]
        with mock.patch.object(pqs, "fetch_questions", return_value=results):
            run_weekly.sweep_pqs(None, self.conn, TAX, WL, WEEK, "2026-08-03", ["safe access zones"])
        rows = self.conn.execute("SELECT id, date_tabled, url FROM items").fetchall()
        self.assertEqual([r["id"] for r in rows], ["pq:2"])
        self.assertEqual(rows[0]["date_tabled"], "2026-07-20")  # deep-link prerequisite
        self.assertIn("/written-questions/detail/2026-07-20/HL2", rows[0]["url"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0], 0)


class EdmSweepTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))

    def tearDown(self):
        self.conn.close()

    def test_signatures_recorded_even_for_old_motions_but_items_only_recent(self):
        motions = [
            edm(603, "Foetal viability and the 24-week abortion limit", "2026-06-01", sigs=6),  # old
            edm(700, "Assisted dying safeguards", "2026-08-01", sigs=12),                       # new
            edm(701, "Road maintenance in Barsetshire", "2026-08-01"),                          # irrelevant
        ]
        with mock.patch.object(edms, "fetch_edms", return_value=motions):
            run_weekly.sweep_edms(None, self.conn, TAX, WL, WEEK, "2026-08-03", ["abortion"])
        # Signature counts: both matched motions, regardless of age.
        sigs = {r["edm_id"]: r["count"] for r in
                self.conn.execute("SELECT edm_id, count FROM edm_signatures").fetchall()}
        self.assertEqual(sigs, {603: 6, 700: 12})
        # Items: only the recently tabled matched motion.
        items = [r["id"] for r in self.conn.execute("SELECT id FROM items").fetchall()]
        self.assertEqual(items, ["edm:700"])

    def test_duplicate_motions_across_terms_stored_once(self):
        motions = [edm(700, "Assisted dying safeguards", "2026-08-01")]
        with mock.patch.object(edms, "fetch_edms", return_value=motions):
            run_weekly.sweep_edms(None, self.conn, TAX, WL, WEEK, "2026-08-03",
                                  ["assisted dying", "abortion"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM edm_signatures").fetchone()[0], 1)


class SettingsTests(unittest.TestCase):
    def test_settings_load_with_sweep_terms(self):
        settings = run_weekly.load_settings()
        self.assertIn("assisted dying", settings.get("pq_sweep_terms", []))
        self.assertIn("abortion", settings.get("edm_sweep_terms", []))


if __name__ == "__main__":
    unittest.main()
