"""Senedd questions pull: ID-walk the Record -> sd_items.

    python3 tools/sd_pull.py               # walk forward from the newest held
    python3 tools/sd_pull.py --backfill    # also walk BACKWARD to 2024-01-01

Discovery is ID-walking (docs/api-notes.md: no data API, search ignores its
query): forward from the highest stored id until MISS_RUN consecutive misses,
backward (with --backfill) until tabled dates pass the 2024-01-01 floor. A
nonexistent id serves the site shell without a "Tabled on" line; real gaps in
the sequence exist (withdrawn questions), so single misses never stop a walk.

Same rules as every watching-brief tool: sd_* tables only, never
items/mp_events, so nothing here can reach the Slack digest. Answers are kept
only for matched rows; classification runs on the question text, so a
taxonomy change re-tests everything offline (--reclassify).
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
from src.ingest import senedd

FLOOR = "2024-01-01"     # matches the NI/Holyrood windows
MISS_RUN = 40            # ids are dense; 40 straight misses = past the end
SEED_ID = 100200         # a known-real id from the probe, first-run anchor
BATCH_COMMIT = 100       # tiny transactions: the one-writer lesson


def store(conn, q, tax, wl, now):
    res = filt.filter_item(tax, wl, q.body or "")
    areas = res.issue_areas or []
    conn.execute(
        "INSERT INTO sd_items (id, kind, reference, member_name, constituency, "
        "dated, welsh, body, answered, answered_by, answer, areas, "
        "matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET answered=excluded.answered, "
        "answered_by=excluded.answered_by, answer=excluded.answer, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen",
        ("sd-question:{0}".format(q.wq_id), "question", q.reference,
         q.member_name, q.constituency, q.dated, int(q.welsh), q.body,
         q.answered, q.answered_by, (q.answer if areas else None),
         json.dumps(areas), json.dumps(res.matched_terms or []),
         res.tier, now, now))
    return bool(areas)


def walk(conn, client, tax, wl, now, start, step):
    """Walk ids from start by step; returns (stored, matched, last_real_id).

    Forward stops on MISS_RUN consecutive misses; backward stops when tabled
    dates pass FLOOR (dates are not strictly ordered by id around week
    boundaries, so the floor triggers only on a run of pre-floor dates).
    """
    stored = matched = misses = prefloor = 0
    wq_id, last_real = start, None
    while True:
        try:
            q = senedd.fetch_question(client, wq_id)
        except FetchError as exc:
            conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                         (datetime.date.today().isoformat(), "sd-questions",
                          "WQ{0}: {1}".format(wq_id, exc.cause)))
            conn.commit()
            print("  [gap] WQ{0}: {1}".format(wq_id, exc.cause))
            q = None
        if q is None:
            misses += 1
            if step > 0 and misses >= MISS_RUN:
                break
            if step < 0 and misses >= MISS_RUN:
                break
        else:
            misses = 0
            last_real = wq_id
            if step < 0 and q.dated and q.dated < FLOOR:
                prefloor += 1
                if prefloor >= 10:
                    break
            else:
                prefloor = 0
            if store(conn, q, tax, wl, now):
                matched += 1
            stored += 1
            if stored % BATCH_COMMIT == 0:
                conn.commit()
                print("  ...{0} stored (at WQ{1}, {2})".format(
                    stored, wq_id, q.dated))
        wq_id += step
    conn.commit()
    return stored, matched, last_real


def main():
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

    if "--reclassify" in sys.argv:
        changed = total = 0
        for r in conn.execute("SELECT id, body, areas FROM sd_items").fetchall():
            total += 1
            res = filt.filter_item(tax, wl, r["body"] or "")
            areas = json.dumps(res.issue_areas or [])
            conn.execute("UPDATE sd_items SET areas=?, matched_terms=?, tier=? "
                         "WHERE id=?", (areas,
                         json.dumps(res.matched_terms or []), res.tier, r["id"]))
            if areas != (r["areas"] or "[]"):
                changed += 1
        conn.commit()
        print("{0} re-tested offline; {1} changed area.".format(total, changed))
        return 0

    row = conn.execute("SELECT MAX(CAST(SUBSTR(id, 13) AS INTEGER)) "
                       "FROM sd_items").fetchone()
    top = row[0] or SEED_ID
    print("Senedd questions: walking forward from WQ{0}".format(top + 1))
    s, m, last = walk(conn, client, tax, wl, now, top + 1, +1)
    print("forward: {0} stored, {1} match our areas (last real WQ{2}).".format(
        s, m, last))

    if "--backfill" in sys.argv:
        low = conn.execute("SELECT MIN(CAST(SUBSTR(id, 13) AS INTEGER)) "
                           "FROM sd_items").fetchone()[0] or (SEED_ID + 1)
        print("backfill: walking backward from WQ{0} to {1}".format(
            low - 1, FLOOR))
        s, m, last = walk(conn, client, tax, wl, now, low - 1, -1)
        print("backward: {0} stored, {1} match our areas.".format(s, m))

    total = conn.execute("SELECT COUNT(*) FROM sd_items").fetchone()[0]
    ours = sum(1 for r in conn.execute("SELECT areas FROM sd_items")
               if r[0] and r[0] != "[]")
    print("\n{0} question(s) in sd_items, {1} on our ground. Not in `items`, "
          "so structurally cannot reach the Slack digest.".format(total, ours))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
