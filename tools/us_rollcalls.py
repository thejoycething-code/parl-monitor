#!/usr/bin/env python3
"""US Congress: members, bills with cosponsors, House roll calls and positions.

    python3 tools/us_rollcalls.py                     # the current Congress
    python3 tools/us_rollcalls.py --congress 118      # an earlier one
    python3 tools/us_rollcalls.py --dry-run           # count, store nothing
    python3 tools/us_rollcalls.py --reclassify        # re-derive areas, offline
    python3 tools/us_rollcalls.py --db /tmp/us.db     # anywhere but the store

PHASE 1 (9 October 2026). Nothing schedules this yet and no edition reads
its tables; see docs/us-scope.md. Every source is open, keyless and
official, except the members crosswalk:

  * govinfo.gov/bulkdata/BILLSTATUS/<congress>/<type>/BILLSTATUS-<c>-<t>.zip
    -- every bill of a type in ONE download (32 MB for House bills, about
    54 MB for all eight types), with titles, CRS subject terms, CRS
    summaries, sponsor and cosponsors. Far richer than a title: the
    taxonomy found 468 bills of the 119th on titles and 650 with these.
  * clerk.house.gov/evs/<year>/roll<NNN>.xml -- one House roll call per
    file, with every member's position, party AT THE VOTE and Bioguide ID.
  * unitedstates.github.io/congress-legislators/legislators-current.json --
    the volunteer crosswalk every US project uses; identity only, never votes.

THE CLERK ANSWERS 200 FOR A ROLL THAT DOES NOT EXIST. The body is
`<xml>Error sanitizing file "roll363.xml"...</xml>`, not a 404. The probe
of 9 October trusted the status and stored 640 error pages; parse_roll
returns None for anything without <vote-metadata>, and the walk stops at
the first run of misses.

A VOTE IS CLASSIFIED WITH ITS BILL. The Clerk's description line is blank
on most amendment and procedural votes: on its own text the taxonomy found
9 of the 119th's 676 roll calls; joined to the bill by number, 116. So
`areas` is the vote's own areas plus its bill's, and `own_areas` keeps the
first set apart. That matters for omnibus bills: every amendment vote on
an appropriations bill inherits "abortion" from the Hyde language in its
summary, which is always true and rarely news. Amendment purposes (phase
1b) need the Congress.gov key and are what will tell those votes apart.

EVERY POSITION IS STORED. Unlike Canada, the positions arrive in the same
file as the vote, so keeping them costs no request, and a vote that gains
an area on --reclassify needs no refetch.

CLASSIFICATION is the shared English taxonomy (v1.17 carries the American
addendum) plus config/watchlist-us.yaml, applied by bill KEY.

Separation guarantee: writes us_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import html
import io
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, us_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "us-rollcalls"
CURRENT_CONGRESS = 119
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
BILL_TYPES = ("hr", "s", "hres", "sres", "hjres", "sjres", "hconres", "sconres")
BILLSTATUS = "https://www.govinfo.gov/bulkdata/BILLSTATUS/{0}/{1}/BILLSTATUS-{0}-{1}.zip"
ROLL = "https://clerk.house.gov/evs/{0}/roll{1:03d}.xml"
MEMBERS = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
BUDGET_S = drain.DEFAULT_S
# Consecutive non-vote answers that end a year's walk. One would do on a
# clean day; three ride out a single transient error page without walking
# into the void.
MISSES_TO_STOP = 3
# Migration is collated, never campaigned (src/partner.py HIDDEN_AREAS).
HIDDEN_AREAS = (11,)

# The Clerk's legis-num -> BILLSTATUS type. Longest first: "H CON RES"
# must not be read as "H R".
LEGIS_TYPES = (("H CON RES", "hconres"), ("S CON RES", "sconres"),
               ("H J RES", "hjres"), ("S J RES", "sjres"),
               ("H RES", "hres"), ("S RES", "sres"), ("H R", "hr"), ("S", "s"))
POSITIONS = {"Yea": "Yea", "Aye": "Yea", "Nay": "Nay", "No": "Nay",
             "Present": "Present", "Not Voting": "Not Voting"}


def congress_years(congress):
    """(first, second) calendar years of a Congress: 119 -> (2025, 2026)."""
    first = 2 * int(congress) + 1787
    return first, first + 1


def bill_key(congress, bill_type, number):
    return "{0}/{1}/{2}".format(int(congress), bill_type.lower(), int(number))


def legis_bill_key(legis_num, congress):
    """'H R 8800' -> '119/hr/8800'; 'QUORUM', 'ADJOURN' or blank -> None."""
    text = re.sub(r"\s+", " ", (legis_num or "").replace(".", " ")).strip().upper()
    for prefix, kind in LEGIS_TYPES:
        hit = re.match(r"^{0} (\d+)$".format(re.escape(prefix)), text)
        if hit:
            return bill_key(congress, kind, hit.group(1))
    return None


def iso_date(clerk_date):
    """'6-Jan-2026' -> '2026-01-06'; anything unreadable is kept as given."""
    try:
        return datetime.datetime.strptime((clerk_date or "").strip(), "%d-%b-%Y").date().isoformat()
    except ValueError:
        return clerk_date or None


def _text(el, path):
    v = el.findtext(path) if el is not None else None
    return v.strip() if v and v.strip() else None


def _int(el, path):
    v = _text(el, path)
    try:
        return int(v) if v is not None else None
    except ValueError:
        return None


def strip_tags(markup):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup or ""))).strip() or None


# --- roll calls --------------------------------------------------------------

def parse_roll(raw):
    """One Clerk roll-call file -> dict, or None when it is not a vote.

    None covers the Clerk's 200-with-an-error-body answer for a roll that
    does not exist, and anything else without <vote-metadata>."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None
    meta = root.find("vote-metadata")
    if meta is None:
        return None
    totals = meta.find("vote-totals/totals-by-vote")
    session = (_text(meta, "session") or "")[:1]
    out = {
        "congress": _int(meta, "congress"),
        "session": int(session) if session.isdigit() else None,
        "roll": _int(meta, "rollcall-num"),
        "date": iso_date(_text(meta, "action-date")),
        "legis_num": _text(meta, "legis-num"),
        "question": _text(meta, "vote-question"),
        "description": _text(meta, "vote-desc"),
        "vote_type": _text(meta, "vote-type"),
        "result": _text(meta, "vote-result"),
        "amendment_num": _text(meta, "amendment-num"),
        "amendment_author": _text(meta, "amendment-author"),
        "yeas": _int(totals, "yea-total"),
        "nays": _int(totals, "nay-total"),
        "present": _int(totals, "present-total"),
        "not_voting": _int(totals, "not-voting-total"),
        "positions": [],
    }
    for rv in root.findall("vote-data/recorded-vote"):
        leg = rv.find("legislator")
        if leg is None or not leg.get("name-id"):
            continue
        said = _text(rv, "vote")
        out["positions"].append({
            "bioguide": leg.get("name-id"),
            "name": (leg.text or "").strip() or leg.get("unaccented-name"),
            "party": leg.get("party"), "state": leg.get("state"),
            # The Speaker's election records a NAME as the vote; keep it raw.
            "position": POSITIONS.get(said, said),
        })
    return out


