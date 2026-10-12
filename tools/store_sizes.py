"""How big is each table in the store? Read-only.

    python3 tools/store_sizes.py                 # top 30 tables, then totals
    python3 tools/store_sizes.py --top 0         # every table
    python3 tools/store_sizes.py --groups        # summed by table prefix (fr_, ca_, ...)
    python3 tools/store_sizes.py --json          # the same numbers for a script
    python3 tools/store_sizes.py --db PATH       # another store file

Why. The store is published as one gzipped release asset, and GitHub caps
one asset at 2 GiB (tools/db_state.py). docs/store-split-plan.md decides
when and how to split it; this prints the numbers that plan is measured
in, so the trigger can be checked without opening sqlite3 by hand.

Bytes per table come from SQLite's dbstat virtual table and INCLUDE the
table's indexes (a vote table's primary-key index can be as large as the
table). "unused" is space inside pages that holds nothing: a VACUUM gives
most of it back. The store is opened read-only (mode=ro), so running this
beside a job never changes a byte or takes a write lock.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "parl-monitor.db")


def open_ro(path):
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    return sqlite3.connect("file:{0}?mode=ro".format(path), uri=True)


def measure(path):
    """-> {"file_bytes", "page_size", "pages", "free_pages", "unused_bytes",
    "index_bytes", "tables": [{name, bytes, table_bytes, index_bytes, rows}]}
    with tables largest first. Raises sqlite3.OperationalError if this
    SQLite was built without dbstat."""
    conn = open_ro(path)
    try:
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        pages = conn.execute("PRAGMA page_count").fetchone()[0]
        free = conn.execute("PRAGMA freelist_count").fetchone()[0]
        owner = {name: (tbl or name) for name, tbl in conn.execute(
            "SELECT name, tbl_name FROM sqlite_master WHERE type IN ('table', 'index')")}
        per = {}
        unused_total = 0
        for name, size, unused in conn.execute(
                "SELECT name, SUM(pgsize), SUM(unused) FROM dbstat GROUP BY name"):
            unused_total += unused or 0
            table = owner.get(name, name)
            entry = per.setdefault(table, {"name": table, "bytes": 0, "table_bytes": 0,
                                           "index_bytes": 0, "rows": None})
            entry["bytes"] += size or 0
            entry["table_bytes" if table == name else "index_bytes"] += size or 0
        kinds = dict(conn.execute("SELECT name, type FROM sqlite_master"))
        for table, entry in per.items():
            if kinds.get(table) == "table":
                entry["rows"] = conn.execute(
                    'SELECT count(*) FROM "{0}"'.format(table.replace('"', '""'))).fetchone()[0]
        tables = sorted(per.values(), key=lambda e: (-e["bytes"], e["name"]))
        return {"file_bytes": os.path.getsize(path), "page_size": page_size, "pages": pages,
                "free_pages": free, "unused_bytes": unused_total,
                "index_bytes": sum(e["index_bytes"] for e in tables), "tables": tables}
    finally:
        conn.close()


def prefix(name):
    """fr_votes -> fr; items -> items (an unprefixed UK or shared table)."""
    return name.split("_", 1)[0] if "_" in name else name


def groups(tables):
    """[{group, bytes, tables}] summed by prefix, largest first."""
    out = {}
    for entry in tables:
        g = out.setdefault(prefix(entry["name"]), {"group": prefix(entry["name"]),
                                                   "bytes": 0, "tables": 0})
        g["bytes"] += entry["bytes"]
        g["tables"] += 1
    return sorted(out.values(), key=lambda g: (-g["bytes"], g["group"]))


def mb(n):
    return "{0:,.1f}".format((n or 0) / 1e6)


def render(stats, top=30, by_group=False):
    lines = []
    if by_group:
        lines.append("{0:<24} {1:>10} {2:>7}".format("prefix", "MB", "tables"))
        for g in groups(stats["tables"]):
            lines.append("{0:<24} {1:>10} {2:>7}".format(g["group"], mb(g["bytes"]), g["tables"]))
    else:
        lines.append("{0:<32} {1:>9} {2:>9} {3:>12}".format("table", "MB", "index MB", "rows"))
        shown = stats["tables"] if not top else stats["tables"][:top]
        for e in shown:
            rows = "" if e["rows"] is None else "{0:,}".format(e["rows"])
            lines.append("{0:<32} {1:>9} {2:>9} {3:>12}".format(
                e["name"], mb(e["bytes"]), mb(e["index_bytes"]), rows))
        if top and len(stats["tables"]) > top:
            rest = stats["tables"][top:]
            lines.append("{0:<32} {1:>9}".format("({0} more)".format(len(rest)),
                                                 mb(sum(e["bytes"] for e in rest))))
    used = stats["pages"] * stats["page_size"]
    lines.append("")
    lines.append("file {0} MB; indexes {1} MB ({2:.0f}%); unused inside pages {3} MB ({4:.1f}%); "
                 "free pages {5}".format(
                     mb(stats["file_bytes"]), mb(stats["index_bytes"]),
                     100.0 * stats["index_bytes"] / used if used else 0,
                     mb(stats["unused_bytes"]),
                     100.0 * stats["unused_bytes"] / used if used else 0, stats["free_pages"]))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=DB)
    ap.add_argument("--top", type=int, default=30, help="tables to list (0: all)")
    ap.add_argument("--groups", action="store_true", help="sum by table prefix")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        stats = measure(args.db)
    except FileNotFoundError:
        print("no store at {0}".format(args.db))
        return 1
    except sqlite3.OperationalError as exc:
        print("cannot measure {0}: {1} (this SQLite may lack dbstat)".format(args.db, exc))
        return 1
    if args.json:
        if args.groups:
            stats = dict(stats, groups=groups(stats["tables"]))
        print(json.dumps(stats, indent=2))
    else:
        print(render(stats, top=args.top, by_group=args.groups))
    return 0


if __name__ == "__main__":
    sys.exit(main())
