"""Discover draft resolutions for a session, and report the new ones.

    python3 tools/un_drafts.py                 # Third Committee, current session
    python3 tools/un_drafts.py --hrc 63        # HRC session 63
    python3 tools/un_drafts.py --max 40        # cap the walk

Draft resolutions are where the text of a fight actually lives -- the family
language, the SRHR language, the mandate renewals. They are numbered
sequentially within a session, so the set is discovered by walking L.1 upward
until the misses run on.

SLOW BY NATURE: about 10 seconds per symbol, and that is the server's
redirect-and-lookup time, not transfer (a Range request already cuts each
check to 64 bytes). Eighty drafts is roughly thirteen minutes, which is fine
for a scheduled job and wrong for an interactive one.

Subjects come from the PDF via pypdf, so each draft is put through the UN
taxonomy and reported with its area. A draft nobody can classify is just a
symbol; a draft tagged "area 6" is a thing to act on.
"""

from __future__ import annotations

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt
from src.http import HttpClient
from src.ingest import un_docs

GA_EPOCH = 1945


def store(conn, rows, body, session, today):
    """rows: (Document, Draft, areas). Returns the ones not seen before."""
    before = {r["symbol"] for r in conn.execute("SELECT symbol FROM un_documents")}
    import json
    for doc, draft, areas in rows:
        conn.execute(
            "INSERT INTO un_documents (symbol, body, session, url, size, "
            "agenda_item, subject, kind, dated, areas, first_seen, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            # first_seen never moves on a re-read; the rest refresh, because a
            # draft can be revised in place.
            "ON CONFLICT(symbol) DO UPDATE SET url=excluded.url, "
            "agenda_item=excluded.agenda_item, subject=excluded.subject, "
            "kind=excluded.kind, dated=excluded.dated, areas=excluded.areas, "
            "last_seen=excluded.last_seen",
            (doc.symbol, body, session, doc.url, doc.size,
             draft.agenda_item, draft.subject, draft.kind, draft.dated,
             json.dumps(areas), today, today))
    conn.commit()
    return [r for r in rows if r[0].symbol not in before]


def main():
    argv = sys.argv[1:]
    hrc = "--hrc" in argv
    max_n = int(argv[argv.index("--max") + 1]) if "--max" in argv else 120
    today = datetime.date.today()
    if hrc:
        idx = argv.index("--hrc")
        session = int(argv[idx + 1]) if len(argv) > idx + 1 and argv[idx + 1].isdigit() else 63
        pattern, body = un_docs.HRC_DRAFTS, "Human Rights Council"
    else:
        # The GA session opening in September of year Y is Y - 1945.
        session = today.year - GA_EPOCH
        pattern, body = un_docs.THIRD_COMMITTEE_DRAFTS, "Third Committee"

    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    print("walking {0} session {1} (up to L.{2}); ~10s per symbol"
          .format(body, session, max_n), flush=True)
    docs, checked = un_docs.enumerate_drafts(client, pattern, session, max_n=max_n)
    print("{0} draft(s) found from {1} checks".format(len(docs), checked))
    if not docs:
        print("none yet -- drafts appear once the session is under way, and "
              "this is not an error during recess.")
        return 0

    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "un-taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    print("reading subjects (one fetch each)...", flush=True)
    rows = []
    for doc in docs:
        try:
            text = un_docs.document_text(client, doc.symbol, pages=1)
        except Exception as exc:
            print("  {0}: could not read ({1})".format(doc.symbol, str(exc)[:50]))
            rows.append((doc, un_docs.Draft(symbol=doc.symbol), []))
            continue
        draft = un_docs.parse_draft(doc.symbol, text)
        areas = filt.filter_item(tax, wl, draft.subject or "").issue_areas
        rows.append((doc, draft, areas))

    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    fresh = store(conn, rows, body, session, today.isoformat())

    ours = [r for r in rows if r[2]]
    print("\n{0} draft(s), {1} touching our areas".format(len(rows), len(ours)))
    for doc, draft, areas in rows:
        mark = "OURS" if areas else "    "
        print("{0}  {1:<16} item {2:<5} {3}".format(
            mark, doc.symbol, draft.agenda_item or "-", (draft.subject or "?")[:52]))
        if areas:
            print("        areas {0}  {1}".format(
                ",".join(str(a) for a in areas), doc.url))
    print("\nNEW since the last run: {0}".format(len(fresh)))
    for doc, draft, _areas in fresh:
        print("  {0}  {1}".format(doc.symbol, (draft.subject or "?")[:60]))
    if not fresh:
        print("  (all of these were already known)")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
