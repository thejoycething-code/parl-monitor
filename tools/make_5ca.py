"""Generate a pre-filled 5CA Plan sheet for one issue area.

    python3 tools/make_5ca.py <area-number> [out.csv] [--active-only]

Emits the Campaigns Brief Five Column Analysis columns (Decision-Maker,
++/+/0/-/--, Target Y/N, Comments) as CSV for direct paste-in. Default is
the FULL COMMONS ROSTER (Christopher, 2026-08-04): one row per sitting MP
(~650, the body a Commons-division 5CA actually targets), suggested column
from the strongest stance evidence, "No recorded activity" at 0 otherwise;
peers are excluded (they do not vote in the Commons). --active-only keeps
the old view: only members of either House with ledger evidence. Target is
left blank -- that is the campaigner's call, never the tool's.

Run tools/pull_commons_roster.py first (and after by-elections).

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
    active_only = "--active-only" in sys.argv
    args = [a for a in sys.argv[2:] if not a.startswith("--")]
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    label = names.get(area, "area {0}".format(area))

    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    if not active_only and not conn.execute(
            "SELECT COUNT(*) FROM members WHERE current_mp = 1").fetchone()[0]:
        print("no Commons roster in the members cache - "
              "run: python3 tools/pull_commons_roster.py")
        sys.exit(1)
    cfg = stance.load_overrides(os.path.join(ROOT, "config", "stance_overrides.yaml"))
    rows = stance.suggest_rows(conn, area, full_roster=not active_only,
                               overrides_cfg=cfg)
    conn.close()
    if not rows:
        print("no ledger activity for {0}".format(label))
        sys.exit(1)

    out = args[0] if args else os.path.join(
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
    active = sum(1 for r in rows if r["n_events"])
    print("5CA ({0}): {1} decision-makers ({2} with ledger evidence) -> {3}".format(
        label, len(rows), active, out))
    print("  " + "  ".join("{0} x{1}".format(c, dist[c]) for c in stance.COLUMNS if c in dist)
          + ("  ({0} conflicting - flagged in Comments)".format(conflicts) if conflicts else ""))


if __name__ == "__main__":
    main()
