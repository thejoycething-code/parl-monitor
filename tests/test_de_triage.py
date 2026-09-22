"""The German triage tool: its frame, its scope, and one judgement per document."""

import importlib.util
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, triage  # noqa: E402


def _load():
    spec = importlib.util.spec_from_file_location(
        "de_triage", os.path.join(ROOT, "tools", "de_triage.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


det = _load()


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    det.ensure_columns(conn)
    return conn


class FrameTests(unittest.TestCase):
    """The EU judge, briefed as a UK monitor, called a Hong Kong resolution
    'unrelated to CitizenGO's UK-focused campaign areas'. Germany must not
    inherit that mistake, and adds three constraints of its own."""

    def test_the_german_frame_drops_the_uk_and_keeps_the_rubric(self):
        p = triage.SYSTEM_PROMPT_DE
        self.assertNotIn("CitizenGO UK's", p)
        self.assertIn("German parliamentary monitor", p)
        self.assertIn("sixteen Land parliaments", p)
        self.assertIn("not been translated", p)
        self.assertIn("never mark a Landtag item down for not being federal", p)
        self.assertIn("in ENGLISH", p)
        for shared in ("Score 0 = irrelevant", "maximum 35 words", "British spelling"):
            self.assertIn(shared, p)

    def test_the_tool_asks_for_the_german_frame(self):
        src = open(os.path.join(ROOT, "tools", "de_triage.py"), encoding="utf-8").read()
        self.assertIn("system=triage.SYSTEM_PROMPT_DE", src)


class ScopeTests(unittest.TestCase):
    def test_every_german_table_with_areas_is_judged_or_exempt(self):
        """The EU monitor grew five collectors whose rows sat unscored while
        the run printed 'nothing unscored'."""
        conn = sqlite3.connect(":memory:")
        db.init_db(conn)
        carrying = []
        for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                    "AND name LIKE 'de/_%' ESCAPE '/' ORDER BY name"):
            cols = {c[1] for c in conn.execute("PRAGMA table_info({0})".format(name))}
            if "areas" in cols:
                carrying.append(name)
        self.assertTrue(carrying, "no German tables carry areas; the glob is wrong")
        missing = sorted(set(carrying) - set(det.SOURCES) - set(det.EXEMPT))
        self.assertEqual(missing, [], "unjudged and unexplained: {0}".format(missing))

    def test_every_exemption_states_a_reason(self):
        for table, reason in det.EXEMPT.items():
            self.assertGreater(len(reason), 40, table)


class PendingTests(unittest.TestCase):
    def _seed(self, conn):
        conn.execute("INSERT INTO de_documents (doc_id, kind, titel, excerpt, areas, tier, "
                     "first_seen, last_seen) VALUES ('drucksache:21/1','drucksache',"
                     "'Antrag','Leihmutterschaft verbieten','[10]',1,'d','d')")
        conn.execute("INSERT INTO de_vorgaenge (vorgang_id, titel, areas, tier, first_seen, "
                     "last_seen) VALUES ('7','Selbstbestimmungsgesetz','[5]',1,'d','d')")
        for vid, inh in (("own", None), ("borrowed", "drucksache:21/1")):
            conn.execute("INSERT INTO de_divisions (vote_id, label, areas, tier, "
                         "inherited_from, first_seen, last_seen) VALUES (?,?,'[5]',1,?,'d','d')",
                         (vid, "Ein Antrag", inh))
        conn.commit()

    def test_an_inherited_division_is_judged_through_its_document(self):
        conn = store(); self._seed(conn)
        ids = sorted(i.id for i in det.pending(conn))
        self.assertIn("de_divisions:own", ids)
        self.assertNotIn("de_divisions:borrowed", ids,
                         "one judgement per document, not one per roll call")

    def test_propagate_copies_the_documents_verdict_down_once(self):
        conn = store(); self._seed(conn)
        conn.execute("UPDATE de_documents SET triage_score = 3, why_it_matters = 'Surrogacy ban'")
        conn.commit()
        self.assertEqual(det.propagate(conn), 1)
        row = conn.execute("SELECT triage_score, why_it_matters FROM de_divisions "
                           "WHERE vote_id='borrowed'").fetchone()
        self.assertEqual((row["triage_score"], row["why_it_matters"]), (3, "Surrogacy ban"))
        self.assertEqual(det.propagate(conn), 0, "already carried")
        self.assertIsNone(conn.execute("SELECT triage_score FROM de_divisions "
                                       "WHERE vote_id='own'").fetchone()[0])

    def test_an_unscored_document_carries_nothing_yet(self):
        conn = store(); self._seed(conn)
        self.assertEqual(det.propagate(conn), 0)

    def test_the_excerpt_travels_with_the_title(self):
        """A Vorgang title is administrative; the passage says what it is about."""
        conn = store(); self._seed(conn)
        item = next(i for i in det.pending(conn) if i.id == "de_documents:drucksache:21/1")
        self.assertIn("Leihmutterschaft", item.text)

    def test_rescore_requeues_one_row_and_refuses_an_unknown_table(self):
        conn = store(); self._seed(conn)
        conn.execute("UPDATE de_vorgaenge SET triage_score = 0, why_it_matters = 'noise'")
        conn.commit()
        self.assertEqual(det.rescore(conn, "de_vorgaenge:7"), 1)
        self.assertIsNone(conn.execute("SELECT triage_score FROM de_vorgaenge").fetchone()[0])
        with self.assertRaises(SystemExit):
            det.rescore(conn, "items:1")


if __name__ == "__main__":
    unittest.main()
