"""Senedd (Welsh Parliament) watching-brief ingester -- phase 1: questions.

What probing established (2026-08-21, full table in docs/api-notes.md):

  * There is NO usable data API. data-style endpoints do not exist; the
    ModernGov XML exports serve HTML shells; the Record's /Search?q= IGNORES
    its query server-side (three different terms returned byte-identical
    pages). What works is the Record's per-id pages:
    record.senedd.wales/WrittenQuestion/<id>.
  * IDs are DENSE sequential integers (~93000 = May 2024, ~100230 = Aug
    2026, ~60/week), so discovery is ID-WALKING: no search, no sweep terms,
    the taxonomy classifies every question -- Holyrood's property by a
    different route. A nonexistent id serves the site shell WITHOUT a
    "Tabled on" line: that absence is the miss signature.
  * record.senedd.wales accepts the project's honest CitizenGO User-Agent.
    business.senedd.wales (ModernGov) rejects it with a WAF 403 and answers
    only to browser UAs -- so PARTY IS NOT HELD in phase 1: question pages
    carry member name and constituency but not party, and the enrichment
    source would require pretending to be a browser, which is a decision,
    not a default. Recorded, not worked around.
  * Answered pages carry "Answered by <minister> | Answered on <date>" and
    the full answer text inline. A "(w)" marker beside the reference means
    tabled in Welsh; the page still carries English text.
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import re
import json as _json
from urllib.parse import urlencode as _urlencode
from dataclasses import dataclass

QUESTION_URL = "https://record.senedd.wales/WrittenQuestion/{0}"

# The vote route, found via mySociety's parlparse scraper (pyscraper/wa): an
# undocumented XML export. The index lists sittings per PARLIAMENT (the
# `committee` parameter takes a parliament id: 700 = Sixth Senedd,
# 908 = Seventh); each sitting links transcript XMLs and, where divisions
# happened, a Votes XML whose <XML_Plenary_Vote> blocks are PER-MEMBER rows:
# division titles in both languages, totals, result, and each MS's individual
# For/Against/Abstain. Holyrood-grade data behind an unadvertised door --
# and record.senedd.wales accepts our honest User-Agent here too.
XML_INDEX_URL = ("https://record.senedd.wales/XMLExport/?committee={0}&page={1}")
VOTES_URL = ("https://record.senedd.wales/XMLExport/Download?meetingID={0}"
             "&xmlDownloadType=Votes")
TRANSCRIPT_URL = ("https://record.senedd.wales/XMLExport/Download?meetingID={0}"
                  "&xmlDownloadType=EnglishTranscript")
SIXTH_SENEDD = 700
SEVENTH_SENEDD = 908

_TABLED = re.compile(r"Tabled on (\d\d)/(\d\d)/(\d\d\d\d)")
_ANSWERED = re.compile(
    r"Answered by (.+?) \| Answered on (\d\d)/(\d\d)/(\d\d\d\d)")
_TO_BE = re.compile(r"To be answered by:\s*(.+)")


def _lines(page):
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    text = re.sub(r"<[^>]+>", "\n", body)
    return [_html.unescape(l.strip()) for l in text.split("\n") if l.strip()]


def _iso(d, m, y):
    return "{0}-{1}-{2}".format(y, m, d)


@dataclass
class Question:
    wq_id: int
    reference: str          # 'WQ100032'
    member_name: str
    constituency: str
    dated: str              # tabled
    welsh: bool             # tabled in Welsh ('(w)' marker)
    body: str
    answered_by: str        # minister title (answered or to-be)
    answered: str           # answer date, None while pending
    answer: str             # answer text, None while pending


def parse_question(page, wq_id):
    """Question from one page, or None on the miss signature.

    The page layout is positional: name / constituency / WQnnnnn / (e|w) /
    Tabled on ... / question text / answer block. Anchoring on the WQ
    reference and the Tabled line keeps the parse independent of the site
    chrome above and below.
    """
    if "Tabled on" not in page:
        return None
    lines = _lines(page)
    ref = "WQ{0}".format(wq_id)
    try:
        i = next(k for k, l in enumerate(lines) if l == ref)
    except StopIteration:
        return None
    name = lines[i - 2] if i >= 2 else ""
    seat = lines[i - 1] if i >= 1 else ""
    welsh = (i + 1 < len(lines) and lines[i + 1].strip("()") == "w")
    t = next((k for k in range(i, min(i + 6, len(lines)))
              if _TABLED.search(lines[k])), None)
    if t is None:
        return None
    dated = _iso(*reversed(_TABLED.search(lines[t]).groups()))
    dated = "{0}-{1}-{2}".format(*_TABLED.search(lines[t]).groups()[::-1])
    # Question text: lines after Tabled until the answer/to-be marker.
    q_parts, answered_by, answered, answer_parts = [], None, None, []
    mode = "question"
    for l in lines[t + 1:]:
        if l.startswith("Contact us"):
            break
        m = _ANSWERED.search(l)
        if m:
            answered_by = m.group(1).strip()
            answered = "{0}-{1}-{2}".format(m.group(4), m.group(3), m.group(2))
            mode = "answer"
            continue
        m = _TO_BE.search(l)
        if m:
            answered_by = m.group(1).strip()
            mode = "done"
            continue
        if mode == "question":
            q_parts.append(l)
        elif mode == "answer":
            answer_parts.append(l)
    return Question(
        wq_id=wq_id, reference=ref, member_name=name, constituency=seat,
        dated=dated, welsh=welsh,
        body=" ".join(" ".join(q_parts).split()),
        answered_by=answered_by,
        answered=answered,
        answer=" ".join(" ".join(answer_parts).split()) or None)


def fetch_question(client, wq_id, timeout=30):
    """Question or None (miss). archive=False: ~170KB of site chrome per page
    and the store keeps the parsed text whole; the id IS the provenance."""
    page = client.get_text(QUESTION_URL.format(wq_id), "senedd",
                           "wq-{0}".format(wq_id), timeout=timeout,
                           archive=False)
    return parse_question(page, wq_id)


@dataclass
class Sitting:
    meeting_id: int
    dated: str
    has_votes: bool


def parse_vote_index(page):
    """Sittings from one XMLExport index page, newest first."""
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", page, re.S):
        mid = re.search(r"meetingID=(\d+)", row)
        date = re.search(r"(\d\d)/(\d\d)/(\d\d\d\d) \d\d:\d\d", row)
        if not (mid and date):
            continue
        out.append(Sitting(
            meeting_id=int(mid.group(1)),
            dated="{0}-{1}-{2}".format(date.group(3), date.group(2),
                                       date.group(1)),
            has_votes="xmlDownloadType=Votes" in row))
    return out


def fetch_vote_index(client, parliament, page=1, timeout=60):
    html_page = client.get_text(XML_INDEX_URL.format(parliament, page),
                                "senedd", "xmlindex-{0}-{1}".format(
                                    parliament, page),
                                timeout=timeout, archive=False)
    return parse_vote_index(html_page), ("See More" in html_page)


@dataclass
class SdVote:
    member_id: str
    member_name: str
    result: str             # For | Against | Abstain


@dataclass
class SdDivision:
    key: str                # the export's own vote ID
    meeting_id: int
    dated: str
    title: str              # Vote_Name_English -- what was voted on
    total_for: int
    total_against: int
    total_abstain: int
    result: str             # "Motion has been agreed" etc.
    votes: list


def _field(block, name):
    m = re.search(r"<{0}>(.*?)</{0}>".format(name), block, re.S)
    return _html.unescape(m.group(1)).strip() if m else None


def parse_votes_xml(text):
    """Divisions with per-member votes from one sitting's Votes XML.

    Blocks are one row per (division, member); grouped here on the export's
    own vote ID. 480 blocks in the probed sitting -> a handful of divisions
    of ~96 voters each.
    """
    divs = {}
    # The row wrapper EMBEDS the parliament name in older exports:
    # <XML_Plenary_Vote> for the Seventh Senedd but
    # <XML_Plenary-SixthSenedd_Vote> for the Sixth -- the exact-tag regex
    # silently parsed the Sixth's two years of divisions to zero. Match any
    # XML_Plenary*_Vote wrapper.
    for block in re.findall(
            r"<XML_Plenary[^>]*_Vote>(.*?)</XML_Plenary[^>]*_Vote>",
            text, re.S):
        # The division key is Contribution_ID: <ID> is unique PER ROW (a
        # member-level id), and grouping on it produced 480 one-voter
        # "divisions" from a sitting that actually held 5 of 96 voters each.
        vid = _field(block, "Contribution_ID")
        if not vid:
            continue
        d = divs.get(vid)
        if d is None:
            d = divs[vid] = SdDivision(
                key=vid,
                meeting_id=int(_field(block, "Meeting_ID") or 0),
                dated=(_field(block, "MeetingDate") or "")[:10],
                title=_field(block, "Vote_Name_English") or "",
                total_for=int(_field(block, "VotesTotalFor") or 0),
                total_against=int(_field(block, "VotesTotalAgainst") or 0),
                total_abstain=int(_field(block, "VotesTotalAbstain") or 0),
                result=_field(block, "Vote_Result_English") or "",
                votes=[])
        d.votes.append(SdVote(
            member_id=_field(block, "Member_Id") or "",
            member_name=_field(block, "Member_name_English") or "",
            result=_field(block, "Results_Result") or ""))
    return sorted(divs.values(), key=lambda x: (x.dated, x.key))


def fetch_votes(client, meeting_id, timeout=90):
    return parse_votes_xml(client.get_text(
        VOTES_URL.format(meeting_id), "senedd",
        "votes-{0}".format(meeting_id), timeout=timeout, archive=False))


@dataclass
class SdSpeech:
    key: str            # 'sdc<Contribution_ID>'
    member_id: str
    member_name: str
    dated: str
    heading: str        # Agenda_item_english
    text: str           # Contribution_English, tags stripped


def parse_transcript(text):
    """Attributed speeches from one sitting's English transcript XML.

    Blocks without a Member_Id are chair/procedural furniture and are
    skipped. The wrapper embeds the VENUE name, the same trap as the votes
    XML: plenary exports say XML_Plenary-SixthSenedd_English, committee
    exports say XML_HealthAndSocialCareCommittee_English. The pattern
    matches any venue and backreferences the closing tag, so a wrapper
    nobody has seen yet still parses (found 2026-08-24: the old
    Plenary-only pattern silently returned ZERO for every committee).
    """
    out = []
    for _tag, block in re.findall(
            r"<(XML_[^>\s]*_English)>(.*?)</\1>", text, re.S):
        mid = _field(block, "Member_Id")
        body = _field(block, "Contribution_English") or ""
        if not mid or not body:
            continue
        body = _html.unescape(re.sub(r"<[^>]+>", " ", body))
        out.append(SdSpeech(
            key="sdc{0}".format(_field(block, "Contribution_ID")),
            member_id=mid,
            member_name=_field(block, "Member_name_English") or "",
            dated=(_field(block, "MeetingDate") or "")[:10],
            heading=_field(block, "Agenda_item_english") or "",
            text=" ".join(body.split())))
    return out


def fetch_transcript(client, meeting_id, timeout=120):
    return parse_transcript(client.get_text(
        TRANSCRIPT_URL.format(meeting_id), "senedd",
        "transcript-{0}".format(meeting_id), timeout=timeout, archive=False))


# -- committees ---------------------------------------------------------------
# business.senedd.wales is ModernGov. mgListCommittees names every current
# body; the XMLExport index accepts these SAME ids (Plenary is committee 908,
# which is why the votes exporter's "committee" param worked all along --
# found 2026-08-24). A committee's detail page states its NEXT meeting date
# in prose; the agenda for a future meeting is published later ("The Agenda
# will be displayed as soon as it is available"), so a forward row carries a
# date and no subject until then. The ModernGov CALENDAR is a dead end: all
# three views (month, week, agenda) hold exhibitions only, and Month=/Year=
# are silently ignored -- the same shape as Holyrood's events API.
COMMITTEES_URL = "https://business.senedd.wales/mgListCommittees.aspx?bcr=1"
COMMITTEE_URL = "https://business.senedd.wales/mgCommitteeDetails.aspx?ID={0}"

# Bodies that are not MS scrutiny committees. The Welsh Youth Parliament sits
# in the same ModernGov instance with its own members, who are not MSs and
# never join the roster; Plenary is already harvested by sd_divisions.
_NOT_A_COMMITTEE = re.compile(r"Youth Parliament|WYP\d|^Plenary$", re.I)
_NEXT_MEETING = re.compile(
    r"will next meet on\s+(?:[A-Z][a-z]+day),?\s+(\d{1,2})\s+([A-Z][a-z]+)"
    r"(?:\s+(\d{4}))?", re.I)
_MONTHS = {m: i + 1 for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"))}


def parse_committees(html):
    """(id, name) for every body ModernGov lists, minus the non-committees."""
    out, seen = [], set()
    for cid, name in re.findall(
            r'mgCommitteeDetails\.aspx\?ID=(\d+)"[^>]*>([^<]{3,120})',
            html or ""):
        name = " ".join(_html.unescape(name).split())
        if cid in seen or not name or _NOT_A_COMMITTEE.search(name):
            continue
        seen.add(cid)
        out.append((cid, name))
    return out


# -- the open estate ----------------------------------------------------------
# 2026-08-28: business.senedd.wales went behind an Azure WAF that returns 403
# to every non-browser client -- the honest UA, the authorised browser UA,
# full browser Accept/Sec-Fetch headers, this laptop and GitHub's runners
# alike, on the host root as well as any page. That host held the committee
# list, the meeting index and the transcripts.
#
# All three are recoverable from hosts that are still open:
#
#   * senedd.wales/committees/ lists all 15 committees, each with the
#     ModernGov CommitteeId we already key on, and carries the same
#     "will next meet on ..." prose the old detail page did;
#   * record.senedd.wales -- the Record of Proceedings itself -- indexes
#     committee transcripts through a paged JSON endpoint and serves each
#     meeting's agenda items and contributions as HTML.
#
# The Record is the better source anyway: it is the transcript, not an
# agenda page that links to one.
COMMITTEE_INDEX = "https://senedd.wales/committees/"
RECORD_INDEX = "https://record.senedd.wales/Search/SeeMore"
RECORD_MEETING = "https://record.senedd.wales/Meeting/{0}"
RECORD_TYPE_TRANSCRIPT = 2      # the Type radio on the Record's search form
RECORD_ALL_COMMITTEES = -2      # its MeetingType radio
RECORD_PAGE_SIZE = 8            # what the endpoint returns, not a choice


def parse_committee_index(html):
    """The committee page URLs listed on senedd.wales/committees/.

    Only the links: the id and the name are read from each committee's own
    page, which has to be fetched anyway for the forward look. Pairing the
    15 slugs against the 15 ModernGov links by document order would have
    worked today and mispaired silently the day one committee is added.
    """
    out = []
    for slug in re.findall(r'href="(/committees/[a-z0-9\-]+/)"', html or ""):
        url = "https://senedd.wales" + slug
        if url not in out:
            out.append(url)
    return out


def parse_committee_page(html, today=None):
    """(committee_id, name, next_meeting_id, next_meeting_date).

    The id is the ModernGov CommitteeId the page links to -- the same one
    the store has always keyed on, so changing source renumbers nothing --
    and the next sitting is the same prose sentence the blocked detail page
    carried, parsed by the same reader.
    """
    m = re.search(r'ieListMeetings\.aspx\?CommitteeId=(\d+)', html or "")
    cid = m.group(1) if m else None
    t = re.search(r"<title>([\s\S]{0,200}?)</title>", html or "")
    name = " ".join(_html.unescape(re.sub(r"<[^>]+>", " ", t.group(1))).split()) if t else ""
    name = re.sub(r"\s*[-|]\s*(Welsh Parliament|Senedd).*$", "", name).strip()
    mid, when = parse_next_meeting(html, today=today)
    return cid, name, mid, when


def fetch_committees(client, timeout=120):
    """[(id, name, url)] for every Senedd committee, from the open host."""
    index = parse_committee_index(client.get_text(
        COMMITTEE_INDEX, "senedd", "committee-index", timeout=timeout,
        archive=False))
    out = []
    for url in index:
        key = "committee-" + url.rstrip("/").rsplit("/", 1)[-1]
        cid, name, _mid, _when = parse_committee_page(
            client.get_text(url, "senedd", key, timeout=timeout, archive=False))
        if cid and name and not _NOT_A_COMMITTEE.search(name):
            out.append((cid, name, url))
    return out


def fetch_committee_page(client, url, key, timeout=120):
    """One committee's own page on the open host: id, name, next sitting."""
    return client.get_text(url, "senedd", key, timeout=timeout, archive=False)


