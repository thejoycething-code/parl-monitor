#!/usr/bin/env python3
"""Canadian provincial legislatures: roster, bills and recorded divisions.

    python3 tools/prov_collect.py --prov ab                      # current session
    python3 tools/prov_collect.py --prov ab --resume             # the weekly: since the last record read
    python3 tools/prov_collect.py --prov ab --session 31-1 \\
        --since 2024-10-28 --until 2024-12-05                   # a window
    python3 tools/prov_collect.py --prov nb --all-sessions \\
        --since 2010-01-01 --budget-seconds 16000               # the backfill
    python3 tools/prov_collect.py --prov qc --roster-only        # Quebec's roster, read again now
    python3 tools/prov_collect.py --prov sk --dry-run            # list, store nothing
    python3 tools/prov_collect.py --prov bc --db /tmp/prov.db    # anywhere but the store

SCHEDULED since 3 October 2026 (.github/workflows/prov-weekly.yml, "Provinces
weekly"): one step per province with --resume, then tools/prov_5ca.py. The
same workflow, dispatched with `provinces` and `since`, runs the backfill.
One runner, one module per legislature (src/ingest/prov_<code>.py), each
exposing collect(ctx, session, roster, bills), list_sessions(ctx) and the
parsers its tests use.

WHAT A RUN DOES, IN ORDER: the roster for the session (party OVER TIME
where the source dates it), the session's bills (classified on their TEXT,
per passage), then every sitting record in the window (--since/--until),
parsing each recorded division and resolving every printed name against the
roster terms valid that day.

WHICH SESSIONS. --session names one. Without it a run reads the module's
CURRENT_SESSION AND every session the legislature's own index lists as newer:
each newer one is read, and is also a GAP ("set CURRENT_SESSION"), so a new
session -- Quebec's 44th legislature after the election of 5 October 2026 --
is collected the week it opens and fails the step loudly until a person
moves the constant. --all-sessions (the backfill) reads every session the
index lists whose dates touch the window, oldest first, on ONE clock. The
list always comes from the legislature's index, never from a list typed into
the repo (src/prov_fetch.py, "sessions"). Saskatchewan's archive is listed by
date across sessions, so it needs no session list at all.

RESUME (--resume): the window starts at the newest record already read, less
RESUME_LOOKBACK_DAYS (a Manitoba division day whose Hansard was not yet out
is a gap and is re-read inside that margin), or at the oldest record still
OWED from the last OWED_DAYS, whichever is earlier. On a store with nothing
read for the province it is the module's own default (the whole current
session; Saskatchewan's last 60 days), and the run says so. A record read
cleanly is never fetched again; a backfill cut short by its clock resumes
where it stopped when dispatched again.

THE TALLY CHECK: a division whose resolved names do not account for the
printed totals is stored with positions_ok=0 and recorded as a gap; its
sitting is read again on the next run. Only positions_ok=1 places anyone.
An unresolved name is stored with a NULL member, never guessed. A decision
taken on voice is stored as kind='voice', never as an empty roll-call. A
layout the parser cannot read therefore shows up as GAPS, never as wrong
votes -- the property a backfill to 2010 leans on.

POLITENESS: the repo's HttpClient (honest CitizenGO UA with contact), at
least 1.1 s between requests to a host, robots.txt honoured (a disallowed
URL is a gap, a Crawl-delay raises the throttle for that host: legnb.ca asks
for 10 s). File names are always taken from the legislature's own listing
pages, never constructed.

Exit status 1 when any gap was recorded. ONE WRITER AT A TIME on the store.
Separation guarantee: writes prov_* and the shared gaps table only.
"""

from __future__ import annotations

import argparse
import datetime
import importlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, prov_classify as pc, prov_store  # noqa: E402
from src.http import HttpClient  # noqa: E402
from src.prov_fetch import Context, overlaps, session_order  # noqa: E402

MODULES = {
    "ab": "src.ingest.prov_ab",
    "sk": "src.ingest.prov_sk",
    "bc": "src.ingest.prov_bc",
    "mb": "src.ingest.prov_mb",
    "on": "src.ingest.prov_on",
    "nb": "src.ingest.prov_nb",
    "nl": "src.ingest.prov_nl",
    "qc": "src.ingest.prov_qc",
    "ns": "src.ingest.prov_ns",
}
NOT_BUILT = {p: "not built yet (docs/canada-provinces-scope.md, build order)"
             for p in prov_store.PROVINCES if p not in MODULES}
# Out of reach, not merely unbuilt: the legislature answers our honest UA
# with a bot challenge, from a GitHub runner as from the laptop. We never
# solve or work around one (docs/canada-provinces-scope.md).
NOT_BUILT["pe"] = ("not built, and out of reach: every inner page of assembly.pe.ca redirects to a Radware CAPTCHA "
                   "(validate.perfdrive.com), from CI too (docs/canada-provinces-scope.md, PEI)")
