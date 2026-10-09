#!/usr/bin/env python3
"""Australia's Federal Parliament: members, bills, House and Senate divisions.

    python3 tools/au_rollcalls.py                     # the current (48th) Parliament
    python3 tools/au_rollcalls.py --dry-run           # list and parse one day, store nothing
    python3 tools/au_rollcalls.py --reclassify        # re-derive areas, offline
    python3 tools/au_rollcalls.py --db /tmp/au.db     # anywhere but the store

PHASE 1 (9 October 2026). See docs/australia-scope.md. No edition reads these
tables yet. Every source is open and keyless:

  * data.openaustralia.org.au/scrapedxml/<chamber>_debates/<date>.xml -- the
    OpenAustralia Foundation's parse of the official Hansard, one file per
    chamber per sitting day. Each division carries EVERY member's vote with an
    office ID that resolves to a person, and the debate it sits in carries
    the Parliament's own bill IDs (<bill id="r7532">). The official Hansard
    XML (ParlInfo) lists division names only ("Aldred, M. R. (Teller)"), so
    this parse is where identities come from.
  * data.openaustralia.org.au/members/{people,representatives,senators}.xml
    -- persons and their office spells, each spell with its party.
  * handbookapi.aph.gov.au/api/individuals -- the Parliamentary Handbook
    (official, OData): the APH's own member ID (PHID) beside ours.
  * api.prod.legislation.gov.au/v1/titles -- the Federal Register of
    Legislation: every Act made, with the bill it came from.

WWW.APH.GOV.AU AND PARLINFO REFUSE THE LAPTOP. Both answer every request,
robots.txt included, with an Azure WAF block (403), with our honest UA and
with curl's default alike (9 October 2026). Bills Search, the bills digests,
explanatory memoranda, Votes and Proceedings, the Journals of the Senate and
the e-petitions all live there. Not worked around (bot detection is never
worked around in this repo); the Hansard route above replaces it for bills
and divisions. See the scope doc.

A DIVISION IS CLASSIFIED WITH ITS BILLS. The division itself carries no
words: its own text is the debate's headings, the Chair's question and the
nearest motion ("I move ..."). Every bill tagged on the debate (cognate
debates tag several) lends its areas; `own_areas` keeps the first set apart.

OPENAUSTRALIA RE-PARSES OLD DAYS. All of June 2026 was rewritten on
25 August. So each day file's listing stamp is stored (au_hansard_files)
and a file is read again only when the stamp moves; a re-read upserts.

CLASSIFICATION is the shared English taxonomy plus config/watchlist-au.yaml,
applied by bill ID.

Separation guarantee: writes au_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import au_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "au-rollcalls"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
OA = "https://data.openaustralia.org.au"
LISTING = OA + "/scrapedxml/{0}_debates/"
DAY = OA + "/scrapedxml/{0}_debates/{1}.xml"
MEMBER_FILES = ("people", "representatives", "senators")
MEMBERS = OA + "/members/{0}.xml"
HANDBOOK = ("https://handbookapi.aph.gov.au/api/individuals?$filter=InCurrentParliament%20eq%20"
            "%27True%27&$select=PHID,FamilyName,GivenName,PreferredName,Electorate,"
            "SenateState,MPorSenator&$orderby=PHID&$top={0}&$skip={1}")
# The Handbook refuses $top over 100 with a 400 that names the limit.
HANDBOOK_PAGE = 100
FRL_ACTS = ("https://api.prod.legislation.gov.au/v1/titles?$filter=collection%20eq%20%27Act%27"
            "%20and%20year%20eq%20{0}&$select=id,name,makingDate,originatingBillUri&$top=500")
CHAMBERS = (("house", "representatives"), ("senate", "senate"))
# The Parliaments: (first sitting day, the day the House was dissolved). The
# 48th was elected on 3 May 2025 and first sat on 22 July 2025.
PARLIAMENTS = {47: ("2022-07-26", "2025-03-28"), 48: ("2025-07-22", None)}
CURRENT_PARLIAMENT = 48
# The lowest bill ID each Parliament can have introduced, by prefix. MEASURED
# 9 October 2026, because OpenAustralia resolves some bill tags BY TITLE and
# so pins the lapsed bill of the previous Parliament on the new one's debate:
# the 48th's Appropriation Bill (No. 1) 2025-2026 is r7354, and its debates
# also carry r7327, the 47th's bill of the same name, which lapsed at the
# dissolution of 28 March 2025. All eight House IDs from r7292 to r7329 seen
# on 48th sitting days have such a twin; r7333 to r7345 were introduced on
# the first sitting days. In the Senate, s1430 is the highest ID whose own
# title year (2024) proves an earlier Parliament, and s1446 the lowest seen
# otherwise. So: below r7330 or s1431 is an earlier Parliament's bill. It is
# stored as tagged (the source said it) but under its own Parliament, and
# every such tag is recorded as a gap.
FIRST_BILL_IDS = {48: {"r": 7330, "s": 1431}}
# The OpenAustralia mirror is a volunteer service behind Cloudflare: one
# request a second, not the repo's default 0.2s.
OA_THROTTLE_S = 1.0
BUDGET_S = drain.DEFAULT_S
GAPS_EXIT = 3          # stored what it could, recorded gaps: jobs/au-weekly.sh publishes
HIDDEN_AREAS = (11,)   # migration is collated, never campaigned (src/partner.py)
QUESTION_CHARS = 600
MOTION_CHARS = 2500
STATES = {"nsw": "NSW", "new south wales": "NSW", "vic": "VIC", "victoria": "VIC",
          "qld": "QLD", "queensland": "QLD", "wa": "WA", "western australia": "WA",
          "sa": "SA", "south australia": "SA", "tas": "TAS", "tasmania": "TAS",
          "act": "ACT", "australian capital territory": "ACT", "nt": "NT",
          "northern territory": "NT"}
BILL_ID = re.compile(r"^[rs]\d+$")
# OpenAustralia opens a separate office spell for the chairs and writes the
# ROLE where the party goes: Sue Lines (Labor) votes as "PRES" and Milton Dick
# (Labor) as "SPK". Measured 9 October 2026: 805 Senate votes stored under
# PRES and 663 under DPRES before this was resolved.
ROLE_PARTIES = ("PRES", "DPRES", "SPK", "CWM")


def _fold(text):
    text = unicodedata.normalize("NFKD", text or "")
    return re.sub(r"\s+", " ", "".join(c for c in text if not unicodedata.combining(c))).strip().lower()


def _squash(text):
    return re.sub(r"\s+", " ", text or "").strip() or None


def bill_parliament(bill_id, date):
    """The Parliament a bill belongs to: that of the sitting day it was named
    on, unless its ID is lower than that Parliament could have issued."""
    parl = parliament_of(date)
    floor = FIRST_BILL_IDS.get(parl, {}).get(bill_id[:1])
    if parl and floor and int(bill_id[1:]) < floor:
        return parl - 1
    return parl


def parliament_of(date):
    for number, (first, last) in sorted(PARLIAMENTS.items()):
        if date >= first and (last is None or date <= last):
            return number
    return None


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def office_id(raw):
    """'uk.org.publicwhip/member/857' -> 'member/857'; 'uk.org.publicwhip/lord/100969' -> 'lord/100969'."""
    hit = re.search(r"(member|lord)/(\d+)$", raw or "")
    return "{0}/{1}".format(*hit.groups()) if hit else None


def person_id(raw):
    hit = re.search(r"person/(\d+)$", raw or "")
    return hit.group(1) if hit else None


# --- members -----------------------------------------------------------------

def parse_people(raw):
    """people.xml -> {office_id: person_id}."""
    out = {}
    for p in ET.fromstring(raw).iter("person"):
        pid = person_id(p.get("id"))
        for o in p.iter("office"):
            oid = office_id(o.get("id"))
            if pid and oid:
                out[oid] = pid
    return out


def parse_offices(raw):
    """representatives.xml / senators.xml -> one dict per office spell."""
    out = []
    for m in ET.fromstring(raw).iter("member"):
        oid = office_id(m.get("id"))
        if not oid:
            continue
        out.append({"office_id": oid,
                    "house": "senate" if oid.startswith("lord/") else "house",
                    "name": " ".join(x for x in (m.get("firstname"), m.get("lastname")) if x) or None,
                    "lastname": m.get("lastname"),
                    "party": m.get("party") or None,
                    "electorate": m.get("division") or None,
                    "from_date": m.get("fromdate"), "to_date": m.get("todate")})
    return out


def resolve_roles(offices, people):
    """In place: a chair's spell gets role=<the role> and party=<the person's
    last real party before it>, from every spell they ever held. None when
    no earlier spell names one (never a guess)."""
    by_person = {}
    for o in offices:
        by_person.setdefault(people.get(o["office_id"]), []).append(o)
    for o in offices:
        if o["party"] not in ROLE_PARTIES:
            continue
        o["role"] = o["party"]
        earlier = [x for x in by_person.get(people.get(o["office_id"]), [])
                   if x["party"] not in ROLE_PARTIES and x.get("role") is None
                   and (x["from_date"] or "") <= (o["from_date"] or "")]
        o["party"] = max(earlier, key=lambda x: x["from_date"] or "")["party"] if earlier else None
    return offices


def electorate_key(house, electorate):
    e = _fold(electorate)
    return STATES.get(e, e.upper()) if house == "senate" else e


def phid_index(records):
    """{(house, folded surname, electorate or state): [PHID, ...]} from the Handbook."""
    idx = {}
    for r in records or []:
        roles = r.get("MPorSenator") or []
        house = "senate" if "Senator" in roles else "house"
        where = r.get("SenateState") if house == "senate" else r.get("Electorate")
        key = (house, _fold(r.get("FamilyName")), electorate_key(house, where))
        idx.setdefault(key, []).append(r.get("PHID"))
    return idx


def pull_handbook(client):
    """Every current member in the Handbook, a page of 100 at a time."""
    out, skip = [], 0
    while True:
        page = client.get_json(HANDBOOK.format(HANDBOOK_PAGE, skip), FEED,
                               "handbook-current-{0}".format(skip)).get("value") or []
        out.extend(page)
        if len(page) < HANDBOOK_PAGE or skip > 2000:
            return out
        skip += HANDBOOK_PAGE


def pull_members(conn, client, today, first_date, log=print):
    """Offices that overlap the Parliament, their persons, and the Handbook's
    PHID where exactly one current member matches. Returns (persons, gaps)."""
    raws = {}
    for name in MEMBER_FILES:
        raws[name] = client.get_bytes(MEMBERS.format(name), FEED, "members-" + name)
    people = parse_people(raws["people"])
    offices = parse_offices(raws["representatives"]) + parse_offices(raws["senators"])
    resolve_roles(offices, people)
    try:
        hb = pull_handbook(client)
    except (FetchError, ValueError, AttributeError) as exc:
        hb = []
        _gap(conn, today, "parliamentary handbook: {0}".format(exc))
        log("  [gap] parliamentary handbook: {0} (PHIDs left as they were)".format(str(exc)[:70]))
    idx = phid_index(hb)
    gaps = 0 if hb else 1
    persons = {}
    for o in offices:
        if (o["to_date"] or "9999") < first_date:
            continue
        pid = people.get(o["office_id"])
        if not pid:
            _gap(conn, today, "office {0} ({1}) has no person in people.xml".format(
                o["office_id"], o["name"]))
            gaps += 1
            continue
        conn.execute("INSERT OR REPLACE INTO au_offices (office_id, person_id, house, party, "
                     "role, electorate, from_date, to_date) VALUES (?,?,?,?,?,?,?,?)",
                     (o["office_id"], pid, o["house"], o["party"], o.get("role"),
                      o["electorate"], o["from_date"], o["to_date"]))
        best = persons.get(pid)
        if best is None or (o["from_date"] or "") >= (best["from_date"] or ""):
            persons[pid] = o
    matched = 0
    for pid, o in persons.items():
        current = (o["to_date"] or "") >= "9999"
        phid = None
        if current and hb:
            hits = idx.get((o["house"], _fold(o["lastname"]),
                            electorate_key(o["house"], o["electorate"]))) or []
            phid = hits[0] if len(hits) == 1 else None
            matched += phid is not None
        conn.execute(
            "INSERT INTO au_members (person_id, name, party, house, electorate, phid, current, "
            "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(person_id) DO UPDATE "
            "SET name=excluded.name, party=excluded.party, house=excluded.house, "
            "electorate=excluded.electorate, phid=COALESCE(excluded.phid, au_members.phid), "
            "current=excluded.current, last_seen=excluded.last_seen",
            (pid, o["name"], o["party"], o["house"], o["electorate"], phid, int(current),
             today, today))
    conn.commit()
    n_current = sum(1 for o in persons.values() if (o["to_date"] or "") >= "9999")
    if hb:
        log("  PHID crosswalk: {0} of {1} current member(s) matched exactly once".format(
            matched, n_current))
    return len(persons), gaps


# --- Hansard day files -------------------------------------------------------

LISTING_ROW = re.compile(r'href="(\d{4}-\d{2}-\d{2})\.xml">[^<]*</a>\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2})')


def parse_listing(html_text):
    """An Apache directory index -> [(date, modified)], oldest first."""
    return sorted(LISTING_ROW.findall(html_text or ""))


def _speech_text(el):
    return _squash("".join(el.itertext()))


def heading_stage(minor):
    """'X Bill 2026; Y Bill 2026; Second Reading' -> 'Second Reading'; None
    when the last part is itself a bill's name."""
    parts = [p.strip() for p in (minor or "").split(";") if p.strip()]
    if len(parts) < 2 or re.search(r"\bBills?\b", parts[-1]):
        return None
    return parts[-1]


