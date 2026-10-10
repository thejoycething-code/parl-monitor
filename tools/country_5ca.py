#!/usr/bin/env python3
"""5CA with stance sign-off for the new country editions (src/country5ca.py).

    python3 tools/country_5ca.py --all-countries --draft --signoff-doc --sheets   # the weekly step
    python3 tools/country_5ca.py --cc pl --draft             # append drafts for new votes
    python3 tools/country_5ca.py --cc pl --signoff-doc       # rewrite docs/5ca-pl-readings.md
    python3 tools/country_5ca.py --cc pl --sign-from-doc --by Christopher
    python3 tools/country_5ca.py --cc pl --confirm pl-10-58-62 --by Christopher [--on 2026-10-10]
    python3 tools/country_5ca.py --cc pl --sheets            # data/5ca/pl-5ca-*.csv (confirmed only)
    python3 tools/country_5ca.py --cc pl --confirm-direction 10/2110 --by Christopher
    python3 tools/country_5ca.py --all-countries --counts
    python3 tools/country_5ca.py --cc fr --prune-out-of-scope [--dry-run]
    python3 tools/country_5ca.py --cc pl --draft --db /path/to/store.db
    python3 tools/country_5ca.py --draft --db-map stores.txt # "cc path" per line (initial drafts)

Reads the store only, read-only; fetches nothing, posts nothing. Drafting is
by rules (no AI call). Nothing it does confirms a reading: only --confirm and
--sign-from-doc do, and both need a named person (--by), who must be Chris or
listed for that country in config/stance_signers.yaml. --confirm-direction
signs a bill's direction (`bill_directions`) the same way; the campaign briefs
(tools/country_briefs.py) take their ask from it only once it is confirmed.

--prune-out-of-scope removes the entries outside a country's sign-off scope
(France: final votes, motions to reject and watched amendments only) that
are unsigned and untouched; a confirmed or hand-edited entry is always kept
and reported. It reads the stance file and the watchlist, not the store.

Countries: {countries}.
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country5ca as c5  # noqa: E402

__doc__ = __doc__.format(countries=", ".join(c5.COUNTRIES))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cc", action="append", default=[], help="country code (repeatable)")
    ap.add_argument("--all-countries", action="store_true")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--db-map", help="file of 'cc path' lines: a store per country")
    ap.add_argument("--draft", action="store_true", help="append drafts for new qualifying votes")
    ap.add_argument("--signoff-doc", action="store_true", help="rewrite docs/5ca-<cc>-readings.md")
    ap.add_argument("--sheets", action="store_true", help="write the 5CA sheets (confirmed only)")
    ap.add_argument("--counts", action="store_true")
    ap.add_argument("--prune-out-of-scope", action="store_true",
                    help="remove unsigned, untouched entries outside the sign-off scope")
    ap.add_argument("--dry-run", action="store_true", help="with --prune-out-of-scope: write nothing")
    ap.add_argument("--confirm", nargs="+", metavar="KEY")
    ap.add_argument("--confirm-direction", nargs="+", metavar="BILL",
                    help="confirm bill_directions entries (the campaign briefs' ask follows them)")
    ap.add_argument("--sign-from-doc", action="store_true")
    ap.add_argument("--by", help="the named person confirming")
    ap.add_argument("--on", help="the date of the confirmation (default today)")
    ap.add_argument("--today", help="ISO date stamped on drafts (default today)")
    ap.add_argument("--out-dir", default=c5.OUT_DIR)
    args = ap.parse_args(argv)

    ccs = list(c5.COUNTRIES) if args.all_countries else []
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
            ccs = [cc for cc in c5.COUNTRIES if cc in stores]
    bad = [cc for cc in ccs if cc not in c5.SPECS]
    if bad:
        ap.error("unknown country: {0} (have {1})".format(", ".join(bad), ", ".join(c5.COUNTRIES)))
    if not ccs:
        ap.error("--cc CC, --all-countries or --db-map")
    if (args.confirm or args.sign_from_doc or args.confirm_direction) and len(ccs) != 1:
        ap.error("confirm one country at a time")
    if args.confirm_direction:
        c5.confirm_direction(ccs[0], args.confirm_direction, args.by, args.on)
        return 0
    if args.confirm:
        c5.confirm(ccs[0], args.confirm, args.by, args.on)
        return 0
    if args.sign_from_doc:
        c5.sign_from_doc(ccs[0], args.by, args.on)
        return 0
    if not (args.draft or args.signoff_doc or args.sheets or args.counts
            or args.prune_out_of_scope):
        ap.error("say what to do: --draft, --signoff-doc, --sheets, --counts, --confirm, "
                 "--sign-from-doc or --prune-out-of-scope")
    if args.prune_out_of_scope:
        for cc in ccs:
            if os.path.exists(c5.stance_path(cc)):
                c5.prune_out_of_scope(cc, dry_run=args.dry_run)

    rc = 0
    for cc in ccs:
        path = stores.get(cc, args.db)
        need_store = args.draft or args.sheets
        if not (need_store or args.signoff_doc):
            continue
        conn = None
        if need_store:
            if not os.path.exists(path):
                print("{0}: no store at {1}; skipped".format(cc, path))
                continue
            conn = c5.connect_ro(path)
        try:
            if args.draft:
                c5.draft(conn, cc, today=args.today)
            if args.signoff_doc:
                c5.write_signoff_doc(cc)
            if args.sheets:
                c5.run_sheets(conn, cc, out_dir=args.out_dir, today=args.today)
        except Exception as exc:          # one country's failure is a gap, not a lost run
            print("  [gap] {0}: {1}: {2}".format(cc, type(exc).__name__, exc))
            rc = 1
        finally:
            if conn is not None:
                conn.close()
    if args.counts or args.draft or args.prune_out_of_scope:
        print("\nconfig/<cc>_stance.yaml, by country (proposed / procedural / need reading / "
              "confirmed):")
        for cc in ccs:
            if os.path.exists(c5.stance_path(cc)):
                c = c5.counts(cc)
                print("  {0}  {1:>5} {2:>5} {3:>5} {4:>5}   {5}".format(
                    cc, c["proposed"], c["procedural"], c["needs_reading"], c["confirmed"],
                    c5.SPECS[cc].name))
    return rc


if __name__ == "__main__":
    sys.exit(main())
