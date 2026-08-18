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
    roster = {r["person_id"]: (r["party"], r["constituency"]) for r in
              conn.execute("SELECT person_id, party, constituency FROM ni_members")}
    for r in visible[:limit]:
        print("  {0:<16} {1:<10} areas {2}".format(
            (r["reference"] or "?")[:16], r["dated"] or "undated",
            ",".join(str(a) for a in sorted(set(areas_of(r)) - hidden))))
        print("        {0}".format((r["title"] or "")[:68]))
        who = r["tabler"] or ""
        if who:
            party, seat = roster.get(r["tabler_person_id"] or "", ("", ""))
            # Party comes from the roster join, not the question: no question
            # payload carries one. Two consequences: a blank party means a
            # former member, and the party shown is the member's party NOW, not
            # when the question was asked. Doug Beattie asked as UUP leader and
            # reads "Independent" here, which is correct today and wrong for
            # the question. GetAllMembersByGivenDate would fix it per-date.
            print("        asked by {0}{1}{2}".format(
                who, " ({0})".format(party) if party else "",
                " — {0}".format(seat or r["tabler_seat"] or "") if
                (seat or r["tabler_seat"]) else ""))
        if r["minister"]:
            print("        of {0}".format(r["minister"][:60]))
        if r["answer"]:
            # Truncated on purpose: the CLAUDE.md rule against pasting full PQ
            # answers is about editions, but the reasoning holds here too.
            print("        ANSWER: {0}...".format(
                " ".join((r["answer"] or "").split())[:74]))
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

    # -- divisions ----------------------------------------------------------
    head("HOW MLAs VOTED", "tools/ni_divisions.py")
    dtotal = conn.execute("SELECT COUNT(*) FROM ni_divisions").fetchone()[0]
    if not dtotal:
        print("  no divisions stored. Run tools/ni_divisions.py --review.")
    else:
        watched = conn.execute(
            "SELECT COUNT(*) FROM ni_divisions WHERE watched = 1").fetchone()[0]
        auto = conn.execute("SELECT COUNT(*) FROM ni_divisions "
                            "WHERE areas IS NOT NULL AND areas != '[]'").fetchone()[0]
        print("  {0} division(s) stored; {1} on watched bills; {2} matched the "
              "taxonomy\n  on their own subject line.".format(dtotal, watched, auto))
        rows_v = conn.execute(
            "SELECT d.bill, d.doc_id, d.dated, d.kind, d.subject, "
            "  SUM(CASE WHEN v.vote='aye' THEN 1 ELSE 0 END) ayes, "
            "  SUM(CASE WHEN v.vote='no' THEN 1 ELSE 0 END) noes, "
            "  COUNT(v.person_id) n "
            "FROM ni_divisions d JOIN ni_votes v ON v.doc_id = d.doc_id "
            "GROUP BY d.doc_id ORDER BY d.dated DESC, d.doc_id").fetchall()
        if not rows_v:
            print("\n  No member votes harvested yet. A bill must be listed in")
            print("  config/ni_watch.yaml first -- a division's subject names an")
            print("  amendment number, not its content, so the choice of which")
            print("  bills matter is a human one. Start with:")
            print("      python3 tools/ni_divisions.py --review")
        for r in rows_v[:12]:
            flag = "  CROSS-COMMUNITY" if "cross" in (r["kind"] or "").lower() else ""
            print("\n  {0}  {1}{2}".format(r["dated"] or "undated",
                                           (r["bill"] or "?")[:44], flag))
            print("        {0}".format((r["subject"] or "")[:68]))
            print("        {0} aye / {1} no  of {2} voting".format(
                r["ayes"], r["noes"], r["n"]))
        if len(rows_v) > 12:
            print("\n  ...and {0} more with votes stored.".format(len(rows_v) - 12))
        # Party comes from the roster join: no division payload carries one.
        # Aggregated across watched divisions rather than per-division, because
        # 34 amendment votes on one bill is a pattern, not 34 findings.
        splits = conn.execute(
            "SELECT m.party, v.vote, COUNT(*) n FROM ni_votes v "
            "JOIN ni_members m ON m.person_id = v.person_id "
            "JOIN ni_divisions d ON d.doc_id = v.doc_id AND d.watched = 1 "
            "GROUP BY m.party, v.vote").fetchall()
        if splits:
            tally = {}
            for r in splits:
                tally.setdefault(r["party"], {})[r["vote"]] = r["n"]
            print("\n  ACROSS ALL WATCHED DIVISIONS, by party (aye/no):")
            for party, counts in sorted(tally.items(),
                                        key=lambda kv: -sum(kv[1].values())):
                total = sum(counts.values())
                print("     {0:<34} {1:>4} aye / {2:>4} no   ({3} positions)"
                      .format(party[:34], counts.get("aye", 0),
                              counts.get("no", 0), total))
            print("  A party voting both ways across a bill is normal: these are")
            print("  amendment votes, so aye and no both cut both ways. Read the")
            print("  individual division before drawing any conclusion.")
        elif rows_v:
            print("\n  No party split available: the MLA roster is empty. Run "
                  "tools/ni_pull.py.")
        # Designation only matters where a vote is cross-community, so it is
        # reported there rather than on every row.
        cc = conn.execute(
            "SELECT COUNT(*) FROM ni_divisions WHERE watched = 1 AND "
            "LOWER(kind) LIKE '%cross%'").fetchone()[0]
        if cc:
            print("\n  {0} watched division(s) are cross-community: they need a "
                  "majority in\n  BOTH designations, so a bare aye/no tally "
                  "misreads them.".format(cc))

    # -- honesty ------------------------------------------------------------
    head("WHAT THIS DOES NOT KNOW", "src/ingest/niassembly.py")
    print("  * DIVISIONS CANNOT BE AUTO-CLASSIFIED. A subject names an amendment")
    print("    number, not its content, and the API truncates it at 100 chars.")
    print("    0 of 139 matched in the year to 2026-08-18. Which bills matter is")
    print("    a human call, made in config/ni_watch.yaml.")
    print("  * MOTIONS CANNOT BE CLASSIFIED from title alone (see above). The")
    print("    Order Paper carries the full text; that is the route in.")
    print("  * The diary carries a committee name, no subject text, so an OURS")
    print("    mark there means the committee is ours -- not the agenda.")
    print("  * PARTY IS AS AT TODAY, not as at the question or vote. The roster")
    print("    is current-members-only, so a member who crossed the floor reads")
    print("    under their party now (Doug Beattie shows Independent for")
    print("    questions he asked as UUP leader). GetAllMembersByGivenDate")
    print("    would resolve party per-date; it is not wired in.")
    print("  * NO MLA SCORING. Attribution and votes are now stored, but there")
    print("    is no NI equivalent of the 5CA: RF4 placement is a human")
    print("    judgement and nothing here estimates a stance.")
    print("  * Nothing here is scheduled. Refreshed only by tools/ni_pull.py")
    print("    and tools/ni_divisions.py.")
    print("\n  {0} row(s) stored in ni_items. Not in `items`, so structurally "
          "cannot\n  reach the Slack digest.".format(total))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
