#!/usr/bin/env python3
"""Rebuild the deep link for every written question in the ledger.

WHY THIS EXISTS. mp_events stores a written question as `pq:{internal id}`
and the date it was ANSWERED. Parliament's permalink is built from the date
it was TABLED plus the uin:

    /written-questions/detail/{dateTabled}/{uin}

Neither field survived ingest, so the public page could not link a written
question at all: 206 of the 1,153 rows in "Also on the record" ended with
"official written question record" as plain text, directly beneath a blurb
promising everything was "linked to the official record".

Both fields ARE in the payloads already on disk under data/raw, so this
costs nothing: no API calls, no spend, no rate limit. All 4,000 ids in the
ledger resolve from the archive.
"""

from __future__ import annotations

import glob
import gzip
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db

DETAIL = "https://questions-statements.parliament.uk/written-questions/detail/{0}/{1}"


def url_for(tabled, uin):
    return DETAIL.format(tabled, uin)


def scan(paths):
    """{pq id: (uin, tabled)} from archived written-question payloads."""
    out = {}
    for path in paths:
        try:
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                payload = json.load(fh)
        except Exception:                                  # noqa: BLE001
            # A truncated archive must not lose the other 1,039 files.
            continue
        for row in (payload.get("results") or []):
            value = row.get("value") or {}
            pid = value.get("id")
            uin = value.get("uin")
            tabled = (value.get("dateTabled") or "")[:10]
            if pid is None or not uin or not tabled:
                continue
            out.setdefault(str(pid), (str(uin), tabled))
    return out


def main():
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    need = set(r[0].split(":", 1)[1] for r in conn.execute(
        "SELECT DISTINCT ref FROM mp_events WHERE kind = 'pq' AND ref LIKE 'pq:%'"))
    print("written questions in the ledger: {0}".format(len(need)))

    found = scan(sorted(glob.glob(os.path.join(ROOT, "data", "raw", "*", "pq_*.json.gz"))))
    print("ids recoverable from the archive: {0}".format(len(found)))

    wrote = 0
    for pid in sorted(need):
        pair = found.get(pid)
        if not pair:
            continue
        conn.execute("INSERT OR REPLACE INTO pq_link (pq_id, uin, tabled) VALUES (?,?,?)",
                     (pid, pair[0], pair[1]))
        wrote += 1
    conn.commit()

    missing = len(need) - wrote
    print("linked {0} of {1} ({2:.0f}%)".format(wrote, len(need), 100.0 * wrote / max(len(need), 1)))
    if missing:
        # Stated, not swallowed: a question with no link still renders, it
        # just renders without one.
        print("NO LINK for {0} -- they render without one".format(missing))
    row = conn.execute("SELECT pq_id, tabled, uin FROM pq_link LIMIT 1").fetchone()
    if row:
        print("example: {0}".format(url_for(row["tabled"], row["uin"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
