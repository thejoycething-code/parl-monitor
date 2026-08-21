"""Holyrood watching brief -- read-only view over the sp_* tables.

    python3 tools/sp_monitor.py           # the overview
    python3 tools/sp_monitor.py --n 40    # more rows per section

NEVER published: this reads sp_items/sp_members and prints to the terminal.
Mirrors tools/ni_monitor.py, one legislature over.
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel

HIDDEN = {11}   # tracked, never displayed -- same rule as everywhere else


def rows(conn, kind):
    out = []
    for r in conn.execute(
            "SELECT * FROM sp_items WHERE kind=? ORDER BY dated DESC", (kind,)):
        areas = [a for a in json.loads(r["areas"] or "[]")]
        out.append((r, areas))
    return out


def shown(areas):
    return [a for a in areas if a not in HIDDEN]


def main():
    n = 10
    if "--n" in sys.argv:
        n = int(sys.argv[sys.argv.index("--n") + 1])
    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    line = "-" * 78

    print("SCOTTISH PARLIAMENT (HOLYROOD)")
    print("as at today    (watching brief -- never published to Slack)\n")

    print(line); print("WHAT IS BEING ASKED    [tools/sp_pull.py]"); print(line)
    qs = rows(conn, "question")
    ours = [(r, a) for r, a in qs if shown(a)]
    hidden_only = sum(1 for r, a in qs if a and not shown(a))
    for r, a in ours[:n]:
        print("  {0:<14} {1} areas {2}{3}".format(
            r["reference"] or "-", r["dated"], ",".join(map(str, shown(a))),
            "" if r["tier"] == 1 else "  (tier 2)"))
        print("        {0}".format((r["body"] or "")[:90]))
        print("        asked by MSP {0} ({1})".format(r["msp_id"], r["party"]))
        if r["answer"]:
            print("        ANSWER: {0}...".format(r["answer"][:80]))
    if len(ours) > n:
        print("\n  ...and {0} more. --n {1} to show them.".format(
            len(ours) - n, len(ours)))
    if hidden_only:
        print("\n  {0} further question(s) match HIDDEN areas only ({1}) -- "
              "tracked,\n  never displayed. Counted here so the silence is "
              "visible.".format(hidden_only, ",".join(map(str, sorted(HIDDEN)))))

    print(); print(line)
    print("WHAT IS BEING MOVED    [tools/sp_pull.py]"); print(line)
    ms = rows(conn, "motion")
    # Tier gate. Holyrood tables thousands of congratulatory motions a year,
    # and tier-2 vocabulary alone filed a dental-charity fundraiser under
    # assisted dying ("hospice") and a stoma-friendly airport under sex-based
    # rights ("changing room*"). Tier 1 is shown; tier-2-only is counted, held
    # and re-testable -- the same judgement Westminster buys with paid triage,
    # bought here with a column.
    m_ours = [(r, a) for r, a in ms if shown(a) and r["tier"] == 1]
    m_tier2 = sum(1 for r, a in ms if shown(a) and r["tier"] == 2)
    m_hidden = sum(1 for r, a in ms if a and not shown(a))
    for r, a in m_ours[:n]:
        terms = ", ".join(json.loads(r["matched_terms"] or "[]")[:4])
        print("  {0} {1:<50} areas {2}".format(
            r["dated"], (r["title"] or "")[:50],
            ",".join(map(str, shown(a)))))
        print("        by MSP {0} ({1}){2}".format(
            r["msp_id"], r["party"],
            "   CROSS-PARTY SUPPORT" if r["cross_party"] else ""))
        print("        on: {0}".format(terms))
        print("        \"{0}...\"".format((r["body"] or "")[:96]))
    print("\n  {0} tier-1 motion(s) shown of {1} stored{2}.".format(
        len(m_ours), len(ms),
        " (+{0} hidden-only)".format(m_hidden) if m_hidden else ""))
    print("  {0} more match on tier-2 vocabulary alone: HELD, not shown -- "
          "mostly\n  congratulatory motions caught by broad terms. All wording "
          "is stored, so\n  a taxonomy change re-tests everything offline "
          "(sp_pull.py --reclassify).".format(m_tier2))

    print(); print(line)
    print("PER AREA    (questions + motions, hidden areas excluded)"); print(line)
    per = {}
    for r, a in qs + ms:
        for x in shown(a):
            per[x] = per.get(x, 0) + 1
    for area in sorted(per):
        print("  {0:<2} {1:<42} {2}".format(area, names.get(area, "?"), per[area]))

    print(); print(line)
    print("HOW MSPs VOTED    [tools/sp_divisions.py]"); print(line)
    dv=conn.execute("SELECT * FROM sp_divisions WHERE source='votesmotion' "
                    "ORDER BY dated DESC").fetchall()
    ordv=conn.execute("SELECT COUNT(*), SUM(CASE WHEN areas != '[]' AND areas "
                      "IS NOT NULL THEN 1 ELSE 0 END) FROM sp_divisions "
                      "WHERE source='official-report'").fetchone()
    ours=[r for r in dv if r["areas"] and r["areas"] != "[]"
          and r["tier"] == 1
          and shown(json.loads(r["areas"]))]
    print("  {0} motion division(s) with every MSP's position; {1} tier-1 on"
          .format(len(dv), len(ours)))
    print("  our ground, classified by their own motion's wording -- an")
    print("  exact-key join, never text-matched against a truncated subject.")
    print("  PLUS {0} bill-amendment division(s) from the Official Report"
          .format(ordv[0] or 0))
    print("  ({0} on our ground by bill heading) -- AGGREGATE ONLY: the OR"
          .format(ordv[1] or 0))
    print("  prints no roll-call, so these are record and context, and can")
    print("  never place anyone in the 5CA.\n")
    # Meaning-line state per division, so a NOT PLACEABLE tally is never
    # shown bare -- S7M-00446 reads 91-27 and means nothing for us: the vote
    # was on a wholesale replacement text (see config/sp_stance.yaml).
    try:
        import sp_5ca
        stance_entries = sp_5ca.load_stance(section="divisions")
    except Exception:                               # noqa: BLE001
        stance_entries = {}
    def meaning(ref):
        e = stance_entries.get(ref)
        if not e:
            return "no meaning line yet: evidence only"
        if e.get("draft"):
            return "meaning line DRAFT: places nobody"
        if e.get("aye") is None and e.get("no") is None:
            return "NOT PLACEABLE (confirmed): see config/sp_stance.yaml"
        return "meaning line confirmed: places voters"
    for r in ours[:n]:
        a=shown(json.loads(r["areas"]))
        print("  OURS  {0}  {1:<12} areas {2}".format(
            r["dated"], r["reference"], ",".join(map(str, a))))
        print("        {0}".format((r["title"] or "")[:66]))
        print("        {0} aye / {1} no -- {2}   [{3}]".format(
            r["vote_for"], r["vote_against"], r["result"],
            meaning(r["reference"])))
    if len(ours) > n:
        print("  ...and {0} more.".format(len(ours) - n))
    # Party tallies over OUR tier-1 divisions, from the party stamped on each
    # vote row at the time of the vote.
    per={}
    keys=tuple(r["key"] for r in ours)
    if keys:
        q=("SELECT party, vote, COUNT(*) FROM sp_votes WHERE division_key IN "
           "({0}) GROUP BY party, vote".format(",".join("?"*len(keys))))
        for party, vote, count in conn.execute(q, keys):
            per.setdefault(party or "?", {})[vote]=count
        print("\n  ACROSS OUR TIER-1 DIVISIONS, by party AT THE VOTE "
              "(aye/no/abstain/absent):")
        for party, tally in sorted(per.items(),
                                   key=lambda x: -sum(x[1].values())):
            print("     {0:<42} {1:>4} / {2:>4} / {3:>3} / {4:>3}".format(
                party[:42], tally.get("Yes",0), tally.get("No",0),
                tally.get("Abstain",0), tally.get("Not Voted",0)))
        print("  Amendment votes cut both ways; read the division before")
        print("  concluding anything from a bare tally.")

    print(); print(line)
    print("WHAT THIS DOES NOT KNOW    [src/ingest/holyrood.py]"); print(line)
    print("  * VOTES: every MSP appears in every division ('Not Voted' and")
    print("    'Abstain' are first-class values), and the API stamps party AND")
    print("    a whip-agreement flag on each vote row. A division whose motion")
    print("    is not in sp_items is stored unclassified, never guessed.")
    ev=conn.execute("SELECT COUNT(*), COUNT(DISTINCT person_id) FROM "
                    "sp_events").fetchone()
    print("  * OFFICIAL REPORT: divisions AND speeches are harvested from one")
    print("    fetch per year. {0} speech event(s) from {1} MSP(s) sit in"
          .format(ev[0], ev[1]))
    print("    sp_events -- passage-matched, quotable, and ACTIVITY ONLY:")
    print("    a watching brief scores no stances, so a speech never places.")
    print("  * PARTY IS THE ROW'S OWN: the API stamps the asker's party on")
    print("    every question, and sp_affiliations holds full date ranges,")
    print("    so party-as-at-date needs no reconstruction (unlike NI).")
    print("  * ANSWERS are kept only for matched rows; classification runs on")
    print("    the question text, so a taxonomy change still re-tests all.")
    print("  * NO ESTIMATED STANCE. tools/sp_5ca.py builds a 5CA sheet, but an")
    print("    MSP is placed ONLY by a vote or proposal whose meaning a human")
    print("    confirmed in config/sp_stance.yaml.")
    try:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import sp_5ca
        entries = dict(sp_5ca.load_stance(section="divisions"))
        entries.update(sp_5ca.load_stance(section="motions"))
        drafts = sum(1 for e in entries.values() if e.get("draft"))
    except Exception:                               # noqa: BLE001
        entries, drafts = {}, 0
    if drafts:
        print("    {0} of {1} meaning line(s) are still DRAFT; a draft places"
              .format(drafts, len(entries)))
        print("    nobody until the flag is removed.")
    elif entries:
        print("    All {0} meaning line(s) are human-confirmed: the sheet"
              .format(len(entries)))
        print("    places MSPs.")
    else:
        print("    config/sp_stance.yaml holds no meaning lines yet.")
    print("  * CO-SIGNATORIES are not held: the supports endpoint answered 503")
    print("    on 2026-08-20. Proposer sponsorship works; retry the endpoint")
    print("    when adding motion meaning lines.")
    print("  * REFRESHED WEEKLY: Friday 06:00 UTC via")
    print("    .github/workflows/sp-weekly.yml (pull + divisions -- no publish")
    print("    step exists; the watching brief stays off Slack).")
    total = conn.execute("SELECT COUNT(*) FROM sp_items").fetchone()[0]
    kinds = dict(conn.execute(
        "SELECT kind, COUNT(*) FROM sp_items GROUP BY kind").fetchall())
    print("\n  {0} row(s) in sp_items ({1}). Not in `items`, so structurally"
          .format(total, ", ".join("{0} {1}".format(v, k)
                                   for k, v in sorted(kinds.items()))))
    print("  cannot reach the Slack digest.")
    conn.close()


if __name__ == "__main__":
    main()
