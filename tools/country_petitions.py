#!/usr/bin/env python3
"""Petitions and consultations for the country editions: read one country's
sources into the store (src/petitions.py; one source module per country in
src/petition_sources/).

    python3 tools/country_petitions.py fr
    python3 tools/country_petitions.py at ch --no-detail
    python3 tools/country_petitions.py fr --reclassify      # offline
    python3 tools/country_petitions.py fr at --report       # open on our ground, offline
    python3 tools/country_petitions.py fr --db /tmp/sample.db

Run as a step of the country's weekly job (jobs/<cc>-weekly.sh), after its
collector and before its edition, so the edition's "Petitions and
consultations" section reads this week's counts. Exit 0 when every source
was read, 3 when something was stored with gaps (recorded in the gaps table
as '<cc>-petitions-<source>'), 1 when nothing was stored. The job treats
any failure as a [gap] line: petitions never cost the store or the edition.

ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, petitions  # noqa: E402
from src.http import HttpClient  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cc", nargs="+", choices=petitions.countries())
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--date", help="read as if on this ISO date")
    ap.add_argument("--no-detail", action="store_true", help="listings only, no item pages")
    ap.add_argument("--detail-limit", type=int, default=petitions.DETAIL_LIMIT)
    ap.add_argument("--reclassify", action="store_true", help="re-derive areas, offline")
    ap.add_argument("--report", action="store_true",
                    help="print the open items on our ground (Markdown), offline")
    args = ap.parse_args(argv)

    today = args.date or datetime.date.today().isoformat()
    conn = db.init_db(db.connect(args.db))
    if args.report:
        for cc in args.cc:
            print("\n".join(petitions.campaign_report(conn, cc, today)))
        conn.close()
        return 0
    if args.reclassify:
        for cc in args.cc:
            petitions.reclassify(conn, cc)
        conn.close()
        return 0
    client = HttpClient(raw_dir=args.raw_dir, throttle=1.0)
    rc = 0
    for cc in args.cc:
        try:
            listed, _, gaps = petitions.collect(conn, cc, client, today,
                                                detail=not args.no_detail,
                                                detail_limit=args.detail_limit)
        except Exception as exc:                            # noqa: BLE001
            print("  [gap] {0}-petitions failed: {1}".format(cc, str(exc)[:160]))
            db.record_gap(conn, "{0}-petitions".format(cc),
                          "failed: {0}".format(str(exc)[:160]), today)
            rc = 1
            continue
        if gaps and rc == 0:
            rc = 3 if listed else 1
    conn.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
