#!/usr/bin/env python3
"""Put the new countries' campaign briefs and debate packs on Google Drive
(src/country_drive.py).

    python3 tools/country_drive.py                 # publish what is new or changed
    python3 tools/country_drive.py --dry-run       # say what it would do; write nothing
    python3 tools/country_drive.py --dry-run --offline   # the same without asking Drive
        [--country pl] [--ready-only] [--max-new 30]

Briefs become Sheets copied from the UK brief template, in
"Country editions/<Country>/Campaign briefs" in the Automated Briefs shared
drive; packs go to "Country editions/<Country>/Debate packs/<date> <title>".
data/country-drive.json records what is there, so a rerun publishes only
what is new or changed. A step of the Sunday editions-session-judge job on
the Mac Mini. Without a service account key it says so and exits 0: a Drive
credential never fails the job.
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import country_drive as cd  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline", action="store_true", help="with --dry-run: do not ask Drive what exists")
    ap.add_argument("--country", action="append", help="only this country (repeatable)")
    ap.add_argument("--ready-only", action="store_true", help="leave out briefs still NOT READY")
    ap.add_argument("--max-new", type=int, default=cd.MAX_NEW)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    args = ap.parse_args(argv)

    import publish_briefs_to_drive as pbd
    drive = None
    if not (args.dry_run and args.offline):
        token, why = pbd.load_credentials()
        if not token:
            print("country-drive skipped: {0}".format(why))
            return 0
        drive = cd.Drive(token, pbd.api, pbd.FOLDER_ID, dry=args.dry_run)
    ccs = args.country or cd.countries()
    briefs, packs = cd.local_briefs(ccs), cd.local_packs(ccs)
    ledger = cd.load_ledger()
    n = cd.run(drive, briefs, packs, ledger, rejected=cd.rejected_slugs(args.db),
               max_new=args.max_new, publish_one=pbd.publish_one, ready_only=args.ready_only)
    if not args.dry_run:
        cd.save_ledger(ledger)
    print(cd.summary(n, args.dry_run))
    return 1 if n["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
