#!/usr/bin/env python3
"""Government consultations and publications for the country editions: read
one country's official sources into gov_docs (src/gov_docs.py; one reader per
country in src/gov_doc_sources/).

    python3 tools/country_gov_docs.py de
    python3 tools/country_gov_docs.py fr nl --db /tmp/scratch.db
    python3 tools/country_gov_docs.py de --reclassify       # offline
    python3 tools/country_gov_docs.py de --deadlines        # open consultations, offline

Run as a step of the country's weekly job (jobs/<cc>-weekly.sh), after the
petitions step and before the edition. Exit 0 when every source was read, 3
when something was stored with gaps (gaps rows under '<cc>-govdocs-<source>'
and [gap] lines), 1 when a country failed outright. The job turns any
failure into a [gap] line: gov docs never cost the store or the edition.

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
    args = ap.parse_args(argv)

    today = args.date or datetime.date.today().isoformat()
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


if __name__ == "__main__":
    sys.exit(main())