def parse_day(raw, chamber, date):
    """One OpenAustralia day file -> {"bills": {id: title}, "stages": [...],
    "divisions": [...]}. A division's bills are those tagged in its section
    (since the last heading) or inside the division element itself."""
    root = ET.fromstring(raw)
    out = {"bills": {}, "stages": [], "divisions": []}
    major = minor = None
    section_bills, speeches = [], []
    for el in root:
        tag = el.tag
        if tag in ("major-heading", "minor-heading"):
            text = _squash("".join(el.itertext()))
            if tag == "major-heading":
                major, minor = text, None
            else:
                minor = text
            section_bills, speeches = [], []
        elif tag == "bills":
            for b in el.iter("bill"):
                bid = (b.get("id") or "").strip()
                if not BILL_ID.match(bid):
                    continue
                out["bills"].setdefault(bid, _squash("".join(b.itertext())))
                if bid not in section_bills:
                    section_bills.append(bid)
                stage = heading_stage(minor)
                if stage:
                    out["stages"].append((bid, stage))
        elif tag == "speech":
            speeches.append(_speech_text(el) or "")
        elif tag == "division":
            bills = list(section_bills)
            for b in el.iter("bill"):
                bid = (b.get("id") or "").strip()
                if BILL_ID.match(bid):
                    out["bills"].setdefault(bid, _squash("".join(b.itertext())))
                    if bid not in bills:
                        bills.append(bid)
            out["divisions"].append(parse_division(el, chamber, date, major, minor, bills, speeches))
    return out


