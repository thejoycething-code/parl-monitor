#!/usr/bin/env python3
"""Canadian provincial legislatures: roster, bills and recorded divisions.

    python3 tools/prov_collect.py --prov ab                      # current session
    python3 tools/prov_collect.py --prov ab --session 31-1 \\
        --since 2024-10-28 --until 2024-12-05                   # a window
    python3 tools/prov_collect.py --prov sk --dry-run            # list, store nothing
    python3 tools/prov_collect.py --prov bc --db /tmp/prov.db    # anywhere but the store

GROUNDWORK (2 October 2026). Nothing schedules this and nothing outside
tools/prov_*.py reads its tables yet; see docs/canada-provinces-scope.md.
One runner, one module per legislature (src/ingest/prov_<code>.py), each
exposing collect(ctx, session, roster, bills) and the parsers its tests use.

WHAT A RUN DOES, IN ORDER: the roster for the session (party OVER TIME
where the source dates it), the session's bills (classified on their TEXT,
per passage), then every sitting record in the window (--since/--until),
parsing each recorded division and resolving every printed name against the
roster terms valid that day.

THE TALLY CHECK: a division whose resolved names do not account for the
printed totals is stored with positions_ok=0 and recorded as a gap; its
sitting is read again on the next run. Only positions_ok=1 places anyone.
An unresolved name is stored with a NULL member, never guessed. A decision
taken on voice is stored as kind='voice', never as an empty roll-call.

POLITENESS: the repo's HttpClient (honest CitizenGO UA with contact), at
least 1.1 s between requests to a host, robots.txt honoured (a disallowed
URL is a gap, a Crawl-delay raises the throttle). File names are always
taken from the legislature's own listing pages, never constructed.

Exit status 1 when any gap was recorded. ONE WRITER AT A TIME on the store.
Separation guarantee: writes prov_* and the shared gaps table only.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, prov_store  # noqa: E402
from src.http import HttpClient  # noqa: E402
from src.prov_fetch import Context  # noqa: E402

MODULES = {
    "ab": "src.ingest.prov_ab",
    "sk": "src.ingest.prov_sk",
    "bc": "src.ingest.prov_bc",
    "mb": "src.ingest.prov_mb",
    "on": "src.ingest.prov_on",
    "nb": "src.ingest.prov_nb",
    "nl": "src.ingest.prov_nl",
}
NOT_BUILT = {p: "not built yet (docs/canada-provinces-scope.md, build order)"
             for p in prov_store.PROVINCES if p not in MODULES}


def module_for(prov):
    if prov not in MODULES:
        raise SystemExit("prov-collect: {0} is {1}".format(
            prov, NOT_BUILT.get(prov, "not a province code")))
    return importlib.import_module(MODULES[prov])


def report(conn, ctx, stats, log=print):
    s = prov_store.summary(conn, ctx.prov)
    log("prov-collect {0}: this run {1}".format(ctx.prov, ", ".join(
        "{0}={1}".format(k, v) for k, v in sorted((stats or {}).items()))))
    log("  store: {members} member(s), {terms} term(s); {bills} bill(s), {bills_ours} on our "
        "ground; {sittings} record(s) read; {recorded} recorded division(s) ({recorded_ok} "
        "tally ok, {recorded_gap} gap, {recorded_totals_only} totals only); {voice} voice decision(s); "
        "{ours} division(s) on our "
        "ground; {votes} vote(s), {unresolved} unresolved".format(**s))
    log("  Matched against the ENGLISH taxonomy plus config/watchlist-prov.yaml, a "
        "groundwork draft nobody in Canada has reviewed.")


def run(conn, client, prov, session=None, since=None, until=None, limit=None,
        budget_seconds=drain.DEFAULT_S, dry_run=False, refresh=False, roster=True,
        bills=True, log=print, budget=None):
    """Drive one province. Returns (stats, gaps)."""
    mod = module_for(prov)
    ctx = Context(conn, client, prov, since=since, until=until, limit=limit,
                  budget=budget or drain.Budget(budget_seconds), dry_run=dry_run,
                  refresh=refresh, log=log)
    stats = mod.collect(ctx, session=session or mod.CURRENT_SESSION,
                        roster=roster, bills=bills) or {}
    if not dry_run:
        db.record_gaps(conn, ctx.feed, ctx.gaps)
        report(conn, ctx, stats, log=log)
    else:
        log("prov-collect {0} (dry run, nothing stored): {1}".format(prov, ", ".join(
            "{0}={1}".format(k, v) for k, v in sorted(stats.items()))))
    if ctx.gaps:
        log("  {0} gap(s) recorded under feed {1}".format(len(ctx.gaps), ctx.feed))
    return stats, ctx.gaps


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prov", required=True, choices=sorted(prov_store.PROVINCES))
    ap.add_argument("--session", help="legislature-session, e.g. 31-1 (default: the current one)")
    ap.add_argument("--since", help="first sitting date to read, YYYY-MM-DD")
    ap.add_argument("--until", help="last sitting date to read, YYYY-MM-DD")
    ap.add_argument("--limit", type=int, help="stop after reading this many sitting records")
    ap.add_argument("--budget-seconds", type=float, default=drain.DEFAULT_S)
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be read, store nothing")
    ap.add_argument("--refresh", action="store_true",
                    help="re-read records already read cleanly")
    ap.add_argument("--no-roster", action="store_true")
    ap.add_argument("--no-bills", action="store_true")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    args = ap.parse_args(argv)
    module_for(args.prov)
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"), throttle=1.1)
    if args.dry_run:
        conn = db.init_db(db.connect(":memory:"))
    else:
        conn = db.init_db(db.connect(args.db))
    _stats, gaps = run(conn, client, args.prov, session=args.session, since=args.since,
                       until=args.until, limit=args.limit,
                       budget_seconds=args.budget_seconds, dry_run=args.dry_run,
                       refresh=args.refresh, roster=not args.no_roster,
                       bills=not args.no_bills)
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
