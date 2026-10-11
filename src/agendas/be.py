"""Belgium: the Chamber's plenary and committee agendas from its eMeeting
service.

The Chamber's agenda pages (agendaList.cfm, comagendaList.cfm) link each
convocation as a PDF and as an eMeeting page. The eMeeting viewer reads a
plain XML service on the same host, no sign-in:

    /agenda/api/meetings/week/<year>/<ISO week>/calendar.xml?status=final
        every meeting of the week: organ ('plen', 'comm_K221'), date, time,
        meeting number, both titles;
    /agenda/api/meetings/<organ>/final/<date>/<number>/agenda.xml
        the meeting's order of business: sections and items, each item's
        paragraphs in Dutch and French, a bill item linking its dossier
        (flwbn.cfm?dossierID=1338&legislat=56).

Measured 11 October 2026: the week of 12 October had 11 meetings (three
plenary sittings, the Conference of Presidents, the Bureau, six committee
meetings); the plenary of 8 October took three bills (DOC 1606, 1654, 1338,
the last on bereavement leave around a planned euthanasia). Agendas are
published about a week ahead, so the third week read is usually empty (the
service answers 404 for a week with nothing convened, which is not a gap).

One point per item (one question, one bill or a joined group), titled in
Dutch with the French as its detail, so both taxonomies read it. Refs are
dossier keys ('56/1338'), the keys of be_dossiers and
config/watchlist-be.yaml, from the item's dossier links and from the
document numbers its text prints ('nrs. 1338/1 tot 8').

robots.txt asks for a crawl delay of 5 seconds: the client is throttled to
that for the host. The Bureau and the Conference of Presidents are left out
(no public order of business).
"""

from __future__ import annotations

import datetime
import re
import xml.etree.ElementTree as ET

from src import agenda
from src.http import FetchError

CC = "be"
SOURCE = "the Chamber's eMeeting agenda service"
# be_dossiers keeps no tier column: tier comes from the point's own words.
BILLS = ("be_dossiers", "dossier_key", "title_nl", None)
FEED = "be-agenda"
HOST = "https://www.lachambre.be"
API = HOST + "/agenda/api/meetings/"
WEEK = API + "week/{0}/{1}/calendar.xml?status=final"
AGENDA = API + "{organ}/final/{date}/{number}/agenda.xml"
WEB = HOST + "/emeeting/?organ={organ}&status=final&number={number}&date={date}"
CRAWL_DELAY = 5.0
LEG = 56
SKIP_ORGANS = ("comm_BUR", "comm_PRES")
MAX_MEETINGS = 60

DOSSIER_LINK = re.compile(r"dossierID=(\d+)&(?:amp;)?legislat=(\d+)")
# 'nrs. 1606/1 tot 5', 'n°s 1338/1 à 8', 'nr. 1773/1', 'n° 1754/1'
DOC_NUM = re.compile(r"\bn(?:rs?|°\s*s?|\s°s)\.?\s*(\d{1,4})/\d+", re.I)


def label(el, lang):
    """The label in `lang` under an element's description or title."""
    if el is None:
        return ""
    for lab in el.iter("label"):
        if lab.get("lang") == lang:
            return " ".join((lab.text or "").split())
    return ""


def weeks(today, days):
    """(ISO year, ISO week) for each week the window touches."""
    d = datetime.date.fromisoformat(today)
    end = d + datetime.timedelta(days=days)
    out = []
    while d <= end:
        iso = d.isocalendar()
        if (iso[0], iso[1]) not in out:
            out.append((iso[0], iso[1]))
        d += datetime.timedelta(days=1)
    return out


def parse_calendar(xml_text):
    """[{organ, date, time, number, nl, fr}] from one week's calendar."""
    try:
        root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    except ET.ParseError:
        return []
    out = []
    for m in root.iter("meeting"):
        if (m.findtext("status") or "final") != "final":
            continue
        out.append({"id": m.findtext("id"), "organ": m.findtext("organ"),
                    "date": (m.findtext("date") or "")[:10] or None,
                    "time": (m.findtext("time") or "")[:5] or None,
                    "number": m.findtext("meetingNumber") or "1",
                    "nl": label(m.find("title"), "nl"), "fr": label(m.find("title"), "fr")})
    return out


