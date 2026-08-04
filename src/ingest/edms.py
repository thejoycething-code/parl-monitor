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
EDM_DETAIL_API = "https://oralquestionsandmotions-api.parliament.uk/EarlyDayMotion"


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


def fetch_edms(client, term, take=10, skip=0, tabled_from=None, tabled_to=None):
    url = "{0}?parameters.searchTerm={1}&parameters.take={2}&parameters.skip={3}".format(
        EDM_API, quote(term), take, skip)
    slug = "search-{0}".format(term)
    if tabled_from:
        url += "&parameters.tabledStartDate={0}&parameters.tabledEndDate={1}".format(
            tabled_from, tabled_to)
        slug = "search-{0}-{1}-s{2}".format(term, tabled_from, skip)
    return parse_response(client.get_json(url, "edm", slug))


@dataclass
class Sponsor:
    member_id: int
    name: str
    party: str
    seat: str
    order: int          # 1 = primary sponsor; >1 = co-signatory
    withdrawn: bool


def parse_sponsors(payload):
    """Sponsor rows from an EDM detail response, live signatures only."""
    detail = payload.get("Response") or {}
    out = []
    for s in (detail.get("Sponsors") or []):
        m = s.get("Member") or {}
        out.append(Sponsor(
            member_id=s.get("MemberId"),
            name=m.get("Name"),
            party=m.get("Party"),
            seat=m.get("Constituency"),
            order=s.get("SponsoringOrder"),
            withdrawn=bool(s.get("IsWithdrawn")),
        ))
    return out


def fetch_sponsors(client, edm_id):
    """Full sponsor list for one EDM (one API call; embeds member details,
    so co-signatories never need Members API resolution)."""
    url = "{0}/{1}".format(EDM_DETAIL_API, edm_id)
    return parse_sponsors(client.get_json(url, "edm", "detail-{0}".format(edm_id)))


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
