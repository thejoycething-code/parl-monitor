"""Rebuild the store's rowid vote tables WITHOUT ROWID, then VACUUM. One-off.

    python3 tools/store_compact.py --dry-run          # what it would do, and the saving
    python3 tools/store_compact.py                    # data/parl-monitor.db, in place
    python3 tools/store_compact.py --db PATH          # another store file
    python3 tools/store_compact.py --no-vacuum        # the rebuilds only

Why (docs/store-split-plan.md, Stage 1; Chris approved 12 October 2026). A
roll-call table such as fr_votes keeps every row twice: once in the table,
keyed by a hidden rowid, and again in the automatic index that enforces its
PRIMARY KEY (division_key, member). A WITHOUT ROWID table is stored inside its
primary key, so the duplicate index goes. pl_votes was built that way from the
start (src/pl_store.py: about 60 bytes a position against 100). On a scratch
copy of the 12 October store the rebuild plus a VACUUM took it from 1,825 MB
to 1,480 MB raw and from 447 MB to 308 MB compressed. No query changes: the
same columns, the same key, the same secondary indexes.

What it does, per table, inside ONE transaction (so a failure part-way leaves
that table exactly as it was, and every table already done stays done):
create `<table>__compact` from the table's own CREATE TABLE plus WITHOUT ROWID,
copy every row, check the row counts match and that a sha256 over every row
read in primary-key order matches the original's, drop the original, rename
the copy, and recreate its secondary indexes (an index that is only a leading
part of the primary key is redundant once the table IS that key, so it is not
recreated and the output says so). Then one VACUUM for the whole file.

Which tables. Every table whose name ends in `_votes` that still has a rowid,
found by reading sqlite_master, not from a list: a vote table a country
branch adds later is picked up the same way. Skipped, with the reason
printed: a table already WITHOUT ROWID (so a second run does nothing), one
with no PRIMARY KEY or an AUTOINCREMENT, one with a NULL in a key column
(WITHOUT ROWID refuses NULL keys), and un_votes (EXCLUDE: its `draft` key
column may be NULL by design).

The store's CREATE TABLE statements (src/db.py and src/<cc>_store.py) say
WITHOUT ROWID since the same change, so a store built from scratch already
has the new form; this tool converts the published store once
(jobs/store-compact.sh on the Mac Mini).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "parl-monitor.db")
SUFFIX = "_votes"
TMP_SUFFIX = "__compact"
# Vote tables that keep their rowid, and why. Printed when skipped.
EXCLUDE = {
    "un_votes": "its key column `draft` may be NULL by design (src/db.py); tiny and paused",
}
# Measured on the 12 October 2026 store (docs/store-split-plan.md): the
# rebuild saved 213 MB against 336 MB of primary-key autoindex on the vote
# tables. Used only for --dry-run's estimate.
REBUILD_SAVING_PER_INDEX_BYTE = 0.63
# A VACUUM writes a full copy beside the store and journals it, so it wants
# about twice the store's size free; the rebuilds want one table's worth.
VACUUM_SPACE_FACTOR = 2.1

_WITHOUT_ROWID = re.compile(r"\)\s*WITHOUT\s+ROWID\s*$", re.I)


def q(name):
    """A quoted SQL identifier."""
    return '"' + name.replace('"', '""') + '"'


def is_without_rowid(sql):
    return bool(sql and _WITHOUT_ROWID.search(sql.strip().rstrip(";")))


def key_columns(conn, table):
    """The PRIMARY KEY columns of `table`, in key order ([] if none)."""
    rows = conn.execute("PRAGMA table_info({0})".format(q(table))).fetchall()
    return [r[1] for r in sorted((r for r in rows if r[5]), key=lambda r: r[5])]


def columns(conn, table):
    return [r[1] for r in conn.execute("PRAGMA table_info({0})".format(q(table)))]


def candidates(conn):
    """[(table, sql)] for every table ending in _votes, by name."""
    return conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND name LIKE ? ESCAPE '\\' "
        "AND name NOT LIKE ? ESCAPE '\\' ORDER BY name",
        ("%\\" + SUFFIX, "%" + TMP_SUFFIX.replace("_", "\\_"))).fetchall()


def skip_reason(conn, table, sql):
    """Why `table` is not rebuilt, or None if it should be."""
    if is_without_rowid(sql):
        return "already WITHOUT ROWID"
    if table in EXCLUDE:
        return "kept: " + EXCLUDE[table]
    if "AUTOINCREMENT" in (sql or "").upper():
        return "AUTOINCREMENT needs a rowid"
    keys = key_columns(conn, table)
    if not keys:
        return "no PRIMARY KEY"
    nulls = conn.execute("SELECT count(*) FROM {0} WHERE {1}".format(
        q(table), " OR ".join("{0} IS NULL".format(q(k)) for k in keys))).fetchone()[0]
    if nulls:
        return "{0} rows with a NULL key column (WITHOUT ROWID refuses them)".format(nulls)
    return None


def plan(conn):
    """-> ([table to rebuild], [(table, reason skipped)])."""
    todo, skipped = [], []
    for table, sql in candidates(conn):
        why = skip_reason(conn, table, sql)
        if why:
            skipped.append((table, why))
        else:
            todo.append(table)
    return todo, skipped


def new_table_sql(sql, table, new_name):
    """The table's own CREATE TABLE under `new_name`, plus WITHOUT ROWID."""
    m = re.match(r'\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?("?)' + re.escape(table) + r'\1(?=[\s(])',
                 sql, re.I)
    if not m:
        raise ValueError("cannot read the CREATE TABLE of {0}".format(table))
    body = sql[m.end():].rstrip().rstrip(";").rstrip()
    return "CREATE TABLE {0}{1} WITHOUT ROWID".format(q(new_name), body)


