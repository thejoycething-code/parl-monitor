#!/usr/bin/env python3
"""Build the German issue pages: one per campaign area, plus an index.

    python3 tools/de_issues.py
    python3 tools/de_issues.py --site      # write to partner_site instead

A thin entry point over src/de_issuepages.py, which holds the reasoning --
including why these are written to docs/de-issues/ and not to the deployed
site while the taxonomy is unverified.

--site is deliberately a FLAG AND NOT A DEFAULT, and it overrides
de_issuepages.PUBLISH_TO_SITE for one run. partner_site deploys to Vercel
production on the Monday publish; nothing should land there by accident.

ONE WRITER AT A TIME is not needed here: this reads the store and writes
markdown, and takes no lock.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, de_issuepages, intel  # noqa: E402

TAXONOMY = os.path.join(ROOT, "config", "taxonomy-de.yaml")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", action="store_true",
                    help="write into partner_site, which DEPLOYS to "
                         "production -- only once the taxonomy is verified")
    args = ap.parse_args()

    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    out_dir = de_issuepages.SITE_DIR if args.site else None
    paths = de_issuepages.build(conn, intel.area_names(TAXONOMY),
                                datetime.date.today(), out_dir=out_dir)
    where = os.path.relpath(os.path.dirname(paths[-1]), ROOT)
    print("de-issues: {0} page(s) written to {1}{2}.".format(
        len(paths), where,
        " -- THIS DEPLOYS TO PRODUCTION" if args.site else
        " (not deployed; the taxonomy is unverified)"))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
