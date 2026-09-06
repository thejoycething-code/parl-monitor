"""tools/retag_items.py (Christopher, 2026-09-06: "Do the retag").

A collector only re-filters a row when it SEES it again, so a taxonomy
change never reaches rows outside the source window. This re-derives
them offline -- and the trust check is the whole point: re-filtering
the wrong text once produced "574 rows re-tagged" that were nothing of
the kind.
"""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt

spec = importlib.util.spec_from_file_location(
    "retag_items", os.path.join(ROOT, "tools", "retag_items.py"))
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)

CURRENT = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
V15 = filt.load_taxonomy(os.path.join(ROOT, "tests", "fixtures",
                                      "taxonomy-v15.yaml"))
WL = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return conn


class Row(dict):
    """sqlite3.Row stand-in: subscript by name, .keys()."""
    def __getitem__(self, k):
        return self.get(k)


class TextMappingTests(unittest.TestCase):
    def test_every_builder_survives_empty_fields(self):
        row = Row(title=None, body=None, label=None, debate=None,
                  excerpt=None, summary=None, kind="question")
        for table, spec in rt.TABLES.items():
            args, kwargs = spec[1](row)
            self.assertTrue(all(isinstance(a, str) for a in args), table)

    def test_sp_divisions_recovers_the_heading_from_an_amendment_title(self):
        args, _ = rt.TABLES["sp_divisions"][1](
            Row(title="Assisted Dying Bill -- amendment 47 disagreed"))
        self.assertEqual(args, ("Assisted Dying Bill",))

    def test_ni_motions_filter_title_and_body_questions_title_only(self):
        build = rt.TABLES["ni_items"][1]
        args, kwargs = build(Row(kind="motion", title="T", body="B"))
        self.assertEqual((args, kwargs), (("T", "B"), {"title": "T"}))
        args, kwargs = build(Row(kind="question", title="Q", body="ignored"))
        self.assertEqual((args, kwargs), (("Q",), {}))

    def test_no_table_is_both_retagged_and_skipped(self):
        self.assertEqual(set(rt.TABLES) & set(rt.SKIPPED), set())
        for table, why in rt.SKIPPED.items():
            self.assertGreater(len(why), 40, table)


class TrustCheckTests(unittest.TestCase):
    """A stored tag must be reproducible under the baseline OR the current
    taxonomy. OR, because Friday's weeklies had already re-tagged the rows
    they re-saw under v1.6 -- [8, 9] on the Shahbaz resolution is not a
    wrong mapping, it is the right mapping under the taxonomy that
    produced it."""

    def test_a_row_only_the_current_taxonomy_explains_is_trusted(self):
        conn = store()
        title = ("The abduction, forced conversion and child marriage of "
                 "Maria Shahbaz")
        areas = rt.derive(CURRENT, WL, rt.TABLES["eu_texts"], Row(title=title))[0]
        self.assertEqual(areas, [8, 9])            # v1.6 vocabulary
        conn.execute("INSERT INTO eu_texts (identifier, title, areas, "
                     "first_seen, last_seen) VALUES ('TA', ?, ?, 'd', 'd')",
                     (title, json.dumps(areas)))
        conn.commit()
        lines = []
        untrusted = rt.trust_check(conn, V15, CURRENT, WL, lines.append)
        self.assertNotIn("eu_texts", untrusted)

    def test_a_row_neither_taxonomy_explains_is_untrusted(self):
        """"Business Programme" carrying area 3 can come from no heading:
        the votesmotion writer copied it from a motion body. That is how
        the second sp_divisions writer was found."""
        conn = store()
        conn.execute("INSERT INTO sp_divisions (key, title, areas, source, "
                     "first_seen, last_seen) VALUES ('b1', 'Business "
                     "Programme', '[3]', 'official-report', 'd', 'd')")
        conn.commit()
        untrusted = rt.trust_check(conn, V15, CURRENT, WL, lambda *a: None)
        self.assertIn("sp_divisions", untrusted)

    def test_votesmotion_rows_are_not_refiltered_but_reinherited(self):
        self.assertIn("official-report", rt.TABLES["sp_divisions"][3])
        conn = store()
        conn.execute("INSERT INTO sp_items (id, kind, reference, title, body, "
                     "areas, matched_terms, tier, first_seen, last_seen) VALUES "
                     "('m1', 'motion', 'S6M-1', 'Prostitution (Offences and "
                     "Support) (Scotland) Bill', '', '[12]', '[]', 1, 'd', 'd')")
        conn.execute("INSERT INTO sp_divisions (key, title, areas, source, "
                     "item_id, first_seen, last_seen) VALUES ('m1', "
                     "'Prostitution (Offences and Support) (Scotland) Bill', "
                     "'[5]', 'votesmotion', 'm1', 'd', 'd')")
        conn.commit()
        changed = rt.reinherit(conn, apply_it=True, log=lambda *a: None)
        self.assertEqual(changed, 1)
        self.assertEqual(conn.execute("SELECT areas FROM sp_divisions").fetchone()[0],
                         "[12]")


class DryRunTests(unittest.TestCase):
    def test_walk_writes_nothing(self):
        conn = store()
        conn.execute("INSERT INTO eu_pqs (identifier, title, areas, first_seen, "
                     "last_seen) VALUES ('E-1', 'Restrictions on the use of "
                     "church bells and freedom of religion', '[]', 'd', 'd')")
        conn.commit()
        n, changes = rt.walk(conn, CURRENT, WL, "eu_pqs", rt.TABLES["eu_pqs"])
        self.assertEqual((n, len(changes)), (1, 1))
        self.assertEqual(changes[0][2], [8])
        self.assertEqual(conn.execute("SELECT areas FROM eu_pqs").fetchone()[0],
                         "[]", "walk() must only report; main() writes")


if __name__ == "__main__":
    unittest.main()
