"""Find divisions on our issues that a title search could never see.

    python3 tools/find_division_candidates.py [start] [end]

The division sweep searches TITLES for 16 phrases, so a vote is invisible to
it unless its title names one of our issues. That fails precisely where it
matters: contentious social change reaches the floor as an amendment to an
unrelated government bill, because private members' bills mostly die. The
biggest abortion vote of the parliament is titled "Crime and Policing Bill
Report Stage: New Clause 1" -- no term could ever have matched it.

This enumerates EVERY Commons division in the range (cheap: the list endpoint
pages 25 at a time) and flags candidates two ways:

  title    the taxonomy matches the division title -- the sweep may have
           missed it through phrasing alone
  debate   tagged speeches that day sat in the SAME debate as the division.
           This is what catches New Clause 1: the abortion speeches of 17
           June 2025 are filed under "Crime and Policing Bill", exactly the
           bill the division names.

Same-DAY alone was tried first and is useless: members debate our issues on
most sitting days, so it flagged carbon budget orders and trade union ballot
regulations. Requiring the same DEBATE is what makes it a signal.

Output is a REVIEW QUEUE, not a decision. A division only reaches the public
tracker when a human adds it to config/vote_tracker.yaml with a meaning line.
Hidden areas (migration) are still listed, marked HIDDEN: we track the issue,
we do not display it.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, intel
from src.http import FetchError, HttpClient
from src.ingest.divisions import COMMONS_API, parse_commons_response

PAGE = 25          # the API's real cap, whatever `take` asks for
MAX_PAGES = 200    # 5,000 divisions: far beyond any range we query
MIN_OVERLAP = 12   # characters: shorter matches are coincidence
MIN_AREA_SPEECHES = 3  # a single stray speech in a long debate is not a signal


def hidden_areas():
    """Areas we track in the ledger but never display (Christopher: migration)."""
    import yaml
    with open(os.path.join(ROOT, "config", "vote_tracker.yaml"), encoding="utf-8") as h:
        cfg = yaml.safe_load(h) or {}
    return {int(a) for a in (cfg.get("hidden_areas") or [])}


def tracked_ids():
    import yaml
    with open(os.path.join(ROOT, "config", "vote_tracker.yaml"), encoding="utf-8") as h:
        cfg = yaml.safe_load(h) or {}
    return {int(d["id"]) for d in (cfg.get("divisions") or [])}


def enumerate_divisions(client, start, end):
    """Every Commons division in the range, by date -- not by search term."""
    out, skip, seen = [], 0, set()
    for _ in range(MAX_PAGES):
        url = ("{0}/divisions.json/search?queryParameters.startDate={1}"
               "&queryParameters.endDate={2}&queryParameters.skip={3}"
               "&queryParameters.take={4}").format(COMMONS_API, start, end, skip, PAGE)
        try:
            batch = parse_commons_response(
                client.get_json(url, "division", "enum-{0}-{1}".format(start, skip)))
        except FetchError as exc:
            print("  [gap] enumeration stopped at skip={0}: {1}".format(skip, exc.cause))
            break
        # Stop on an empty page, not a short one: the API caps pages at 25
        # however large a `take` you ask for, so a short page is every page.
        fresh = [d for d in batch if d.id not in seen]
        if not fresh:
            break
        seen.update(d.id for d in fresh)
        out.extend(fresh)
        skip += PAGE
    return out


def _norm(text):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", (text or "").lower()).split())


def debate_titles_by_date(conn):
    """{date: [(debate title, areas)]} for tagged speeches."""
    out = {}
    for r in conn.execute(
            "SELECT date, line, areas FROM mp_events WHERE kind = 'debate' "
            "AND areas IS NOT NULL AND areas != '[]'"):
        title = re.sub(r"^Spoke:\s*", "", r["line"] or "")
        title = re.sub(r"\s*\(re: [^)]*\)$", "", title)
        out.setdefault(r["date"], []).append((_norm(title), json.loads(r["areas"])))
    return out


def same_debate_areas(division_title, day_debates):
    """Areas of tagged speeches sitting in the SAME debate as this division.

    Bidirectional substring on normalised text: a division titled "Crime and
    Policing Bill Report Stage: New Clause 1" and a debate titled "Crime and
    Policing Bill" match, while a carbon budget order matches nothing.
    """
    div = _norm(division_title)
    hits = {}
    for debate, areas in day_debates:
        if len(debate) < MIN_OVERLAP:
            continue
        if debate in div or (len(div) >= MIN_OVERLAP and div in debate):
            for area in areas:
                hits[area] = hits.get(area, 0) + 1
    return hits


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else "2020-01-01"
    end = sys.argv[2] if len(sys.argv) > 2 else datetime.date.today().isoformat()
    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    hidden, tracked = hidden_areas(), tracked_ids()
    day_debates = debate_titles_by_date(conn)

    held = {int(r["ref"].split("c")[1].split(":")[0])
            for r in conn.execute("SELECT DISTINCT ref FROM mp_events "
                                  "WHERE kind='vote' AND ref LIKE 'div:c%'")}
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    print("enumerating Commons divisions {0} to {1}...".format(start, end))
    divisions = enumerate_divisions(client, start, end)
    print("{0} divisions found; {1} already in the ledger, {2} on the tracker\n".format(
        len(divisions), len(held), len(tracked)))

    candidates = []
    for d in divisions:
        if not d.id or d.id in tracked:
            continue
        title = " ".join((d.title or "").split())
        result = filt.filter_item(tax, wl, title)
        title_areas = set(result.issue_areas) if (result.tier == 1 or result.watchlist_hits) else set()
        day_areas = same_debate_areas(
            title, day_debates.get(d.date.isoformat() if d.date else "", []))
        if not title_areas and not day_areas:
            continue
        areas = title_areas | set(day_areas)
        # Displayable only on real evidence for a displayable area: the title
        # naming it, or enough speeches to mean something. A Rwanda division
        # with one incidental free-speech contribution in a 73-speech debate
        # is a migration vote, not a free-speech one.
        shown_title = title_areas - hidden
        shown_debate = {a for a, n in day_areas.items()
                        if a not in hidden and n >= MIN_AREA_SPEECHES}
        candidates.append({
            "id": d.id, "date": d.date.isoformat() if d.date else "?", "title": title,
            "title_areas": sorted(title_areas), "day_areas": day_areas,
            "areas": sorted(areas), "in_ledger": d.id in held,
            "hidden_only": not (shown_title or shown_debate),
        })

    fresh = [c for c in candidates if not c["in_ledger"]]
    hidden_only = [c for c in fresh if c["hidden_only"]]
    actionable = [c for c in fresh if not c["hidden_only"]]
    print("{0} candidates, of which {1} are NOT already in the ledger.".format(
        len(candidates), len(fresh)))
    print("  {0} concern hidden areas only (tracked, never displayed)".format(
        len(hidden_only)))
    print("  {0} touch a displayable area -- these are the review queue".format(
        len(actionable)))
    by_area = {}
    for c in actionable:
        strong = (set(c["title_areas"]) |
                  {a for a, n in c["day_areas"].items() if n >= MIN_AREA_SPEECHES})
        for a in strong - hidden:
            by_area[a] = by_area.get(a, 0) + 1
    if by_area:
        print("  by area: " + ", ".join(
            "{0} {1}".format(names.get(a, a), n)
            for a, n in sorted(by_area.items(), key=lambda kv: -kv[1])))
    fresh = actionable
    print("Sorted by evidence strength: title match first, then weight of "
          "same-debate speeches.\n")
    fresh.sort(key=lambda c: (not c["title_areas"], -sum(c["day_areas"].values())))
    for c in fresh[:40]:
        marks = []
        if c["title_areas"]:
            marks.append("title: " + ", ".join(names.get(a, str(a)) for a in c["title_areas"]))
        if c["day_areas"]:
            marks.append("same debate: " + ", ".join(
                "{0} x{1}".format(names.get(a, a), n)
                for a, n in sorted(c["day_areas"].items(), key=lambda kv: -kv[1])[:3]))
        flag = "  [HIDDEN AREA - track, do not display]" if c["hidden_only"] else ""
        print("  id {0:5}  {1}  {2}".format(c["id"], c["date"], c["title"][:70]))
        print("        {0}{1}".format(" | ".join(marks), flag))
    if len(fresh) > 40:
        print("\n  ...and {0} more".format(len(fresh) - 40))
    print("\nNothing here is published. Add the ones that belong to "
          "config/vote_tracker.yaml with a meaning line a human has written.")
    conn.close()


if __name__ == "__main__":
    main()
