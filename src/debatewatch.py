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
FIELDS = ("date", "house", "term", "area", "note")


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


def add(watches, date, term, house="Commons", area=None, note=None):
    date = date.isoformat() if hasattr(date, "isoformat") else str(date)
    datetime.date.fromisoformat(date)                      # a real date or a ValueError
    for w in watches:
        if w["date"] == date and w["term"].lower() == term.lower() and (w.get("house") or "Commons") == house:
            w.update({"area": area if area is not None else w.get("area"), "note": note or w.get("note")})
            return watches, False
    watches.append({"date": date, "house": house, "term": term, "area": area, "note": note})
    watches.sort(key=lambda w: (w["date"], w.get("house") or "", w["term"]))
    return watches, True


def remove(watches, date, term):
    date = str(date)
    keep = [w for w in watches if not (w["date"] == date and w["term"].lower() == term.lower())]
    return keep, len(watches) - len(keep)


def line(w):
    return "WATCH: %s | %s | area %s | %s" % (w.get("house") or "Commons", w["term"],
                                             w.get("area") if w.get("area") is not None else "-", w.get("note") or "")


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
        if not title:
            continue
        key = (e.start_date.isoformat(), e.house, title.lower())
        if key in seen:
            continue
        seen.add(key)
        areas, reasons = dt.title_areas(taxonomy, watchlist, title, tracker_terms)
        if areas or reasons:
            out.append((e.start_date.isoformat(), e.house, title, areas, reasons))
    return out
