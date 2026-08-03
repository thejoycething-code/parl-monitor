"""Bills ingester (handoff section 4.1).

Fetches bill detail and stages from bills-api.parliament.uk and normalises them
into a Bill object. Everything is keyed on billId, never title: two live bills
share the title "Terminally Ill Adults (End of Life) Bill" (IDs 3774 and 4157).

The board state machine (board.py) consumes Bill objects; this module only
fetches, archives (via HttpClient) and parses.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

BILLS_API = "https://bills-api.parliament.uk/api/v1"


def bill_page_url(bill_id):
    return "https://bills.parliament.uk/bills/{0}".format(bill_id)


def parse_api_date(value):
    """Parse an API datetime like '2026-09-11T00:00:00' into a date.

    Returns None for empty/None. Only the date part is significant for the
    board (sittings are day-granularity).
    """
    if not value:
        return None
    text = str(value).split("T", 1)[0]
    return datetime.date.fromisoformat(text)


@dataclass
class Stage:
    description: str
    house: str
    sittings: list  # list[datetime.date], ascending


@dataclass
class Bill:
    bill_id: int
    short_title: str
    is_act: bool
    is_defeated: bool
    originating_house: str
    current_house: str
    current_stage: str
    introduced_session_id: int
    included_session_ids: list
    last_update: str
    sponsor_name: str
    sponsor_party: str
    stages: list = field(default_factory=list)  # list[Stage]

    @property
    def url(self):
        return bill_page_url(self.bill_id)

    def all_sittings(self):
        """Every stage sitting date across all stages, ascending."""
        dates = [d for stage in self.stages for d in stage.sittings]
        return sorted(dates)

    def next_key_date(self, run_date):
        """Earliest stage sitting on or after run_date, else None (-> TBA)."""
        future = [d for d in self.all_sittings() if d >= run_date]
        return min(future) if future else None

    def last_sitting_date(self):
        """Latest stage sitting date; the point a fallen bill froze at."""
        sittings = self.all_sittings()
        return sittings[-1] if sittings else None

    def royal_assent_date(self):
        """Date of the Royal Assent stage sitting, if any.

        NOTE: this is the parliamentary Royal Assent stage date from bills-api.
        It is not necessarily a section's commencement/in-force date, which
        legislation.gov.uk carries (handoff section 4.8). See docs/api-notes.md.
        """
        for stage in self.stages:
            if "royal assent" in (stage.description or "").lower():
                if stage.sittings:
                    return max(stage.sittings)
        return None

    def stage_sittings(self, description, house=None):
        """Sitting dates for stages matching a description (and optional house)."""
        out = []
        for stage in self.stages:
            if (stage.description or "").lower() == description.lower():
                if house is None or (stage.house or "").lower() == house.lower():
                    out.extend(stage.sittings)
        return sorted(out)


def parse_stages(stages_payload):
    """Turn a Stages API payload into a list[Stage]."""
    result = []
    for item in (stages_payload.get("items") or []):
        sittings = sorted(
            d for d in (parse_api_date(s.get("date")) for s in (item.get("stageSittings") or [])) if d
        )
        result.append(Stage(description=item.get("description"), house=item.get("house"), sittings=sittings))
    return result


def parse_bill(detail, stages_payload):
    """Combine a Bill detail payload and a Stages payload into a Bill."""
    sponsors = detail.get("sponsors") or []
    member = (sponsors[0].get("member") or {}) if sponsors else {}
    return Bill(
        bill_id=detail.get("billId"),
        short_title=detail.get("shortTitle"),
        is_act=bool(detail.get("isAct")),
        is_defeated=bool(detail.get("isDefeated")),
        originating_house=detail.get("originatingHouse"),
        current_house=detail.get("currentHouse"),
        current_stage=(detail.get("currentStage") or {}).get("description"),
        introduced_session_id=detail.get("introducedSessionId"),
        included_session_ids=list(detail.get("includedSessionIds") or []),
        last_update=detail.get("lastUpdate"),
        sponsor_name=member.get("name"),
        sponsor_party=member.get("party"),
        stages=parse_stages(stages_payload),
    )


# -- live fetch helpers (thin; archiving happens inside the client) ----------

def fetch_bill_detail(client, bill_id):
    return client.get_json("{0}/Bills/{1}".format(BILLS_API, bill_id), "bills", "detail-{0}".format(bill_id))


def fetch_bill_stages(client, bill_id, take=30):
    url = "{0}/Bills/{1}/Stages?Take={2}".format(BILLS_API, bill_id, take)
    return client.get_json(url, "bills", "stages-{0}".format(bill_id))


def search_bills(client, term, take=15):
    from urllib.parse import quote
    url = "{0}/Bills?SearchTerm={1}&SortOrder=DateUpdatedDescending&Take={2}".format(
        BILLS_API, quote(term), take
    )
    return client.get_json(url, "bills", "search-{0}".format(term))


def load_bill(client, bill_id):
    """Fetch + parse a Bill in one call."""
    return parse_bill(fetch_bill_detail(client, bill_id), fetch_bill_stages(client, bill_id))
