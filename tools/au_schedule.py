#!/usr/bin/env python3
"""Australia's week ahead: what the open sources say is coming.

    python3 tools/au_schedule.py                          # read and store
    python3 tools/au_schedule.py --dry-run                # read and summarise, store nothing
    python3 tools/au_schedule.py --db /tmp/au.db --raw-dir /tmp/au-raw   # a scratch run

Built 9 October 2026, in a recess (no sitting since 17 September). See
docs/australia-scope.md, "The week ahead".

THE CALENDAR IS BLOCKED. The APH sitting calendar, the House and Senate
Notice Papers, the Senate's Daily Program, the House's Daily Program and
committee inquiry deadlines all live on www.aph.gov.au or ParlInfo, which
refuse the laptop and GitHub's runners (an Azure WAF 403). They are not
worked around and were not found mirrored on any host that answers
(data.gov.au, data.openaustralia.org.au: measured 9 October 2026). So this
cannot say which bill comes up on which day.

WHAT ANSWERS, keyless and official:

  * api.prod.legislation.gov.au/v1/titles/search(criteria='openfordisallowance(0)')
    -- the Federal Register of Legislation's list of every legislative
    instrument still open for disallowance (277 on 9 October 2026, one
    request, 4 s, 138 KB), each with the LAST DAY the House and the Senate
    can disallow it and the Acts it is made under (authorisedBy). A last day
    is the fifteenth sitting day after the instrument was tabled in that
    House, counted on the Register's own copy of the sitting calendar. So
    EVERY LAST DAY STILL AHEAD IS A DAY THAT HOUSE IS DUE TO SIT: the only
    forward sitting days any answering source gives. It is not the whole
    calendar (a sitting day on which no instrument's clock ends is missing)
    and it says nothing of Senate estimates.
  * api.prod.legislation.gov.au/v1/titles('<id>')?$expand=parliamentaryScrutiny
    -- one instrument's tabling dates and any notice of a DISALLOWANCE
    MOTION (who gave it, in which House, when). Read only for instruments on
    our ground: reading all 277 took 262 s and found one motion.
  * handbookapi.aph.gov.au/api/parliaments -- the Parliamentary Handbook's
    record of each Parliament: a dissolution date there means every bill
    before Parliament has lapsed.

KEYS, NEVER TITLES. An instrument is keyed on the Register's title ID
('F2026L00968'). Its areas are its own name's, then (by Register ID) those
of a principal Act on config/watchlist-au.yaml's acts: list, then those of
a bill of this Parliament whose Act enables it (au_bills.act_id -> bill_id,
the r7512-style key). Bills themselves have no forward date reachable.

Separation guarantee: writes au_instruments, au_sitting_days,
au_parliaments, the shared gaps table and its own source_runs heartbeat.
ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import au_store, db, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "au-schedule"
HEARTBEAT = "AU week ahead"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
FRL = "https://api.prod.legislation.gov.au/v1"
# The Register's own search grammar (read from its website's code): the
# argument is "extra sitting days"; 0 asks for what is open now. $top is
# capped at 500 by the API; 277 were open on 9 October 2026.
OPEN_FOR_DISALLOWANCE = (
    FRL + "/titles/search(criteria='openfordisallowance(0)')?$top=500&$count=true"
    "&$select=id,name,makingDate,collection,asMadeRegisteredAt"
    "&$expand=searchContexts($expand=openForDisallowance),authorisedBy($select=affectingTitleId)")
SCRUTINY = FRL + "/titles('{0}')?$select=id,name&$expand=parliamentaryScrutiny"
PARLIAMENTS = ("https://handbookapi.aph.gov.au/api/parliaments?$select=PID,Name,DateElection,"
               "DateOpening,DateDissolution,ParliamentEnd&$orderby=PID%20desc&$top=2")
PAGE_CAP = 500
NO_DAY = "9999-12-31"
HIDDEN_AREAS = (11,)
CHAMBERS = (("house", "lastDayForDisallowanceHor"), ("senate", "lastDayForDisallowanceSenate"))
HOUSE_OF = {"HouseOfReps": "house", "Senate": "senate"}


def _day(value):
    return (value or "")[:10] or None


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def empty_watchlist():
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


# --- parsing ---------------------------------------------------------------------

def parse_open(payload):
    """The Register's open-for-disallowance list -> one dict per instrument.
    A last day of 9999-12-31 is None: no clock running in that House."""
    out = []
    for t in (payload or {}).get("value") or []:
        ofd = ((t.get("searchContexts") or {}).get("openForDisallowance")) or {}
        row = {"title_id": t.get("id"), "name": t.get("name"),
               "collection": t.get("collection"), "making_date": _day(t.get("makingDate")),
               "registered_at": _day(t.get("asMadeRegisteredAt")),
               "acts": sorted({a.get("affectingTitleId") for a in t.get("authorisedBy") or []
                               if a.get("affectingTitleId")})}
        for chamber, key in CHAMBERS:
            day = _day(ofd.get(key))
            row["last_day_" + chamber] = None if (not day or day >= NO_DAY) else day
        if row["title_id"]:
            out.append(row)
    return out


def parse_scrutiny(payload):
    """One title's parliamentaryScrutiny -> compact events, oldest first."""
    out = []
    for e in (payload or {}).get("parliamentaryScrutiny") or []:
        ev = {"type": e.get("eventType"), "date": _day(e.get("eventDate")),
              "house": HOUSE_OF.get(e.get("house"), e.get("house"))}
        for k, name in (("disallowanceMotionSponsor", "sponsor"),
                        ("disallowanceMotionExpiryDate", "expires"),
                        ("motionOutcomeType", "outcome"),
                        ("disallowanceMotionProvisionsForPartial", "provisions")):
            if e.get(k):
                ev[name] = _day(e[k]) if name == "expires" else e[k]
        out.append(ev)
    return sorted(out, key=lambda e: (e["date"] or "", e["type"] or ""))


