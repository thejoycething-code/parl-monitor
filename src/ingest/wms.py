"""Written ministerial statements ingester (handoff 4.3).

Same host as the PQ API but this endpoint tolerates the date filter
(madeWhenFrom). Duplicate rows appear (same statement, both Houses): dedupe on
title+date. Filter title+text against the taxonomy client-side (step 4).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from src.ingest.bills import parse_api_date

WMS_API = "https://questions-statements-api.parliament.uk/api/writtenstatements/statements"


@dataclass
class WrittenStatement:
    id: int
    uin: str
    title: str
    text: str
    made_when: datetime.date
    house: str
    answering_body: str


def _value(row):
    return row.get("value") or row


def parse_statement(row):
    value = _value(row)
    return WrittenStatement(
        id=value.get("id"),
        uin=value.get("uin"),
        title=value.get("title") or value.get("heading"),
        text=value.get("text") or value.get("statementText"),
        made_when=parse_api_date(value.get("dateMade") or value.get("madeWhen")),
        house=value.get("house"),
        answering_body=value.get("answeringBodyName"),
    )


def parse_response(payload):
    rows = payload.get("results") if isinstance(payload, dict) else payload
    return dedupe([parse_statement(row) for row in (rows or [])])


def dedupe(statements):
    """Drop duplicate (title, date) rows that appear once per House."""
    seen = set()
    out = []
    for s in statements:
        key = (s.title, s.made_when)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def fetch_statements(client, made_when_from, take=60):
    url = "{0}?madeWhenFrom={1}&take={2}".format(WMS_API, made_when_from, take)
    return parse_response(client.get_json(url, "wms", "from-{0}".format(made_when_from)))