NOT_BUILT["yt"] = ("not built, and out of reach: yukonassembly.ca answers a Cloudflare challenge, from CI too "
                   "(docs/canada-provinces-scope.md, Yukon)")

RESUME_LOOKBACK_DAYS = 14
OWED_DAYS = 120


def module_for(prov):
    if prov not in MODULES:
        raise SystemExit("prov-collect: {0} is {1}".format(
            prov, NOT_BUILT.get(prov, "not a province code")))
    return importlib.import_module(MODULES[prov])


def resume_since(conn, prov, today=None, log=print):
    """The weekly window's first day, from what the store already holds (see
    RESUME in the module docstring). None on a store with nothing read."""
    today = today or datetime.date.today()
    newest = conn.execute("SELECT MAX(date) FROM prov_sittings WHERE prov=? AND date IS NOT NULL",
                          (prov,)).fetchone()[0]
    if not newest:
        log("  {0}: nothing read for this province yet; the module's own default window "
            "(the whole current session; sk: the last 60 days)".format(prov))
        return None
    since = (datetime.date.fromisoformat(newest[:10])
             - datetime.timedelta(days=RESUME_LOOKBACK_DAYS)).isoformat()
    floor = (today - datetime.timedelta(days=OWED_DAYS)).isoformat()
    owed = conn.execute("SELECT MIN(date) FROM prov_sittings WHERE prov=? AND status != 'ok' "
                        "AND date >= ?", (prov, floor)).fetchone()[0]
    if owed and owed < since:
        since = owed
    log("  {0}: resuming from {1} (newest record read {2}{3})".format(
        prov, since, newest, "; oldest still owed {0}".format(owed) if owed and owed == since else ""))
    return since


def plan_sessions(ctx, mod, session=None, all_sessions=False, log=print):
    """The session codes this run collects, in order (see WHICH SESSIONS)."""
    if getattr(mod, "DATE_DRIVEN", False):
        if session:
            return [session]
        return [None]                      # the module reads its window across sessions
    if session:
        return [session]
    lister = getattr(mod, "list_sessions", None)
    listed = lister(ctx) if lister else None
    if all_sessions:
        if not listed:
            ctx.gap("{0}: no session list from the legislature's index, so the backfill cannot "
                    "choose its sessions; nothing was collected".format(ctx.prov))
            return []
        chosen = [s["code"] for s in listed if overlaps(s, ctx.since, ctx.until)]
        log("  {0}: {1} session(s) listed, {2} touch the window {3}..{4}: {5}".format(
            ctx.prov, len(listed), len(chosen), ctx.since or "(start)", ctx.until or "today",
            " ".join(chosen) or "none"))
        return chosen
    current = mod.CURRENT_SESSION
    newer = [s["code"] for s in listed or []
             if session_order(s["code"]) > session_order(current)]
    for code in newer:
        ctx.gap("{0}: the legislature lists session {1}, newer than CURRENT_SESSION {2}. It is "
                "read this run, but set CURRENT_SESSION in {3}.py so the roster and the "
                "closed-session rules know it".format(ctx.prov, code, current, mod.__name__.replace(".", "/")))
    return [current] + newer


def report(conn, ctx, stats, log=print):
    s = prov_store.summary(conn, ctx.prov)
    log("prov-collect {0}: this run {1}".format(ctx.prov, ", ".join(
        "{0}={1}".format(k, v) for k, v in sorted((stats or {}).items()))))
    log("  store: {members} member(s), {terms} term(s); {bills} bill(s), {bills_ours} on our "
        "ground; {sittings} record(s) read; {recorded} recorded division(s) ({recorded_ok} "
        "tally ok, {recorded_gap} gap, {recorded_totals_only} totals only, {recorded_no_names} no names); "
        "{voice} voice decision(s); "
        "{ours} division(s) on our "
        "ground; {votes} vote(s), {unresolved} unresolved, {with_party} with a dated party at the vote".format(**s))
    if ctx.prov in pc.FRENCH_LAYERS:
        log("  French text matched against config/taxonomy-qc.yaml (AI draft, no Quebec reader "
            "yet), English titles against the English taxonomy, plus config/watchlist-prov.yaml.")
    else:
        log("  Matched against the ENGLISH taxonomy plus config/watchlist-prov.yaml, a "
            "groundwork draft nobody in Canada has reviewed.")


def _add(total, stats):
    for k, v in (stats or {}).items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            total[k] = total.get(k, 0) + v
        else:
            total[k] = v