def parse_record_index(payload):
    """[(meeting_id, committee_name, iso_date)] from the Record's JSON.

    The endpoint answers with HTML fragments inside JSON, which is why a
    naive regex over the response finds nothing: the markup arrives
    escaped.
    """
    out = []
    for frag in (payload or {}).get("Results") or []:
        mid = re.search(r"/Meeting/(\d+)", frag)
        name = re.search(r'class="title">\s*Transcript - ([^<]+)<', frag)
        when = re.search(r"Meeting on (\d\d)/(\d\d)/(\d{4})", frag)
        if not (mid and when):
            continue
        out.append((mid.group(1),
                    " ".join(_html.unescape(name.group(1)).split()) if name else "",
                    "{2}-{1}-{0}".format(*when.groups())))
    return out


def fetch_record_index(client, page=1, timeout=120):
    """One page of the Record's committee-transcript index, newest first."""
    query = _urlencode({
        "Query": "", "MemberID": -1, "Type": RECORD_TYPE_TRANSCRIPT,
        "Start": "01/01/0001", "End": "01/01/0001",
        "MeetingType": RECORD_ALL_COMMITTEES, "MotionType": -1,
        "OrderPaperFilter": "False", "Page": page, "Unselected": "All"})
    raw = client.get_text("{0}?{1}".format(RECORD_INDEX, query), "senedd",
                          "record-index-{0}".format(page), timeout=timeout,
                          archive=False)
    try:
        return parse_record_index(_json.loads(raw))
    except ValueError:
        return []


