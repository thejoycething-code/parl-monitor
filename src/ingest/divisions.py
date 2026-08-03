"""Divisions ingester (handoff 4.6).

Commons list carries Aye/No counts; Lords list returns null counts, so a
shortlisted Lords division must fetch its detail endpoint for counts. Division
titles are matched against the ENTITY watchlist (bill titles + acts_watch short
titles), not just keywords: the 8 July Children's Wellbeing SI approval slipped
past keyword matching in the pilot.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from src.ingest.bills import parse_api_date

COMMONS_API = "https://commonsvotes-api.parliament.uk/data"
LORDS_API = "https://lordsvotes-api.parliament.uk/data"


@dataclass
class Division:
    id: int
    house: str
    number: int
    title: str
    date: datetime.date
    aye_count: int
    no_count: int

    @property
    def url(self):
        if self.house == "Lords":
            return "https://lordsvotes-api.parliament.uk/data/Division/{0}".format(self.id)
        return "https://commonsvotes-api.parliament.uk/data/division/{0}.json".format(self.id)


def parse_commons_division(row):
    return Division(
        id=row.get("DivisionId"), house="Commons", number=row.get("Number"),
        title=row.get("Title"), date=parse_api_date(row.get("Date")),
        aye_count=row.get("AyeCount"), no_count=row.get("NoCount"),
    )


def parse_lords_division(row):
    # Lords list view: content/notContent counts are null; fetch detail when shortlisted.
    return Division(
        id=row.get("divisionId") or row.get("DivisionId"), house="Lords",
        number=row.get("number") or row.get("Number"),
        title=row.get("title") or row.get("Title"),
        date=parse_api_date(row.get("date") or row.get("Date")),
        aye_count=row.get("contentCount") or row.get("ContentCount"),
        no_count=row.get("notContentCount") or row.get("NotContentCount"),
    )


def parse_commons_response(payload):
    # Commons search returns a bare JSON array.
    return [parse_commons_division(row) for row in (payload or [])]


def fetch_commons_divisions(client, date):
    url = ("{0}/divisions.json/search?queryParameters.startDate={1}"
           "&queryParameters.endDate={1}&queryParameters.take=60").format(COMMONS_API, date)
    return parse_commons_response(client.get_json(url, "division", "commons-{0}".format(date)))


def fetch_lords_divisions(client, start, end):
    url = "{0}/Divisions/search?StartDate={1}&EndDate={2}".format(LORDS_API, start, end)
    payload = client.get_json(url, "division", "lords-{0}-{1}".format(start, end))
    return [parse_lords_division(row) for row in (payload or [])]


def _norm(text):
    """Lowercase and fold smart quotes so 'Children's' matches 'Children's'."""
    if not text:
        return ""
    return (text.replace("’", "'").replace("‘", "'")
                .replace("“", '"').replace("”", '"').lower())


def matches_watchlist(title, entities):
    """Entity titles (bill titles, acts_watch shorts) found in a division title."""
    low = _norm(title)
    return [e for e in entities if e and _norm(e) in low]
