"""EP written questions on our ground -- the last parity item, by cost.

    python3 tools/eu_pqs.py

The parliamentary-questions listing returns id-only stubs, so every title
costs a detail fetch: the reason this was deferred to last. Same
capped-drain pattern as the committee documents -- 150 detail fetches per
run against the shared 500/5min budget, the backlog drains over weeks,
the cap disclosed every time it bites. EN titles are taxonomy-matched;
the asker's person id joins the MEP roster so a question can eventually
ride its author's tracker card.

Separation guarantee: writes eu_pqs only.
ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, eulabel, filter as filt
from src.http import FetchError, HttpClient

LIST = ("https://data.europarl.europa.eu/api/v2/parliamentary-questions"
        "?year={0}&limit=1000&offset={1}&format=application%2Fld%2Bjson")
DOC = ("https://data.europarl.europa.eu/api/v2/parliamentary-questions/{0}"
       "?format=application%2Fld%2Bjson")
FETCH_CAP = 300        # same drain arithmetic as the committee cap
THROTTLE_S = 0.65


def pull(conn, client, today, log=print):
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    known = {r[0] for r in conn.execute("SELECT identifier FROM eu_pqs")}
    stubs, offset = [], 0
    while True:
        try:
            reply = client.get_json(LIST.format(today[:4], offset), "eu-pqs",
                                    "list-{0}".format(offset), archive=False)
        except (FetchError, ValueError) as exc:
            log("  [gap] pq listing: {0}".format(exc))
            return 0, 0, 1
        batch = reply.get("data") or []
        stubs.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    # Newest first, so the drain spends its cap on the current backlog
    # before history.
    stubs.sort(key=lambda s: s.get("identifier") or "", reverse=True)
    new = ours = 0
    for s in stubs:
        ident = s.get("identifier") or ""
        if not ident or ident in known:
            continue
        if new >= FETCH_CAP:
            log("  fetch cap ({0}) reached; the rest drains on later runs "
                "-- disclosed, not silent".format(FETCH_CAP))
            break
        new += 1
        time.sleep(THROTTLE_S)
        try:
            det = client.get_json(DOC.format(ident), "eu-pqs", ident,
                                  archive=False)
            d = (det.get("data") or [{}])[0]
        except (FetchError, ValueError) as exc:
            log("  [gap] pq {0}: {1}".format(ident, exc))
            continue
        title = eulabel.english(d.get("title_dcterms"))
        if not title:
            continue
        res = filt.filter_item(tax, wl, title)
        areas = res.issue_areas or []
        if areas:
            ours += 1
        creators = d.get("creator") or []
        asker = str(creators[0]).rsplit("/", 1)[-1] if creators else None
        conn.execute(
            "INSERT INTO eu_pqs (identifier, date, title, asker, areas, "
            "matched_terms, tier, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(identifier) DO UPDATE "
            "SET title=excluded.title, areas=excluded.areas, "
            "last_seen=excluded.last_seen",
            (ident, d.get("document_date"), title, asker,
             json.dumps(areas), json.dumps(res.matched_terms or []),
             res.tier, today, today))
    conn.commit()
    return new, ours, 0


def main():
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    today = datetime.date.today().isoformat()
    new, ours, gaps = pull(conn, client, today)
    total = conn.execute("SELECT COUNT(*) FROM eu_pqs WHERE areas != '[]'"
                         ).fetchone()[0]
    print("eu-pqs: {0} new question(s) fetched, {1} on our ground "
          "({2} matched held); {3} gap(s).".format(new, ours, total, gaps))
    for r in conn.execute("SELECT p.date, p.title, m.name FROM eu_pqs p "
                          "LEFT JOIN eu_meps m ON m.person_id = p.asker "
                          "WHERE p.areas != '[]' ORDER BY p.date DESC "
                          "LIMIT 6").fetchall():
        print("  {0} {1} - {2}".format(r[0], (r[2] or "?")[:28],
                                       (r[1] or "")[:70]))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
