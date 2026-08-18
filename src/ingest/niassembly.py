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
MOTIONS_NDN = BASE + "/plenary.asmx/GetNoDayNamedMotions_JSON"
BUSINESS_DIARY = (BASE + "/plenary.asmx/GetBusinessDiary_JSON"
                  "?startDate={start}&endDate={end}")

# A question's public page. The API's own QuestionDetails link returns raw XML,
# which is no use to a human reading the monitor.
QUESTION_PAGE = ("http://aims.niassembly.gov.uk/questions/"
                 "printquestionsummary.aspx?docid={doc}")

MIN_SEARCH = 3          # the endpoint rejects shorter terms

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


def _quote(term):
    from urllib.parse import quote
    return quote(term, safe="")


def _slug(term):
    return re.sub(r"[^a-z0-9]+", "-", (term or "").lower()).strip("-") or "term"
