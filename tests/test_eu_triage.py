"""EU triage (Christopher, 2026-09-01: "Triage the EU items"): the same
judge Westminster items get, over every taxonomy-matched EU row. Scored
once, ever; stub fallback without a key; spend recorded.
"""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, triage


def _load():
    spec = importlib.util.spec_from_file_location(
        "eu_triage", os.path.join(ROOT, "tools", "eu_triage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


eut = _load()


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    eut.ensure_columns(conn)
    conn.execute("INSERT INTO eu_consultations (key, title, summary, areas, "
                 "tier, first_seen, last_seen) VALUES ('1', 'Fitness check "
                 "on abortion access', 'framework text', '[1]', 1, "
                 "'2026-09-01', '2026-09-01')")
    conn.execute("INSERT INTO eu_divisions (vote_id, label, areas, tier, "
                 "first_seen, last_seen) VALUES ('D1', 'ePrivacy scanning "
                 "derogation', '[6]', 2, '2026-09-01', '2026-09-01')")
    conn.execute("INSERT INTO eu_texts (identifier, title, areas, tier, "
                 "first_seen, last_seen) VALUES ('TA-1', 'CAP transition', "
                 "'[]', NULL, '2026-09-01', '2026-09-01')")
    conn.commit()
    return conn


class TriageTests(unittest.TestCase):
    def test_only_matched_rows_are_judged(self):
        conn = store()
        items = eut.pending(conn)
        self.assertEqual(sorted(i.id for i in items),
                         ["eu_consultations:1", "eu_divisions:D1"])

    def test_stub_scores_apply_and_never_rescore(self):
        conn = store()
        results = triage.score_stub(eut.pending(conn))
        eut.apply(conn, results)
        row = conn.execute("SELECT triage_score FROM eu_consultations "
                           "WHERE key='1'").fetchone()
        self.assertEqual(row["triage_score"], 2)   # tier 1 -> 2 in the stub
        self.assertEqual(eut.pending(conn), [],
                         "scored once, ever: nothing left to judge")

    def test_scores_land_on_the_right_table_and_key(self):
        conn = store()
        eut.apply(conn, [triage.TriageResult(
            id="eu_divisions:D1", score=3, areas=[6],
            why_it_matters="Scanning precedent.")])
        row = conn.execute("SELECT triage_score, why_it_matters FROM "
                           "eu_divisions WHERE vote_id='D1'").fetchone()
        self.assertEqual((row["triage_score"], row["why_it_matters"]),
                         (3, "Scanning precedent."))


class ResilienceTests(unittest.TestCase):
    def test_a_live_failure_leaves_rows_unscored_never_stubbed(self):
        """Scores are once-ever, so a transient API failure must not freeze
        stub scores in; the rows stay unscored and next week retries. The
        guard is structural: main() returns before apply() on failure."""
        src = open(os.path.join(ROOT, "tools", "eu_triage.py"),
                   encoding="utf-8").read()
        self.assertIn("left unscored; next run retries", src)
        self.assertIn("for attempt in (1, 2):", src)
        # the failure path must NOT fall through to score_stub
        live_block = src[src.index("if api_key:"):src.index("else:")]
        self.assertNotIn("score_stub", live_block)


class CoverageTests(unittest.TestCase):
    """The judge must see EVERY table that carries `areas`.

    It listed four while the monitor had grown to nine collectors, so 66
    matched rows -- courts, written questions, committee documents, ECIs,
    speeches -- sat unscored while the run printed "nothing unscored"
    (2026-09-03). This fails if a new eu_ table with an `areas` column is
    ever added without joining SOURCES.
    """

    def test_every_eu_table_with_areas_is_judged(self):
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        db.init_db(conn)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name LIKE 'eu\\_%' ESCAPE '\\'")]
        with_areas = []
        for name in tables:
            cols = [c[1] for c in conn.execute(
                "PRAGMA table_info({0})".format(name))]
            if "areas" in cols:
                with_areas.append(name)
        missing = sorted(set(with_areas) - set(eut.SOURCES)
                         - set(eut.EXEMPT))
        self.assertEqual(missing, [], "these carry areas but are neither "
                                      "judged nor exempt: {0}".format(missing))

    def test_every_exemption_states_a_reason(self):
        for table, reason in eut.EXEMPT.items():
            self.assertGreater(len(reason), 40,
                               "{0} is exempt without a real reason"
                               .format(table))
            self.assertNotIn(table, eut.SOURCES,
                             "{0} cannot be both judged and exempt"
                             .format(table))


class BatchingTests(unittest.TestCase):
    def test_long_texts_are_trimmed_and_chunks_halve_on_failure(self):
        src = open(os.path.join(ROOT, "tools", "eu_triage.py"),
                   encoding="utf-8").read()
        self.assertIn("[:300]", src)
        self.assertIn("def score_chunk(", src)
        self.assertIn("half = len(chunk) // 2", src)
        self.assertIn("left for next run", src)


class TextExcerptTests(unittest.TestCase):
    """17 September 2026: adopted texts moved from title matching to body
    matching, because Parliament titles are generic. The judge still read the
    title alone, so it would have been asked to score the very string that
    failed to match -- with none of the evidence that admitted the row."""

    def test_the_judge_sees_the_excerpt_as_well_as_the_title(self):
        ident, fields = eut.SOURCES["eu_texts"]
        self.assertEqual(ident, "identifier")
        self.assertIn("title", fields)
        self.assertIn("excerpt", fields, "the passage that admitted the row must reach the judge")

    def test_every_body_matched_source_carries_its_evidence(self):
        """eu_speeches has always passed its excerpt; eu_texts now does too."""
        for table in ("eu_texts", "eu_speeches"):
            self.assertIn("excerpt", eut.SOURCES[table][1], table)


if __name__ == "__main__":
    unittest.main()


class RescoreTests(unittest.TestCase):
    def test_rescore_requeues_one_row_and_only_that_row(self):
        conn = store()
        conn.execute("UPDATE eu_consultations SET triage_score = 0, why_it_matters = 'noise' WHERE key = '1'")
        conn.execute("UPDATE eu_divisions SET triage_score = 2, why_it_matters = 'kept' WHERE vote_id = 'D1'")
        self.assertEqual(eut.rescore(conn, "eu_consultations:1"), 1)
        row = conn.execute("SELECT triage_score, why_it_matters FROM eu_consultations WHERE key='1'").fetchone()
        self.assertEqual(tuple(row), (None, None))
        row = conn.execute("SELECT triage_score, why_it_matters FROM eu_divisions WHERE vote_id='D1'").fetchone()
        self.assertEqual(tuple(row), (2, "kept"))
        self.assertEqual([i.id for i in eut.pending(conn) if i.id == "eu_consultations:1"],
                         ["eu_consultations:1"])

    def test_rescore_refuses_an_unknown_table(self):
        with self.assertRaises(SystemExit):
            eut.rescore(store(), "items:1")


class PropagateTests(unittest.TestCase):
    def _store(self):
        conn = store()
        conn.execute("INSERT INTO eu_texts (identifier, date, title, areas, tier, body_read, first_seen, last_seen, "
                     "triage_score, why_it_matters) VALUES ('TA-G', '2026-09-16', 'Gender inequalities in health', "
                     "'[1,4]', 1, '2026-09-17', '2026-09-17', '2026-09-17', 2, 'SRHR and abortion throughout')")
        for vid, inh in (("G1", "TA-G"), ("G2", "TA-G"), ("L1", None)):
            conn.execute("INSERT INTO eu_divisions (vote_id, date, label, areas, tier, inherited_from, first_seen, "
                         "last_seen) VALUES (?,?,?,?,?,?,?,?)", (vid, "2026-09-16", vid, "[1,4]", 1, inh,
                                                                 "2026-09-17", "2026-09-17"))
        return conn

    def test_inherited_divisions_are_not_queued_for_the_judge(self):
        ids = [i.id for i in eut.pending(self._store()) if i.id.startswith("eu_divisions:")]
        self.assertEqual(ids, ["eu_divisions:D1", "eu_divisions:L1"],
                         "G1 and G2 are judged through their text")

    def test_propagate_copies_the_text_score_once(self):
        conn = self._store()
        self.assertEqual(eut.propagate(conn), 2)
        rows = conn.execute("SELECT vote_id, triage_score, why_it_matters FROM eu_divisions ORDER BY vote_id").fetchall()
        self.assertEqual([tuple(r) for r in rows], [("D1", None, None), ("G1", 2, "SRHR and abortion throughout"),
                                                    ("G2", 2, "SRHR and abortion throughout"), ("L1", None, None)])
        self.assertEqual(eut.propagate(conn), 0, "already carried")

    def test_an_unscored_text_carries_nothing_yet(self):
        conn = self._store()
        conn.execute("UPDATE eu_texts SET triage_score = NULL WHERE identifier = 'TA-G'")
        self.assertEqual(eut.propagate(conn), 0)
