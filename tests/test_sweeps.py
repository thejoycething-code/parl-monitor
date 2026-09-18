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

    def test_parallel_fetch_attributes_each_failure_to_the_right_term(self):
        """Which term gapped must not depend on which thread finished first.

        The fetch runs three at a time (2026-08-17); results come back in
        completion order, so the sweep re-reads them in term order before
        deciding anything.
        """
        import time

        def slow_and_flaky(client, term):
            # The failing term is also the SLOWEST, so a naive implementation
            # that zipped results onto terms in completion order would blame
            # the wrong one.
            if term == "grooming-gangs":
                time.sleep(0.05)
                raise FetchError("u", "pq", term, 2, TimeoutError("slow"))
            return []

        with mock.patch.object(pqs, "fetch_questions", side_effect=slow_and_flaky):
            failed = run_weekly.sweep_pqs(
                None, self.conn, TAX, WL, WEEK, "2026-08-03",
                ["hospices", "grooming-gangs", "surrogacy", "Rwanda"])
        self.assertEqual(failed, ["grooming-gangs"])
        gap = self.conn.execute("SELECT detail FROM gaps").fetchone()
        self.assertIn("grooming-gangs", gap["detail"])

    def test_parallel_and_sequential_store_the_same_items(self):
        results = {
            "safe access zones": [pq(2, "Abortion: safe access zones", "2026-08-01")],
            "hospices": [pq(3, "Hospices: funding", "2026-08-02")],
        }
        stored = {}
        for workers in (1, 3):
            conn = db.init_db(db.connect(":memory:"))
            with mock.patch.object(run_weekly, "PQ_SWEEP_CONCURRENCY", workers), \
                 mock.patch.object(pqs, "fetch_questions",
                                   side_effect=lambda c, t: results.get(t, [])):
                run_weekly.sweep_pqs(None, conn, TAX, WL, WEEK, "2026-08-03",
                                     list(results))
            stored[workers] = [r["id"] for r in conn.execute("SELECT id FROM items ORDER BY id")]
            conn.close()
        self.assertEqual(stored[1], stored[3])
        self.assertTrue(stored[1], "fixture should store something to compare")

    def test_sweep_reports_which_terms_failed(self):
        def flaky(client, term):
            if term == "border-security":
                raise FetchError("u", "pq", term, 2, TimeoutError("slow"))
            return []

        with mock.patch.object(pqs, "fetch_questions", side_effect=flaky):
            failed = run_weekly.sweep_pqs(None, self.conn, TAX, WL, WEEK, "2026-08-03",
                                          ["hospices", "border-security"])
        self.assertEqual(failed, ["border-security"])

    def test_resweep_clears_the_gap_and_stores_what_it_recovers(self):
        """A rescued term must stop being disclosed as a gap (2026-08-17).

        Written Questions failures cluster in a window, so the term that
        500ed during the sweep often answers at the end of the pull. If the
        gaps row survived, the footer would report missing results that are
        in fact stored.
        """
        with mock.patch.object(pqs, "fetch_questions",
                               side_effect=FetchError("u", "pq", "t", 2, TimeoutError("x"))):
            failed = run_weekly.sweep_pqs(None, self.conn, TAX, WL, WEEK, "2026-08-03",
                                          ["safe access zones"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0], 1)

        recovered = [pq(2, "Abortion: safe access zones", "2026-08-01")]
        with mock.patch.object(pqs, "fetch_questions", return_value=recovered):
            rescued = run_weekly.resweep_pq_gaps(None, self.conn, TAX, WL, WEEK,
                                                 "2026-08-03", failed)
        self.assertEqual(rescued, 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0], 0)
        self.assertEqual([r["id"] for r in self.conn.execute("SELECT id FROM items")], ["pq:2"])

    def test_resweep_leaves_the_gap_when_the_term_fails_again(self):
        with mock.patch.object(pqs, "fetch_questions",
                               side_effect=FetchError("u", "pq", "t", 2, TimeoutError("x"))):
            failed = run_weekly.sweep_pqs(None, self.conn, TAX, WL, WEEK, "2026-08-03",
                                          ["safe access zones"])
            rescued = run_weekly.resweep_pq_gaps(None, self.conn, TAX, WL, WEEK,
                                                 "2026-08-03", failed)
        self.assertEqual(rescued, 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0], 1)

    def test_resweep_costs_nothing_on_a_clean_week(self):
        calls = []
        with mock.patch.object(pqs, "fetch_questions", side_effect=lambda *a: calls.append(a)):
            self.assertEqual(
                run_weekly.resweep_pq_gaps(None, self.conn, TAX, WL, WEEK, "2026-08-03", []), 0)
        self.assertEqual(calls, [], "no gaps should mean no API calls")

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
        # The link's two halves are stored AS WE GO (18 Sept 2026): the tracker
        # builds the permalink from pq_link, and until now only the offline
        # backfill wrote it, so every question ledged after July was linkless.
        link = self.conn.execute("SELECT uin, tabled FROM pq_link WHERE pq_id = '2'").fetchone()
        self.assertEqual(tuple(link), ("HL2", "2026-07-20"))


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
        # A Monday edition REPORTS the week just ended: divisions are fetched
        # for [week-7, week-1), not the edition week itself, which on
        # publication morning has not happened yet (fixed 2026-08-24 after a
        # rehearsal showed the Votes section could never populate).
        division_day = WEEK - datetime.timedelta(days=4)
        dv = divisions.Division(id=1798, house="Commons", number=51,
                                title="Terminally Ill Adults (End of Life) Bill: Third Reading",
                                date=division_day, aye_count=1, no_count=1)
        voters = [divisions.Voter(14, "Aye MP", "Con", "Wokingham", "aye"),
                  divisions.Voter(15, "No MP", "Lab", "Leeds", "no")]
        with mock.patch.object(divisions, "fetch_commons_divisions",
                               side_effect=lambda c, d: ([dv] if d == division_day.isoformat()
                                                   else [])), \
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
        pq = settings.get("pq_sweep_terms", [])
        edm = settings.get("edm_sweep_terms", [])
        self.assertTrue(pq, "no PQ sweep terms configured")
        self.assertTrue(edm, "no EDM sweep terms configured")
        # Assert COVERAGE, not a literal term: the exact wording is editorial
        # and changes as the API's matching behaviour is measured. "assisted
        # dying" was replaced by terminally-ill-adults and assisted-suicide
        # because the original returned 12,480 matches led by a question about
        # fuel oil (2026-08-17).
        self.assertTrue(
            any("assisted" in t.lower() or "terminally" in t.lower() for t in pq),
            "no sweep term covers assisted dying, our core opposition issue")
        self.assertIn("abortion", edm)

    def test_sweep_terms_are_unique(self):
        """A duplicated term costs a slow API call and returns the same rows;
        one crept in while terms were being retuned (2026-08-17)."""
        for key in ("pq_sweep_terms", "edm_sweep_terms"):
            terms = run_weekly.load_settings().get(key, [])
            dupes = sorted({t for t in terms if terms.count(t) > 1})
            self.assertFalse(dupes, "duplicate {0}: {1}".format(key, dupes))


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
