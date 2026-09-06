"""Re-derive areas for stored devolved and EU rows under the current taxonomy.

    python3 tools/retag_items.py                       # dry run: what would change
    python3 tools/retag_items.py --apply               # write it
    python3 tools/retag_items.py --baseline old.yaml   # trust check (see below)

Christopher, 2026-09-06: "Do the retag." Taxonomy v1.6 added an area and
closed five recall gaps, but a collector only re-filters a row when it
SEES it again, so anything outside the source window keeps the tags it
was given under v1.5 -- the EP's Maria Shahbaz resolution sat in the
store as area 8 by luck while the taxonomy that would tag it properly
already existed. This re-derives areas, matched_terms and tier for every
stored row, offline, no API.

THE TRAP, paid for once already. Each collector filters a PARTICULAR
text -- sp_items on body then title, sd_items on body alone, eu_speeches
on "debate excerpt", dg_consultations on "title summary" -- and the
first field passed is the title by convention (src/filter.py). Comparing
title-only re-derivation against stored full-text tags once produced
"574 rows re-tagged" that were nothing of the kind. So every table here
names the exact text its collector used, and a table whose deciding text
is not fully stored is SKIPPED and said so, rather than approximated.

THE TRUST CHECK. --baseline takes the PREVIOUS taxonomy yaml. Re-deriving
with it should reproduce the stored tags almost exactly; where it does
not, the text mapping above is wrong for that table, and the tool
refuses to --apply that table. This is how a wrong mapping is caught
before it writes, not after.

TRIAGE IS NOT TOUCHED. Scores are written once, ever, and triage is
paused (Christopher, 2026-09-04). A row that gains an area has no
why-line yet; a row that loses every area keeps a why-line written for
an area it no longer has. Both counts are printed so neither is silent.

DRY RUN BY DEFAULT, because re-derivation is authoritative: a row that no
longer supports an area has its areas CLEARED -- the ni_classify contract.
ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt


def _s(v):
    return v or ""


# table -> (key column, text builder: row -> (args, kwargs), note)
# The builder reproduces EXACTLY the filter_item call in the collector.
TABLES = {
    "sp_items": ("id",
                 lambda r: ((_s(r["body"]), _s(r["title"])), {}),
                 "sp_pull: filter_item(body, title)"),
    "sd_items": ("id",
                 lambda r: ((_s(r["body"]),), {}),
                 "sd_pull: filter_item(body)"),
    "ni_items": ("id",
                 lambda r: (((_s(r["title"]), _s(r["body"])),
                             {"title": _s(r["title"])})
                            if r["kind"] == "motion"
                            else ((_s(r["title"]),), {})),
                 "ni_pull: motions filter_item(title, body, title=title); "
                 "questions and diary filter_item(title)"),
    "eu_texts": ("identifier", lambda r: ((_s(r["title"]),), {}),
                 "eu_texts: filter_item(title)"),
    "eu_agenda": ("activity_id", lambda r: ((_s(r["label"]),), {}),
                  "eu_agenda: filter_item(label)"),
    "eu_pqs": ("identifier", lambda r: ((_s(r["title"]),), {}),
               "eu_pqs: filter_item(title)"),
    "eu_cmte_docs": ("identifier", lambda r: ((_s(r["title"]),), {}),
                     "eu_committees: filter_item(title)"),
    "eu_ecis": ("reg_num", lambda r: ((_s(r["title"]),), {}),
                "eu_eci: filter_item(title)"),
    "eu_speeches": ("speech_id",
                    lambda r: (("{0} {1}".format(_s(r["debate"]),
                                                 _s(r["excerpt"])),), {}),
                    "eu_speeches: filter_item('debate excerpt')"),
    "eu_divisions": ("vote_id", lambda r: ((_s(r["label"]),), {}),
                     "eu_rollcalls: filter_item(label)"),
    "dg_consultations": ("key",
                         lambda r: (("{0} {1}".format(_s(r["title"]),
                                                      _s(r["summary"])),), {}),
                         "dg_consultations: filter_item('title summary')"),
    "sd_divisions": ("key", lambda r: ((_s(r["title"]),), {}),
                     "sd_divisions: filter_item(title)"),
    # sp_divisions has TWO writers. official-report rows were filtered on
    # the HEADING (for an amendment the stored title is "heading --
    # amendment N outcome", so the heading is recovered). votesmotion rows
    # never saw the filter at all: they COPY areas from the linked
    # sp_items motion, and are re-inherited below after sp_items is
    # retagged -- the trust check exposed this when "Business Programme"
    # turned out to carry area 3, which no heading could produce.
    "sp_divisions": ("key",
                     lambda r: ((_s(r["title"]).split(" -- amendment ")[0],),
                                {}),
                     "sp_divisions (official-report): filter_item(heading)",
                     "source = 'official-report'"),
}

INHERIT = {
    # (table, key col, link col) <- (parent table, parent key)
    "sp_divisions/votesmotion": (
        "sp_divisions", "key", "item_id", "sp_items", "id",
        "source = 'votesmotion' AND item_id IS NOT NULL"),
}

# Tables NOT retagged, each with its reason. Listed so the omission is a
# decision on the page rather than a gap nobody notices.
SKIPPED = {
    "eu_judgments": "eu_courts filters 'case_name conclusion SEARCH-TERM' and "
                    "the search term is not stored, so the deciding text "
                    "cannot be reproduced.",
    "ni_divisions": "owned by tools/ni_classify.py, which re-derives from "
                    "archived Hansard by the amendment's own wording.",
    "sp_events": "passage-matched by tools/sp_divisions.py from speech "
                 "text held in data/raw; retag_passages-shaped, not this.",
    "sd_events": "passage-matched from the Record by tools/sd_committees.py "
                 "and sd_divisions.py; same reason.",
    "items": "the Westminster ledger has tools/retag_passages.py.",
    "mp_events": "the Westminster ledger has tools/retag_passages.py.",
}


def derive(tax, wl, spec, row):
    args, kwargs = spec[1](row)
    res = filt.filter_item(tax, wl, *args, **kwargs)
    return (sorted(res.issue_areas or []), sorted(res.matched_terms or []),
            res.tier)


def stored(row):
    areas = sorted(json.loads(row["areas"] or "[]"))
    return areas


def walk(conn, tax, wl, table, spec):
    """-> rows, [(key, old_areas, new_areas, new_terms, new_tier, row)]"""
    keycol = spec[0]
    where = ("WHERE " + spec[3]) if len(spec) > 3 else ""
    changes, n = [], 0
    for row in conn.execute("SELECT * FROM {0} {1}".format(table, where)):
        n += 1
        old = stored(row)
        new, terms, tier = derive(tax, wl, spec, row)
        if old != new:
            changes.append((row[keycol], old, new, terms, tier, row))
    return n, changes


def trust_check(conn, baseline, current, wl, log):
    """Re-derivation must reproduce the stored tags under the OLD taxonomy
    OR the current one.

    OR, because a weekly that ran after the taxonomy changed has already
    re-tagged the rows it re-saw: on 2026-09-05 the EU and NI weeklies
    stored [8, 9] and [11, 12], which v1.5 could never derive. Those rows
    are not evidence of a wrong mapping -- they are evidence the mapping
    is right under the taxonomy that actually produced them. A row that
    NEITHER taxonomy reproduces is the real signal.
    """
    untrusted = set()
    log("TRUST CHECK: every stored tag must be reproducible under the "
        "baseline OR the current taxonomy.")
    for table, spec in TABLES.items():
        n, changes = walk(conn, baseline, wl, table, spec)
        if not n:
            continue
        # keep only the rows the CURRENT taxonomy cannot explain either
        changes = [c for c in changes
                   if derive(current, wl, spec, c[5])[0] != c[1]]
        agree = 100.0 * (n - len(changes)) / n
        flag = ""
        if agree < 99.0:
            untrusted.add(table)
            flag = "   <-- MAPPING WRONG, will not apply"
        log("  {0:<18} {1:>6} rows  {2:6.2f}% reproduced{3}".format(
            table, n, agree, flag))
        if changes and agree < 99.0:
            for key, old, new, _t, _tier, row in changes[:3]:
                log("      e.g. {0}: stored {1}, baseline derives {2}".format(
                    key, old, new))
    return untrusted


def reinherit(conn, apply_it, log):
    """Copy tags back onto rows that never saw the filter themselves.

    votesmotion divisions take their areas from the linked sp_items
    motion; once sp_items is retagged, the copies are stale until this
    runs. Returns how many rows changed.
    """
    changed = 0
    for label, (table, keycol, link, parent, pkey, where) in INHERIT.items():
        rows = conn.execute(
            "SELECT c.{0} AS k, c.areas AS old, p.areas AS new, "
            "p.matched_terms AS terms, p.tier AS tier FROM {1} c "
            "JOIN {2} p ON p.{3} = c.{4} WHERE {5}".format(
                keycol, table, parent, pkey, link, where)).fetchall()
        diff = [r for r in rows
                if sorted(json.loads(r["old"] or "[]"))
                != sorted(json.loads(r["new"] or "[]"))]
        changed += len(diff)
        state = ""
        if apply_it and diff:
            for r in diff:
                conn.execute(
                    "UPDATE {0} SET areas = ?, matched_terms = ?, tier = ? "
                    "WHERE {1} = ?".format(table, keycol),
                    (r["new"], r["terms"], r["tier"], r["k"]))
            conn.commit()
            state = "   [written]"
        log("{0:<18} {1:>6} rows: ~{2} re-inherited from {3}{4}".format(
            label, len(rows), len(diff), parent, state))
    return changed


def main():
    apply_it = "--apply" in sys.argv
    baseline_path = None
    if "--baseline" in sys.argv:
        baseline_path = sys.argv[sys.argv.index("--baseline") + 1]
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

    untrusted = set()
    if baseline_path:
        untrusted = trust_check(conn, filt.load_taxonomy(baseline_path), tax,
                                wl, print)
        print("")

    total_gain = total_move = total_clear = 0
    no_why = stale_why = 0
    for table, spec in TABLES.items():
        n, changes = walk(conn, tax, wl, table, spec)
        if not n:
            continue
        gained = [c for c in changes if not c[1] and c[2]]
        cleared = [c for c in changes if c[1] and not c[2]]
        moved = [c for c in changes if c[1] and c[2]]
        total_gain += len(gained); total_move += len(moved); total_clear += len(cleared)
        cols = [c[1] for c in conn.execute("PRAGMA table_info({0})".format(table))]
        has_why = "why_it_matters" in cols
        if has_why:
            no_why += sum(1 for c in gained if not c[5]["why_it_matters"])
            stale_why += sum(1 for c in cleared if c[5]["why_it_matters"])
        state = ""
        if table in untrusted:
            state = "   [NOT APPLIED: mapping untrusted]"
        elif apply_it and changes:
            keycol = spec[0]
            for key, _old, new, terms, tier, _row in changes:
                conn.execute(
                    "UPDATE {0} SET areas = ?, matched_terms = ?, tier = ? "
                    "WHERE {1} = ?".format(table, keycol),
                    (json.dumps(new), json.dumps(terms), tier, key))
            conn.commit()
            state = "   [written]"
        print("{0:<18} {1:>6} rows: +{2} gained, ~{3} moved, -{4} cleared{5}"
              .format(table, n, len(gained), len(moved), len(cleared), state))
        for key, old, new, _t, _tier, row in (gained + moved)[:4]:
            title = next((row[c] for c in ("title", "label", "debate")
                          if c in row.keys() and row[c]), str(key))
            print("      {0} -> {1}  {2}".format(old, new, title[:70]))

    total_move += reinherit(conn, apply_it, print)

    print("")
    print("SKIPPED, by decision:")
    for table, why in SKIPPED.items():
        print("  {0:<16} {1}".format(table, why))
    print("")
    print("{0} gained an area, {1} moved, {2} cleared.".format(
        total_gain, total_move, total_clear))
    if no_why or stale_why:
        print("Triage untouched (paused): {0} newly matched row(s) have no "
              "why-line; {1} cleared row(s) keep a why-line written for an "
              "area they no longer have.".format(no_why, stale_why))
    if not apply_it:
        print("dry run; re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
