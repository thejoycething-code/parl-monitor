#!/usr/bin/env python3
"""Bundestag namentliche Abstimmungen, with every member's position.

    python3 tools/de_rollcalls.py                  # the current legislature
    python3 tools/de_rollcalls.py --legislature 132
    python3 tools/de_rollcalls.py --dry-run

Source: abgeordnetenwatch.de's open API (no key). One call lists the
legislature's recorded votes; one call per NEW vote returns all ~630 member
positions with the member's Fraktion, so a completed vote is never refetched.

NOTHING IS CLASSIFIED HERE. config/taxonomy.yaml is English and matched one
useful vote in sixty-eight when it was run over this House (22 September
2026, docs/germany-scope.md), so every recorded vote is stored and the API's
own German topic labels are kept verbatim. Filtering with a blind taxonomy
would discard the lot and report success. Areas arrive with the German term
layer, phase 2.

Volume is small on purpose: 68 votes in the current legislature, 162 in the
last. Storing all of them costs less than deciding badly which to keep.

Separation guarantee: writes de_members, de_divisions and de_votes only.
ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

API = "https://www.abgeordnetenwatch.de/api/v2"
BUNDESTAG = 5
PERIODS = (API + "/parliament-periods?parliament={0}&type=legislature"
                 "&sort_by=start_date_period&sort_direction=desc&range_end=4")
POLLS = API + "/polls?field_legislature={0}&range_end=999"
POLL = API + "/polls/{0}?related_data=votes"

# The Drucksache the House voted on lives in the intro's HTML, as the first
# dserver/dip link. Phase 3 reads its text the way src/eudoc.py reads an
# adopted text; phase 1 only records where it is.
DOC_LINK = re.compile(r'href="(https?://(?:dserver|dip)\.bundestag\.de/[^"]+)"')


def current_legislature(client):
    """(id, label) of the newest Bundestag legislature."""
    reply = client.get_json(PERIODS.format(BUNDESTAG), "de-rollcalls",
                            "periods", archive=False)
    rows = (reply or {}).get("data") or []
    if not rows:
        raise ValueError("no Bundestag legislature returned")
    return str(rows[0]["id"]), rows[0].get("label") or ""


def document_url(intro):
    hit = DOC_LINK.search(intro or "")
    return hit.group(1) if hit else None


def tally(votes):
    """{'yes': n, ...} counted from the member rows, not from any summary."""
    out = {"yes": 0, "no": 0, "abstain": 0, "no_show": 0}
    for v in votes:
        pos = v.get("vote")
        if pos in out:
            out[pos] += 1
    return out


def pull(conn, client, today, legislature=None, log=print, limit=None):
    """Store every recorded vote of one legislature. Returns (seen, new, gaps)."""
    if legislature is None:
        legislature, label = current_legislature(client)
        log("de-rollcalls: legislature {0} ({1})".format(legislature, label))
    reply = client.get_json(POLLS.format(legislature), "de-rollcalls",
                            "polls-{0}".format(legislature), archive=False)
    polls = (reply or {}).get("data") or []
    known = {r[0] for r in conn.execute("SELECT vote_id FROM de_divisions")}
    seen = new = gaps = 0
    for p in polls:
        seen += 1
        vote_id = str(p.get("id"))
        if vote_id in known:
            continue
        if limit is not None and new >= limit:
            log("  fetch cap ({0}) reached; the rest lands on the next run "
                "-- disclosed, not silent".format(limit))
            break
        try:
            detail = client.get_json(POLL.format(vote_id), "de-rollcalls",
                                     "poll-" + vote_id, archive=False)
        except (FetchError, ValueError) as exc:
            conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) "
                         "VALUES (?,?,?)", (today, "de-rollcalls",
                                            "{0}: {1}".format(vote_id, exc)))
            log("  [gap] poll {0}: {1}".format(vote_id, str(exc)[:70]))
            gaps += 1
            continue
        d = (detail or {}).get("data") or {}
        votes = (d.get("related_data") or {}).get("votes") or []
        counts = tally(votes)
        accepted = d.get("field_accepted")
        conn.execute(
            "INSERT INTO de_divisions (vote_id, legislature, date, label, "
            "yes, no, abstain, absent, accepted, committee, topics, "
            "document_url, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(vote_id) DO UPDATE SET label=excluded.label, "
            "yes=excluded.yes, no=excluded.no, abstain=excluded.abstain, "
            "absent=excluded.absent, accepted=excluded.accepted, "
            "last_seen=excluded.last_seen",
            (vote_id, str(legislature), d.get("field_poll_date"),
             d.get("label"), counts["yes"], counts["no"], counts["abstain"],
             counts["no_show"],
             None if accepted is None else int(bool(accepted)),
             ((d.get("field_committees") or [{}])[0] or {}).get("label"),
             json.dumps([t.get("label") for t in (d.get("field_topics") or [])],
                        ensure_ascii=False),
             document_url(d.get("field_intro")), today, today))
        for v in votes:
            mandate = v.get("mandate") or {}
            person = str(mandate.get("id") or "")
            if not person:
                continue
            fraction = (v.get("fraction") or {}).get("label")
            conn.execute(
                "INSERT INTO de_members (person_id, name, party, legislature, "
                "first_seen, last_seen) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(person_id) DO UPDATE SET name=excluded.name, "
                "party=excluded.party, last_seen=excluded.last_seen",
                (person, mandate.get("label"), fraction, str(legislature),
                 today, today))
            conn.execute(
                "INSERT OR REPLACE INTO de_votes (vote_id, person_id, position) "
                "VALUES (?,?,?)", (vote_id, person, v.get("vote")))
        new += 1
    conn.commit()
    return seen, new, gaps


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--legislature", help="abgeordnetenwatch legislature id")
    ap.add_argument("--limit", type=int, help="stop after this many NEW votes")
    ap.add_argument("--dry-run", action="store_true",
                    help="list the legislature and its vote count, store nothing")
    args = ap.parse_args()
    import datetime
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    today = datetime.date.today().isoformat()
    if args.dry_run:
        leg, label = (args.legislature, "") if args.legislature else current_legislature(client)
        polls = (client.get_json(POLLS.format(leg), "de-rollcalls",
                                 "polls-{0}".format(leg), archive=False) or {}).get("data") or []
        print("de-rollcalls: legislature {0} {1}, {2} recorded vote(s)".format(leg, label, len(polls)))
        return 0
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    seen, new, gaps = pull(conn, client, today, legislature=args.legislature,
                           limit=args.limit)
    print("de-rollcalls: {0} recorded vote(s) listed, {1} new, {2} gap(s).".format(
        seen, new, gaps))
    members = conn.execute("SELECT COUNT(*) FROM de_members").fetchone()[0]
    rows = conn.execute("SELECT COUNT(*) FROM de_votes").fetchone()[0]
    print("  {0} member(s), {1} recorded position(s) held.".format(members, rows))
    print("  NOT classified: the taxonomy is English (docs/germany-scope.md).")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
