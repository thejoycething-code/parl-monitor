#!/usr/bin/env python3
"""Re-apply the German taxonomy to stored rows -- ADDING areas, never removing.

    python3 tools/de_retag.py --dry-run     # what would change
    python3 tools/de_retag.py               # apply

Written for v0.5 (26 September 2026), and kept because every taxonomy change
needs it: a new term reaches only rows collected AFTER it joined unless
something goes back over the ones already held.

ADDITIVE ONLY, and that is the whole design. Each table was classified at
ingest from MORE text than this can re-read -- a speech from its full body,
not the 300-character excerpt the table keeps; a division from its label,
its topics and the document it inherits from. Re-deriving areas from the
stored field alone and writing the result back would have CLEARED 52
correct tags on the first run, which is the same trap that nearly cleared
34 Westminster PQ tags on 6 September. So an area is only ever added: a
match on the stored field is also a match on the fuller text it came from,
because the stored field is part of that text.

What this cannot do is REMOVE a tag a term no longer earns. If a term is
ever narrowed or dropped, the rows it tagged need re-reading from their full
source, not this.

Rows that gain their first area become pending for tools/de_triage.py,
which scores them on its next run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt  # noqa: E402

# table -> (primary key, the stored text field to re-read)
SOURCES = {
    "de_vorgaenge": ("vorgang_id", "titel"),
    "de_committee_reports": ("doc_id", "titel"),
    "de_divisions": ("vote_id", "label"),
    "de_petitions": ("petition_id", "title"),
    "de_judgments": ("case_no", "subject"),
    "de_amendments": ("doc_id", "titel"),
    "de_speeches": ("speech_id", "excerpt"),
}


def retag(conn, tax, wl, dry_run=False):
    """-> [(table, key, added areas, terms)] for every row that would grow."""
    changes = []
    for table, (key, field) in SOURCES.items():
        cols = {r[1] for r in conn.execute("PRAGMA table_info({0})".format(table))}
        if field not in cols or "areas" not in cols:
            continue
        has_terms = "matched_terms" in cols
        rows = conn.execute("SELECT {0} AS k, {1} AS t, areas{2} FROM {3}".format(
            key, field, ", matched_terms" if has_terms else "", table)).fetchall()
        for r in rows:
            stored = set(json.loads(r["areas"] or "[]"))
            res = filt.filter_item(tax, wl, r["t"] or "", "", "")
            added = set(res.issue_areas) - stored
            if not added:
                continue
            changes.append((table, r["k"], sorted(added), res.matched_terms))
            if dry_run:
                continue
            terms = set(json.loads(r["matched_terms"] or "[]")) if has_terms else set()
            sets = "areas = ?" + (", matched_terms = ?" if has_terms else "")
            args = [json.dumps(sorted(stored | added))]
            if has_terms:
                args.append(json.dumps(sorted(terms | set(res.matched_terms)),
                                       ensure_ascii=False))
            conn.execute("UPDATE {0} SET {1} WHERE {2} = ?".format(table, sets, key),
                         args + [r["k"]])
    if not dry_run:
        conn.commit()
    return changes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy-de.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist-de.yaml"))
    changes = retag(conn, tax, wl, dry_run=args.dry_run)
    for table, key, added, terms in changes:
        print("  {0:<22} {1:<14} +area {2}  via {3}".format(
            table, str(key)[:14], added, ", ".join(terms[:2])))
    print("de-retag: {0} row(s) gain an area under taxonomy v{1}; none lose one{2}".format(
        len(changes), tax.version, " (dry run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
