#!/usr/bin/env python3
"""Flag the debate days we want a pack on; the debate-day tasks read this first.

    python3 tools/debate_watch.py today                       # WATCH lines for today, or "no watch today"
    python3 tools/debate_watch.py list
    python3 tools/debate_watch.py add 2026-09-18 "Terminally Ill Adults" --house Commons --area 2 --note "Second Reading"
    python3 tools/debate_watch.py remove 2026-09-18 "Terminally Ill Adults"
    python3 tools/debate_watch.py suggest [--days 10]         # week-ahead debates on our ground, as add commands

Christopher, 14 Sept 2026: "I'm not sure we need the daily pulls unless we flag
something coming up in the week we want a pack on." So the tasks ask this file,
not Hansard, and a quiet day costs nothing.
"""

import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import debatewatch as dw  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("today").add_argument("--date")
    sub.add_parser("list")
    a = sub.add_parser("add"); a.add_argument("date"); a.add_argument("term")
    a.add_argument("--house", default="Commons", choices=["Commons", "Lords"]); a.add_argument("--area", type=int); a.add_argument("--note")
    r = sub.add_parser("remove"); r.add_argument("date"); r.add_argument("term")
    s = sub.add_parser("suggest"); s.add_argument("--days", type=int, default=10)
    args = ap.parse_args()
    watches = dw.load()
    if args.cmd == "today":
        from src import debatetoday as dt
        day = args.date or dt.today_london()
        hits = dw.for_day(watches, day)
        if not hits:
            print("no watch today (%s)" % day); return 0
        for w in hits:
            print(dw.line(w))
        return 0
    if args.cmd == "list":
        today = datetime.date.today().isoformat()
        for w in watches:
            print(("  " if w["date"] >= today else "  (past) ") + w["date"] + "  " + dw.line(w))
        if not watches:
            print("no watches")
        return 0
    if args.cmd == "add":
        watches, new = dw.add(watches, args.date, args.term, args.house, args.area, args.note)
        dw.save(watches); print(("added: " if new else "updated: ") + dw.line(dw.for_day(watches, args.date)[-1]))
        return 0
    if args.cmd == "remove":
        watches, n = dw.remove(watches, args.date, args.term)
        dw.save(watches); print("removed %d watch(es)" % n)
        return 0
    if args.cmd == "suggest":
        from src import filter as filt
        from src.ingest import whatson
        from src.http import HttpClient
        import make_vote_tracker
        cfg = make_vote_tracker.load_config()
        terms = {}
        for i in cfg.get("issues") or []:
            for t in i.get("debate_match") or []:
                terms.setdefault(t, i.get("area"))
        tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
        client = HttpClient(os.path.join(ROOT, "data", "raw"))
        today = datetime.date.today()
        events = whatson.fetch_events(client, today, today + datetime.timedelta(days=args.days))
        rows = dw.suggest(events, tax, wl, terms, today)
        if not rows:
            print("nothing on our ground in the next %d days" % args.days); return 0
        flagged = {(w["date"], w["term"].lower()) for w in watches}
        for date, house, title, areas, reasons in rows:
            mark = "  (flagged)" if any(d == date and t in title.lower() for d, t in flagged) else ""
            area = areas[0] if areas else ""
            print('python3 tools/debate_watch.py add %s "%s" --house %s%s --note "%s"%s' % (
                date, title.replace('"', "'")[:60], house, (" --area %d" % area) if area else "", "; ".join(reasons[:2])[:60], mark))
        return 0


if __name__ == "__main__":
    sys.exit(main())