def division_key(d, chamber="house"):
    return "{0}-{1}-{2}-{3}".format(chamber, d["congress"], d["session"], d["roll"])


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def classify_division(tax, wl, d, bill_areas):
    """(own FilterResult, combined areas). The bill lends its areas: see the
    module docstring for why, and for what that costs on omnibus bills."""
    own = filt.filter_item(tax, wl, d.get("description") or "", d.get("question") or "",
                           d.get("amendment_author") or "")
    return own, sorted(set(own.issue_areas or []) | set(bill_areas or []))


def _bill_areas(conn, key):
    if not key:
        return []
    row = conn.execute("SELECT areas FROM us_bills WHERE bill_key=?", (key,)).fetchone()
    return json.loads(row[0] or "[]") if row else []


def store_division(conn, d, tax, wl, today):
    key = division_key(d)
    bkey = legis_bill_key(d["legis_num"], d["congress"])
    own, areas = classify_division(tax, wl, d, _bill_areas(conn, bkey))
    conn.execute(
        "INSERT INTO us_divisions (division_key, chamber, congress, session, roll, date, "
        "legis_num, bill_key, question, description, vote_type, result, amendment_num, "
        "amendment_author, yeas, nays, present, not_voting, own_areas, areas, "
        "matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET result=excluded.result, "
        "yeas=excluded.yeas, nays=excluded.nays, present=excluded.present, "
        "not_voting=excluded.not_voting, bill_key=excluded.bill_key, "
        "own_areas=excluded.own_areas, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (key, "house", d["congress"], d["session"], d["roll"], d["date"], d["legis_num"],
         bkey, d["question"], d["description"], d["vote_type"], d["result"],
         d["amendment_num"], d["amendment_author"], d["yeas"], d["nays"], d["present"],
         d["not_voting"], us_store.dumps(own.issue_areas), us_store.dumps(areas),
         us_store.dumps(own.matched_terms), own.tier, today, today))
    for p in d["positions"]:
        conn.execute(us_store.MEMBER_UPSERT,
                     (p["bioguide"], None, p["party"], p["state"], None, "house", None,
                      d["date"], today, today))
        fill_name(conn, p["bioguide"], p["name"])
        conn.execute("INSERT OR REPLACE INTO us_votes (division_key, bioguide, position, "
                     "party, state) VALUES (?,?,?,?,?)",
                     (key, p["bioguide"], p["position"], p["party"], p["state"]))
    return key, areas