class RecordContribution(object):
    """One speech in a committee meeting, as the Record publishes it."""

    __slots__ = ("key", "member_id", "member_name", "heading", "text")

    def __init__(self, key, member_id, member_name, heading, text):
        self.key = key
        self.member_id = member_id
        self.member_name = member_name
        self.heading = heading
        self.text = text


def _record_text(block, prefer_translation=False):
    """Verbatim plus interpretation.

    Proceedings are recorded in the language they were spoken in, with the
    interpretation alongside. Both go to the taxonomy: a Welsh-language
    contribution is not less of a receipt, and dropping the verbatim half
    would silently under-read Welsh-speaking members.
    """
    found = {}
    # The class is "verbatim fullWidth" as often as bare "verbatim", and
    # demanding an exact match found 2 contributions in a meeting of 11.
    for cls in ("verbatim", "translation"):
        parts = []
        for inner in re.findall(
                r'class="%s(?:\s[^"]*)?"[^>]*>([\s\S]*?)</div>' % cls, block):
            got = " ".join(_html.unescape(re.sub(r"<[^>]+>", " ", inner)).split())
            if got and got not in parts:
                parts.append(got)
        found[cls] = " ".join(parts)
    if prefer_translation and found["translation"]:
        return found["translation"]
    both = [x for x in (found["verbatim"], found["translation"]) if x]
    return " ".join(dict.fromkeys(both))


