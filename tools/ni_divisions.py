"""Northern Ireland Assembly divisions, and per-MLA votes for watched bills.

    python3 tools/ni_divisions.py --review          # candidate bills, no votes
    python3 tools/ni_divisions.py                   # harvest watched bills
    python3 tools/ni_divisions.py --days 730        # a longer window

TWO MODES ON PURPOSE. `--review` lists the bills that divided the Assembly,
ranked by how many divisions they drew, and fetches nothing per-member. That
is the queue a human reads before deciding what belongs in
config/ni_watch.yaml. Without the flag, only bills already listed there get
their member votes harvested.

The reason for the split is measured, not stylistic: of 139 divisions in the
twelve months to 2026-08-18, ZERO matched the taxonomy on their subject line.
A subject reads "Amendment 97 - Consideration Stage: Justice Bill (NIA Bill
7/22-27) (Day 4) [Mr Timothy Gaston]" -- an amendment number, never the
amendment's content, and cut off at 100 characters. Classifying that is not
possible; deciding that the Justice Bill is worth watching is. So the tool
asks a human for the one judgement it cannot make, exactly as
find_division_candidates.py does for Westminster.

Writes to ni_divisions and ni_votes, never to `items` or `mp_events`.
"""

from __future__ import annotations

import collections
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, ni_store
from src.http import HttpClient
from src.ingest import ni_hansard, niassembly

DEFAULT_DAYS = 365


def watched_bills():
    """Bill names a human has decided are ours, from config/ni_watch.yaml."""
    import yaml
    path = os.path.join(ROOT, "config", "ni_watch.yaml")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    return {(b.get("name") or "").strip(): (b.get("why") or "")
            for b in (cfg.get("bills") or []) if b.get("name")}


def store_division(conn, d, canonical_name, today):
    """Store one division's IDENTITY. `canonical_name` is the ni_watch.yaml name
    when the bill is watched, else None -- it replaces the derived (and possibly
    truncated) bill so every amendment of one Act groups together.

    Named-column upsert, NOT INSERT OR REPLACE. The old version replaced the
    whole row on every harvest, which blanked the areas that tools/ni_classify.py
    derives from Hansard -- and a re-appearing empty `areas` would have looked
    exactly like the bug the classifier exists to fix. This function no longer
    touches areas/matched_terms/evidence*/excerpt/item*/amendment_no at all; see
    the ownership comment on the table in src/db.py.
    """
    existing = conn.execute("SELECT doc_id FROM ni_divisions WHERE doc_id = ?",
                            (d.doc_id,)).fetchone()
    conn.execute(
        "INSERT INTO ni_divisions (doc_id, event_id, subject, bill, dated, "
        "kind, watched, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(doc_id) DO UPDATE SET "
        "event_id=excluded.event_id, subject=excluded.subject, "
        "bill=excluded.bill, dated=excluded.dated, kind=excluded.kind, "
        "watched=excluded.watched, last_seen=excluded.last_seen",
        (d.doc_id, d.event_id, d.subject, canonical_name or d.bill,
         d.when.isoformat() if d.when else None, d.kind,
         1 if canonical_name else 0, today, today))
    return existing is None


