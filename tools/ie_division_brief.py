#!/usr/bin/env python3
"""Ireland same-day vote brief: Dail, Seanad and committee divisions.

    python3 tools/ie_division_brief.py                       # the last 3 days
    python3 tools/ie_division_brief.py --since 2026-09-30 --no-dm --out /tmp/x

Christopher, 9 October 2026: "start the same-day vote briefs" (parity with
the UK division watch). Shared rules and rendering: src/vote_brief.py.

ONE SOURCE, READ DIRECTLY, NO STORE: the Oireachtas Open Data API.

  * /votes?chamber_id=<house>&date_start=&date_end=  -- each House's divisions
    in the window, every member's vote included; committee divisions by
    chamber_type=committee.
  * /legislation?date_start=<first day of the Dail>  -- every bill of this
    Dail (one request); each lists the debate sections that carried it, so a division is
    joined to its bill by (debate URI, section), an ID join, as the weekly does.
  * /members?chamber_id=<house>  -- party spells, so a vote is counted under
    the party the member held ON THE DAY (tools/ie_rollcalls.PartyBook).
  * The day's debate transcript, only for an amendment vote: the amendment
    as moved ("I move amendment No. 9 ..."), read by
    tools/ie_rollcalls.amendments_in. A transcript not yet published leaves
    the amendment unread, and the brief says so.

Classification is tools/ie_rollcalls.classify_division: the debate title,
the subject line and the amendment, plus the bill's areas (classify_bill,
with config/watchlist-ie.yaml by key). Nothing here is imported for writing;
those functions are read-only to this tool.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import filter as filt, vote_brief  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
import ie_rollcalls as ier  # noqa: E402  (read-only: its parsers and classifier)

WINDOW_DAYS = 3
POSITIONS = ("Tá (Yes)", "Níl (No)", "Staon (Abstain)")
LABEL = {"Yes": "Tá (Yes)", "No": "Níl (No)", "Abstain": "Staon (Abstain)"}
VOTE_PAGE = "https://www.oireachtas.ie/en/debates/vote/{0}/{1}/{2}/"


def party_book(members):
    """A PartyBook from /members records, without a store."""
    book = ier.PartyBook.__new__(ier.PartyBook)
    book.spells = {}
    for rec in members:
        m = ier.parse_member(rec)
        for s in m["memberships"]:
            for p in s["parties"]:
                book.spells.setdefault(m["code"], []).append((s["house_key"], p["party"], p["start"], p["end"]))
    return book


def bill_index(bills):
    """{(debate uri, section): [bill dict]} from /legislation records."""
    idx = {}
    for rec in bills:
        try:
            b = ier.parse_bill(rec)
        except (KeyError, TypeError, ValueError):
            continue
        for d in b["debates"]:
            idx.setdefault((d["uri"], d["section"]), [])
            if b not in idx[(d["uri"], d["section"])]:
                idx[(d["uri"], d["section"])].append(b)
    return idx


def is_amendment(subject):
    return (subject or "").startswith(ier.AMENDMENT_SUBJECTS)


def to_vote(d, bill, book, tax, wl, amendment=None, transcript_read=False):
    bill_areas = ier.classify_bill(tax, wl, bill).issue_areas if bill else []
    d = dict(d, amendment_text=amendment)
    own, areas = ier.classify_division(tax, wl, d, bill_areas)
    amend_own = filt.filter_item(tax, wl, ier.strip_offices(amendment)).issue_areas if amendment else []
    if vote_brief.visible(amend_own):
        matched = "amendment"
    elif vote_brief.visible(own.issue_areas):
        matched = "own text"
    else:
        matched = "bill only"
    house = None if d["chamber"] == "committee" else d["house_key"]
    parties, names = {}, {}
    for p in d["positions"]:
        party = book.at(p["member_code"], d["date"], house) or "party not found"
        pos = LABEL.get(p["position"], p["position"])
        parties.setdefault(party, {})
        parties[party][pos] = parties[party].get(pos, 0) + 1
        names.setdefault(pos, []).append("{0} ({1})".format(p["name"] or p["member_code"], party))
    order = sorted(parties, key=lambda x: (-sum(parties[x].values()), x))
    chamber = (d["committee"] or "Committee") if d["chamber"] == "committee" else \
        {"dail": "Dáil", "seanad": "Seanad"}.get(d["chamber"], d["chamber"])
    url = (VOTE_PAGE.format(d["house_key"], d["date"], (d["vote_id"] or "").replace("vote_", ""))
           if d["chamber"] in ("dail", "seanad") else ier.transcript_url(d["debate_uri"]))
    links = [("the debate transcript", ier.transcript_url(d["debate_uri"]))] if d["debate_uri"] else []
    if bill and bill.get("url"):
        links.append(("the bill", "https://www.oireachtas.ie/en/bills/bill/{0}/{1}/".format(
            bill["year"], bill["number"])))
    notes = []
    if bill:
        notes.append("Bill: {0} (Bill {1} of {2}), joined by its debate section.".format(
            bill["title"], bill["number"], bill["year"]))
    elif d.get("debate_bill"):
        notes.append("The debate names {0}, but no bill record lists this section: not joined.".format(
            d["debate_bill"]))
    if is_amendment(d["subject"]) and not amendment:
        notes.append("The amendment moved was not found before this division in the transcript"
                     if transcript_read else
                     "The amendment's text is not in a published transcript yet.")
    if d.get("tellers"):
        notes.append(d["tellers"])
    return {
        "cc": "ie", "key": d["key"], "file_key": vote_brief.safe_key(d["key"]), "date": d["date"],
        "house": "{0}, division {1}".format(chamber, (d["vote_id"] or "?").replace("vote_", "")),
        "business": d["debate_title"] or d["debate_bill"] or "?",
        "question": (d["subject"] or "").strip() or None, "result": d["outcome"],
        "tally": "Tá {0}, Níl {1}, Staon {2}".format(d["ta"] or 0, d["nil"] or 0, d["staon"] or 0),
        "parties": [(p, parties[p]) for p in order], "split_positions": POSITIONS,
        "positions": POSITIONS, "names": names, "matched": matched, "areas": areas,
        "terms": list(own.matched_terms or []), "url": url, "links": links,
        "amendment": amendment, "notes": notes, "on_ground": bool(vote_brief.visible(areas)),
    }


def collect(client, since, today, log=print):
    tax = filt.load_taxonomy(ier.TAXONOMY)
    wl = ier.empty_watchlist()
    window = {"date_start": since, "date_end": today}
    houses = (("dail", ier.DAIL), ("seanad", ier.SEANAD))
    raw = []
    for chamber, no in houses:
        recs, _ = ier.fetch_all(client, "votes", dict(window, chamber_id=ier.HOUSE_URI.format(chamber, no)),
                                "brief-votes-{0}-{1}".format(chamber, no), archive=True)
        raw += recs
    recs, _ = ier.fetch_all(client, "votes", dict(window, chamber_type="committee"),
                            "brief-votes-committee", archive=True)
    raw += recs
    divisions = [d for d in (ier.parse_division(r) for r in raw) if d["key"] and d["date"]]
    log("ie: {0} division(s) from {1} to {2}".format(len(divisions), since, today))
    if not divisions:
        return []
    # Every bill with an event since the Dail first met (one request, 419
    # records and 3.7 MB on 9 October 2026): the API's date filter is on a
    # bill's events, and a Second Stage resumed for a deferred division is
    # not one (measured: the three-day-wait Bill of 17 June 2026 is missing
    # from a 15-18 June window). Not archived: the weekly archives this list.
    bills, _ = ier.fetch_all(client, "legislation", {"date_start": ier.DAIL_START, "date_end": today},
                             "brief-legislation", archive=False, size=1000)
    idx = bill_index(bills)
    members = []
    for chamber, no in houses:
        recs, _ = ier.fetch_all(client, "members", {"chamber_id": ier.HOUSE_URI.format(chamber, no)},
                                "brief-members-{0}-{1}".format(chamber, no), archive=False)
        members += recs
    book = party_book(members)
    transcripts, out = {}, []
    for d in divisions:
        cands = idx.get((d["debate_uri"], d["debate_section"])) or []
        bill = cands[0] if len(cands) == 1 else None
        amendment, read = None, False
        if is_amendment(d["subject"]) and d["debate_uri"]:
            if d["debate_uri"] not in transcripts:
                try:
                    transcripts[d["debate_uri"]] = ier.amendments_in(client.get_bytes(
                        ier.transcript_url(d["debate_uri"]), ier.FEED,
                        "brief-transcript-{0}".format(vote_brief.safe_key(
                            d["debate_uri"].split("debateRecord/")[-1].replace("/debate/main", "")))))
                except (FetchError, ValueError, SyntaxError) as exc:
                    log("  transcript not readable yet for {0}: {1}".format(d["key"], str(exc)[:60]))
                    transcripts[d["debate_uri"]] = None
            found = transcripts[d["debate_uri"]]
            if found is not None:
                read = True
                amendment = (found.get(d["vote_id"]) or (None, ""))[1] or None
        out.append(to_vote(d, bill, book, tax, wl, amendment, read))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", default="", help="YYYY-MM-DD (default: {0} days ago)".format(WINDOW_DAYS))
    ap.add_argument("--today", default="", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--force", action="store_true", help="rewrite and resend briefs that exist")
    ap.add_argument("--no-dm", action="store_true", help="print the DM instead of sending it")
    ap.add_argument("--out", default=vote_brief.BRIEFS)
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    args = ap.parse_args()
    today = args.today or datetime.date.today().isoformat()
    since = args.since or vote_brief.window_start(today, WINDOW_DAYS)
    client = HttpClient(raw_dir=args.raw_dir)
    try:
        votes = collect(client, since, today)
    except (FetchError, ValueError) as exc:
        print("ie: the Oireachtas API did not answer: {0}".format(str(exc)[:120]))
        return 1
    vote_brief.run("ie", votes, out_dir=args.out, force=args.force, dm=not args.no_dm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
