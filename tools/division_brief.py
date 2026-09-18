"""Same-day division brief: the vote, by party and by name, within the hour.

    python3 tools/division_brief.py                      # today's divisions
    python3 tools/division_brief.py --date 2026-09-11    # a given day
    python3 tools/division_brief.py --date 2025-06-20 --force --no-dm --out /tmp/x

Christopher, 2026-09-07: "Build the division brief." The TIA Second Reading
divides on Friday 11 September and nothing else runs before the Sunday
pull, yet Friday afternoon is when the supporter emails naming MPs get
written. This runs on sitting days (division-watch.yml), finds every
division of the day on our ground, and for each one writes a brief and
sends a DM: the tallies, how each party split, what the anchor members
did, who changed lobby since the comparable vote, and the full name lists
by lobby -- the raw material of a "thank your MP" or "write to your MP"
email, with links to the record.

WHAT IT DOES NOT DO. It attaches no meaning to the question. The Commons
API carries no motion text (measured: null in every archived payload), so
"what did an Aye mean" is read by a human from Hansard and signed through
tools/prep_division.py, exactly as before. The brief reports lobbies as
facts and names no vote good or bad. The tracker is not touched: config/
vote_tracker.yaml is editorial and stays that way.

IDEMPOTENT ON THE FILE, NOT THE STORE. A brief that exists is not written
or sent again (--force overrides), so the watch can run hourly through an
afternoon and speak once per division. Nothing here reads or writes the
store; the Sunday pull ledgers the votes as it always has. The detail
payloads this fetches are archived under data/raw like every other fetch,
so the tracker's rebuild finds them ready.
"""

from __future__ import annotations

import argparse
import datetime
import glob
import gzip
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import filter as filt, publish
from src.http import FetchError, HttpClient
from src.ingest import divisions as div_ingest

BRIEFS = os.path.join(ROOT, "data", "briefs")
REPO = "thejoycething-code/parl-monitor"
TRACKER = "https://parl-monitor-partner.vercel.app/mp-votes.html"
HANSARD_DAY = "https://hansard.parliament.uk/{house}/{date}"
VANDP = ("https://commonsbusiness.parliament.uk/document/search?date={date}"
         "&type=VotesAndProceedings")

# Members whose record on an issue is measured and consistent, so what
# they did today is the first thing to read (tools/prep_division.ANCHORS
# holds the verdict each MUST render once our_side is signed; here they
# are reported as lobbies only). Keyed by a phrase of the division title.
ANCHORS = {
    "Terminally Ill Adults": {
        4858: "Danny Kruger", 4923: "Kim Leadbeater", 5298: "Lauren Edwards",
    },
}
# The earlier vote each Bill's members are compared against for lobby
# changes: the 2025 Third Reading (314-291) for the 2026 assisted suicide
# Bill. Same question polarity (a vote for the Bill is an Aye in both), so
# a member who changed lobby changed their mind, or their whip.
COMPARE = {"Terminally Ill Adults": 2071}

MERGE_PARTY = {"Labour (Co-op)": "Labour"}


def party_splits(voters):
    """[(party, ayes, noes)] largest party first."""
    tally = {}
    for v in voters:
        party = MERGE_PARTY.get(v.party or "", v.party or "Unknown")
        a, n = tally.get(party, (0, 0))
        tally[party] = (a + (v.vote == "aye"), n + (v.vote == "no"))
    return sorted(((p, a, n) for p, (a, n) in tally.items()),
                  key=lambda r: (-(r[1] + r[2]), r[0]))


def anchor_lobbies(title, voters):
    """[(name, 'aye'|'no'|'did not vote')] for the issue's anchors, if any."""
    for phrase, anchors in ANCHORS.items():
        if phrase.lower() in (title or "").lower():
            by_id = {v.member_id: v.vote for v in voters}
            return [(name, by_id.get(mid, "did not vote")) for mid, name in anchors.items()]
    return []


