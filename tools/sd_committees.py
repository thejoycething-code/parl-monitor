"""Senedd committee scrutiny and the forward look, in one walk.

    python3 tools/sd_committees.py                  # the weekly
    python3 tools/sd_committees.py --committee 985   # just one

Two things from the same pass over ModernGov's committee list:

  1. SCRUTINY. The XMLExport index accepts committee ids (Plenary is
     committee 908, which is why the votes exporter's `committee` param
     worked all along), so each committee's sittings expose the same
     English transcript XML as plenary. MS contributions whose text
     passage-matches the taxonomy land in sd_events with an `sdcc` key
     prefix and a "Committee -- item" heading; classification runs on the
     agenda ITEM, never the committee's own name.
  2. THE FORWARD LOOK. A committee's detail page states its next sitting
     in prose ("will next meet on Thursday 17 September"). The agenda for
     a future sitting is published later, so a forward row carries a date
     and no subject until then -- said, not hidden. The ModernGov calendar
     is useless for this: all three views hold exhibitions only.

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

MAX_INDEX_PAGES = 12    # bounded walk; log when a committee is still paging


def harvest_committee(client, conn, tax, wl, cid, name, now, log):
    """Transcripts for one committee. Returns (sittings, stored, gaps)."""
    sittings = stored = gaps = 0
    page = 1
    while page <= MAX_INDEX_PAGES:
        try:
            found, more = senedd.fetch_vote_index(client, cid, page)
        except FetchError as exc:
            conn.execute("INSERT INTO gaps (edition, feed, detail) "
                         "VALUES (?,?,?)",
                         (now, "sd-committees",
                          "{0} index page {1}: {2}".format(name, page,
                                                           exc.cause)))
            log("  [gap] {0} index page {1}: {2}".format(name, page,
                                                        exc.cause))
            return sittings, stored, gaps + 1
        if not found:
            break
        for sitting in found:
            sittings += 1
            try:
                speeches = senedd.fetch_transcript(client,
                                                   sitting.meeting_id)
            except FetchError as exc:
                conn.execute("INSERT INTO gaps (edition, feed, detail) "
                             "VALUES (?,?,?)",
                             (now, "sd-committees",
                              "{0} meeting {1}: {2}".format(
                                  name, sitting.meeting_id, exc.cause)))
                log("  [gap] {0} meeting {1}: {2}".format(
                    name, sitting.meeting_id, exc.cause))
                gaps += 1
                continue
            for sp in speeches:
                matches = filt.match_passages(tax, wl, sp.text,
                                              title=sp.heading or "")
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
                    ("sdcc{0}".format(sp.key[3:] if sp.key.startswith("sdc")
                                      else sp.key),
                     sp.member_id, sp.member_name, sp.dated,
                     "{0} -- {1}".format(name, sp.heading or "?"),
                     json.dumps(areas), json.dumps(terms), excerpt, now, now))
                stored += 1
        conn.commit()
        if not more:
            break
        page += 1
    else:
        log("  [note] {0} still paging at page {1} -- capped, older "
            "sittings unseen".format(name, MAX_INDEX_PAGES))
    return sittings, stored, gaps


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
        conn.execute("INSERT INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                     (now, "sd-committees",
                      "committee list: {0}".format(exc.cause)))
        conn.commit()
        print("  [gap] committee list unreachable: {0}".format(exc.cause))
        return 1
    if only:
        committees = [c for c in committees if c[0] == only]
    print("{0} committee(s) listed (Plenary and the Youth Parliament are "
          "excluded by design).".format(len(committees)))

    sittings = stored = gaps = forward = 0
    for cid, name in committees:
        # The forward look first: one page, and it is the useful bit even
        # when a committee has no transcripts yet.
        try:
            mid, when = senedd.fetch_next_meeting(client, cid)
        except FetchError as exc:
            print("  [gap] {0} detail page: {1}".format(name, exc.cause))
            mid, when = None, None
            gaps += 1
        if when:
            forward += 1
        res = filt.filter_item(tax, wl, name)
        s, st, g = harvest_committee(client, conn, tax, wl, cid, name, now,
                                    print)
        sittings += s
        stored += st
        gaps += g
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
             json.dumps(res.matched_terms or []), s, now, now))
        conn.commit()
        print("  {0:<62} {1} sitting(s), next {2}".format(
            name[:62], s, when or "not announced"))

    print("\n{0} sitting(s) read across {1} committee(s); {2} passage-matched "
          "event(s) stored in sd_events (sdcc keys) -- ACTIVITY ONLY, never "
          "direction.".format(sittings, len(committees), stored))
    print("{0} committee(s) have announced a next sitting. A future agenda is "
          "published later, so a forward row carries a date and no subject "
          "until then.".format(forward))
    print("no gaps." if not gaps else
          "{0} gap(s) -- printed above.".format(gaps))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