def main():
    review = "--review" in sys.argv
    days = DEFAULT_DAYS
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    today = datetime.date.today()
    start = today - datetime.timedelta(days=days)

    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    watch = watched_bills()

    # fetch_divisions raises where its looped siblings return (result, error),
    # and this call site did not wrap it -- a single 500 was an uncaught
    # traceback that lost the whole run.
    try:
        divisions = niassembly.fetch_divisions(client, start, today)
    except Exception as exc:                        # noqa: BLE001
        print("could not fetch divisions: {0}: {1}".format(
            type(exc).__name__, exc))
        conn.close()
        return 1
    print("{0} division(s) between {1} and {2}".format(
        len(divisions), start.isoformat(), today.isoformat()))

    by_bill = collections.defaultdict(list)
    for d in divisions:
        by_bill[d.bill].append(d)

    # canonical_bill/is_watched now live in niassembly so they can carry
    # regression tests: this logic decides `watched`, it has broken silently
    # once already (37 divisions -> 35), and a closure cannot be unit-tested.
    def canonical(bill):
        return niassembly.canonical_bill(bill, watch)

    def is_watched(bill):
        return niassembly.is_watched(bill, watch)

    for d in divisions:
        store_division(conn, d, canonical(d.bill), today.isoformat())
    conn.commit()
    # NOT classified here any more. Classifying the subject line yielded 0 of
    # 139 for a year; that is now a recorded fact rather than something
    # re-demonstrated on every run. tools/ni_classify.py owns areas.

    # A watch entry matching nothing is almost always a typo or a renamed
    # bill. Reported loudly: a silently-ignored watch line is a bill you
    # believe you are monitoring and are not.
    unmatched = [name for name in watch
                 if not any(niassembly.bill_matches(b, name) for b in by_bill)]
    if unmatched:
        print("\nWARNING: {0} ni_watch.yaml entr(ies) matched NO division in "
              "this window:".format(len(unmatched)))
        for name in unmatched:
            print("  * {0!r}".format(name))
        print("  Either the bill drew no divisions in the window, or the name "
              "is wrong.\n  Check it against --review output.")
    classified = conn.execute(
        "SELECT COUNT(*) FROM ni_divisions WHERE areas IS NOT NULL "
        "AND areas != '[]'").fetchone()[0]
    print("{0} of {1} stored division(s) carry an issue area."
          .format(classified, len(divisions)))
    if not classified:
        print("  Subjects name an amendment NUMBER, never its content, so none")
        print("  can be classified from the subject. Run tools/ni_classify.py,")
        print("  which reads the amendment's own wording from Hansard.")

    # -- review mode --------------------------------------------------------
    if review:
        print("\nCANDIDATE BILLS, most-divided first. Add the ones that matter")
        print("to config/ni_watch.yaml with a `why` line.\n")
        for bill, ds in sorted(by_bill.items(), key=lambda kv: -len(kv[1])):
            if len(ds) < 2 and not is_watched(bill):
                continue
            mark = "WATCHED" if is_watched(bill) else "       "
            cross = sum(1 for d in ds if d.cross_community)
            print("  {0} {1:>3} div  {2}".format(mark, len(ds), bill[:52]))
            if cross:
                print("              {0} cross-community (needs a majority in "
                      "BOTH designations)".format(cross))
        singles = sum(1 for ds in by_bill.values() if len(ds) == 1)
        print("\n  {0} bill(s)/motion(s) drew a single division and are not "
              "listed above.".format(singles))

        # The feedback loop, and the reason classifying every division matters
        # rather than only the watched ones: a bill the watch list never named
        # can only surface here.
        unwatched = [r for r in conn.execute(
            "SELECT item_name, bill, dated, areas, excerpt, amendment_no "
            "FROM ni_divisions WHERE watched = 0 AND areas IS NOT NULL "
            "AND areas != '[]' ORDER BY dated DESC")]
        print("\nCLASSIFIED BUT NOT WATCHED -- no member votes are held for "
              "these.\n")
        if not unwatched:
            print("  none. Every division carrying an issue area is on a bill "
                  "already\n  listed in config/ni_watch.yaml.")
        for r in unwatched:
            print("  {0}  areas {1}".format(
                r["dated"] or "undated",
                ",".join(str(a) for a in json.loads(r["areas"] or "[]"))))
            print("      {0}".format((r["item_name"] or r["bill"] or "?")[:66]))
            if r["excerpt"]:
                print("      {0}".format(r["excerpt"][:66]))
        print("\n  Nothing was fetched per-member: --review costs one request.")
        print("  Areas come from tools/ni_classify.py; run it if they look stale.")
        conn.close()
        return 0

    # -- harvest watched bills ---------------------------------------------
    targets = [d for d in divisions if is_watched(d.bill)]
    if not watch:
        print("\nconfig/ni_watch.yaml lists no bills. Run --review first.")
        conn.close()
        return 0
    print("\nHarvesting member votes for {0} division(s) across {1} watched "
          "bill(s).".format(len(targets), len(watch)))

    gaps, rows = [], 0
    for d in targets:
        votes, err = niassembly.fetch_member_voting(client, d.doc_id)
        if err:
            gaps.append("division {0} ({1}): {2}".format(d.doc_id, d.bill, err))
            continue
        if not votes:
            gaps.append("division {0} ({1}): no member rows returned"
                        .format(d.doc_id, d.bill))
            continue
        for v in votes:
            conn.execute(
                "INSERT OR REPLACE INTO ni_votes (doc_id, person_id, member, "
                "vote, designation, captured_at) VALUES (?,?,?,?,?,?)",
                (v.doc_id or d.doc_id, v.person_id, v.member, v.vote,
                 v.designation, today.isoformat()))
            rows += 1
    # Party as at the DIVISION date, for the same reason questions need it: a
    # vote belongs to the party the member held when they cast it.
    vdates = {d.when.isoformat() for d in targets if d.when}
    fetched, aff_gaps = ni_store.resolve_dates(
        conn, client, vdates, today.isoformat(), niassembly.fetch_members_at)
    gaps.extend(aff_gaps)

    # Archive Hansard for EVERY division date, not just watched ones: the whole
    # point of classifying is to surface bills the watch list missed, which is
    # impossible if only watched dates are fetched. One request per date, ever.
    all_dates = {d.when.isoformat() for d in divisions if d.when}
    sat, sit_gaps = ni_store.resolve_sittings(
        conn, client, all_dates, today.isoformat(), ni_hansard.fetch_sitting)
    gaps.extend(sit_gaps)
    print("hansard archived for {0} new sitting(s); {1} held in total."
          .format(sat, len(ni_store.sittings_present(conn))))
    conn.commit()
    print("{0} member position(s) stored.".format(rows))
    print("party resolved for {0} new division date(s); {1} held in total."
          .format(fetched, len(ni_store.dates_present(conn))))
    if gaps:
        print("\n{0} gap(s) -- printed, never swallowed:".format(len(gaps)))
        for g in gaps:
            print("  * {0}".format(g))
    else:
        print("no gaps.")
    print("\nRead it with: python3 tools/ni_monitor.py")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