def index_columns(conn, index):
    return [r[2] for r in conn.execute("PRAGMA index_info({0})".format(q(index)))]


def indexes(conn, table):
    """[(name, sql, redundant)] for the table's own (non-automatic) indexes.
    redundant: a plain index on a leading part of the primary key, which the
    WITHOUT ROWID table already is."""
    keys = key_columns(conn, table)
    out = []
    for name, sql in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name=? "
            "AND sql IS NOT NULL ORDER BY name", (table,)):
        cols = index_columns(conn, name)
        plain = not re.search(r"\bUNIQUE\b", sql, re.I) and not re.search(r"\bWHERE\b", sql, re.I)
        redundant = plain and bool(cols) and cols == keys[:len(cols)]
        out.append((name, sql, redundant))
    return out


def checksum(conn, table, cols, keys):
    """sha256 over every row (all columns), read in primary-key order."""
    h = hashlib.sha256()
    cur = conn.execute("SELECT {0} FROM {1} ORDER BY {2}".format(
        ", ".join(q(c) for c in cols), q(table), ", ".join(q(k) for k in keys)))
    while True:
        rows = cur.fetchmany(10000)
        if not rows:
            break
        for row in rows:
            h.update(repr(row).encode("utf-8"))
            h.update(b"\n")
    return h.hexdigest()


def rebuild(conn, table, log=print):
    """Rebuild one table WITHOUT ROWID in one transaction. -> rows copied.
    Raises (after rolling back) if anything does not match."""
    new = table + TMP_SUFFIX
    started = time.time()
    conn.execute("BEGIN IMMEDIATE")
    try:
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                           (table,)).fetchone()[0]
        cols, keys = columns(conn, table), key_columns(conn, table)
        idx = indexes(conn, table)
        conn.execute("DROP TABLE IF EXISTS {0}".format(q(new)))   # a crashed run's leftover
        conn.execute(new_table_sql(sql, table, new))
        names = ", ".join(q(c) for c in cols)
        conn.execute("INSERT INTO {0} ({1}) SELECT {1} FROM {2}".format(q(new), names, q(table)))
        before = conn.execute("SELECT count(*) FROM {0}".format(q(table))).fetchone()[0]
        after = conn.execute("SELECT count(*) FROM {0}".format(q(new))).fetchone()[0]
        if before != after:
            raise RuntimeError("{0}: {1} rows, the copy has {2}".format(table, before, after))
        if checksum(conn, table, cols, keys) != checksum(conn, new, cols, keys):
            raise RuntimeError("{0}: the copy's checksum differs from the original's".format(table))
        conn.execute("DROP TABLE {0}".format(q(table)))
        conn.execute("ALTER TABLE {0} RENAME TO {1}".format(q(new), q(table)))
        dropped = []
        for name, isql, redundant in idx:
            if redundant:
                dropped.append(name)
            else:
                conn.execute(isql)
        if not is_without_rowid(conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]):
            raise RuntimeError("{0}: the rebuilt table is not WITHOUT ROWID".format(table))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    log("  {0:<20} {1:>11,} rows  {2:5.1f}s{3}".format(
        table, before, time.time() - started,
        "  (dropped redundant index {0})".format(", ".join(dropped)) if dropped else ""))
    return before


