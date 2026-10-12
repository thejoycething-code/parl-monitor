#!/usr/bin/env python3
"""Length of service for the new country editions (src/member_service.py).

    python3 tools/member_service.py ch                 # the weekly step, before member_profiles.py
    python3 tools/member_service.py fr at pt --force   # read now, whatever the cadence
    python3 tools/member_service.py br --budget 300    # a per-member source, five minutes
    python3 tools/member_service.py pl --db /tmp/pl.db # a scratch store

Every period each member has sat (start, end, chamber, party or group where
the source gives it) and the dated party or group spells, from each
parliament's own open data, into ms_periods / ms_party / ms_runs. The
profiles (tools/member_profiles.py) and the vote pages
(tools/make_country_votes.py) read them: "Serving since" and earlier
periods, never more than the source supports, and DERIVED positions given
only for days the member sat, by the group they were in on the day.

A country whose source was read within its cadence (src/member_service.py
STALE_DAYS: a week for one-request sources, four weeks for a request a
member or a dozen files) is skipped unless --force. Nothing is posted or DMed.

Exit 0 when every country was read or skipped, 3 when one failed (its [gap]
line printed, its rows from the last run kept, the others still read): the
weekly jobs treat a failure here as a gap, never as the run's failure.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sqlite3
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import member_service as ms  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from src.robots_guard import guard  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("countries", nargs="+", help="country codes: " + " ".join(ms.COUNTRIES))
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--force", action="store_true", help="read now, whatever the cadence")
    ap.add_argument("--budget", type=int, default=None,
                    help="seconds for a per-member source (AT, BR); default "
                         "src/member_service.BUDGET")
    args = ap.parse_args(argv)
    bad = [c for c in args.countries if c not in ms.FETCHERS]
    if bad:
        ap.error("no service source for: " + ", ".join(bad))
    conn = ms.ensure(sqlite3.connect(args.db))
    client = guard(HttpClient(raw_dir=args.raw), 'member-service')
    rc = 0
    for cc in args.countries:
        if not args.force and not ms.due(conn, cc, args.date):
            print("member-service {0}: read {1}, not due (every {2} days)".format(
                cc, ms.last_read(conn, cc), ms.STALE_DAYS.get(cc, 7)))
            continue
        try:
            done = ms.collect(conn, client, cc, args.date, budget=args.budget)
        except (FetchError, ValueError, KeyError, sqlite3.Error) as exc:
            print("  [gap] member-service {0}: {1}; last run's rows kept".format(cc, str(exc)[:200]))
            rc = 3
            continue
        except Exception:  # one country's failure never costs the others
            traceback.print_exc()
            print("  [gap] member-service {0}: failed; last run's rows kept".format(cc))
            rc = 3
            continue
        print("member-service {0}: {1}".format(cc, "; ".join(
            "{0} {1} period(s), {2} spell(s)".format(s, p, n)
            for s, (p, n) in sorted(done.items()))))
    conn.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
