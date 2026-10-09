#!/usr/bin/env python3
"""US same-day vote brief: House roll calls (and Senate votes, from GitHub).

    python3 tools/us_division_brief.py                       # House, the last 2 days
    python3 tools/us_division_brief.py --chamber senate      # Senate (GitHub's network only)
    python3 tools/us_division_brief.py --since 2026-09-15 --no-dm --out /tmp/x

Christopher, 9 October 2026: "start the same-day vote briefs" (parity with
the UK division watch). Shared rules and rendering: src/vote_brief.py.

HOUSE. The Clerk posts each roll call as clerk.house.gov/evs/<year>/rollNNN.xml
within minutes. There is no index, and a roll that does not exist answers 200
with an error body, so the newest roll is found by bisection (about ten
small requests), then the walk goes DOWN from it until a roll is dated before
the window. "Since the last check" is that window (default two days): the
brief files are the memory, as in the UK brief, so no state file is shared
between the Mac Mini and GitHub.

CLASSIFIED AS THE COLLECTOR DOES (tools/us_rollcalls.classify_division): the
vote's own text, plus its bill's areas unless a House amendment vote has a
real purpose of its own. The bill comes from its own BILLSTATUS file on
GovInfo (one small keyless file per bill, the same record the weekly reads in
bulk), which also carries the House amendments with the rolls they were voted
on. BILLSTATUS lags the floor by days; with CONGRESS_API_KEY the purpose of a
same-day amendment vote is asked of Congress.gov, as the weekly does.
Without either, the brief says the purpose is not published yet.

SENATE. senate.gov refuses the Mac Mini's network (403, 9 October 2026) and
answers GitHub's runners, so the Senate half runs only on GitHub, in its own
ungated job of us-division-watch.yml. The menu (one request per session)
lists every vote with its date; each vote in the window is read from its
own file, whose amendment purpose is part of its own text.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import filter as filt, us_store, vote_brief  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
import us_rollcalls as usr  # noqa: E402  (read-only: its parsers and classifier)

FEED = "us-division-brief"
BILLSTATUS_ONE = "https://www.govinfo.gov/bulkdata/BILLSTATUS/{0}/{1}/BILLSTATUS-{0}{1}{2}.xml"
CLERK_PAGE = "https://clerk.house.gov/Votes/{0}{1}"
SENATE_PAGE = ("https://www.senate.gov/legislative/LIS/roll_call_votes/vote{0}{1}/"
               "vote_{0}_{1}_{2:05d}.htm")
WINDOW_DAYS = 2
MAX_ROLL = 2048          # no House session has reached 1,000 roll calls
PARTY = {"R": "Republican", "D": "Democrat", "I": "Independent"}
HOUSE_POSITIONS = ("Yea", "Nay", "Present", "Not Voting")


def is_vote(raw):
    return usr.parse_roll(raw) is not None


def newest_roll(client, year, log=print):
    """The highest roll call of `year`, by bisection, or 0 for none.

    A hole between real votes (the Clerk's error page in the middle) can stop
    a bisection short, so the answer is checked against the next
    MISSES_TO_STOP rolls and the search goes on from any vote found there."""
    def probe(n):
        try:
            return is_vote(client.get_bytes(usr.ROLL.format(year, n), FEED,
                                            "probe-{0}-{1}".format(year, n), archive=False))
        except FetchError:
            return False
    lo, hi = 0, MAX_ROLL
    while True:
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if probe(mid):
                lo = mid
            else:
                hi = mid
        ahead = next((lo + k for k in range(1, usr.MISSES_TO_STOP + 1) if probe(lo + k)), None)
        if ahead is None:
            return lo
        lo, hi = ahead, MAX_ROLL


def bill_record(client, key, cache):
    """The BILLSTATUS record for '119/hr/8800', or None. One file per bill."""
    if not key:
        return None
    if key not in cache:
        congress, btype, number = key.split("/")
        try:
            raw = client.get_bytes(BILLSTATUS_ONE.format(congress, btype, number), FEED,
                                   "billstatus-{0}".format(key.replace("/", "-")))
            cache[key] = usr.parse_billstatus(raw)
        except (FetchError, ET.ParseError):
            cache[key] = None
    return cache[key]


def amendment_purpose(client, d, bill, key=None):
    """(text, source) for a House amendment vote, or (None, why-not)."""
    dkey = usr.division_key(d)
    if bill:
        hits = [a for a in bill.get("amendments") or [] if dkey in a["rolls"]]
        if hits:
            a = usr.pick_amendment(hits, d.get("amendment_author"))
            if a["text"]:
                return a["text"], "BILLSTATUS"
    if key:
        try:
            vote = usr._cg(client, usr.CG_HOUSE_VOTE.format(d["congress"], d["session"], d["roll"]),
                           "cg-house-vote-{0}".format(dkey), key).get("houseRollCallVote") or {}
            atype, anum = vote.get("amendmentType"), vote.get("amendmentNumber")
            if atype and anum:
                record = usr._cg(client, usr.CG_AMENDMENT.format(d["congress"], atype.lower(), anum),
                                 "cg-amendment-{0}-{1}".format(atype, anum), key).get("amendment") or {}
                text = usr.amendment_text(record)
                if text:
                    return text, "Congress.gov"
        except (FetchError, ValueError, AttributeError):
            pass
    return None, "not published yet (BILLSTATUS lags the floor by days)"


def to_vote(d, bill, tax, wl, amendment=None, purpose_note=None):
    chamber = d.get("chamber") or "house"
    d = dict(d, chamber=chamber, amendment_text=amendment)
    bill_areas = usr.classify_bill(tax, wl, bill).issue_areas if bill else []
    own, areas = usr.classify_division(tax, wl, d, bill_areas)
    amend_own = (filt.filter_item(tax, wl, amendment).issue_areas if amendment else [])
    if usr.has_own_purpose(d) and vote_brief.visible(amend_own):
        matched = "amendment"
    elif vote_brief.visible(own.issue_areas):
        matched = "own text"
    else:
        matched = "bill only"
    key = usr.division_key(d)
    parties, names = {}, {}
    for p in d["positions"]:
        party = PARTY.get(p["party"], p["party"] or "?")
        parties.setdefault(party, {})
        parties[party][p["position"]] = parties[party].get(p["position"], 0) + 1
        names.setdefault(p["position"], []).append("{0} ({1}-{2})".format(
            p["name"] or p.get("bioguide") or p.get("lis_id"), p["party"] or "?", p["state"] or "?"))
    order = sorted(parties, key=lambda x: ({"Republican": 0, "Democrat": 1}.get(x, 2), x))
    bkey = usr.legis_bill_key(d.get("legis_num"), d["congress"])
    business = d.get("legis_num") or "No measure"
    if bill and bill.get("title"):
        business = "{0}: {1}".format(d["legis_num"], bill["title"])
    links = []
    if bkey:
        links.append(("the bill on Congress.gov", "https://www.congress.gov/bill/{0}th-congress/{1}/{2}".format(
            *_bill_url_parts(bkey))))
    notes = []
    if chamber == "house" and usr.is_amendment_vote(d.get("question")):
        who = d.get("amendment_author") or "an amendment"
        notes.append("Amendment vote: {0}. Purpose: {1}.".format(
            who, "as below" if amendment else purpose_note or "not published yet"))
    if chamber == "senate" and d.get("description"):
        notes.append("As the Senate records it: {0}".format(d["description"]))
    url = (SENATE_PAGE.format(d["congress"], d["session"], d["roll"]) if chamber == "senate"
           else CLERK_PAGE.format((d["date"] or "????")[:4], d["roll"]))
    return {
        "cc": "us", "key": key, "file_key": key, "date": d["date"],
        "house": "US {0}, roll call {1}".format("Senate" if chamber == "senate" else "House", d["roll"]),
        "business": business, "question": d.get("question"),
        "result": d.get("result"),
        "tally": "Yea {0}, Nay {1}, Present {2}, Not Voting {3}".format(
            d.get("yeas") or 0, d.get("nays") or 0, d.get("present") or 0, d.get("not_voting") or 0),
        "parties": [(p, parties[p]) for p in order], "split_positions": ("Yea", "Nay"),
        "positions": HOUSE_POSITIONS, "names": names, "matched": matched,
        "areas": areas, "terms": list(own.matched_terms or []), "url": url, "links": links,
        "amendment": amendment, "notes": notes,
        "on_ground": bool(vote_brief.visible(areas)),
    }


def _bill_url_parts(bkey):
    congress, btype, number = bkey.split("/")
    kind = {"hr": "house-bill", "s": "senate-bill", "hres": "house-resolution",
            "sres": "senate-resolution", "hjres": "house-joint-resolution",
            "sjres": "senate-joint-resolution", "hconres": "house-concurrent-resolution",
            "sconres": "senate-concurrent-resolution"}.get(btype, btype)
    return congress, kind, number


def house_votes(client, since, today, tax, wl, key=None, log=print):
    out, cache = [], {}
    for year in range(int(since[:4]), int(today[:4]) + 1):
        top = newest_roll(client, year, log)
        log("us: House {0}: newest roll call {1}".format(year, top or "none"))
        for n in range(top, 0, -1):
            try:
                raw = client.get_bytes(usr.ROLL.format(year, n), FEED, "roll-{0}-{1}".format(year, n))
            except FetchError as exc:
                log("  [gap] roll {0} of {1}: {2}".format(n, year, str(exc)[:70]))
                continue
            d = usr.parse_roll(raw)
            if d is None:
                continue
            if (d["date"] or "") < since:
                break
            if d["date"] > today:          # a historical --today: newer rolls are not in the window
                continue
            d["chamber"] = "house"
            bill = bill_record(client, usr.legis_bill_key(d["legis_num"], d["congress"]), cache)
            text, note = (None, None)
            if usr.is_amendment_vote(d.get("question")):
                text, note = amendment_purpose(client, d, bill, key)
            out.append(to_vote(d, bill, tax, wl, text, note))
    return out


def senate_votes(client, since, today, tax, wl, log=print):
    out, cache = [], {}
    congress = us_store.congress_on(today)
    for session, year in enumerate(usr.congress_years(congress), start=1):
        if year < int(since[:4]) or year > int(today[:4]):
            continue
        try:
            raw = client.get_bytes(usr.SENATE_MENU.format(congress, session), FEED,
                                   "senate-menu-{0}-{1}".format(congress, session))
        except FetchError as exc:
            log("  [gap] Senate menu {0}-{1}: {2} (senate.gov refuses some networks; it "
                "answers GitHub)".format(congress, session, str(exc)[:60]))
            raise
        for n, issue, date in menu_dates(raw, year):
            if date < since or date > today:
                continue
            try:
                d = usr.parse_senate_vote(client.get_bytes(
                    usr.SENATE_VOTE.format(congress, session, n), FEED,
                    "senate-{0}-{1}-{2}".format(congress, session, n)))
            except FetchError as exc:
                log("  [gap] Senate vote {0}: {1}".format(n, str(exc)[:70]))
                continue
            if d is None:
                continue
            d["legis_num"] = d["legis_num"] or issue
            bill = bill_record(client, usr.legis_bill_key(d["legis_num"], congress), cache)
            out.append(to_vote(d, bill, tax, wl))
    return out


def menu_dates(raw, year):
    """[(vote number, issue, ISO date)] from a Senate session menu ('18-Dec')."""
    root = ET.fromstring(raw)
    out = []
    for v in root.iter("vote"):
        n = usr._int(v, "vote_number")
        try:
            date = datetime.datetime.strptime("{0}-{1}".format(usr._text(v, "vote_date"), year),
                                              "%d-%b-%Y").date().isoformat()
        except (ValueError, TypeError):
            continue
        if n:
            out.append((n, usr._text(v, "issue"), date))
    return out


def collect(client, chamber, since, today, log=print):
    tax = filt.load_taxonomy(usr.TAXONOMY)
    wl = usr.empty_watchlist()
    if chamber == "senate":
        return senate_votes(client, since, today, tax, wl, log)
    return house_votes(client, since, today, tax, wl, usr.congress_key(), log)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chamber", choices=("house", "senate"), default="house")
    ap.add_argument("--since", default="", help="YYYY-MM-DD (default: {0} days ago)".format(WINDOW_DAYS))
    ap.add_argument("--today", default="", help="YYYY-MM-DD (default: today, UTC)")
    ap.add_argument("--force", action="store_true", help="rewrite and resend briefs that exist")
    ap.add_argument("--no-dm", action="store_true", help="print the DM instead of sending it")
    ap.add_argument("--out", default=vote_brief.BRIEFS)
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    args = ap.parse_args()
    today = args.today or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    since = args.since or vote_brief.window_start(today, WINDOW_DAYS)
    client = HttpClient(raw_dir=args.raw_dir)
    try:
        votes = collect(client, args.chamber, since, today)
    except FetchError:
        return 1
    vote_brief.run("us", votes, out_dir=args.out, force=args.force, dm=not args.no_dm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
