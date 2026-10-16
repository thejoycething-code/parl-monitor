#!/usr/bin/env python3
"""Regional parliaments' forward business into regional_agenda: plenary and
committee agendas, orders of the day, notice papers and session calendars,
from today to as far ahead as each parliament publishes
(src/regional_agenda.py; one source module per country in
src/regional_agendas/).

    python3 tools/regional_agenda.py de                  # every Land, 56 days
    python3 tools/regional_agenda.py ca --regions on bc  # some provinces
    python3 tools/regional_agenda.py ch --days 28 --db /tmp/scratch.db
    python3 tools/regional_agenda.py --list              # routes per region

Run as a step of the country's weekly job, after its regional collector.
Fails loud: every region that cannot be read is a [gap] line and a gaps row
(feed '<cc>-regional-agenda') and keeps its stored rows; a region with no
permitted route is a [no-route] / [blocked] line every run. Exit 0 when every
region with a reader was read, 3 when some were not, 1 when none was.

robots.txt is asked for every request and every redirect hop
(src/robots_guard.guard); documented APIs pass as everywhere else.
ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, regional_agenda as ra  # noqa: E402
from src.http import HttpClient  # noqa: E402
from src.robots_guard import guard  # noqa: E402


def make_client(raw_dir, cc, budget=None):
    raw = HttpClient(raw_dir=raw_dir, throttle=1.0)
    mod = ra.module(cc)
    for host, seconds in getattr(mod, "THROTTLES", {}).items():
        raw.set_host_throttle(host, seconds)
    return guard(raw, ra.feed(cc), budget=budget)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cc", nargs="*", help="country codes: " + " ".join(ra.COUNTRIES))
    ap.add_argument("--regions", nargs="*", help="region codes (default: all)")
    ap.add_argument("--days", type=int, default=ra.DEFAULT_DAYS)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--date", help="read as if on this ISO date")
    ap.add_argument("--budget-seconds", type=float, default=None)
    ap.add_argument("--list", action="store_true", help="print each region's route and exit")
    args = ap.parse_args(argv)

    if args.list:
        for cc in (args.cc or ra.COUNTRIES):
            try:
                mod = ra.module(cc)
            except ImportError:
                continue
            for code, reg in mod.REGIONS.items():
                print("{0} {1:6} {2:28} {3}".format(
                    cc, code, reg.name[:28], "reader" if reg.reader else
                    "{0}: {1}".format(reg.status, reg.note)))
        return 0
    if not args.cc:
        ap.error("name at least one country")
    bad = [c for c in args.cc if c not in ra.COUNTRIES]
    if bad:
        ap.error("unknown country code(s): " + " ".join(bad))

    today = args.date or datetime.date.today().isoformat()
    conn = db.init_db(db.connect(args.db))
    rc_all = []
    for cc in args.cc:
        print("{0} regional forward agendas, {1} + {2} days".format(cc.upper(), today, args.days))
        try:
            client = make_client(args.raw_dir, cc, budget=args.budget_seconds)
            s = ra.collect(conn, cc, client, today, days=args.days, regions=args.regions,
                           budget_seconds=args.budget_seconds)
        except Exception as exc:                            # noqa: BLE001
            print("  [gap] {0}-regional-agenda failed: {1}".format(cc, str(exc)[:200]))
            db.record_gap(conn, ra.feed(cc), "failed: {0}".format(str(exc)[:200]))
            rc_all.append(1)
            continue
        print(ra.summary_line(cc, s))
        readers = len(s["read"]) + len(s["gap"]) + len(
            [c for c in s["blocked"] if ra.module(cc).REGIONS[c].reader])
        if readers and not s["read"]:
            rc_all.append(1)
        elif s["gap"] or [c for c in s["blocked"] if ra.module(cc).REGIONS[c].reader]:
            rc_all.append(3)
        else:
            rc_all.append(0)
    conn.close()
    return max(rc_all) if 1 not in rc_all else 1


if __name__ == "__main__":
    sys.exit(main())
