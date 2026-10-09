#!/usr/bin/env python3
"""Ireland, the Oireachtas: members, bills with sponsors, and divisions in the
Dail, the Seanad and committee, with every member's vote.

    python3 tools/ie_rollcalls.py                     # the 34th Dail and 27th Seanad
    python3 tools/ie_rollcalls.py --dry-run           # one page of each, store nothing
    python3 tools/ie_rollcalls.py --reclassify        # re-derive areas, offline
    python3 tools/ie_rollcalls.py --db /tmp/ie.db     # anywhere but the store

PHASE 1 (9 October 2026). No edition reads these tables yet; see
docs/ireland-scope.md. One source, open, keyless and official: the
Houses of the Oireachtas Open Data API (api.oireachtas.ie/v1).

  * /members?chamber_id=<house>       -- every member of a House, with each
    party spell (dated) and constituency or panel.
  * /legislation?date_start=<first day of the Dail>
                                      -- every bill with any event since,
    with titles in English and Irish, sponsors, stages, events and the
    debate sections that carried it (419 records on 9 October 2026).
  * /votes?chamber_id=<house>         -- every plenary division of a House
    with every member's vote (Dail 429, Seanad 221 on 9 October 2026).
  * /votes?chamber_type=committee&date_start=...
                                      -- committee divisions (61), where
    Committee Stage amendments are voted.

Each list is read whole every week: it is about 15 requests, a minute, and
it is what re-stamps last_seen for the coverage watch.

A DIVISION NAMES NO BILL. The vote record has `isBill: false` on all 711
divisions of this Dail and Seanad and no bill field at all. What it does
carry is the debate section it was taken in (debate URI + 'dbsect_N'), and
every bill record lists the debate sections that carried it. So a division
is joined to its bill by that pair: an ID join, never a title join. On
9 October 2026 it joined 343 of the 350 plenary divisions whose debate
title names a bill; the 7 others sit in sections the bill record does not
list (a motion to restore a bill to the order paper, an instruction to
committee). Those keep the bill's printed name in `debate_bill`, as text,
and no bill_key: nothing is joined on a title.

A VOTE IS CLASSIFIED WITH ITS BILL. The subject line of an amendment vote
is 'Amendment put:' and nothing else; the amendment is only in the debate
transcript and the amendment-list PDFs (phase 1b). So `areas` is the
division's own areas (debate title + subject) plus its bill's, and
`own_areas` keeps the first set apart, as in the US.

THE API ANSWERS 200 WHEN IT HAS NOTHING TO SAY. An unknown House returns
200 with zero results, a bad `limit` silently falls back to 10, and the
counts saturate at 10,000. So a House that returns no members, or no bills
at all, is a gap, and paging runs until a short page, never to the count.
`skip` over 10,000 or `limit` over 1,000 is a 422.

CLASSIFICATION is the shared English taxonomy plus config/watchlist-ie.yaml,
applied by bill KEY. Ministerial titles are struck from the text first:
the 'Minister for Justice, Home Affairs and Migration' would otherwise file
every justice question and bill under migration (916 of 8,052 PQs in
September 2026 named him).

Separation guarantee: writes ie_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import sys
from urllib.parse import quote, urlencode

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, ie_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "ie-rollcalls"
API = "https://api.oireachtas.ie/v1/"
HOUSE_URI = "https://data.oireachtas.ie/ie/oireachtas/house/{0}/{1}"
# The current Houses. The 34th Dail first met on 18 December 2024 after the
# election of 29 November 2024 (the API dates its membership from the 29th);
# the 27th Seanad from 29 January 2025. At the next general election these
# change, every bill lapses, and config/watchlist-ie.yaml must be re-checked
# (a lapsed bill keeps its key if it is restored, but not if re-introduced).
DAIL, SEANAD = 34, 27
DAIL_START = "2024-11-29"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
BUDGET_S = drain.DEFAULT_S
PAGE = 200            # votes pages are ~5 MB at 200; the API's ceiling is 1,000
# Migration is collated, never campaigned (src/partner.py HIDDEN_AREAS).
HIDDEN_AREAS = (11,)
POSITIONS = (("taVotes", "Yes"), ("nilVotes", "No"), ("staonVotes", "Abstain"))
# Struck from text before matching (see the module docstring). Only the
# office: 'migration' anywhere else in the text still counts.
OFFICES = re.compile(r"\b(?:Minister|Ministers|Department|Minister of State)"
                     r"(?: of State)?(?: at the Department of| for) Justice, Home Affairs and Migration",
                     re.I)
BILL_IN_TITLE = re.compile(r"^(.*?\bBill,? \d{4})\b")


def strip_tags(markup):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup or ""))).strip() or None


def strip_offices(text):
    return OFFICES.sub(" ", text or "")


def house_key(uri):
    """'.../house/dail/34' -> 'dail/34'; anything else -> None."""
    hit = re.search(r"/house/(dail|seanad)/(\d+)$", uri or "")
    return "{0}/{1}".format(hit.group(1), hit.group(2)) if hit else None


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def empty_watchlist():
    """The Irish watchlist is applied by KEY (ie_store.add_watch_areas), so
    the filter itself gets no title entities."""
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def fetch_all(client, path, params, slug, budget=None, archive=False, size=PAGE):
    """Every record of a list, paging until a short page. Returns (records, complete).

    Never trusts head.counts: it saturates at 10,000."""
    out, skip = [], 0
    while True:
        if budget is not None and budget.exhausted():
            return out, False
        query = urlencode(dict(params, limit=size, skip=skip), safe=":/", quote_via=quote)
        data = client.get_json("{0}{1}?{2}".format(API, path, query), FEED,
                               "{0}-{1}".format(slug, skip), archive=archive)
        page = (data or {}).get("results")
        if not isinstance(page, list):
            raise ValueError("{0}: no results list in the answer".format(path))
        out.extend(page)
        if len(page) < size:
            return out, True
        skip += size


# --- members -----------------------------------------------------------------

def parse_member(rec):
    """One /members record -> dict with every membership and party spell."""
    m = rec.get("member") or rec
    ships = []
    for item in m.get("memberships") or []:
        ms = item.get("membership") or {}
        hk = house_key((ms.get("house") or {}).get("uri"))
        if not hk:
            continue
        rng = ms.get("dateRange") or {}
        reps = [(r.get("represent") or {}).get("showAs") for r in ms.get("represents") or []]
        ships.append({
            "house_key": hk, "start": rng.get("start"), "end": rng.get("end"),
            "represents": next((r for r in reps if r), None),
            "parties": [{"party": (p.get("party") or {}).get("showAs"),
                         "start": ((p.get("party") or {}).get("dateRange") or {}).get("start"),
                         "end": ((p.get("party") or {}).get("dateRange") or {}).get("end")}
                        for p in ms.get("parties") or []
                        if (p.get("party") or {}).get("showAs")],
        })
    return {"code": m.get("memberCode"), "name": m.get("fullName") or m.get("showAs"),
            "first": m.get("firstName"), "last": m.get("lastName"), "memberships": ships}


def store_member(conn, m, today):
    ships = sorted(m["memberships"], key=lambda s: s["start"] or "")
    latest = ships[-1] if ships else {}
    parties = sorted(latest.get("parties") or [], key=lambda p: p["start"] or "")
    hk = latest.get("house_key") or "/"
    conn.execute(
        "INSERT INTO ie_members (member_code, name, first_name, last_name, house, house_no, party, "
        "represents, start_date, end_date, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(member_code) DO UPDATE SET name=excluded.name, first_name=excluded.first_name, "
        "last_name=excluded.last_name, "
        # A House's roster carries only that House's membership, so a senator
        # who was a TD is not overwritten by the older spell: newest start wins.
        "house=CASE WHEN COALESCE(excluded.start_date,'') >= COALESCE(ie_members.start_date,'') "
        "THEN excluded.house ELSE ie_members.house END, "
        "house_no=CASE WHEN COALESCE(excluded.start_date,'') >= COALESCE(ie_members.start_date,'') "
        "THEN excluded.house_no ELSE ie_members.house_no END, "
        "party=CASE WHEN COALESCE(excluded.start_date,'') >= COALESCE(ie_members.start_date,'') "
        "THEN excluded.party ELSE ie_members.party END, "
        "represents=CASE WHEN COALESCE(excluded.start_date,'') >= COALESCE(ie_members.start_date,'') "
        "THEN excluded.represents ELSE ie_members.represents END, "
        "end_date=CASE WHEN COALESCE(excluded.start_date,'') >= COALESCE(ie_members.start_date,'') "
        "THEN excluded.end_date ELSE ie_members.end_date END, "
        "start_date=MAX(COALESCE(excluded.start_date,''), COALESCE(ie_members.start_date,'')), "
        "last_seen=excluded.last_seen",
        (m["code"], m["name"], m["first"], m["last"], hk.split("/")[0] or None,
         int(hk.split("/")[1]) if hk.split("/")[1].isdigit() else None,
         parties[-1]["party"] if parties else None, latest.get("represents"),
         latest.get("start"), latest.get("end"), today, today))
    for s in ships:
        for p in s["parties"]:
            if not p["start"]:
                continue
            conn.execute("INSERT INTO ie_member_parties (member_code, house_key, party, start_date, "
                         "end_date) VALUES (?,?,?,?,?) ON CONFLICT(member_code, house_key, party, "
                         "start_date) DO UPDATE SET end_date=excluded.end_date",
                         (m["code"], s["house_key"], p["party"], p["start"], p["end"]))


def pull_members(conn, client, today, houses, log=print):
    """Every member of each House. Returns (stored, gaps)."""
    stored = gaps = 0
    for chamber, no in houses:
        try:
            recs, _complete = fetch_all(client, "members",
                                        {"chamber_id": HOUSE_URI.format(chamber, no)},
                                        "members-{0}-{1}".format(chamber, no), archive=True)
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "members {0}/{1}: {2}".format(chamber, no, exc))
            log("  [gap] members {0}/{1}: {2}".format(chamber, no, str(exc)[:70]))
            gaps += 1
            continue
        if not recs:
            # The API's 200-with-nothing answer for a House it does not know.
            _gap(conn, today, "members {0}/{1}: the API returned no members".format(chamber, no))
            log("  [gap] members {0}/{1}: none returned".format(chamber, no))
            gaps += 1
            continue
        for rec in recs:
            m = parse_member(rec)
            if m["code"]:
                store_member(conn, m, today)
                stored += 1
        conn.commit()
    return stored, gaps


# --- bills -------------------------------------------------------------------

def bill_key(year, number):
    return "{0}/{1}".format(int(year), int(number))


def _event_dates(bill, name):
    dates = []
    for e in bill.get("events") or []:
        ev = e.get("event") or {}
        if ev.get("showAs") == name:
            dates.extend(d.get("date") for d in ev.get("dates") or [] if d.get("date"))
    return max(dates) if dates else None


def is_alive(status, last_stage_house, lapsed_at, restored_at, current):
    """Alive: the API says Current AND the bill is before a sitting House.

    'Current' alone is not enough. A bill that lapsed on a dissolution stays
    'Current' in the API (102 of 266 on 9 October 2026). It is before a
    sitting House when its latest stage was taken there, or when it was
    restored to the order paper after it lapsed: restoration resumes the
    stage it had reached, so its latest stage can be in the old House."""
    if status != "Current":
        return False
    if last_stage_house in current:
        return True
    return bool(restored_at and (not lapsed_at or restored_at >= lapsed_at))


def parse_bill(rec, current=()):
    b = rec.get("bill") or rec
    mrs = (b.get("mostRecentStage") or {}).get("event") or {}
    stage_dates = [d.get("date") for d in mrs.get("dates") or [] if d.get("date")]
    act = b.get("act") or None
    sponsors = []
    for s in b.get("sponsors") or []:
        sp = s.get("sponsor") or {}
        by, office = sp.get("by") or {}, (sp.get("as") or {}).get("showAs")
        code = (by.get("uri") or "").rsplit("/", 1)[-1] or None
        sponsors.append({"member_code": code, "name": by.get("showAs"), "office": office,
                         "primary": bool(sp.get("isPrimary"))})
    debates = []
    for d in b.get("debates") or []:
        if d.get("uri") and d.get("debateSectionId"):
            debates.append({"uri": d["uri"], "section": d["debateSectionId"],
                            "date": d.get("date"), "title": d.get("showAs")})
    out = {
        "year": int(b["billYear"]), "number": int(b["billNo"]),
        "title": (b.get("shortTitleEn") or "").strip() or None,
        "title_ga": (b.get("shortTitleGa") or "").strip() or None,
        "long_title": strip_tags(b.get("longTitleEn")),
        "source": b.get("source"), "bill_type": b.get("billType"),
        "origin_house": ((b.get("originHouse") or {}).get("uri") or "").rsplit("/", 1)[-1] or None,
        "status": b.get("status"),
        "last_stage": mrs.get("showAs"),
        "last_stage_house": house_key((mrs.get("house") or {}).get("uri")),
        "last_stage_at": max(stage_dates) if stage_dates else None,
        "lapsed_at": _event_dates(b, "Bill Lapsed"),
        "restored_at": _event_dates(b, "Bill Restored"),
        "act": ("Act {0} of {1}".format(act.get("actNo"), act.get("actYear"))
                if act and act.get("actNo") else None),
        "act_title": (act or {}).get("shortTitleEn"),
        "last_updated": b.get("lastUpdated"),
        "url": b.get("uri"),
        "sponsors": sponsors, "debates": debates,
    }
    out["alive"] = is_alive(out["status"], out["last_stage_house"], out["lapsed_at"],
                            out["restored_at"], current)
    return out


def classify_bill(tax, wl, b, watch_path=None):
    """Short title first (filter_item's convention), then the long title."""
    res = filt.filter_item(tax, wl, strip_offices(b["title"]), strip_offices(b["long_title"]),
                           title=strip_offices(b["title"]))
    return ie_store.add_watch_areas(res, bill_key(b["year"], b["number"]), watch_path)


def store_bill(conn, b, res, today):
    key = bill_key(b["year"], b["number"])
    conn.execute(
        "INSERT INTO ie_bills (bill_key, year, number, title, title_ga, long_title, source, "
        "bill_type, origin_house, status, last_stage, last_stage_house, last_stage_at, lapsed_at, "
        "restored_at, alive, act, act_title, last_updated, url, areas, matched_terms, tier, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(bill_key) DO UPDATE SET title=excluded.title, title_ga=excluded.title_ga, "
        "long_title=excluded.long_title, source=excluded.source, bill_type=excluded.bill_type, "
        "origin_house=excluded.origin_house, status=excluded.status, "
        "last_stage=excluded.last_stage, last_stage_house=excluded.last_stage_house, "
        "last_stage_at=excluded.last_stage_at, lapsed_at=excluded.lapsed_at, "
        "restored_at=excluded.restored_at, alive=excluded.alive, act=excluded.act, "
        "act_title=excluded.act_title, last_updated=excluded.last_updated, url=excluded.url, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen",
        (key, b["year"], b["number"], b["title"], b["title_ga"], b["long_title"], b["source"],
         b["bill_type"], b["origin_house"], b["status"], b["last_stage"], b["last_stage_house"],
         b["last_stage_at"], b["lapsed_at"], b["restored_at"], int(b["alive"]), b["act"],
         b["act_title"], b["last_updated"], b["url"], ie_store.dumps(res.issue_areas),
         ie_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])), res.tier,
         today, today))
    conn.execute("DELETE FROM ie_sponsors WHERE bill_key=?", (key,))
    for s in b["sponsors"]:
        sponsor = s["member_code"] or s["office"]
        if not sponsor:
            continue
        conn.execute("INSERT OR REPLACE INTO ie_sponsors (bill_key, sponsor, member_code, name, "
                     "office, is_primary) VALUES (?,?,?,?,?,?)",
                     (key, sponsor, s["member_code"], s["name"], s["office"], int(s["primary"])))
    for d in b["debates"]:
        conn.execute("INSERT OR REPLACE INTO ie_bill_debates (debate_uri, debate_section, bill_key, "
                     "date, title) VALUES (?,?,?,?,?)",
                     (d["uri"], d["section"], key, d["date"], d["title"]))
    return key


