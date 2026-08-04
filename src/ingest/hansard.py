"""Hansard spoken-contributions ingester (handoff 4.13; built 2026-08-04 for
the historic backlog, ahead of the September weekly wiring).

The search endpoint returns full contribution text plus the member's MNIS id
and the external ids needed for a public deep link. Speeches are the richest
text-derived stance evidence: a member choosing to speak is expressing their
own position, unlike a whipped vote.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from urllib.parse import quote

HANSARD_API = "https://hansard-api.parliament.uk"


@dataclass
class Contribution:
    ext_id: str
    member_id: int
    member_name: str
    date: datetime.date
    house: str
    debate_title: str
    text: str
    debate_ext_id: str

    @property
    def url(self):
        """Public Hansard page, anchored to this contribution."""
        return "https://hansard.parliament.uk/{0}/{1}/debates/{2}/#contribution-{3}".format(
            self.house, self.date.isoformat(), self.debate_ext_id, self.ext_id)


def parse_contribution(row):
    raw_date = (row.get("SittingDate") or "")[:10]
    return Contribution(
        ext_id=row.get("ContributionExtId"),
        member_id=row.get("MemberId"),
        member_name=row.get("MemberName"),
        date=datetime.date.fromisoformat(raw_date) if raw_date else None,
        house=row.get("House"),
        debate_title=row.get("DebateSection"),
        text=row.get("ContributionTextFull") or row.get("ContributionText") or "",
        debate_ext_id=row.get("DebateSectionExtId"),
    )


def parse_response(payload):
    return [parse_contribution(row) for row in (payload.get("Results") or [])]


def search_contributions(client, term, start, end, page_size=100, max_pages=20):
    """All spoken contributions matching a term in a date range (both Houses,
    paged)."""
    out, skip = [], 0
    for _ in range(max_pages):
        url = ("{0}/search/contributions/Spoken.json?queryParameters.searchTerm={1}"
               "&queryParameters.startDate={2}&queryParameters.endDate={3}"
               "&queryParameters.skip={4}&queryParameters.take={5}").format(
                   HANSARD_API, quote(term), start, end, skip, page_size)
        batch = parse_response(client.get_json(
            url, "hansard", "search-{0}-{1}-s{2}".format(term, start[:4], skip)))
        out.extend(batch)
        if len(batch) < page_size:
            break
        skip += page_size
    return out