def display_name(full):
    """'Rep. Steube, W. Gregory [R-FL-17]' -> 'W. Gregory Steube'."""
    hit = re.match(r"^(?:Rep\.|Sen\.|Del\.|Resident Commissioner)?\s*([^,\[]+),\s*([^\[]+?)\s*(?:\[|$)",
                   (full or "").strip())
    return "{0} {1}".format(hit.group(2).strip(), hit.group(1).strip()) if hit else None


def fill_name(conn, bioguide, name):
    """A name only where the store has none. The crosswalk's official name
    wins; this covers members who have left, whom it no longer lists."""
    if name:
        conn.execute("UPDATE us_members SET name=? WHERE bioguide=? AND name IS NULL",
                     (name, bioguide))


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def pull_rolls(conn, client, today, congress=CURRENT_CONGRESS, tax=None, wl=None,
               log=print, limit=None, budget=None, years=None):
    """Walk each year of the Congress from the roll after the last one stored.

    Returns (stored, ours, gaps). Resuming from the store means a run cut
    short by the budget or the cap picks up where it stopped, and the
    weekly run costs one miss per year once the House is caught up."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else empty_watchlist()
    stored = ours = gaps = 0
    this_year = datetime.date.fromisoformat(today).year
    for session, year in enumerate(years or congress_years(congress), start=1):
        if year > this_year:
            continue
        (last,) = conn.execute("SELECT COALESCE(MAX(roll), 0) FROM us_divisions WHERE "
                               "chamber='house' AND congress=? AND session=?",
                               (congress, session)).fetchone()
        roll, misses = last + 1, 0
        while misses < MISSES_TO_STOP:
            if limit is not None and stored >= limit:
                log("  fetch cap ({0}) reached; the rest lands on the next run "
                    "-- disclosed, not silent".format(limit))
                return stored, ours, gaps
            if budget is not None and budget.exhausted():
                log(budget.disclose("House roll calls", stored))
                return stored, ours, gaps
            try:
                raw = client.get_bytes(ROLL.format(year, roll), FEED,
                                       "roll-{0}-{1}".format(year, roll), archive=False)
            except FetchError as exc:
                # A real HTTP failure, not the Clerk's 200-error page. Stop the
                # year rather than skip: the next run resumes from this roll.
                _gap(conn, today, "{0} roll {1}: {2}".format(year, roll, exc))
                log("  [gap] {0} roll {1}: {2}".format(year, roll, str(exc)[:70]))
                gaps += 1
                break
            d = parse_roll(raw)
            if d is None:
                misses += 1
                roll += 1
                continue
            if misses:
                # Error pages BETWEEN real votes: a hole, not the end. Say so.
                _gap(conn, today, "{0}: rolls {1}-{2} answered with no vote".format(
                    year, roll - misses, roll - 1))
                gaps += 1
            misses = 0
            _key, areas = store_division(conn, d, tax, wl, today)
            conn.commit()
            stored += 1
            ours += on_our_ground(areas)
            roll += 1
    return stored, ours, gaps


# --- bills -------------------------------------------------------------------

def _latest_summary(bill):
    best = None
    for s in bill.findall("summaries/summary"):
        stamp = (_text(s, "updateDate") or "", _text(s, "actionDate") or "")
        if best is None or stamp >= best[0]:
            best = (stamp, _text(s, "text"))
    return strip_tags(best[1]) if best else None


def parse_billstatus(raw):
    """One BILLSTATUS XML record -> dict, or None if it has no <bill>."""
    bill = ET.fromstring(raw).find("bill")
    if bill is None:
        return None
    title = _text(bill, "title")
    titles = []
    for t in bill.findall("titles/item"):
        v = _text(t, "title")
        if v and v != title and v not in titles:
            titles.append(v)
    cos = []
    for c in bill.findall("cosponsors/item"):
        if not _text(c, "bioguideId"):
            continue
        cos.append({"bioguide": _text(c, "bioguideId"), "name": _text(c, "fullName"),
                    "party": _text(c, "party"), "state": _text(c, "state"),
                    "district": _text(c, "district"),
                    "sponsored_at": _text(c, "sponsorshipDate"),
                    "withdrawn_at": _text(c, "sponsorshipWithdrawnDate"),
                    "original": (_text(c, "isOriginalCosponsor") or "").lower() == "true"})
    sp = bill.find("sponsors/item")
    law = bill.find("laws/item")
    return {
        "congress": _int(bill, "congress"),
        "type": (_text(bill, "type") or "").lower(),
        "number": _int(bill, "number"),
        "title": title,
        "titles": titles,
        "policy_area": _text(bill, "policyArea/name"),
        "subjects": [s for s in (_text(i, "name") for i in
                                 bill.findall("subjects/legislativeSubjects/item")) if s],
        "summary": _latest_summary(bill),
        "introduced": _text(bill, "introducedDate"),
        "sponsor": {"bioguide": _text(sp, "bioguideId"), "name": _text(sp, "fullName"),
                    "party": _text(sp, "party"), "state": _text(sp, "state"),
                    "district": _text(sp, "district")} if sp is not None else None,
        "cosponsors": cos,
        "latest_action": _text(bill, "latestAction/text"),
        "latest_action_at": _text(bill, "latestAction/actionDate"),
        "law": ("{0} {1}".format(_text(law, "type") or "Public Law", _text(law, "number"))
                if law is not None and _text(law, "number") else None),
        "update_date": _text(bill, "updateDate"),
    }


def classify_bill(tax, wl, b):
    """Title first (filter_item's convention), then every other title, the
    CRS subject terms and the latest CRS summary."""
    res = filt.filter_item(tax, wl, b["title"] or "", *b["titles"],
                           " ; ".join(b["subjects"]), b["summary"] or "",
                           title=b["title"] or "")
    return us_store.add_watch_areas(res, bill_key(b["congress"], b["type"], b["number"]))


def store_bill(conn, b, res, today):
    key = bill_key(b["congress"], b["type"], b["number"])
    sp = b["sponsor"] or {}
    current = [c for c in b["cosponsors"] if not c["withdrawn_at"]]
    conn.execute(
        "INSERT INTO us_bills (bill_key, congress, bill_type, number, title, short_titles, "
        "policy_area, subjects, summary, introduced, sponsor, sponsor_name, cosponsors, "
        "latest_action, latest_action_at, law, update_date, areas, matched_terms, tier, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(bill_key) DO UPDATE SET title=excluded.title, "
        "short_titles=excluded.short_titles, policy_area=excluded.policy_area, "
        "subjects=excluded.subjects, summary=excluded.summary, sponsor=excluded.sponsor, "
        "sponsor_name=excluded.sponsor_name, cosponsors=excluded.cosponsors, "
        "latest_action=excluded.latest_action, latest_action_at=excluded.latest_action_at, "
        "law=excluded.law, update_date=excluded.update_date, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (key, b["congress"], b["type"], b["number"], b["title"], us_store.dumps(b["titles"]),
         b["policy_area"], us_store.dumps(b["subjects"]), b["summary"], b["introduced"],
         sp.get("bioguide"), sp.get("name"), len(current), b["latest_action"],
         b["latest_action_at"], b["law"], b["update_date"],
         us_store.dumps(res.issue_areas),
         us_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
         res.tier, today, today))
    for person in ([sp] if sp.get("bioguide") else []) + b["cosponsors"]:
        conn.execute(us_store.MEMBER_UPSERT,
                     (person["bioguide"], None, person.get("party"), person.get("state"),
                      person.get("district"), None, None, None, today, today))
        fill_name(conn, person["bioguide"], display_name(person.get("name")))
    for c in b["cosponsors"]:
        conn.execute("INSERT OR REPLACE INTO us_cosponsors (bill_key, bioguide, sponsored_at, "
                     "withdrawn_at, original) VALUES (?,?,?,?,?)",
                     (key, c["bioguide"], c["sponsored_at"], c["withdrawn_at"],
                      int(c["original"])))
    return key


def pull_bills(conn, client, today, congress=CURRENT_CONGRESS, types=BILL_TYPES,
               tax=None, wl=None, log=print, budget=None):
    """Every bill of the Congress, one bulk zip per type. Returns (read, ours, gaps)."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else empty_watchlist()
    read = ours = gaps = 0
    for t in types:
        if budget is not None and budget.exhausted():
            log(budget.disclose("BILLSTATUS types", read))
            break
        try:
            blob = client.get_bytes(BILLSTATUS.format(congress, t), FEED,
                                    "billstatus-{0}-{1}".format(congress, t), archive=False)
            zf = zipfile.ZipFile(io.BytesIO(blob))
        except (FetchError, zipfile.BadZipFile) as exc:
            _gap(conn, today, "billstatus {0}/{1}: {2}".format(congress, t, exc))
            log("  [gap] billstatus {0}: {1}".format(t, str(exc)[:70]))
            gaps += 1
            continue
        n = 0
        for name in zf.namelist():
            if not name.endswith(".xml"):
                continue
            try:
                b = parse_billstatus(zf.read(name))
            except ET.ParseError as exc:
                _gap(conn, today, "billstatus {0}: {1}".format(name, exc))
                gaps += 1
                continue
            if not b or not b["number"]:
                continue
            res = classify_bill(tax, wl, b)
            store_bill(conn, b, res, today)
            ours += on_our_ground(res.issue_areas)
            n += 1
        conn.commit()
        read += n
        log("  {0}: {1} record(s)".format(t, n))
    return read, ours, gaps


# --- members -----------------------------------------------------------------

def parse_members(records):
    out = []
    for r in records or []:
        ids, term = r.get("id") or {}, (r.get("terms") or [{}])[-1]
        if not ids.get("bioguide"):
            continue
        name = (r.get("name") or {})
        out.append({"bioguide": ids["bioguide"],
                    "name": name.get("official_full") or " ".join(
                        x for x in (name.get("first"), name.get("last")) if x) or None,
                    "party": (term.get("party") or "")[:1] or None,
                    "state": term.get("state"),
                    "district": (None if term.get("type") != "rep" else
                                 ("AL" if term.get("district") == 0 else str(term.get("district")))),
                    "chamber": {"rep": "house", "sen": "senate"}.get(term.get("type")),
                    "lis_id": ids.get("lis"),
                    "as_of": term.get("start")})
    return out


def pull_members(conn, client, today):
    rows = parse_members(client.get_json(MEMBERS, FEED, "legislators-current", archive=False))
    for m in rows:
        conn.execute(us_store.MEMBER_UPSERT,
                     (m["bioguide"], m["name"], m["party"], m["state"], m["district"],
                      m["chamber"], m["lis_id"], m["as_of"], today, today))
    conn.commit()
    return len(rows)


# --- offline -----------------------------------------------------------------

def empty_watchlist():
    """The US watchlist is applied by KEY (us_store.add_watch_areas), so the
    filter itself gets no title entities."""
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def reclassify(conn, tax=None, log=print):
    """Re-derive bill areas, then division areas, offline, after a taxonomy
    or watchlist change. Bills first: divisions inherit from them."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = empty_watchlist()
    changed_b = changed_d = 0
    for (key, congress, btype, number, title, titles, subjects, summary,
         areas) in conn.execute(
            "SELECT bill_key, congress, bill_type, number, title, short_titles, subjects, "
            "summary, areas FROM us_bills").fetchall():
        b = {"congress": congress, "type": btype, "number": number, "title": title,
             "titles": json.loads(titles or "[]"), "subjects": json.loads(subjects or "[]"),
             "summary": summary}
        res = classify_bill(tax, wl, b)
        new = us_store.dumps(res.issue_areas)
        changed_b += new != (areas or "[]")
        conn.execute("UPDATE us_bills SET areas=?, matched_terms=?, tier=? WHERE bill_key=?",
                     (new, us_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, key))
    for (key, bkey, desc, question, author, areas) in conn.execute(
            "SELECT division_key, bill_key, description, question, amendment_author, areas "
            "FROM us_divisions").fetchall():
        d = {"description": desc, "question": question, "amendment_author": author}
        own, combined = classify_division(tax, wl, d, _bill_areas(conn, bkey))
        new = us_store.dumps(combined)
        changed_d += new != (areas or "[]")
        conn.execute("UPDATE us_divisions SET own_areas=?, areas=?, matched_terms=?, tier=? "
                     "WHERE division_key=?",
                     (us_store.dumps(own.issue_areas), new, us_store.dumps(own.matched_terms),
                      own.tier, key))
    conn.commit()
    log("us-rollcalls: reclassified; {0} bill(s) and {1} division(s) changed area".format(
        changed_b, changed_d))
    return changed_b, changed_d


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = lambda t: sum(on_our_ground(json.loads(a or "[]"))  # noqa: E731
                         for (a,) in conn.execute("SELECT areas FROM {0}".format(t)))
    log("  store: {0} bill(s), {1} on our ground; {2} House roll call(s), {3} on our "
        "ground; {4} member(s), {5} position(s), {6} cosponsorship(s)".format(
            n("SELECT COUNT(*) FROM us_bills"), ours("us_bills"),
            n("SELECT COUNT(*) FROM us_divisions"), ours("us_divisions"),
            n("SELECT COUNT(*) FROM us_members"), n("SELECT COUNT(*) FROM us_votes"),
            n("SELECT COUNT(*) FROM us_cosponsors")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--congress", type=int, default=CURRENT_CONGRESS)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--types", default=",".join(BILL_TYPES),
                    help="bill types to pull, comma-separated (default: all eight)")
    ap.add_argument("--no-bills", action="store_true")
    ap.add_argument("--no-rolls", action="store_true")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored bills and divisions, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--limit", type=int, help="stop after this many roll calls")
    ap.add_argument("--dry-run", action="store_true",
                    help="parse the first roll call of the Congress, store nothing")
    args = ap.parse_args()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    today = datetime.date.today().isoformat()
    if args.dry_run:
        year = congress_years(args.congress)[0]
        d = parse_roll(client.get_bytes(ROLL.format(year, 1), FEED, "dry", archive=False))
        print("us-rollcalls: {0} roll 1: {1}".format(
            year, "{0} position(s), {1}".format(len(d["positions"]), d["question"]) if d else
            "NOT A VOTE"))
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
        print("us-rollcalls: {0} current member(s) from the crosswalk".format(
            pull_members(conn, client, today)))
    if not args.no_bills:
        types = tuple(t.strip() for t in args.types.split(",") if t.strip())
        read, ours, g = pull_bills(conn, client, today, congress=args.congress,
                                   types=types, tax=tax, wl=wl, budget=budget)
        gaps += g
        print("us-rollcalls: {0} bill(s) read, {1} on our ground, {2} gap(s)".format(read, ours, g))
    if not args.no_rolls:
        stored, ours, g = pull_rolls(conn, client, today, congress=args.congress, tax=tax,
                                     wl=wl, limit=args.limit, budget=budget)
        gaps += g
        print("us-rollcalls: {0} new House roll call(s), {1} on our ground, {2} gap(s)".format(
            stored, ours, g))
    summary(conn)
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
