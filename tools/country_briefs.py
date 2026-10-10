#!/usr/bin/env python3
"""Campaign brief drafts for the new countries (src/country_briefs.py).

    python3 tools/country_briefs.py --cc pl            # the weekly step: new and refreshed briefs
    python3 tools/country_briefs.py --cc pl --list     # the subjects, write nothing
    python3 tools/country_briefs.py --cc pl --force SLUG_OR_KEY   # rewrite one, even if edited
    python3 tools/country_briefs.py --cc pl --subject 10/2110      # brief a quiet live bill now
    python3 tools/country_briefs.py --all-countries
    python3 tools/country_briefs.py --db-map stores.txt --out-dir DIR --ledger-dir DIR --no-log

One brief per watched or tier-1 bill that moved in the last 90 days, at most
eight new ones per country per run, in briefs/<cc>-<title>-<key>.md and .csv
(and -5ca.csv once CONFIRMED readings place anyone). Every brief is NOT READY
until the bill's direction and every reading of its votes in
config/<cc>_stance.yaml are confirmed by a named person
(tools/country_5ca.py --confirm-direction / --confirm / --sign-from-doc).
An unedited brief is refreshed each week; an edited one is left alone. Reads
the store; writes brief_log rows (status not-ready / draft) and the ledger
data/country-briefs/<cc>.json. Sends nothing, calls no model.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country_briefs as cb  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cc", action="append", default=[], help="country code (repeatable)")
    ap.add_argument("--all-countries", action="store_true")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--db-map", help="file of 'cc path' lines: a store per country (scratch runs)")
    ap.add_argument("--list", action="store_true", help="show the subjects, write nothing")
    ap.add_argument("--force", action="append", default=[], help="rewrite this brief (slug or key)")
    ap.add_argument("--subject", action="append", default=[], help="brief this live bill now (key)")
    ap.add_argument("--today", default=datetime.date.today().isoformat())
    ap.add_argument("--recent-days", type=int, default=cb.RECENT_DAYS)
    ap.add_argument("--max-new", type=int, default=cb.MAX_NEW)
    ap.add_argument("--out-dir", default=cb.BRIEFS_DIR)
    ap.add_argument("--ledger-dir", default=cb.LEDGER_DIR)
    ap.add_argument("--config", default=cb.CONFIG_PATH)
    ap.add_argument("--config-dir", help="where the stance and watchlist files live (tests)")
    ap.add_argument("--no-log", action="store_true", help="write no brief_log row (scratch stores)")
    args = ap.parse_args(argv)

    cfg = cb.load_config(args.config)
    ccs = list(cfg["countries"]) if args.all_countries else []
    for c in args.cc:
        ccs += [x.strip() for x in c.split(",") if x.strip()]
    stores = {}
    if args.db_map:
        with open(args.db_map, encoding="utf-8") as h:
            for line in h:
                bits = line.split()
                if len(bits) == 2 and not line.startswith("#"):
                    stores[bits[0]] = bits[1]
        if not ccs:
            ccs = [cc for cc in cfg["countries"] if cc in stores]
    bad = [cc for cc in ccs if cc not in cfg["countries"]]
    if bad:
        ap.error("no config/country-briefs.yaml entry for: " + ", ".join(bad))
    if not ccs:
        ap.error("--cc CC, --all-countries or --db-map")

    rc = 0
    for cc in ccs:
        path = stores.get(cc, args.db)
        if not os.path.exists(path):
            print("country-briefs: {0}: no store at {1}; skipped".format(cc, path))
            continue
        ro = args.list or args.no_log
        conn = sqlite3.connect("file:{0}?mode=ro".format(path) if ro else path, uri=ro)
        conn.row_factory = sqlite3.Row
        try:
            if args.list:
                subs = cb.subjects(conn, cc, args.today, args.recent_days, args.config_dir)
                ledger = cb.load_ledger(cc, args.ledger_dir)
                print("country-briefs: {0}: {1} live watched or tier-1 bill(s), {2} moved in "
                      "{3} days".format(cc, len(subs), sum(1 for s in subs if s["recent"]),
                                        args.recent_days))
                for s in subs:
                    print("  {0} {1} {2} {3}\n      {4}".format(
                        "brief" if s["slug"] in ledger else ("NEW  " if s["recent"] else "quiet"),
                        "W " if s["watched"] else "t1", s["last_date"] or "?", s["key"], s["slug"]))
                continue
            got = cb.run(conn, cc, cfg, args.today, args.out_dir, args.ledger_dir, args.config_dir,
                         args.recent_days, args.max_new, args.force, args.subject,
                         write_log=not args.no_log)
            print("country-briefs: {0}: {1} new, {2} refreshed, {3} ready ({4} newly), {5} edited "
                  "and left alone{6}".format(
                      cc, got["new"], got["refreshed"], got["ready"], got["now_ready"], got["edited"],
                      "; {0} more new subject(s) wait for next week".format(got["waiting"])
                      if got["waiting"] else ""))
        except Exception as exc:              # one country's failure is a gap, not a lost run
            print("  [gap] country-briefs {0}: {1}: {2}".format(cc, type(exc).__name__, exc))
            rc = 1
        finally:
            conn.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
