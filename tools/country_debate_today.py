#!/usr/bin/env python3
"""Name today's key debate on our ground in a new country, if there was one.

    python3 tools/country_debate_today.py nl                  # today
    python3 tools/country_debate_today.py fr --date 2026-10-09
    python3 tools/country_debate_today.py --all               # every qualifying country
    python3 tools/country_debate_today.py --list              # which countries qualify, and why not

The new countries' tools/debate_today.py (src/country_live.py). For each
country it prints the day's agenda points on our ground (country_agenda,
read-only), the debates the chamber has published so far with their
speakers on our ground (each speech matched in its own words by the
country's own collector, tools/<cc>_chamber.py, into a throwaway in-memory
store: the real store is never written), and a final line

    KEY DEBATE: <cc> | <chamber> | <title> | <debate id> | N speakers | areas A
    KEY DEBATE: <cc> | none

which the same-day net task (ops/scheduled-tasks/debate-day-net.md) reads.
The key debate id is what tools/country_live_debate.py --debate takes.

Only countries whose source publishes the day's speeches the same day
qualify (--list). Exit 0 either way; exit 2 for a single country when the
source has published nothing for the day yet. Fetches, archives raw replies,
posts nothing, calls no AI.
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country_live as cl  # noqa: E402
from src.http import HttpClient  # noqa: E402


def listing():
    print("Qualify (the chamber source publishes the day's speeches the same day):")
    for cc, q in cl.QUALIFYING.items():
        print("  {0}  {1}: {2}{3}".format(cc, q["source"], q["delay"],
                                          "" if q["live"] else " [after each sitting, not mid-sitting]"))
    print("Do not qualify:")
    for cc, why in cl.NOT_QUALIFYING.items():
        print("  {0}  {1}".format(cc, why))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cc", nargs="*")
    ap.add_argument("--all", action="store_true", help="every qualifying country")
    ap.add_argument("--list", action="store_true", help="which countries qualify")
    ap.add_argument("--date", default=cl.today_local())
    ap.add_argument("--key", type=int, default=cl.KEY_SPEAKERS, help="speakers on our ground that make a key debate")
    ap.add_argument("--db", default=cl.STORE, help="the store, read-only (agenda, roster)")
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--budget-seconds", type=float, default=300.0, help="per country")
    ap.add_argument("--quiet", action="store_true", help="no collector log lines")
    args = ap.parse_args(argv)
    if args.list:
        listing()
        return 0
    codes = list(cl.COUNTRIES) if args.all else args.cc
    if not codes:
        ap.error("name a country, or --all, or --list")
    for cc in codes:
        if cc not in cl.QUALIFYING:
            ap.error("{0} does not qualify: {1}".format(cc, cl.NOT_QUALIFYING.get(cc, "no chamber collector")))
    client = HttpClient(raw_dir=args.raw_dir, throttle=1.0)
    log = (lambda *a, **k: None) if args.quiet else print
    rc = 0
    for cc in codes:
        text, rows, published = cl.day(cc, args.date, client, args.db, args.key, log=log,
                                       budget=args.budget_seconds)
        print(text)
        if len(codes) == 1 and not published:
            print("{0}: the source has published nothing for {1} yet.".format(cc, args.date))
            rc = 2
    return rc


if __name__ == "__main__":
    sys.exit(main())