def compare_id(title):
    for phrase, div_id in COMPARE.items():
        if phrase.lower() in (title or "").lower():
            return div_id
    return None


def archived_breakdown(div_id, root=ROOT):
    """(Division, voters) from the newest archived Commons detail payload."""
    paths = sorted(glob.glob(os.path.join(root, "data", "raw", "*",
                                          "division_cdetail-{0}.json.gz".format(div_id))))
    if not paths:
        return None, []
    with gzip.open(paths[-1], "rb") as handle:
        return div_ingest.parse_commons_breakdown(json.loads(handle.read().decode("utf-8")))


def both_lobbies(voters):
    """Members recorded in BOTH lobbies: the Commons' way of recording a
    deliberate abstention. Wendy Chamberlain did it on the 2025 Third
    Reading, and a naive comparison of that division with itself reported
    her as having "changed lobby" (found building this, 2026-09-07)."""
    ayes = {v.member_id for v in voters if v.vote == "aye" and v.member_id}
    noes = {v.member_id for v in voters if v.vote == "no" and v.member_id}
    names = {v.member_id: v for v in voters}
    return sorted((names[m] for m in ayes & noes), key=lambda v: v.name or "")


def lobby_changes(voters, previous):
    """Members in both divisions who voted the other way this time.

    A member in both lobbies of either division abstained by the record's
    own convention and is left out: they did not change their mind, they
    declined to give one."""
    skip = {v.member_id for v in both_lobbies(voters)} | {v.member_id for v in both_lobbies(previous)}
    before = {v.member_id: v for v in previous if v.member_id and v.member_id not in skip}
    out, seen = [], set()
    for v in voters:
        if v.member_id in skip or v.member_id in seen:
            continue
        p = before.get(v.member_id)
        if p and p.vote != v.vote:
            seen.add(v.member_id)
            out.append((v.name, MERGE_PARTY.get(v.party or "", v.party or ""), v.seat, p.vote, v.vote))
    return sorted(out, key=lambda r: (r[4], r[1], r[0] or ""))


def _lobby_word(vote):
    return {"aye": "Aye", "no": "No"}.get(vote, vote)


