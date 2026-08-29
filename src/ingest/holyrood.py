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
import re
from dataclasses import dataclass

API = "https://data.parliament.scot/api"

QUESTIONS_URL = API + "/Motionsquestionsanswersquestions?year={0}"
MOTIONS_URL = API + "/Motionsquestionsanswersmotions"
MEMBERS_URL = API + "/members"
MEMBER_PARTIES_URL = API + "/memberparties"
PARTIES_URL = API + "/parties"
# Singular lowercase. The portal's own API list advertises "Votesmotions",
# which 404s for every year -- probed 2026-08-20.
VOTES_URL = API + "/votesmotion?year={0}"
OR_URL = API + "/orsplenarymeeting?year={0}"
# Works for 2025 and 2026 even though the apilist stops advertising it at
# 2024 -- probed 2026-08-22 (42MB for 2026). Same row shape as the plenary
# OR plus a Committee block.
COMMITTEE_OR_URL = API + "/Orscommitteemeeting?year={0}"
SUPPORTS_URL = API + "/Motionsquestionsanswerssupports/{0}"
# The register. The endpoint returns all 169 committees the Parliament has
# ever had, across sessions; a row with no ValidUntilDate is still sitting,
# which after the May 2026 election is 16 of them. Scotland harvested 6,965
# committee contributions while holding no list of its committees at all.
COMMITTEES_URL = API + "/Committees"

BILLS_URL = API + "/bills"
BILL_STAGES_URL = API + "/BillStages"
BILL_STAGE_TYPES_URL = API + "/BillStageTypes"


def parse_committees(payload, current_only=True):
    """[(id, name, short_name, valid_from, valid_until)] from /Committees.

    `current_only` keeps the rows with no ValidUntilDate. Everything else is
    a committee of a previous session -- real history, but a register that
    lists 169 committees when 16 are sitting answers the wrong question.
    """
    rows = payload if isinstance(payload, list) else [payload or {}]
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("ID") or "").strip()
        name = clean(row.get("Name"))
        if not cid or not name:
            continue
        until = (row.get("ValidUntilDate") or "").strip()[:10] or None
        if current_only and until:
            continue
        out.append((cid, name, clean(row.get("ShortName")) or None,
                    (row.get("ValidFromDate") or "").strip()[:10] or None,
                    until))
    return out


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


@dataclass
class Vote:
    person_id: str
    person_name: str
    party: str              # stamped on the vote row by the API itself
    constituency: str = None  # Person.ConstituencyRegion, also on the row
    party_abbrev: str = None
    vote: str = None        # Yes | No | Abstain | Not Voted
    shares_party: str = None  # the API's own whip-agreement flag


@dataclass
class Division:
    key: str                # MotionAgendaItemID -- unique per division
    reference: str          # 'S7M-00469.5': base motion + amendment suffix
    title: str
    date: str
    session: str
    vote_for: int
    vote_against: int
    result: str             # Carried | Defeated ...
    votes: list             # [Vote]


def parse_votes(payload):
    """Group per-MSP rows into divisions, keyed on MotionAgendaItemID.

    2026 measured: 19,473 rows -> 151 divisions of 128-129 voters each --
    every MSP appears, with 'Not Voted' and 'Abstain' as first-class values,
    so absence is data rather than a missing row.
    """
    divs = {}
    for r in payload or []:
        d = r.get("Detail") or {}
        m = r.get("Motion") or {}
        p = r.get("Person") or {}
        t = r.get("Time") or {}
        # TWO Detail schemas coexist in one dump: most rows carry
        # MotionAgendaItemID, but 1,419 of 19,473 in 2026 (11 whole divisions)
        # carry BackupAgendaItemID instead. Keying on the first alone silently
        # dropped those 11 -- caught only because the division count was
        # checked against an independent (reference, time) grouping. The
        # prefix keeps the two ID spaces from colliding.
        d_key = d.get("MotionAgendaItemID")
        b_key = d.get("BackupAgendaItemID")
        key = ("m{0}".format(d_key) if d_key else
               "b{0}".format(b_key) if b_key else "")
        if not key:
            continue
        div = divs.get(key)
        if div is None:
            div = divs[key] = Division(
                key=key,
                reference=clean(m.get("Reference")) or None,
                title=clean(m.get("Title"))[:300],
                date=day(t.get("Start")),
                session=clean(t.get("Session")) or None,
                vote_for=d.get("VoteFor"),
                vote_against=d.get("VoteAgainst"),
                result=clean(d.get("VoteResult")) or None,
                votes=[])
        div.votes.append(Vote(
            person_id=str(p.get("ID") or ""),
            person_name=clean(p.get("ParliamentaryName")),
            party=clean(p.get("PartyName")) or None,
            constituency=clean(p.get("ConstituencyRegion")) or None,
            party_abbrev=clean(p.get("PartyAbbreviation")) or None,
            vote=clean(d.get("VoteMSP")) or None,
            shares_party=clean(d.get("MSPSharesParty")) or None))
    return sorted(divs.values(), key=lambda x: (x.date or "", x.key))


