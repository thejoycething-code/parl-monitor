"""Scottish Parliament ingester (handoff 4.11).

Two sources, different jobs:

  * `data.parliament.scot/api/bills` returns the full bills dataset (473 rows).
    It carries identity only (ID, Reference, ShortName, FullName) and NO status,
    so it cannot tell us whether a bill fell or passed. Cached for 30 days.
    (The pilot saw this endpoint time out at 60s; it responded in ~5s on
    2026-08-01. See docs/api-notes.md.)
  * The bill page `parliament.scot/bills-and-laws/bills/s6/{slug}` carries the
    status sentence and is the proven route to it.

Status parsing trap: the bill page also contains "Current status:" lines that
belong to *motions* on the page, not to the bill. Keying on that string yields a
motion date. The bill's own status is the sentence "The Bill fell on {date} at
{stage}" (or a Royal Assent / passed equivalent), so match that shape instead.
"""

from __future__ import annotations

import datetime
import html
import re
from dataclasses import dataclass

SCOT_API = "https://data.parliament.scot/api/bills"
BILL_PAGE = "https://www.parliament.scot/bills-and-laws/bills/s6/{slug}"
CACHE_DAYS = 30

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june",
     "july", "august", "september", "october", "november", "december"], start=1)}

# "The Bill fell on 17 March 2026 at Stage 3"
_FELL = re.compile(
    r"\bBill fell on\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})(?:\s+at\s+(Stage\s*\d|[A-Za-z0-9 ]{3,20}?))?(?=[.<]|\s{2}|\s+[A-Z])",
    re.I)
# "received Royal Assent on 4 June 2026" / "The Bill was passed on ..."
_ASSENT = re.compile(r"\bRoyal Assent(?:\s+on)?\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", re.I)
_PASSED = re.compile(r"\bBill was passed on\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", re.I)

FELL = "fell"
ASSENT = "royal_assent"
PASSED = "passed"
LIVE = "live"


@dataclass
class HolyroodBill:
    slug: str
    title: str
    status: str                    # fell | royal_assent | passed | live
    status_date: datetime.date
    stage: str
    areas: list

    @property
    def url(self):
        return BILL_PAGE.format(slug=self.slug)

    @property
    def is_terminal(self):
        return self.status in (FELL, ASSENT, PASSED)

    def closed_note(self):
        if self.status == FELL:
            at = " at {0}".format(self.stage) if self.stage else ""
            return "Fell on {0}{1}".format(self.status_date.isoformat() if self.status_date else "unknown", at)
        if self.status == ASSENT:
            return "Royal Assent {0}".format(self.status_date.isoformat() if self.status_date else "unknown")
        if self.status == PASSED:
            return "Passed {0}".format(self.status_date.isoformat() if self.status_date else "unknown")
        return None


def _to_date(day, month_name, year):
    month = MONTHS.get((month_name or "").lower())
    if not month:
        return None
    try:
        return datetime.date(int(year), month, int(day))
    except ValueError:
        return None


def strip_html(page):
    """Tags out, entities decoded, whitespace collapsed."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_status(page):
    """Return (status, date, stage) from a Holyrood bill page."""
    text = strip_html(page)

    m = _FELL.search(text)
    if m:
        stage = (m.group(4) or "").strip() or None
        return FELL, _to_date(m.group(1), m.group(2), m.group(3)), stage

    m = _ASSENT.search(text)
    if m:
        return ASSENT, _to_date(m.group(1), m.group(2), m.group(3)), None

    m = _PASSED.search(text)
    if m:
        return PASSED, _to_date(m.group(1), m.group(2), m.group(3)), None

    return LIVE, None, None


# -- fetch ------------------------------------------------------------------

def fetch_bill(client, slug, title=None, areas=None, timeout=45):
    page = client.get_text(BILL_PAGE.format(slug=slug), "scotland", "bill-{0}".format(slug), timeout=timeout)
    status, status_date, stage = parse_status(page)
    return HolyroodBill(slug=slug, title=title or slug, status=status,
                        status_date=status_date, stage=stage, areas=list(areas or []))


def fetch_bills_index(client, timeout=90):
    """Full bills dataset (identity only). Long timeout per handoff 4.11."""
    return client.get_json(SCOT_API, "scotland", "bills-api", timeout=timeout)


def find_in_index(index, title_fragment):
    """Locate a bill in the API index by title fragment (identity lookup)."""
    low = (title_fragment or "").lower()
    return [b for b in (index or [])
            if low in (b.get("FullName") or "").lower() or low in (b.get("ShortName") or "").lower()]


def load_watched(client, watchlist_holyrood):
    """Fetch each watched Holyrood bill from watchlist.yaml's holyrood: block."""
    out = []
    for entry in (watchlist_holyrood or []):
        out.append(fetch_bill(client, entry.get("slug"), title=entry.get("title"), areas=entry.get("areas")))
    return out
