"""Senedd plenary divisions -> sd_divisions / sd_votes.

    python3 tools/sd_divisions.py            # walk both parliaments to 2024
    python3 tools/sd_divisions.py --parl 908 # one parliament

Also harvests SPEECHES: the same index links each sitting's English
transcript XML, so one walk serves votes and speeches (the Holyrood lesson).
Speeches are passage-classified into sd_events -- activity evidence only.

The route is the undocumented XMLExport behind record.senedd.wales, found via
mySociety's parlparse scraper: an index of sittings per parliament (700 =
Sixth Senedd, 908 = Seventh), each linking a Votes XML of per-member rows.
Divisions are classified by the taxonomy over their English title -- the vote
names carry the debate subject ("Welsh Conservatives Debate - deposit return
scheme"), which is coarser than Holyrood's motion-text join and says so below.

Same rules as every watching-brief tool: sd_* tables only, never
items/mp_events; gaps printed, never swallowed; tiny transactions.
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


def not_ours_keys():
    """Divisions a human has struck as NOT on our ground, whatever the
    title says. The collector re-derives areas from the title on every
    run, so a store-only correction returns the following week; this is
    where the human's reading of the Record outranks the regex.
    Christopher, 2026-09-06: the Crime and Policing Bill LCM was tagged
    abortion by its title, and abortion is a reserved matter in Wales."""
    import yaml
    path = os.path.join(ROOT, "config", "senedd_votes.yaml")
    if not os.path.exists(path):
        return set()
    divs = (yaml.safe_load(open(path, encoding="utf-8")) or {}).get("divisions") or []
    return {str(d["key"]) for d in divs if d.get("not_ours")}

FLOOR = "2024-01-01"


def main():
    parls = [senedd.SEVENTH_SENEDD, senedd.SIXTH_SENEDD]
    if "--parl" in sys.argv:
        parls = [int(sys.argv[sys.argv.index("--parl") + 1])]
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))

    known = {r[0] for r in conn.execute("SELECT key FROM sd_divisions")}
    stored = voted = ours = gaps = 0
    for parl in parls:
        page, more = 1, True
        floor_hit = False
        while more and not floor_hit:
            try:
                sittings, more = senedd.fetch_vote_index(client, parl, page)
            except FetchError as exc:
                print("  [gap] index {0} p{1}: {2}".format(parl, page, exc.cause))
                gaps += 1
                break
            struck = not_ours_keys()
            for s in sittings:
                if s.dated < FLOOR:
                    floor_hit = True
                    continue
                # SPEECHES for every sitting in range (transcripts exist even
                # where no division happened); stored only when a passage
                # matches. Skipped when the sitting is already held, so the
                # weekly run fetches only new sittings.
                already = conn.execute(
                    "SELECT 1 FROM sd_events WHERE key LIKE 'sdc%' AND "
                    "dated = ? LIMIT 1", (s.dated,)).fetchone()
                if not already or "--refetch" in sys.argv:
                    try:
                        for sp in senedd.fetch_transcript(client, s.meeting_id):
                            matches = filt.match_passages(
                                tax, wl, sp.text, title=sp.heading or "")
                            if not matches:
                                continue
                            s_areas, s_terms, excerpt = \
                                filt.aggregate_passages(matches)
                            if not s_areas:
                                continue
                            conn.execute(
                                "INSERT INTO sd_events (key, member_id, "
                                "member_name, dated, heading, areas, "
                                "matched_terms, excerpt, first_seen, "
                                "last_seen) VALUES (?,?,?,?,?,?,?,?,?,?) "
                                "ON CONFLICT(key) DO UPDATE SET "
                                "areas=excluded.areas, "
                                "matched_terms=excluded.matched_terms, "
                                "excerpt=excluded.excerpt, "
                                "last_seen=excluded.last_seen",
                                (sp.key, sp.member_id, sp.member_name,
                                 sp.dated, sp.heading, json.dumps(s_areas),
                                 json.dumps(s_terms), excerpt, now, now))
                    except FetchError as exc:
                        conn.execute(
                            "INSERT OR IGNORE INTO gaps (edition, feed, detail) "
                            "VALUES (?,?,?)",
                            (datetime.date.today().isoformat(), "sd-speeches",
                             "meeting {0}: {1}".format(s.meeting_id,
                                                       exc.cause)))
                        conn.commit()
                        print("  [gap] transcript {0}: {1}".format(
                            s.meeting_id, exc.cause))
                        gaps += 1
                if not s.has_votes:
                    continue
                try:
                    divs = senedd.fetch_votes(client, s.meeting_id)
                except FetchError as exc:
                    conn.execute(
                        "INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                        (datetime.date.today().isoformat(), "sd-votes",
                         "meeting {0}: {1}".format(s.meeting_id, exc.cause)))
                    conn.commit()
                    print("  [gap] meeting {0}: {1}".format(
                        s.meeting_id, exc.cause))
                    gaps += 1
                    continue
                for d in divs:
                    res = filt.filter_item(tax, wl, d.title or "")
                    areas = res.issue_areas or []
                    if str(d.key) in struck:
                        areas = []          # a human read the Record; the title lies
                    if areas and d.key not in known:
                        ours += 1
                    conn.execute(
                        "INSERT INTO sd_divisions (key, meeting_id, dated, "
                        "title, total_for, total_against, total_abstain, "
                        "result, areas, matched_terms, tier, first_seen, "
                        "last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(key) DO UPDATE SET title=excluded.title, "
                        "areas=excluded.areas, "
                        "matched_terms=excluded.matched_terms, "
                        "tier=excluded.tier, last_seen=excluded.last_seen",
                        (d.key, d.meeting_id, d.dated, d.title, d.total_for,
                         d.total_against, d.total_abstain, d.result,
                         json.dumps(areas), json.dumps(res.matched_terms or []),
                         res.tier, now, now))
                    for v in d.votes:
                        conn.execute(
                            "INSERT OR REPLACE INTO sd_votes (division_key, "
                            "member_id, member_name, result) VALUES (?,?,?,?)",
                            (d.key, v.member_id, v.member_name, v.result))
                        voted += 1
                    stored += 1
                conn.commit()
            page += 1
        print("parliament {0}: cumulative {1} division(s).".format(parl, stored))

    total = conn.execute("SELECT COUNT(*) FROM sd_divisions").fetchone()[0]
    n_ours = conn.execute("SELECT COUNT(*) FROM sd_divisions WHERE areas "
                          "IS NOT NULL AND areas != '[]'").fetchone()[0]
    print("\n{0} division(s) held ({1} this run), {2} vote position(s) "
          "written; {3} on our ground by DEBATE TITLE -- coarser than "
          "Holyrood's motion-text join, and classification improves when "
          "phase 3 adds the transcript XMLs.".format(
              total, stored, voted, n_ours))
    sp_n = conn.execute("SELECT COUNT(*) FROM sd_events").fetchone()[0]
    print("{0} speech event(s) in sd_events (passage-matched; activity "
          "evidence, never direction).".format(sp_n))
    print("no gaps." if not gaps else "{0} gap(s) -- printed above.".format(gaps))
    print("Written to sd_divisions/sd_votes, not `items`: structurally "
          "cannot reach the Slack digest.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
