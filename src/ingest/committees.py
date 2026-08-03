"""Committee calls-for-evidence ingester (handoff 4.12, Phase 2).

The handoff left this endpoint untested; probed live 2026-08-03:

  * GET /api/CommitteeBusiness?CurrentlyAcceptingEvidence=true is the lever --
    the unfiltered listing returns decades-old closed business.
  * Deadline = openSubmissionPeriods[0].endDate (datetime; date part used).
    Some open calls carry no period end (rolling submissions) -> deadline None.
  * Neither the list nor the detail view carries committee names; they resolve
    via GET /api/Committees?CommitteeBusinessId={id}, so names are fetched for
    shortlisted (taxonomy-matched) items only, like member resolution.
  * Public page: https://committees.parliament.uk/work/{id}/
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from src.ingest.bills import parse_api_date

COMMITTEES_API = "https://committees-api.parliament.uk/api"


@dataclass
class CallForEvidence:
    id: int
    title: str
    type_name: str
    deadline: datetime.date          # None for rolling/open-ended calls
    committees: list = field(default_factory=list)

    @property
    def url(self):
        return "https://committees.parliament.uk/work/{0}/".format(self.id)


def parse_business(value):
    periods = value.get("openSubmissionPeriods") or []
    deadline = parse_api_date(periods[0].get("endDate")) if periods else None
    return CallForEvidence(
        id=value.get("id"),
        title=value.get("title"),
        type_name=(value.get("type") or {}).get("name") or "Inquiry",
        deadline=deadline,
    )


def parse_response(payload):
    return [parse_business(item.get("value") or item) for item in (payload.get("items") or [])]


def fetch_open_calls(client, take=50):
    url = "{0}/CommitteeBusiness?CurrentlyAcceptingEvidence=true&Take={1}".format(COMMITTEES_API, take)
    return parse_response(client.get_json(url, "committee", "accepting-evidence"))


def resolve_committees(client, business_id):
    """Committee names for one business item (shortlisted items only)."""
    url = "{0}/Committees?CommitteeBusinessId={1}&Take=5".format(COMMITTEES_API, business_id)
    payload = client.get_json(url, "committee", "committees-for-{0}".format(business_id))
    return [(item.get("value") or item).get("name") for item in (payload.get("items") or [])]
