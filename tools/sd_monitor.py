"""Senedd watching brief -- read-only view over the sd_* tables.

    python3 tools/sd_monitor.py           # the overview
    python3 tools/sd_monitor.py --n 30    # more rows

NEVER published. Phase 1 holds written questions only; the phase map and the
honest limits are in the closing section.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel

HIDDEN = {11}


def main():
    n = 10
    if "--n" in sys.argv:
        n = int(sys.argv[sys.argv.index("--n") + 1])
    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    line = "-" * 78

    print("SENEDD (WELSH PARLIAMENT)")
    print("as at today    (watching brief -- never published to Slack)\n")
    print(line); print("WHAT IS BEING ASKED    [tools/sd_pull.py]"); print(line)
    rows = conn.execute("SELECT * FROM sd_items WHERE kind='question' "
                        "ORDER BY dated DESC").fetchall()
    ours = [r for r in rows if r["areas"] and
            [a for a in json.loads(r["areas"]) if a not in HIDDEN]]
    hidden_only = sum(1 for r in rows if r["areas"] and json.loads(r["areas"])
                      and not [a for a in json.loads(r["areas"])
                               if a not in HIDDEN])
    for r in ours[:n]:
        a = [x for x in json.loads(r["areas"]) if x not in HIDDEN]
        print("  {0:<10} {1} areas {2}{3}{4}".format(
            r["reference"], r["dated"], ",".join(map(str, a)),
            "" if r["tier"] == 1 else "  (tier 2)",
            "  [tabled in Welsh]" if r["welsh"] else ""))
        print("        {0}".format((r["body"] or "")[:92]))
        print("        asked by {0} ({1})".format(
            r["member_name"], r["constituency"]))
        if r["answer"]:
            print("        ANSWER ({0}, {1}): {2}...".format(
                r["answered_by"], r["answered"], (r["answer"] or "")[:70]))
    if len(ours) > n:
        print("\n  ...and {0} more. --n {1} to show them.".format(
            len(ours) - n, len(ours)))
    if hidden_only:
        print("\n  {0} further question(s) match HIDDEN areas only (11) -- "
              "tracked,\n  never displayed. Counted here so the silence is "
              "visible.".format(hidden_only))

    per = {}
    for r in ours:
        for a in json.loads(r["areas"]):
            if a not in HIDDEN:
                per[a] = per.get(a, 0) + 1
    if per:
        print(); print(line)
        print("PER AREA"); print(line)
        for a in sorted(per):
            print("  {0:<2} {1:<42} {2}".format(a, names.get(a, "?"), per[a]))

    nb=conn.execute("SELECT COUNT(*) FROM sd_bills").fetchone()[0]
    if nb:
        print(); print(line)
        print("BILLS    [tools/sd_bills.py]"); print(line)
        for r in conn.execute("SELECT iid, title, latest_stage, stage_date, "
                              "areas FROM sd_bills ORDER BY "
                              "CASE WHEN latest_stage LIKE 'Stage%' THEN 0 "
                              "WHEN latest_stage='Introduced' THEN 1 ELSE 2 "
                              "END, iid DESC"):
            mark = "OURS  " if r["areas"] and r["areas"] != "[]" else "      "
            print("  {0}{1:<58} {2}{3}".format(
                mark, (r["title"] or "?")[:57], r["latest_stage"],
                " ({0})".format(r["stage_date"]) if r["stage_date"] else ""))
        print("\n  {0} bill(s); stage parsed from the tracking page's PROSE"
              .format(nb))
        print("  (no status field exists); NEW bills are caught the week")
        print("  their tracking page first moves in mgWhatsNew.")

    dv=conn.execute("SELECT COUNT(*) FROM sd_divisions").fetchone()[0]
    if dv:
        print(); print(line)
        print("HOW MSs VOTED    [tools/sd_divisions.py]"); print(line)
        nours=conn.execute("SELECT COUNT(*) FROM sd_divisions WHERE areas IS "
                           "NOT NULL AND areas != '[]'").fetchone()[0]
        nv=conn.execute("SELECT COUNT(*) FROM sd_votes").fetchone()[0]
        print("  {0} division(s) with per-member votes ({1} positions); {2} "
              "on our ground".format(dv, nv, nours))
        print("  by DEBATE TITLE -- coarser than a motion-text join; phase 3")
        print("  transcripts sharpen it.")
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import sd_5ca
        entries = sd_5ca.load_stance()
        placing = sum(1 for e in entries.values()
                      if not e.get("draft") and (e.get("for") is not None
                                                 or e.get("against") is not None))
        drafts = sum(1 for e in entries.values() if e.get("draft"))
        print("  Meaning lines (config/sd_stance.yaml): {0} entries -- {1} "
              "place, {2} draft,".format(len(entries), placing, drafts))
        print("  {0} NOT PLACEABLE; the sheet is tools/sd_5ca.py, never "
              "posted.\n".format(len(entries) - placing - drafts))
        for r in conn.execute("SELECT dated,title,total_for,total_against,"
                              "result FROM sd_divisions WHERE areas IS NOT "
                              "NULL AND areas != '[]' AND areas NOT IN "
                              "('[11]') ORDER BY dated DESC LIMIT " + str(n)):
            print("  OURS  {0}  {1}".format(r["dated"], (r["title"] or "")[:64]))
            print("        {0} for / {1} against -- {2}".format(
                r["total_for"], r["total_against"], (r["result"] or "")[:44]))

    occ = conn.execute("SELECT COUNT(*), COUNT(DISTINCT member_id) FROM "
                       "sd_events WHERE key LIKE 'sdcc%'").fetchone()
    ncom = conn.execute("SELECT COUNT(*), SUM(meetings_seen) FROM "
                        "sd_committees").fetchone()
    if ncom[0]:
        print(); print(line)
        print("COMMITTEE SCRUTINY    [tools/sd_committees.py]"); print(line)
        print("  {0} committee(s) tracked, {1} sitting(s) read; {2} passage-"
              .format(ncom[0], ncom[1] or 0, occ[0]))
        print("  matched contribution(s) from {0} Member(s). The Seventh"
              .format(occ[1] or 0))
        print("  Senedd's committees were only established in mid-2026, so")
        print("  this ledger is thin BY AGE, not by omission. ACTIVITY ONLY.\n")
        for r in conn.execute("SELECT dated, member_name, heading, areas, "
                              "excerpt FROM sd_events WHERE key LIKE 'sdcc%' "
                              "ORDER BY dated DESC LIMIT " + str(n)):
            a = [x for x in json.loads(r["areas"] or "[]") if x not in HIDDEN]
            if not a:
                continue
            print("  OURS  {0}  {1}".format(r["dated"], (r["heading"] or "")[:60]))
            print("        {0}   areas {1}".format(
                r["member_name"], ",".join(map(str, a))))
            # 180 chars, not 88: a committee contribution buries the
            # subject mid-paragraph ("...next item, 3.2, P-07-1564,
            # 'Restore parental consent for RVE lessons'"), so a short
            # window shows only the chair clearing his throat.
            print("        \"{0}...\"".format(
                " ".join((r["excerpt"] or "").split())[:180]))

        print(); print(line)
        print("WHAT IS COMING    [committee detail pages]"); print(line)
        upcoming = conn.execute(
            "SELECT name, next_meeting, next_meeting_id FROM sd_committees "
            "WHERE next_meeting IS NOT NULL AND next_meeting >= date('now') "
            "ORDER BY next_meeting").fetchall()
        silent = conn.execute("SELECT COUNT(*) FROM sd_committees WHERE "
                              "next_meeting IS NULL OR next_meeting < "
                              "date('now')").fetchone()[0]
        for r in upcoming:
            print("  {0}  {1}".format(r["next_meeting"], (r["name"] or "")[:58]))
        print("\n  {0} committee(s) have announced a next sitting; {1} have"
              .format(len(upcoming), silent))
        print("  not. The AGENDA for a future sitting is published later, so")
        print("  a date here carries NO subject yet -- the taxonomy cannot")
        print("  tell you whether it is ours until the agenda appears.")
        print("  There is no plenary forward diary: the ModernGov calendar")
        print("  holds exhibitions only (all three views), and its Month and")
        print("  Year parameters are silently ignored.")

    print(); print(line)
    print("GOVERNMENT CONSULTATIONS    [tools/dg_consultations.py]")
    print(line)
    from src.ingest import devolved
    devolved.render_consultations(
        conn, "wales", lambda areas: [a for a in areas if a not in HIDDEN],
        datetime.date.today().isoformat(), n=n)

    print(); print(line)
    print("WHAT THIS DOES NOT KNOW    [src/ingest/senedd.py]"); print(line)
    print("  * NO DATA API EXISTS. Discovery is ID-WALKING the Record's")
    print("    per-question pages (the /Search endpoint ignores its query;")
    print("    the ModernGov XML exports serve HTML shells). Dense ids mean")
    print("    the taxonomy classifies EVERY question -- no sweep terms.")
    ros = conn.execute("SELECT COUNT(*) FROM sd_members WHERE end_date IS "
                       "NULL OR end_date >= date('now')").fetchone()[0]
    if ros:
        print("  * PARTY comes from mySociety parlparse ({0} sitting members"
              .format(ros))
        print("    held), joined by name at display time -- the Senedd's own")
        print("    party source WAF-403s our honest User-Agent, and parlparse")
        print("    is public and maintained. Unmatched names are reported,")
        print("    never guessed.")
    else:
        print("  * PARTY: the parlparse roster loader is built but not yet")
        print("    run (tools/sd_members.py; waits for the question backfill")
        print("    to release the store -- one writer at a time).")
    ev=conn.execute("SELECT COUNT(*), COUNT(DISTINCT member_id) FROM "
                    "sd_events").fetchone()
    print("  * VOTES AND SPEECHES come from the undocumented XMLExport (found")
    print("    via mySociety's scraper), one index walk serving both.")
    print("    {0} speech event(s) from {1} member(s) sit in sd_events --"
          .format(ev[0], ev[1]))
    print("    passage-matched, quotable, ACTIVITY ONLY: no stance scoring")
    print("    in a watching brief, so a speech never places.")
    print("  * COMMITTEES remain behind the ModernGov SOAP WSDL, which")
    print("    rejects our honest User-Agent -- blocked on the same UA")
    print("    decision as party was before parlparse solved it.")
    print("  * REFRESHED WEEKLY: Thursday 06:00 UTC via")
    print("    .github/workflows/sd-weekly.yml (roster + question walk --")
    print("    no publish step exists; the watching brief stays off Slack).")
    total = conn.execute("SELECT COUNT(*) FROM sd_items").fetchone()[0]
    print("\n  {0} row(s) in sd_items. Not in `items`, so structurally "
          "cannot reach\n  the Slack digest.".format(total))
    conn.close()


if __name__ == "__main__":
    main()