def vacuum_space_ok(path, factor=VACUUM_SPACE_FACTOR):
    """(ok, free bytes, wanted bytes) for a VACUUM of `path`."""
    free = shutil.disk_usage(os.path.dirname(os.path.abspath(path))).free
    want = int(os.path.getsize(path) * factor)
    return free >= want, free, want


def estimate(conn, todo):
    """-> (primary-key index bytes of the tables to rebuild, unused bytes in
    the file) from dbstat, or (None, None) if this SQLite lacks it."""
    try:
        auto = {}
        for name, tbl in conn.execute(
                "SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND sql IS NULL"):
            auto[name] = tbl
        idx_bytes = unused = 0
        for name, size, free in conn.execute(
                "SELECT name, SUM(pgsize), SUM(unused) FROM dbstat GROUP BY name"):
            unused += free or 0
            if auto.get(name) in todo:
                idx_bytes += size or 0
        return idx_bytes, unused
    except sqlite3.OperationalError:
        return None, None


def mb(n):
    return "{0:,.1f} MB".format((n or 0) / 1e6)


def run(path, dry_run=False, vacuum=True, log=print):
    """Compact the store at `path`. -> 0 on success, 1 on a failure."""
    if not os.path.exists(path):
        log("no store at {0}".format(path))
        return 1
    started = time.time()
    size0 = os.path.getsize(path)
    if dry_run:
        conn = sqlite3.connect("file:{0}?mode=ro".format(path), uri=True, isolation_level=None)
    else:
        conn = sqlite3.connect(path, isolation_level=None)
    try:
        todo, skipped = plan(conn)
        log("store {0}: {1}".format(path, mb(size0)))
        for table, why in skipped:
            log("  skip {0}: {1}".format(table, why))
        if dry_run:
            idx_bytes, unused = estimate(conn, set(todo))
            log("would rebuild {0} table(s) WITHOUT ROWID:".format(len(todo)))
            for table in todo:
                rows = conn.execute("SELECT count(*) FROM {0}".format(q(table))).fetchone()[0]
                log("  {0:<20} {1:>11,} rows".format(table, rows))
            if vacuum:
                ok, free, want = vacuum_space_ok(path)
                log("then VACUUM{0}".format("" if ok else " (NOT ENOUGH DISK: {0} free, {1} wanted; "
                                            "it would be skipped)".format(mb(free), mb(want))))
            if idx_bytes is None:
                log("expected saving: unknown (this SQLite has no dbstat)")
            else:
                rebuild_saving = int(idx_bytes * REBUILD_SAVING_PER_INDEX_BYTE)
                total = rebuild_saving + (unused if vacuum else 0)
                log("expected saving: about {0} raw ({1:.0f}%): about {2} from the rebuilds "
                    "(their primary-key indexes are {3}), up to {4} unused space a VACUUM "
                    "recovers{5}".format(mb(total), 100.0 * total / size0 if size0 else 0,
                                         mb(rebuild_saving), mb(idx_bytes), mb(unused),
                                         "" if vacuum else " (not run: --no-vacuum)"))
            return 0
        log("rebuilding {0} table(s) WITHOUT ROWID, one transaction each:".format(len(todo)))
        rows = 0
        for table in todo:
            try:
                rows += rebuild(conn, table, log=log)
            except Exception as exc:                        # noqa: BLE001
                log("FAILED on {0}: {1}. That table is unchanged (rolled back); the {2} "
                    "before it stay rebuilt. Fix and rerun: done tables are skipped."
                    .format(table, exc, todo.index(table)))
                return 1
        log("  {0} table(s), {1:,} rows, in {2:.0f}s".format(len(todo), rows, time.time() - started))
        if vacuum:
            ok, free, want = vacuum_space_ok(path)
            if not ok:
                log("  [warn] VACUUM skipped: {0} free beside the store, {1} wanted. "
                    "The next db_state.py --push vacuums it.".format(mb(free), mb(want)))
            else:
                t = time.time()
                conn.execute("VACUUM")
                log("  VACUUM in {0:.0f}s".format(time.time() - t))
    finally:
        conn.close()
    size1 = os.path.getsize(path)
    log("store {0} -> {1} ({2:+.1f}%) in {3:.0f}s".format(
        mb(size0), mb(size1), 100.0 * (size1 - size0) / size0 if size0 else 0, time.time() - started))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=DB)
    ap.add_argument("--dry-run", action="store_true", help="say what would happen; change nothing")
    ap.add_argument("--no-vacuum", action="store_true", help="rebuild only")
    args = ap.parse_args(argv)
    return run(args.db, dry_run=args.dry_run, vacuum=not args.no_vacuum)


if __name__ == "__main__":
    sys.exit(main())
