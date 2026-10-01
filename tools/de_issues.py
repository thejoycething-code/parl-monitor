#!/usr/bin/env python3
"""Build the German issue pages: one per campaign area, plus an index.

    python3 tools/de_issues.py             # partner_site, as HTML (published)
    python3 tools/de_issues.py --docs      # the unpublished Markdown copy

A thin entry point over src/de_issuepages.py, which holds the reasoning.
Published since 2 October 2026 (Christopher: "publish the Germany issue
pages"): partner_site deploys to Vercel production with the next partner
deploy, behind the site's passphrase.

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
                    help="write into partner_site (the default since 2 Oct 2026)")
    ap.add_argument("--docs", action="store_true",
                    help="write the unpublished Markdown copy to docs/de-issues")
    args = ap.parse_args()

    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    out_dir = (de_issuepages.OUT_DIR if args.docs else
               de_issuepages.SITE_DIR if args.site else None)
    paths = de_issuepages.build(conn, intel.area_names(TAXONOMY),
                                datetime.date.today(), out_dir=out_dir)
    where = os.path.relpath(os.path.dirname(paths[-1]), ROOT)
    print("de-issues: {0} page(s) written to {1}{2}.".format(
        len(paths), where,
        " -- deploys with the next partner-site deploy"
        if where == "partner_site" else " (not deployed)"))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
