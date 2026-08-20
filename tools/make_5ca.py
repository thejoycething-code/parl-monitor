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
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel, stance


def main():
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    cfg = stance.load_overrides(os.path.join(ROOT, "config", "stance_overrides.yaml"))
    excluded = cfg.get("excluded_from_5ca") or []
    if len(sys.argv) < 2 or not sys.argv[1].isdigit():
        print("usage: python3 tools/make_5ca.py <area-number> [out.csv]\nareas:")
        for n, label in sorted(names.items()):
            print("  {0:>2}  {1}{2}".format(
                n, label, "   (collated only, not a 5CA area)" if n in excluded else ""))
        sys.exit(1)
    area = int(sys.argv[1])
    active_only = "--active-only" in sys.argv
    peers = "--peers" in sys.argv
    house = "Lords" if peers else "Commons"
    args = [a for a in sys.argv[2:] if not a.startswith("--")]
    label = names.get(area, "area {0}".format(area))
    if area in excluded:
        print("{0} is collated for MP intelligence but excluded from 5CA "
              "(config/stance_overrides.yaml: excluded_from_5ca).".format(label))
        sys.exit(1)

    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    flag = "current_peer" if peers else "current_mp"
    if not active_only and not conn.execute(
            "SELECT COUNT(*) FROM members WHERE {0} = 1".format(flag)).fetchone()[0]:
        print("no {0} roster in the members cache - "
              "run: python3 tools/pull_commons_roster.py".format(house))
        sys.exit(1)
    rows = stance.suggest_rows(conn, area, full_roster=not active_only,
                               overrides_cfg=cfg, house=house)
    conn.close()
    if not rows:
        print("no ledger activity for {0}".format(label))
        sys.exit(1)

    out = args[0] if args else os.path.join(
        ROOT, "data", "5ca",
        # Slugify rather than just swapping spaces: an area label may carry
        # punctuation ("Free speech, privacy and civil liberties") and a comma
        # has no business in a filename. Labels without punctuation slug to
        # exactly what they did before, so existing sheet names do not move.
        "5ca-{0}{1}-{2}.csv".format(
            re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-"),
            "-peers" if peers else "",
            datetime.date.today().isoformat()))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        # Total = how much evidence sits behind the placement. Comments keep the
        # dated evidence lines: the sheet is the record even though the web
        # table does not show them (Christopher, 2026-08-06).
        writer.writerow(["Decision-Maker"] + list(stance.COLUMNS)
                        + ["Target (Y/N)", "Based on", "Confidence",
                           "Evidence items", "Profile", "Comments"])
        tally = {c: 0 for c in stance.COLUMNS}
        for r in rows:
            marks = ["1" if c == r["column"] else "" for c in stance.COLUMNS]
            tally[r["column"]] += 1
            confidence = ("{0} ({1})".format(r["confidence"], r["confidence_why"])
                          if r["confidence"] else "")
            writer.writerow([r["decision_maker"]] + marks
                            + ["", stance.based_on(r["decided_kind"], r["decided_date"]),
                               confidence, r["n_events"],
                               "mp-votes.html#mp-{0}".format(r["member_id"]),
                               r["comments"]])
        # Totals as a row, as the Brief does for a party (Christopher, 2026-08-07).
        writer.writerow(["Totals - {0} decision-makers".format(len(rows))]
                        + [tally[c] for c in stance.COLUMNS] + ["", "", "", "", "", ""])

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
