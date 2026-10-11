#!/usr/bin/env python3
"""Post the new countries' 5CA to Chris alone, and keep the canvases current
(src/country5ca_post.py; the new-country tools/post_5ca.py and
tools/republish_canvas.py).

    python3 tools/country_5ca_post.py --cc pl --dry-run                  # print what would be posted
    python3 tools/country_5ca_post.py --cc pl                            # canvases, Chris alone
    python3 tools/country_5ca_post.py --cc pl --area 1 --to both         # one area: canvas and a DM
    python3 tools/country_5ca_post.py --cc pl --area 1 --chamber sejm --to dm
    python3 tools/country_5ca_post.py --all-countries --refresh          # the weekly step
    python3 tools/country_5ca_post.py --cc pl --db-map stores.txt        # "cc path" per line

Renders each chamber and area that src/country5ca.publishable_sheets lets
through (CONFIRMED readings only; DERIVED rows labelled; the non-attached
never placed from a group vote, #80). A canvas is shared with Chris's user
id alone (forced, whatever config/secrets.yaml says) and never a channel; a
rerun rewrites the same canvas in place (ids in
data/5ca/country-post-state.json). --refresh rewrites only canvases whose
confirmed readings changed. Nothing confirmed or nothing changed: no Slack
call, no message. One DM per run lists the canvases touched (--no-dm: none).

Countries: {countries}.
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country5ca as c5  # noqa: E402
from src import country5ca_post as cp  # noqa: E402

__doc__ = __doc__.format(countries=", ".join(c5.COUNTRIES))


def main(argv=None, transport=None, secrets=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cc", action="append", default=[], help="country code (repeatable)")
    ap.add_argument("--all-countries", action="store_true")
    ap.add_argument("--area", type=int, help="one issue area only")
    ap.add_argument("--chamber", help="one chamber only (as the stance file names it)")
    ap.add_argument("--to", choices=cp.TARGETS, default="canvas",
                    help="a canvas for Chris alone (default), a DM to him, or both")
    ap.add_argument("--refresh", action="store_true",
                    help="only what changed since the last post (the weekly step)")
    ap.add_argument("--dry-run", action="store_true", help="print what would be posted; send nothing")
    ap.add_argument("--no-dm", action="store_true", help="no summary DM listing the canvases")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--db-map", help="file of 'cc path' lines: a store per country")
    ap.add_argument("--config-dir", default=None)
    ap.add_argument("--state", default=cp.STATE_PATH)
    ap.add_argument("--today", help="ISO date (default today)")
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
    bad = [cc for cc in ccs if cc not in c5.SPECS]
    if bad:
        ap.error("unknown country: {0} (have {1})".format(", ".join(bad), ", ".join(c5.COUNTRIES)))
    if not ccs:
        ap.error("--cc CC or --all-countries")
    _done, gaps = cp.run(ccs, stores, args.db, args.config_dir, args.state, args.to,
                         args.refresh, args.dry_run, args.area, args.chamber, args.today,
                         secrets=secrets, transport=transport, announce=not args.no_dm)
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
