#!/usr/bin/env python3
"""Flag the debate days we want a pack on; the debate-day tasks read this first.

    python3 tools/debate_watch.py today                       # WATCH lines for today, or "no watch today"
    python3 tools/debate_watch.py list
    python3 tools/debate_watch.py add 2026-09-18 "Terminally Ill Adults" --house Commons --area 2 --note "Second Reading"
    python3 tools/debate_watch.py remove 2026-09-18 "Terminally Ill Adults"
    python3 tools/debate_watch.py suggest [--days 10]         # week-ahead debates on our ground, as add commands
    python3 tools/debate_watch.py suggest --write             # ...and flag the debate-shaped ones (Monday's run does this)
    python3 tools/debate_watch.py add-bill 4254 --area 11 --note "committee stage"   # every future sitting of a bill
    python3 tools/debate_watch.py refresh                     # re-expand the bills already flagged (new sittings)
    python3 tools/debate_watch.py net [--date D] [--min 8]    # same-day: flag today's debates Hansard already shows

Christopher, 14 Sept 2026: "I'm not sure we need the daily pulls unless we flag
something coming up in the week we want a pack on." So the tasks ask this file,
not Hansard, and a quiet day costs nothing. 17 Sept 2026: the flagging itself
is now automatic in three ways (Monday's week-ahead pass, a bill's stage
sittings, the 16:45 same-day net); a hand `add` still outranks all three.
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
    s.add_argument("--write", action="store_true", help="flag the debate-shaped candidates and refresh flagged bills")
    b = sub.add_parser("add-bill"); b.add_argument("bill_id", type=int)
    b.add_argument("--area", type=int); b.add_argument("--note")
    sub.add_parser("refresh")
    n = sub.add_parser("net"); n.add_argument("--date"); n.add_argument("--min", type=int, default=dw.SAME_DAY_MIN_SPEAKERS)
    args = ap.parse_args()
    watches = dw.load()

    def bills_fetch(client):
        from src.ingest import bills
        return lambda bill_id: (bills.fetch_bill_detail(client, bill_id), bills.fetch_bill_stages(client, bill_id))

    if args.cmd == "add-bill":
        from src.http import HttpClient
        client = HttpClient(os.path.join(ROOT, "data", "raw"))
        detail, stages = bills_fetch(client)(args.bill_id)
        if not detail or not detail.get("shortTitle"):
            print("bill %d: no detail from the Bills API" % args.bill_id); return 1
        watches, added, kept = dw.expand_bill(watches, detail, stages, datetime.date.today(), args.area, args.note)
        dw.save(watches)
        print("bill %d %s: %d sitting(s) flagged, %d already there" % (args.bill_id, detail["shortTitle"], len(added), kept))
        for date, house, term in added:
            print("  %s  %s" % (date, house))
        return 0
    if args.cmd == "refresh":
        from src.http import HttpClient
        client = HttpClient(os.path.join(ROOT, "data", "raw"))
        watches, added = dw.refresh_bills(watches, bills_fetch(client), datetime.date.today())
        dw.save(watches)
        print("refresh: %d new bill sitting(s)" % len(added))
        return 0
    if args.cmd == "net":
        from src import debatetoday as dt
        from src import filter as filt
        from src.http import HttpClient
        import make_vote_tracker
        day = args.date or dt.today_london()
        cfg = make_vote_tracker.load_config()
        terms = {}
        for i in cfg.get("issues") or []:
            for t in i.get("debate_match") or []:
                terms.setdefault(t, i.get("area"))
        tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
        wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
        client = HttpClient(os.path.join(ROOT, "data", "raw"))
        rows = dt.sized(client, day, dt.candidates(client, day, tax, wl, terms))
        watches, flagged = dw.net(watches, rows, day, args.min)
        if flagged:
            dw.save(watches)
            print("NET: flagged %d for %s: %s" % (len(flagged), day, "; ".join("%s %s (%d speakers)" % f for f in flagged)))
        else:
            biggest = max((r["speakers"] for r in rows), default=0)
            print("NET: nothing to flag for %s (%d on our ground, largest %d speakers, floor %d)" % (day, len(rows), biggest, args.min))
        return 0
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
        if args.write:
            # Monday's run: one unindented first line carries everything (the
            # relay in run_monday.py keeps the head and bins indented lines).
            watches, written = dw.auto_flag(watches, rows, today)
            watches, from_bills = dw.refresh_bills(watches, bills_fetch(client), today)
            dw.save(watches)
            ahead = [w for w in watches if w["date"] >= today.isoformat()]
            skipped = [r for r in rows if (r[5] if len(r) > 5 else "") not in dw.AUTO_CATEGORIES]
            print("debate watch: flagged %d from the week-ahead, %d new bill sitting(s); %d watch(es) ahead; %d candidate(s) not debate-shaped" % (
                len(written), len(from_bills), len(ahead), len(skipped)))
            for date, house, title in written + from_bills:
                print("  %s  %s  %s" % (date, house, title))
            return 0
        if not rows:
            print("nothing on our ground in the next %d days" % args.days); return 0
        flagged = {(w["date"], w["term"].lower()) for w in watches}
        for row in rows:
            date, house, title, areas, reasons = row[:5]
            category = row[5] if len(row) > 5 else ""
            mark = "  (flagged)" if any(d == date and t in title.lower() for d, t in flagged) else ""
            if category and category not in dw.AUTO_CATEGORIES:
                mark += "  [%s: not auto-flagged]" % category
            area = areas[0] if areas else ""
            print('python3 tools/debate_watch.py add %s "%s" --house %s%s --note "%s"%s' % (
                date, title.replace('"', "'")[:60], house, (" --area %d" % area) if area else "", "; ".join(reasons[:2])[:60], mark))
        return 0


if __name__ == "__main__":
    sys.exit(main())
