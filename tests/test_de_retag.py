"""tools/de_retag.py only ever ADDS areas.

Re-deriving from the stored field and writing the result back would have
cleared 52 correct tags on its first run: speeches were classified from their
full body, not the excerpt the table keeps, and divisions from label, topics
and inheritance. The additive rule is the whole design.
"""

import importlib.util as iu
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt  # noqa: E402

spec = iu.spec_from_file_location("de_retag", os.path.join(ROOT, "tools", "de_retag.py"))
retag = iu.module_from_spec(spec)
spec.loader.exec_module(retag)


class AdditiveRetagTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))
        self.tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy-de.yaml"))
        self.wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist-de.yaml"))

    def _speech(self, sid, excerpt, areas):
        self.conn.execute(
            "INSERT INTO de_speeches (speech_id, protocol, excerpt, areas, first_seen, last_seen)"
            " VALUES (?,?,?,?,'2026-09-26','2026-09-26')",
            (sid, "21/96", excerpt, json.dumps(areas)))
        self.conn.commit()

    def _areas(self, sid):
        return json.loads(self.conn.execute(
            "SELECT areas FROM de_speeches WHERE speech_id = ?", (sid,)).fetchone()[0])

    def test_a_tag_the_stored_field_cannot_justify_is_kept(self):
        """Classified from a body this table no longer holds."""
        self._speech("s1", "Meine Damen und Herren, zur Tagesordnung.", [2])
        retag.retag(self.conn, self.tax, self.wl)
        self.assertEqual(self._areas("s1"), [2])

    def test_a_new_term_adds_its_area_beside_the_old_ones(self):
        self._speech("s2", "Kinderehen und Zwangsverheiratungen gibt es.", [9])
        retag.retag(self.conn, self.tax, self.wl)
        self.assertEqual(self._areas("s2"), [9, 12])

    def test_a_dry_run_writes_nothing(self):
        self._speech("s3", "Zwangsverheiratungen verhindern.", [])
        changes = retag.retag(self.conn, self.tax, self.wl, dry_run=True)
        self.assertTrue(changes)
        self.assertEqual(self._areas("s3"), [])


if __name__ == "__main__":
    unittest.main()
