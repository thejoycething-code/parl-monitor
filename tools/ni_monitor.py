"""The Northern Ireland Assembly at a glance, from the store. No network.

    python3 tools/ni_monitor.py            # everything
    python3 tools/ni_monitor.py --area 1   # one issue area
    python3 tools/ni_monitor.py --n 20     # show more questions

A SEPARATE report by design (Christopher, 2026-08-18). NI is a watching brief,
not digest material, so it is read here and never written into `items` -- the
table the Slack edition is built from. Nothing in this file can put a row on
Slack, and nothing in the Sunday pull touches ni_items.

Why NI is worth watching at all: abortion law was imposed on the Assembly from
Westminster in 2019 and it has never accepted that settlement. Arguments
Westminster treats as closed are live here, which makes NI an early indicator
rather than a footnote.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel

BAR = "-" * 78


def head(title, refreshed_by):
    print("\n" + BAR)
    print("{0}    [{1}]".format(title, refreshed_by))
    print(BAR)


def areas_of(row):
    return json.loads(row["areas"] or "[]")


def hidden_areas():
    """Areas we track but never display (migration). Same source of truth as
    tools/find_division_candidates.py, so the two cannot drift apart."""
    import yaml
    with open(os.path.join(ROOT, "config", "vote_tracker.yaml"),
              encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    return {int(a) for a in (cfg.get("hidden_areas") or [])}


def main():
    want = None
    if "--area" in sys.argv:
        want = int(sys.argv[sys.argv.index("--area") + 1])
    limit = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 10
    today = datetime.date.today()
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))

    scope = " — area {0} ({1})".format(want, names.get(want, "?")) if want else ""
    print("\nNORTHERN IRELAND ASSEMBLY{0}".format(scope))
    print("as at {0}    (watching brief — never published to Slack)".format(
        today.isoformat()))

    def rows(kind):
        out = [r for r in conn.execute(
            "SELECT * FROM ni_items WHERE kind = ? ORDER BY dated DESC", (kind,))]
        if want is not None:
            out = [r for r in out if want in areas_of(r)]
        return out

    total = conn.execute("SELECT COUNT(*) FROM ni_items").fetchone()[0]
    if not total:
        print("\n  nothing stored. Run tools/ni_pull.py first.")
        conn.close()
        return 0

    # -- questions ----------------------------------------------------------
    # Migration is tracked but never displayed. Hidden-only rows are pushed
    # BELOW the rest and marked rather than dropped: without this, area 11
    # filled seven of the top ten and buried everything else.
    hidden = hidden_areas()
    head("WHAT IS BEING ASKED", "tools/ni_pull.py")
    qs = rows("question")
    visible = [r for r in qs if set(areas_of(r)) - hidden]
    hidden_only = [r for r in qs if not set(areas_of(r)) - hidden]
    if not qs:
        print("  no classified questions stored.")
    for r in visible[:limit]:
        print("  {0:<16} {1:<10} areas {2}".format(
            (r["reference"] or "?")[:16], r["dated"] or "undated",
            ",".join(str(a) for a in sorted(set(areas_of(r)) - hidden))))
        print("        {0}".format((r["title"] or "")[:68]))
    if len(visible) > limit:
        print("\n  ...and {0} more. --n {1} to show them."
              .format(len(visible) - limit, len(visible)))
    if hidden_only:
        print("\n  {0} further question(s) match HIDDEN areas only ({1}) -- "
              "tracked,\n  never displayed. Counted here so the silence is "
              "visible.".format(
                  len(hidden_only), ",".join(str(a) for a in sorted(hidden))))

    # -- motions ------------------------------------------------------------
    head("WHAT IS BEING MOVED", "tools/ni_pull.py")
    print("  Motions tabled but not yet scheduled -- the nearest thing NI has")
    print("  to an EDM. Unlike a Westminster EDM these name their tablers.\n")
    ms = rows("motion")
    if not ms:
        print("  no motions matched. This is a MEASURED zero, not a quiet feed:")
        print("  33 current motions parse correctly and none match the taxonomy.")
        print("  Titles run three to six words -- \"Women's Health\", \"Modernising")
        print("  Divorce Laws\" -- which is too little text to classify on, and the")
        print("  endpoint gives no motion body. Loosening the taxonomy to catch")
        print("  them would misfire everywhere else; the fix is the motion text.")
    for r in ms:
        parties = json.loads(r["parties"] or "[]")
        print("  {0:<10} {1:<28} areas {2}".format(
            r["dated"] or "undated", (r["title"] or "")[:28],
            ",".join(str(a) for a in areas_of(r))))
        print("        {0}   {1}".format(
            (r["category"] or "")[:34], "/".join(parties) or "unattributed"))

    # -- forward diary ------------------------------------------------------
    head("WHAT IS COMING", "tools/ni_pull.py")
    diary = [r for r in conn.execute(
        "SELECT * FROM ni_items WHERE kind = 'diary' AND dated >= ? "
        "ORDER BY dated", (today.isoformat(),))]
    if not diary:
        print("  nothing stored ahead of today. Run tools/ni_pull.py.")
    for r in diary[:12]:
        left = (datetime.date.fromisoformat(r["dated"]) - today).days
        mark = "OURS" if areas_of(r) else "    "
        print("  {0} {1:>4}d  {2:<18} {3}".format(
            mark, left, (r["category"] or "")[:18], (r["title"] or "")[:38]))
    if len(diary) > 12:
        print("  ...and {0} more within the stored horizon".format(len(diary) - 12))

    # -- honesty ------------------------------------------------------------
    head("WHAT THIS DOES NOT KNOW", "src/ingest/niassembly.py")
    print("  * NO MLA ATTRIBUTION on questions. The search endpoint returns no")
    print("    member name, so naming one costs a fetch per question. The 5CA")
    print("    scores Westminster members; a partial MLA ledger would be worse")
    print("    than none.")
    print("  * NO DIVISIONS. GetDivisionMemberVoting_JSON exists and is the")
    print("    high-value evidence (a vote outranks a question 5:1 in the 5CA),")
    print("    but it is not built yet. This is the obvious next step.")
    print("  * The diary carries a committee name, no subject text, so an OURS")
    print("    mark there means the committee is ours -- not the agenda.")
    print("  * MOTIONS CANNOT BE CLASSIFIED from title alone (see above). The")
    print("    Order Paper carries the full text; that is the route in.")
    print("  * Nothing here is scheduled. Refreshed only by tools/ni_pull.py.")
    print("\n  {0} row(s) stored in ni_items. Not in `items`, so structurally "
          "cannot\n  reach the Slack digest.".format(total))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