def brief_markdown(division, voters, previous=None, previous_title=None, generated=None):
    d = division
    date = d.date.isoformat() if d.date else "?"
    result = "passed" if (d.aye_count or 0) > (d.no_count or 0) else "rejected"
    margin = abs((d.aye_count or 0) - (d.no_count or 0))
    house = "Commons" if d.house != "Lords" else "Lords"
    out = ["# Division brief: {0}".format(" ".join((d.title or "").split())), ""]
    out.append("*{0} division {1} (No. {2}), {3}. Generated {4}. Facts of the record only: "
               "the meaning of the question is signed separately through "
               "tools/prep_division.py.*".format(house, d.id, d.number, date,
                                                 generated or datetime.datetime.now().isoformat(timespec="minutes")))
    out.append("")
    out.append("**Result: Ayes {0}, Noes {1} — {2} by {3}.**".format(d.aye_count, d.no_count, result, margin))
    out.append("")
    both = both_lobbies(voters)
    if both:
        out.append("*Recorded in both lobbies (the Commons' form of a deliberate abstention): {0}.*".format(
            "; ".join("{0} ({1})".format(v.name, v.party) for v in both)))
        out.append("")
    out.append("*The name lists below exclude the tellers; the official counts are as declared.*")
    out.append("")
    out.append("Sources: [division record]({0}) · [Hansard for the day]({1}) · "
               "[Votes and Proceedings]({2}) · [our vote tracker]({3})".format(
                   d.url, HANSARD_DAY.format(house=house.lower(), date=date), VANDP.format(date=date), TRACKER))
    out.append("")
    if getattr(d, "notes", None):
        out.append("Question as recorded (Lords motion notes): {0}".format(d.notes))
        out.append("")
    out.append("## By party")
    out.append("")
    out.append("| Party | Ayes | Noes | Voted |")
    out.append("|---|---|---|---|")
    for party, a, n in party_splits(voters):
        out.append("| {0} | {1} | {2} | {3} |".format(party, a, n, a + n))
    out.append("")
    anchors = anchor_lobbies(d.title, voters)
    if anchors:
        out.append("## Anchors")
        out.append("")
        out.append("*Members with a measured, consistent record on this issue. Read these first: "
                   "if they sit where the record says, the polarity of the question is the usual one.*")
        out.append("")
        for name, lobby in anchors:
            out.append("- {0}: **{1}**".format(name, _lobby_word(lobby) if lobby != "did not vote" else "did not vote"))
        out.append("")
    if previous:
        changes = lobby_changes(voters, previous)
        out.append("## Changed lobby since {0}".format(previous_title or "the comparable division"))
        out.append("")
        if changes:
            out.append("| Member | Party | Seat | Then | Now |")
            out.append("|---|---|---|---|---|")
            for name, party, seat, then, now in changes:
                out.append("| {0} | {1} | {2} | {3} | {4} |".format(name, party, seat, _lobby_word(then), _lobby_word(now)))
        else:
            out.append("*Nobody who voted both times changed lobby.*")
        out.append("")
        newcomers = sum(1 for v in voters if v.member_id and v.member_id not in {p.member_id for p in previous})
        out.append("*{0} of today's voters had no vote in the comparison division (new members, or absent then).*".format(newcomers))
        out.append("")
    for lobby, heading in (("aye", "Ayes"), ("no", "Noes")):
        side = [v for v in voters if v.vote == lobby]
        out.append("## {0} ({1})".format(heading, len(side)))
        out.append("")
        by_party = {}
        for v in side:
            by_party.setdefault(MERGE_PARTY.get(v.party or "", v.party or "Unknown"), []).append(v)
        for party in sorted(by_party, key=lambda p: (-len(by_party[p]), p)):
            names = sorted(by_party[party], key=lambda v: v.name or "")
            out.append("**{0}** ({1}): {2}".format(
                party, len(names),
                "; ".join("{0} ({1})".format(v.name, v.seat) if v.seat else (v.name or "?") for v in names)))
            out.append("")
    out.append("---")
    out.append("")
    out.append("Next: read the question from Hansard, then "
               "`python3 tools/prep_division.py --date {0} --our-side aye|no --division {1}` "
               "to anchor-test a verdict and print the sign-off block.".format(date, d.id))
    return "\n".join(out) + "\n"


def dm_text(division, voters, brief_url, previous=None):
    d = division
    result = "passed" if (d.aye_count or 0) > (d.no_count or 0) else "rejected"
    house = "Commons" if d.house != "Lords" else "Lords"
    lines = [":ballot_box_with_ballot: *{0} division: {1}*".format(house, " ".join((d.title or "").split()))]
    lines.append("Ayes {0}, Noes {1} — {2} by {3}.".format(
        d.aye_count, d.no_count, result, abs((d.aye_count or 0) - (d.no_count or 0))))
    splits = party_splits(voters)[:5]
    lines.append("By party: " + "; ".join("{0} {1}–{2}".format(p, a, n) for p, a, n in splits) + ".")
    anchors = anchor_lobbies(d.title, voters)
    if anchors:
        lines.append("Anchors: " + "; ".join("{0} {1}".format(n, _lobby_word(l) if l != "did not vote" else "did not vote")
                                              for n, l in anchors) + ".")
    if previous:
        changes = lobby_changes(voters, previous)
        lines.append("{0} member(s) changed lobby since the comparison division.".format(len(changes)))
    lines.append("Brief with the full lists by party: {0}".format(brief_url))
    lines.append("Record: {0}".format(d.url))
    lines.append("_No meaning is attached. Read the question, then run prep_division.py to sign the verdict._")
    return "\n".join(lines)


