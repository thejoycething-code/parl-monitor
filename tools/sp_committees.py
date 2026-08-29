"""Holyrood committee scrutiny: MSP contributions in committee, classified.

    python3 tools/sp_committees.py               # current year (the weekly)
    python3 tools/sp_committees.py --backfill    # every year since 2024
    python3 tools/sp_committees.py --year 2025

The committee Official Report (`Orscommitteemeeting?year=N`) works for 2025
and 2026 even though the apilist stops advertising it at 2024 -- same row
shape as the plenary OR plus a Committee block. MSP contributions whose text
passage-matches the taxonomy land in sp_events with an `occ` key prefix and
a "Committee -- item" heading; classification runs on the ITEM heading only,
never the committee's own name. Witnesses and officials (null Person block)
are counted and skipped: the ledger records MSP activity.

Watching brief: writes sp_* tables only, never items/mp_events, so nothing
here can reach the published digest. ONE WRITER AT A TIME on
data/parl-monitor.db.
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
from src.ingest import holyrood

FIRST_YEAR = 2024   # matches sp_pull.MOTIONS_SINCE / sp_divisions.FIRST_YEAR
BATCH_COMMIT = 500


def main():
    today = datetime.date.today()
    if "--year" in sys.argv:
        years = [int(sys.argv[sys.argv.index("--year") + 1])]
    elif "--backfill" in sys.argv:
        years = list(range(FIRST_YEAR, today.year + 1))
    else:
        years = [today.year]

    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    now = today.isoformat()

    seen = msp = stored = gaps = 0
    committees = set()
    for year in years:
        try:
            payload = holyrood.fetch_committee_or(client, year)
        except FetchError as exc:
            conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) "
                         "VALUES (?,?,?)",
                         (now, "sp-committee-or",
                          "year {0}: {1}".format(year, exc.cause)))
            conn.commit()
            print("  [gap] committee OR {0}: {1}".format(year, exc.cause))
            gaps += 1
            continue
        seen += len(payload or [])
        pending = 0
        for sp in holyrood.parse_committee_speeches(payload):
            msp += 1
            matches = filt.match_passages(tax, wl, sp.text,
                                          title=sp.heading or "")
            if not matches:
                continue
            areas, terms, excerpt = filt.aggregate_passages(matches)
            if not areas:
                continue
            heading = "{0} -- {1}".format(sp.committee or "?",
                                          sp.heading or "?")
            conn.execute(
                "INSERT INTO sp_events (key, person_id, dated, heading, "
                "areas, matched_terms, excerpt, first_seen, last_seen) "
                "VALUES (?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET areas=excluded.areas, "
                "matched_terms=excluded.matched_terms, "
                "excerpt=excluded.excerpt, heading=excluded.heading, "
                "last_seen=excluded.last_seen",
                (sp.key, sp.person_id, sp.dated, heading,
                 json.dumps(areas), json.dumps(terms), excerpt, now, now))
            if sp.committee:
                committees.add(sp.committee)
            stored += 1
            pending += 1
            if pending >= BATCH_COMMIT:
                conn.commit()
                pending = 0
        conn.commit()
        print("{0}: {1} contribution(s) seen, {2} matched so far."
              .format(year, seen, stored))

    print("\n{0} committee contribution(s) read; {1} by MSPs ({2} witness/"
          "official rows skipped -- the ledger records MSP activity)."
          .format(seen, msp, seen - msp))
    print("{0} passage-matched event(s) stored in sp_events (occ keys) "
          "across {1} committee(s) -- ACTIVITY ONLY, never direction."
          .format(stored, len(committees)))
    print("no gaps." if not gaps else
          "{0} gap(s) -- printed above.".format(gaps))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
