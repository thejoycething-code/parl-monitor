#!/usr/bin/env python3
"""Print the logo filename each sitting party's mark expects.

The party mark in the MP header is a circular slot (Christopher, 2026-08-27:
"make it so we can drop in party logos"). This lists exactly what to name a
file so it lands in the right circle, biggest party first, so the ones worth
sourcing are obvious.

Deliberately does NOT fetch anything: party logos are registered trademarks
and choosing to publish them is CitizenGO's call, not mine.
"""

from __future__ import annotations

import os
import sys
import unicodedata
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db


def slug(party):
    """Must match partySlug() in templates/vote-tracker.html."""
    text = unicodedata.normalize("NFD", party or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("&", "and")
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", text))


def main():
    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    conn.row_factory = db.sqlite3.Row if hasattr(db, "sqlite3") else None
    rows = conn.execute(
        "SELECT party, COUNT(*) n FROM members WHERE current_mp = 1 "
        "GROUP BY party ORDER BY n DESC").fetchall()
    print("{0:<34} {1:>5}  {2}".format("PARTY", "MPs", "FILENAME"))
    have = missing = 0
    for row in rows:
        party, n = row[0], row[1]
        name = slug(party) + ".svg"
        present = os.path.exists(os.path.join(ROOT, "partner_site", "logos", name))
        have += n if present else 0
        missing += 0 if present else n
        print("{0:<34} {1:>5}  {2} {3}".format(
            party or "(none)", n, name, "[present]" if present else ""))
    print("\nMPs whose header would show a logo:  {0}".format(have))
    print("MPs falling back to colour+initials: {0}".format(missing))
    print("\nDrop files in BOTH partner_site/logos/ and docs/logos/.")
    print("See partner_site/logos/README.md -- and note they are trademarks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