def on_our_ground(title, tax, wl):
    entities = [e[0] for e in (wl.bill_titles or [])] + [e[0] for e in (wl.act_shorts or [])]
    if div_ingest.matches_watchlist(title, entities):
        return True
    return filt.filter_item(tax, wl, title or "").matched()


def run(date, out_dir=BRIEFS, force=False, dm=True, client=None, secrets=None, log=print):
    client = client or HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    found = []
    try:
        found.extend(("c", div_ingest.fetch_commons_breakdown, d)
                     for d in div_ingest.fetch_commons_divisions(client, date))
    except FetchError as exc:
        log("commons list unavailable for {0}: {1} (the list endpoint lags after a big vote; retry)".format(date, exc.cause))
    try:
        found.extend(("l", div_ingest.fetch_lords_breakdown, d)
                     for d in div_ingest.fetch_lords_divisions(client, date, date))
    except FetchError as exc:
        log("lords list unavailable for {0}: {1}".format(date, exc.cause))
    if not found:
        log("no divisions recorded on {0}.".format(date))
        return 0
    ours = [(p, b, d) for p, b, d in found if on_our_ground(d.title, tax, wl)]
    log("{0} division(s) on {1}, {2} on our ground.".format(len(found), date, len(ours)))
    os.makedirs(out_dir, exist_ok=True)
    written, messages = 0, []
    for prefix, breakdown, d in ours:
        path = os.path.join(out_dir, "division-{0}{1}.md".format(prefix, d.id))
        if os.path.exists(path) and not force:
            log("  {0}{1} {2}: already briefed ({3})".format(prefix, d.id, d.title, os.path.relpath(path, ROOT)))
            continue
        try:
            division, voters = breakdown(client, d.id)
        except FetchError as exc:
            log("  {0}{1} {2}: name lists not published yet ({3}); next run".format(prefix, d.id, d.title, exc.cause))
            continue
        division.house = "Lords" if prefix == "l" else "Commons"
        previous, previous_title = [], None
        cid = compare_id(d.title) if prefix == "c" else None
        if cid and cid != d.id:
            prev_div, previous = archived_breakdown(cid)
            if prev_div:
                previous_title = "{0} ({1}, division {2})".format(
                    " ".join((prev_div.title or "").split()), prev_div.date, cid)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(brief_markdown(division, voters, previous, previous_title))
        written += 1
        url = "https://github.com/{0}/blob/main/{1}".format(REPO, os.path.relpath(path, ROOT))
        log("  {0}{1} {2}: brief written -> {3}".format(prefix, d.id, d.title, os.path.relpath(path, ROOT)))
        messages.append(dm_text(division, voters, url, previous))
    # ONE message per run, however many divisions: the 20 June 2025
    # rehearsal (six divisions) sent six DMs in a row (2026-09-07).
    if dm and messages:
        text = "\n\n".join(messages)
        if len(messages) > 1:
            text = "*{0} divisions on our ground today.*\n\n".format(len(messages)) + text
        result = publish.slack_dm(secrets if secrets is not None else publish.load_secrets(), text)
        log("  DM: {0} ({1} division(s) in one message)".format(
            "sent" if result.get("message_ts") or result.get("ok") else
            result.get("skipped") or result.get("error") or "sent", len(messages)))
    log("{0} brief(s) written.".format(written))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="", help="YYYY-MM-DD (blank = today, UK date)")
    ap.add_argument("--force", action="store_true", help="rewrite and resend a brief that exists")
    ap.add_argument("--no-dm", action="store_true")
    ap.add_argument("--out", default=BRIEFS)
    args = ap.parse_args()
    date = args.date or datetime.date.today().isoformat()
    return run(date, out_dir=args.out, force=args.force, dm=not args.no_dm)


if __name__ == "__main__":
    sys.exit(main())
