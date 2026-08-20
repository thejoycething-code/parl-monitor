"""Holyrood divisions and per-MSP votes -> sp_divisions / sp_votes.

    python3 tools/sp_divisions.py                 # years 2024..today
    python3 tools/sp_divisions.py --year 2026     # one year

Same rules as every sp_/ni_ tool: its own tables, never items/mp_events, so
nothing here can reach the Slack digest; every failed source is a printed gap.

Classification is an exact-key join, not text matching: a division's reference
('S7M-00469.5') is itself a motion row in the dump, whose full text sp_pull.py
already stored. The division inherits areas from that row's own wording. A
division whose reference is NOT in sp_items (a pre-2024 motion, or sp_pull not
yet run for the period) is stored unclassified and COUNTED, never guessed.
"""

from __future__ import annotations

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db
from src.http import FetchError, HttpClient
from src.ingest import holyrood

FIRST_YEAR = 2024   # matches sp_pull.MOTIONS_SINCE


def main():
    years = list(range(FIRST_YEAR, datetime.date.today().year + 1))
    if "--year" in sys.argv:
        years = [int(sys.argv[sys.argv.index("--year") + 1])]
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))

    # The join table: reference -> (item id, areas, terms, tier).
    by_ref = {r["reference"]: r for r in conn.execute(
        "SELECT id, reference, areas, matched_terms, tier FROM sp_items "
        "WHERE kind='motion' AND reference IS NOT NULL")}

    stored = voted = unlinked = gaps = 0
    for year in years:
        try:
            divisions = holyrood.fetch_votes(client, year)
        except FetchError as exc:
            conn.execute("INSERT INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                         (datetime.date.today().isoformat(), "sp-votes",
                          "year {0}: {1}".format(year, exc.cause)))
            conn.commit()
            print("  [gap] votes {0}: {1}".format(year, exc.cause))
            gaps += 1
            continue
        for d in divisions:
            item = by_ref.get(d.reference)
            if item is None:
                unlinked += 1
            conn.execute(
                "INSERT INTO sp_divisions (key, reference, title, dated, "
                "session, vote_for, vote_against, result, item_id, areas, "
                "matched_terms, tier, first_seen, last_seen) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET vote_for=excluded.vote_for, "
                "vote_against=excluded.vote_against, result=excluded.result, "
                "item_id=excluded.item_id, areas=excluded.areas, "
                "matched_terms=excluded.matched_terms, tier=excluded.tier, "
                "last_seen=excluded.last_seen",
                (d.key, d.reference, d.title, d.date, d.session,
                 d.vote_for, d.vote_against, d.result,
                 item["id"] if item else None,
                 item["areas"] if item else None,
                 item["matched_terms"] if item else None,
                 item["tier"] if item else None, now, now))
            for v in d.votes:
                conn.execute(
                    "INSERT OR REPLACE INTO sp_votes (division_key, person_id, "
                    "vote, party, shares_party) VALUES (?,?,?,?,?)",
                    (d.key, v.person_id, v.vote, v.party, v.shares_party))
                # The vote row carries ConstituencyRegion; sp_members has no
                # other source for it. Latest vote wins, which is right: a
                # member's seat is whatever they last sat for.
                if v.constituency:
                    conn.execute(
                        "UPDATE sp_members SET constituency=? WHERE person_id=?",
                        (v.constituency, v.person_id))
                voted += 1
            stored += 1
        conn.commit()
        print("{0}: {1} division(s) so far.".format(year, stored))

    import json
    ours = conn.execute(
        "SELECT COUNT(*) FROM sp_divisions WHERE areas IS NOT NULL "
        "AND areas != '[]'").fetchone()[0]
    print("\n{0} division(s) stored, {1} vote position(s); {2} on our ground "
          "by their own motion's wording.".format(stored, voted, ours))
    if unlinked:
        print("{0} division(s) reference a motion NOT in sp_items (pre-{1} or "
              "sp_pull not yet run) -- stored unclassified, never guessed."
              .format(unlinked, FIRST_YEAR))
    print("no gaps." if not gaps else "{0} gap(s) -- printed above.".format(gaps))
    print("\nWritten to sp_divisions/sp_votes, not `items`: structurally "
          "cannot reach the Slack digest.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
