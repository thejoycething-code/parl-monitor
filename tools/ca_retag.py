#!/usr/bin/env python3
"""Re-apply the taxonomy and watchlist-ca to the stored Canadian rows -- ADDING
areas, never removing.

    python3 tools/ca_retag.py --dry-run     # what would change
    python3 tools/ca_retag.py               # apply

Written 29 September 2026 for taxonomy v1.10 ("Marriage (Same Sex Couples)",
area 9). The Canadian store had been tagged across v1.8-v1.10 and two
watchlist-ca edits, and a term reaches only rows collected after it joined
unless something goes back over the ones already held.

ADDITIVE ONLY, like tools/de_retag.py and for the same reason. Each row is
re-matched from the SAME inputs its collector used, where the store still
holds them:
  * a Commons division from its subject (ca_rollcalls.classify);
  * a Senate division from its title AND its bill's long title (ca_senate);
  * a bill from its long and short titles;
  * a petition from its category + keywords and its prayer (ca_petitions);
  * a speech from its full text, per passage, with its subject as a title
    passage (ca_hansard) -- for a Senate floor speech the subject plus its
    bill's long title, joined on its sitting's session (ca_senate_debates,
    ca_store.speech_title); a committee speech's subject is its meeting's
    study titles (ca_committees);
  * committee testimony the same way (ca_committees);
  * a Gazette item from its stored text per passage (a notice, a PDF item);
    a notice matched on its title alone, from its title and department; a
    regulation whose body lives at its URL, from its excerpt -- part of the
    body, so a match there is a match on the body, but the excerpt cannot
    reproduce every tag the body earned (the trust check reports it);
  * a Supreme Court judgment from its subjects and stored headnote, with its
    case name as a title passage; a leave decision from the Registrar's
    summary, likewise (ca_courts). Both keep their full inputs, so both are
    gated.
A match on those is a match on what the collector read, so adding is safe;
re-deriving and writing back would drop any tag earned from text the store
no longer keeps. ca_rollcalls.reclassify is NOT this: it re-derives every
division from its subject alone, which would strip a Senate vote's tags
that came from its bill's long title.

WHAT THIS CANNOT DO. A Hansard speech is stored only if it matched when its
sitting was read, so a speech that matches ONLY under a new term was never
kept, and no retag can find it; that needs the sitting re-read. The same
holds for any term narrowed or dropped: the rows it tagged need re-reading.

Rows that gain their first area on our ground: a division is still
positions_fetched=0, so the next ordinary run fetches its members'
positions; a petition becomes pending for tools/ca_triage.py.

ONE WRITER AT A TIME on the store: this runs in CI (ca-weekly's `retag`).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, filter as filt  # noqa: E402

TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
WATCHLIST = os.path.join(ROOT, "config", "watchlist-ca.yaml")


def _item(res):
    """(areas, terms, tier) from a filter_item result."""
    return (set(res.issue_areas or []),
            list(res.matched_terms or []) + list(res.watchlist_hits or []), res.tier)


def _passages(tax, wl, text, title):
    matches = filt.match_passages(tax, wl, text or "", title=title)
    areas, terms, _ = filt.aggregate_passages(matches)
    tier = 1 if any(m.result.tier == 1 for m in matches) else 2 if matches else None
    return set(areas or []), list(terms or []), tier


def _rows(conn, tax, wl):
    """Yield (table, key column, key, stored areas, stored terms, stored tier,
    (areas, terms, tier) re-derived)."""
    titles = {(r[0], r[1], r[2]): r[3] for r in conn.execute(
        "SELECT parliament, session, number, long_title FROM ca_bills")}
    for r in conn.execute("SELECT division_key, chamber, parliament, session, subject, "
                          "bill_number, areas, matched_terms, tier FROM ca_divisions"):
        fields = [r[4] or ""]
        if r[1] == "senate":
            fields.append(titles.get((r[2], r[3], r[5])) or "")
        yield ("ca_divisions", "division_key", r[0], r[6], r[7], r[8],
               _item(filt.filter_item(tax, wl, *fields)))
    for r in conn.execute("SELECT bill_key, long_title, short_title, areas, matched_terms, "
                          "tier FROM ca_bills"):
        yield ("ca_bills", "bill_key", r[0], r[3], r[4], r[5],
               _item(filt.filter_item(tax, wl, r[1] or "", r[2] or "")))
    for r in conn.execute("SELECT petition_id, category, keywords, prayer, areas, "
                          "matched_terms, tier FROM ca_petitions"):
        head = " ".join([r[1] or ""] + json.loads(r[2] or "[]"))
        yield ("ca_petitions", "petition_id", r[0], r[4], r[5], r[6],
               _item(filt.filter_item(tax, wl, head, r[3] or "")))
    # A Senate floor speech was matched with its bill's long title in the
    # title passage (tools/ca_senate_debates.py), joined on the session its
    # sitting belongs to; re-reading it from the subject alone would fail the
    # trust check on every speech whose tags came from that title.
    for r in conn.execute("SELECT s.speech_id, s.text, s.subject, s.areas, s.matched_terms, "
                          "s.chamber, s.bill_number, ss.parliament, ss.session "
                          "FROM ca_speeches s LEFT JOIN ca_senate_sittings ss "
                          "ON ss.sitting_key = s.sitting_key"):
        title = r[2]
        if r[5] == "senate" and r[7] is not None:
            title = ca_store.speech_title(r[2], r[6], titles.get((r[7], r[8], r[6])))
        yield ("ca_speeches", "speech_id", r[0], r[3], r[4], None,
               _passages(tax, wl, r[1], title))
    # Committee testimony is matched exactly as a committee speech: its full
    # text per passage, the meeting's study titles (stored as subject) as the
    # title passage (tools/ca_committees.py).
    for r in conn.execute("SELECT testimony_id, text, subject, areas, matched_terms "
                          "FROM ca_testimony"):
        yield ("ca_testimony", "testimony_id", r[0], r[3], r[4], None,
               _passages(tax, wl, r[1], r[2]))
    for r in conn.execute("SELECT item_key, text, excerpt, title, areas, matched_terms, "
                          "tier, matched_on, department FROM ca_gazette_items"):
        # A notice whose anchor was missing was matched on its title and
        # department (ca_gazette.read_issue), so it is re-matched the same way.
        again = (_item(filt.filter_item(tax, wl, r[3] or "", r[8] or ""))
                 if r[7] == "title" else _passages(tax, wl, r[1] or r[2], r[3]))
        yield ("ca_gazette_items", "item_key", r[0], r[4], r[5], r[6], again)
    # Supreme Court judgments from their subjects and headnote, with the case
    # name as a title passage (ca_courts.classify_judgment); a Federal Court
    # row was matched on reasons the store does not keep, so it is left out.
    for r in conn.execute("SELECT judgment_id, title, subjects, headnote, areas, matched_terms, "
                          "tier FROM ca_judgments WHERE court = 'SCC'"):
        text = "\n".join(json.loads(r[2] or "[]") + [r[3] or ""])
        yield ("ca_judgments", "judgment_id", r[0], r[4], r[5], r[6],
               _passages(tax, wl, text, r[1]))
    # Leave decisions from the Registrar's summary with the case name as a
    # title passage (ca_courts.classify_leave).
    for r in conn.execute("SELECT docket, title, summary, areas, matched_terms, tier "
                          "FROM ca_leave"):
        yield ("ca_leave", "docket", r[0], r[3], r[4], r[5], _passages(tax, wl, r[2], r[1]))


# THE TRUST CHECK (29 September 2026). Re-matching a row from its stored
# inputs should reproduce the areas it already holds; if it does not, the
# retag is not reading what the collector read, and whatever it would add is
# suspect too. The EU retag that day passed on the Mac and was refused in CI
# for exactly this (a raw-archive lookup that missed on case). For the tables
# whose full inputs are in the store the floor is 99%; a Gazette regulation is
# re-read from its excerpt, not its body, so that table is reported, not
# gated.
TRUST_FLOOR = 0.99
GATED = ("ca_divisions", "ca_bills", "ca_petitions", "ca_speeches", "ca_testimony",
         "ca_judgments", "ca_leave")
UNTIERED = ("ca_speeches", "ca_testimony")    # no tier column


class Untrusted(RuntimeError):
    pass


def retag(conn, tax, wl, dry_run=False, log=print, floor=TRUST_FLOOR):
    """-> [(table, key, added areas, terms)] for every row that would grow.
    Raises Untrusted, writing nothing, if a gated table's stored areas are
    reproduced for fewer than TRUST_FLOOR of its tagged rows."""
    rows = list(_rows(conn, tax, wl))
    held, kept = {}, {}
    for table, _, _, areas, _, _, (new, _, _) in rows:
        stored = set(json.loads(areas or "[]"))
        if stored:
            held[table] = held.get(table, 0) + 1
            kept[table] = kept.get(table, 0) + (stored <= new)
    low = []
    for table in sorted(held):
        share = kept[table] / float(held[table])
        log("  trust {0:<17} {1}/{2} tagged rows reproduced ({3:.1%}){4}".format(
            table, kept[table], held[table], share,
            "" if table in GATED else " -- reported, not gated"))
        if table in GATED and share < floor:
            low.append(table)
    if low:
        raise Untrusted("reproduction under {0:.0%} in {1}: not reading what the collector "
                        "read, nothing written".format(floor, ", ".join(low)))
    changes = []
    for table, keycol, key, areas, terms, tier, (new, new_terms, new_tier) in rows:
        stored = set(json.loads(areas or "[]"))
        added = new - stored
        if not added:
            continue
        changes.append((table, key, sorted(added), new_terms))
        if dry_run:
            continue
        merged_terms = sorted(set(json.loads(terms or "[]")) | set(new_terms))
        sets = ["areas = ?", "matched_terms = ?"]
        args = [json.dumps(sorted(stored | added)), json.dumps(merged_terms, ensure_ascii=False)]
        if table not in UNTIERED:
            # Tier 1 outranks tier 2; a tier only ever improves here.
            best = min(t for t in (tier, new_tier) if t is not None) if (tier or new_tier) else None
            sets.append("tier = ?")
            args.append(best)
        conn.execute("UPDATE {0} SET {1} WHERE {2} = ?".format(table, ", ".join(sets), keycol),
                     args + [key])
    if not dry_run:
        conn.commit()
    return changes


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    conn = ca_store.ensure_schema(db.init_db(db.connect(args.db)))
    tax = filt.load_taxonomy(TAXONOMY)
    wl = filt.load_watchlist(WATCHLIST)
    try:
        changes = retag(conn, tax, wl, dry_run=args.dry_run)
    except Untrusted as exc:
        print("ca-retag: REFUSED -- {0}".format(exc))
        conn.close()
        return 1
    by_table = {}
    for table, key, added, terms in changes:
        by_table[table] = by_table.get(table, 0) + 1
        print("  {0:<17} {1:<32} +area {2}  via {3}".format(
            table, str(key)[-32:], added, ", ".join(terms[:2])))
    # The YAML's `version: 1.10` loads as the float 1.1; read it as written.
    with open(TAXONOMY) as fh:
        version = next((l.split(":", 1)[1].strip() for l in fh if l.startswith("version:")),
                       tax.version)
    print("ca-retag: {0} row(s) gain an area under taxonomy v{1}{2}; none lose one{3}".format(
        len(changes), version,
        " ({0})".format(", ".join("{0} {1}".format(n, t) for t, n in sorted(by_table.items())))
        if by_table else "", " (dry run)" if args.dry_run else ""))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
