"""Was there a key debate today? (12 September 2026)

The debate pack, the reels and the report all begin with a person naming the
debate. For the standing evening task there is no person, so this asks Hansard
for the day's sections in both Houses, keeps the debates whose TITLE carries a
tier-1 taxonomy term, a watchlist hit or one of the vote tracker's
`debate_match` phrases, fetches those few, and counts who spoke. A debate with
KEY_SPEAKERS members or more is a key debate; the task builds its pack. On a
quiet day the answer is "none" and the task stops without a word.

Titles only, on purpose: fetching every debate of a sitting day to read its
text would be forty requests for one answer. The title gate is the same one the
edition uses ("a debate title match is real", src/filter.py).
"""

import datetime

from src import debatepack as dp
from src import filter as filt

KEY_SPEAKERS = 15          # members on their feet: a Second Reading or a big Westminster Hall day
MIN_SPEAKERS = 6           # below this it is a statement or an adjournment debate: listed, not packed
HOUSES = ("Commons", "Lords")


def title_areas(taxonomy, watchlist, title, tracker_terms=()):
    """(areas, reasons) a debate title earns on its own; empty when it earns none."""
    areas, reasons = set(), []
    for m in filt.match_passages(taxonomy, watchlist, "", title=title):
        areas.update(m.result.issue_areas or [])
        reasons += list(m.result.matched_terms or []) + [h if isinstance(h, str) else str(h) for h in (m.result.watchlist_hits or [])]
    for term in tracker_terms:
        if term.lower() in (title or "").lower():
            reasons.append("tracker: " + term)
    return sorted(areas), reasons


def candidates(client, date, taxonomy, watchlist, tracker_terms=(), houses=HOUSES):
    """[(house, title, section, ext_id, areas, reasons)] for the day's debates whose title earns an area or a tracker term."""
    out, seen = [], set()
    for house in houses:
        for title, section, ext_id in dp._find_debate_once(client, date, "", house):
            title = (title or "").strip()          # Hansard pads some titles with a leading space
            if ext_id in seen:
                continue
            seen.add(ext_id)
            areas, reasons = title_areas(taxonomy, watchlist, title, tracker_terms)
            if areas or reasons:
                out.append((house, title, section, ext_id, areas, reasons))
    return out


def sized(client, date, cands):
    """The candidates with their speaker count, largest first. Fetches each debate once."""
    rows = []
    for house, title, section, ext_id, areas, reasons in cands:
        payload = dp.fetch_debate(client, ext_id) or {}
        speakers = dp.speakers(dp.contributions(payload, date))
        rows.append({"house": house, "title": title, "section": section, "ext_id": ext_id, "areas": areas,
                     "reasons": reasons, "speakers": len(speakers)})
    rows.sort(key=lambda r: -r["speakers"])
    return rows


def verdict(rows, key=KEY_SPEAKERS):
    """The key debate (the largest with `key` speakers or more), or None."""
    return rows[0] if rows and rows[0]["speakers"] >= key else None


def report(rows, date, key=KEY_SPEAKERS, minimum=MIN_SPEAKERS):
    lines = ["Debates on our ground, %s:" % date] if rows else ["No debate on our ground on %s." % date]
    for r in rows:
        if r["speakers"] < minimum:
            continue
        lines.append("  %-7s %3d speakers  %s  [areas %s; %s]" % (r["house"], r["speakers"], r["title"][:70],
                                                                   ",".join(str(a) for a in r["areas"]) or "-",
                                                                   "; ".join(r["reasons"][:3])))
    top = verdict(rows, key)
    if top:
        lines.append("KEY DEBATE: %s | %s | %s | %d speakers" % (top["house"], top["title"], top["ext_id"], top["speakers"]))
    else:
        lines.append("KEY DEBATE: none")
    return "\n".join(lines)


def today_london():
    return datetime.datetime.now(dp.LONDON).date().isoformat()
