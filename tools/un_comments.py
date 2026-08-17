"""General comments from the treaty bodies: how a treaty gets reinterpreted.

    python3 tools/un_comments.py

General Comment 36 read abortion into the right to life. That outlasts any
resolution, because it becomes the lens every future review applies -- which
makes this the most consequential feed here and the last one to be built.

Flagged by COMMITTEE rather than keyword: the listing truncates titles, so
CEDAW, CRC and CCPR are treated as our ground by definition.

WHAT THIS IS NOT: the consultation window. Draft general comments go out for
public comment before adoption and that is the campaignable moment, but every
OHCHR page listing open consultations answers 403 to a non-browser client. This
tells you what the treaty bodies have DECIDED, not what they are deciding.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt
from src.http import FetchError, HttpClient
from src.ingest import treaty_comments


def main():
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "un-taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    try:
        comments = treaty_comments.fetch_general_comments(client)
    except FetchError as exc:
        print("treaty body search failed: {0}".format(exc.cause))
        return 1
    if not comments:
        print("parsed ZERO general comments. The document search layout has "
              "probably changed -- check before believing none exist.")
        return 1

    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    before = {r["symbol"] for r in conn.execute("SELECT symbol FROM un_documents")}
    today = datetime.date.today().isoformat()
    for gc in comments:
        # Title keywords still run, so a CMW comment that plainly touches our
        # ground is not thrown away just because its committee is not ours.
        areas = filt.filter_item(tax, wl, gc.title).issue_areas
        conn.execute(
            "INSERT INTO un_documents (symbol, body, url, kind, title, dated, "
            "areas, event, first_seen, last_seen) "
            "VALUES (?, ?, ?, 'general comment', ?, ?, ?, 'interpretation', ?, ?) "
            "ON CONFLICT(symbol) DO UPDATE SET title=excluded.title, "
            "areas=excluded.areas, last_seen=excluded.last_seen",
            (gc.symbol, gc.treaty, gc.url, gc.title, gc.year,
             json.dumps(areas), today, today))
    conn.commit()

    fresh = [g for g in comments if g.symbol not in before]
    print("{0} general comment(s) listed\n".format(len(comments)))
    for gc in comments:
        mark = "OURS" if gc.ours else "    "
        print("{0}  {1:<14} {2:<5} {3}".format(
            mark, gc.symbol, gc.year or "-", gc.title[:56]))
    print("\n{0} from our committees (CEDAW/CRC/CCPR).".format(
        sum(1 for g in comments if g.ours)))
    print("NEW since the last run: {0}".format(len(fresh)))
    for gc in fresh:
        print("  {0}  {1}".format(gc.symbol, gc.title[:60]))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
