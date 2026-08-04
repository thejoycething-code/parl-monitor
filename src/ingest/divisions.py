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
        """Public division page (votes.parliament.uk), not the JSON API."""
        house = "Lords" if self.house == "Lords" else "Commons"
        return "https://votes.parliament.uk/Votes/{0}/Division/{1}".format(house, self.id)


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


@dataclass
class Voter:
    member_id: int
    name: str
    party: str
    seat: str
    vote: str            # 'aye' | 'no' (Lords content/not-content normalised)


def parse_commons_breakdown(payload):
    """(Division, [Voter...]) from a Commons division detail response."""
    division = parse_commons_division(payload)
    voters = []
    for side, vote in (("Ayes", "aye"), ("Noes", "no")):
        for m in (payload.get(side) or []):
            voters.append(Voter(member_id=m.get("MemberId"), name=m.get("Name"),
                                party=m.get("Party"), seat=m.get("MemberFrom"),
                                vote=vote))
    return division, voters


def parse_lords_breakdown(payload):
    """(Division, [Voter...]); Lords contents/notContents map to aye/no."""
    division = parse_lords_division(payload)
    voters = []
    for side, vote in (("contents", "aye"), ("notContents", "no")):
        for m in (payload.get(side) or []):
            voters.append(Voter(member_id=m.get("memberId"), name=m.get("name"),
                                party=m.get("party"), seat=m.get("memberFrom"),
                                vote=vote))
    return division, voters


def fetch_commons_breakdown(client, division_id):
    url = "{0}/division/{1}.json".format(COMMONS_API, division_id)
    return parse_commons_breakdown(
        client.get_json(url, "division", "cdetail-{0}".format(division_id)))


def fetch_lords_breakdown(client, division_id):
    url = "{0}/Divisions/{1}".format(LORDS_API, division_id)
    return parse_lords_breakdown(
        client.get_json(url, "division", "ldetail-{0}".format(division_id)))


def search_commons_divisions(client, term, start, end, page_size=100):
    """All Commons divisions matching a title term in a date range (paged)."""
    from urllib.parse import quote
    out, skip = [], 0
    while True:
        url = ("{0}/divisions.json/search?queryParameters.searchTerm={1}"
               "&queryParameters.startDate={2}&queryParameters.endDate={3}"
               "&queryParameters.skip={4}&queryParameters.take={5}").format(
                   COMMONS_API, quote(term), start, end, skip, page_size)
        batch = parse_commons_response(client.get_json(
            url, "division", "csearch-{0}-{1}-{2}".format(term, start, skip)))
        out.extend(batch)
        if len(batch) < page_size:
            return out
        skip += page_size


def search_lords_divisions(client, term, start, end, page_size=100):
    from urllib.parse import quote
    out, skip = [], 0
    while True:
        url = ("{0}/Divisions/search?SearchTerm={1}&StartDate={2}&EndDate={3}"
               "&skip={4}&take={5}").format(LORDS_API, quote(term), start, end,
                                            skip, page_size)
        payload = client.get_json(
            url, "division", "lsearch-{0}-{1}-{2}".format(term, start, skip))
        batch = [parse_lords_division(row) for row in (payload or [])]
        out.extend(batch)
        if len(batch) < page_size:
            return out
        skip += page_size


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
