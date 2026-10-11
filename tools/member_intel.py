#!/usr/bin/env python3
"""Member intelligence for the new country editions (src/member_intel.py).

    python3 tools/member_intel.py br                 # the weekly step, before member_profiles.py
    python3 tools/member_intel.py nl ch pl fr it at  # several countries
    python3 tools/member_intel.py br --full          # every Brazilian front now (about 15 minutes)
    python3 tools/member_intel.py pl --db /tmp/pl.db # a scratch store

Committees, cross-party groups (Brazil's frentes parlamentares, France's
groupes d'études) and registers of interests (the Tweede Kamer's
nevenfuncties, the Swiss Interessenbindungen) from each parliament's own open
data, into mi_groups / mi_interests in the store. The profiles step that
follows (tools/member_profiles.py) shows them and flags the groups on our
ground (config/member-intel-groups.yaml). Nothing is posted or DMed.

Exit 0 when every country was read, 3 when one failed (its [gap] line
printed, its rows from the last run kept, the others still read): the weekly
jobs treat a failure here as a gap, never as the run's failure.
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

from src import member_intel as mi  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("countries", nargs="+", help="country codes: " + " ".join(mi.COUNTRIES))
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--full", action="store_true",
                    help="Brazil: read every front now, not the week's rotation")
    args = ap.parse_args(argv)
    bad = [c for c in args.countries if c not in mi.FETCHERS]
    if bad:
        ap.error("no member-intel source for: " + ", ".join(bad))
    conn = mi.ensure(sqlite3.connect(args.db))
    client = HttpClient(raw_dir=args.raw)
    rc = 0
    for cc in args.countries:
        try:
            done = mi.collect(conn, client, cc, args.date, full=args.full)
        except (FetchError, ValueError, KeyError, sqlite3.Error) as exc:
            print("  [gap] member-intel {0}: {1}; last run's rows kept".format(cc, str(exc)[:200]))
            rc = 3
            continue
        except Exception:  # one country's failure never costs the others
            traceback.print_exc()
            print("  [gap] member-intel {0}: failed; last run's rows kept".format(cc))
            rc = 3
            continue
        print("member-intel {0}: {1}".format(cc, "; ".join(
            "{0} {1} membership(s), {2} interest(s)".format(s, g, i)
            for s, (g, i) in sorted(done.items()))))
    conn.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
