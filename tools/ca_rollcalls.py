#!/usr/bin/env python3
"""House of Commons of Canada: recorded divisions, member positions and bills.

    python3 tools/ca_rollcalls.py                    # the current session
    python3 tools/ca_rollcalls.py --session 44-1     # an earlier one
    python3 tools/ca_rollcalls.py --dry-run          # count, store nothing
    python3 tools/ca_rollcalls.py --db /tmp/ca.db    # anywhere but the store

GROUNDWORK (26 September 2026). Nothing schedules this and nothing reads its
tables yet; see docs/canada-scope.md. Every source here is open, keyless and
official:

  * ourcommons.ca/members/en/votes/xml?parlSession=P-S  -- every division of
    a session in ONE call (174 for 45-1, 928 for 44-1), with the House's own
    result and tallies.
  * ourcommons.ca/members/en/votes/P/S/N/xml  -- every member's position on
    division N, with the caucus they voted in. ~250 KB each.
  * parl.ca/legisinfo/en/bills/json?parlsession=P-S  -- every bill of the
    session with status, sponsor and stage dates, in ONE call.

EVERY DIVISION IS STORED; POSITIONS ONLY WHERE THEY ARE USED. The division
list is one request, so it costs nothing to keep all of it and the watching
list is the proof it was read. Member positions are a request PER division,
and the 5CA only reads them on our ground, so they are fetched for divisions
with an area (23 of 174 in 45-1). `positions_fetched` is the flag, NOT the
row's existence: a --reclassify that gives an old division an area leaves
positions_fetched=0, and the next run fetches it. A collector that skips
work because the row exists is how the German members kept a NULL for ever.
--all-positions fetches every division, and is a backfill: run it from CI,
paced, and say so (the Bundestag IP block of 24 September 2026).

CLASSIFICATION is against the ENGLISH taxonomy, unchanged, plus
config/watchlist-ca.yaml. Unlike Germany this works: federal Canada is
bilingual and every subject line has an English text. The watchlist carries
what the taxonomy measurably missed.

Separation guarantee: writes ca_members, ca_divisions, ca_votes, ca_bills
and the shared gaps table only. ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "ca-rollcalls"
CURRENT_SESSION = "45-1"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
WATCHLIST = os.path.join(ROOT, "config", "watchlist-ca.yaml")
DIVISIONS = "https://www.ourcommons.ca/members/en/votes/xml?parlSession={0}"
DIVISION = "https://www.ourcommons.ca/members/en/votes/{0}/{1}/{2}/xml"
BILLS = "https://www.parl.ca/legisinfo/en/bills/json?parlsession={0}"
BUDGET_S = drain.DEFAULT_S
# Migration is collated, never campaigned (src/partner.py HIDDEN_AREAS). It
# still gets an area -- the row is honest about what it is -- but it does not
# earn a per-division fetch.
HIDDEN_AREAS = (11,)

SESSION_RE = re.compile(r"^(\d{1,2})-(\d)$")


def parse_session(code):
    """'45-1' -> (45, 1). Raises ValueError on anything else."""
    hit = SESSION_RE.match((code or "").strip())
    if not hit:
        raise ValueError("session must look like 45-1, not {0!r}".format(code))
    return int(hit.group(1)), int(hit.group(2))


def division_key(parl, sess, number, chamber="commons"):
    return "{0}-{1}-{2}-{3}".format(chamber, parl, sess, number)


def _text(el, tag):
    v = el.findtext(tag)
    return v.strip() if v is not None and v.strip() else None


def _int(el, tag):
    v = _text(el, tag)
    try:
        return int(v) if v is not None else None
    except ValueError:
        return None


def parse_divisions(xml_text):
    """The session's division list as dicts, in the House's order."""
    out = []
    for v in ET.fromstring(xml_text).findall("Vote"):
        out.append({
            "parliament": _int(v, "ParliamentNumber"),
            "session": _int(v, "SessionNumber"),
            "number": _int(v, "DecisionDivisionNumber"),
            "date": _text(v, "DecisionEventDateTime"),
            "subject": _text(v, "DecisionDivisionSubject"),
            "result": _text(v, "DecisionResultName"),
            "yeas": _int(v, "DecisionDivisionNumberOfYeas"),
            "nays": _int(v, "DecisionDivisionNumberOfNays"),
            "paired": _int(v, "DecisionDivisionNumberOfPaired"),
            "doc_type": _text(v, "DecisionDivisionDocumentTypeName"),
            "bill_number": _text(v, "BillNumberCode"),
        })
    return out


def position(p):
    """'Yea' / 'Nay' / 'Paired' from a participant, trusting the booleans
    over the display name when both are present."""
    if (p.findtext("IsVotePaired") or "").lower() == "true":
        return "Paired"
    if (p.findtext("IsVoteYea") or "").lower() == "true":
        return "Yea"
    if (p.findtext("IsVoteNay") or "").lower() == "true":
        return "Nay"
    return _text(p, "VoteValueName")


def parse_participants(xml_text):
    out = []
    for p in ET.fromstring(xml_text).findall("VoteParticipant"):
        pid = _text(p, "PersonId")
        if not pid:
            continue
        name = " ".join(x for x in (_text(p, "PersonOfficialFirstName"),
                                    _text(p, "PersonOfficialLastName")) if x)
        out.append({"person_id": pid, "name": name or None,
                    "party": _text(p, "CaucusShortName"),
                    "constituency": _text(p, "ConstituencyName"),
                    "province": _text(p, "ConstituencyProvinceTerritoryName"),
                    "position": position(p)})
    return out


def classify(tax, wl, *fields):
    return filt.filter_item(tax, wl, *fields)


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def store_division(conn, d, res, today):
    key = division_key(d["parliament"], d["session"], d["number"])
    conn.execute(
        "INSERT INTO ca_divisions (division_key, chamber, parliament, session, "
        "number, date, subject, result, yeas, nays, paired, doc_type, "
        "bill_number, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET subject=excluded.subject, "
        "result=excluded.result, yeas=excluded.yeas, nays=excluded.nays, "
        "paired=excluded.paired, doc_type=excluded.doc_type, "
        "bill_number=excluded.bill_number, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen",
        (key, "commons", d["parliament"], d["session"], d["number"], d["date"],
         d["subject"], d["result"], d["yeas"], d["nays"], d["paired"],
         d["doc_type"], d["bill_number"], json.dumps(res.issue_areas or []),
         json.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
         res.tier, today, today))
    return key


def store_positions(conn, key, participants, today):
    for p in participants:
        conn.execute(
            "INSERT INTO ca_members (person_id, name, party, constituency, "
            "province, first_seen, last_seen) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(person_id) DO UPDATE SET name=excluded.name, "
            "party=excluded.party, constituency=excluded.constituency, "
            "province=excluded.province, last_seen=excluded.last_seen",
            (p["person_id"], p["name"], p["party"], p["constituency"],
             p["province"], today, today))
        conn.execute(
            "INSERT OR REPLACE INTO ca_votes (division_key, person_id, "
            "position, party) VALUES (?,?,?,?)",
            (key, p["person_id"], p["position"], p["party"]))
    conn.execute("UPDATE ca_divisions SET positions_fetched=1 "
                 "WHERE division_key=?", (key,))


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) "
                 "VALUES (?,?,?)", (today, FEED, detail))


def pull_divisions(conn, client, today, session=CURRENT_SESSION, tax=None,
                   wl=None, log=print, limit=None, budget=None,
                   all_positions=False):
    """Store every division of one session; fetch positions on our ground.

    Returns (listed, ours, fetched, gaps)."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else filt.load_watchlist(WATCHLIST)
    parl, sess = parse_session(session)
    rows = parse_divisions(client.get_text(DIVISIONS.format(session), FEED,
                                           "divisions-" + session, archive=False))
    ours = 0
    for d in rows:
        res = classify(tax, wl, d["subject"] or "")
        store_division(conn, d, res, today)
        if on_our_ground(res.issue_areas):
            ours += 1
    conn.commit()
    want = conn.execute(
        "SELECT division_key, number, areas FROM ca_divisions "
        "WHERE parliament=? AND session=? AND positions_fetched=0 "
        "ORDER BY number", (parl, sess)).fetchall()
    fetched = gaps = 0
    for key, number, areas in want:
        if not all_positions and not on_our_ground(json.loads(areas or "[]")):
            continue
        if limit is not None and fetched >= limit:
            log("  fetch cap ({0}) reached; the rest lands on the next run "
                "-- disclosed, not silent".format(limit))
            break
        if budget is not None and budget.exhausted():
            log(budget.disclose("division positions", fetched))
            break
        try:
            text = client.get_text(DIVISION.format(parl, sess, number), FEED,
                                   "division-{0}".format(key), archive=False)
            participants = parse_participants(text)
        except (FetchError, ET.ParseError) as exc:
            _gap(conn, today, "{0}: {1}".format(key, exc))
            log("  [gap] {0}: {1}".format(key, str(exc)[:70]))
            gaps += 1
            continue
        if not participants:
            # An empty participant list is not a division nobody voted in.
            # Record it and leave positions_fetched=0 so it is asked again.
            _gap(conn, today, "{0}: no participants returned".format(key))
            gaps += 1
            continue
        store_positions(conn, key, participants, today)
        conn.commit()
        fetched += 1
    return len(rows), ours, fetched, gaps


