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

    def test_matched_edm_cosignatories_ledgered_with_areas(self):
        motions = [edm(700, "Assisted dying safeguards", "2026-08-01", sigs=3)]
        sponsors = [
            edms.Sponsor(5244, "Prime Mover", "Labour", "Seat A", 1, False),
            edms.Sponsor(5319, "Co Signer", "Conservative", "Seat B", 2, False),
            edms.Sponsor(5400, "With Drawn", "Labour", "Seat C", 3, True),
        ]
        with mock.patch.object(edms, "fetch_edms", return_value=motions), \
                mock.patch.object(edms, "fetch_sponsors", return_value=sponsors):
            run_weekly.sweep_edms(None, self.conn, TAX, WL, WEEK, "2026-08-03",
                                  ["assisted dying"])
        rows = self.conn.execute(
            "SELECT member_id, kind, areas FROM mp_events ORDER BY member_id").fetchall()
        # Order-1 primary and withdrawn signatures never ledger as co-signatories.
        self.assertEqual([(r["member_id"], r["kind"]) for r in rows],
                         [(5319, "edm-signed")])
        self.assertIn("2", rows[0]["areas"])  # assisted dying = area 2, stamped
        cached = self.conn.execute(
            "SELECT name, house FROM members WHERE id = 5319").fetchone()
        self.assertEqual((cached["name"], cached["house"]), ("Co Signer", "Commons"))

    def test_duplicate_motions_across_terms_stored_once(self):
        motions = [edm(700, "Assisted dying safeguards", "2026-08-01")]
        with mock.patch.object(edms, "fetch_edms", return_value=motions):
            run_weekly.sweep_edms(None, self.conn, TAX, WL, WEEK, "2026-08-03",
                                  ["assisted dying", "abortion"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM edm_signatures").fetchone()[0], 1)


class DeadClient:
    """Every unmocked feed fails as a disclosed gap, so these tests exercise
    one capture path at a time without reaching the network."""

    def get_json(self, url, feed, slug, timeout=None):
        raise FetchError(url, feed, slug, 1, TimeoutError("offline"))


class WeeklyLedgerCaptureTests(unittest.TestCase):
    """From September the weekly pull must keep the ledger's two strongest
    evidence tiers growing: division breakdowns and Hansard speeches."""

    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))

    def tearDown(self):
        self.conn.close()

    def test_division_breakdown_ledgered_and_item_stored(self):
        from src.ingest import divisions
        dv = divisions.Division(id=1798, house="Commons", number=51,
                                title="Terminally Ill Adults (End of Life) Bill: Third Reading",
                                date=datetime.date(2026, 8, 4), aye_count=1, no_count=1)
        voters = [divisions.Voter(14, "Aye MP", "Con", "Wokingham", "aye"),
                  divisions.Voter(15, "No MP", "Lab", "Leeds", "no")]
        with mock.patch.object(divisions, "fetch_commons_divisions",
                               side_effect=lambda c, d: [dv] if d == "2026-08-04" else []), \
                mock.patch.object(divisions, "fetch_lords_divisions", return_value=[]), \
                mock.patch.object(divisions, "fetch_commons_breakdown",
                                  return_value=(dv, voters)), \
                mock.patch.object(run_weekly, "load_settings", return_value={}):
            run_weekly.ingest_all(DeadClient(), self.conn, TAX, WL, WEEK,
                                  WEEK + datetime.timedelta(days=6))
        rows = self.conn.execute(
            "SELECT member_id, kind, ref, areas FROM mp_events ORDER BY member_id").fetchall()
        self.assertEqual([(r["member_id"], r["ref"]) for r in rows],
                         [(14, "div:c1798:aye"), (15, "div:c1798:no")])
        self.assertIn("2", rows[0]["areas"])  # assisted dying area stamped
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM items WHERE source_feed='division'"
                              ).fetchone()[0], 1)
        # Voter details seed the members cache without Members API traffic.
        self.assertEqual(
            self.conn.execute("SELECT name FROM members WHERE id=14").fetchone()["name"],
            "Aye MP")

    def test_hansard_speech_ledgered_with_areas(self):
        from src.ingest import hansard
        speech = hansard.Contribution(
            ext_id="ABC", member_id=99, member_name="Speaking MP",
            date=datetime.date(2026, 8, 5), house="Commons",
            debate_title="Assisted Dying", text="I oppose assisted suicide.",
            debate_ext_id="DEF")
        with mock.patch.object(hansard, "search_contributions",
                               return_value=[speech]), \
                mock.patch.object(pqs, "fetch_questions", return_value=[]), \
                mock.patch.object(run_weekly, "load_settings",
                                  return_value={"pq_sweep_terms": ["assisted dying"]}), \
                mock.patch.object(run_weekly.members, "resolve", return_value=None):
            run_weekly.ingest_all(DeadClient(), self.conn, TAX, WL, WEEK,
                                  WEEK + datetime.timedelta(days=6))
        row = self.conn.execute(
            "SELECT member_id, kind, ref, line FROM mp_events WHERE kind='debate'").fetchone()
        self.assertEqual((row["member_id"], row["ref"]), (99, "hansard:ABC"))
        self.assertIn("Spoke: Assisted Dying", row["line"])


class SettingsTests(unittest.TestCase):
    def test_settings_load_with_sweep_terms(self):
        settings = run_weekly.load_settings()
        self.assertIn("assisted dying", settings.get("pq_sweep_terms", []))
        self.assertIn("abortion", settings.get("edm_sweep_terms", []))


class StoreItemUpsertTests(unittest.TestCase):
    """Re-pulling must never wipe editorial state (scores, priorities, owners)."""

    def test_repull_preserves_editorial_fields(self):
        conn = db.init_db(db.connect(":memory:"))
        try:
            r = filt.FilterResult(matched_terms=["weddings law"], issue_areas=[9], tier=1)
            run_weekly.store_item(conn, "consultation:x", "consultation", "consultation",
                                  "Old title", "https://old", r)
            conn.execute("UPDATE items SET triage_score=3, priority_tag='ACT', owner='Zuzana', "
                         "why_it_matters='Campaign live' WHERE id='consultation:x'")
            conn.commit()
            run_weekly.store_item(conn, "consultation:x", "consultation", "consultation",
                                  "New title", "https://new", r)
            row = conn.execute("SELECT * FROM items WHERE id='consultation:x'").fetchone()
            self.assertEqual(row["title"], "New title")          # feed data refreshed
            self.assertEqual(row["triage_score"], 3)             # editorial preserved
            self.assertEqual(row["priority_tag"], "ACT")
            self.assertEqual(row["owner"], "Zuzana")
            self.assertEqual(row["why_it_matters"], "Campaign live")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
