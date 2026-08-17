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

Titles are NOT available: they are in the PDF body in subset fonts, which
stdlib cannot decode. This reports that a draft exists and links to it.
"""

from __future__ import annotations

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db
from src.http import HttpClient
from src.ingest import un_docs

GA_EPOCH = 1945


def store(conn, docs, body, session, today):
    before = {r["symbol"] for r in conn.execute("SELECT symbol FROM un_documents")}
    for d in docs:
        conn.execute(
            "INSERT INTO un_documents (symbol, body, session, url, size, "
            "first_seen, last_seen) VALUES (?, ?, ?, ?, ?, ?, ?) "
            # first_seen never moves on a re-read; last_seen always does.
            "ON CONFLICT(symbol) DO UPDATE SET url=excluded.url, "
            "last_seen=excluded.last_seen",
            (d.symbol, body, session, d.url, d.size, today, today))
    conn.commit()
    return [d for d in docs if d.symbol not in before]


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

    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    fresh = store(conn, docs, body, session, today.isoformat())
    print("NEW since the last run: {0}".format(len(fresh)))
    for d in fresh:
        print("  {0}  {1}".format(d.symbol, d.url))
    if not fresh:
        print("  (all of these were already known)")
    conn.close()
    print("\nTitles are not available: they live in the PDF body in subset "
          "fonts that stdlib cannot decode. Open the link to read one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
