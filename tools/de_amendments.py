#!/usr/bin/env python3
"""Amendments moved to bills we are watching.

    python3 tools/de_amendments.py
    python3 tools/de_amendments.py --since 2025-01-01 --dry-run

Christopher, 23 September 2026: build amendments. Westminster tracks
amendments to watched Bills; Germany tracked none, so a bill could be
rewritten in second reading and the monitor would show only that it had
"moved".

HOW THEY ARE FOUND, after two dead ends. "Änderungsantrag" is NOT a
Vorgangstyp -- that query returns zero. Searching Drucksache TITLES for the
word returned one document for the whole of 2025. The seam is
f.drucksachetyp=Änderungsantrag, which returns 32 since March 2025, each
carrying a `vorgangsbezug`: the Vorgang it amends, by id and title.

AN AMENDMENT IS ADMITTED BY ITS PARENT, NOT ITS OWN WORDS, and this is the
whole design. An Änderungsantrag's title is procedure --

    "zu der zweiten Beratung des Gesetzentwurfs der Bundesregierung
     - Drucksachen 21/6130, 21/6559, 21/7016 - Entwurf eines ..."

-- so matching it against the taxonomy finds nothing, every week, and a
section that is always empty reads as a quiet Parliament rather than a broken
filter. The vorgangsbezug is the join: an amendment to a bill already on our
board is on our ground whatever its own title says. That is the same
inheritance the roll calls use for terse division labels, and when it fires
the row records `inherited = 1` so a reader knows the classification is
second-hand.

An amendment whose own title DOES match is taken on its own terms too -- both
routes are live, and the two are distinguished rather than merged.

ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, dip, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

LOOKBACK_DAYS = 365
DRUCKSACHETYP = "Änderungsantrag"


def paper_url(number):
    """dserver's PDF path for a Drucksache.

    Shared with tools/de_committees.py, which established the rule against
    the live server: the number pads to FIVE digits, the directory is its
    first three. The construction here before that was checked produced
    /btd/21/816/218164.pdf for 21/8164, which 404s -- every amendment link
    written on 23 September was dead.
    """
    m = re.fullmatch(r"(\d{1,2})/(\d{1,6})", number or "")
    if not m:
        return None
    wp, num = m.group(1), m.group(2).zfill(5)
    return "https://dserver.bundestag.de/btd/{0}/{1}/{0}{2}.pdf".format(
        wp, num[:3], num)


def urheber_of(doc):
    """Who moved it, as DIP gives it. Never inferred."""
    names = []
    for u in doc.get("urheber") or []:
        label = u.get("titel") or u.get("bezeichnung")
        if label:
            names.append(label)
    return "; ".join(names) or None


def parents(doc):
    """[(vorgang_id, titel)] this amendment attaches to."""
    return [(str(v.get("id")), v.get("titel"))
            for v in (doc.get("vorgangsbezug") or []) if v.get("id")]


def ours(conn, vorgang_id):
    """The parent's areas, if we hold it and it is on our ground."""
    row = conn.execute("SELECT areas FROM de_vorgaenge WHERE vorgang_id = ?",
                       (vorgang_id,)).fetchone()
    if not row:
        return []
    try:
        return json.loads(row[0] or "[]")
    except (TypeError, ValueError):
        return []


def pull(conn, client, key, today, tax, wl, since, log=print, dry_run=False):
    seen = new = own = inherited = 0
    # The join's own denominator. Without it, "0 on our ground"
    # cannot be told from "the parent lookup is broken" -- and the
    # first live run legitimately returned zero, which is exactly
    # when a silent join failure would have been believed.
    parents_seen, parents_held = set(), set()
    try:
        pages = list(dip.pages(client, "drucksache", key, feed="de-amendments",
                               slug="aenderung", log=log,
                               **{"f.drucksachetyp": DRUCKSACHETYP,
                                  "f.datum.start": since}))
    except (FetchError, ValueError) as exc:
        log("  [gap] de-amendments: unreadable ({0})".format(str(exc)[:80]))
        db.record_gap(conn, "de-amendments",
                      "amendment sweep unreadable: {0}".format(str(exc)[:110]),
                      today)
        return 0, 0, 0, 0, 0, 0
    for reply in pages:
        for doc in reply.get("documents") or []:
            number = doc.get("dokumentnummer")
            if not number:
                continue
            seen += 1
            titel = " ".join((doc.get("titel") or "").split())
            res = filt.filter_item(tax, wl, titel)
            areas = list(res.issue_areas or [])
            terms = list(res.matched_terms or [])
            from_parent = False
            parent_id = parent_titel = None
            for pid, ptitel in parents(doc):
                parent_id, parent_titel = pid, ptitel
                parents_seen.add(pid)
                if conn.execute("SELECT 1 FROM de_vorgaenge WHERE vorgang_id "
                                "= ?", (pid,)).fetchone():
                    parents_held.add(pid)
                if not areas:
                    got = ours(conn, pid)
                    if got:
                        areas, from_parent = got, True
                break           # the first bezug is the bill it amends
            if areas:
                if from_parent:
                    inherited += 1
                else:
                    own += 1
                log("  [amendment] {0} {1}{2}: {3}".format(
                    number, areas, " (from parent)" if from_parent else "",
                    (parent_titel or titel)[:56]))
            if dry_run:
                continue
            doc_id = "drucksache:" + number
            if not conn.execute("SELECT 1 FROM de_amendments WHERE doc_id = ?",
                                (doc_id,)).fetchone():
                new += 1
            conn.execute(
                "INSERT INTO de_amendments (doc_id, datum, titel, urheber, "
                "vorgang_id, vorgang_titel, inherited, url, areas, "
                "matched_terms, tier, first_seen, last_seen) VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(doc_id) DO UPDATE SET "
                "titel=excluded.titel, urheber=excluded.urheber, "
                "vorgang_id=excluded.vorgang_id, "
                "vorgang_titel=excluded.vorgang_titel, "
                "inherited=excluded.inherited, areas=excluded.areas, "
                "matched_terms=excluded.matched_terms, tier=excluded.tier, "
                "last_seen=excluded.last_seen",
                (doc_id, (doc.get("datum") or "")[:10], titel,
                 urheber_of(doc), parent_id, parent_titel,
                 1 if from_parent else 0,
                 paper_url(number),
                 json.dumps(sorted(set(areas))),
                 json.dumps(sorted(set(terms))), res.tier, today, today))
    if not dry_run:
        conn.commit()
    return seen, new, own, inherited, len(parents_seen), len(parents_held)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", help="ISO date; default {0} days back".format(
        LOOKBACK_DAYS))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    since = args.since or (datetime.date.today()
                           - datetime.timedelta(days=LOOKBACK_DAYS)).isoformat()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    today = datetime.date.today().isoformat()
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy-de.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist-de.yaml"))
    key = dip.api_key(client=client)

    seen, new, own, inherited, p_seen, p_held = pull(
        conn, client, key, today, tax, wl, since, dry_run=args.dry_run)
    print("de-amendments: {0} amendment(s) since {1}, {2} new, {3} matched on "
          "their own title, {4} admitted through the bill they amend. They "
          "amend {5} distinct bill(s), of which we hold {6} -- so a zero "
          "above means no overlap, not a broken join{7}."
          .format(seen, since, new, own, inherited, p_seen, p_held,
                  " (dry run)" if args.dry_run else ""))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
