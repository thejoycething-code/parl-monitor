"""Generate a pre-filled 5CA Plan sheet for one issue area.

    python3 tools/make_5ca.py <area-number> [out.csv]

Emits the Campaigns Brief Five Column Analysis columns (Decision-Maker,
++/+/0/-/--, Target Y/N, Comments) as CSV for direct paste-in: one row per
parliamentarian active on the area, suggested column from the strongest
stance evidence, dated evidence lines as the Comments rationale. Target is
left blank -- that is the campaigner's call, never the tool's.

Placements are SUGGESTIONS from ledger evidence (docs/5ca-notes.md evidence
hierarchy). Until September's votes and speeches land, most PQ-only members
sit at 0: neutral information-seeking is not a stance.
"""

from __future__ import annotations

import csv
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel, stance


def main():
    if len(sys.argv) < 2 or not sys.argv[1].isdigit():
        names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
        print("usage: python3 tools/make_5ca.py <area-number> [out.csv]\nareas:")
        for n, label in sorted(names.items()):
            print("  {0:>2}  {1}".format(n, label))
        sys.exit(1)
    area = int(sys.argv[1])
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    label = names.get(area, "area {0}".format(area))

    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    rows = stance.suggest_rows(conn, area)
    conn.close()
    if not rows:
        print("no ledger activity for {0}".format(label))
        sys.exit(1)

    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        ROOT, "data", "5ca",
        "5ca-{0}-{1}.csv".format(label.lower().replace(" ", "-"),
                                 datetime.date.today().isoformat()))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Decision-Maker"] + list(stance.COLUMNS) + ["Target (Y/N)", "Comments"])
        for r in rows:
            marks = ["1" if c == r["column"] else "" for c in stance.COLUMNS]
            writer.writerow([r["decision_maker"]] + marks + ["", r["comments"]])

    dist = {}
    for r in rows:
        dist[r["column"]] = dist.get(r["column"], 0) + 1
    conflicts = sum(1 for r in rows if r["conflict"])
    print("5CA ({0}): {1} decision-makers -> {2}".format(label, len(rows), out))
    print("  " + "  ".join("{0} x{1}".format(c, dist[c]) for c in stance.COLUMNS if c in dist)
          + ("  ({0} conflicting - flagged in Comments)".format(conflicts) if conflicts else ""))


if __name__ == "__main__":
    main()
