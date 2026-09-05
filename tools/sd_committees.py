"""Senedd committee scrutiny and the forward look, in one walk.

    python3 tools/sd_committees.py                  # the weekly
    python3 tools/sd_committees.py --committee 985   # just one

RE-SOURCED 2026-08-28. business.senedd.wales -- which held the committee
list, the meeting index and the transcripts -- went behind an Azure WAF that
returns 403 to every non-browser client. Not a UA problem: it refuses the
honest UA, the authorised browser UA and full browser headers alike, from a
laptop and from GitHub's runners, on the host root as well as any page.

Everything is now read from hosts that are open, and the Record is a better
source than what it replaces -- it is the transcript itself, not an agenda
page linking to one:

  1. THE LIST. senedd.wales/committees/ links all 15 committees. Each
     committee's own page carries the ModernGov CommitteeId the store has
     always keyed on, so changing source renumbers nothing.
  2. SCRUTINY. record.senedd.wales indexes committee transcripts through a
     paged JSON endpoint, newest first, and serves each meeting's agenda
     items and contributions with the speaker's name and UID. Contributions
     that passage-match the taxonomy land in sd_events with an `sdcc` key
     prefix and a "Committee -- item" heading; classification runs on the
     agenda ITEM, never the committee's own name.
     Both the verbatim and the interpretation go to the taxonomy: a
     Welsh-language contribution is not less of a receipt.
  3. THE FORWARD LOOK. The same "will next meet on Thursday 17 September"
     prose the blocked detail page carried appears on the committee's
     senedd.wales page, and is read by the same parser. A future agenda is
     published later, so a forward row carries a date and no subject until
     then -- said, not hidden.

Watching brief: writes sd_* tables only, never items/mp_events, so nothing
here reaches the published digest. ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt
from src.http import FetchError, HttpClient
from src.ingest import senedd

MAX_INDEX_PAGES = 12    # bounded walk; log when the index is still paging
RECORD_PAGES = 4        # 8 transcripts a page, newest first: a month of
                        # committee weeks, which a weekly run cannot outrun


def harvest_meeting(conn, tax, wl, name, meeting_id, dated, contributions, now):
    """Store the taxonomy-matching contributions of one meeting."""
    stored = 0
    for c in contributions:
        matches = filt.match_passages(tax, wl, c.text, title=c.heading or "")
        if not matches:
            continue
        areas, terms, excerpt = filt.aggregate_passages(matches)
        if not areas:
            continue
        conn.execute(
            "INSERT INTO sd_events (key, member_id, member_name, "
            "dated, heading, areas, matched_terms, excerpt, "
            "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET areas=excluded.areas, "
            "matched_terms=excluded.matched_terms, "
            "excerpt=excluded.excerpt, heading=excluded.heading, "
            "last_seen=excluded.last_seen",
            ("sdcc{0}-{1}".format(meeting_id, c.key or len(excerpt)),
             c.member_id, c.member_name, dated,
             "{0} -- {1}".format(name, c.heading or "?"),
             json.dumps(areas), json.dumps(terms), excerpt, now, now))
        stored += 1
    return stored


def walk_record(client, conn, tax, wl, now, log, wanted=None):
    """Recent committee transcripts, newest first, from the Record.

    One paged walk for the whole Senedd rather than a walk per committee:
    the index is chronological across all of them, which is also what a
    weekly run wants. Returns (meetings, stored, gaps, per_committee).
    """
    meetings = stored = gaps = 0
    per = {}
    for page in range(1, RECORD_PAGES + 1):
        try:
            found = senedd.fetch_record_index(client, page)
        except FetchError as exc:
            conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                         (now, "sd-committees",
                          "record index page {0}: {1}".format(page, exc.cause)))
            log("  [gap] record index page {0}: {1}".format(page, exc.cause))
            return meetings, stored, gaps + 1, per
        if not found:
            break
        for meeting_id, committee, dated in found:
            if wanted and committee != wanted:
                continue
            meetings += 1
            per[committee] = per.get(committee, 0) + 1
            try:
                _items, contributions = senedd.fetch_record_meeting(
                    client, meeting_id)
            except FetchError as exc:
                conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) "
                             "VALUES (?,?,?)",
                             (now, "sd-committees",
                              "meeting {0}: {1}".format(meeting_id, exc.cause)))
                log("  [gap] meeting {0}: {1}".format(meeting_id, exc.cause))
                gaps += 1
                continue
            stored += harvest_meeting(conn, tax, wl, committee, meeting_id,
                                      dated, contributions, now)
        conn.commit()
    return meetings, stored, gaps, per


def main():
    only = None
    if "--committee" in sys.argv:
        only = sys.argv[sys.argv.index("--committee") + 1]

    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    now = datetime.date.today().isoformat()

    try:
        committees = senedd.fetch_committees(client)
    except FetchError as exc:
        conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                     (now, "sd-committees",
                      "committee list: {0}".format(exc.cause)))
        conn.commit()
        print("  [gap] committee list unreachable: {0}".format(exc.cause))
        # A GAP, NOT A CRASH -- the contract every other collector here
        # keeps. senedd.wales answers this laptop and 403s GitHub's
        # runners (measured 2026-09-05, the Azure WAF that already owns
        # business.senedd.wales now reaching the committee index for
        # datacentre IPs), so exiting 1 turned the Senedd weekly red
        # every week over a source that is merely refusing robots. A
        # weekly red run trains people to ignore the alert, which is the
        # cost this repo already wrote down about paused pipelines.
        #
        # Safe to soften ONLY because the consequence is now watched:
        # sd_committees is a cadence-checked feed in tools/coverage.py,
        # so if the committee data really stops refreshing, the coverage
        # watch says so within eleven days and DMs. The gap is recorded
        # in `gaps` and printed either way.
        return 0
    if only:
        committees = [c for c in committees if c[0] == only]
    print("{0} committee(s) listed from senedd.wales.".format(len(committees)))

    # The scrutiny walk is ONE pass over the Record for the whole Senedd,
    # not a pass per committee: the index is chronological across all of
    # them, which is what a weekly run wants anyway.
    wanted = committees[0][1] if (only and committees) else None
    meetings, stored, gaps, per = walk_record(client, conn, tax, wl, now,
                                              print, wanted)

    forward = 0
    for cid, name, url in committees:
        key = "committee-" + url.rstrip("/").rsplit("/", 1)[-1]
        when = mid = None
        try:
            page = senedd.fetch_committee_page(client, url, key)
            _cid, _name, mid, when = senedd.parse_committee_page(page)
        except FetchError as exc:
            conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) "
                         "VALUES (?,?,?)",
                         (now, "sd-committees",
                          "{0} page: {1}".format(name, exc.cause)))
            print("  [gap] {0} page: {1}".format(name, exc.cause))
            gaps += 1
        if when:
            forward += 1
        res = filt.filter_item(tax, wl, name)
        seen = per.get(name, 0)
        conn.execute(
            "INSERT INTO sd_committees (committee_id, name, next_meeting, "
            "next_meeting_id, areas, matched_terms, meetings_seen, "
            "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(committee_id) DO UPDATE SET name=excluded.name, "
            "next_meeting=excluded.next_meeting, "
            "next_meeting_id=excluded.next_meeting_id, "
            "areas=excluded.areas, matched_terms=excluded.matched_terms, "
            "meetings_seen=excluded.meetings_seen, "
            "last_seen=excluded.last_seen",
            (cid, name, when, mid, json.dumps(res.issue_areas or []),
             json.dumps(res.matched_terms or []), seen, now, now))
        conn.commit()
        print("  {0:<58} {1} transcript(s) read, next {2}".format(
            name[:58], seen, when or "not announced"))

    print("\n{0} meeting(s) read across {1} committee(s); {2} passage-matched "
          "contribution(s) stored in sd_events (sdcc keys) -- ACTIVITY ONLY, "
          "never direction.".format(meetings, len(per), stored))
    print("{0} committee(s) have announced a next sitting. A future agenda is "
          "published later, so a forward row carries a date and no subject "
          "until then.".format(forward))
    print("no gaps." if not gaps else
          "{0} gap(s) -- printed above.".format(gaps))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