def _last(speeches, pattern, start_at=None, limit=None):
    for text in reversed(speeches):
        hit = re.search(pattern, text or "", re.I)
        if hit:
            text = text[hit.start():] if start_at else text
            return text[:limit] if limit else text
    return None


def parse_division(el, chamber, date, major, minor, bills, speeches):
    count = el.find("divisioncount")
    count = count.attrib if count is not None else {}
    votes = []
    for ml in el.findall("memberlist"):
        side = {"aye": "Aye", "no": "No"}.get((ml.get("vote") or "").lower(), ml.get("vote"))
        for m in ml.findall("member"):
            votes.append({"office_id": office_id(m.get("id")), "name": _squash(m.text),
                          "position": {"aye": "Aye", "no": "No"}.get(
                              (m.get("vote") or "").lower(), side)})
    # The pairs list does not say which side each partner was on, so the
    # side is never guessed: both are 'Paired'.
    for pair in el.iter("pair"):
        for m in pair.findall("member"):
            votes.append({"office_id": office_id(m.get("id")), "name": _squash(m.text),
                          "position": "Paired"})

    def num(k):
        try:
            return int(count[k]) if k in count else None
        except ValueError:
            return None
    return {"chamber": chamber, "date": date, "number": int(el.get("divnumber") or 0),
            "time": el.get("time"), "major": major, "minor": minor, "bills": bills,
            "question": _last(speeches, r"the question is", start_at=True, limit=QUESTION_CHARS),
            "motion": _last(speeches, r"\bI move\b", start_at=True, limit=MOTION_CHARS),
            "ayes": num("ayes"), "noes": num("noes"), "pairs": num("pairs"),
            "url": el.get("url"), "votes": votes}


