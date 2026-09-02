"""ECI watch: European Citizens' Initiatives on our ground.

    python3 tools/eu_eci.py

The gap Christopher's "something must be missing" question surfaced
(2026-09-02): the EU monitor watched the Commission and the Parliament
but not the CITIZENS' instrument -- and an ECI is both a threat ("My
Voice, My Choice" seeks EU-funded abortion access) and CitizenGO's own
natural battlefield, since an initiative crossing 1M validated
signatures forces a Commission response.

Source: the ECI register's JSON API (register.eci.ec.europa.eu), probed
live -- id, title, status, totalSupporters, support link. One call per
status per week; titles taxonomy-matched; supporter counts tracked so
the edition can say "grew 40,000 this week" about a hostile initiative.

Separation guarantee: writes eu_ecis only.
ONE WRITER AT A TIME on data/parl-monitor.db.
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

# ONGOING = collecting signatures (the live battlefield); ANSWERED and
# VERIFICATION carry recent history the edition may reference.
SEARCH = ("https://register.eci.ec.europa.eu/core/api/register/search/"
          "{0}/EN/0/200")
# VERIFICATION is not a register search status (400, measured live);
# ONGOING is the battlefield and ANSWERED the recent history.
STATUSES = ("ONGOING", "ANSWERED")


def pull(conn, client, today, log=print):
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    n = ours = gaps = 0
    for status in STATUSES:
        try:
            reply = client.get_json(SEARCH.format(status), "eu-eci",
                                    status.lower(), archive=False)
        except (FetchError, ValueError) as exc:
            conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) "
                         "VALUES (?,?,?)",
                         (today, "eu-eci", "{0}: {1}".format(status, exc)))
            log("  [gap] eci {0}: {1}".format(status, exc))
            gaps += 1
            continue
        for e in reply.get("entries") or []:
            title = e.get("title") or ""
            res = filt.filter_item(tax, wl, title)
            areas = res.issue_areas or []
            if areas:
                ours += 1
            n += 1
            prev = conn.execute("SELECT supporters FROM eu_ecis WHERE "
                                "reg_num = ?",
                                (e.get("pubRegNum"),)).fetchone()
            conn.execute(
                "INSERT INTO eu_ecis (reg_num, title, status, supporters, "
                "prev_supporters, support_link, areas, matched_terms, tier, "
                "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(reg_num) DO UPDATE SET title=excluded.title, "
                "status=excluded.status, "
                "prev_supporters=eu_ecis.supporters, "
                "supporters=excluded.supporters, "
                "areas=excluded.areas, matched_terms=excluded.matched_terms, "
                "tier=excluded.tier, last_seen=excluded.last_seen",
                (e.get("pubRegNum"), title, e.get("status"),
                 e.get("totalSupporters"),
                 prev["supporters"] if prev else None,
                 e.get("supportLink"), json.dumps(areas),
                 json.dumps(res.matched_terms or []), res.tier, today,
                 today))
    conn.commit()
    return n, ours, gaps


def main():
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    today = datetime.date.today().isoformat()
    n, ours, gaps = pull(conn, client, today)
    print("eu-eci: {0} initiative(s) across {1} statuses, {2} on our "
          "ground; {3} gap(s).".format(n, len(STATUSES), ours, gaps))
    for r in conn.execute("SELECT * FROM eu_ecis WHERE areas != '[]' "
                          "ORDER BY supporters DESC").fetchall():
        delta = ""
        if r["prev_supporters"] is not None and r["supporters"] is not None:
            d = r["supporters"] - r["prev_supporters"]
            if d:
                delta = " ({0}{1} since last pull)".format(
                    "+" if d > 0 else "", d)
        print("  [{0}] {1} - {2} - {3:,} supporters{4}".format(
            ",".join(str(a) for a in json.loads(r["areas"])),
            r["status"], (r["title"] or "")[:60], r["supporters"] or 0,
            delta))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
