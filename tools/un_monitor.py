"""The UN monitor at a glance, from the store. No network, no waiting.

    python3 tools/un_monitor.py            # everything
    python3 tools/un_monitor.py --area 6   # one issue area

Reads only what has already been harvested, so it is safe to run any time and
tells you what the monitor currently KNOWS -- which is not the same as what is
true. Each section says when it was last refreshed and what refreshes it, so a
stale section reads as stale rather than as quiet.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, emerging, filter as filt, intel
from src.ingest import treaty_comments, un_votes as votes_mod

BAR = "-" * 78


def head(title, refreshed_by):
    print("\n" + BAR)
    print("{0}    [{1}]".format(title, refreshed_by))
    print(BAR)


def areas_of(row):
    return json.loads(row["areas"] or "[]")


def area_terms(tax, areas):
    """The configured terms for the given areas, for rights-claim co-occurrence."""
    out = []
    for area in areas:
        for tier in (tax.terms.get(area) or {}).values():
            out.extend(term for term, _p, _cs, _g in tier)
    return [t.rstrip("*") for t in out]


def main():
    want = None
    if "--area" in sys.argv:
        want = int(sys.argv[sys.argv.index("--area") + 1])
    today = datetime.date.today()
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))

    scope = " — area {0} ({1})".format(want, names.get(want, "?")) if want else ""
    print("\nCITIZENGO UN MONITOR{0}".format(scope))
    print("as at {0}".format(today.isoformat()))

    # -- forward calendar ---------------------------------------------------
    head("WHAT IS COMING", "tools/un_forward.py")
    rows = [r for r in conn.execute(
        "SELECT * FROM un_calendar WHERE gone_at IS NULL AND starts >= ? "
        "ORDER BY starts", (today.isoformat(),))]
    if want is not None:
        rows = [r for r in rows if want in areas_of(r)]
    if not rows:
        print("  nothing stored ahead of today. Run tools/un_forward.py.")
    for r in rows[:14]:
        left = (datetime.date.fromisoformat(r["starts"][:10]) - today).days
        mark = "OURS" if areas_of(r) else "    "
        when = r["starts"][:10] if not r["approximate"] else r["starts"][:7]
        print("  {0} {1:>4}d  {2:<8} {3}".format(mark, left, r["kind"].upper(),
                                                 (r["title"] or "")[:52]))
        print("            {0}{1}".format(when, "  areas " + ",".join(
            str(a) for a in areas_of(r)) if areas_of(r) else ""))
    if len(rows) > 14:
        print("  ...and {0} more within the stored horizon".format(len(rows) - 14))

    # -- drafts -------------------------------------------------------------
    head("WHAT IS BEING PROPOSED", "tools/un_drafts.py")
    drafts = [r for r in conn.execute(
        "SELECT * FROM un_documents WHERE areas IS NOT NULL AND areas != '[]' "
        "ORDER BY body, session, symbol")]
    if want is not None:
        drafts = [r for r in drafts if want in areas_of(r)]
    if not drafts:
        print("  no classified drafts stored. Run tools/un_drafts.py.")
    for r in drafts:
        label = r["kind"] or "?"
        if r["amends"]:
            label = "amendment to " + r["amends"]
        # Fall back to the agenda-item title: a long resolution title lands
        # in `subject` when the parser could not isolate the shorter one, and
        # printing "?" hid A/C.3/80/L.59 entirely.
        print("  OURS  {0:<16} {1}".format(
            r["symbol"], (r["title"] or r["subject"] or "?")[:50]))
        print("        {0:<30} areas {1}   {2}".format(
            label[:30], ",".join(str(a) for a in areas_of(r)), r["dated"] or ""))
    total = conn.execute("SELECT COUNT(*) FROM un_documents").fetchone()[0]
    print("\n  {0} of {1} stored drafts touch our areas.".format(len(drafts), total))

    # -- campaign triggers --------------------------------------------------
    head("CAMPAIGN TRIGGERS", "tools/un_drafts.py, tools/un_comments.py")
    print("  A campaign needs a date, a decider, and a decision that can still")
    print("  go either way. These are the events that offer all three.\n")
    trig = [r for r in conn.execute(
        "SELECT symbol, body, title, kind, event, areas, dated FROM un_documents "
        "WHERE event IS NOT NULL ORDER BY event, symbol")]
    if want is not None:
        trig = [r for r in trig if want in areas_of(r) or r["event"] != "mandate"]
    if not trig:
        print("  none stored.")
    for r in trig:
        # A general comment is ours by COMMITTEE, not by being a general
        # comment: the first version flagged CERD and CMW as ours, which is the
        # over-flagging this codebase keeps having to design out.
        ours = bool(areas_of(r))
        if r["event"] == "interpretation" and r["body"]:
            ours = ours or any(r["body"].upper().startswith(t)
                               for t in treaty_comments.OURS)
        mark = "OURS" if ours else "    "
        print("  {0}  {1:<14} {2:<14} {3}".format(
            mark, (r["event"] or "").upper()[:14], r["symbol"][:14],
            (r["title"] or "")[:44]))
    print("\n  MANDATE      a rapporteur post created, renewed or ended. Renewal")
    print("               runs on a three-year cycle, so the vote is knowable")
    print("               years ahead -- the most predictable moment there is.")
    print("  INTERPRETATION a treaty body general comment. GC36 read abortion")
    print("               into the right to life; this outlasts any resolution.")
    print("  NOT TRACKED  appointments and elections -- the Bachelet class. Every")
    print("               OHCHR vacancies and elections page answers 403.")

    # -- votes --------------------------------------------------------------
    head("HOW STATES VOTED", "tools/un_votes.py")
    vrows = conn.execute(
        "SELECT report, COUNT(DISTINCT draft) votes, COUNT(*) positions "
        "FROM un_votes GROUP BY report").fetchall()
    if not vrows:
        print("  no votes stored. Run tools/un_votes.py <session>.")
    for r in vrows:
        print("  {0}: {1} recorded votes, {2} state positions".format(
            r["report"], r["votes"], r["positions"]))
    # Join on the UNREVISED symbol: a vote is taken on L.20/Rev.1 while the
    # draft harvest holds L.20, so an exact join silently matches nothing --
    # which is what made this section look empty at first.
    docs = {r["symbol"]: r for r in conn.execute(
        "SELECT symbol, title, subject, areas FROM un_documents")}
    tallies = {}
    for r in conn.execute("SELECT draft, position, COUNT(*) n FROM un_votes "
                          "GROUP BY draft, position"):
        tallies.setdefault(r["draft"], {})[r["position"]] = r["n"]
    shown = 0
    for draft, counts in sorted(tallies.items()):
        doc = docs.get(draft) or docs.get(votes_mod.base_symbol(draft))
        if not doc:
            continue
        areas = json.loads(doc["areas"] or "[]")
        if not areas or (want is not None and want not in areas):
            continue
        shown += 1
        print("  OURS  {0:<22} {1} for / {2} against / {3} abstaining".format(
            draft, counts.get("for", 0), counts.get("against", 0),
            counts.get("abstain", 0)))
        print("        {0}".format((doc["title"] or doc["subject"] or "")[:64]))
    if not shown:
        print("  none of the voted drafts are in our areas -- our texts in this "
              "session were adopted without a vote, which is itself the finding.")

    # -- UPR ----------------------------------------------------------------
    head("WHERE STATES STAND (UPR)", "tools/pull_upr.py, monthly")
    n = conn.execute("SELECT COUNT(*) FROM upr_recommendations").fetchone()[0]
    states = conn.execute("SELECT COUNT(DISTINCT state_under_review) "
                          "FROM upr_recommendations").fetchone()[0]
    print("  {0} recommendations across {1} states reviewed.".format(n, states))
    sql = ("SELECT state_under_review s, COUNT(*) n, SUM(refused) f "
           "FROM upr_recommendations WHERE state_under_review IS NOT NULL ")
    if want is not None:
        sql += "AND issue_areas LIKE '%{0}%' ".format(want)
    sql += ("GROUP BY s HAVING n >= 10 "
            "ORDER BY (CAST(SUM(refused) AS FLOAT)/COUNT(*)) DESC, n DESC LIMIT 5")
    print("  highest refusal rates (10+ recommendations):")
    for r in conn.execute(sql):
        print("     {0:<34} {1}/{2} refused ({3:.0%})".format(
            r["s"][:34], r["f"], r["n"], r["f"] / r["n"]))

    # -- emerging language ----------------------------------------------------
    head("EMERGING LANGUAGE", "tools/un_emerging.py")
    print("  Phrases the corpus has barely seen, in drafts already on our ground.")
    corpus = [r["text"] for r in conn.execute(
        "SELECT text FROM upr_recommendations WHERE text IS NOT NULL")]
    corpus += [" ".join(filter(None, (r["title"], r["instruction"])))
               for r in conn.execute("SELECT title, instruction FROM un_documents")]
    baseline = emerging.build_baseline(corpus)
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "un-taxonomy.yaml"))
    edocs = [r for r in conn.execute(
        "SELECT symbol, title, subject, instruction, areas FROM un_documents "
        "WHERE areas IS NOT NULL AND areas != '[]'")]
    if want is not None:
        edocs = [r for r in edocs if want in areas_of(r)]
    scanned = flagged = shown = 0
    for r in edocs:
        scanned += 1
        text = " ".join(filter(None, (r["title"], r["instruction"])))
        novel = emerging.longest_novel(text, baseline, max_df=1, limit=3)
        claims = emerging.rights_claims(text, area_terms(tax, areas_of(r)))
        if not novel and not claims:
            continue
        flagged += 1
        if shown >= 6:
            continue
        shown += 1
        print("  {0:<16} areas {1}".format(r["symbol"], ",".join(
            str(a) for a in areas_of(r))))
        for phrase in novel:
            print("        NEW PHRASE   {0}".format(phrase[:64]))
        for sentence, terms in claims:
            print("        RIGHTS CLAIM {0}".format(sentence[:60]))
    if not scanned:
        print("  no classified drafts to scan.")
    elif not flagged:
        print("  {0} draft(s) scanned, nothing novel found.".format(scanned))
    else:
        print("\n  {0} of {1} scanned raised something (top {2} shown). Full "
              "queue, tunable df: tools/un_emerging.py".format(
                  flagged, scanned, shown))

    # -- honesty ------------------------------------------------------------
    head("WHAT THIS DOES NOT KNOW", "docs/un-sources.md")
    print("  * Third Committee votes: the report series is not enumerable and "
          "session 80 plenary records are unpublished. One report symbol "
          "would unlock it.")
    print("  * Nothing here is scheduled except the monthly UPR harvest. The "
          "calendar, drafts and votes are refreshed only when run by hand.")
    print("  * The weekly DM is PAUSED (.github/workflows/un-calls-weekly.yml).")
    print("  * Draft subjects need pypdf; agendas come from L.1 of a session.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
