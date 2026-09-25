#!/usr/bin/env python3
"""Who said what in the Bundestag, on our issues.

    python3 tools/de_speeches.py                  # the recent window
    python3 tools/de_speeches.py --since 2026-01-01 --limit 40
    python3 tools/de_speeches.py --dry-run        # parse and count, store nothing

Christopher, 23 September 2026, on Germany's gap against Westminster: build
the speeches layer first. It is the backbone the Westminster ledger rests on
-- stance scoring, debate packs and eventually a 5CA all read from it -- and
Germany had none of it.

THE SOURCE. DIP's plenarprotokoll-text returns the Stenografischer Bericht in
full: 370,000 to 650,000 characters per sitting day, 4,674 protocols in the
corpus. No PDF, no scraping.

HOW A SPEECH IS FOUND. A heading on its own line, then the speech until the
next heading. Three forms, all measured on protocol 21/94:

    Cansin Köktürk (Die Linke):            97 of them      -> member
    Bärbel Bas, Bundesministerin ...:       4              -> minister
    Vizepräsidentin Andrea Lindholz:       96              -> chair

That accounted for 98% of the document's characters, which is the number that
says the parser is not quietly missing half the day.

THE CHAIR IS PARSED AND NOT STORED. Ninety-six of the headings are the
presiding officer calling the next speaker; they are procedural, and storing
them would bury the speeches that matter under the machinery of getting to
them. They are COUNTED, because a parser that silently drops half its matches
is indistinguishable from one that is broken.

ONLY SPEECHES ON OUR GROUND ARE STORED, for the same reason: a hundred
speeches a sitting day across 4,674 protocols is a copy of the Bundestag, not
a monitor. Every protocol read gets a row in de_protocols with its totals
whether or not anything matched, so "nothing on our ground in September" can
always be told apart from "September was never read".

NO VERDICTS. What a member said is recorded; what it means for us is the
judge's score and, ultimately, a human's.

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

LOOKBACK_DAYS = 90
PROTOCOL_LIMIT = 20

# How much of a matched speech is kept. Generous on purpose: src/stance.py
# centres its 1,500-character window on the excerpt INSIDE the full text, and
# it can only do that if the full text is here. A Bundestag speech runs to a
# few thousand characters, so this keeps whole ones.
SPEECH_CAP = 20000

# Words that open a PROCEDURAL heading, never a person. "Tagesordnungspunkt 3
# (Fortsetzung):" has the exact shape of a name with a party in brackets and
# was the one false positive in the probe; left in, every sitting day would
# have produced a speech by a speaker called Tagesordnungspunkt.
# The protocol parser lives in src/de_protocol.py since 2026-09-25, so the
# debate packs can use it too: src never imports from tools, and a second
# copy of this regex would drift from the one measured against 21/94.
from src.de_protocol import (  # noqa: E402,F401
    NOT_A_PERSON, QUESTION_LABEL, SPEAKER, TITLES, clean_name,
    match_key, parse_speeches, role_of)


def resolve_person(conn, name, party, cache={}):    # noqa: B006
    """de_members.person_id for this speaker, or None.

    None is a perfectly good answer and is stored as such. A guessed match
    would put words in the mouth of someone who did not say them, which is
    the one failure this whole file must never produce -- so the rule is
    EXACTLY ONE member or nothing. Two people sharing a name is precisely the
    case where a guess does damage, and a minister who holds no Bundestag
    mandate legitimately resolves to nobody.
    """
    key = match_key(name)
    if not key:
        return None
    if key not in cache:
        rows = conn.execute(
            "SELECT person_id, name FROM de_members WHERE parliament = '5'"
        ).fetchall() if "__all__" not in cache else cache["__all__"]
        if "__all__" not in cache:
            cache["__all__"] = rows
        hit = [r[0] for r in rows if match_key(r[1]) == key]
        cache[key] = hit[0] if len(hit) == 1 else None
    return cache[key]


def reresolve(conn, log=print):
    """Re-run attribution over speeches already stored (--reresolve).

    A fix to the resolver does nothing for rows already written, and this
    collector reads each protocol once, so nothing would ever revisit them.
    """
    rows = conn.execute("SELECT speech_id, speaker, party FROM de_speeches "
                        "WHERE person_id IS NULL").fetchall()
    fixed = 0
    for speech_id, speaker, party in rows:
        # Re-clean first: a speaker stored before the question-time label was
        # understood is carrying a name that can never resolve.
        cleaned = QUESTION_LABEL.sub("", (speaker or "").strip())
        if cleaned != speaker:
            conn.execute("UPDATE de_speeches SET speaker = ? WHERE "
                         "speech_id = ?", (cleaned, speech_id))
        pid = resolve_person(conn, cleaned, party)
        if pid:
            conn.execute("UPDATE de_speeches SET person_id = ? WHERE "
                         "speech_id = ?", (pid, speech_id))
            fixed += 1
    conn.commit()
    log("de-speeches: {0} of {1} unattributed speech(es) now resolve to a "
        "member.".format(fixed, len(rows)))
    return fixed, len(rows)


def protocols(client, key, since, limit, log=print):
    """Sitting-day protocols from DIP, newest first, with their full text.

    PAGED. The endpoint returns TEN per page and carries a cursor, so the
    first draft -- one request, then documents[:limit] -- could never read
    more than ten however high the limit was set, and would have reported
    "read 10" as though that were the whole window. dip.pages() follows the
    cursor and stops when it stops moving, because DIP repeats a spent
    cursor rather than returning an empty page.

    Protocols dated ahead of today come back as stubs with no text: the
    Bundestag publishes the number before the Bericht exists. They are
    skipped by the caller on emptiness, not by date, so a late-published
    Bericht is picked up whenever it lands.
    """
    out = []
    try:
        for reply in dip.pages(client, "plenarprotokoll-text", key,
                               feed="de-speeches",
                               slug="protokolle-" + since, log=log,
                               **{"f.zuordnung": "BT",
                                  "f.datum.start": since}):
            for doc in reply.get("documents") or []:
                if (doc.get("text") or "").strip():
                    out.append(doc)
                if len(out) >= limit:
                    return out
    except (FetchError, ValueError) as exc:
        log("  [gap] de-speeches: protocol list unreadable ({0})".format(
            str(exc)[:80]))
    return out


def store(conn, client, key, today, tax, wl, since, limit, log=print,
          dry_run=False):
    docs = protocols(client, key, since, limit, log=log)
    read = stored = 0
    for doc in docs:
        number = doc.get("dokumentnummer") or ""
        text = doc.get("text") or ""
        if not number or not text.strip():
            continue
        done = conn.execute("SELECT 1 FROM de_protocols WHERE protocol = ?",
                            (number,)).fetchone()
        if done:
            continue            # read once; the Bericht is final
        speeches, skipped = parse_speeches(text)
        members = [s for s in speeches if s[2] != "chair"]
        matched = 0
        for i, (name, party, role, body) in enumerate(speeches):
            if role == "chair" or not body:
                continue
            hits = filt.match_passages(tax, wl, body)
            areas, terms, excerpt = filt.aggregate_passages(hits)
            if not areas:
                continue
            matched += 1
            if dry_run:
                continue
            conn.execute(
                "INSERT INTO de_speeches (speech_id, protocol, wahlperiode, "
                "date, speaker, party, role, person_id, excerpt, text, url, "
                "areas, matched_terms, tier, first_seen, last_seen) VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(speech_id) DO "
                "UPDATE SET areas=excluded.areas, "
                "matched_terms=excluded.matched_terms, "
                "excerpt=excluded.excerpt, text=excluded.text, "
                "last_seen=excluded.last_seen",
                ("protokoll:{0}#{1}".format(number, i), number,
                 doc.get("wahlperiode") and str(doc.get("wahlperiode")),
                 (doc.get("datum") or "")[:10], name, party, role,
                 resolve_person(conn, name, party), (excerpt or "")[:400],
                 body[:SPEECH_CAP],
                 doc.get("fundstelle", {}).get("pdf_url")
                 if isinstance(doc.get("fundstelle"), dict) else None,
                 json.dumps(sorted(set(areas))),
                 json.dumps(sorted(set(terms or []))), 1, today, today))
        read += 1
        stored += matched
        log("  [protokoll] {0} {1}: {2} speech(es), {3} on our ground"
            .format(number, (doc.get("datum") or "")[:10], len(members),
                    matched))
        if not dry_run:
            conn.execute(
                "INSERT INTO de_protocols (protocol, wahlperiode, date, url, "
                "speeches, matched, chars, read_on) VALUES (?,?,?,?,?,?,?,?) "
                "ON CONFLICT(protocol) DO UPDATE SET speeches=excluded.speeches,"
                " matched=excluded.matched, read_on=excluded.read_on",
                (number, doc.get("wahlperiode") and str(doc.get("wahlperiode")),
                 (doc.get("datum") or "")[:10], None, len(members), matched,
                 len(text), today))
    if not dry_run:
        conn.commit()
    return read, stored


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", help="ISO date; default {0} days back".format(
        LOOKBACK_DAYS))
    ap.add_argument("--limit", type=int, default=PROTOCOL_LIMIT,
                    help="protocols to read this run")
    ap.add_argument("--reread", action="store_true",
                    help="forget which protocols have been read, so a change "
                         "to what is extracted can reach the stored rows")
    ap.add_argument("--reresolve", action="store_true",
                    help="re-attribute stored speeches to members, offline")
    ap.add_argument("--dry-run", action="store_true",
                    help="parse and count, store nothing")
    args = ap.parse_args()

    since = args.since or (datetime.date.today()
                           - datetime.timedelta(days=LOOKBACK_DAYS)).isoformat()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    today = datetime.date.today().isoformat()
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy-de.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist-de.yaml"))
    if args.reread:
        # The collector reads each protocol once, so nothing would otherwise
        # revisit them -- the same trap the reclassify and repair passes
        # exist for.
        n = conn.execute("DELETE FROM de_protocols").rowcount
        conn.commit()
        print("de-speeches: forgot {0} protocol(s); the next run re-reads "
              "them.".format(n))
    if args.reresolve:
        reresolve(conn)
        conn.close()
        return 0
    key = dip.api_key(client=client)

    read, stored = store(conn, client, key, today, tax, wl, since, args.limit,
                         dry_run=args.dry_run)
    print("de-speeches: {0} protocol(s) read since {1}, {2} speech(es) on our "
          "ground{3}.".format(read, since, stored,
                              " (dry run, nothing stored)" if args.dry_run
                              else ""))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
