"""Early Day Motions ingester (handoff 4.4).

Note the literal `parameters.` prefix on every query arg. Response envelope is
{PagingInfo, Response:[...]}. Signature counts are tracked week-on-week via the
edm_signatures table (store SponsorsCount per edition).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from urllib.parse import quote

from src.ingest.bills import parse_api_date

EDM_API = "https://oralquestionsandmotions-api.parliament.uk/EarlyDayMotions/list"


@dataclass
class EDM:
    id: int
    uin: str
    title: str
    motion_text: str
    sponsor_name: str
    sponsor_constituency: str
    signature_count: int
    date_tabled: datetime.date
    member_id: int = None      # primary sponsor's member id (ledger capture)

    @property
    def url(self):
        return "https://edm.parliament.uk/early-day-motion/{0}".format(self.id)


def parse_edm(row):
    sponsor = row.get("PrimarySponsor") or {}
    return EDM(
        id=row.get("Id"),
        uin=row.get("UIN"),
        title=row.get("Title"),
        motion_text=row.get("MotionText"),
        sponsor_name=sponsor.get("Name"),
        sponsor_constituency=sponsor.get("Constituency"),
        signature_count=row.get("SponsorsCount"),
        date_tabled=parse_api_date(row.get("DateTabled")),
        member_id=row.get("MemberId"),
    )


def parse_response(payload):
    return [parse_edm(row) for row in (payload.get("Response") or [])]


def fetch_edms(client, term, take=10):
    url = "{0}?parameters.searchTerm={1}&parameters.take={2}".format(EDM_API, quote(term), take)
    return parse_response(client.get_json(url, "edm", "search-{0}".format(term)))


def record_signatures(conn, edm, edition):
    """Store this edition's signature count (edm_signatures PK = edm_id+edition)."""
    conn.execute(
        "INSERT OR REPLACE INTO edm_signatures (edm_id, edition, count) VALUES (?, ?, ?)",
        (edm.id, edition, edm.signature_count),
    )
    conn.commit()


def signature_delta(conn, edm_id, edition, prior_edition):
    """Change in signatures between two editions, or None if no prior count."""
    def _count(ed):
        row = conn.execute(
            "SELECT count FROM edm_signatures WHERE edm_id = ? AND edition = ?", (edm_id, ed)
        ).fetchone()
        return row["count"] if row else None

    now, before = _count(edition), _count(prior_edition)
    if now is None or before is None:
        return None
    return now - before
