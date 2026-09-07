"""UK Parliament e-petitions (petition.parliament.uk): the early-warning feed.

Christopher, 2026-09-07: "Build the e-petitions early warning." Both
Westminster Hall debates on 7 September 2026 -- surrogacy law, misogyny as
a hate crime -- came from petitions crossing 100,000 signatures; What's On
showed them a fortnight before the day, the petition site had shown them
coming for months. The thresholds are public and mechanical: 10,000
signatures earn a Government response, 100,000 put the petition before
the Petitions Committee for a debate. A petition on our ground climbing
towards either is a campaign trigger with a lead time.

The JSON API pages 25 at a time (91 pages of open petitions measured
2026-09-07), ordered by signature count, with `links.next` for paging and
`state=` for the lifecycle filter. No text search, so every open petition
is fetched and the taxonomy filter runs over action + background +
details here. Pages are NOT archived under data/raw (archive=False): the
store's snapshot table is the record, and 90 files a week of a listing
the API serves canonically would grow the repo for nothing.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

API = "https://petition.parliament.uk/petitions.json"
PAGE_URL = "https://petition.parliament.uk/petitions/{0}"
RESPONSE_THRESHOLD = 10000
DEBATE_THRESHOLD = 100000
# Petitions that can still move: open ones, and those past a threshold
# waiting on the Government or the Committee.
STATES = ("open", "awaiting_response", "awaiting_debate")


@dataclass
class Petition:
    id: int
    action: str
    background: str
    details: str
    state: str
    signatures: int
    opened_at: str = None            # ISO date
    closing_date: str = None
    response_reached: str = None     # 10,000 crossed (ISO date)
    government_response_at: str = None
    debate_reached: str = None       # 100,000 crossed (ISO date)
    debate_scheduled_on: str = None  # the day the Committee fixed a date
    scheduled_debate_date: str = None
    debate_outcome_at: str = None
    departments: list = field(default_factory=list)
    topics: list = field(default_factory=list)

    @property
    def url(self):
        return PAGE_URL.format(self.id)

    @property
    def text(self):
        return " ".join(x for x in (self.action, self.background, self.details) if x)


def _day(value):
    return (value or "")[:10] or None


def parse_petition(row):
    a = row.get("attributes") or {}
    return Petition(
        id=row.get("id"), action=(a.get("action") or "").strip(),
        background=(a.get("background") or "").strip(),
        details=(a.get("additional_details") or "").strip(),
        state=a.get("state"), signatures=a.get("signature_count") or 0,
        opened_at=_day(a.get("opened_at")), closing_date=_day(a.get("closing_date")),
        response_reached=_day(a.get("response_threshold_reached_at")),
        government_response_at=_day(a.get("government_response_at")),
        debate_reached=_day(a.get("debate_threshold_reached_at")),
        debate_scheduled_on=_day(a.get("debate_scheduled_on")),
        scheduled_debate_date=_day(a.get("scheduled_debate_date")),
        debate_outcome_at=_day(a.get("debate_outcome_at")),
        departments=[d.get("name") for d in (a.get("departments") or []) if isinstance(d, dict) and d.get("name")],
        topics=[t.get("name") if isinstance(t, dict) else t for t in (a.get("topics") or [])],
    )


def parse_response(payload):
    """(petitions, next_url) from one page."""
    rows = [parse_petition(r) for r in (payload.get("data") or [])]
    return rows, (payload.get("links") or {}).get("next")


def fetch_all(client, states=STATES, max_pages=150):
    """Every petition in the given states, paged; the same id may appear in
    two states during a transition -- the last seen wins."""
    seen = {}
    for state in states:
        url = "{0}?state={1}".format(API, state)
        pages = 0
        while url and pages < max_pages:
            payload = client.get_json(url, "petitions", "{0}-p{1}".format(state, pages + 1), archive=False)
            rows, url = parse_response(payload)
            for p in rows:
                if p.id:
                    seen[p.id] = p
            pages += 1
    return list(seen.values())


def milestone(p, today=None):
    """One plain-English line on where the petition stands in the process."""
    today = today or datetime.date.today()
    if p.scheduled_debate_date and p.scheduled_debate_date >= today.isoformat():
        return "Debate scheduled for {0}".format(p.scheduled_debate_date)
    if p.debate_outcome_at:
        return "Debated {0}".format(p.scheduled_debate_date or p.debate_outcome_at)
    if p.debate_reached:
        return "Passed 100,000 on {0}; debate to be scheduled".format(p.debate_reached)
    if p.government_response_at:
        return "Government responded {0}; {1:,} more to a debate".format(
            p.government_response_at, max(DEBATE_THRESHOLD - p.signatures, 0))
    if p.response_reached:
        return "Passed 10,000 on {0}; Government response due".format(p.response_reached)
    if p.closing_date:
        return "{0:,} to a Government response; closes {1}".format(
            max(RESPONSE_THRESHOLD - p.signatures, 0), p.closing_date)
    return "{0:,} to a Government response".format(max(RESPONSE_THRESHOLD - p.signatures, 0))


def exclusions(settings):
    """{petition id} named in settings.petition_exclusions. Each entry must
    carry a reason: an exclusion nobody can explain is a silent suppression."""
    out = set()
    for entry in (settings or {}).get("petition_exclusions") or []:
        if isinstance(entry, dict) and entry.get("id") is not None:
            if not entry.get("reason"):
                raise ValueError("petition_exclusions: id {0} has no reason".format(entry["id"]))
            out.add(int(entry["id"]))
    return out