def parse_record_meeting(html):
    """(agenda item titles, [RecordContribution]) for one meeting.

    Contributions carry the speaker's name and their ModernGov UID, and
    each block has a stable id -- so an event key survives a re-read
    without duplicating.
    """
    html = html or ""
    items, out, heading = [], [], ""
    for block in re.split(r'(?=<div class="itemContent (?:agendaItem|contribution)")',
                          html):
        if 'class="itemContent agendaItem"' in block:
            # The heading takes ONE language -- the interpretation where
            # there is one -- or a Petitions item reads "3. Deisebau newydd
            # 3. New Petitions". The contribution TEXT keeps both, because
            # that is what the taxonomy reads.
            title = _record_text(block, prefer_translation=True)
            if title:
                items.append(title[:300])
                heading = title[:300]
            continue
        if 'class="itemContent contribution"' not in block:
            continue
        text = _record_text(block)
        if not text:
            continue
        cid = re.search(r'class="itemContent contribution"[^>]*id="([^"]+)"', block)
        uid = re.search(r"mgUserInfo\.aspx\?UID=(\d+)", block)
        name = re.search(r'class="name"[^>]*>([\s\S]{0,120}?)</span>', block)
        out.append(RecordContribution(
            cid.group(1) if cid else None,
            uid.group(1) if uid else None,
            " ".join(_html.unescape(re.sub(r"<[^>]+>", " ", name.group(1))).split())
            if name else "",
            heading, text))
    return items, out