def pull_bills(conn, client, today, since=DAIL_START, current=(), tax=None, wl=None,
               log=print, budget=None):
    """Every bill with an event since the Dail's first day. Returns (read, ours, gaps)."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else empty_watchlist()
    try:
        recs, complete = fetch_all(client, "legislation", {"date_start": since}, "legislation",
                                   budget=budget, archive=True, size=1000)
    except (FetchError, ValueError) as exc:
        _gap(conn, today, "legislation since {0}: {1}".format(since, exc))
        log("  [gap] legislation: {0}".format(str(exc)[:70]))
        return 0, 0, 1
    gaps = 0
    if not complete:
        log(budget.disclose("bill pages", len(recs)))
    if not recs:
        _gap(conn, today, "legislation since {0}: the API returned no bills".format(since))
        return 0, 0, 1
    read = ours = 0
    for rec in recs:
        try:
            b = parse_bill(rec, current)
        except (KeyError, TypeError, ValueError) as exc:
            _gap(conn, today, "bill record unreadable: {0}".format(exc))
            gaps += 1
            continue
        res = classify_bill(tax, wl, b)
        store_bill(conn, b, res, today)
        read += 1
        ours += on_our_ground(res.issue_areas)
    conn.commit()
    return read, ours, gaps


# --- divisions ---------------------------------------------------------------

def division_key(uri):
    """'.../division/house/dail/34/2026-10-06/vote_214' -> 'dail/34/2026-10-06/vote_214';
    '.../division/committee/<name>/<date>/vote_3' -> 'committee/<name>/<date>/vote_3'."""
    hit = re.search(r"/division/(?:house/)?(.+)$", uri or "")
    return hit.group(1) if hit else None


def parse_division(rec):
    d = rec.get("division") or rec
    house = d.get("house") or {}
    is_cmte = bool(house.get("committeeCode")) or "/committee/" in (d.get("uri") or "")
    debate = d.get("debate") or {}
    title = debate.get("showAs")
    named = BILL_IN_TITLE.match(title or "")
    out = {
        "key": division_key(d.get("uri")),
        "chamber": "committee" if is_cmte else (house.get("houseCode") or None),
        # A committee's House is its parent ('dail/34' for a joint committee
        # too: the API files every committee of this Oireachtas under the Dail).
        "house_key": house_key(house.get("uri")) or (
            "{0}/{1}".format(house["houseCode"], house["houseNo"])
            if house.get("houseCode") in ("dail", "seanad") and str(house.get("houseNo") or "").isdigit()
            else None),
        "committee": house.get("showAs") if is_cmte else None,
        "date": d.get("date"), "vote_id": d.get("voteId"),
        "debate_title": title, "debate_uri": debate.get("uri"),
        "debate_section": debate.get("debateSection"),
        "subject": ((d.get("subject") or {}).get("showAs") or "").strip() or None,
        "outcome": d.get("outcome"),
        "tellers": d.get("tellers") or None, "vote_note": (d.get("voteNote") or "").strip() or None,
        "debate_bill": named.group(1).strip() if named else None,
        "positions": [],
    }
    tallies = d.get("tallies") or {}
    for field, position in POSITIONS:
        t = tallies.get(field) or {}
        out[{"taVotes": "ta", "nilVotes": "nil", "staonVotes": "staon"}[field]] = t.get("tally")
        for mm in t.get("members") or []:
            code = (mm.get("member") or {}).get("memberCode")
            if code:
                out["positions"].append({"member_code": code, "position": position,
                                         "name": (mm.get("member") or {}).get("showAs")})
    return out


def join_bill(conn, d):
    """The bill whose record lists this division's debate section, or None.

    Returns (bill_key, candidates): candidates > 1 means the section carries
    two bills, and no bill is chosen for it."""
    if not d["debate_uri"] or not d["debate_section"]:
        return None, 0
    rows = [r[0] for r in conn.execute(
        "SELECT DISTINCT bill_key FROM ie_bill_debates WHERE debate_uri=? AND debate_section=?",
        (d["debate_uri"], d["debate_section"]))]
    return (rows[0] if len(rows) == 1 else None), len(rows)


def classify_division(tax, wl, d, bill_areas):
    """(own FilterResult, combined areas). The bill lends its areas."""
    own = filt.filter_item(tax, wl, strip_offices(d.get("debate_title")),
                           strip_offices(d.get("subject")),
                           title=strip_offices(d.get("debate_title")))
    return own, sorted(set(own.issue_areas or []) | set(bill_areas or []))


def _bill_areas(conn, key):
    if not key:
        return []
    row = conn.execute("SELECT areas FROM ie_bills WHERE bill_key=?", (key,)).fetchone()
    return json.loads(row[0] or "[]") if row else []


class PartyBook:
    """Party AT A DATE, from the stored party spells. Never the latest party."""

    def __init__(self, conn):
        self.spells = {}
        for code, hk, party, start, end in conn.execute(
                "SELECT member_code, house_key, party, start_date, end_date FROM ie_member_parties"):
            self.spells.setdefault(code, []).append((hk, party, start, end))

    def at(self, code, date, house=None):
        """The party of the spell covering `date` (in `house` when given), or None.

        The Oireachtas dates a party change on both spells (Eoin Hayes:
        Social Democrats to 2025-01-10, Independent from 2025-01-10), so on
        that day the spell that STARTS then is the one in force. A committee
        division has no House of its own here, so any of the member's spells
        covering the date will do; two that still disagree give None."""
        hits = [(start, party) for hk, party, start, end in self.spells.get(code, [])
                if (house is None or hk == house) and start and start <= date
                and (end is None or date <= end)]
        if not hits:
            return None
        latest = max(start for start, _ in hits)
        parties = {party for start, party in hits if start == latest}
        return parties.pop() if len(parties) == 1 else None


def store_division(conn, d, tax, wl, today, parties):
    """Store one division and its votes. Returns (areas, gap details)."""
    gaps = []
    bkey, candidates = join_bill(conn, d)
    if candidates > 1:
        gaps.append("{0}: debate section {1} carries {2} bills; none joined".format(
            d["key"], d["debate_section"], candidates))
    own, areas = classify_division(tax, wl, d, _bill_areas(conn, bkey))
    conn.execute(
        "INSERT INTO ie_divisions (division_key, chamber, house_key, committee, date, vote_id, "
        "debate_title, debate_uri, debate_section, subject, outcome, ta, nil, staon, tellers, "
        "vote_note, bill_key, debate_bill, own_areas, areas, matched_terms, tier, first_seen, "
        "last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET outcome=excluded.outcome, ta=excluded.ta, "
        "nil=excluded.nil, staon=excluded.staon, tellers=excluded.tellers, "
        "vote_note=excluded.vote_note, debate_title=excluded.debate_title, "
        "subject=excluded.subject, bill_key=excluded.bill_key, debate_bill=excluded.debate_bill, "
        "own_areas=excluded.own_areas, areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen",
        (d["key"], d["chamber"], d["house_key"], d["committee"], d["date"], d["vote_id"],
         d["debate_title"], d["debate_uri"], d["debate_section"], d["subject"], d["outcome"],
         d["ta"], d["nil"], d["staon"], d["tellers"], d["vote_note"], bkey, d["debate_bill"],
         ie_store.dumps(own.issue_areas), ie_store.dumps(areas),
         ie_store.dumps(own.matched_terms), own.tier, today, today))
    no_party = []
    for p in d["positions"]:
        party = parties.at(p["member_code"], d["date"],
                           None if d["chamber"] == "committee" else d["house_key"])
        if party is None:
            no_party.append(p["member_code"])
        conn.execute("INSERT OR REPLACE INTO ie_votes (division_key, member_code, position, party) "
                     "VALUES (?,?,?,?)", (d["key"], p["member_code"], p["position"], party))
    if no_party:
        gaps.append("{0}: no party spell covers {1} on {2}".format(
            d["key"], ", ".join(sorted(no_party)), d["date"]))
    return areas, gaps


def pull_divisions(conn, client, today, houses, since=DAIL_START, committees=True, tax=None,
                   wl=None, log=print, budget=None):
    """Every division of each House, and committee divisions since `since`.
    Returns (stored, ours, gaps)."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else empty_watchlist()
    parties = PartyBook(conn)
    lists = [("{0}/{1}".format(c, n), {"chamber_id": HOUSE_URI.format(c, n)}) for c, n in houses]
    if committees:
        lists.append(("committee", {"chamber_type": "committee", "date_start": since,
                                    "date_end": "2099-12-31"}))
    stored = ours = gaps = 0
    for label, params in lists:
        try:
            recs, complete = fetch_all(client, "votes", params, "votes-" + label.replace("/", "-"),
                                       budget=budget)
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "votes {0}: {1}".format(label, exc))
            log("  [gap] votes {0}: {1}".format(label, str(exc)[:70]))
            gaps += 1
            continue
        if not complete:
            log(budget.disclose("division pages ({0})".format(label), len(recs)))
        for rec in recs:
            d = parse_division(rec)
            if not d["key"] or not d["date"]:
                _gap(conn, today, "votes {0}: a division with no URI or date".format(label))
                gaps += 1
                continue
            areas, problems = store_division(conn, d, tax, wl, today, parties)
            for detail in problems:
                _gap(conn, today, detail)
                log("  [gap] " + detail[:110])
                gaps += 1
            stored += 1
            ours += on_our_ground(areas)
        conn.commit()
        log("  votes {0}: {1} division(s)".format(label, len(recs)))
    return stored, ours, gaps


