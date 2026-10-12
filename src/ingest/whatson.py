"""What's On ingester (handoff 4.7).

Quirks encoded:
  * long ranges return HTTP 400: chunk requests to <= 4 weeks;
  * keys are PascalCase; an empty array is valid and means no business;
  * recess detection: zero Commons AND Lords chamber events for the edition
    week => recess mode; return date = earliest event per house in the next 6 weeks;
  * response order reflects Order Paper order (first PMB listed gets the debate).
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass

from src.ingest.bills import parse_api_date

WHATSON_API = "https://whatson-api.parliament.uk/calendar/events/list.json"
MAX_RANGE_DAYS = 28  # <= 4 weeks (handoff 4.7)


@dataclass
class Event:
    start_date: datetime.date
    start_time: str
    # Added 2026-09-07 for the Week ahead table: Parliament's own event id
    # (stable across runs, unlike a Python string hash, which changed with
    # every process and stored each event twice), the end time, and the
    # members leading the item.
    house: str
    category: str
    type: str
    description: str
    bill_id: int
    bill_name: str
    committee: str
    location: str
    id: int = None
    end_time: str = None
    members: list = None


def parse_event(row):
    return Event(
        id=row.get("Id"),
        end_time=row.get("EndTime") or None,
        members=[m.get("Name") for m in (row.get("Members") or []) if isinstance(m, dict) and m.get("Name")],
        start_date=parse_api_date(row.get("StartDate")),
        start_time=row.get("StartTime"),
        house=row.get("House"),
        category=row.get("Category"),
        type=row.get("Type"),
        description=row.get("Description"),
        bill_id=row.get("BillId"),
        bill_name=row.get("BillName"),
        committee=row.get("Committee"),
        location=row.get("Location"),
    )


def parse_response(payload):
    return [parse_event(row) for row in (payload or [])]


def date_chunks(start, end, max_days=MAX_RANGE_DAYS):
    """Split [start, end] into <= max_days sub-ranges (handoff 4.7)."""
    chunks = []
    cursor = start
    step = datetime.timedelta(days=max_days - 1)
    while cursor <= end:
        chunk_end = min(cursor + step, end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + datetime.timedelta(days=1)
    return chunks


def fetch_events(client, start, end):
    """Fetch events across [start, end], chunked to respect the range limit."""
    events = []
    for chunk_start, chunk_end in date_chunks(start, end):
        url = "{0}?queryParameters.startDate={1}&queryParameters.endDate={2}".format(
            WHATSON_API, chunk_start.isoformat(), chunk_end.isoformat())
        payload = client.get_json(url, "whatson", "range-{0}-{1}".format(chunk_start, chunk_end))
        events.extend(parse_response(payload))
    return events


SEQUENCED = "after other business"


def _text(value):
    """Some fields arrive as dicts ({'Name': ...}) rather than strings.

    Committee arrives as {'Id': 851, 'Description': 'Draft Conversion
    Practices Bill (Joint Committee)', ...}, with no Name: reading only Name
    left every committee event without its committee, so the filter never
    saw it (found 2026-10-12: the joint committee met on 12 and 15 Oct and
    neither meeting reached the edition)."""
    if isinstance(value, dict):
        return value.get("Name") or value.get("name") or value.get("Description") or ""
    return value if isinstance(value, str) else ""


def _collapse(text):
    """Collapse runs of whitespace; source descriptions carry double spaces."""
    return " ".join((text or "").split())


def format_time(start_time):
    """'11:30' -> '11.30am'; '' -> None.

    StartTime is an empty string (never null) for chamber business that runs in
    Order Paper sequence rather than at a clock time: oral questions, orders and
    regulations, ministerial statements, urgent questions, adjournment. Those
    items have no time to publish, so callers render SEQUENCED instead of
    inventing one. Committee evidence sessions do carry HH:MM.
    """
    raw = (start_time or "").strip()
    if not raw:
        return None
    parts = raw.replace(".", ":").split(":")
    try:
        # Strip any am/pm suffix before converting; '10:00 am' -> hour 10, minute 0.
        hour = int(re.sub(r"[^0-9]", "", parts[0]))
        minute = int(re.sub(r"[^0-9]", "", parts[1]) or 0) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return raw
    if "pm" in raw.lower() and hour < 12:
        hour += 12
    elif "am" in raw.lower() and hour == 12:
        hour = 0
    suffix = "am" if hour < 12 else "pm"
    display_hour = hour % 12 or 12
    return "{0}.{1:02d}{2}".format(display_hour, minute, suffix)


def event_url(event):
    """The event's own page on whatson.parliament.uk, or None without an id."""
    return "https://whatson.parliament.uk/event/cal{0}".format(event.id) if getattr(event, "id", None) else None


def event_text(event):
    """All matchable text for an event, for the taxonomy filter."""
    return " ".join(_text(x) for x in (event.description, event.bill_name, event.committee,
                                       event.category, event.type))


def event_label(event):
    """One-line diary label: '11.30am, Commons Oral evidence. <description>'.

    Sequenced chamber business gets 'after other business' where the time would
    go, so the reader knows it is order-paper business and not a missing time.
    """
    when = format_time(event.start_time) or SEQUENCED
    where = " ".join(x for x in (_text(event.house),
                                 _text(event.category) or _text(event.type)) if x)
    what = _collapse(_text(event.description) or _text(event.bill_name) or _text(event.committee))
    head = ", ".join(x for x in (when, where) if x)
    return "{0}. {1}".format(head, what).strip() if what else head


def is_recess(events):
    """Recess when there are no Commons or Lords chamber events in the week."""
    for event in events:
        if event.house in ("Commons", "Lords"):
            return False
    return True


def return_dates(events):
    """Earliest event date per house (for the recess return line)."""
    out = {}
    for event in sorted(events, key=lambda e: (e.start_date or datetime.date.max)):
        if event.house in ("Commons", "Lords") and event.house not in out and event.start_date:
            out[event.house] = event.start_date
    return out


# -- Announced business (2026-10-12) -----------------------------------------
# The Week ahead table holds only events the taxonomy matched, so business on
# our ground whose TITLE says nothing taxonomy-shaped never reached the
# edition. The 5 Oct edition missed both the Commons general debate on Baby
# Loss Awareness Week and the Westminster Hall petition debate on rejoining
# the EU (12 Oct), though both were announced on 10 Sep and What's On had
# them. The announced list shows the week's headline business regardless of
# keywords, so the reader sees everything announced and judges for themself.

# (house, category) pairs that are headline business. Questions, statements,
# introductions, adjournments, procedural motions and committee meetings are
# left out: either they are routine or the existing feeds already cover them.
HEADLINE = {
    ("Commons", "General debate"), ("Commons", "Legislation"),
    ("Commons", "Westminster Hall debate"), ("Commons", "Private Members' Bills"),
    ("Commons", "Ten Minute Rule Motion"), ("Commons", "Debate"),
    ("Commons", "Backbench Business"),
    ("Lords", "Legislation"), ("Lords", "Debate"), ("Lords", "Short debate"),
    ("Lords", "Question for short debate"),
}
# Fridays list every Private Member's Bill on the Order Paper, in order, and
# only the first few are ever reached (the response order is the Order Paper
# order). More than three is a list of titles nobody will debate.
PMB_CAP = 3


def is_headline(event):
    """Headline chamber, Westminster Hall or Grand Committee business."""
    if _text(event.type) not in ("Main Chamber", "Westminster Hall", "Grand Committee"):
        return False
    return (_text(event.house), _text(event.category)) in HEADLINE


def announced(events, exclude_ids=()):
    """The headline business in `events`, in Order Paper order per day.

    Returns (rows, held_back): rows are Events; held_back counts the Private
    Members' Bills past the cap, per ISO date, so the edition can say how
    many more are listed without naming them.
    """
    exclude = set(i for i in exclude_ids if i)
    rows, pmbs, held_back = [], {}, {}
    for e in events:
        if not is_headline(e) or (e.id and e.id in exclude):
            continue
        day = e.start_date.isoformat() if e.start_date else ""
        if _text(e.category) == "Private Members' Bills":
            pmbs[day] = pmbs.get(day, 0) + 1
            if pmbs[day] > PMB_CAP:
                held_back[day] = held_back.get(day, 0) + 1
                continue
        rows.append(e)
    # Stable sort by day keeps the response's Order Paper order within a day.
    rows.sort(key=lambda e: (e.start_date or datetime.date.max))
    return rows, held_back


def first_sitting_week(events):
    """The Monday of the first week in `events` with Commons or Lords chamber
    business, or None. Used in recess to show the business announced for
    the return."""
    days = sorted(e.start_date for e in events
                  if e.start_date and _text(e.house) in ("Commons", "Lords")
                  and _text(e.type) in ("Main Chamber", "Westminster Hall", "Grand Committee"))
    if not days:
        return None
    return days[0] - datetime.timedelta(days=days[0].weekday())
