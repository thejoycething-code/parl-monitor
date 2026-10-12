#!/usr/bin/env python3
"""Canadian provincial Hansard: who said what, on our issues.

    python3 tools/prov_speeches.py --prov on --resume             # the weekly
    python3 tools/prov_speeches.py --prov bc --session 43-2 \\
        --since 2026-02-12 --until 2026-02-28 --db /tmp/prov.db  # a window
    python3 tools/prov_speeches.py --prov mb --all-sessions \\
        --since 2010-01-01 --budget-seconds 16000                # the backfill
    python3 tools/prov_speeches.py --prov sk --dry-run            # list, store nothing

The sibling of tools/prov_collect.py, as tools/ca_hansard.py is of the federal
roll-call collector: it reads the provinces' Hansard for SPEECHES and never
touches a division, a vote, a bill or prov_sittings, so the vote collectors
-- and the vote backfill dispatched through them -- behave exactly as they
did. The engine is src/prov_speeches.py (its docstring says what a speech
is, who spoke and what is stored); each province's reader is
src/ingest/prov_<code>_hansard.py. Scoped, measured and decided per province
in docs/canada-provinces-scope.md ("Hansard speeches").

WHICH SESSIONS AND WHICH DAYS: as prov_collect.py -- the session list comes
from the legislature's own index (the vote module's list_sessions), and
--all-sessions reads every listed session touching the window, oldest
first, on one clock. Days come from the legislature's own Hansard index.

RESUME (--resume, the weekly): from the newest Hansard day already read for
speeches, less 14 days, or from the oldest day still owed in the last 120
days. On a province with no day read yet, the last 60 days, said out loud:
the weekly is never the backfill (the ca_hansard lesson -- a weekly that
starts at the beginning of a session crawls the backlog for months).

THE ROSTER COMES FIRST. Speakers are resolved against the roster terms the
vote collector stored (prov_collect.py runs before this in the weekly).
Saskatchewan, Manitoba and Ontario date their rosters from each day's own
Hansard member list, and this reads that list for every day it reads, as
the vote collector does on a division day. A day where fewer than half the
speakers resolve is a gap and is read again later; a backfill of speeches
should follow the vote backfill of the same province, not precede it.

RAW: each day's transcript is archived to data/raw through HttpClient
(archive=True), feed prov-<code>-speeches; the archive's own slugify()
makes every name lowercase.

Exit status 1 on any gap not listed in config/prov_known_gaps.yaml. ONE
WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import importlib
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, prov_classify as pc, prov_speeches as sp, prov_store  # noqa: E402
from src.http import HttpClient  # noqa: E402
from src.prov_fetch import Context  # noqa: E402

READERS = {
    "on": "src.ingest.prov_on_hansard",
    "bc": "src.ingest.prov_bc_hansard",
    "mb": "src.ingest.prov_mb_hansard",
    "sk": "src.ingest.prov_sk_hansard",
    "nl": "src.ingest.prov_nl_hansard",
    "qc": "src.ingest.prov_qc_hansard",
    "ab": "src.ingest.prov_ab_hansard",
    "nb": "src.ingest.prov_nb_hansard",
}
NOT_BUILT = {}
# The step heartbeat (tools/coverage.py AWAITING_FIRST_RUN): stamped into
# source_runs at the end of every stored run, so the empty speech tables are
# excused only until the speeches step itself has run once -- not merely
# until the Provinces weekly has (a vote backfill dispatch runs no speeches).
HEARTBEAT = "Provinces speeches"


def _collector():
    spec = importlib.util.spec_from_file_location("prov_collect", os.path.join(ROOT, "tools", "prov_collect.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


collector = _collector()


def reader_for(prov):
    if prov not in READERS:
        raise SystemExit("prov-speeches: {0}'s Hansard is {1}".format(
            prov, NOT_BUILT.get(prov, "not built (docs/canada-provinces-scope.md, 'Hansard speeches')")))
    return importlib.import_module(READERS[prov])


def stamp(conn, today=None):
    conn.execute("INSERT OR REPLACE INTO source_runs (source, last_run, run_id, note) VALUES (?,?,?,?)",
                 (HEARTBEAT, (today or datetime.date.today()).isoformat(), os.environ.get("GITHUB_RUN_ID"),
                  "step heartbeat: tools/prov_speeches.py"))


def run(conn, client, prov, session=None, since=None, until=None, limit=None,
        budget_seconds=drain.DEFAULT_S, dry_run=False, refresh=False, resume=False,
        all_sessions=False, log=print, budget=None):
    """Read one province's Hansard days. Returns (stats, gaps)."""
    reader = reader_for(prov)
    base = collector.module_for(prov)
    if since is None and not all_sessions:
        since = sp.resume_since(conn, prov, log=log) if resume else (
            datetime.date.today() - datetime.timedelta(days=sp.DEFAULT_WINDOW_DAYS)).isoformat()
    if all_sessions and not since:
        raise SystemExit("prov-speeches: --all-sessions needs --since (the backfill's first day)")
    ctx = Context(conn, client, prov, feed=sp.feed(prov), since=since, until=until, limit=limit,
                  budget=budget or drain.Budget(budget_seconds), dry_run=dry_run, refresh=refresh, log=log)
    tax = pc.load_french_taxonomy(prov) if reader.LANGUAGE == "fr" else pc.load_taxonomy()
    wl = pc.load_watchlist(prov)
    stats = {}
    codes = collector.plan_sessions(ctx, base, session=session, all_sessions=all_sessions, log=log)
    for n, code in enumerate(codes):
        if n and ctx.stop():
            log("  sessions not started this run (the clock or the day cap): {0}; a later dispatch "
                "resumes there".format(" ".join(c or "" for c in codes[n:])))
            break
        if len(codes) > 1:
            log("  -- {0} session {1}".format(prov, code))
        days = reader.list_days(ctx, code if code is not None else getattr(base, "CURRENT_SESSION", None))
        state = {}

        def resolver_for(day, state=state):
            # Rebuilt after every day: the day's own member list may have
            # just widened the terms (Saskatchewan, Manitoba, Ontario).
            return reader.resolver(ctx)

        got = sp.collect_days(ctx, days, lambda day: reader.read_day(ctx, day), resolver_for, tax, wl,
                              language=reader.LANGUAGE)
        for k, v in got.items():
            stats[k] = stats.get(k, 0) + v
    stats["sessions"] = len(codes)
    if not dry_run:
        db.record_gaps(conn, ctx.feed, ctx.gaps)
        stamp(conn)
        conn.commit()
        s = sp.summary(conn, prov)
        log("prov-speeches {0}: this run {1}".format(prov, ", ".join(
            "{0}={1}".format(k, v) for k, v in sorted(stats.items()))))
        log("  store: {days} Hansard day(s) read ({days_owed} owed); {resolved} of {turns} speaker "
            "turn(s) resolved; {speeches} speech(es) on our ground from {speakers} member(s), "
            "{unresolved} unattributed".format(**s))
        log("  Matched against {0} plus config/watchlist-prov.yaml.".format(
            "config/taxonomy-qc.yaml (French; AI draft, no Quebec reader yet)" if reader.LANGUAGE == "fr"
            else "the ENGLISH taxonomy"))
    else:
        log("prov-speeches {0} (dry run, nothing stored): {1}".format(prov, ", ".join(
            "{0}={1}".format(k, v) for k, v in sorted(stats.items()))))
    if ctx.gaps:
        log("  {0} gap(s) recorded under feed {1}".format(len(ctx.gaps), ctx.feed))
    return stats, ctx.gaps


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prov", required=True, choices=sorted(prov_store.PROVINCES))
    ap.add_argument("--session", help="legislature-session, e.g. 44-1 (default: the current one, "
                                      "plus any newer one the legislature lists)")
    ap.add_argument("--since", help="first Hansard day to read, YYYY-MM-DD")
    ap.add_argument("--until", help="last Hansard day to read, YYYY-MM-DD")
    ap.add_argument("--resume", action="store_true",
                    help="without --since: from the newest day read, less 14 days (the weekly)")
    ap.add_argument("--all-sessions", action="store_true",
                    help="every listed session touching --since/--until (the backfill)")
    ap.add_argument("--limit", type=int, help="stop after reading this many Hansard days")
    ap.add_argument("--budget-seconds", type=float, default=drain.DEFAULT_S)
    ap.add_argument("--dry-run", action="store_true", help="list the days, read and store nothing")
    ap.add_argument("--refresh", action="store_true", help="re-read days already read cleanly")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"),
                    help="where the day transcripts are archived (default data/raw)")
    args = ap.parse_args(argv)
    if args.all_sessions and args.session:
        ap.error("--all-sessions and --session are exclusive")
    if args.all_sessions and not args.since:
        ap.error("--all-sessions needs --since")
    reader_for(args.prov)
    client = HttpClient(raw_dir=args.raw_dir, throttle=1.1)
    conn = db.init_db(db.connect(":memory:" if args.dry_run else args.db))
    _stats, gaps = run(conn, client, args.prov, session=args.session, since=args.since,
                       until=args.until, limit=args.limit, budget_seconds=args.budget_seconds,
                       dry_run=args.dry_run, refresh=args.refresh, resume=args.resume,
                       all_sessions=args.all_sessions)
    conn.close()
    unknown = [g for g in gaps if not collector.known_gap(args.prov, g)]
    if gaps and not unknown:
        print("  every gap is a reviewed known gap (config/prov_known_gaps.yaml): not a failure")
    return 1 if unknown else 0


if __name__ == "__main__":
    sys.exit(main())
