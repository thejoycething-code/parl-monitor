#!/usr/bin/env python3
"""Fetch and cache member portraits for the country vote pages (src/portraits.py).

    python3 tools/fetch_portraits.py                    # every country with an OK licence
    python3 tools/fetch_portraits.py --country pl --max 50
    python3 tools/fetch_portraits.py --list             # the sources and their licence class

Only countries whose photo licence docs/portraits-logos-licences.md classes as
usable are fetched: OK with attribution, internal non-commercial use (the
partner pages count, Chris, 12 October 2026), or used on Chris's instruction
with the licence unclear (12 October 2026, credited "<institution> (official
portrait)"); "not allowed" is never fetched, and every other country is
skipped by name. Only the members on the
country's vote page are fetched (src/country_votes.build), at most --max new
or due photos per country per run (default 150), so the first weeks fill the
cache gradually and later runs fetch only new members, refreshes (180 days)
and rechecks of members with no photo (30 days).

Politeness: src/http.py (the honest CitizenGO UA, the per-host throttle,
retries with backoff), robots.txt read per host per run through the guard
(src/robots_guard, src/prov_fetch.read_robots) and obeyed for the photos and
for any member page read to find one (an unreadable robots.txt means no
fetch), no bot check ever bypassed. The photos are not
archived to data/raw (the image URL in the manifest is the provenance).

Writes data/portraits/<cc>/<file>.jpg (gitignored) and data/portraits/<cc>.json
(committed). Read-only on the store. Run by jobs/editions-session-judge.sh on
the Mini (sips makes the thumbnails), before the vote pages are built.
Exit 0 when every country ran, 1 when one failed (the others still run).
"""

from __future__ import annotations

import argparse
import datetime
import os
import sqlite3
import sys
import traceback
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country_votes as cv  # noqa: E402
from src import portraits as pt  # noqa: E402


def page_members(conn, cc, today):
    """[(key, member-like)] for the members on a country's vote page."""
    data = cv.build(conn, cc, today)
    out = []
    for key, m in zip(data["_keys"], data["members"]):
        if str(key).startswith("name:"):
            continue      # named in a record only: no source id to find a photo by
        out.append((key, types.SimpleNamespace(name=m[0], party=m[1], chamber=m[2],
                                               region=m[3])))
    return out


def main(argv=None, client=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--country", action="append")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--cache", default=pt.CACHE_DIR)
    ap.add_argument("--max", type=int, default=150, help="photos fetched per country per run")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--list", action="store_true", help="print the sources and stop")
    args = ap.parse_args(argv)
    if args.list:
        for cc in sorted(pt.SOURCES):
            s = pt.SOURCES[cc]
            print("{0}  {1:<12} {2:<5} {3}: {4}".format(
                cc, s.licence_class, "use" if s.usable else "skip", s.legislature, s.licence))
        return 0
    usable = pt.usable_countries()
    countries = args.country or [cc for cc in usable if cc in cv.COUNTRIES]
    if not os.path.exists(args.db):
        print("portraits: no store at {0}".format(args.db))
        return 1
    conn = sqlite3.connect("file:{0}?mode=ro".format(args.db), uri=True)
    if client is None:
        from src.http import HttpClient
        client = HttpClient(os.path.join(ROOT, "data", "raw"))
    robots = pt.Robots(client, log=print)
    rc = 0
    for cc in countries:
        if cc not in usable:
            src = pt.SOURCES.get(cc)
            print("portraits {0}: skipped, photo licence {1} (docs/portraits-logos-licences.md)"
                  .format(cc, src.licence_class if src else "not assessed for use"))
            continue
        try:
            members = page_members(conn, cc, args.date)
            got = pt.fetch_country(client, cc, members, args.date, max_fetch=args.max,
                                   cache_dir=args.cache, robots=robots)
        except Exception:
            traceback.print_exc()
            print("  [gap] portraits {0}: failed; the cached ones stand".format(cc))
            rc = 1
            continue
        print("portraits {0}: {1} member(s) on the page; {2} fetched, {3} without a photo, "
              "{4} refused by robots.txt, {5} up to date, {6} left for the next run".format(
                  cc, len(members), got["fetched"], got["missing"], got["refused"],
                  got["not_due"], got["left"]))
    conn.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
