"""Northern Ireland Assembly ingester.

NI matters to us out of proportion to its size: abortion law was imposed on it
from Westminster in 2019 and the Assembly has never accepted that settlement,
so the live arguments here are ones Westminster considers closed. The handoff
listed `aims.niassembly.gov.uk` as "research needed"; that host is not the
answer. The open data service is `data.niassembly.gov.uk`, a set of .asmx
endpoints each offering XML, JSON and JSONP variants. The _JSON suffix is what
we use, and none of it needs a key.

THREE SOURCES, DIFFERENT JOBS:

  * questions.asmx/GetQuestionsBySearchText_JSON?searchText=  -- the direct
    analogue of the Westminster PQ sweep, so it runs off the same
    `pq_sweep_terms`. Requires 3+ characters.
  * plenary.asmx/GetNoDayNamedMotions_JSON  -- motions tabled but not yet
    scheduled. The nearest thing NI has to an EDM, and unlike Westminster EDMs
    it names its tablers WITH party in a single field.
  * plenary.asmx/GetBusinessDiary_JSON?startDate=&endDate=  -- the forward
    calendar of sittings and committee meetings.

THE TRAP THAT SHAPES THIS MODULE. The search endpoint has no date parameter
and no paging: "abortion" returns all 242 questions back to 2008 in one 110KB
response. So the window is applied HERE, after the fetch, and the full history
is a feature rather than waste -- it is the only cheap way to ask what the
Assembly has said about an issue over eighteen years. Callers that want the
week pass `since`; callers building a back-history pass nothing.

WHAT THIS DELIBERATELY DOES NOT DO. Search results carry no member name --
only DocumentId, Reference, TabledDate and QuestionText -- so attributing a
question to an MLA costs one GetQuestionDetails call each. That is not built:
the 5CA scores Westminster members, and inventing a partial MLA ledger would
be worse than having none. Divisions (GetDivisionMemberVoting_JSON) are the
high-value 5CA-equivalent evidence and are likewise NOT built yet; they are
reported as untracked rather than half-done.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field

BASE = "http://data.niassembly.gov.uk"
QUESTIONS_SEARCH = BASE + "/questions.asmx/GetQuestionsBySearchText_JSON?searchText={term}"
QUESTION_DETAIL = BASE + "/questions.asmx/GetQuestionDetails_JSON?documentId={doc}"
MOTIONS_NDN = BASE + "/plenary.asmx/GetNoDayNamedMotions_JSON"
BUSINESS_DIARY = (BASE + "/plenary.asmx/GetBusinessDiary_JSON"
                  "?startDate={start}&endDate={end}")
ALL_MEMBERS = BASE + "/members.asmx/GetAllCurrentMembers_JSON"
# The roster AS AT a date. Same payload shape as GetAllCurrentMembers, so
# parse_members serves both. This is what makes party-at-the-time answerable:
# Doug Beattie reads "Ulster Unionist Party" on 2025-09-19 and "Independent"
# on the current roster, and only the first is true of a 2025 question.
MEMBERS_AT = BASE + "/members.asmx/GetAllMembersByGivenDate_JSON?specificDate={date}"
DIVISIONS = (BASE + "/plenary.asmx/GetVotesOnDivision_JSON"
             "?startDate={start}&endDate={end}")
MEMBER_VOTING = BASE + "/plenary.asmx/GetDivisionMemberVoting_JSON?documentId={doc}"

# A question's public page. The API's own QuestionDetails link returns raw XML,
# which is no use to a human reading the monitor.
QUESTION_PAGE = ("http://aims.niassembly.gov.uk/questions/"
                 "printquestionsummary.aspx?docid={doc}")

MIN_SEARCH = 3          # the endpoint rejects shorter terms
# Bill-name matching thresholds. A 12-character stem is enough for a clean
# prefix ("Justice Bill"); 50 identical leading characters is the bar for
# calling two DIVERGING names the same bill. See bill_matches.
MIN_BILL_STEM = 12
MIN_BILL_COMMON = 50

# Party appears parenthesised after each name: "Ms Kellie Armstrong (APNI)".
_TABLER = re.compile(r"([^/(]+?)\s*\(([A-Z][A-Za-z]*)\)")


def _iso_date(value):
    """The date half of an API timestamp, which carries a BST/GMT offset.

    Only the date is kept. The offset flips mid-year and comparing full
    timestamps across it invites the same class of bug the Sunday cron guard
    exists to avoid.
    """
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _rows(payload, *path):
    """Dig out a list from the API's nested single-key envelopes.

    Every endpoint wraps its rows twice ({"QuestionsList": {"Question": [...]}})
    and COLLAPSES a one-row result to a bare object rather than a list of one.
    Both shapes are normalised here so no caller has to think about it.
    """
    node = payload or {}
    for key in path:
        if not isinstance(node, dict):
            return []
        node = node.get(key)
    if node is None:
        return []
    return node if isinstance(node, list) else [node]


@dataclass
class Question:
    doc_id: str
    reference: str              # 'AQW 4832/08'
    tabled: datetime.date
    text: str
    oral: bool = False
    areas: list = field(default_factory=list)
    matched_terms: list = field(default_factory=list)

    @property
    def url(self):
        return QUESTION_PAGE.format(doc=self.doc_id)

    @property
    def id(self):
        return "ni-question:{0}".format(self.doc_id)

    @property
    def series(self):
        """'oral' or 'written', from the REFERENCE PREFIX.

        AQO is the oral series and AQW the written one, and that designation is
        authoritative. `QOralAnswerRequested` disagreed with it on 2 of 20
        matched questions (AQO 2937 and AQO 3230, both flagged false), so the
        flag is only a fallback for a reference we cannot read.
        """
        prefix = (self.reference or "").strip()[:3].upper()
        if prefix == "AQO":
            return "oral"
        if prefix == "AQW":
            return "written"
        return "oral" if self.oral else "written"


@dataclass
class Motion:
    doc_id: str
    title: str
    category: str               # "Private Members' Motion" etc
    tabled: datetime.date
    tablers_raw: str
    areas: list = field(default_factory=list)
    matched_terms: list = field(default_factory=list)

    @property
    def id(self):
        return "ni-motion:{0}".format(self.doc_id)

    @property
    def tablers(self):
        """[(name, party)] parsed from the single slash-separated field."""
        out = []
        for name, party in _TABLER.findall(self.tablers_raw or ""):
            cleaned = name.replace("/", " ").strip()
            if cleaned:
                out.append((cleaned, party))
        return out

    @property
    def parties(self):
        seen = []
        for _name, party in self.tablers:
            if party not in seen:
                seen.append(party)
        return seen


@dataclass
class DiaryItem:
    event_id: str
    starts: datetime.date
    event_type: str             # 'Committee Meeting' | 'Plenary' | ...
    organisation: str
    room: str = ""
    areas: list = field(default_factory=list)
    matched_terms: list = field(default_factory=list)

    @property
    def id(self):
        return "ni-diary:{0}".format(self.event_id)


# -- parse ------------------------------------------------------------------

def parse_questions(payload, since=None):
    """Questions from a search response, newest first.

    `since` filters on tabled date because the endpoint cannot: see the module
    docstring. Rows whose date will not parse are KEPT and sort last -- a
    question we cannot date is still a question, and dropping it silently is
    the failure mode this codebase keeps designing against.
    """
    out = []
    for row in _rows(payload, "QuestionsList", "Question"):
        tabled = _iso_date(row.get("TabledDate"))
        if since and tabled and tabled < since:
            continue
        out.append(Question(
            doc_id=str(row.get("DocumentId") or ""),
            reference=(row.get("Reference") or "").strip(),
            tabled=tabled,
            text=(row.get("QuestionText") or "").strip(),
            oral=str(row.get("QOralAnswerRequested") or "").lower() == "true"))
    out.sort(key=lambda q: (q.tabled is not None, q.tabled or datetime.date.min),
             reverse=True)
    return out


def parse_motions(payload, since=None):
    out = []
    for row in _rows(payload, "PlenaryList", "Plenary"):
        tabled = _iso_date(row.get("TabledDate"))
        if since and tabled and tabled < since:
            continue
        out.append(Motion(
            doc_id=str(row.get("DocumentID") or row.get("DocumentId") or ""),
            title=(row.get("Title") or "").strip(),
            category=(row.get("MotionCategory") or "").strip(),
            tabled=tabled,
            tablers_raw=(row.get("MotionTablers") or "").strip()))
    out.sort(key=lambda m: (m.tabled is not None, m.tabled or datetime.date.min),
             reverse=True)
    return out


def parse_diary(payload):
    out = []
    for row in _rows(payload, "BusinessDiary", "DiaryItem"):
        out.append(DiaryItem(
            event_id=str(row.get("EventId") or ""),
            starts=_iso_date(row.get("EventDate")),
            event_type=(row.get("EventType") or "").strip(),
            organisation=(row.get("OrganisationName") or "").strip(),
            room=(row.get("LocationRoom") or "").strip()))
    out.sort(key=lambda d: d.starts or datetime.date.max)
    return out


# -- fetch ------------------------------------------------------------------

def fetch_questions(client, term, since=None, timeout=60):
    """Search questions for one term. Returns (questions, error_or_None).

    Errors are RETURNED, not raised: a sweep of forty terms must not lose
    thirty-nine because one timed out, and the caller records the gap. Same
    contract as sweep_pqs on the Westminster side.
    """
    if len(term or "") < MIN_SEARCH:
        return [], "term shorter than {0} characters".format(MIN_SEARCH)
    url = QUESTIONS_SEARCH.format(term=_quote(term))
    try:
        payload = client.get_json(url, "niassembly", "q-" + _slug(term),
                                  timeout=timeout)
    except Exception as exc:                      # noqa: BLE001 - reported up
        return [], "{0}: {1}".format(type(exc).__name__, exc)
    return parse_questions(payload, since=since), None


def fetch_motions(client, since=None, timeout=60):
    payload = client.get_json(MOTIONS_NDN, "niassembly", "motions-ndn",
                              timeout=timeout)
    return parse_motions(payload, since=since)


def fetch_diary(client, start, end, timeout=60):
    url = BUSINESS_DIARY.format(start=start.isoformat(), end=end.isoformat())
    return parse_diary(client.get_json(
        url, "niassembly", "diary-{0}".format(start.isoformat()), timeout=timeout))


# -- attribution ------------------------------------------------------------
# GetQuestionDetails carries far more than the tabler: the minister, the
# department and the full answer text. Measured against the alternative on
# 2026-08-18: GetQuestionsByMember returns 670 questions and 399KB for ONE
# member, so covering 90 MLAs is 90 requests and ~36MB and still gives no
# answer text. Detail-per-matched-question was 20 requests at 1.3KB each.
# Classify first, enrich only the matches.

@dataclass
class QuestionDetail:
    doc_id: str
    tabler: str = ""
    tabler_person_id: str = ""
    tabler_title: str = ""       # 'MLA - North Antrim'
    minister: str = ""
    department: str = ""
    answered: datetime.date = None
    answer: str = ""

    @property
    def constituency(self):
        """The seat out of 'MLA - North Antrim'. Empty for a minister-only row."""
        _, _, seat = (self.tabler_title or "").partition("-")
        return seat.strip()


def parse_question_detail(payload):
    rows = _rows(payload, "QuestionsList", "Question")
    if not rows:
        return None
    row = rows[0]
    return QuestionDetail(
        doc_id=str(row.get("DocumentId") or ""),
        tabler=(row.get("TablerName") or "").strip(),
        tabler_person_id=str(row.get("TablerPersonId") or ""),
        tabler_title=(row.get("TablerTitle") or "").strip(),
        minister=(row.get("MinisterTitle") or "").strip(),
        department=(row.get("Department") or "").strip(),
        answered=_iso_date(row.get("AnsweredOnDate")),
        answer=(row.get("AnswerPlainText") or "").strip())


def fetch_question_detail(client, doc_id, timeout=45):
    """One question's full record. Returns (detail_or_None, error_or_None)."""
    try:
        payload = client.get_json(QUESTION_DETAIL.format(doc=doc_id),
                                  "niassembly", "qd-{0}".format(doc_id),
                                  timeout=timeout)
    except Exception as exc:                      # noqa: BLE001 - reported up
        return None, "{0}: {1}".format(type(exc).__name__, exc)
    return parse_question_detail(payload), None