def refs_of(item):
    refs = []
    for link in item.iter("link"):
        for lab in link.iter("label"):
            for num, leg in DOSSIER_LINK.findall(lab.text or ""):
                refs.append("{0}/{1}".format(leg, int(num)))
    for para in item.iter("para"):
        for lang in ("nl", "fr"):
            for num in DOC_NUM.findall(label(para.find("description"), lang)):
                refs.append("{0}/{1}".format(LEG, int(num)))
    return refs


def parse_agenda(xml_text, meeting):
    """Points from one meeting's agenda.xml."""
    try:
        root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    except ET.ParseError:
        return []
    organ = meeting["organ"]
    plenary = organ == "plen"
    body = "Plenary" if plenary else (meeting.get("nl") or meeting.get("fr") or organ)
    url = WEB.format(organ=organ, number=meeting["number"], date=meeting["date"])
    out, n = [], 0
    ag = root.find("agenda")
    if ag is None:
        return out
    for section in ag.iter("section"):
        head_nl = label(section.find("description"), "nl")
        head_fr = label(section.find("description"), "fr")
        items = section.findall("item")
        if not items:
            if head_nl or head_fr:
                n += 1
                out.append(agenda.point("{0}-{1}".format(meeting["id"], n), meeting["date"],
                                        head_nl or head_fr, body,
                                        "plenary" if plenary else "committee", meeting["time"],
                                        head_fr if head_nl else None, url=url))
            continue
        groups = []
        for item in items:
            paras = [p for p in item.findall("para")
                     if p.get("type") not in ("FLWB-motivation", "FLWB-rapporteurs")]
            numbered = [p for p in paras if refs_of(p)]
            # A list (the prises en considération) prints several dossiers in
            # one item: one point per dossier, so each meets its own bill.
            if len(numbered) > 1:
                groups += [(p, [p]) for p in numbered]
            elif paras:
                groups.append((item, paras))
        for item, paras in groups:
            nl = [label(p.find("description"), "nl") for p in paras]
            fr = [label(p.find("description"), "fr") for p in paras]
            title = next((t for t in nl if t), "") or next((t for t in fr if t), "")
            if not title:
                continue
            n += 1
            rest_nl = " ".join(t for t in nl if t and t != title)
            detail = " ".join(x for x in (" ".join(t for t in fr if t), rest_nl) if x)
            out.append(agenda.point("{0}-{1}".format(meeting["id"], n), meeting["date"], title,
                                    body, "plenary" if plenary else "committee",
                                    meeting["time"], detail or None, refs=refs_of(item),
                                    url=url, status=head_nl or None))
    return out


def fetch(client, today, days, log=print):
    end = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    throttle = getattr(client, "set_host_throttle", None)
    if throttle:
        throttle("www.lachambre.be", CRAWL_DELAY)
    meetings, gaps = [], []
    for year, week in weeks(today, days):
        try:
            got = parse_calendar(client.get_text(WEEK.format(year, week), FEED,
                                                 "week-{0}-{1}".format(year, week)))
        except FetchError as exc:
            # The service answers 404 for a week with nothing convened yet.
            if getattr(exc.cause, "code", None) != 404:
                gaps.append("week {0}/{1} unreadable: {2}".format(year, week, str(exc)[:80]))
            continue
        meetings += [m for m in got if m["date"] and today <= m["date"] <= end
                     and m["organ"] not in SKIP_ORGANS]
    points, read = [], 0
    for m in meetings:
        if read >= MAX_MEETINGS:
            gaps.append("agendas: stopped after {0} meetings".format(MAX_MEETINGS))
            break
        read += 1
        try:
            page = client.get_text(AGENDA.format(organ=m["organ"], date=m["date"],
                                                 number=m["number"]),
                                   FEED, "agenda-{0}-{1}-{2}".format(m["organ"], m["date"],
                                                                     m["number"]))
        except FetchError as exc:
            gaps.append("{0} {1} unreadable: {2}".format(m["organ"], m["date"], str(exc)[:80]))
            continue
        points += parse_agenda(page, m)
    plenary = sorted(m["date"] for m in meetings if m["organ"] == "plen")
    note = None if meetings else "No meeting is convened yet in the weeks read"
    return agenda.fetched(points, horizon=max((m["date"] for m in meetings), default=None),
                          next_sitting=plenary[0] if plenary else None, note=note, gaps=gaps)
