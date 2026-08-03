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
    house: str
    category: str
    type: str
    description: str
    bill_id: int
    bill_name: str
    committee: str
    location: str


def parse_event(row):
    return Event(
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
    """Some fields arrive as dicts ({'Name': ...}) rather than strings."""
    if isinstance(value, dict):
        return value.get("Name") or value.get("name") or ""
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
