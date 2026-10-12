"""tools/store_compact.py: rowid vote tables rebuilt WITHOUT ROWID, on throwaway stores.
Also pins that every vote table the code creates is WITHOUT ROWID (12 October 2026)."""

import contextlib
import glob
import io
import os
import re
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import store_compact  # noqa: E402


def quiet(fn, *args, **kwargs):
    lines = []
    rc = fn(*args, log=lines.append, **kwargs)
    return rc, lines


class CompactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "store.db")
        conn = sqlite3.connect(self.path)
        conn.executescript("""
            CREATE TABLE fr_votes (
                division_key TEXT NOT NULL,
                acteur_ref   TEXT NOT NULL,
                position     TEXT,           -- 'pour' / 'contre' (a comment with (parens))
                PRIMARY KEY (division_key, acteur_ref)
            );
            CREATE INDEX fr_votes_member ON fr_votes (acteur_ref);
            CREATE INDEX fr_votes_div ON fr_votes (division_key);
            CREATE TABLE pl_votes (division_key TEXT NOT NULL, mp_key TEXT NOT NULL, position TEXT,
                PRIMARY KEY (division_key, mp_key)) WITHOUT ROWID;
            CREATE TABLE un_votes (report TEXT NOT NULL, draft TEXT, state TEXT NOT NULL,
                position TEXT, PRIMARY KEY (report, draft, state));
            CREATE TABLE xx_votes (a TEXT, b TEXT);
            CREATE TABLE yy_votes (k TEXT PRIMARY KEY, v TEXT);
            CREATE TABLE fr_divisions (division_key TEXT PRIMARY KEY, title TEXT);
        """)
        conn.executemany("INSERT INTO fr_votes VALUES (?,?,?)",
                         [("d{0}".format(d), "m{0}".format(m), "pour" if (d + m) % 3 else None)
                          for d in range(60) for m in range(40)])
        conn.executemany("INSERT INTO pl_votes VALUES (?,?,?)", [("d1", "m1", "YES")])
        conn.executemany("INSERT INTO un_votes VALUES (?,?,?,?)",
                         [("A/HRC/58/2", None, "Cuba", "for"), ("A/HRC/58/2", "L.1", "Cuba", "no")])
        conn.executemany("INSERT INTO xx_votes VALUES (?,?)", [("a", "b")])
        conn.executemany("INSERT INTO yy_votes VALUES (?,?)", [(None, "a null key"), ("k", "v")])
        conn.executemany("INSERT INTO fr_divisions VALUES (?,?)", [("d1", "t")])
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def _sql(self, table):
        conn = sqlite3.connect(self.path)
        try:
            return conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (table,)).fetchone()[0]
        finally:
            conn.close()

    def _rows(self, table):
        conn = sqlite3.connect(self.path)
        try:
            return sorted(conn.execute("SELECT * FROM {0}".format(table)).fetchall(), key=repr)
        finally:
            conn.close()

    def test_plan_finds_rowid_vote_tables_by_name_and_says_why_others_are_skipped(self):
        conn = sqlite3.connect(self.path)
        todo, skipped = store_compact.plan(conn)
        conn.close()
        self.assertEqual(todo, ["fr_votes"])
        why = dict(skipped)
        self.assertIn("already WITHOUT ROWID", why["pl_votes"])
        self.assertIn("kept", why["un_votes"])
        self.assertIn("no PRIMARY KEY", why["xx_votes"])
        self.assertIn("NULL key", why["yy_votes"])
        self.assertNotIn("fr_divisions", why)            # not a vote table at all

    def test_rebuild_keeps_every_row_and_index_and_drops_the_redundant_one(self):
        before = self._rows("fr_votes")
        rc, lines = quiet(store_compact.run, self.path)
        self.assertEqual(rc, 0, lines)
        self.assertTrue(store_compact.is_without_rowid(self._sql("fr_votes")))
        self.assertIn("(parens)", self._sql("fr_votes"))   # the original definition, kept
        self.assertEqual(self._rows("fr_votes"), before)
        conn = sqlite3.connect(self.path)
        idx = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='fr_votes'")}
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        # The key still holds: a duplicate is refused.
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO fr_votes VALUES ('d1', 'm1', 'x')")
        conn.close()
        self.assertIn("fr_votes_member", idx)              # still needed: member lookups
        self.assertNotIn("fr_votes_div", idx)              # a leading part of the key: redundant
        self.assertTrue(any("redundant index fr_votes_div" in ln for ln in lines))
        self.assertNotIn("fr_votes__compact", names)
        # The others are untouched.
        self.assertFalse(store_compact.is_without_rowid(self._sql("un_votes")))
        self.assertEqual(len(self._rows("un_votes")), 2)
        self.assertTrue(any(ln.startswith("  VACUUM in") for ln in lines))

    def test_idempotent(self):
        quiet(store_compact.run, self.path)
        rc, lines = quiet(store_compact.run, self.path, vacuum=False)
        self.assertEqual(rc, 0)
        self.assertTrue(any("rebuilding 0 table(s)" in ln for ln in lines), lines)
        self.assertTrue(any("skip fr_votes: already WITHOUT ROWID" in ln for ln in lines))

    def test_dry_run_changes_nothing_and_estimates(self):
        with open(self.path, "rb") as handle:
            raw = handle.read()
        rc, lines = quiet(store_compact.run, self.path, dry_run=True)
        self.assertEqual(rc, 0)
        with open(self.path, "rb") as handle:
            self.assertEqual(handle.read(), raw)
        text = "\n".join(lines)
        self.assertIn("would rebuild 1 table(s)", text)
        self.assertIn("fr_votes", text)
        self.assertIn("expected saving", text)

    def test_a_mismatch_rolls_the_table_back(self):
        real = store_compact.checksum
        calls = []

        def bad(conn, table, cols, keys):
            calls.append(table)
            return real(conn, table, cols, keys) + ("x" if table.endswith("__compact") else "")

        before = self._rows("fr_votes")
        with mock.patch.object(store_compact, "checksum", side_effect=bad):
            rc, lines = quiet(store_compact.run, self.path)
        self.assertEqual(rc, 1)
        self.assertTrue(any("checksum differs" in ln for ln in lines), lines)
        self.assertFalse(store_compact.is_without_rowid(self._sql("fr_votes")))
        self.assertEqual(self._rows("fr_votes"), before)
        conn = sqlite3.connect(self.path)
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
        conn.close()
        self.assertNotIn("fr_votes__compact", names)
        self.assertIn("fr_votes_div", names)

    def test_vacuum_skipped_when_the_disk_is_short(self):
        with mock.patch.object(store_compact, "vacuum_space_ok", return_value=(False, 1, 2)):
            rc, lines = quiet(store_compact.run, self.path)
        self.assertEqual(rc, 0)
        self.assertTrue(any("VACUUM skipped" in ln for ln in lines))

    def test_new_table_sql(self):
        sql = "CREATE TABLE ab_votes (\n k TEXT NOT NULL, PRIMARY KEY (k)\n)"
        self.assertEqual(store_compact.new_table_sql(sql, "ab_votes", "ab_votes__compact"),
                         'CREATE TABLE "ab_votes__compact" (\n k TEXT NOT NULL, PRIMARY KEY (k)\n) WITHOUT ROWID')

    def test_cli(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc = store_compact.main(["--db", self.path, "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("would rebuild", out.getvalue())


class SchemaTests(unittest.TestCase):
    """New stores are built compact: every _votes table the code creates is
    WITHOUT ROWID, except un_votes (its key may be NULL)."""

    def test_every_vote_table_created_without_rowid(self):
        conn = sqlite3.connect(":memory:")
        from src import db
        db.init_db(conn)
        for path in sorted(glob.glob(os.path.join(ROOT, "src", "*_store.py"))):
            mod = __import__("src." + os.path.basename(path)[:-3], fromlist=["x"])
            if hasattr(mod, "ensure_schema"):
                mod.ensure_schema(conn)
        tables = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table' "
                              "AND name LIKE '%\\_votes' ESCAPE '\\'").fetchall()
        self.assertGreaterEqual(len(tables), 37)
        rowid = sorted(n for n, sql in tables if not store_compact.is_without_rowid(sql))
        self.assertEqual(rowid, sorted(store_compact.EXCLUDE))

    def test_no_code_addresses_a_vote_table_by_rowid(self):
        pat = re.compile(r"\b(\w+_votes)\b[^\n;]*\browid\b|\browid\b[^\n;]*\bFROM\s+(\w+_votes)\b", re.I)
        for path in glob.glob(os.path.join(ROOT, "src", "**", "*.py"), recursive=True) + \
                glob.glob(os.path.join(ROOT, "tools", "*.py")):
            if path.endswith("store_compact.py"):
                continue
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            for m in pat.finditer(text):
                if "WITHOUT ROWID" in m.group(0).upper():
                    continue
                self.fail("{0}: {1}".format(os.path.relpath(path, ROOT), m.group(0)[:100]))


if __name__ == "__main__":
    unittest.main()
