#!/usr/bin/env python3
"""The Northern Ireland Assembly committee register -> ni_committees.

    python3 tools/ni_committees.py

WHY THIS EXISTS. Wales stored 19 committees and Scotland harvests 6,965
committee contributions; Northern Ireland stored none, so the store could not
answer "which NI committees exist, and which of them touch our issues" --
the one question a register is for.

organisations.asmx was an entire service this pipeline had never called. It
lists committees in four kinds, and the useful one is STATUTORY: Health,
Education, Justice and Communities are the departmental scrutiny committees
where our issues are actually argued. The Standing list is procedural (Audit,
Business, Procedures, Standards). All four are read anyway -- a register that
silently omits three of its four kinds is worse than no register -- and the
kind is stored so a reader can tell them apart.

WHAT THIS IS NOT. It is not committee scrutiny. NI committee TRANSCRIPTS are
not in the Open Data API at all: GetAllHansardReports returns 652 reports and
every one is keyed on PlenaryDate, so Hansard there is plenary-only. That gap
against Scotland stays open, and closing it would mean scraping the Assembly
website.

Watching brief: writes ni_committees only, never items/mp_events, so nothing
here can reach the published digest. ONE WRITER AT A TIME on the store.
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
from src.ingest import niassembly


def main():
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

    stored = ours = 0
    gaps = []
    for kind in niassembly.COMMITTEE_KINDS:
        try:
            payload = client.get_json(
                niassembly.COMMITTEES_LIST.format(kind), "ni",
                "committees-{0}".format(kind.lower()), archive=False)
        except FetchError as exc:
            gaps.append("{0} committees: {1}".format(kind, exc.cause))
            continue
        found = niassembly.parse_committees(payload, kind)
        if not found:
            # An empty kind is possible (there may be no ad hoc committees
            # sitting), so it is reported, not treated as a failure.
            print("  {0:<10} none listed".format(kind))
            continue
        for cid, name, abbr, k in found:
            # The taxonomy runs on the committee's NAME, which is its REMIT
            # -- "Committee for Health" is our ground on assisted dying
            # whatever it happens to be discussing this week. That is a
            # different claim from a subject match and is stored as such.
            res = filt.filter_item(tax, wl, name)
            areas = res.issue_areas or []
            if areas:
                ours += 1
            conn.execute(
                "INSERT INTO ni_committees (committee_id, name, abbreviation, "
                "kind, areas, matched_terms, first_seen, last_seen) "
                "VALUES (?,?,?,?,?,?,?,?) "
                "ON CONFLICT(committee_id) DO UPDATE SET name=excluded.name, "
                "abbreviation=excluded.abbreviation, kind=excluded.kind, "
                "areas=excluded.areas, matched_terms=excluded.matched_terms, "
                "last_seen=excluded.last_seen",
                (cid, name, abbr, k, json.dumps(areas),
                 json.dumps(res.matched_terms or []), now, now))
            stored += 1
        conn.commit()
        print("  {0:<10} {1} committee(s)".format(kind, len(found)))

    if gaps:
        db.record_gaps(conn, "ni-committees", gaps)
        print("\n{0} gap(s) -- printed, never swallowed:".format(len(gaps)))
        for g in gaps:
            print("  * {0}".format(g))
    else:
        print("\nno gaps.")

    print("{0} committee(s) held; {1} match our areas by remit.".format(
        stored, ours))
    for row in conn.execute(
            "SELECT name, abbreviation, kind, areas FROM ni_committees "
            "WHERE areas NOT IN ('[]', '') ORDER BY kind, name"):
        print("  * {0:<46} {1:<10} {2}".format(
            (row[0] or "")[:44], row[1] or "", row[3]))
    print("\nStored in ni_committees, not items: this cannot reach the "
          "Slack digest.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
