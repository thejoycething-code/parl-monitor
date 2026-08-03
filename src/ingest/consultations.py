"""gov.uk open consultations ingester (handoff 4.10).

Fast and reliable. Titles are matched against the taxonomy plus a broadened
area-6 set (government labels rarely match campaign vocabulary), but that
matching is the filter's job (step 4); this module only fetches and parses.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from src.ingest.bills import parse_api_date

GOVUK_SEARCH = "https://www.gov.uk/api/search.json"


@dataclass
class Consultation:
    title: str
    link: str
    end_date: datetime.date
    organisations: list

    @property
    def url(self):
        if self.link and self.link.startswith("/"):
            return "https://www.gov.uk{0}".format(self.link)
        return self.link


def parse_consultation(row):
    orgs = [o.get("title") for o in (row.get("organisations") or []) if isinstance(o, dict)]
    return Consultation(
        title=row.get("title"),
        link=row.get("link"),
        end_date=parse_api_date(row.get("end_date")),
        organisations=orgs,
    )


def parse_response(payload):
    return [parse_consultation(row) for row in (payload.get("results") or [])]


def fetch_open_consultations(client, count=200):
    url = ("{0}?filter_content_store_document_type=open_consultation&count={1}"
           "&fields=title,link,end_date,organisations").format(GOVUK_SEARCH, count)
    return parse_response(client.get_json(url, "consultation", "govuk-open-{0}".format(count)))
