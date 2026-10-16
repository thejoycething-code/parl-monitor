#!/usr/bin/env python3
"""The UK weekly's Sunday-pull items, scored by the FREE session judge.

    tools/session_judge.sh tools/uk_pull_judge.py 120 25      # on the Mac Mini (jobs/uk-session-judge.sh)
    python3 tools/uk_pull_judge.py --queue-out /tmp/q.md --limit 25
    python3 tools/uk_pull_judge.py --queue-in /tmp/q.md
    python3 tools/uk_pull_judge.py --pending

Round 3 of the countdown (Chris, 16 October 2026: "paid AI off for the UK
weekly"). The Sunday pull (run_weekly.run_triage_pass, TRIAGE=auto) no
longer calls the paid API when a key is set: it leaves its items unscored,
and this tool hands them to a Claude Code session on the Mini's plan
allowance (tools/session_judge.sh, src/session_queue.py), the route the
What's On re-read (tools/uk_whatson_judge.py), the country editions, the
provinces, US, Ireland and Australia already use.

THERE IS NO PAID PATH HERE: no API call, no key read. Items carry the frame
the UK judge is given (triage.SYSTEM_PROMPT) and the evidence text it would
read (a watched Bill's "why we track it" line included); scores are applied
exactly as the pull applied them (watchlist floor, discards log), once ever,
and noted in session_scores as 'claude-code-session'.

ORDER (the weekly cap spreads a backlog over runs, so the most useful go
first): watchlist hits, then tier 1, then tier 2; newest first within each.
"""

import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, review, session_queue, triage  # noqa: E402

QUEUE_MARKER = "<!-- uk-pull-session-queue v1 -->"


def _db_path(arg):
    if arg:
        return arg
    name = os.environ.get("PARL_DB") or "parl-monitor.db"
    return name if os.path.isabs(name) else os.path.join(ROOT, "data", name)


def pending(conn, wl):
    """Every unscored UK item, in the order the cap should take them."""
    dates = {r["id"]: r["event_date"] or "" for r in conn.execute(
        "SELECT id, event_date FROM items WHERE triage_score IS NULL")}
    items = [i for i in triage.pending_items(conn, wl) if i.id in dates]

    def rank(i):
        if i.watchlist_hit or i.tier is None:
            return 0
        return 1 if i.tier == 1 else 2
    items.sort(key=lambda i: dates[i.id], reverse=True)
    items.sort(key=rank)
    return items


def queue_out(conn, wl, path, today, limit, log=print):
    items = pending(conn, wl)
    chosen = items[:max(0, limit)]
    n = session_queue.write_queue(path, chosen, "UK weekly judge queue, {0}".format(today),
                                  QUEUE_MARKER, triage.SYSTEM_PROMPT)
    log("uk-pull-judge: session queue: {0} item(s) written to {1}; {2} unscored in all.".format(
        n, path, len(items)))
    return n


def queue_in(conn, wl, path, today, log=print):
    results, refused, blank = session_queue.read_queue(path, QUEUE_MARKER)
    if refused and refused[0][0] == "(file)":
        log("  [gap] session queue {0} refused: {1}".format(path, refused[0][1]))
        return None
    items = {i.id: i for i in pending(conn, wl)}
    good = []
    for res in results:
        if res.id not in items:
            refused.append((res.id, "not an unscored UK item"))
            continue
        good.append(triage.TriageResult(id=res.id, score=res.score, areas=list(items[res.id].issue_areas),
                                        why_it_matters=res.why, stub=False))
    scored, discards = triage.apply_scores(conn, [items[g.id] for g in good], good)
    review.log_discards(conn, today, [(i, t, None) for i, t in discards])
    session_queue.record(conn, "uk", good, today)
    for iid, why in refused:
        log("  [gap] queue item refused: {0}: {1}".format(iid, why))
    log("uk-pull-judge: session queue: {0} item(s) scored, {1} refused, {2} left blank".format(
        scored, len(refused), len(blank)))
    return scored


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    q = ap.add_mutually_exclusive_group(required=True)
    q.add_argument("--queue-out", metavar="PATH")
    q.add_argument("--queue-in", metavar="PATH")
    q.add_argument("--pending", action="store_true")
    args = ap.parse_args(argv)
    conn = db.init_db(db.connect(_db_path(args.db)))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    try:
        if args.pending:
            print("uk-pull-judge: {0} unscored UK item(s)".format(len(pending(conn, wl))))
            return 0
        if args.queue_out:
            queue_out(conn, wl, args.queue_out, args.date, args.limit)
            return 0
        return 1 if queue_in(conn, wl, args.queue_in, args.date) is None else 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
