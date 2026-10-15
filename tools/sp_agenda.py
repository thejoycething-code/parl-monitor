"""Holyrood forward business into sp_agenda: the Chamber and committees,
day by day, from today to as far ahead as the Parliament publishes.

    python3 tools/sp_agenda.py                       # today + 56 days
    python3 tools/sp_agenda.py --from 2026-10-19 --to 2026-12-13
    python3 tools/sp_agenda.py --db /tmp/scratch.db  # any store

Two sources (src/ingest/holyrood_agenda.py has the probing):
  1. parliament.scot "What's on" for each weekday (robots.txt asked every
     run): the Chamber programme and committee agendas;
  2. data.parliament.scot's Business Programme motions (open-data API): the
     Chamber programme as agreed by the Bureau. Used for a day whose page
     could not be read, or a programmed day the page does not show yet.

Fails loud: a page or the API that cannot be read, or a page that answers
in a shape this reader does not know, is a [gap] line and a gaps row (feed
sp-agenda), and that day's stored rows are kept, never emptied. A run with
no source read at all exits 1.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, devolved_agenda as dva, filter as filt, robots_guard  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from src.ingest import holyrood_agenda as ha  # noqa: E402

FEED = "sp-agenda"
TABLE = "sp_agenda"
DEFAULT_DAYS = 56


def rows_for(items, tax, wl):
    out = []
    for it in items:
        areas, terms = dva.classify(tax, wl, it.business, it.detail)
        out.append({
            "key": "sp:{0}:{1}:{2}".format(it.dated, dva.slug(it.body, 40), dva.slug(it.business)),
            "dated": it.dated, "item_time": it.item_time, "body": it.body,
            "item_order": it.order, "business": it.business, "detail": it.detail,
            "item_type": dva.item_type(it.business, it.detail, it.committee),
            "reference": it.reference or None, "meeting_id": it.meeting_id or None,
            "url": it.url, "source": it.source, "areas": areas, "matched_terms": terms})
    return dva.unique_keys(out)


def collect(client, conn, tax, wl, start, end, today, log=print):
    """Read the window into sp_agenda. Returns a summary dict."""
    gaps = []
    stats = {"days_read": 0, "days_sitting": 0, "rows": 0, "new": 0, "ours": 0,
             "pruned": 0, "programme_days": 0, "committee_pending": 0, "gaps": gaps}

    def gap(detail):
        gaps.append(detail)
        db.record_gap(conn, FEED, detail)

    programme, refs = {}, {}
    try:
        motions = client.get_json(ha.PROGRAMME_URL, "holyrood", "business-programme",
                                  timeout=120, archive=False)
        programme, refs = ha.parse_programme(motions)
        if not programme:
            gap("business programme API: answered but no programmed day parsed")
    except (FetchError, ValueError) as exc:
        gap("business programme API: {0}".format(getattr(exc, "cause", exc)))

    page_ok = 0
    for day in ha.weekdays(start, end):
        dated = day.isoformat()
        items, read = [], False
        try:
            page = client.get_text(ha.WHATS_ON.format(dated), "holyrood",
                                   "whats-on-{0}".format(dated), archive=False)
            parsed = ha.parse_whats_on(page, dated)
            read = True
            page_ok += 1
            stats["days_read"] += 1
            if parsed.sitting:
                stats["days_sitting"] += 1
            if parsed.committee_pending:
                stats["committee_pending"] += 1
            items = parsed.chamber + parsed.committees
            if not parsed.chamber and dated in programme:
                # Programmed by the Bureau, not on the page yet.
                items = ha.programme_items(programme, refs, dated) + items
                stats["programme_days"] += 1
        except (FetchError, ha.PageShapeError) as exc:
            gap("What's on {0}: {1}".format(dated, getattr(exc, "cause", exc)))
            if dated in programme:
                items = ha.programme_items(programme, refs, dated)
                stats["programme_days"] += 1
        rows = rows_for(items, tax, wl)
        for row in rows:
            stats["new"] += dva.upsert(conn, TABLE, row, today)
            stats["rows"] += 1
            if row["areas"] or row["matched_terms"]:
                stats["ours"] += 1
        if read:
            stats["pruned"] += dva.prune_unseen(conn, TABLE, today, "dated = ?", [dated])
        elif rows:
            # Fallback rows replace only earlier fallback rows of that day.
            stats["pruned"] += dva.prune_unseen(
                conn, TABLE, today, "dated = ? AND source = 'business-programme'", [dated])
        conn.commit()
    stats["source_read"] = bool(page_ok or programme)
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--from", dest="start", type=datetime.date.fromisoformat)
    ap.add_argument("--to", dest="end", type=datetime.date.fromisoformat)
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    args = ap.parse_args(argv)
    today = datetime.date.today()
    start = args.start or today
    end = args.end or (start + datetime.timedelta(days=args.days))

    conn = db.init_db(db.connect(args.db))
    raw = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    raw.set_host_throttle("www.parliament.scot", 1.0)
    raw.add_redirect_guard(dva.official_only(("www.parliament.scot", "data.parliament.scot")))
    client = robots_guard.guard(raw, FEED)
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

    print("Holyrood forward business {0} to {1}".format(start, end))
    s = collect(client, conn, tax, wl, start, end, today.isoformat())
    held = conn.execute("SELECT COUNT(*) FROM sp_agenda WHERE dated >= ?",
                        (start.isoformat(),)).fetchone()[0]
    print("{0} weekday(s) read, {1} sitting; {2} agenda item(s) stored ({3} new), "
          "{4} match our areas; {5} day(s) from the Business Programme; "
          "{6} day(s) with committee agendas not yet published; {7} stale row(s) "
          "removed; {8} held from {9}.".format(
              s["days_read"], s["days_sitting"], s["rows"], s["new"], s["ours"],
              s["programme_days"], s["committee_pending"], s["pruned"], held, start))
    print("no gaps." if not s["gaps"] else "{0} gap(s) -- printed above.".format(len(s["gaps"])))
    return 0 if s["source_read"] else 1


if __name__ == "__main__":
    sys.exit(main())