# Bill AMENDMENT divisions are the second class of Holyrood vote, and they are
# NOT in votesmotion: that endpoint carries motion decisions only. In 2026 the
# Official Report held 672 division results, of which 530 were bill amendments
# -- including all 215 of the Assisted Dying Bill's Stage 3 amendment battle.
# The OR prints AGGREGATE results only ("For 47, Against 67, Abstentions 0");
# no per-member roll exists anywhere in the open data, so these divisions can
# never place anyone in a 5CA -- they are record and context.
_OR_RESULT = re.compile(
    r"result of the division(?: on)?[^:]*is:\s*"
    r"For\s*(\d+),\s*Against\s*(\d+),\s*Abstentions\s*(\d+)", re.I)
_OR_AMENDMENT = re.compile(r"Amendment\s+(\d+[A-Z]?)\s+(agreed|disagreed)\s+to", re.I)
_OR_MOTION = re.compile(r"\b(S\d+M-\d+(?:\.\d+)?)")


@dataclass
class ORDivision:
    key: str                 # 'or<contribution ID>'
    dated: str
    heading: str             # ItemOfBusiness heading, e.g. '... Bill: Stage 3'
    vote_for: int
    vote_against: int
    abstentions: int
    amendment_no: str        # '266' / '56A'; None when not an amendment
    outcome: str             # agreed | disagreed | None
    motion_ref: str          # set when the result cites a motion: those rows
                             # duplicate votesmotion and the caller skips them


def parse_or_divisions(payload):
    """Division results from a year of the plenary Official Report.

    Measured on 2026 before writing: exactly ONE result per contribution row
    (672 by finditer == 672 by search), and the amendment outcome sits in the
    same row's text, so no cross-row stitching is needed.
    """
    out = []
    for r in payload or []:
        detail = r.get("Detail") or {}
        text = detail.get("EditedText") or ""
        m = _OR_RESULT.search(text)
        if not m:
            continue
        amd = _OR_AMENDMENT.search(text)
        ref = _OR_MOTION.search(text)
        cid = detail.get("ContributionID") or r.get("ID")
        out.append(ORDivision(
            key="or{0}".format(cid),
            dated=day((r.get("Time") or {}).get("Start")),
            heading=clean((r.get("ItemOfBusiness") or {}).get("Heading")),
            vote_for=int(m.group(1)), vote_against=int(m.group(2)),
            abstentions=int(m.group(3)),
            amendment_no=amd.group(1) if amd else None,
            outcome=(amd.group(2).lower() if amd else None),
            motion_ref=ref.group(1) if ref else None))
    return out


@dataclass
class Speech:
    key: str            # 'orc<ContributionID>'
    person_id: str
    dated: str
    heading: str
    text: str


def parse_or_speeches(payload):
    """Spoken contributions with a known speaker, for taxonomy classification.

    Same payload as parse_or_divisions -- the caller fetches the 65MB year
    dump ONCE and feeds both parsers. All 193 distinct 2026 speakers join
    sp_members by Person.ID; median contribution is 393 chars and the
    taxonomy match rate is under 1%, so the resulting ledger is small.
    """
    out = []
    for r in payload or []:
        p = r.get("Person") or {}
        text = (r.get("Detail") or {}).get("EditedText") or ""
        if not p.get("ID") or not text:
            continue
        out.append(Speech(
            key="orc{0}".format((r.get("Detail") or {}).get("ContributionID")
                                or r.get("ID")),
            person_id=str(p.get("ID")),
            dated=day((r.get("Time") or {}).get("Start")),
            heading=clean((r.get("ItemOfBusiness") or {}).get("Heading")),
            text=text))
    return out


@dataclass
class CommitteeSpeech:
    key: str            # 'occ<ContributionID>' -- distinct from plenary 'orc'
    person_id: str
    dated: str
    committee: str      # 'Education, Children and Young People Committee'
    heading: str        # the item of business, NOT the committee name
    text: str