def division_key(d):
    return "{0}-{1}-{2}".format(d["chamber"], d["date"], d["number"])


# --- classification ----------------------------------------------------------

def empty_watchlist():
    """The AU watchlist is applied by bill ID (au_store.add_watch_areas), so the
    filter itself gets no title entities."""
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify_bill(tax, wl, bill_id, title, wl_path=None):
    res = filt.filter_item(tax, wl, title or "", title=title or "")
    return au_store.add_watch_areas(res, bill_id, wl_path)


def classify_division(tax, wl, d, bill_areas):
    """(own FilterResult, combined areas). The headings name the business;
    the question and motion say what was put. Debate speeches are left out:
    a speech that mentions abortion in passing is not a vote on it."""
    own = filt.filter_item(tax, wl, d.get("minor") or "", d.get("major") or "",
                           d.get("motion") or "", d.get("question") or "",
                           title=d.get("minor") or "")
    combined = set(own.issue_areas or [])
    for areas in bill_areas:
        combined |= set(areas or [])
    return own, sorted(combined)


def _bill_areas(conn, bill_ids):
    out = []
    for bid in bill_ids or []:
        row = conn.execute("SELECT areas FROM au_bills WHERE bill_id=?", (bid,)).fetchone()
        out.append(json.loads(row[0] or "[]") if row else [])
    return out


