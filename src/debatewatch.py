"""Flagged debate days (14 September 2026).

The evening and lunchtime tasks read config/debate_watch.yaml before anything
else. A day with no watch ends the task at once; a day with one names the
house, the Hansard title phrase and the area, so debate_today and the pack
know what to look for. `suggest` reads the week-ahead for the coming days and
prints the candidates on our ground as ready-made `add` commands: the person
decides, the file remembers.
"""

import datetime
import os

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "config", "debate_watch.yaml")
FIELDS = ("date", "house", "term", "area", "note", "source", "bill", "min_speakers")

# Week-ahead categories worth a pack without a person looking: business where
# members speak at length. Oral questions, statements, urgent questions and
# private meetings are listed by `suggest` for the eye but never auto-flagged
# (17 September 2026: an evening run on a statement would only DM "looks
# small" and stop, which is noise, not coverage).
AUTO_CATEGORIES = {"Debate", "General debate", "Westminster Hall debate", "Legislation",
                   "Private Members' Bills", "Backbench Business", "Motion", "Short debate",
                   "Orders and regulations", "Ten Minute Rule Motion", "Oral evidence"}
COMMITTEE_MIN_SPEAKERS = 8      # a bill committee seats about 17; 12-13 spoke on 15 Sept 2026
SAME_DAY_MIN_SPEAKERS = 8       # at 16:45 Hansard has the morning and early afternoon; counts still grow


def load(path=PATH):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    out = []
    for w in raw.get("watches") or []:
        w = dict(w)
        w["date"] = str(w.get("date"))
        out.append(w)
    return out


def save(watches, path=PATH):
    head = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("#"):
                    head.append(line)
                else:
                    break
    body = yaml.safe_dump({"watches": [{k: w.get(k) for k in FIELDS if w.get(k) is not None} for w in watches]},
                          sort_keys=False, allow_unicode=True, default_flow_style=False)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("".join(head) + body)


def for_day(watches, day):
    day = day.isoformat() if hasattr(day, "isoformat") else str(day)
    return [w for w in watches if w["date"] == day]


def add(watches, date, term, house="Commons", area=None, note=None, source=None, bill=None, min_speakers=None):
    date = date.isoformat() if hasattr(date, "isoformat") else str(date)
    datetime.date.fromisoformat(date)                      # a real date or a ValueError
    for w in watches:
        if w["date"] == date and w["term"].lower() == term.lower() and (w.get("house") or "Commons") == house:
            # A person's watch outranks an automatic one: an auto pass never
            # rewrites the note or area a hand `add` set, only fills blanks.
            # A hand `add` over any watch still updates, as it always did.
            protect = w.get("source") in (None, "hand") and source not in (None, "hand")
            w.update({"area": area if (area is not None and not (protect and w.get("area") is not None)) else w.get("area"),
                      "note": w.get("note") if (protect and w.get("note")) else (note or w.get("note")),
                      "bill": bill if bill is not None else w.get("bill"),
                      "min_speakers": min_speakers if min_speakers is not None else w.get("min_speakers")})
            return watches, False
    watches.append({"date": date, "house": house, "term": term, "area": area, "note": note,
                    "source": source or "hand", "bill": bill, "min_speakers": min_speakers})
    watches.sort(key=lambda w: (w["date"], w.get("house") or "", w["term"]))
    return watches, True


def remove(watches, date, term):
    date = str(date)
    keep = [w for w in watches if not (w["date"] == date and w["term"].lower() == term.lower())]
    return keep, len(watches) - len(keep)


def line(w):
    out = "WATCH: %s | %s | area %s | %s" % (w.get("house") or "Commons", w["term"],
                                            w.get("area") if w.get("area") is not None else "-", w.get("note") or "")
    if w.get("min_speakers"):
        out += " | min %d" % int(w["min_speakers"])       # the evening task reads this instead of its default 15
    return out


def suggest(events, taxonomy, watchlist, tracker_terms, today):
    """[(date, house, title, areas, reasons)] for week-ahead events on our ground,
    from `today` on. Uses debatetoday.title_areas so the same gate names a debate
    here and on the day."""
    from src import debatetoday as dt
    out, seen = [], set()
    for e in events:
        if not getattr(e, "start_date", None) or e.start_date < today:
            continue
        title = (getattr(e, "description", "") or getattr(e, "bill_name", "") or "").strip()
        committee = getattr(e, "committee", None)
        if not title and isinstance(committee, dict):
            # A bill committee's sitting has an empty description; the bill's
            # name is the committee's (found 17 Sept 2026 on the Immigration
            # and Asylum Bill's evidence sittings).
            title = (committee.get("Description") or "").strip()
        if not title:
            continue
        key = (e.start_date.isoformat(), e.house, title.lower())
        if key in seen:
            continue
        seen.add(key)
        areas, reasons = dt.title_areas(taxonomy, watchlist, title, tracker_terms)
        if areas or reasons:
            out.append((e.start_date.isoformat(), e.house, title, areas, reasons, getattr(e, "category", None) or ""))
    return out


