"""Devolved petitions -> dv_petitions + weekly signature snapshots.

    python3 tools/dv_petitions.py --nation wales
    python3 tools/dv_petitions.py --nation scotland

Christopher, 2026-09-07: "Devolved petitions. Holyrood and Senedd petition
systems, now that Westminster's is collated." Collated only, like
Westminster's: never items, never judged, never in the edition; they
surface on the companion page. Runs in the Senedd and Holyrood weeklies,
which hold the store lock. Precision gate as for Westminster: tier 1 or a
watchlist name, or tier 2 once past the referral threshold (Senedd 250;
Holyrood has no signature threshold, so tier 2 needs 250 signatures too).
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
from src.ingest import dv_petitions

TIER2_FLOOR = 250


def sweep(nation, client, conn, tax, wl, today, log=print):
    fetch = dv_petitions.fetch_senedd if nation == "wales" else dv_petitions.fetch_scotland
    try:
        rows = fetch(client)
    except FetchError as exc:
        conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?, ?, ?)",
                     (today.isoformat(), "dv_petition", "{0}: petitions unreachable ({1})".format(nation, exc.cause)))
        conn.commit()
        log("{0} petitions: unreachable ({1}) -- gap recorded".format(nation, exc.cause))
        return 0
    n = 0
    for p in rows:
        r = filt.filter_item(tax, wl, p.action, p.text)
        if not r.matched():
            continue
        if not (r.tier == 1 or r.watchlist_hits) and p.signatures < TIER2_FLOOR:
            continue
        n += 1
        conn.execute("INSERT OR REPLACE INTO dv_petition_snapshots (key, captured_at, signatures) VALUES (?,?,?)",
                     (p.key, today.isoformat(), p.signatures))
        conn.execute(
            "INSERT INTO dv_petitions (key, nation, id, action, url, state, signatures, areas, matched, tier, opened, "
            "closes, milestone, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET action=excluded.action, state=excluded.state, signatures=excluded.signatures, "
            "areas=excluded.areas, matched=excluded.matched, tier=excluded.tier, closes=excluded.closes, "
            "milestone=excluded.milestone, last_seen=excluded.last_seen",
            (p.key, p.nation, p.id, p.action, p.url, p.state, p.signatures, json.dumps(r.issue_areas),
             json.dumps(r.matched_terms + r.watchlist_hits), r.tier, p.opened, p.closes, p.milestone(),
             today.isoformat(), today.isoformat()))
    conn.commit()
    log("{0} petitions: {1} live, {2} on our ground (collated, not judged)".format(nation, len(rows), n))
    return n


def main():
    if "--nation" not in sys.argv:
        print(__doc__)
        return 2
    nation = sys.argv[sys.argv.index("--nation") + 1]
    if nation not in ("wales", "scotland"):
        print("unknown nation: {0} (wales|scotland)".format(nation))
        return 2
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    sweep(nation, client, conn, tax, wl, datetime.date.today())
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