@dataclass
class Member:
    person_id: str
    name: str                   # 'Aiken, Steve OBE'
    display_name: str           # 'Dr Steve Aiken OBE'
    party: str
    constituency: str

    @property
    def id(self):
        return "ni-mla:{0}".format(self.person_id)


def parse_members(payload):
    out = []
    for row in _rows(payload, "AllMembersList", "Member"):
        out.append(Member(
            person_id=str(row.get("PersonId") or ""),
            name=(row.get("MemberName") or "").strip(),
            display_name=(row.get("MemberFullDisplayName") or "").strip(),
            party=(row.get("PartyName") or "").strip(),
            constituency=(row.get("ConstituencyName") or "").strip()))
    return out


def fetch_members(client, timeout=60):
    return parse_members(client.get_json(ALL_MEMBERS, "niassembly", "members",
                                        timeout=timeout))


def fetch_members_at(client, when, timeout=60):
    """The roster as at `when`. Returns (members, error_or_None).

    Errors are returned rather than raised: resolving twenty-five dates must
    not lose twenty-four because one failed, and the caller records the gap.
    """
    day = when.isoformat() if hasattr(when, "isoformat") else str(when)
    try:
        payload = client.get_json(MEMBERS_AT.format(date=day), "niassembly",
                                  "members-at-{0}".format(day), timeout=timeout)
    except Exception as exc:                      # noqa: BLE001 - reported up
        return [], "{0}: {1}".format(type(exc).__name__, exc)
    return parse_members(payload), None


