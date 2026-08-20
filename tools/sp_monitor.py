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
    print("WHAT THIS DOES NOT KNOW    [src/ingest/holyrood.py]"); print(line)
    print("  * NO VOTES YET: votesmotion?year= is probed and shaped (per-MSP")
    print("    per-motion, 19,473 rows in 2026) but not ingested -- phase 2.")
    print("  * NO OFFICIAL REPORT: orsplenarymeeting?year= (65MB/year) is the")
    print("    Hansard equivalent, for offline classification -- phase 3.")
    print("  * PARTY IS THE ROW'S OWN: the API stamps the asker's party on")
    print("    every question, and sp_affiliations holds full date ranges,")
    print("    so party-as-at-date needs no reconstruction (unlike NI).")
    print("  * ANSWERS are kept only for matched rows; classification runs on")
    print("    the question text, so a taxonomy change still re-tests all.")
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