def pull_bills(conn, client, today, session=CURRENT_SESSION, tax=None, wl=None):
    """Store every bill of one session. Returns (listed, ours)."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else filt.load_watchlist(WATCHLIST)
    parl, sess = parse_session(session)
    bills = client.get_json(BILLS.format(session), FEED, "bills-" + session,
                            archive=False) or []
    ours = 0
    for b in bills:
        if b.get("IsProForma"):
            continue    # C-1 and S-1: introduced to assert the House's right, never debated
        number = b.get("NumberCode")
        res = classify(tax, wl, b.get("LongTitleEn") or "", b.get("ShortTitleEn") or "")
        if on_our_ground(res.issue_areas):
            ours += 1
        conn.execute(
            "INSERT INTO ca_bills (bill_key, parliament, session, number, "
            "legisinfo_id, long_title, short_title, status, is_government, "
            "sponsor, latest_event, latest_event_at, royal_assent_at, areas, "
            "matched_terms, tier, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(bill_key) DO UPDATE SET long_title=excluded.long_title, "
            "short_title=excluded.short_title, status=excluded.status, "
            "sponsor=excluded.sponsor, latest_event=excluded.latest_event, "
            "latest_event_at=excluded.latest_event_at, "
            "royal_assent_at=excluded.royal_assent_at, areas=excluded.areas, "
            "matched_terms=excluded.matched_terms, tier=excluded.tier, "
            "last_seen=excluded.last_seen",
            ("{0}-{1}/{2}".format(parl, sess, number), parl, sess, number,
             str(b.get("Id") or ""), b.get("LongTitleEn"),
             b.get("ShortTitleEn") or None, b.get("StatusNameEn"),
             None if b.get("IsGovernmentBill") is None else int(bool(b.get("IsGovernmentBill"))),
             b.get("SponsorPersonName"), b.get("LatestBillEventTypeNameEn"),
             b.get("LatestBillEventDateTime"), b.get("ReceivedRoyalAssentDateTime"),
             json.dumps(res.issue_areas or []),
             json.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
             res.tier, today, today))
    conn.commit()
    return len(bills), ours


def reclassify(conn, tax=None, wl=None, log=print):
    """Re-derive areas offline after a taxonomy or watchlist change.

    Leaves positions_fetched alone: a division that GAINS an area here is
    fetched by the next ordinary run, because it is still 0."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else filt.load_watchlist(WATCHLIST)
    changed = 0
    for key, subject, areas in conn.execute(
            "SELECT division_key, subject, areas FROM ca_divisions").fetchall():
        res = classify(tax, wl, subject or "")
        new = json.dumps(res.issue_areas or [])
        if new != (areas or "[]"):
            changed += 1
        conn.execute("UPDATE ca_divisions SET areas=?, matched_terms=?, tier=? "
                     "WHERE division_key=?",
                     (new, json.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, key))
    conn.commit()
    log("ca-rollcalls: reclassified; {0} division(s) changed area".format(changed))
    return changed


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    log("  store: {0} division(s), {1} with positions, {2} member(s), "
        "{3} position(s), {4} bill(s)".format(
            n("SELECT COUNT(*) FROM ca_divisions"),
            n("SELECT COUNT(*) FROM ca_divisions WHERE positions_fetched=1"),
            n("SELECT COUNT(*) FROM ca_members"),
            n("SELECT COUNT(*) FROM ca_votes"),
            n("SELECT COUNT(*) FROM ca_bills")))
    log("  Matched against the ENGLISH taxonomy plus config/watchlist-ca.yaml, "
        "a groundwork draft nobody in Canada has reviewed.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", default=CURRENT_SESSION, help="parliament-session, e.g. 45-1")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--all-positions", action="store_true",
                    help="fetch member positions for EVERY division (a backfill: CI, paced, announced)")
    ap.add_argument("--no-bills", action="store_true")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored divisions, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--limit", type=int, help="stop after this many position fetches")
    ap.add_argument("--dry-run", action="store_true",
                    help="count the session's divisions and bills, store nothing")
    args = ap.parse_args()
    parse_session(args.session)
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    today = datetime.date.today().isoformat()
    if args.dry_run:
        rows = parse_divisions(client.get_text(DIVISIONS.format(args.session), FEED,
                                               "divisions-" + args.session, archive=False))
        bills = client.get_json(BILLS.format(args.session), FEED,
                                "bills-" + args.session, archive=False) or []
        print("ca-rollcalls: {0}: {1} division(s), {2} bill(s)".format(
            args.session, len(rows), len(bills)))
        return 0
    conn = ca_store.ensure_schema(db.init_db(db.connect(args.db)))
    if args.reclassify:
        reclassify(conn)
        summary(conn)
        conn.close()
        return 0
    tax = filt.load_taxonomy(TAXONOMY)
    wl = filt.load_watchlist(WATCHLIST)
    listed, ours, fetched, gaps = pull_divisions(
        conn, client, today, session=args.session, tax=tax, wl=wl,
        limit=args.limit, budget=drain.Budget(args.budget_seconds),
        all_positions=args.all_positions)
    print("ca-rollcalls: {0}: {1} division(s) listed, {2} on our ground, "
          "{3} position fetch(es), {4} gap(s).".format(args.session, listed, ours,
                                                        fetched, gaps))
    if not args.no_bills:
        blisted, bours = pull_bills(conn, client, today, session=args.session,
                                    tax=tax, wl=wl)
        print("  {0} bill(s) listed, {1} on our ground.".format(blisted, bours))
    summary(conn)
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