# -- divisions --------------------------------------------------------------
# A DivisionSubject names the amendment number, the stage, the bill and the
# proposer -- but never what the amendment SAYS. "Amendment 97 to the Justice
# Bill" cannot be classified, so the unit of interest is the BILL, extracted
# below and reviewed by a human. This mirrors the Westminster side, where
# find_division_candidates.py is explicitly a review queue and a division only
# becomes trackable once somebody writes down what it means.

_AMEND_PREFIX = re.compile(r"^\s*-?#?\d*\s*(?:Amendment\s*\d*\s*[-:]\s*)?", re.I)
_STAGE = re.compile(
    r"(?:Further\s+)?(?:Consideration|Second|First|Final|Reconsideration)\s+Stage\s*:\s*",
    re.I)
# Trailing furniture: "(NIA Bill 7/22-27)", "(Day 4)", "[Mr Paul Frew]",
# " - Amendment 1: Motion Amendment 1".
#
# DivisionSubject IS TRUNCATED AT 100 CHARACTERS by the API -- 49 of 139 rows
# in the 2025-26 sample sit exactly on the cap -- so the proposer's closing
# bracket is frequently missing: "... (Day 4) [Minister of Justice - D".
# An unclosed bracket run to end-of-string must therefore be stripped too, or
# every long-titled bill grows a different fake suffix per amendment and the
# grouping shatters ("Justice Bill [Minister of Justice - D" vs "Justice Bill").
# An unclosed trailing BRACKET is always furniture -- brackets only ever hold
# the proposer -- so "[Minister of Justice - D" goes.
#
# An unclosed trailing PARENTHESIS is not. Stripping any of them looked right
# and was wrong: "Inquiry (Mother and Baby Institutions, Magdalene Laundrie"
# carries an unclosed paren that is part of the NAME, and a blanket rule cut it
# to "Inquiry", silently dropping two watched divisions (37 -> 35). So only the
# bill REFERENCE is stripped when unclosed, and "(NIA Bil" can be cut mid-word,
# hence "\(NIA" rather than the full literal.
_TRAILING = re.compile(
    r"\s*(?:-\s*Amendment\s*\d+\s*:.*"
    r"|\(NIA Bill[^)]*\)|\(Day\s*\d+\)|\[[^\]]*\]"
    r"|\[[^\]]*$|\(NIA[^)]*$)\s*",
    re.I)


