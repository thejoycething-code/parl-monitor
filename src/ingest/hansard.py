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


def spoken_form(term):
    """A sweep term as Hansard wants it: hyphens back to spaces.

    config/settings.yaml is hyphenated for the Written Questions API, which
    needs it to force a phrase match ("age assurance" returned 77,980 near-
    random results; "age-assurance" returned 258). Hansard is a different API
    and did not ask for any of that. Mostly it does not care -- measured
    2026-08-17, "assisted-dying" 501 against "assisted dying" 522 -- but
    "abortion-clinics" returned 0 where "abortion clinics" returned 3, so the
    hyphens we added for one API were quietly costing hits in the other.

    Only hyphens BETWEEN words are relaxed. A term is left alone if the
    de-hyphenated form measured worse (see NO_RELAX), because a hyphen is
    sometimes part of the word rather than a phrase separator.
    """
    if term in NO_RELAX:
        return term
    return " ".join(term.replace("-", " ").split())


# Terms whose de-hyphenated form measured no better in Hansard and reads
# wrong as separate words. Kept explicit rather than inferred: this is a
# measured exception list, not a rule.
NO_RELAX = frozenset()


def search_contributions(client, term, start, end, page_size=100, max_pages=20):
    """All spoken contributions matching a term in a date range (both Houses,
    paged)."""
    out, skip = [], 0
    for _ in range(max_pages):
        url = ("{0}/search/contributions/Spoken.json?queryParameters.searchTerm={1}"
               "&queryParameters.startDate={2}&queryParameters.endDate={3}"
               "&queryParameters.skip={4}&queryParameters.take={5}").format(
                   HANSARD_API, quote(term), start, end, skip, page_size)
        # The archive slug carries the FULL range, not start[:4]. With just the
        # year, "hansard_search-digital-id-2026-s0.json.gz" looked like a whole-
        # year search when the weekly actually asks for one week -- which is how
        # a run of legitimate recess zeroes got misread as a broken sweep
        # (2026-08-20). The filename should say what was requested.
        batch = parse_response(client.get_json(
            url, "hansard", "search-{0}-{1}-to-{2}-s{3}".format(
                term, start, end, skip)))
        out.extend(batch)
        if len(batch) < page_size:
            break
        skip += page_size
    return out
