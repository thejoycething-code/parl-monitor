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

from src import db, intel, ni_answers, ni_store

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
    # Two maps, not one: party AS AT the tabling date where we have it, the
    # current roster only as a marked fallback. No question payload carries a
    # party at all, so this join is the whole of attribution.
    as_at = ni_store.affiliation_map(conn)
    current = ni_store.current_map(conn)
    for r in visible[:limit]:
        print("  {0:<16} {1:<10} areas {2}".format(
            (r["reference"] or "?")[:16], r["dated"] or "undated",
            ",".join(str(a) for a in sorted(set(areas_of(r)) - hidden))))
        print("        {0}".format((r["title"] or "")[:68]))
        who = r["tabler"] or ""
        if who:
            party, seat, source = ni_store.party_at(
                r["tabler_person_id"], r["dated"], as_at, current)
            seat = seat or r["tabler_seat"] or ""
            print("        asked by {0} ({1}){2}".format(
                who, ni_store.label(party, source),
                " — {0}".format(seat) if seat else ""))
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
    print("  to an EDM, and unlike a Westminster EDM these name their tablers.")
    print("  Classified on the motion's TEXT, not its title: a title runs three")
    print("  to six words and matched 0 of 33 for as long as the feed existed.\n")
    # Motions are stored UNFILTERED (so a taxonomy change can re-test them
    # offline, and so their wording is not re-fetched weekly), so the filter
    # happens here. `rows` already narrows to --area when one is given.
    all_motions = rows("motion")
    ms = [r for r in all_motions if areas_of(r)]
    if not ms:
        print("  no motions matched. Run tools/ni_pull.py -- if this is still")
        print("  empty afterwards it is a real zero, since the operative")
        print("  wording is now fetched and classified.")
    for r in ms:
        parties = json.loads(r["parties"] or "[]")
        print("  {0:<10} {1:<34} areas {2}".format(
            r["dated"] or "undated", (r["title"] or "")[:34],
            ",".join(str(a) for a in areas_of(r))))
        print("        {0}   tabled by {1}".format(
            (r["category"] or "")[:30], "/".join(parties) or "unattributed"))
        terms = json.loads(r["matched_terms"] or "[]")
        if terms:
            print("        on: {0}".format(", ".join(terms[:4])))
        # The wording is why the row is here, so show it rather than making
        # someone open the Assembly site to find out what the motion says.
        if r["body"]:
            print("        \"{0}...\"".format(
                " ".join(r["body"].split())[:96]))
    if all_motions:
        print("\n  {0} of {1} tabled motion(s) match our areas. The rest are "
              "held with their\n  wording so a taxonomy change can re-test them "
              "without re-fetching.".format(len(ms), len(all_motions)))

    # -- ministerial answers --------------------------------------------------
    head("WHAT MINISTERS SAY", "tools/ni_pull.py")
    print("  The only GOVERNMENT position in this monitor -- everything else is")
    print("  what members do. Grouped by department, and led by the answers")
    print("  where a Minister DECLINED: those are the quotable ones.\n")
    ans = [r for r in conn.execute(
        "SELECT reference, dated, department, minister, title, answer, "
        "answer_shape, areas FROM ni_items WHERE kind = 'question' "
        "AND answer IS NOT NULL AND answer != '' ORDER BY dated DESC")]
    if want is not None:
        ans = [r for r in ans if want in areas_of(r)]
    shaped = [r for r in ans if r["answer_shape"]]
    if not ans:
        print("  no answers stored. Run tools/ni_pull.py.")
    elif not shaped:
        print("  {0} answer(s) held, none of them a refusal or a data gap. That")
        print("  is a real result: a substantive answer carries no shape."
              .format(len(ans)))
    for r in shaped[:8]:
        print("  {0}  {1:<34} {2}".format(
            r["dated"] or "undated", (r["department"] or "?")[:34],
            r["answer_shape"].upper()))
        print("        Q: {0}".format(" ".join((r["title"] or "").split())[:66]))
        # The sentence that declines, not an arbitrary slice of 980 characters.
        print("        A: \"{0}\"".format(
            ni_answers.quote(r["answer"], r["answer_shape"], limit=104)))
    if len(shaped) > 8:
        print("\n  ...and {0} more declined answer(s).".format(len(shaped) - 8))
    if ans:
        by_dept = {}
        for r in ans:
            d = by_dept.setdefault(r["department"] or "?", [0, 0])
            d[0] += 1
            if r["answer_shape"]:
                d[1] += 1
        print("\n  {0} of {1} answer(s) decline, across {2} department(s):".format(
            len(shaped), len(ans), len(by_dept)))
        for dept, (total, declined) in sorted(
                by_dept.items(), key=lambda kv: -kv[1][1])[:6]:
            print("     {0:<44} {1:>3} answers, {2} declined".format(
                dept[:44], total, declined))

    # -- forward diary ------------------------------------------------------
    head("WHAT IS COMING", "tools/ni_pull.py")
    # TWO SOURCES, in order of substance. The Order Paper (kind='plenary')
    # names the BUSINESS -- motions, bill stages, petitions of concern -- and
    # is the NI equivalent of Westminster's What's On. The business diary
    # (kind='diary') names committees and rooms only, so it renders second, as
    # calendar rather than agenda.
    plenary = [r for r in conn.execute(
        "SELECT * FROM ni_items WHERE kind = 'plenary' AND dated >= ? "
        "ORDER BY dated", (today.isoformat(),))]
    if want is not None:
        plenary = [r for r in plenary if want in areas_of(r)]
    if not plenary:
        print("  no plenary business stored ahead of today. During recess only")
        print("  Written Ministerial Statements are tabled ahead; motions and")
        print("  bill stages arrive roughly four weeks out. Run tools/ni_pull.py.")
    for r in plenary[:14]:
        left = (datetime.date.fromisoformat(r["dated"]) - today).days
        mark = "OURS" if areas_of(r) else "    "
        poc = "  PETITION OF CONCERN" if "petition of concern" in (
            r["category"] or "").lower() else ""
        print("  {0} {1:>4}d  {2:<24} {3}{4}".format(
            mark, left, (r["category"] or "")[:24], (r["title"] or "")[:40],
            poc))
    if len(plenary) > 14:
        print("  ...and {0} more within the stored horizon".format(
            len(plenary) - 14))
    diary = [r for r in conn.execute(
        "SELECT * FROM ni_items WHERE kind = 'diary' AND dated >= ? "
        "ORDER BY dated", (today.isoformat(),))]
    # Committee agendas, keyed on the diary's event id. An agenda item's SUBJECT
    # is classified, so an OURS mark here means the business is ours -- which is
    # what the committee name alone could never tell you.
    agenda = {}
    for r in conn.execute(
            "SELECT event_id, item_order, business, item_type, session, areas "
            "FROM ni_agenda ORDER BY event_id, item_order"):
        agenda.setdefault(r["event_id"], []).append(r)
    if diary:
        print("\n  committee meetings, with the business they are taking:")
    for r in diary[:8]:
        left = (datetime.date.fromisoformat(r["dated"]) - today).days
        event_id = (r["id"] or "").split(":")[-1]
        items = agenda.get(event_id, [])
        ours = [i for i in items if areas_of(i)]
        print("       {0:>4}d  {1}".format(left, (r["title"] or "")[:52]))
        if not items:
            print("              (no agenda published yet)")
        for i in ours:
            print("         OURS  areas {0}  {1}{2}".format(
                ",".join(str(a) for a in areas_of(i)), (i["business"] or "")[:46],
                "  [CLOSED SESSION]"
                if "closed" in (i["session"] or "").lower() else ""))
        # Everything else as a count, not a list: a meeting can run nine slots
        # and listing them all would bury the OURS rows this section exists for.
        rest = len(items) - len(ours)
        if rest:
            print("              +{0} other item(s)".format(rest))
    if len(diary) > 8:
        print("       ...and {0} more meeting(s)".format(len(diary) - 8))

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
        print("  {0} division(s) stored; {1} on watched bills; {2} carry an "
              "issue area,\n  derived from the amendment's own wording in "
              "Hansard.".format(dtotal, watched, auto))
        rows_v = conn.execute(
            "SELECT d.bill, d.doc_id, d.dated, d.kind, d.subject, d.item_name, "
            "  d.amendment_no, d.excerpt, d.evidence, d.evidence_source, d.areas, "
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
        # OURS-first, then by date: with 37 rows and a 12-row budget, sorting by
        # date alone buried the four classified divisions -- which are the only
        # ones anybody opened this section to find.
        ordered = sorted(rows_v, key=lambda r: (
            not areas_of(r), r["dated"] or ""), reverse=False)
        ordered = sorted(ordered, key=lambda r: (bool(areas_of(r)),
                                                 r["dated"] or ""), reverse=True)
        for r in ordered[:12]:
            flag = "  CROSS-COMMUNITY" if "cross" in (r["kind"] or "").lower() else ""
            areas = areas_of(r)
            mark = "OURS  " if areas else "      "
            # The UNTRUNCATED item name from Hansard, where classification found
            # one: `bill` is derived from a subject the API cuts at 100 chars.
            print("\n  {0}{1}  {2}{3}".format(
                mark, r["dated"] or "undated",
                (r["item_name"] or r["bill"] or "?")[:44], flag))
            if areas:
                print("        areas {0}".format(
                    ",".join(str(a) for a in areas)))
            print("        {0} aye / {1} no  of {2} voting".format(
                r["ayes"], r["noes"], r["n"]))
            shown = r["excerpt"] or r["evidence"]
            if shown:
                # Labelled with its source so a motion-derived area can never
                # read as though it came from the amendment.
                label = ("amendment {0}".format(r["amendment_no"])
                         if r["amendment_no"] is not None
                         else (r["evidence_source"] or "text"))
                print("        {0}: {1}".format(label, shown[:60]))
        if len(rows_v) > 12:
            print("\n  ...and {0} more with votes stored.".format(len(rows_v) - 12))
        # Party is resolved AS AT THE DIVISION DATE, not from the current
        # roster: a vote belongs to the party the member held when they cast
        # it. Joining ni_members instead would file every Beattie vote before
        # his resignation under "Independent".
        positions = conn.execute(
            "SELECT v.person_id, v.vote, d.dated FROM ni_votes v "
            "JOIN ni_divisions d ON d.doc_id = v.doc_id AND d.watched = 1"
        ).fetchall()
        tally, fallbacks = {}, 0
        for r in positions:
            party, _seat, source = ni_store.party_at(
                r["person_id"], r["dated"], as_at, current)
            if source != ni_store.AS_AT:
                fallbacks += 1
            key = ni_store.label(party, source)
            tally.setdefault(key, {})[r["vote"]] = \
                tally.setdefault(key, {}).get(r["vote"], 0) + 1
        if tally:
            print("\n  ACROSS ALL WATCHED DIVISIONS, by party AT THE TIME "
                  "(aye/no):")
            for party, counts in sorted(tally.items(),
                                        key=lambda kv: -sum(kv[1].values())):
                total = sum(counts.values())
                print("     {0:<34} {1:>4} aye / {2:>4} no   ({3} positions)"
                      .format(party[:34], counts.get("aye", 0),
                              counts.get("no", 0), total))
            print("  A party voting both ways across a bill is normal: these are")
            print("  amendment votes, so aye and no both cut both ways. Read the")
            print("  individual division before drawing any conclusion.")
            if fallbacks:
                print("  {0} position(s) could not be dated and use today's "
                      "party.".format(fallbacks))
        elif rows_v:
            print("\n  No party split available: no roster stored. Run "
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
    ev = conn.execute(
        "SELECT COUNT(*) FROM ni_divisions WHERE evidence_source = "
        "'amendment-text'").fetchone()[0]
    nt = conn.execute(
        "SELECT COUNT(*) FROM ni_divisions WHERE evidence_source = 'no-text'"
    ).fetchone()[0]
    print("  * DIVISIONS ARE CLASSIFIED FROM THE AMENDMENT'S OWN WORDING, read")
    print("    from Hansard: {0} of 139 carry their amendment text, {1} carry".format(
        ev, nt))
    print("    none at all. A subject line alone yielded 0 of 139, because it")
    print("    names an amendment NUMBER and is cut at 100 characters.")
    print("    Refresh with tools/ni_classify.py.")
    print("  * A FALSE NEGATIVE IS INVISIBLE. An amendment whose wording is")
    print("    anodyne but whose effect is on our ground will not classify, which")
    print("    is why config/ni_watch.yaml still gates what gets harvested.")
    print("  * MOTIONS CANNOT BE CLASSIFIED from title alone (see above). The")
    print("    Order Paper carries the full text; that is the route in.")
    ag = conn.execute("SELECT COUNT(*) FROM ni_agenda").fetchone()[0]
    ag_ours = conn.execute("SELECT COUNT(*) FROM ni_agenda WHERE areas IS NOT "
                           "NULL AND areas != '[]'").fetchone()[0]
    print("  * COMMITTEE AGENDAS are held for {0} slot(s), {1} on our ground, so"
          .format(ag, ag_ours))
    print("    an OURS mark on a committee item means the BUSINESS is ours. The")
    print("    diary row above it still carries only a committee name.")
    print("    A meeting weeks out often has no agenda published yet; that is")
    print("    shown as such rather than as an empty agenda.")
    held = len(ni_store.dates_present(conn))
    print("  * PARTY IS AS AT THE EVENT for the {0} date(s) resolved via "
          "GetAllMembersByGivenDate.".format(held))
    print("    Anything on an unresolved date falls back to today's roster and")
    print("    is marked \"(party today)\" -- never shown bare, because an")
    print("    unmarked party is what filed Doug Beattie's UUP questions under")
    print("    Independent. Run tools/ni_pull.py to resolve new dates.")
    try:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import ni_5ca
        entries = ni_5ca.load_stance()
        drafts = sum(1 for e in entries.values() if e.get("draft"))
    except Exception:                               # noqa: BLE001
        entries, drafts = {}, 0
    print("  * NO ESTIMATED STANCE. tools/ni_5ca.py builds a 5CA sheet, but an")
    print("    MLA is placed in a column ONLY by their vote on a division whose")
    print("    meaning a human has confirmed in config/ni_stance.yaml --")
    print("    {0} of {1} meaning line(s) there are still DRAFT and place "
          "nobody.".format(drafts, len(entries)))
    print("  * REFRESHED WEEKLY: Saturday 06:00 UTC via")
    print("    .github/workflows/ni-weekly.yml (pull, divisions, reclassify --")
    print("    no publish step exists; the watching brief stays off Slack).")
    print("    Run tools/ni_pull.py by hand for a mid-week refresh.")
    print("\n  {0} row(s) stored in ni_items. Not in `items`, so structurally "
          "cannot\n  reach the Slack digest.".format(total))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