def auto_flag(watches, rows, today=None):
    """Flag every `suggest` row whose category is in AUTO_CATEGORIES. Returns the
    watches and the rows written. Rows already flagged (any source) are left as
    they are, so a person's note survives Monday's pass."""
    today = str(today or datetime.date.today())
    written = []
    for row in rows:
        date, house, title, areas, reasons = row[:5]
        category = row[5] if len(row) > 5 else ""
        if date < today or category not in AUTO_CATEGORIES:
            continue
        if any(w["date"] == date and (w.get("house") or "Commons") == house and w["term"].lower() in title.lower()
               for w in watches):
            continue
        note = "auto: %s; %s" % (category, "; ".join(reasons[:2]))
        watches, new = add(watches, date, title[:60], house, areas[0] if areas else None, note[:120], source="auto")
        if new:
            written.append((date, house, title[:60]))
    return watches, written


def bill_watches(detail, stages, today, area=None, note=None):
    """[(date, house, term, note, min_speakers)] for a bill's sittings from `today`
    on, one per stage sitting. Committee sittings carry COMMITTEE_MIN_SPEAKERS
    because a bill committee never seats fifteen speakers. `detail` and `stages`
    are the Bills API payloads (Bills/<id>, Bills/<id>/Stages)."""
    today = str(today)
    term = (detail or {}).get("shortTitle") or ""
    bill_id = (detail or {}).get("billId")
    out = []
    for stage in (stages or {}).get("items") or []:
        desc = stage.get("description") or "stage"
        house = stage.get("house") or "Commons"
        for sitting in stage.get("stageSittings") or []:
            date = (sitting.get("date") or "")[:10]
            if not date or date < today:
                continue
            minimum = COMMITTEE_MIN_SPEAKERS if "ommittee" in desc else None
            out.append((date, house, term, "%s%s (bill %s)" % (note + ": " if note else "", desc, bill_id), minimum))
    out.sort()
    return out


def expand_bill(watches, detail, stages, today, area=None, note=None, only_new=False):
    """Add a watch for each future sitting of the bill. Returns (watches, added, kept).
    `only_new` (the Monday refresh) leaves every existing watch exactly as it is."""
    added, kept = [], 0
    bill_id = (detail or {}).get("billId")
    for date, house, term, line_note, minimum in bill_watches(detail, stages, today, area, note):
        if only_new and any(w["date"] == date and w["term"].lower() == term.lower() and (w.get("house") or "Commons") == house
                            for w in watches):
            kept += 1
            continue
        watches, new = add(watches, date, term, house, area, line_note, source="bill", bill=bill_id, min_speakers=minimum)
        if new:
            added.append((date, house, term))
        else:
            kept += 1
    return watches, added, kept


def refresh_bills(watches, fetch, today):
    """Re-expand every bill id the file already carries, so a sitting added to the
    Bills API after the flag still gets its watch. `fetch(bill_id)` returns
    (detail, stages). A bill's area and hand note are carried from its first watch."""
    added = []
    seen = set()
    for w in list(watches):
        bill_id = w.get("bill")
        if not bill_id or bill_id in seen:
            continue
        seen.add(bill_id)
        detail, stages = fetch(bill_id)
        # Carry the hand note's prefix ("immigration: Committee stage (bill 4254)")
        # to the new sittings, so a refresh reads like the add-bill that started it.
        prefix = (w.get("note") or "").split(": ")[0] if ": " in (w.get("note") or "") else None
        watches, new, _ = expand_bill(watches, detail, stages, today, w.get("area"), prefix, only_new=True)
        added += new
    return watches, added


def net(watches, rows, today, minimum=SAME_DAY_MIN_SPEAKERS):
    """Same-day net (17 September 2026): flag today's debates on our ground that
    Hansard already shows with `minimum` speakers or more, so the evening task
    packs a debate nobody saw coming (an urgent question that grew, a statement
    that became a debate). `rows` are debatetoday.sized rows. Returns (watches,
    flagged) where flagged is [(house, title, speakers)]."""
    today = str(today)
    flagged = []
    for r in rows:
        if r["speakers"] < minimum:
            continue
        if any(w["date"] == today and (w.get("house") or "Commons") == r["house"] and w["term"].lower() in r["title"].lower()
               for w in watches):
            continue
        areas = r.get("areas") or []
        note = "same-day: %d speakers by the net; %s" % (r["speakers"], "; ".join((r.get("reasons") or [])[:2]))
        watches, new = add(watches, today, r["title"][:60], r["house"], areas[0] if areas else None, note[:120],
                           source="same-day", min_speakers=minimum)
        if new:
            flagged.append((r["house"], r["title"][:60], r["speakers"]))
    return watches, flagged