# --- storing -----------------------------------------------------------------

def store_bill(conn, tax, wl, bill_id, title, date, today, wl_path=None):
    res = classify_bill(tax, wl, bill_id, title, wl_path)
    conn.execute(
        "INSERT INTO au_bills (bill_id, parliament, origin, title, first_date, areas, "
        "matched_terms, tier, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(bill_id) DO UPDATE SET title=COALESCE(excluded.title, au_bills.title), "
        "parliament=MIN(COALESCE(au_bills.parliament, excluded.parliament), excluded.parliament), "
        "first_date=MIN(COALESCE(au_bills.first_date, excluded.first_date), excluded.first_date), "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen",
        (bill_id, bill_parliament(bill_id, date), "senate" if bill_id.startswith("s") else "house",
         title, date, au_store.dumps(res.issue_areas),
         au_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
         res.tier, today, today))
    return res


def store_stage(conn, bill_id, chamber, date, stage):
    conn.execute("UPDATE au_bills SET last_stage=?, last_stage_chamber=?, last_stage_date=? "
                 "WHERE bill_id=? AND COALESCE(last_stage_date, '') <= ?",
                 (stage, chamber, date, bill_id, date))


def store_division(conn, d, tax, wl, offices, today):
    """Returns (key, areas, unknown office IDs). A vote whose office nobody
    knows is dropped and reported, never stored under a guessed person."""
    key = division_key(d)
    own, areas = classify_division(tax, wl, d, _bill_areas(conn, d["bills"]))
    conn.execute(
        "INSERT INTO au_divisions (division_key, chamber, parliament, date, number, time, "
        "major_heading, minor_heading, bill_ids, question, motion, ayes, noes, pairs, own_areas, "
        "areas, matched_terms, tier, source_url, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET time=excluded.time, "
        "major_heading=excluded.major_heading, minor_heading=excluded.minor_heading, "
        "bill_ids=excluded.bill_ids, question=excluded.question, motion=excluded.motion, "
        "ayes=excluded.ayes, noes=excluded.noes, pairs=excluded.pairs, "
        "own_areas=excluded.own_areas, areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, source_url=excluded.source_url, last_seen=excluded.last_seen",
        (key, d["chamber"], parliament_of(d["date"]), d["date"], d["number"], d["time"],
         d["major"], d["minor"], au_store.dumps(d["bills"]), d["question"], d["motion"],
         d["ayes"], d["noes"], d["pairs"], au_store.dumps(own.issue_areas),
         au_store.dumps(areas), au_store.dumps(own.matched_terms), own.tier, d["url"],
         today, today))
    unknown = []
    for v in d["votes"]:
        o = offices.get(v["office_id"])
        if not o:
            unknown.append(v["office_id"] or v["name"] or "?")
            continue
        conn.execute("INSERT OR REPLACE INTO au_votes (division_key, person_id, office_id, "
                     "position, party, electorate) VALUES (?,?,?,?,?,?)",
                     (key, o[0], v["office_id"], v["position"], o[1], o[2]))
    return key, areas, unknown