def bill_of(subject):
    """The bill or motion a division belongs to.

    Newlines matter: one real subject arrives as "Moving Beyond the Windsor
    Framework\\n - Amendment 1: ...", so whitespace is collapsed before any
    pattern is applied.
    """
    text = re.sub(r"\s+", " ", subject or "").strip()
    text = _AMEND_PREFIX.sub("", text)
    split = _STAGE.split(text, maxsplit=1)
    text = split[-1] if len(split) > 1 else text
    prev = None
    while prev != text:                # furniture can nest: "(Day 4) [Mr X]"
        prev = text
        text = _TRAILING.sub(" ", text).strip()
    return re.sub(r"\s+", " ", text).strip(" -–:")


def bill_matches(stored, watched):
    """Is `stored` the same bill as the watch-list name `watched`?

    PREFIX comparison, not equality. The 100-character cap cuts the bill NAME
    itself, not just the trailing furniture, so one bill arrives under several
    truncations: "Inquiry (Mother and Baby Institutions, Magdalene Laundrie"
    and "...Magdalene Laundries and W" are the same Act. Truncation only ever
    removes a suffix, so prefix matching is its exact inverse.

    Both directions are tested because the watch list may hold the full legal
    name (longer than anything stored) or a short handle ("Justice Bill").

    A clean prefix is not always enough. Truncation can land INSIDE the name
    and leave the two strings diverging rather than nesting: the stored
    "...Magdalene Laundries and W" against a watch entry ending
    "...Magdalene Laundries) Bill" share fifty characters and then part
    company. So a long common prefix also counts. Two genuinely different
    bills agreeing on their first fifty characters is not a thing that
    happens; a watch entry whose tail is slightly wrong very much is.
    """
    a = re.sub(r"\s+", " ", (stored or "")).strip().lower()
    b = re.sub(r"\s+", " ", (watched or "")).strip().lower()
    if not a or not b:
        return False
    shorter, longer = sorted((a, b), key=len)
    # A handful of characters would match far too much: "The" would claim
    # every motion beginning "The". Require a substantial stem.
    if len(shorter) >= MIN_BILL_STEM and longer.startswith(shorter):
        return True
    common = 0
    for x, y in zip(a, b):
        if x != y:
            break
        common += 1
    return common >= MIN_BILL_COMMON


