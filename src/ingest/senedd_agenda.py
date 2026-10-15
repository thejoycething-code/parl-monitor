"""Senedd forward business: Plenary and committee agendas from ModernGov's
web service.

Routes, probed from the laptop 15 October 2026 with the identified UA
"CitizenGO-ParlMonitor/1.0 (contact: cjoyce@citizengo.net)"
(docs/devolved-forward-scope.md has the full table):

  * business.senedd.wales (ModernGov) web pages -- the calendar, agenda pages
    (ieListDocuments), the host root, robots.txt itself -- answer the Azure
    WAF's 403 "Service unavailable" page, as they have since 28 August. The
    403 WebFetch saw on the calendar is that WAF, not a WebFetch quirk.
  * business.senedd.wales/mgWebService.asmx -- ModernGov's documented web
    service, self-describing (the .asmx page lists its 21 operations with
    GET/SOAP signatures) -- ANSWERS the identified UA with 200 and XML. No
    browser User-Agent, no cookie, no key: the host serves its machine
    interface to programs and blocks only the web pages. The host's
    robots.txt is the WAF page (a 4xx: no rules, RFC 9309 2.3.1.3).
      GetCommittees                         every body (210), expired flag
      GetMeetings?lCommitteeId&sFromDate&sToDate   meetings in a window
                                            (dates DD/MM/YYYY; ISO dates are
                                            misread and return May onwards)
      GetMeeting?lMeetingId                 the agenda: numbered items with
                                            titles, the agenda text, whether
                                            the agenda is published yet
    Plenary (committee 908) lists its sittings to mid-December; a sitting's
    agenda is published about a week ahead (agendapublished=False before),
    committee draft agendas a week or two ahead.
  * senedd.wales "Business Statement and Announcement" (the three-week look
    the Trefnydd gives each Tuesday): the Plenary agenda item has no link,
    and the only route on senedd.wales is /search, which robots.txt
    disallows. Not used; the ModernGov meetings list gives the sitting dates
    and each agenda as soon as it is published.
  * record.senedd.wales (the Record) holds what WAS said; the Plenary agenda
    links its OrderPaper/OralQuestions page for the day, which is not needed
    for the item list.

The web service answers in English (agendaitemtitle). Welsh-only text is not
expected; if a title carries both languages the English is what the
taxonomy reads (the brief: English taxonomy, English version).
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import re
from dataclasses import dataclass

from src.devolved_agenda import clean

WS = "https://business.senedd.wales/mgWebService.asmx/"
COMMITTEES_URL = WS + "GetCommittees"
MEETINGS_URL = WS + "GetMeetings?lCommitteeId={0}&sFromDate={1}&sToDate={2}"
MEETING_URL = WS + "GetMeeting?lMeetingId={0}"
# The official agenda page a reader opens (a person's browser passes the WAF).
AGENDA_PAGE = "https://business.senedd.wales/ieListDocuments.aspx?MId={0}"
PLENARY = "908"

# Bodies whose agendas are Senedd business. Business Committee (procedure),
# the Commission, the Youth Parliament, ceremonial occasions are not.
CATEGORIES = ("Plenary", "Committees")
_NOT_SCRUTINY = re.compile(r"Youth Parliament|WYP\d|Chairs' Forum|Llywydd's Committee", re.I)


def _tag(block, name):
    m = re.search(r"<{0}>([\s\S]*?)</{0}>".format(name), block or "")
    return _html.unescape(m.group(1)).strip() if m else ""


def ddmmyyyy(day):
    return day.strftime("%d/%m/%Y")


def _iso(ddmmyy):
    m = re.match(r"(\d\d)/(\d\d)/(\d{4})", ddmmyy or "")
    return "{0}-{1}-{2}".format(m.group(3), m.group(2), m.group(1)) if m else None


class ServiceShapeError(ValueError):
    """The service answered with something that is not its XML."""


def _expect(xml, root):
    if "<{0}".format(root) not in (xml or ""):
        raise ServiceShapeError("expected <{0}>, got {1!r}".format(root, (xml or "")[:80]))


def parse_committees(xml):
    """[(id, title, category)] for live Plenary and scrutiny committees."""
    _expect(xml, "committees")
    out = []
    for block in re.findall(r"<committee>([\s\S]*?)</committee>", xml):
        if _tag(block, "committeeexpired") != "False" or _tag(block, "committeedeleted") == "True":
            continue
        cid, title, cat = (_tag(block, "committeeid"), " ".join(_tag(block, "committeetitle").split()),
                           _tag(block, "committeecategory"))
        if cat in CATEGORIES and not _NOT_SCRUTINY.search(title):
            out.append((cid, title, cat))
    return out


@dataclass
class Meeting:
    meeting_id: str
    committee_id: str
    committee: str
    dated: str
    time: str
    status: str


def parse_meetings(xml, committee_id="", committee=""):
    _expect(xml, "getmeetings")
    out = []
    for block in re.findall(r"<meeting>([\s\S]*?)</meeting>", xml):
        out.append(Meeting(
            meeting_id=_tag(block, "meetingid"), committee_id=committee_id,
            committee=committee or _tag(xml, "committeetitle"),
            dated=_iso(_tag(block, "meetingdate")),
            time=_tag(block, "meetingtime").replace(".", ":"),
            status=_tag(block, "meetingstatus")))
    return out


@dataclass
class AgendaItem:
    item_id: str
    number: str
    order: int
    title: str
    text: str
    restricted: bool


def parse_meeting(xml):
    """(published, location, [AgendaItem]) from GetMeeting. Only numbered
    items are agenda business: the unnumbered ones are notes ("This meeting
    will be held in a hybrid format", "This is a draft agenda")."""
    _expect(xml, "meeting")
    published = _tag(xml.split("<agendaitems>")[0], "agendapublished") == "True"
    location = _tag(xml.split("<meetingroom>")[0], "meetinglocation")
    items = []
    for block in re.findall(r"<agendaitem>([\s\S]*?)</agendaitem>", xml):
        title = " ".join(clean(_tag(block, "agendaitemtitle")).split())
        number = _tag(block, "fulldisplaynumberformat")
        if not title or not number:
            continue
        try:
            order = int(_tag(block, "agendaitemnumber") or 0)
        except ValueError:
            order = 0
        # Sub-items ("6.1" under "6. Papers to note") sort after their parent.
        parts = re.findall(r"\d+", number)
        if len(parts) > 1:
            order = int(parts[0]) * 100 + int(parts[1])
        text = clean(_tag(block, "agendatext"))
        text = "\n".join(l for l in text.splitlines()
                         if not re.match(r"^(View\b|Ymddiheuriadau)", l))
        items.append(AgendaItem(
            item_id=_tag(block, "agendaitemid"), number=number.rstrip("."),
            order=order, title=title, text=text[:4000],
            restricted=_tag(block, "isrestricted") == "True"))
    return published, location, items


def english(title):
    """English half of a bilingual 'Welsh / English' title, else the title."""
    if " / " in title:
        a, b = title.split(" / ", 1)
        welsh = re.search(r"\b(y|yr|a|ac|ar|i|o|gan|Pwyllgor|Cyfarfod|Bil)\b", a)
        return b.strip() if welsh else title
    return title


def window(start, end):
    return ddmmyyyy(start), ddmmyyyy(end)