def _offices(conn):
    return {oid: (pid, party, el) for oid, pid, party, el in conn.execute(
        "SELECT office_id, person_id, party, electorate FROM au_offices")}


def pull_days(conn, client, today, parliament=CURRENT_PARLIAMENT, tax=None, wl=None,
              log=print, limit=None, budget=None, wl_path=None):
    """Every sitting day of the Parliament whose file is new or re-parsed since
    it was read. Returns a dict of counts."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else empty_watchlist()
    first, last = PARLIAMENTS[parliament]
    offices = _offices(conn)
    # lapsed_tags are recorded in the gaps table but do not fail the run:
    # they are the source's known habit, not a fetch that went wrong.
    stats = {"files": 0, "divisions": 0, "ours": 0, "gaps": 0, "bills": set(), "lapsed_tags": 0}
    for chamber, folder in CHAMBERS:
        try:
            listing = parse_listing(client.get_text(LISTING.format(folder), FEED,
                                                    "listing-" + folder))
        except FetchError as exc:
            _gap(conn, today, "listing {0}: {1}".format(folder, exc))
            log("  [gap] {0} listing: {1}".format(folder, str(exc)[:70]))
            stats["gaps"] += 1
            continue
        if not listing:
            _gap(conn, today, "listing {0}: no day files on the page".format(folder))
            log("  [gap] {0} listing: no day files (a challenge page?)".format(folder))
            stats["gaps"] += 1
            continue
        held = dict(conn.execute("SELECT path, listed_modified FROM au_hansard_files "
                                 "WHERE chamber=?", (chamber,)))
        for date, modified in listing:
            if date < first or (last and date > last):
                continue
            path = "{0}_debates/{1}.xml".format(folder, date)
            if held.get(path) == modified:
                continue
            if limit is not None and stats["files"] >= limit:
                log("  fetch cap ({0}) reached; the rest lands on the next run "
                    "-- disclosed, not silent".format(limit))
                return stats
            if budget is not None and budget.exhausted():
                log(budget.disclose("Hansard day files", stats["files"]))
                return stats
            try:
                raw = client.get_bytes(DAY.format(folder, date), FEED,
                                       "{0}-{1}".format(chamber, date))
                day = parse_day(raw, chamber, date)
            except (FetchError, ET.ParseError) as exc:
                _gap(conn, today, "{0}: {1}".format(path, exc))
                log("  [gap] {0}: {1}".format(path, str(exc)[:70]))
                stats["gaps"] += 1
                continue
            for bid, title in day["bills"].items():
                store_bill(conn, tax, wl, bid, title, date, today, wl_path)
                stats["bills"].add(bid)
                if bill_parliament(bid, date) != parliament_of(date):
                    _gap(conn, today, "{0}: {1} is an earlier Parliament's bill ID, tagged "
                         "by title on this day's debate ({2})".format(path, bid, title))
                    stats["lapsed_tags"] += 1
            for bid, stage in day["stages"]:
                store_stage(conn, bid, chamber, date, stage)
            for d in day["divisions"]:
                key, areas, unknown = store_division(conn, d, tax, wl, offices, today)
                stats["divisions"] += 1
                stats["ours"] += on_our_ground(areas)
                if unknown:
                    _gap(conn, today, "{0}: no person for office(s) {1}".format(
                        key, ", ".join(sorted(set(unknown)))))
                    stats["gaps"] += 1
            conn.execute("INSERT OR REPLACE INTO au_hansard_files (path, chamber, date, "
                         "listed_modified, read_at, divisions) VALUES (?,?,?,?,?,?)",
                         (path, chamber, date, modified, today, len(day["divisions"])))
            conn.commit()
            stats["files"] += 1
    return stats


# --- Acts (Federal Register of Legislation) ---------------------------------

def bill_of_act(uri):
    """The ParlInfo bill link FRL gives an Act -> 'r7473', or None."""
    hit = re.search(r"billhome(?:%2F|/)([rs]\d+)", uri or "")
    return hit.group(1) if hit else None


def pull_acts(conn, client, today, parliament=CURRENT_PARLIAMENT, tax=None, wl=None,
              log=print, wl_path=None):
    """Mark every bill that became an Act. Returns (acts, matched, added, gaps).
    An Act whose bill the Hansard never tagged is added from the Act's name."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else empty_watchlist()
    first, last = PARLIAMENTS[parliament]
    this_year = int(today[:4])
    acts = matched = added = gaps = 0
    for year in range(int(first[:4]), int((last or today)[:4]) + 1):
        if year > this_year:
            break
        try:
            rows = client.get_json(FRL_ACTS.format(year), FEED, "frl-acts-{0}".format(year))
            rows = rows.get("value") or []
        except (FetchError, ValueError, AttributeError) as exc:
            _gap(conn, today, "FRL Acts {0}: {1}".format(year, exc))
            log("  [gap] FRL Acts {0}: {1}".format(year, str(exc)[:70]))
            gaps += 1
            continue
        for a in rows:
            made = (a.get("makingDate") or "")[:10]
            if made < first or (last and made > last):
                continue
            acts += 1
            bid = bill_of_act(a.get("originatingBillUri"))
            if not bid:
                continue
            if not conn.execute("SELECT 1 FROM au_bills WHERE bill_id=?", (bid,)).fetchone():
                store_bill(conn, tax, wl, bid, re.sub(r"\bAct\b", "Bill", a.get("name") or ""),
                           made, today, wl_path)
                added += 1
            else:
                matched += 1
            conn.execute("UPDATE au_bills SET act_id=?, act_name=?, assent_date=?, "
                         "last_seen=? WHERE bill_id=?",
                         (a.get("id"), a.get("name"), made, today, bid))
    conn.commit()
    return acts, matched, added, gaps