@dataclass
class Division:
    doc_id: str
    event_id: str
    subject: str
    when: datetime.date
    kind: str                   # 'Simple Majority' | 'Cross-Community'
    areas: list = field(default_factory=list)
    matched_terms: list = field(default_factory=list)

    @property
    def id(self):
        return "ni-division:{0}".format(self.doc_id)

    @property
    def bill(self):
        return bill_of(self.subject)

    @property
    def cross_community(self):
        """Cross-community votes need majorities in BOTH designations, so a
        simple tally misreads them. Flagged rather than silently counted."""
        return "cross" in (self.kind or "").lower()


def parse_divisions(payload, since=None):
    out = []
    for row in _rows(payload, "DivisionList", "Division"):
        when = _iso_date(row.get("DivisionDate"))
        if since and when and when < since:
            continue
        out.append(Division(
            doc_id=str(row.get("DocumentID") or ""),
            event_id=str(row.get("EventID") or ""),
            subject=re.sub(r"\s+", " ", row.get("DivisionSubject") or "").strip(),
            when=when,
            # Their own field is misspelled "DivisonType". Read both so a
            # later fix upstream does not silently blank the column.
            kind=(row.get("DivisonType") or row.get("DivisionType") or "").strip()))
    out.sort(key=lambda d: (d.when is not None, d.when or datetime.date.min),
             reverse=True)
    return out


def fetch_divisions(client, start, end, since=None, timeout=90):
    url = DIVISIONS.format(start=start.isoformat(), end=end.isoformat())
    return parse_divisions(client.get_json(
        url, "niassembly", "divisions-{0}".format(start.isoformat()),
        timeout=timeout), since=since)


@dataclass
class MemberVote:
    doc_id: str
    person_id: str
    member: str
    vote: str                   # aye | no | abstain | other
    designation: str            # Unionist | Nationalist | Other -- NI-specific


_VOTE_MAP = {"aye": "aye", "yes": "aye", "no": "no", "nay": "no",
             "abstain": "abstain", "abstained": "abstain"}


def parse_member_voting(payload):
    """Per-MLA positions on one division.

    An unrecognised Vote string is kept verbatim rather than coerced to a
    known value: guessing here would put words in a member's mouth, which is
    the one thing the ledger must never do.
    """
    out = []
    for row in _rows(payload, "MemberVoting", "Member"):
        raw = (row.get("Vote") or "").strip()
        out.append(MemberVote(
            doc_id=str(row.get("DocumentID") or ""),
            person_id=str(row.get("PersonID") or ""),
            member=(row.get("MemberName") or "").strip(),
            vote=_VOTE_MAP.get(raw.lower(), raw.lower()),
            designation=(row.get("Designation") or "").strip()))
    return out


def fetch_member_voting(client, doc_id, timeout=60):
    """Returns (votes, error_or_None). Errors reported, never raised."""
    try:
        payload = client.get_json(MEMBER_VOTING.format(doc=doc_id),
                                  "niassembly", "mv-{0}".format(doc_id),
                                  timeout=timeout)
    except Exception as exc:                      # noqa: BLE001
        return [], "{0}: {1}".format(type(exc).__name__, exc)
    return parse_member_voting(payload), None


def _quote(term):
    from urllib.parse import quote
    return quote(term, safe="")


def _slug(term):
    return re.sub(r"[^a-z0-9]+", "-", (term or "").lower()).strip("-") or "term"
