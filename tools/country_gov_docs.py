#!/usr/bin/env python3
"""Government consultations and publications for the country editions: read
one country's official sources into gov_docs (src/gov_docs.py; one reader per
country in src/gov_doc_sources/).

    python3 tools/country_gov_docs.py de
    python3 tools/country_gov_docs.py fr nl --db /tmp/scratch.db
    python3 tools/country_gov_docs.py de --reclassify       # offline
    python3 tools/country_gov_docs.py de --deadlines        # open consultations, offline
    python3 tools/country_gov_docs.py pt --daily            # the daily read, NO STORE

Run as a step of the country's weekly job (jobs/<cc>-weekly.sh), after the
petitions step and before the edition. Exit 0 when every source was read, 3
when something was stored with gaps (gaps rows under '<cc>-govdocs-<source>'
and [gap] lines), 1 when a country failed outright. The job turns any
failure into a [gap] line: gov docs never cost the store or the edition.

--daily (16 October 2026): for a country whose reader has a daily() (Portugal:
the Diário da República's feeds carry only the latest issue), read today's
issue into its committed ledger under data/gov-docs-daily/ WITHOUT opening
the store (the daily job is `mini_run: no-store`; creating an empty store
file there would read as an unpublished store). The weekly step stores the
ledger's rows. Exit 0, 3 (read with gaps) or 1 (failed).

ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, gov_docs  # noqa: E402
from src.http import HttpClient  # noqa: E402
from src.robots_guard import guard  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cc", nargs="+", choices=gov_docs.countries())
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--date", help="read as if on this ISO date")
    ap.add_argument("--window-days", type=int, default=gov_docs.WINDOW_DAYS)
    ap.add_argument("--reclassify", action="store_true", help="re-derive areas, offline")
    ap.add_argument("--deadlines", action="store_true",
                    help="print the open consultations on our ground, offline")
    ap.add_argument("--daily", action="store_true",
                    help="the reader's daily() into its ledger; the store is never opened")
    args = ap.parse_args(argv)

    today = args.date or datetime.date.today().isoformat()
    if args.daily:
        return daily(args.cc, today, args.raw_dir)
    conn = db.init_db(db.connect(args.db))
    if args.deadlines:
        far = (datetime.date.fromisoformat(today) + datetime.timedelta(days=366)).isoformat()
        for cc in args.cc:
            for r in gov_docs.deadline_rows(conn, cc, today, far):
                print("{0} {1} closes {2} [{3}] {4} ({5}) {6}".format(
                    cc, r["doc_type"], r["closing_date"], r["areas"], r["title"][:90],
                    r["body"] or "", r["url"]))
        conn.close()
        return 0
    if args.reclassify:
        for cc in args.cc:
            gov_docs.reclassify(conn, cc)
        conn.close()
        return 0
    client = guard(HttpClient(raw_dir=args.raw_dir, throttle=1.0), "country-gov-docs")
    rc = 0
    for cc in args.cc:
        try:
            listed, kept, gaps = gov_docs.collect(conn, cc, client, today,
                                                  window_days=args.window_days)
        except Exception as exc:                            # noqa: BLE001
            print("  [gap] {0}-govdocs failed: {1}".format(cc, str(exc)[:200]))
            db.record_gap(conn, "{0}-govdocs".format(cc), "failed: {0}".format(str(exc)[:200]), today)
            rc = 1
            continue
        print("{0}-govdocs: {1} listed, {2} on our ground, {3} gap(s)".format(cc, listed, kept, gaps))
        if gaps and rc == 0:
            rc = 3
    conn.close()
    return rc


def daily(ccs, today, raw_dir, client=None, log=print):
    """The daily reads (no store). 0 clean, 3 with gaps, 1 failed or no daily()."""
    client = client or guard(HttpClient(raw_dir=raw_dir, throttle=1.0), "country-gov-docs")
    rc = 0
    for cc in ccs:
        fn = getattr(gov_docs.module(cc), "daily", None)
        if fn is None:
            log("  [gap] {0}-govdocs: no daily read for this country".format(cc))
            rc = 1
            continue
        try:
            read, added, gaps = fn(client, today, log=log)
        except Exception as exc:                            # noqa: BLE001
            log("  [gap] {0}-govdocs daily failed: {1}".format(cc, str(exc)[:200]))
            rc = 1
            continue
        for g in gaps:
            log("  [gap] {0}-govdocs daily: {1}".format(cc, g))
        if gaps and rc == 0:
            rc = 1 if not read else 3
    return rc


if __name__ == "__main__":
    sys.exit(main())
