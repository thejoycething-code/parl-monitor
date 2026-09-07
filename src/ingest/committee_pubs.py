"""Select committee reports and Government responses (Christopher, 2026-09-07).

The committees feed captured calls for evidence -- the start of an
inquiry. The report and the Government's reply are where recommendations
become policy, and neither was seen. The Committees API lists
publications by type: 1 Report, 2 Government Response, 12 Special Report
(the form a Government response usually takes in the Commons). Measured
2026-09-07: 62 reports, 12 responses and 14 special reports since 1 July.

The public site (committees.parliament.uk) refuses non-browser clients,
so the link is Parliament's canonical publications URL, unverified by
fetch; the API is the source of record here.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

API = "https://committees-api.parliament.uk/api"
PUBLIC = "https://committees.parliament.uk/publications/{id}/"
TYPES = {1: "Report", 2: "Government Response", 12: "Special Report"}


@dataclass
class Publication:
    id: int
    description: str
    type_id: int
    type_name: str
    committee: str
    house: str
    published: datetime.date
    responding_department: str = None
    response_to: int = None
    hc_number: str = None
    business: str = None

    @property
    def url(self):
        return PUBLIC.format(id=self.id)

    @property
    def is_response(self):
        return self.type_id in (2, 12) or bool(self.response_to) or bool(self.responding_department)

    @property
    def text(self):
        return " ".join(x for x in (self.description, self.business, self.committee) if x)


def _date(value):
    v = (value or "")[:10]
    try:
        return datetime.date.fromisoformat(v) if v else None
    except ValueError:
        return None


def parse_publication(row):
    t = row.get("type") or {}
    c = row.get("committee") or {}
    biz = row.get("businesses") or []
    return Publication(
        id=int(row.get("id")), description=(row.get("description") or "").strip(),
        type_id=t.get("id"), type_name=t.get("name") or TYPES.get(t.get("id"), "Publication"),
        committee=c.get("name") or "Committee", house=c.get("house") or "",
        published=_date(row.get("publicationStartDate")),
        responding_department=((row.get("respondingDepartment") or {}).get("name")
                               if isinstance(row.get("respondingDepartment"), dict) else row.get("respondingDepartment")),
        response_to=row.get("responseToPublicationId"), hc_number=row.get("hcNumber"),
        business=(biz[0].get("title") if biz and isinstance(biz[0], dict) else None),
    )


def fetch_publications(client, start, end, types=(1, 2, 12), page=50, max_pages=20):
    out, skip = [], 0
    ids = "&".join("PublicationTypeIds={0}".format(t) for t in types)
    for _ in range(max_pages):
        payload = client.get_json(
            "{0}/Publications?{1}&StartDate={2}&EndDate={3}&Take={4}&Skip={5}".format(API, ids, start, end, page, skip),
            "committees", "publications-{0}-to-{1}-s{2}".format(start, end, skip))
        rows = payload.get("items") or []
        out.extend(parse_publication(r) for r in rows)
        skip += page
        if len(rows) < page or skip >= (payload.get("totalResults") or 0):
            break
    return out
