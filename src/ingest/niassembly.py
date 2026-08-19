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
# One plenary item's FULL TEXT. The motion list gives a three-to-six-word title
# ("Rural Transport Needs") and no body, which is why 0 of 33 motions classified
# for as long as the feed existed; this gives the operative wording, which is
# several hundred characters of exactly the language the taxonomy is built for.
PLENARY_DETAILS = BASE + "/plenary.asmx/GetPlenaryDetails_JSON?documentid={doc}"
# A committee meeting's AGENDA, keyed on the diary's own event id. XML ONLY:
# this operation has no _JSON sibling and asking for one returns 500 "Web
# Service method name is not valid" -- the three GetCommitteeAgendaItems*
# operations are the only ones on plenary.asmx without JSON variants.
#
# This is what the business diary is not. The diary gives a committee NAME and
# a room, so an OURS mark on it means the committee is ours, never the agenda;
# this gives the subjects actually being taken.
COMMITTEE_AGENDA = (BASE + "/plenary.asmx/"
                    "GetCommitteeAgendaItemsCommitteeMeetingId?eventId={event}")
# Who tabled a plenary item, with PersonIds and -- the part that matters -- a
# TablerSequence. Sequence 1 is the PROPOSER and the rest are co-signatories,
# which is the same distinction Westminster draws between sponsoring an EDM
# (weight 3) and signing one (weight 2).
#
# The motion list's own MotionTablers string cannot do this job twice over: it
# carries no PersonId, so it cannot be joined to the roster, and its order
# after the first name is NOT the tabling sequence -- measured on motion
# 448545, the string reads Armstrong/Donnelly/McReynolds/McMurray where the
# real sequence is Armstrong/McMurray/McReynolds/Donnelly.
PLENARY_TABLERS = (BASE + "/plenary.asmx/"
                   "GetPlenaryTablers_JSON?documentId={doc}")
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
# The forward Order Paper: plenary items BY SITTING DATE, and the range may
# run into the future. This is what the business diary is not -- the diary
# names committees and rooms, this names the BUSINESS ("Consideration Stage:
# Justice Bill", "Petition of Concern: ..."). Measured 2026-08-18: one sitting
# week carries ~31 titled items; during recess only Written Ministerial
# Statements are tabled ahead, with motions arriving nearer the day
# (TabledDate shows roughly a four-week horizon).
PLENARY_FORWARD = (BASE + "/plenary.asmx/GetPlenaryItemsPlenaryDate_JSON"
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
# How far back fetch_members steps when the current-members endpoint is empty.
# A week: the by-date roster lags by at least a day and the Assembly does not
# change composition often enough for a stale-by-days roster to mislead.
MEMBER_FALLBACK_DAYS = 7

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


def rows(payload, *path):
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
    for row in rows(payload, "QuestionsList", "Question"):
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
    for row in rows(payload, "PlenaryList", "Plenary"):
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
    for row in rows(payload, "BusinessDiary", "DiaryItem"):
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


@dataclass
class Tabler:
    doc_id: str
    sequence: int               # 1 = the proposer; 2+ = co-signatories
    person_id: str              # joins to ni_members / ni_affiliations
    name: str
    title: str = ""             # 'MLA - Strangford'

    @property
    def proposer(self):
        return self.sequence == 1

    @property
    def kind(self):
        """The 5CA evidence kind. Mirrors the Westminster split: sponsoring is
        a stronger act than adding your name to somebody else's text."""
        return "motion" if self.proposer else "motion-signed"

    @property
    def constituency(self):
        _, _, seat = (self.title or "").partition("-")
        return seat.strip()


def parse_tablers(payload):
    """Tablers of one item, proposer first."""
    out = []
    for row in rows(payload, "TablerList", "Tabler"):
        try:
            sequence = int(row.get("TablerSequence") or 0)
        except ValueError:
            sequence = 0
        out.append(Tabler(
            doc_id=str(row.get("DocumentID") or row.get("DocumentId") or ""),
            sequence=sequence,
            person_id=str(row.get("TablerPersonID")
                          or row.get("TablerPersonId") or ""),
            name=(row.get("TablerName") or "").strip(),
            title=(row.get("TablerTitle") or "").strip()))
    out.sort(key=lambda t: t.sequence)
    return out


def fetch_tablers(client, doc_id, timeout=45):
    """One item's tablers. Returns (tablers, error_or_None) -- looped call."""
    try:
        payload = client.get_json(PLENARY_TABLERS.format(doc=doc_id),
                                  "niassembly", "tablers-{0}".format(doc_id),
                                  timeout=timeout)
    except Exception as exc:                      # noqa: BLE001 - reported up
        return [], "{0}: {1}".format(type(exc).__name__, exc)
    return parse_tablers(payload), None


@dataclass
class AgendaItem:
    event_id: str
    item_id: str                # identifies the SUBJECT, repeats across slots
    order: int                  # the slot within the meeting; unique per event
    committee: str
    business: str
    item_type: str              # 'Committee Business' | 'Published EU Act...' | ...
    session: str                # 'Public, 10:00 AM - 10:05 AM'
    when: datetime.date = None
    areas: list = field(default_factory=list)
    matched_terms: list = field(default_factory=list)

    @property
    def id(self):
        # Keyed on ORDER, not item_id. One subject occupies several slots -- the
        # 20 August meeting ran three EU regulations in public and then the same
        # three in closed session, so ItemId repeated and nine slots would have
        # collapsed to four, losing the public/closed distinction with them.
        return "ni-agenda:{0}:{1}".format(self.event_id, self.order)

    @property
    def closed(self):
        """A closed session cannot be observed, which changes what a campaign
        can do about it -- worth surfacing rather than flattening away."""
        return "closed" in (self.session or "").lower()


def parse_agenda_items(xml_text):
    """Agenda items from the XML payload, in meeting order.

    Parsed with ElementTree rather than regex: this is the only NI feed that
    is XML, and a malformed reply should fail here rather than silently yield
    half a meeting.
    """
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(xml_text or "")
    except ET.ParseError:
        return []

    def text(node, tag):
        found = node.find(tag)
        return (found.text or "").strip() if found is not None and found.text else ""

    out = []
    for node in root.findall("Committee"):
        try:
            order = int(text(node, "ItemOrder") or 0)
        except ValueError:
            order = 0
        out.append(AgendaItem(
            event_id=text(node, "EventId"),
            item_id=text(node, "ItemId"),
            order=order,
            committee=text(node, "CommitteeName"),
            business=re.sub(r"\s+", " ", text(node, "ItemOfBusiness")),
            item_type=text(node, "ItemType"),
            session=text(node, "Session"),
            when=_iso_date(text(node, "MeetingDate"))))
    out.sort(key=lambda a: a.order)
    return out


def fetch_agenda_items(client, event_id, timeout=45):
    """One meeting's agenda. Returns (items, error_or_None).

    Called once per diary event in a loop, so it returns its error. An EMPTY
    agenda is not an error: a meeting several weeks out often has none
    published yet, and the caller counts those separately.
    """
    try:
        raw = client.get_text(COMMITTEE_AGENDA.format(event=event_id),
                              "niassembly", "agenda-{0}".format(event_id),
                              timeout=timeout)
    except Exception as exc:                      # noqa: BLE001 - reported up
        return [], "{0}: {1}".format(type(exc).__name__, exc)
    return parse_agenda_items(raw), None


def parse_plenary_text(payload):
    """The operative text of one plenary item, or '' when it carries none.

    Returns the empty string rather than None so a caller storing it cannot
    accidentally write the word "None" into the body column.
    """
    found = rows(payload, "PlenaryList", "Plenary")
    if not found:
        return ""
    return re.sub(r"\s+", " ", (found[0].get("Text") or "")).strip()


def fetch_plenary_text(client, doc_id, timeout=45):
    """One item's full text. Returns (text, error_or_None).

    Called once per motion in a loop, so it returns its error: thirty-two
    motions must not be lost because one timed out.
    """
    try:
        payload = client.get_json(PLENARY_DETAILS.format(doc=doc_id),
                                  "niassembly", "pd-{0}".format(doc_id),
                                  timeout=timeout)
    except Exception as exc:                      # noqa: BLE001 - reported up
        return "", "{0}: {1}".format(type(exc).__name__, exc)
    return parse_plenary_text(payload), None


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
    found = rows(payload, "QuestionsList", "Question")
    if not found:
        return None
    row = found[0]
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
    for row in rows(payload, "AllMembersList", "Member"):
        out.append(Member(
            person_id=str(row.get("PersonId") or ""),
            name=(row.get("MemberName") or "").strip(),
            display_name=(row.get("MemberFullDisplayName") or "").strip(),
            party=(row.get("PartyName") or "").strip(),
            constituency=(row.get("ConstituencyName") or "").strip()))
    return out


def fetch_members(client, timeout=60, today=None):
    """The current roster. Returns (members, source).

    FALLS BACK because the primary operation is broken upstream. Measured
    2026-08-19: GetAllCurrentMembers_JSON answers HTTP 200 with
    {"AllMembersList": null} -- a success carrying nothing, three times in a
    row -- while GetAllMembers_JSON, GetAllConstituencies_JSON and
    GetAllMembersByGivenDate_JSON all still return data. So it is that one
    operation, not the service.

    GetAllMembersByGivenDate for TODAY is the same payload shape and the same
    ~40KB, so parse_members serves it unchanged and "the roster now" is
    recoverable. `source` is returned rather than hidden: a caller that showed
    a fallback roster as though it were the primary would be repeating the
    unmarked-fallback bug this codebase keeps designing out.
    """
    members = parse_members(client.get_json(ALL_MEMBERS, "niassembly",
                                            "members", timeout=timeout))
    if members:
        return members, "current"
    # STEP BACK from today, because the by-date roster LAGS: measured
    # 2026-08-19, that date returned 0 members while the 18th, 17th, 15th and
    # 12th all returned 90. Asking only for today would have left the weekly
    # run -- which fires at 06:00 on a Saturday -- with an empty roster from
    # both endpoints and no roster refresh at all, silently.
    start = today or datetime.date.today()
    problems = []
    for back in range(MEMBER_FALLBACK_DAYS + 1):
        day = start - datetime.timedelta(days=back)
        members, err = fetch_members_at(client, day, timeout=timeout)
        if err:
            problems.append("{0}: {1}".format(day.isoformat(), err))
            continue
        # fetch_members_at returns ([], None) for an empty-but-errorless reply,
        # so an empty day must not read as a successful fallback carrying
        # nobody -- the same empty-is-not-success trap one level down.
        if members:
            return members, "by-date fallback ({0})".format(day.isoformat())
    detail = "; ".join(problems) if problems else "all empty"
    return [], "current-empty and no by-date roster in {0} days ({1})".format(
        MEMBER_FALLBACK_DAYS, detail)


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
class PlenaryItem:
    doc_id: str
    title: str
    kind: str                   # 'Motion' | 'Petition of Concern' | ...
    when: datetime.date         # the SITTING date, not the tabled date
    tabled: datetime.date = None
    areas: list = field(default_factory=list)
    matched_terms: list = field(default_factory=list)

    @property
    def id(self):
        return "ni-plenary:{0}".format(self.doc_id)

    @property
    def petition_of_concern(self):
        """Flagged because it changes the arithmetic: a petition of concern
        turns the affected vote cross-community, so a simple majority stops
        being enough. Worth seeing coming."""
        return "petition of concern" in (self.kind or "").lower()


def parse_plenary_items(payload, since=None):
    """Order Paper items, soonest first."""
    out = []
    for row in rows(payload, "PlenaryList", "Plenary"):
        when = _iso_date(row.get("PlenaryDate"))
        if since and when and when < since:
            continue
        out.append(PlenaryItem(
            doc_id=str(row.get("DocumentID") or row.get("DocumentId") or ""),
            title=(row.get("Title") or "").strip(),
            kind=(row.get("PlenaryType") or "").strip(),
            when=when,
            tabled=_iso_date(row.get("TabledDate"))))
    out.sort(key=lambda p: p.when or datetime.date.max)
    return out


def fetch_plenary_forward(client, start, end, timeout=60):
    """The Order Paper for a date range. Called once per run, so it raises
    (the looped fetches return errors); the caller wraps it as a gap."""
    url = PLENARY_FORWARD.format(start=start.isoformat(), end=end.isoformat())
    return parse_plenary_items(client.get_json(
        url, "niassembly", "plenary-fwd-{0}".format(start.isoformat()),
        timeout=timeout))


def canonical_bill(bill, watched_names):
    """The watch-list spelling of `bill`, or None when it is not watched.

    Returning the watch-list NAME is what makes grouping work: the 100-char cap
    truncates each amendment at a different point, so one Act otherwise sits in
    three groups. The human-authored name is the one complete spelling.

    LONGEST match wins, ties broken by sort. The first version returned the
    first match in YAML file order, which meant two watch entries that both
    prefix-match one stored bill gave an answer that depended on how the file
    happened to be arranged. The longest name is also the most specific.
    """
    hits = [name for name in (watched_names or []) if bill_matches(bill, name)]
    if not hits:
        return None
    return sorted(hits, key=lambda n: (-len(n), n))[0]


def is_watched(bill, watched_names):
    return canonical_bill(bill, watched_names) is not None


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
    for row in rows(payload, "DivisionList", "Division"):
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
    for row in rows(payload, "MemberVoting", "Member"):
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