def sitting_days(rows, today):
    """{(chamber, date): instruments} for every last day still ahead: each is
    a day the Register counts as a sitting day of that House."""
    out = {}
    for r in rows:
        for chamber, _key in CHAMBERS:
            day = r["last_day_" + chamber]
            if day and day >= today:
                out[(chamber, day)] = out.get((chamber, day), 0) + 1
    return out


def parse_parliaments(payload):
    return [{"parliament": p.get("PID"), "name": p.get("Name"),
             "election": p.get("DateElection") or None, "opening": p.get("DateOpening") or None,
             "dissolution": p.get("DateDissolution") or None,
             "ended": p.get("ParliamentEnd") or None}
            for p in (payload or {}).get("value") or [] if p.get("PID")]


# --- classification --------------------------------------------------------------

def act_bills(conn):
    """{Register Act ID: (bill_id, areas)} for the Acts this store's bills became."""
    return {act: (bid, json.loads(areas or "[]")) for bid, act, areas in conn.execute(
        "SELECT bill_id, act_id, areas FROM au_bills WHERE act_id IS NOT NULL")}


def classify(tax, wl, row, acts_watch, bills_by_act):
    """(own, areas, areas_from, terms, tier, bill_id). Own name first; then a
    watched principal Act, by Register ID; then the bill an enabling Act of
    this Parliament came from, only when that bill is on our ground."""
    res = filt.filter_item(tax, wl, row["name"] or "", title=row["name"] or "")
    own = sorted(set(res.issue_areas or []))
    areas, source = set(own), ("own" if own else None)
    terms = list(res.matched_terms or [])
    tier = res.tier
    bill_id = None
    for act in row["acts"]:
        if act in acts_watch:
            areas |= set(acts_watch[act][0])
            source = source or "act"
            terms.append("act:" + act)
            tier = tier or 2
        if act in bills_by_act:
            bid, bill_areas = bills_by_act[act]
            bill_id = bill_id or bid
            if on_our_ground(bill_areas):
                areas |= set(bill_areas)
                source = source or "bill"
                terms.append("bill:" + bid)
                tier = tier or 2
    return own, sorted(areas), source, terms, tier, bill_id


# --- storing ---------------------------------------------------------------------

def store_instruments(conn, rows, today, tax, wl, acts_watch=None):
    acts_watch = au_store.act_watchlist() if acts_watch is None else acts_watch
    bills_by_act = act_bills(conn)
    conn.execute("UPDATE au_instruments SET open=0")
    ours = []
    for r in rows:
        own, areas, source, terms, tier, bill_id = classify(tax, wl, r, acts_watch, bills_by_act)
        conn.execute(
            "INSERT INTO au_instruments (title_id, name, collection, making_date, registered_at, "
            "last_day_house, last_day_senate, enabling_acts, bill_id, own_areas, areas, "
            "areas_from, matched_terms, tier, open, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?) ON CONFLICT(title_id) DO UPDATE SET "
            "name=excluded.name, collection=excluded.collection, making_date=excluded.making_date, "
            "registered_at=excluded.registered_at, last_day_house=excluded.last_day_house, "
            "last_day_senate=excluded.last_day_senate, enabling_acts=excluded.enabling_acts, "
            "bill_id=excluded.bill_id, own_areas=excluded.own_areas, areas=excluded.areas, "
            "areas_from=excluded.areas_from, matched_terms=excluded.matched_terms, "
            "tier=excluded.tier, open=1, last_seen=excluded.last_seen",
            (r["title_id"], r["name"], r["collection"], r["making_date"], r["registered_at"],
             r["last_day_house"], r["last_day_senate"], au_store.dumps(r["acts"]), bill_id,
             au_store.dumps(own), au_store.dumps(areas), source, au_store.dumps(terms), tier,
             today, today))
        if on_our_ground(areas):
            ours.append(r["title_id"])
    return ours


def store_sitting_days(conn, days, today):
    for (chamber, date), n in sorted(days.items()):
        conn.execute(
            "INSERT INTO au_sitting_days (chamber, date, source, instruments, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(chamber, date) DO UPDATE SET "
            "instruments=excluded.instruments, last_seen=excluded.last_seen",
            (chamber, date, "frl-disallowance", n, today, today))


