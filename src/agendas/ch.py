"""Switzerland: the sessions programme from the Parliament Webservices.

The Federal Assembly sits in four three-week sessions a year (plus special
sessions). Each sitting of either council is a `Meeting` with its
`Subjects` (the order of business), each naming the businesses taken
(`SubjectBusiness`: the Geschäftsnummer, the title, the stage such as
'Erstrat', 'Differenzen' or 'Schlussabstimmung'). The OData service carries a
session's meetings once the programme is published, a few weeks before the
session opens; between sessions there is nothing ahead, and the Coverage
line names the next session when the service lists it.

Measured 10 October 2026: the Herbstsession 2026 (to 2 October) is the
latest session in the service; the Wintersession (from 30 November) has no
meetings yet. Refs are the short business numbers ('25.3944'), the keys
config/watchlist-ch.yaml and ch_businesses.short_number use.
"""

from __future__ import annotations

import datetime
import re

from src import agenda
from src.http import FetchError

CC = "ch"
SOURCE = "the Parliament Webservices' Meeting and Subject records"
BILLS = ("ch_businesses", "short_number", "title_de")
FEED = "ch-agenda"
ODATA = "https://ws.parlament.ch/odata.svc/"
MEETINGS = (ODATA + "Meeting?$filter=Language%20eq%20'DE'%20and%20Date%20ge%20datetime'"
            "{0}T00:00:00'%20and%20Date%20lt%20datetime'{1}T00:00:00'"
            "&$expand=Subjects/SubjectsBusiness&$format=json")
SESSIONS = (ODATA + "Session?$filter=Language%20eq%20'DE'%20and%20StartDate%20ge%20datetime'"
            "{0}T00:00:00'&$orderby=StartDate&$top=2&$format=json")
COUNCIL = {"NR": "Nationalrat", "SR": "Ständerat", "VB": "United Federal Assembly"}
WEB = "https://www.parlament.ch/de/ratsbetrieb/suche-curia-vista/geschaeft?AffairId={0}"
MS = re.compile(r"/Date\((-?\d+)\)/")


def odata_date(raw):
    m = MS.search(raw or "")
    if not m:
        return None
    return datetime.datetime.utcfromtimestamp(int(m.group(1)) / 1000).date().isoformat()


def results(value):
    if isinstance(value, dict):
        return value.get("results") or []
    return value or []


def parse(reply):
    out = []
    for m in results((reply or {}).get("d")):
        date = odata_date(m.get("Date"))
        begin = (m.get("Begin") or "").strip()
        time = "{0}:{1}".format(begin[:2], begin[2:4]) if len(begin) == 4 else None
        council = COUNCIL.get(m.get("CouncilAbbreviation"), m.get("CouncilName") or "Council")
        body = "{0}, {1}".format(council, m.get("SessionName") or "session")
        for s in sorted(results(m.get("Subjects")), key=lambda x: x.get("SortOrder") or 0):
            biz = results(s.get("SubjectsBusiness"))
            if not biz:
                continue
            first = biz[0]
            title = " ".join((first.get("Title") or "").split())
            stage = " ".join((first.get("PublishedNotes") or "").split()) or None
            refs = [b.get("BusinessShortNumber") for b in biz if b.get("BusinessShortNumber")]
            fr = " ".join((first.get("TitleFR") or "").split())
            others = ["{0} {1}".format(b.get("BusinessShortNumber") or "",
                                       " ".join((b.get("Title") or "").split()))
                      for b in biz[1:]]
            # The French title is classified too (taxonomy-fr, Swiss terms).
            detail = "; ".join(([fr] if fr else []) + others) or None
            out.append(agenda.point(s.get("ID"), date, title, body, "plenary", time, detail,
                                    refs=refs, url=WEB.format(first.get("BusinessNumber")),
                                    status=stage))
    return out


def fetch(client, today, days, log=print):
    end = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    gaps, points, nxt, note = [], [], None, None
    try:
        points = parse(client.get_json(MEETINGS.format(today, end), FEED,
                                       "meetings-{0}".format(today), timeout=120))
    except (FetchError, ValueError) as exc:
        gaps.append("Meeting unreadable: {0}".format(str(exc)[:120]))
    try:
        sess = results(client.get_json(SESSIONS.format(today), FEED,
                                       "sessions-{0}".format(today)).get("d"))
    except (FetchError, ValueError) as exc:
        sess = []
        gaps.append("Session unreadable: {0}".format(str(exc)[:120]))
    if sess:
        nxt = odata_date(sess[0].get("StartDate"))
        note = "Next session: {0}".format(sess[0].get("SessionName"))
    if not points:
        note = ((note + "; ") if note else "") + \
            "no sittings ahead in the open data (the councils sit only in session)"
    dates = sorted(p["date"] for p in points if p["date"])
    return agenda.fetched(points, next_sitting=nxt or (dates[0] if dates else None),
                          note=note, gaps=gaps)
