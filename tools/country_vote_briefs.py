#!/usr/bin/env python3
"""Same-day vote briefs for the new country editions and the Latam monitor.

    python3 tools/country_vote_briefs.py --country pl                # from the store, print only
    python3 tools/country_vote_briefs.py --country pl --send         # brief, DM Chris, record
    python3 tools/country_vote_briefs.py --daily --send              # the daily direct pass
    python3 tools/country_vote_briefs.py --country it --db /tmp/it.db --since 2026-09-09 \\
        --out /tmp/briefs --no-seed                                   # a sample, nothing recorded

Handover item 1 (docs/country-parity-handover.md). The rules, the ledger
and the rendering are src/country_vote_brief.py's; the daily readers are
src/vote_brief_sources.py's.

FROM THE STORE (--country, repeatable): a step in each country's weekly
(or fortnightly) job, right after its collector, over the last --days
(default 14, so Guatemala's and Mexico's fortnightly pulls are covered).

DAILY (--daily): ONE pass for every country whose source publishes votes
the same day cheaply and openly (the Netherlands, Poland, Switzerland,
Brazil, Italy), over the last --days (default 3: late positions and a
missed slot). Each reader fills one throwaway store in a temporary
directory, never data/; it is deleted afterwards. A reader that fails is a
[gap] line and costs the other countries nothing. jobs/vote-briefs-daily.sh
runs it on the Mac Mini, and publishes the raw payloads it archived.

Without --send nothing is sent and the ledger is not touched (briefs are
still written, to --out). The DM goes to Chris alone (U05LJP0BT61).
"""

from __future__ import annotations

import argparse
import datetime
import os
import shutil
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import country_vote_brief as cvb  # noqa: E402
from src import db  # noqa: E402
from src import vote_brief_sources as sources  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

STORE_DAYS = 14
DAILY_DAYS = 3


def daily(client, since, today, countries=sources.DAILY, log=print, scratch_dir=None):
    """Fill one scratch store from the direct readers. Returns (conn, path,
    the countries read)."""
    path = os.path.join(scratch_dir or tempfile.mkdtemp(prefix="vote-briefs-"), "scratch.db")
    conn = db.init_db(db.connect(path))
    read = []
    for cc in countries:
        reader = sources.READERS[cc]
        try:
            n = reader.collect(conn, client, since, today, log=log)
            if n:
                conn.row_factory = sqlite3.Row
                want = {it["key"] for it, _r in cvb.candidates(conn, cc, since, today)
                        if cvb.awaiting_positions(it)}
                conn.row_factory = None
                got = reader.positions(conn, client, today, log=log, keys=want) if want else 0
                log("{0}: positions read for {1} of {2} vote(s) to brief".format(cc, got, len(want)))
            read.append(cc)
        except (FetchError, ValueError, KeyError, IndexError, TypeError, sqlite3.Error) as exc:
            conn.rollback()
            log("  [gap] {0}: the daily reader failed: {1}".format(cc, str(exc)[:160]))
    conn.row_factory = sqlite3.Row
    return conn, path, read


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--country", action="append",
                    help="a country code (repeatable): {0}".format(", ".join(cvb.COUNTRIES)))
    ap.add_argument("--daily", action="store_true",
                    help="read today's votes directly ({0})".format(", ".join(sources.DAILY)))
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--date", default=datetime.date.today().isoformat(), help="today (YYYY-MM-DD)")
    ap.add_argument("--since", help="window start, exclusive (default: --days before --date)")
    ap.add_argument("--days", type=int)
    ap.add_argument("--send", action="store_true", help="DM Chris and record in the ledger")
    ap.add_argument("--no-seed", action="store_true",
                    help="brief even on a country's first pass (samples; implies no ledger)")
    ap.add_argument("--out", default=cvb.BRIEFS)
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    args = ap.parse_args(argv)
    if bool(args.country) == bool(args.daily):
        ap.error("give --country (from the store) or --daily (direct), not both")
    bad = [c for c in args.country or [] if c not in cvb.COUNTRIES]
    if bad:
        ap.error("no vote brief for: {0}".format(", ".join(bad)))
    today = args.date
    days = args.days or (DAILY_DAYS if args.daily else STORE_DAYS)
    since = args.since or cvb.window_start(today, days)
    ledger_dir = None
    if args.no_seed:
        if args.send:
            ap.error("--no-seed is for samples; it never sends")
        ledger_dir = tempfile.mkdtemp(prefix="vote-briefs-ledger-")
        for cc in args.country or sources.DAILY:
            cvb.save(dict(cvb.load(cc, ledger_dir), seeded="sample"), today, ledger_dir)
    scratch = None
    if args.daily:
        client = HttpClient(raw_dir=args.raw_dir)
        conn, scratch, countries = daily(client, since, today)
        label = "Same-day vote briefs"
    else:
        if not os.path.exists(args.db):
            print("no store at {0}".format(args.db))
            return 1
        conn = sqlite3.connect("file:{0}?mode=ro".format(args.db), uri=True)
        conn.row_factory = sqlite3.Row
        countries = args.country
        label = "Vote briefs after the {0} collection".format(
            ", ".join(cvb.country_name(c) for c in countries))
    try:
        cvb.run(conn, countries, since, today, today=today, out_dir=args.out, dm=args.send,
                directory=ledger_dir, label=label, sample=args.no_seed)
        if args.send and not args.daily:
            for cc in countries:       # the daily reader's map of bills (Poland)
                path = sources.save_parents(cc, conn)
                if path:
                    print("{0}: wrote {1}".format(cc, os.path.relpath(path, ROOT)))
    finally:
        conn.close()
        if scratch:
            shutil.rmtree(os.path.dirname(scratch), ignore_errors=True)
        if ledger_dir:
            shutil.rmtree(ledger_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
