"""Devolved government consultations: open calls in Scotland, Wales and NI.

    python3 tools/dg_consultations.py                 # all three nations
    python3 tools/dg_consultations.py --nation wales

Executive consultations (governments, not parliaments), so they live in
their own dg_consultations table and surface in each nation's monitor --
never in items/mp_events, so nothing here can reach the published digest.

Fetch discipline: listings are cheap; the closing date lives only on the
detail page, so each NEW consultation costs one detail fetch and a key
already holding a closing date is never refetched. Everything is stored
(the open sets are small); classification runs on title + listing summary
and marks OURS in the monitors. All pages fetch with archive=False -- the
db is the archive, and gov.wales detail pages are 240KB each.

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
from src.ingest import devolved

WALES_MAX_PAGES = 10    # ~5 pages of open consultations in 2026; cap, don't spin


def fetch_open(client, nation, log):
    if nation in ("scotland", "ni"):
        url = devolved.SOURCES[nation]
        host = url.split("/consultation_finder")[0]
        html = client.get_text(url, "dg-consultations", nation, archive=False)
        return devolved.parse_citizen_space_finder(html, nation, host)
    out, page = [], 0
    while page < WALES_MAX_PAGES:
        html = client.get_text(devolved.SOURCES["wales"].format(page),
                               "dg-consultations", "wales-p{0}".format(page),
                               archive=False)
        batch = devolved.parse_govwales_index(html)
        if not batch:
            break
        out.extend(batch)
        page += 1
    else:
        log("  [gap] wales listing still returning items at page {0} -- "
            "capped, later pages unseen".format(WALES_MAX_PAGES))
    return out


def main():
    nations = ["scotland", "wales", "ni"]
    if "--nation" in sys.argv:
        nations = [sys.argv[sys.argv.index("--nation") + 1]]

    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    now = datetime.date.today().isoformat()

    total = new = ours = gaps = 0
    for nation in nations:
        try:
            found = fetch_open(client, nation, print)
        except FetchError as exc:
            conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) "
                         "VALUES (?,?,?)",
                         (now, "dg-consultations",
                          "{0}: {1}".format(nation, exc.cause)))
            conn.commit()
            print("  [gap] {0}: {1}".format(nation, exc.cause))
            gaps += 1
            continue
        known = {r[0]: r[1] for r in conn.execute(
            "SELECT key, closes FROM dg_consultations WHERE nation = ?",
            (nation,))}
        for c in found:
            total += 1
            if c.key not in known or not known[c.key]:
                # One detail fetch per new (or dateless) consultation.
                try:
                    html = client.get_text(c.url, "dg-consultations",
                                           "detail", archive=False)
                    if nation == "wales":
                        c.opened, c.closes = devolved.parse_govwales_detail(html)
                    else:
                        c.opened, c.closes = devolved.parse_citizen_space_detail(html)
                except FetchError as exc:
                    print("  [gap] detail {0}: {1}".format(c.url, exc.cause))
                    gaps += 1
            res = filt.filter_item(tax, wl, "{0} {1}".format(c.title,
                                                             c.summary))
            areas = res.issue_areas or []
            if areas:
                ours += 1
            if c.key not in known:
                new += 1
            conn.execute(
                "INSERT INTO dg_consultations (key, nation, title, url, "
                "summary, opened, closes, areas, matched_terms, tier, "
                "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET title=excluded.title, "
                "summary=excluded.summary, "
                "opened=COALESCE(excluded.opened, opened), "
                "closes=COALESCE(excluded.closes, closes), "
                "areas=excluded.areas, matched_terms=excluded.matched_terms, "
                "tier=excluded.tier, last_seen=excluded.last_seen",
                (c.key, nation, c.title, c.url, c.summary, c.opened,
                 c.closes, json.dumps(areas),
                 json.dumps(res.matched_terms or []), res.tier, now, now))
        conn.commit()
        print("{0}: {1} open consultation(s) listed.".format(
            nation, len(found)))

    print("\n{0} open consultation(s) across {1} nation(s); {2} new, {3} on "
          "our ground by title+summary.".format(total, len(nations), new,
                                                ours))
    dateless = conn.execute("SELECT COUNT(*) FROM dg_consultations WHERE "
                            "closes IS NULL AND last_seen = ?",
                            (now,)).fetchone()[0]
    if dateless:
        print("{0} still carry NO closing date (detail parse failed) -- "
              "shown dateless, never guessed.".format(dateless))
    print("no gaps." if not gaps else
          "{0} gap(s) -- printed above.".format(gaps))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
