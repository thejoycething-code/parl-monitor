#!/usr/bin/env python3
"""The week ahead for the country editions: read one country's agenda into
the store (src/agenda.py; one source module per country in src/agendas/).

    python3 tools/country_agenda.py nl
    python3 tools/country_agenda.py pl --days 28
    python3 tools/country_agenda.py fr --db /tmp/sample.db

Run as a step of the country's weekly job (jobs/<cc>-weekly.sh), after its
collector and before its edition, so the edition's week-ahead section
reads this week's agenda and the agenda's bills are matched against this
week's store. Exit 0 when the agenda was read, 3 when it was stored with
gaps (recorded in the gaps table as '<cc>-agenda'), 1 on a failure that
stored nothing. The job treats any failure as a [gap] line: the agenda
never costs the store or the edition.

ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import agenda, db  # noqa: E402
from src.http import HttpClient  # noqa: E402

COUNTRIES = ("nl", "pl", "ch", "br", "it", "fr", "at", "es", "ar")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cc", nargs="+", choices=COUNTRIES)
    ap.add_argument("--days", type=int, default=agenda.FETCH_DAYS,
                    help="how far ahead to read (default %(default)s)")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--date", help="read as if on this ISO date")
    args = ap.parse_args(argv)

    today = args.date or datetime.date.today().isoformat()
    client = HttpClient(raw_dir=args.raw_dir, throttle=1.0)
    conn = db.init_db(db.connect(args.db))
    rc = 0
    for cc in args.cc:
        try:
            _, _, gaps = agenda.collect(conn, cc, client, today, days=args.days)
        except Exception as exc:                            # noqa: BLE001
            print("  [gap] {0}-agenda failed: {1}".format(cc, str(exc)[:160]))
            db.record_gap(conn, "{0}-agenda".format(cc), "failed: {0}".format(str(exc)[:160]),
                          today)
            rc = 1
            continue
        if gaps and rc == 0:
            rc = 3
    conn.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
