"""Scottish Parliament (Holyrood) watching-brief ingester (2026-08-20).

Sits beside scotland.py, which does one older job -- scraping bill STATUS from
the public bill pages for the Westminster board -- and keeps it. This module
speaks data.parliament.scot's open data API for the watching brief proper:
questions (with answers inline), motions, the roster, and party history.

What probing established, so nobody re-learns it:

  * There is NO search API. Questions come as WHOLE-YEAR dumps
    (?year=N, ~7MB/4,700 rows for 2026) and motions as ONE dump of everything
    since 1999 (110MB, 84,751 rows) -- the ?year= parameter on the motions
    endpoint is accepted and silently IGNORED, so check sizes, not statuses.
    No search means no sweep terms: the taxonomy classifies every row.
  * The portal's own API list advertises `Votesmotions` (plural): it 404s.
    The real endpoint is singular lowercase `votesmotion?year=N`.
  * Questions carry AnswerText INLINE -- no second fetch per answer, where NI
    spent 8 minutes a week re-fetching answered questions until guarded.
  * /api/memberparties publishes party membership as DATE RANGES
    (ValidFromDate/ValidUntilDate, null = current), so party-as-at-date needs
    no reconstruction. 976 rows; 129 current, which is exactly the chamber.
  * Text fields carry HTML entities (&rsquo;, &pound;): unescape on parse.

Year dumps are fetched with archive=False: data/raw is committed to git weekly
and the API serves these canonically by year, re-fetchable at will. The STORE
keeps the text (sp_items.body), so offline re-classification never re-fetches.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

API = "https://data.parliament.scot/api"

QUESTIONS_URL = API + "/Motionsquestionsanswersquestions?year={0}"
MOTIONS_URL = API + "/Motionsquestionsanswersmotions"
MEMBERS_URL = API + "/members"
MEMBER_PARTIES_URL = API + "/memberparties"
PARTIES_URL = API + "/parties"


def clean(text):
    """Unescape HTML entities and normalise whitespace. Never None."""
    return " ".join(html.unescape(text or "").split())


def day(value):
    """'2026-01-05T10:03:41.207' -> '2026-01-05'. None-safe."""
    return (value or "")[:10] or None


@dataclass
class Row:
    uid: str            # UniqueID -- the stable key
    kind: str           # question | motion
    reference: str      # EventID, e.g. 'S6W-12345'; motions may have none
    title: str
    body: str           # ItemText, cleaned; the classification text
    dated: str          # submission date
    msp_id: str
    party: str          # as carried on the row by the API itself
    answer: str
    answered: str
    answered_by: str
    cross_party: bool


def parse_row(raw, kind):
    return Row(
        uid=str(raw.get("UniqueID") or ""),
        kind=kind,
        reference=str(raw.get("EventID") or "") or None,
        title=clean(raw.get("Title"))[:300],
        body=clean(raw.get("ItemText")),
        dated=day(raw.get("SubmissionDateTime")) or day(raw.get("ApprovedDate")),
        msp_id=str(raw.get("MSPID") or "") or None,
        party=clean(raw.get("Party")) or None,
        answer=clean(raw.get("AnswerText")) or None,
        answered=day(raw.get("AnswerDate")),
        answered_by=str(raw.get("AnsweredByMSP") or "") or None,
        cross_party=bool(raw.get("CrossPartySupport")),
    )


def parse_questions(payload):
    return [parse_row(r, "question") for r in (payload or []) if r.get("UniqueID")]


def parse_motions(payload, since=None):
    """Motions, optionally floored by submission date.

    The dump is everything since 1999; the caller floors it because storing
    84,751 motion texts would add ~100MB to a database that is committed to
    git weekly, for rows the watching brief will never look at.
    """
    out = []
    for r in payload or []:
        if not r.get("UniqueID"):
            continue
        if since and (day(r.get("SubmissionDateTime")) or "") < since:
            continue
        out.append(parse_row(r, "motion"))
    return out


@dataclass
class Member:
    person_id: str
    name: str
    preferred_name: str
    is_current: bool


def parse_members(payload):
    return [Member(person_id=str(r.get("PersonID") or ""),
                   name=clean(r.get("ParliamentaryName")),
                   preferred_name=clean(r.get("PreferredName")),
                   is_current=bool(r.get("IsCurrent")))
            for r in (payload or []) if r.get("PersonID")]


@dataclass
class Affiliation:
    row_id: str
    person_id: str
    party_id: str
    valid_from: str
    valid_until: str    # None = current


def parse_affiliations(payload):
    return [Affiliation(row_id=str(r.get("ID") or ""),
                        person_id=str(r.get("PersonID") or ""),
                        party_id=str(r.get("PartyID") or ""),
                        valid_from=day(r.get("ValidFromDate")),
                        valid_until=day(r.get("ValidUntilDate")))
            for r in (payload or []) if r.get("ID")]


def parse_parties(payload):
    """{party_id: name}. 'Scottish National Party' etc."""
    return {str(r.get("ID")): clean(r.get("ActualName") or r.get("Name")
                                    or r.get("PreferredName"))
            for r in (payload or []) if r.get("ID")}


def fetch_questions(client, year, timeout=120):
    return parse_questions(client.get_json(
        QUESTIONS_URL.format(year), "holyrood",
        "questions-{0}".format(year), timeout=timeout, archive=False))


def fetch_motions(client, since, timeout=180):
    return parse_motions(client.get_json(
        MOTIONS_URL, "holyrood", "motions", timeout=timeout, archive=False),
        since=since)


def fetch_members(client, timeout=60):
    return parse_members(client.get_json(
        MEMBERS_URL, "holyrood", "members", timeout=timeout))


def fetch_affiliations(client, timeout=60):
    return parse_affiliations(client.get_json(
        MEMBER_PARTIES_URL, "holyrood", "memberparties", timeout=timeout))


def fetch_parties(client, timeout=60):
    return parse_parties(client.get_json(
        PARTIES_URL, "holyrood", "parties", timeout=timeout))
