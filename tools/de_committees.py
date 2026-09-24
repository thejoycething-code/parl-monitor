#!/usr/bin/env python3
"""What Bundestag committees are recommending, and what is laid before them.

    python3 tools/de_committees.py
    python3 tools/de_committees.py --since 2026-01-01 --dry-run

Christopher, 24 September 2026: "Build the committee reports collector." It
was the last section Westminster had and Germany did not, and it covers the
most actionable moment in a bill's life -- a Beschlussempfehlung is the
committee telling the House what to do with a bill, published BEFORE the vote
rather than reporting it afterwards.

FOUR DIP DOCUMENT TYPES, measured 24 September 2026 over four months:

    Beschlussempfehlung und Bericht    98   recommendation with reasons
    Beschlussempfehlung                51   recommendation alone
    Bericht                            12   a committee's own report
    Unterrichtung                     181   laid before the House by someone
                                            else -- the Government, the EU
                                            Commission, an oversight body

The first three are the committee speaking; Unterrichtung is the nearest
German thing to Westminster's "Government responses", so both halves of that
section have an equivalent here.

CLASSIFIED ON ITS OWN TITLE FIRST, which is the opposite of how
tools/de_amendments.py works and the difference is real. An Änderungsantrag's
title is pure procedure, but a committee report's names the bill:

    "zu dem Gesetzentwurf der Bundesregierung - Drucksachen 21/4500, 21/4784
     - Entwurf eines Ersten Gesetzes zur Änderung des
       Wissenschaftsfreiheitsgesetzes"

So the taxonomy has something to bite on. The parent Vorgang is still used as
a fallback, and a row records `inherited = 1` when that is where its areas
came from.

THE NEWEST DOCUMENTS ARRIVE INCOMPLETE, and this is the trap. Of 128 reports
sampled, 123 carried the committee and 123 the parent Vorgang -- but the two
most recent, published that morning, carried NEITHER. DIP enriches them
later. A collector that wrote once and skipped what it had seen would leave
every report permanently committee-less, because the week it is first seen is
exactly the week those fields are missing. So the upsert UPDATES committee,
parent and areas on conflict, and the weekly window deliberately reaches back
far enough to re-see recent documents.

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

# Far enough back to re-see documents published in the last few weeks, so the
# committee and parent that DIP adds late are picked up on a later sweep.
LOOKBACK_DAYS = 60

COMMITTEE_TYPES = ("Beschlussempfehlung und Bericht", "Beschlussempfehlung",
                   "Bericht")
NOTIFICATION_TYPES = ("Unterrichtung",)
TYPES = COMMITTEE_TYPES + NOTIFICATION_TYPES

# "Drucksachen 21/4500, 21/4784" or "Drucksache 21/6498". The en dash form
# ("– 21/6561 –") appears too, so the numbers are taken wherever they sit.
PARENTS = re.compile(r"\b(\d{1,2}/\d{1,6})\b")


def kind_of(drucksachetyp):
    return ("committee report" if drucksachetyp in COMMITTEE_TYPES
            else "notification")


def body_of(doc):
    """The committee, or whoever laid the paper. Never inferred."""
    for u in doc.get("urheber") or []:
        label = u.get("titel") or u.get("bezeichnung")
        if label:
            return label
    return None


def parents_in_title(titel, own_number):
    """The papers this one reports on, from its title.

    The document's OWN number is excluded: a title often repeats it, and a
    report listed as its own parent would make the board look circular.
    """
    found = [n for n in PARENTS.findall(titel or "") if n != own_number]
    seen, out = set(), []
    for n in found:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def parent_vorgang(doc):
    """(id, titel) of the Vorgang this reports on, when DIP has linked it."""
    for v in doc.get("vorgangsbezug") or []:
        if v.get("id"):
            return str(v["id"]), v.get("titel")
    return None, None


def inherit(conn, vorgang_id):
    if not vorgang_id:
        return []
    row = conn.execute("SELECT areas FROM de_vorgaenge WHERE vorgang_id = ?",
                       (vorgang_id,)).fetchone()
    if not row:
        return []
    try:
        return json.loads(row[0] or "[]")
    except (TypeError, ValueError):
        return []


def paper_url(number):
    """dserver's PDF path, for Bundestag-numbered papers only.

    An Unterrichtung can carry Bundesrat numbering ('542/26', 'zu542/26'),
    which does not live under /btd/ at all -- so no URL is invented for it.
    """
    m = re.fullmatch(r"(\d{1,2})/(\d{1,6})", number or "")
    if not m:
        return None
    wp, num = m.group(1), m.group(2).zfill(5)
    # VERIFIED against dserver on five papers including the edge case 21/1:
    # the number pads to FIVE digits, the directory is its first three, and
    # the filename is the Wahlperiode followed by the padded number.
    #   21/8164 -> /btd/21/081/2108164.pdf
    #   21/1    -> /btd/21/000/2100001.pdf
    # Two other paddings were tried first and both 404'd.
    return "https://dserver.bundestag.de/btd/{0}/{1}/{0}{2}.pdf".format(
        wp, num[:3], num)


def pull(conn, client, key, today, tax, wl, since, log=print, dry_run=False):
    seen = new = own = inherited = enriched = 0
    for drucksachetyp in TYPES:
        try:
            pages = dip.pages(client, "drucksache", key, feed="de-committees",
                              slug="rep-" + drucksachetyp[:12], log=log,
                              **{"f.drucksachetyp": drucksachetyp,
                                 "f.datum.start": since})
            for reply in pages:
                for doc in reply.get("documents") or []:
                    number = doc.get("dokumentnummer")
                    if not number:
                        continue
                    seen += 1
                    titel = " ".join((doc.get("titel") or "").split())
                    res = filt.filter_item(tax, wl, titel)
                    areas = list(res.issue_areas or [])
                    from_parent = False
                    vid, vtitel = parent_vorgang(doc)
                    if not areas:
                        got = inherit(conn, vid)
                        if got:
                            areas, from_parent = got, True
                    if areas:
                        own += 0 if from_parent else 1
                        inherited += 1 if from_parent else 0
                        log("  [{0}] {1} {2}{3}: {4}".format(
                            kind_of(drucksachetyp), number, areas,
                            " (from parent)" if from_parent else "",
                            titel[:56]))
                    if dry_run:
                        continue
                    doc_id = "drucksache:" + number
                    before = conn.execute(
                        "SELECT committee FROM de_committee_reports WHERE "
                        "doc_id = ?", (doc_id,)).fetchone()
                    if before is None:
                        new += 1
                    elif before[0] is None and body_of(doc):
                        # The late-arriving field, landing on a later sweep.
                        enriched += 1
                    conn.execute(
                        "INSERT INTO de_committee_reports (doc_id, kind, "
                        "drucksachetyp, datum, titel, committee, vorgang_id, "
                        "vorgang_titel, parent_drucksachen, inherited, url, "
                        "areas, matched_terms, tier, first_seen, last_seen) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(doc_id) DO UPDATE SET "
                        # Every one of these can arrive LATE: DIP publishes
                        # the paper first and enriches it afterwards. Leaving
                        # them out of the conflict branch would freeze the
                        # emptiest version of every report we ever saw first.
                        "titel=excluded.titel, "
                        "committee=COALESCE(excluded.committee, committee), "
                        "vorgang_id=COALESCE(excluded.vorgang_id, vorgang_id), "
                        "vorgang_titel=COALESCE(excluded.vorgang_titel, "
                        "vorgang_titel), "
                        "parent_drucksachen=excluded.parent_drucksachen, "
                        "inherited=excluded.inherited, areas=excluded.areas, "
                        "matched_terms=excluded.matched_terms, "
                        "tier=excluded.tier, last_seen=excluded.last_seen",
                        (doc_id, kind_of(drucksachetyp), drucksachetyp,
                         (doc.get("datum") or "")[:10], titel, body_of(doc),
                         vid, vtitel,
                         json.dumps(parents_in_title(titel, number)),
                         1 if from_parent else 0, paper_url(number),
                         json.dumps(sorted(set(areas))),
                         json.dumps(sorted(set(res.matched_terms or []))),
                         res.tier, today, today))
        except (FetchError, ValueError) as exc:
            log("  [gap] de-committees '{0}': {1}".format(
                drucksachetyp, str(exc)[:70]))
            db.record_gap(conn, "de-committees",
                          "{0} sweep unreadable: {1}".format(
                              drucksachetyp, str(exc)[:100]), today)
    if not dry_run:
        conn.commit()
    return seen, new, own, inherited, enriched


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

    seen, new, own, inherited, enriched = pull(
        conn, client, key, today, tax, wl, since, dry_run=args.dry_run)
    print("de-committees: {0} report(s) and notification(s) since {1}, {2} "
          "new, {3} matched on their own title, {4} through the paper they "
          "report on, {5} gained a committee DIP had not yet published{6}."
          .format(seen, since, new, own, inherited, enriched,
                  " (dry run)" if args.dry_run else ""))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