def fetch_record_meeting(client, meeting_id, timeout=120):
    return parse_record_meeting(client.get_text(
        RECORD_MEETING.format(meeting_id), "senedd",
        "record-meeting-{0}".format(meeting_id), timeout=timeout,
        archive=False))


def parse_next_meeting(html, today=None):
    """(meeting_id, iso_date) for a committee's next sitting, or (None, None).

    The date is prose ("will next meet on Thursday 17 September"), often
    with no year, so the year is inferred as the next occurrence from
    `today` -- never guessed backwards.
    """
    mid = None
    m = re.search(r'ieListDocuments\.aspx\?CId=\d+&(?:amp;)?MId=(\d+)',
                  html or "")
    if m:
        mid = m.group(1)
    d = _NEXT_MEETING.search(html or "")
    if not d:
        return mid, None
    month = _MONTHS.get((d.group(2) or "").lower())
    if not month:
        return mid, None
    day = int(d.group(1))
    if d.group(3):
        year = int(d.group(3))
    else:
        today = today or _dt.date.today()
        year = today.year
        if (month, day) < (today.month, today.day):
            year += 1
    try:
        return mid, _dt.date(year, month, day).isoformat()
    except ValueError:
        return mid, None


# The ModernGov readers, kept but NOT reachable: business.senedd.wales has
# returned 403 to every client since 2026-08-28. They are named with a
# _moderngov suffix so that a second `def fetch_committees` can never again
# silently shadow the open-host one further up this file -- which is exactly
# what happened when the replacement was first written, and the tool went on
# calling the blocked host while reporting the WAF's 403 as a data gap.
def fetch_committees_moderngov(client, timeout=120):
    return parse_committees(client.get_text(
        COMMITTEES_URL, "senedd", "committees", timeout=timeout,
        archive=False))


