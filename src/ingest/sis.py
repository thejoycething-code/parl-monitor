"""Statutory Instruments ingester (handoff 4.5).

No reliable server-side date ordering: the laid date is the first non-null of
commonsLayingDate / lordsLayingDate / paperMadeDate, filtered client-side.
Sweep terms must include Act short titles to catch commencement and
consequential regulations (that is how implementation gets tracked).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from urllib.parse import quote

from src.ingest.bills import parse_api_date

SI_API = "https://statutoryinstruments-api.parliament.uk/api/v2/StatutoryInstrument"


@dataclass
class StatutoryInstrument:
    id: str
    name: str
    procedure: str
    commons_laying_date: datetime.date
    lords_laying_date: datetime.date
    paper_made_date: datetime.date
    text_link: str = None        # legislation.gov.uk instrument text (detail only)
    enabling_acts: list = None   # parent Act names (detail only)

    @property
    def tracker_url(self):
        """Public status page: timeline, procedure, dates (not the JSON API)."""
        return "https://statutoryinstruments.parliament.uk/instrument/{0}".format(self.id)

    @property
    def laid_date(self):
        """First non-null of the three date fields (handoff 4.5)."""
        for d in (self.commons_laying_date, self.lords_laying_date, self.paper_made_date):
            if d is not None:
                return d
        return None


def parse_si(value):
    return StatutoryInstrument(
        id=value.get("id"),
        name=value.get("name"),
        procedure=(value.get("procedure") or {}).get("name"),
        commons_laying_date=parse_api_date(value.get("commonsLayingDate")),
        lords_laying_date=parse_api_date(value.get("lordsLayingDate")),
        paper_made_date=parse_api_date(value.get("paperMadeDate")),
    )


def parse_response(payload):
    return [parse_si(item.get("value") or {}) for item in (payload.get("items") or [])]


def parse_si_detail(payload):
    """Detail adds the legislation.gov.uk text link and the enabling Act(s)."""
    v = payload.get("value") or payload
    si = parse_si(v)
    si.text_link = v.get("link")
    si.enabling_acts = [a.get("name") for a in (v.get("enablingActs") or [])]
    return si


def fetch_si_detail(client, si_id):
    url = "{0}/{1}".format(SI_API, si_id)
    return parse_si_detail(client.get_json(url, "si", "detail-{0}".format(si_id)))


def fetch_sis(client, name, take=25):
    url = "{0}?Name={1}&Take={2}".format(SI_API, quote(name), take)
    return parse_response(client.get_json(url, "si", "search-{0}".format(name)))
