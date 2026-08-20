"""Holyrood watching-brief pull: roster, questions, motions -> sp_* tables.

    python3 tools/sp_pull.py            # current year's questions + recent motions
    python3 tools/sp_pull.py --year 2025   # add an earlier year of questions
    python3 tools/sp_pull.py --reclassify  # offline: re-run the taxonomy over
                                           # stored bodies, no fetching. The DB
                                           # is the archive here.

Same rules as the NI tools: writes ONLY sp_* tables, so nothing here can reach
the Slack digest, and every source that fails is a printed gap, never a silent
absence. No sweep terms exist: Holyrood serves whole-year dumps, so the
taxonomy classifies every row (src/ingest/holyrood.py records the probing).

Answers are kept only for matched rows. Classification runs on the QUESTION
text, so unmatched rows keep enough to re-test a taxonomy change offline
without carrying ~7MB a year of answers nobody will read.
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
from src.ingest import holyrood

# Motions are floored here, not fetched by year (the dump ignores ?year=).
# 2024-01-01 matches the NI question window and keeps the stored slice to a
# few thousand rows of a 84,751-row dump.
MOTIONS_SINCE = "2024-01-01"


def record_gap(conn, feed, detail):
    conn.execute("INSERT INTO gaps (edition, feed, detail) VALUES (?, ?, ?)",
                 (datetime.date.today().isoformat(), feed, detail))
    conn.commit()
    print("  [gap] {0}: {1}".format(feed, detail))


def store_roster(conn, client, now):
    members = holyrood.fetch_members(client)
    for m in members:
        conn.execute(
            "INSERT INTO sp_members (person_id, name, preferred_name, "
            "is_current, first_seen, last_seen) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(person_id) DO UPDATE SET name=excluded.name, "
            "preferred_name=excluded.preferred_name, "
            "is_current=excluded.is_current, last_seen=excluded.last_seen",
            (m.person_id, m.name, m.preferred_name, int(m.is_current), now, now))
    parties = holyrood.fetch_parties(client)
    affs = holyrood.fetch_affiliations(client)
    for a in affs:
        conn.execute(
            "INSERT OR REPLACE INTO sp_affiliations (id, person_id, party_id, "
            "party, valid_from, valid_until, captured_at) VALUES (?,?,?,?,?,?,?)",
            (a.row_id, a.person_id, a.party_id,
             parties.get(a.party_id), a.valid_from, a.valid_until, now))
    conn.commit()
    current = sum(1 for m in members if m.is_current)
    print("{0} member(s) stored, {1} current; {2} party range(s) from {3} "
          "parties.".format(len(members), current, len(affs), len(parties)))
    if current != 129:
        # The chamber is 129 seats. Anything else is the roster lying, and the
        # NI lesson is that a wrong roster files people under wrong parties
        # silently -- so say it loudly instead.
        print("  WARNING: current roster is {0}, not 129 -- check "
              "/api/members before trusting attribution.".format(current))


def store_rows(conn, rows, tax, wl, now):
    matched = 0
    for r in rows:
        res = filt.filter_item(tax, wl, r.body or "", r.title or "")
        areas = res.issue_areas or []
        if areas:
            matched += 1
        conn.execute(
            "INSERT INTO sp_items (id, kind, reference, title, dated, msp_id, "
            "party, areas, matched_terms, body, answered, answer, answered_by, "
            "cross_party, tier, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET areas=excluded.areas, "
            "matched_terms=excluded.matched_terms, body=excluded.body, "
            "answered=excluded.answered, answer=excluded.answer, "
            "answered_by=excluded.answered_by, tier=excluded.tier, "
            "last_seen=excluded.last_seen",
            ("sp-{0}:{1}".format(r.kind, r.uid), r.kind, r.reference,
             r.title, r.dated, r.msp_id, r.party, json.dumps(areas),
             json.dumps(res.matched_terms or []), r.body,
             r.answered, (r.answer if areas else None), r.answered_by,
             int(r.cross_party), res.tier, now, now))
    conn.commit()
    return matched


def reclassify(conn, tax, wl):
    """Re-run the taxonomy over STORED text. No fetching: sp_items.body is
    the archive, which is the whole point of storing it whole."""
    changed = total = 0
    for r in conn.execute("SELECT id, title, body, areas FROM sp_items").fetchall():
        total += 1
        res = filt.filter_item(tax, wl, r["body"] or "", r["title"] or "")
        areas = json.dumps(res.issue_areas or [])
        if areas != (r["areas"] or "[]"):
            changed += 1
            conn.execute("UPDATE sp_items SET areas=?, matched_terms=?, tier=? "
                         "WHERE id=?",
                         (areas, json.dumps(res.matched_terms or []),
                          res.tier, r["id"]))
        else:
            conn.execute("UPDATE sp_items SET tier=? WHERE id=?",
                         (res.tier, r["id"]))
    conn.commit()
    print("{0} row(s) re-tested offline; {1} changed area.".format(total, changed))


def main():
    year = datetime.date.today().year
    if "--year" in sys.argv:
        year = int(sys.argv[sys.argv.index("--year") + 1])
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

    if "--reclassify" in sys.argv:
        reclassify(conn, tax, wl)
        conn.close()
        return 0

    print("Holyrood pull: questions {0}, motions since {1}".format(
        year, MOTIONS_SINCE))
    gaps = 0
    try:
        store_roster(conn, client, now)
    except FetchError as exc:
        record_gap(conn, "sp-roster", str(exc.cause)); gaps += 1

    try:
        qs = holyrood.fetch_questions(client, year)
        m = store_rows(conn, qs, tax, wl, now)
        print("{0} question(s) for {1}; {2} match our areas.".format(
            len(qs), year, m))
    except FetchError as exc:
        record_gap(conn, "sp-questions", str(exc.cause)); gaps += 1

    try:
        motions = holyrood.fetch_motions(client, MOTIONS_SINCE)
        m = store_rows(conn, motions, tax, wl, now)
        print("{0} motion(s) since {1}; {2} match our areas.".format(
            len(motions), MOTIONS_SINCE, m))
    except FetchError as exc:
        record_gap(conn, "sp-motions", str(exc.cause)); gaps += 1

    print("no gaps." if not gaps else "{0} gap(s) -- printed above.".format(gaps))
    total = conn.execute("SELECT COUNT(*) FROM sp_items").fetchone()[0]
    print("\n{0} row(s) in sp_items. Not in `items`, so structurally cannot "
          "reach the Slack digest.".format(total))
    print("Read it with: python3 tools/sp_monitor.py")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