def run(conn, client, prov, session=None, since=None, until=None, limit=None,
        budget_seconds=drain.DEFAULT_S, dry_run=False, refresh=False, roster=True,
        bills=True, log=print, budget=None, bill_numbers=None, all_sessions=False,
        resume=False, roster_only=False, refresh_roster=False):
    """Drive one province. Returns (stats, gaps)."""
    mod = module_for(prov)
    if resume and since is None and not dry_run:
        since = resume_since(conn, prov, log=log)
    if all_sessions and not since:
        raise SystemExit("prov-collect: --all-sessions needs --since (the backfill's first day)")
    ctx = Context(conn, client, prov, since=since, until=until, limit=limit,
                  budget=budget or drain.Budget(budget_seconds), dry_run=dry_run,
                  refresh=refresh, log=log)
    # --bill N: read only these bills' pages (the listing is still read in
    # full, for the number -> key map). Honoured by qc; the others read all.
    ctx.bill_numbers = set(bill_numbers) if bill_numbers else None
    ctx.refresh_roster = refresh_roster
    stats = {}
    if roster_only:
        if not hasattr(mod, "refresh_roster"):
            raise SystemExit("prov-collect: --roster-only is built for qc only (its roster is "
                             "the whole Assembly, not one session's)")
        _add(stats, mod.refresh_roster(ctx))
    else:
        codes = plan_sessions(ctx, mod, session=session, all_sessions=all_sessions, log=log)
        for n, code in enumerate(codes):
            if n and ctx.stop():
                log("  sessions not started this run (the clock or the record cap): {0}; a later "
                    "dispatch resumes there".format(" ".join(c or "" for c in codes[n:])))
                break
            if len(codes) > 1:
                log("  -- {0} session {1}".format(prov, code))
            kwargs = {"roster": roster, "bills": bills}
            if code is not None:
                kwargs["session"] = code
            elif not getattr(mod, "DATE_DRIVEN", False):
                kwargs["session"] = mod.CURRENT_SESSION
            _add(stats, mod.collect(ctx, **kwargs) or {})
        stats["sessions"] = len(codes)
    if not dry_run:
        db.record_gaps(conn, ctx.feed, ctx.gaps)
        report(conn, ctx, stats, log=log)
    else:
        log("prov-collect {0} (dry run, nothing stored): {1}".format(prov, ", ".join(
            "{0}={1}".format(k, v) for k, v in sorted(stats.items()))))
    if ctx.gaps:
        log("  {0} gap(s) recorded under feed {1}".format(len(ctx.gaps), ctx.feed))
    return stats, ctx.gaps


def known_gap(prov, gap, path=None):
    """True when `gap` (the recorded text) contains a reviewed pattern for
    this province in config/prov_known_gaps.yaml."""
    import yaml
    path = path or os.path.join(ROOT, "config", "prov_known_gaps.yaml")
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    for entry in (cfg.get(prov) or []):
        if entry.get("contains") and entry["contains"] in str(gap):
            return True
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prov", required=True, choices=sorted(prov_store.PROVINCES))
    ap.add_argument("--session", help="legislature-session, e.g. 31-1 (default: the current one, "
                                      "plus any newer one the legislature lists)")
    ap.add_argument("--since", help="first sitting date to read, YYYY-MM-DD")
    ap.add_argument("--until", help="last sitting date to read, YYYY-MM-DD")
    ap.add_argument("--resume", action="store_true",
                    help="without --since: start at the newest record read, less "
                         "{0} days (the weekly)".format(RESUME_LOOKBACK_DAYS))
    ap.add_argument("--all-sessions", action="store_true",
                    help="every session the legislature lists that touches --since/--until "
                         "(the backfill)")
    ap.add_argument("--limit", type=int, help="stop after reading this many sitting records")
    ap.add_argument("--budget-seconds", type=float, default=drain.DEFAULT_S)
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be read, store nothing")
    ap.add_argument("--refresh", action="store_true",
                    help="re-read records already read cleanly")
    ap.add_argument("--refresh-roster", action="store_true",
                    help="re-read the roster whatever its age (qc)")
    ap.add_argument("--roster-only", action="store_true",
                    help="read the roster again and nothing else (qc)")
    ap.add_argument("--no-roster", action="store_true")
    ap.add_argument("--no-bills", action="store_true")
    ap.add_argument("--bill", action="append", metavar="N",
                    help="read only this bill number's page (repeatable; qc only)")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    args = ap.parse_args(argv)
    if args.all_sessions and args.session:
        ap.error("--all-sessions and --session are exclusive")
    if args.all_sessions and not args.since:
        ap.error("--all-sessions needs --since")
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
                       bills=not args.no_bills, bill_numbers=args.bill,
                       all_sessions=args.all_sessions, resume=args.resume,
                       roster_only=args.roster_only, refresh_roster=args.refresh_roster)
    conn.close()
    # Known permanent gaps (config/prov_known_gaps.yaml, reviewed by a human:
    # e.g. a Journal the legislature serves truncated) are still recorded and
    # printed, but do not fail the run -- otherwise one broken source file
    # fails the weekly and alerts every Wednesday for ever (3 October 2026).
    unknown = [g for g in gaps if not known_gap(args.prov, g)]
    if gaps and not unknown:
        print("  every gap is a reviewed known gap (config/prov_known_gaps.yaml): not a failure")
    return 1 if unknown else 0


if __name__ == "__main__":
    sys.exit(main())
