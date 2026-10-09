#!/usr/bin/env python3
"""Australia next-morning vote brief: House and Senate divisions.

    python3 tools/au_division_brief.py                       # files posted in the last 2 days
    python3 tools/au_division_brief.py --since 2026-09-14 --no-dm --out /tmp/x

Christopher, 9 October 2026: "start the same-day vote briefs" (parity with
the UK division watch). Shared rules and rendering: src/vote_brief.py.

THE SOURCE IS OPENAUSTRALIA'S PARSE OF HANSARD, read directly, no store:
data.openaustralia.org.au/scrapedxml/<chamber>_debates/<date>.xml, one file
per chamber per sitting day, with every member's vote and the Parliament's
own bill IDs (tools/au_rollcalls.parse_day). The parser runs daily at 09:05
Canberra time, so a sitting day's file appears the next morning there:
22:05 to 00:05 London, depending on the two countries' clocks. The Apache
index stamps each file, and "since the last check" is that stamp: a file
posted (or re-posted) within the window is read; the brief files remember
what was said.

Classified as tools/au_rollcalls.classify_division does: the headings, the
question and the nearest motion, plus every bill tagged on the debate
(classify_bill, with config/watchlist-au.yaml by bill ID). A vote's party is
the office spell's party (OpenAustralia members files; chairs resolved to
their party by tools/au_rollcalls.resolve_roles).
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

from src import filter as filt, vote_brief  # noqa: E402
from src.http import FetchError  # noqa: E402
import au_rollcalls as aur  # noqa: E402  (read-only: its parsers and classifier)

WINDOW_DAYS = 2          # by the listing's stamp
OLDEST_SITTING = 21      # a re-parse of an older day is not news
POSITIONS = ("Aye", "No", "Paired")


def offices(client):
    raws = {name: client.get_bytes(aur.MEMBERS.format(name), aur.FEED, "brief-members-" + name,
                                   archive=False)
            for name in aur.MEMBER_FILES}
    people = aur.parse_people(raws["people"])
    rows = aur.parse_offices(raws["representatives"]) + aur.parse_offices(raws["senators"])
    aur.resolve_roles(rows, people)
    return {o["office_id"]: o for o in rows}


def outcome(ayes, noes):
    """Arithmetic, not a verdict (tools/au_monitor.outcome)."""
    if ayes is None or noes is None:
        return "count not recorded"
    return "Agreed to" if ayes > noes else "Negatived" if noes > ayes else "Tied"


def to_vote(d, bills, office_map, tax, wl):
    bill_areas = [aur.classify_bill(tax, wl, bid, bills.get(bid)).issue_areas for bid in d["bills"]]
    own, areas = aur.classify_division(tax, wl, d, bill_areas)
    matched = "own text" if vote_brief.visible(own.issue_areas) else "bill only"
    parties, names = {}, {}
    for v in d["votes"]:
        o = office_map.get(v["office_id"]) or {}
        party = o.get("party") or "party not found"
        parties.setdefault(party, {})
        parties[party][v["position"]] = parties[party].get(v["position"], 0) + 1
        names.setdefault(v["position"], []).append("{0} ({1}{2})".format(
            v["name"] or o.get("name") or v["office_id"], party,
            ", " + o["electorate"] if o.get("electorate") else ""))
    order = sorted(parties, key=lambda x: (-sum(parties[x].values()), x))
    key = aur.division_key(d)
    notes = []
    if d["bills"]:
        notes.append("On: " + "; ".join("{0} ({1})".format(bills.get(b) or "?", b) for b in d["bills"][:4]))
    if d.get("motion"):
        notes.append("Nearest motion: " + " ".join(d["motion"].split())[:600])
    notes.append("Pairs are listed without a side: Hansard does not publish which side each "
                 "partner was on.")
    day_file = aur.DAY.format("senate" if d["chamber"] == "senate" else "representatives", d["date"])
    links = [("the Hansard day file (OpenAustralia)", day_file)] + [("the bill on ParlInfo", "https://parlinfo.aph.gov.au/parlInfo/search/display/"
              "display.w3p;query=Id:%22legislation/billhome/{0}%22".format(b)) for b in d["bills"][:2]]
    return {
        "cc": "au", "key": key, "file_key": key, "date": d["date"],
        "house": "{0}, division {1}".format("Senate" if d["chamber"] == "senate" else "House of Representatives",
                                            d["number"]),
        "business": " ".join(x for x in (d.get("major"), d.get("minor")) if x) or "?",
        "question": d.get("question"), "result": outcome(d["ayes"], d["noes"]),
        "tally": "Ayes {0}, Noes {1}{2}".format(d["ayes"], d["noes"],
                                                ", pairs {0}".format(d["pairs"]) if d.get("pairs") else ""),
        "parties": [(p, parties[p]) for p in order], "split_positions": ("Aye", "No"),
        "positions": POSITIONS, "names": names, "matched": matched, "areas": areas,
        "terms": list(own.matched_terms or []), "url": d.get("url") or day_file,
        "links": links, "amendment": None, "notes": notes,
        "on_ground": bool(vote_brief.visible(areas)),
    }


def collect(client, since_stamp, today, log=print, oldest=OLDEST_SITTING):
    tax = filt.load_taxonomy(aur.TAXONOMY)
    wl = aur.empty_watchlist()
    oldest_day = vote_brief.window_start(today, oldest)
    days = []
    for chamber, folder in aur.CHAMBERS:
        listing = aur.parse_listing(client.get_text(aur.LISTING.format(folder), aur.FEED,
                                                    "brief-listing-" + folder, archive=False))
        if not listing:
            raise FetchError(aur.LISTING.format(folder), aur.FEED, "listing", 1,
                             "no day files on the page (a challenge page?)")
        for date, modified in listing:
            if modified[:10] >= since_stamp and date >= oldest_day:
                days.append((chamber, folder, date, modified))
    log("au: {0} day file(s) posted since {1}: {2}".format(
        len(days), since_stamp, ", ".join("{0} {1} ({2})".format(c, d, m) for c, _f, d, m in days) or "none"))
    out, office_map = [], None
    for chamber, folder, date, _modified in days:
        try:
            day = aur.parse_day(client.get_bytes(aur.DAY.format(folder, date), aur.FEED,
                                                 "brief-{0}-{1}".format(chamber, date)), chamber, date)
        except (FetchError, ET.ParseError) as exc:
            log("  [gap] {0} {1}: {2}".format(chamber, date, str(exc)[:70]))
            continue
        for d in day["divisions"]:
            if office_map is None:
                office_map = offices(client)
            out.append(to_vote(d, day["bills"], office_map, tax, wl))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", default="", help="files stamped on or after YYYY-MM-DD "
                    "(default: {0} days ago)".format(WINDOW_DAYS))
    ap.add_argument("--today", default="", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--force", action="store_true", help="rewrite and resend briefs that exist")
    ap.add_argument("--no-dm", action="store_true", help="print the DM instead of sending it")
    ap.add_argument("--out", default=vote_brief.BRIEFS)
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    args = ap.parse_args()
    today = args.today or datetime.date.today().isoformat()
    since = args.since or vote_brief.window_start(today, WINDOW_DAYS)
    client = aur.make_client(args.raw_dir)
    try:
        votes = collect(client, since, today, oldest=max(OLDEST_SITTING, (
            datetime.date.fromisoformat(today) - datetime.date.fromisoformat(since)).days + 7))
    except FetchError as exc:
        print("au: OpenAustralia did not answer: {0}".format(str(exc)[:120]))
        return 1
    vote_brief.run("au", votes, out_dir=args.out, force=args.force, dm=not args.no_dm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
