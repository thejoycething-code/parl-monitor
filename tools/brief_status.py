"""Set a brief's status by hand -- the replacement for the Asana verdict loop.

    python3 tools/brief_status.py SLUG rejected|approved|pending
    python3 tools/brief_status.py --list

The editorial loop is retired (Christopher, 2026-08-21): briefs generate and
upload automatically, and HE decides what happens to them. 'rejected' remains
load-bearing in two places -- make_briefs refuses to regenerate a rejected
slug, and the Drive publisher never uploads one -- so rejection stays a
deliberate, recorded act rather than an Asana verdict.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db

VALID = ("rejected", "approved", "pending", "generated")


def main():
    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    if "--list" in sys.argv or len(sys.argv) < 3:
        for r in conn.execute("SELECT slug, status, generated_at FROM "
                              "brief_log ORDER BY generated_at"):
            print("  {0:<10} {1}  {2}".format(r["status"], r["generated_at"],
                                              r["slug"]))
        return 0
    slug, status = sys.argv[1], sys.argv[2]
    if status not in VALID:
        print("status must be one of {0}".format(", ".join(VALID)))
        return 1
    row = conn.execute("SELECT status FROM brief_log WHERE slug = ?",
                       (slug,)).fetchone()
    if not row:
        print("no brief_log row for {0!r}".format(slug))
        return 1
    conn.execute("UPDATE brief_log SET status = ? WHERE slug = ?",
                 (status, slug))
    conn.commit()
    print("{0}: {1} -> {2}".format(slug, row["status"], status))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