# --- offline -----------------------------------------------------------------

def reclassify(conn, tax=None, log=print, watch_path=None):
    """Re-derive bill areas, then division areas, offline, after a taxonomy
    or watchlist change. Bills first: divisions inherit from them."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = empty_watchlist()
    changed_b = changed_d = 0
    for key, year, number, title, long_title, areas in conn.execute(
            "SELECT bill_key, year, number, title, long_title, areas FROM ie_bills").fetchall():
        b = {"year": year, "number": number, "title": title, "long_title": long_title}
        res = classify_bill(tax, wl, b, watch_path)
        new = ie_store.dumps(res.issue_areas)
        changed_b += new != (areas or "[]")
        conn.execute("UPDATE ie_bills SET areas=?, matched_terms=?, tier=? WHERE bill_key=?",
                     (new, ie_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, key))
    for key, bkey, title, subject, areas in conn.execute(
            "SELECT division_key, bill_key, debate_title, subject, areas "
            "FROM ie_divisions").fetchall():
        own, combined = classify_division(tax, wl, {"debate_title": title, "subject": subject},
                                          _bill_areas(conn, bkey))
        new = ie_store.dumps(combined)
        changed_d += new != (areas or "[]")
        conn.execute("UPDATE ie_divisions SET own_areas=?, areas=?, matched_terms=?, tier=? "
                     "WHERE division_key=?",
                     (ie_store.dumps(own.issue_areas), new, ie_store.dumps(own.matched_terms),
                      own.tier, key))
    conn.commit()
    log("ie-rollcalls: reclassified; {0} bill(s) and {1} division(s) changed area".format(
        changed_b, changed_d))
    return changed_b, changed_d


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = lambda sql: sum(on_our_ground(json.loads(a or "[]"))  # noqa: E731
                           for (a,) in conn.execute(sql))
    log("  store: {0} bill(s) ({1} alive), {2} on our ground; {3} division(s), {4} joined to a "
        "bill, {5} on our ground; {6} member(s), {7} vote(s), {8} sponsorship(s)".format(
            n("SELECT COUNT(*) FROM ie_bills"), n("SELECT COUNT(*) FROM ie_bills WHERE alive=1"),
            ours("SELECT areas FROM ie_bills"),
            n("SELECT COUNT(*) FROM ie_divisions"),
            n("SELECT COUNT(*) FROM ie_divisions WHERE bill_key IS NOT NULL"),
            ours("SELECT areas FROM ie_divisions"),
            n("SELECT COUNT(*) FROM ie_members"), n("SELECT COUNT(*) FROM ie_votes"),
            n("SELECT COUNT(*) FROM ie_sponsors")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dail", type=int, default=DAIL)
    ap.add_argument("--seanad", type=int, default=SEANAD)
    ap.add_argument("--since", default=DAIL_START,
                    help="bills and committee divisions with an event on or after this date")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"),
                    help="where the member and bill pages are archived")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--no-bills", action="store_true")
    ap.add_argument("--no-divisions", action="store_true")
    ap.add_argument("--no-committees", action="store_true", help="skip committee divisions")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored bills and divisions, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true",
                    help="read one page of members, bills and Dail divisions; store nothing")
    args = ap.parse_args()
    client = HttpClient(raw_dir=args.raw_dir)
    today = datetime.date.today().isoformat()
    houses = (("dail", args.dail), ("seanad", args.seanad))
    current = tuple("{0}/{1}".format(c, n) for c, n in houses)
    if args.dry_run:
        def one(path, params):
            q = urlencode(dict(params, limit=5), safe=":/", quote_via=quote)
            return client.get_json("{0}{1}?{2}".format(API, path, q), FEED, "dry", archive=False)
        mem = one("members", {"chamber_id": HOUSE_URI.format("dail", args.dail)})
        bills = one("legislation", {"date_start": args.since})
        votes = one("votes", {"chamber_id": HOUSE_URI.format("dail", args.dail)})
        d = parse_division(votes["results"][0]) if votes.get("results") else None
        print("ie-rollcalls: {0} member(s), {1} bill(s), {2} Dail division(s) listed; "
              "first listed division {3}: {4} vote(s)".format(
                  mem["head"]["counts"].get("memberCount"), bills["head"]["counts"].get("billCount"),
                  votes["head"]["counts"].get("divisionCount"), d["key"] if d else None,
                  len(d["positions"]) if d else 0))
        return 0
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn)
        summary(conn)
        conn.close()
        return 0
    tax = filt.load_taxonomy(TAXONOMY)
    wl = empty_watchlist()
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    if not args.no_members:
        n, g = pull_members(conn, client, today, houses)
        gaps += g
        print("ie-rollcalls: {0} member(s) of the {1}th Dail and {2}th Seanad, {3} gap(s)".format(
            n, args.dail, args.seanad, g))
    if not args.no_bills:
        read, ours, g = pull_bills(conn, client, today, since=args.since, current=current,
                                   tax=tax, wl=wl, budget=budget)
        gaps += g
        print("ie-rollcalls: {0} bill(s) read, {1} on our ground, {2} gap(s)".format(read, ours, g))
    if not args.no_divisions:
        stored, ours, g = pull_divisions(conn, client, today, houses, since=args.since,
                                         committees=not args.no_committees, tax=tax, wl=wl,
                                         budget=budget)
        gaps += g
        print("ie-rollcalls: {0} division(s) stored, {1} on our ground, {2} gap(s)".format(
            stored, ours, g))
    summary(conn)
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
