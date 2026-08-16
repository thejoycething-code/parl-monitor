"""State-by-state UPR tracker from the store.

    python3 tools/make_upr_tracker.py             # both cuts, markdown
    python3 tools/make_upr_tracker.py --area 1    # one issue area
    python3 tools/make_upr_tracker.py --csv       # csv for a spreadsheet

Two cuts, because they answer different questions:

  UNDER REVIEW  -- what a state was asked to do and whether it agreed. This
                   is the defensive read: who is under pressure, and who is
                   holding.
  RECOMMENDING  -- which states do the asking. This is the one a national
                   team acts on: it names the governments actively pushing a
                   position at the UN, including our own.

"Noted" counts as refused throughout (src/ingest/upr.py REFUSED). A state's
refusal rate is the headline number: a government that notes every
recommendation on an issue is telling you its settled position.

Reads only the store, so it never touches the network.
"""

from __future__ import annotations

import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel

OUT_MD = os.path.join(ROOT, "docs", "upr-tracker.md")
OUT_CSV = os.path.join(ROOT, "docs", "upr-tracker.csv")


def rows_for(conn, area=None):
    sql = "SELECT * FROM upr_recommendations"
    rows = [dict(r) for r in conn.execute(sql)]
    if area is not None:
        rows = [r for r in rows
                if area in json.loads(r.get("issue_areas") or "[]")]
    return rows


def tally(rows, key):
    """{state: {supported, refused, total, rate}} for one grouping column."""
    out = {}
    for row in rows:
        state = row.get(key)
        if not state:
            continue
        entry = out.setdefault(state, {"supported": 0, "refused": 0})
        entry["refused" if row.get("refused") else "supported"] += 1
    for entry in out.values():
        entry["total"] = entry["supported"] + entry["refused"]
        entry["rate"] = (entry["refused"] / entry["total"]) if entry["total"] else 0.0
    return out


def table(counts, heading, min_total=1):
    """Markdown table, most active first, refusal rate as the sort tiebreak."""
    lines = ["", "### " + heading, "",
             "| State | Recommendations | Supported | Refused | Refusal rate |",
             "|---|---:|---:|---:|---:|"]
    ordered = sorted(((s, c) for s, c in counts.items() if c["total"] >= min_total),
                     key=lambda kv: (-kv[1]["total"], -kv[1]["rate"]))
    for state, c in ordered:
        lines.append("| {0} | {1} | {2} | {3} | {4:.0%} |".format(
            state, c["total"], c["supported"], c["refused"], c["rate"]))
    if not ordered:
        lines.append("| _no recommendations stored_ | | | | |")
    return lines


def main():
    area = None
    if "--area" in sys.argv:
        area = int(sys.argv[sys.argv.index("--area") + 1])
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    rows = rows_for(conn, area)
    if not rows:
        print("no UPR recommendations stored; run tools/pull_upr.py first")
        return 1

    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    scope = "area {0} ({1})".format(area, names.get(area, "?")) if area else "all areas"
    under = tally(rows, "state_under_review")
    doing = tally(rows, "recommending_state")

    out = ["# UPR tracker", "",
           "Universal Periodic Review recommendations touching our issues, "
           "{0}. Source: UPR Info. \"Noted\" is the diplomatic form of refusal "
           "and is counted as such.".format(scope), "",
           "{0} recommendations, {1} states reviewed, {2} states recommending."
           .format(len(rows), len(under), len(doing))]
    out += table(under, "By state under review — who was asked, and who agreed")
    out += table(doing, "By recommending state — who does the asking", min_total=2)

    # The refusals themselves: a tally is a starting point, but the sentence a
    # state refused is what a campaigner actually quotes.
    refused = [r for r in rows if r.get("refused")]
    out += ["", "### Refused recommendations", ""]
    for r in sorted(refused, key=lambda r: (r.get("state_under_review") or ""))[:60]:
        out.append("- **{0}** declined {1}'s recommendation ({2}): \"{3}\" [source]({4})".format(
            r.get("state_under_review"), r.get("recommending_state"),
            r.get("response"), (r.get("text") or "").strip()[:200], r.get("url")))
    if len(refused) > 60:
        out.append("")
        out.append("_...and {0} more._".format(len(refused) - 60))

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print("upr tracker: {0} recommendations, {1} reviewed / {2} recommending states"
          .format(len(rows), len(under), len(doing)))
    print("  -> " + OUT_MD)

    if "--csv" in sys.argv:
        with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["cut", "state", "recommendations", "supported", "refused", "refusal_rate"])
            for cut, counts in (("under review", under), ("recommending", doing)):
                for state, c in sorted(counts.items(), key=lambda kv: -kv[1]["total"]):
                    w.writerow([cut, state, c["total"], c["supported"], c["refused"],
                                "{0:.2f}".format(c["rate"])])
        print("  -> " + OUT_CSV)
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
