"""Which past Commons divisions would the clause-text path now flag?

    python3 tools/check_clause_text.py [since] [until]

(PARL_DB=<path> reads another store, e.g. the main checkout's from a worktree.)

Read-only over cv_divisions (every Commons division of this Parliament,
tools/pull_division_rolls.py): for each division whose TITLE matches nothing
but names a clause ("Health Bill: Report Stage: New Clause 142"), read the
clause from the Bills API and run the taxonomy over it (src/clausetext.py).
Prints the divisions it would flag -- the votes the title sweep missed -- and
the ones whose clause text could not be read, which are NOT no-matches.

The store is opened read-only (mode=ro), so nothing is cached there; a run
re-reads the Bills API, one search and one stage list per Bill plus one
amendment list per stage, held in memory for the run. Nothing is published.
"""

from __future__ import annotations

import datetime
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import clausetext, filter as filt, intel
from src.http import HttpClient


def scan(rows, reader, tax, wl):
    """(flagged, gaps) over (division_id, date, title) rows."""
    flagged, gaps = [], []
    for did, date, title in rows:
        title = " ".join((title or "").split())
        if filt.filter_item(tax, wl, title).matched():
            continue                    # the title sweep already sees it
        lk = reader.lookup(title, date, "Commons", None, did)
        if lk.gap:
            gaps.append((did, date, title, lk.gap))
        result, labels = clausetext.match(lk, tax, wl)
        if labels:
            flagged.append({"id": did, "date": date, "title": title, "clauses": labels,
                            "areas": result.issue_areas, "tier": result.tier,
                            "terms": result.matched_terms + result.watchlist_hits,
                            "why": clausetext.describe(lk, labels),
                            "ledger": clausetext.ledger_ok(lk, labels, tax, wl)})
    return flagged, gaps


def main():
    until = sys.argv[2] if len(sys.argv) > 2 else datetime.date.today().isoformat()
    since = sys.argv[1] if len(sys.argv) > 1 else (
        datetime.date.fromisoformat(until) - datetime.timedelta(days=183)).isoformat()
    path = os.environ.get("PARL_DB") or os.path.join(ROOT, "data", "parl-monitor.db")
    conn = sqlite3.connect("file:{0}?mode=ro".format(path), uri=True)
    rows = conn.execute("SELECT division_id, date, title FROM cv_divisions "
                        "WHERE date BETWEEN ? AND ? ORDER BY date, division_id",
                        (since, until)).fetchall()
    conn.close()
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    # archive=False on every list call; detail calls archive under a scratch
    # dir, never data/raw, because this is a check, not a pull.
    client = HttpClient(raw_dir=os.environ.get("CLAUSE_CHECK_RAW", "/tmp/clause-check-raw"))
    reader = clausetext.ClauseReader(client, None)
    print("{0} Commons divisions {1} to {2}".format(len(rows), since, until))
    flagged, gaps = scan(rows, reader, tax, wl)
    print("\n{0} would now be flagged on clause text:".format(len(flagged)))
    for f in flagged:
        print("  id {0:5}  {1}  {2}".format(f["id"], f["date"], f["title"]))
        print("        {0} | tier {1}{3} | areas: {2}".format(
            ", ".join(f["terms"]), f["tier"],
            ", ".join("{0} {1}".format(a, names.get(a, "")) for a in f["areas"]),
            "" if f["ledger"] or f["tier"] != 1 else " (body only: stored, not ledgered)"))
        print("        {0}".format(f["why"]))
    print("\n{0} name a clause that could not be read (NOT a no-match):".format(len(gaps)))
    for did, date, title, gap in gaps:
        print("  id {0:5}  {1}  {2}\n        {3}".format(did, date, title[:80], gap))
    return 0


if __name__ == "__main__":
    sys.exit(main())