def parse_committee_speeches(payload):
    """MSP contributions in committee, for taxonomy classification.

    Witnesses and officials carry a null Person block (their names live only
    in Detail.SpeakerDisplayName) and are skipped: the ledger records MSP
    activity. The committee name is returned SEPARATELY from the item
    heading so classification never runs on the committee's own name --
    'Equalities, Human Rights and Civil Justice Committee' must not area-tag
    every word said in that room (the NI 'Committee for Finance' lesson,
    inverted).
    """
    out = []
    for r in payload or []:
        if not isinstance(r, dict):
            continue    # the API intermittently interleaves error strings
        p = r.get("Person") or {}
        text = (r.get("Detail") or {}).get("EditedText") or ""
        if not p.get("ID") or not text:
            continue
        out.append(CommitteeSpeech(
            key="occ{0}".format((r.get("Detail") or {}).get("ContributionID")
                                or r.get("ID")),
            person_id=str(p.get("ID")),
            dated=day((r.get("Time") or {}).get("Start")),
            committee=clean((r.get("Committee") or {}).get("Name")),
            heading=clean((r.get("ItemOfBusiness") or {}).get("Heading")),
            text=text))
    return out


def fetch_committee_or(client, year, timeout=240):
    """The committee OR year dump (42MB for 2026) -- the db is the archive."""
    return client.get_json(COMMITTEE_OR_URL.format(year), "holyrood",
                           "committee-or-{0}".format(year), timeout=timeout,
                           archive=False)


@dataclass
class Bill:
    bill_id: str
    reference: str      # 'SP Bill 1'
    name: str           # FullName -- the classification text
    person_id: str
    latest_stage: str = None
    latest_stage_date: str = None


def parse_bills(payload, stages=None, stage_types=None):
    """All 473+ bills with each one's LATEST stage joined on.

    /api/bills carries identity only (no status -- the scotland.py finding);
    /api/BillStages carries (BillID, BillStageTypeID, StageDate). Joining the
    newest stage per bill gives machine-readable progress where scotland.py
    had to scrape the public bill page for a status sentence.
    """
    names = stage_types or {}
    latest = {}
    for st in stages or []:
        bid = str(st.get("BillID") or "")
        d = day(st.get("StageDate"))
        if bid and (bid not in latest or (d or "") > (latest[bid][1] or "")):
            latest[bid] = (str(st.get("BillStageTypeID") or ""), d)
    out = []
    for r in payload or []:
        bid = str(r.get("ID") or "")
        if not bid:
            continue
        stage_id, stage_date = latest.get(bid, (None, None))
        out.append(Bill(
            bill_id=bid,
            reference=clean(r.get("Reference")) or None,
            name=clean(r.get("FullName") or r.get("ShortName")),
            person_id=str(r.get("PersonID") or "") or None,
            latest_stage=names.get(stage_id, stage_id),
            latest_stage_date=stage_date))
    return out


def parse_stage_types(payload):
    return {str(r.get("ID")): clean(r.get("Name") or r.get("Description"))
            for r in (payload or []) if r.get("ID")}


def fetch_supports(client, uid, timeout=45):
    """Co-signatories for ONE motion, by its UniqueID.

    The full-dump endpoint 503s after ~46s (probed twice, 2026-08-20 and -21):
    the server cannot build it. The per-id form answers in under a second, so
    supports are fetched per matched motion -- bounded at our tier-1 motions,
    never the whole dataset. Returns [(person_id, lodged_date)].
    """
    payload = client.get_json(SUPPORTS_URL.format(uid), "holyrood",
                              "supports-{0}".format(uid), timeout=timeout,
                              archive=False)
    return [(str(r.get("MSPID") or ""), day(r.get("SupporterDateOfLodging")))
            for r in (payload or []) if r.get("MSPID")]


def fetch_bills(client, timeout=90):
    stages = client.get_json(BILL_STAGES_URL, "holyrood", "billstages",
                             timeout=timeout)
    try:
        types = parse_stage_types(client.get_json(
            BILL_STAGE_TYPES_URL, "holyrood", "billstagetypes",
            timeout=timeout))
    except Exception:                                   # noqa: BLE001
        types = {}
    return parse_bills(client.get_json(BILLS_URL, "holyrood", "bills-all",
                                       timeout=timeout), stages, types)


def fetch_or_payload(client, year, timeout=240):
    """One 65MB fetch serving both OR parsers (divisions and speeches)."""
    return client.get_json(OR_URL.format(year), "holyrood",
                           "or-{0}".format(year), timeout=timeout,
                           archive=False)


def fetch_or_divisions(client, year, timeout=240):
    return parse_or_divisions(fetch_or_payload(client, year, timeout=timeout))


def base_reference(reference):
    """'S7M-00469.5' -> 'S7M-00469'; the base motion a division belongs to."""
    return (reference or "").split(".")[0]


def fetch_votes(client, year, timeout=180):
    return parse_votes(client.get_json(
        VOTES_URL.format(year), "holyrood", "votes-{0}".format(year),
        timeout=timeout, archive=False))


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