def fetch_next_meeting_moderngov(client, committee_id, timeout=120):
    return parse_next_meeting(client.get_text(
        COMMITTEE_URL.format(committee_id), "senedd",
        "committee-{0}".format(committee_id), timeout=timeout, archive=False))


# -- bills --------------------------------------------------------------------
# The register route: senedd.wales/senedd-business/legislation/ (honest UA)
# links per-bill ModernGov tracking pages on business.senedd.wales (the one
# authorised browser-UA host). The tracking page carries no status FIELD --
# the stage lives in PROSE ("Royal Assent was given on 27 April 2026",
# "Stage 4 proceedings took place in..."), the scotland.py pattern exactly.
LEGISLATION_URL = "https://senedd.wales/senedd-business/legislation/"
REJECTED_URL = ("https://senedd.wales/senedd-business/legislation/"
                "rejected-bills-and-withdrawn-bills/")
BILL_URL = "https://business.senedd.wales/mgIssueHistoryHome.aspx?IId={0}"

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}
_ASSENT = re.compile(r"Royal Assent(?:\s+was)?(?:\s+given)?(?:\s+on)?\s+"
                     r"\(?(\d{1,2}) (\w+) (\d{4})", re.I)
_STAGE = re.compile(r"Stage (\d)", re.I)
_DEAD = re.compile(r"withdrawn|rejected|fell|did not proceed", re.I)


def parse_bill_links(page):
    """[(iid, title)] from a senedd.wales page linking tracking pages."""
    out = []
    for iid, title in re.findall(
            r'href="https://business\.senedd\.wales/mgIssueHistoryHome'
            r'\.aspx\?IId=(\d+)"[^>]*>([^<]+)', page):
        out.append((int(iid), _html.unescape(title).strip()))
    return out


def parse_bill_status(page):
    """(latest_stage, date_iso_or_None) from a tracking page's prose.

    Royal Assent (with its date) wins; otherwise the highest Stage number
    mentioned; a dead marker (withdrawn/rejected/fell) is its own terminal
    stage. No date is extractable for bare stage mentions -- the page gives
    event timelines, not a stage-date field -- so date is None there.
    """
    m = _ASSENT.search(page)
    if m:
        month = _MONTHS.get(m.group(2).lower())
        date = ("{0}-{1:02d}-{2:02d}".format(m.group(3), month,
                                             int(m.group(1)))
                if month else None)
        return "Royal Assent", date
    if _DEAD.search(page):
        return "Withdrawn or rejected", None
    stages = [int(x) for x in _STAGE.findall(page)]
    if stages:
        return "Stage {0}".format(max(stages)), None
    return "Introduced", None


def fetch_bill(client, iid, timeout=60):
    page = client.get_text(BILL_URL.format(iid), "senedd",
                           "bill-{0}".format(iid), timeout=timeout,
                           archive=False)
    title = re.search(r"<title>([^<|]+)", page)
    stage, date = parse_bill_status(page)
    return (_html.unescape(title.group(1)).strip() if title else "",
            stage, date)
