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


def fetch_sis(client, name, take=25):
    url = "{0}?Name={1}&Take={2}".format(SI_API, quote(name), take)
    return parse_response(client.get_json(url, "si", "search-{0}".format(name)))
