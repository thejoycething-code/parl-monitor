#!/usr/bin/env python3
"""Attendance for the new country editions (src/attendance.py).

    python3 tools/country_attendance.py br               # the weekly step, before member_profiles.py
    python3 tools/country_attendance.py fr cl nl co      # several countries
    python3 tools/country_attendance.py br --years 2025 2026   # a backfill of earlier years
    python3 tools/country_attendance.py cl --db /tmp/cl.db     # a scratch store
    python3 tools/country_attendance.py --participation pl     # print the derived vote participation
    python3 tools/country_attendance.py pt --budget-seconds 600   # PT plenary rolls, a page per sitting

Who attended the committee and plenary sittings, from each parliament's own
open data, into att_sittings / att_marks / att_referrals in the store: the
Câmara's presence register (BR), the Assemblée's commission présences (FR),
the Chilean Cámara's session and committee attendance (CL), the Tweede
Kamer's committee-debate participants (NL, "took part", not a roll call),
Colombia's plenary attendance already in co_attendance (CO), and the
Assembleia's plenary roll, one page per sitting (PT, from 11 October 2026:
at most PT_MAX_SITTINGS rolls and --budget-seconds a run, so the XVII
legislature's backfill spreads over the first few weekly runs). The profiles
step that follows (tools/member_profiles.py) shows it, with the plenary vote
participation derived from the stored votes where they list absences (IT,
CH, PL, ES, AR, PE, DO, HU); the debate packs show who attended the
committee handling the bill. Nothing is posted or DMed.

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

from src import attendance as att  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("countries", nargs="+", help="country codes: " + " ".join(att.COUNTRIES))
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--years", nargs="+", help="BR, CL: the years to read (default: this year)")
    ap.add_argument("--budget-seconds", type=float, default=None,
                    help="PT: stop reading sitting rolls after this many seconds "
                         "(tools/collector_budget.sh); the rest are read next run")
    ap.add_argument("--max-sittings", type=int, default=None,
                    help="PT: at most this many sitting rolls this run (default "
                         "src/attendance.PT_MAX_SITTINGS)")
    ap.add_argument("--participation", action="store_true",
                    help="print each member's derived plenary vote participation; fetch nothing")
    args = ap.parse_args(argv)
    if args.participation:
        conn = sqlite3.connect(args.db)
        for cc in args.countries:
            got, basis = att.participation(conn, cc, args.date)
            if not got:
                print("{0}: no participation figure (the vote records do not list "
                      "absences)".format(cc))
                continue
            print("{0}: {1} member(s); basis: {2}".format(cc, len(got), basis))
            for key, r in sorted(got.items(), key=lambda kv: (kv[1]["cast"] / kv[1]["of"],
                                                              str(kv[1]["name"])))[:20]:
                print("  {0}: {1}".format(r["name"] or key, att.participation_text(r)))
        return 0
    bad = [c for c in args.countries if c not in att.FETCHERS]
    if bad:
        ap.error("no attendance source for: " + ", ".join(bad))
    conn = att.ensure(sqlite3.connect(args.db))
    client = HttpClient(raw_dir=args.raw)
    rc = 0
    for cc in args.countries:
        try:
            done = att.collect(conn, client, cc, args.date, years=args.years,
                               budget=args.budget_seconds, max_sittings=args.max_sittings)
        except (FetchError, ValueError, KeyError, sqlite3.Error) as exc:
            print("  [gap] attendance {0}: {1}; last run's rows kept".format(cc, str(exc)[:200]))
            rc = 3
            continue
        except Exception:  # one country's failure never costs the others
            traceback.print_exc()
            print("  [gap] attendance {0}: failed; last run's rows kept".format(cc))
            rc = 3
            continue
        print("attendance {0}: {1}".format(cc, "; ".join(
            "{0} {1} sitting(s), {2} mark(s)".format(s, n, m)
            for s, (n, m) in sorted(done.items()))))
    conn.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