def store_parliaments(conn, rows, today):
    for p in rows:
        conn.execute(
            "INSERT INTO au_parliaments (parliament, name, election, opening, dissolution, ended, "
            "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(parliament) DO UPDATE SET "
            "name=excluded.name, election=excluded.election, opening=excluded.opening, "
            "dissolution=excluded.dissolution, ended=excluded.ended, last_seen=excluded.last_seen",
            (p["parliament"], p["name"], p["election"], p["opening"], p["dissolution"],
             p["ended"], today, today))


def stamp_heartbeat(conn, today, note):
    conn.execute("INSERT OR REPLACE INTO source_runs (source, last_run, run_id, note) "
                 "VALUES (?,?,?,?)", (HEARTBEAT, today, os.environ.get("GITHUB_RUN_ID"), note))


# --- the run ---------------------------------------------------------------------

def run(conn, client, today, tax=None, wl=None, log=print, dry=False, acts_watch=None):
    """Returns a dict of counts, 'gaps' among them."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else empty_watchlist()
    stats = {"open": 0, "ours": 0, "days": 0, "motions": 0, "gaps": 0, "parliaments": 0}
    try:
        payload = client.get_json(OPEN_FOR_DISALLOWANCE, FEED, "frl-open-for-disallowance",
                                  archive=not dry)
        rows = parse_open(payload)
        if payload.get("@odata.count") is not None and payload["@odata.count"] > len(rows):
            _gap(conn, today, "FRL open for disallowance: {0} listed, {1} read (the $top cap "
                 "is {2})".format(payload["@odata.count"], len(rows), PAGE_CAP))
            log("  [gap] open for disallowance: {0} of {1} read".format(
                len(rows), payload["@odata.count"]))
            stats["gaps"] += 1
    except (FetchError, ValueError, AttributeError) as exc:
        _gap(conn, today, "FRL open for disallowance: {0}".format(exc))
        log("  [gap] FRL open for disallowance: {0}".format(str(exc)[:80]))
        stats["gaps"] += 1
        rows = None
    if rows is not None:
        days = sitting_days(rows, today)
        stats["open"], stats["days"] = len(rows), len(days)
        if dry:
            acts_watch = au_store.act_watchlist() if acts_watch is None else acts_watch
            bills_by_act = act_bills(conn)
            ours = [r["title_id"] for r in rows
                    if on_our_ground(classify(tax, wl, r, acts_watch, bills_by_act)[1])]
        else:
            ours = store_instruments(conn, rows, today, tax, wl, acts_watch)
            store_sitting_days(conn, days, today)
        stats["ours"] = len(ours)
        for tid in ours:
            try:
                events = parse_scrutiny(client.get_json(SCRUTINY.format(tid), FEED,
                                                        "frl-scrutiny-" + tid, archive=not dry))
            except (FetchError, ValueError, AttributeError) as exc:
                _gap(conn, today, "FRL scrutiny {0}: {1}".format(tid, exc))
                log("  [gap] scrutiny {0}: {1}".format(tid, str(exc)[:70]))
                stats["gaps"] += 1
                continue
            stats["motions"] += sum(e["type"] == "DisallowanceMotion" for e in events)
            if not dry:
                conn.execute("UPDATE au_instruments SET scrutiny=? WHERE title_id=?",
                             (json.dumps(events), tid))
    try:
        parls = parse_parliaments(client.get_json(PARLIAMENTS, FEED, "handbook-parliaments",
                                                  archive=not dry))
        stats["parliaments"] = len(parls)
        if not dry:
            store_parliaments(conn, parls, today)
    except (FetchError, ValueError, AttributeError) as exc:
        _gap(conn, today, "handbook parliaments: {0}".format(exc))
        log("  [gap] handbook parliaments: {0}".format(str(exc)[:70]))
        stats["gaps"] += 1
    if not dry:
        if rows is not None:
            stamp_heartbeat(conn, today, "step heartbeat: tools/au_schedule.py ({0} open, {1} "
                            "ours, {2} sitting days ahead)".format(stats["open"], stats["ours"],
                                                                   stats["days"]))
        conn.commit()
    return stats


def make_client(raw_dir=None):
    return HttpClient(raw_dir=raw_dir or os.path.join(ROOT, "data", "raw"))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", help="archive raw payloads here instead of data/raw")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--dry-run", action="store_true", help="read and summarise, store nothing")
    args = ap.parse_args()
    conn = db.init_db(db.connect(args.db))
    s = run(conn, make_client(args.raw_dir), args.date, dry=args.dry_run)
    print("au-schedule: {0} instrument(s) open for disallowance, {1} on our ground, {2} "
          "disallowance motion(s) on those; {3} sitting day(s) ahead read from their last "
          "days; {4} Parliament(s) from the Handbook; {5} gap(s){6}".format(
              s["open"], s["ours"], s["motions"], s["days"], s["parliaments"], s["gaps"],
              " (dry run, nothing stored)" if args.dry_run else ""))
    conn.close()
    return 3 if s["gaps"] else 0


if __name__ == "__main__":
    sys.exit(main())