# --- offline -----------------------------------------------------------------

def reclassify(conn, tax=None, log=print, wl_path=None):
    """Re-derive bill areas, then division areas, offline. Bills first:
    divisions inherit from them."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = empty_watchlist()
    changed_b = changed_d = 0
    for bid, title, areas, first_date in conn.execute(
            "SELECT bill_id, title, areas, first_date FROM au_bills").fetchall():
        if first_date:
            conn.execute("UPDATE au_bills SET parliament=? WHERE bill_id=?",
                         (bill_parliament(bid, first_date), bid))
        res = classify_bill(tax, wl, bid, title, wl_path)
        new = au_store.dumps(res.issue_areas)
        changed_b += new != (areas or "[]")
        conn.execute("UPDATE au_bills SET areas=?, matched_terms=?, tier=? WHERE bill_id=?",
                     (new, au_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, bid))
    for key, major, minor, bills, question, motion, areas in conn.execute(
            "SELECT division_key, major_heading, minor_heading, bill_ids, question, motion, "
            "areas FROM au_divisions").fetchall():
        d = {"major": major, "minor": minor, "question": question, "motion": motion}
        own, combined = classify_division(tax, wl, d, _bill_areas(conn, json.loads(bills or "[]")))
        new = au_store.dumps(combined)
        changed_d += new != (areas or "[]")
        conn.execute("UPDATE au_divisions SET own_areas=?, areas=?, matched_terms=?, tier=? "
                     "WHERE division_key=?",
                     (au_store.dumps(own.issue_areas), new, au_store.dumps(own.matched_terms),
                      own.tier, key))
    conn.commit()
    log("au-rollcalls: reclassified; {0} bill(s) and {1} division(s) changed area".format(
        changed_b, changed_d))
    return changed_b, changed_d


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = lambda t: sum(on_our_ground(json.loads(a or "[]"))  # noqa: E731
                         for (a,) in conn.execute("SELECT areas FROM {0}".format(t)))
    log("  store: {0} bill(s) ({8} of them an earlier Parliament's ID), {1} on our ground, "
        "{2} became Acts; {3} division(s) (House and Senate), {4} on our ground; "
        "{5} member(s), {6} vote(s), {7} Hansard day file(s)".format(
            n("SELECT COUNT(*) FROM au_bills"), ours("au_bills"),
            n("SELECT COUNT(*) FROM au_bills WHERE act_id IS NOT NULL"),
            n("SELECT COUNT(*) FROM au_divisions"), ours("au_divisions"),
            n("SELECT COUNT(*) FROM au_members"), n("SELECT COUNT(*) FROM au_votes"),
            n("SELECT COUNT(*) FROM au_hansard_files"),
            n("SELECT COUNT(*) FROM au_bills WHERE parliament < {0}".format(CURRENT_PARLIAMENT))))


def make_client():
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    client.set_host_throttle("data.openaustralia.org.au", OA_THROTTLE_S)
    return client


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--parliament", type=int, default=CURRENT_PARLIAMENT,
                    choices=sorted(PARLIAMENTS))
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--no-days", action="store_true", help="skip the Hansard day files")
    ap.add_argument("--no-acts", action="store_true")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored bills and divisions, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--limit", type=int, help="stop after this many day files")
    ap.add_argument("--dry-run", action="store_true",
                    help="read both listings and the latest day, store nothing")
    args = ap.parse_args()
    client = make_client()
    today = datetime.date.today().isoformat()
    if args.dry_run:
        for chamber, folder in CHAMBERS:
            days = [d for d in parse_listing(client.get_text(
                LISTING.format(folder), FEED, "dry-listing-" + folder, archive=False))
                if d[0] >= PARLIAMENTS[args.parliament][0]]
            if not days:
                print("au-rollcalls: {0}: NO DAY FILES LISTED".format(chamber))
                continue
            date = days[-1][0]
            day = parse_day(client.get_bytes(DAY.format(folder, date), FEED, "dry", archive=False),
                            chamber, date)
            print("au-rollcalls: {0}: {1} sitting day(s) listed; {2}: {3} division(s), "
                  "{4} vote(s), {5} bill(s)".format(
                      chamber, len(days), date, len(day["divisions"]),
                      sum(len(d["votes"]) for d in day["divisions"]), len(day["bills"])))
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
    first = PARLIAMENTS[args.parliament][0]
    if not args.no_members:
        try:
            n, g = pull_members(conn, client, today, first)
        except (FetchError, ET.ParseError) as exc:
            _gap(conn, today, "members: {0}".format(exc))
            conn.commit()
            print("  [gap] members: {0}".format(str(exc)[:70]))
            n, g = 0, 1
        gaps += g
        print("au-rollcalls: {0} member(s) in the {1}th Parliament, {2} gap(s)".format(
            n, args.parliament, g))
    if not args.no_days:
        s = pull_days(conn, client, today, parliament=args.parliament, tax=tax, wl=wl,
                      limit=args.limit, budget=budget)
        gaps += s["gaps"]
        print("au-rollcalls: {0} Hansard day file(s) read; {1} division(s), {2} on our "
              "ground; {3} bill(s) named, {4} tag(s) of an earlier Parliament's bill ID; "
              "{5} gap(s)".format(s["files"], s["divisions"], s["ours"], len(s["bills"]),
                                  s["lapsed_tags"], s["gaps"]))
    if not args.no_acts:
        acts, matched, added, g = pull_acts(conn, client, today, parliament=args.parliament,
                                            tax=tax, wl=wl)
        gaps += g
        print("au-rollcalls: {0} Act(s) made; {1} joined to a stored bill, {2} bill(s) "
              "added from the Act; {3} gap(s)".format(acts, matched, added, g))
    # Divisions inherit from bills, and a bill can gain an area after its
    # division was stored (a watchlist entry, an Act's name): settle both.
    reclassify(conn)
    summary(conn)
    conn.close()
    return GAPS_EXIT if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
