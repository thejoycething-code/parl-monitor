"""Slovakia: the Národná rada's sitting programmes (program schôdze) from
its open data.

`General/Meetings?termNr=9` lists the term's sittings (schôdze) with their
first day and, once closed, their last; a sitting appears there once the
Speaker has convened it, about a week before it opens. Its programme,
`General/MeetingProgram?termNr=9&meetingNr=<n>`, is the order of business
point by point, each with the print it takes (`billNr`, the tlač) and the
Speaker's notes ('druhé čítanie', who presents it). Measured 11 October
2026: the 61st sitting (15 September to 9 October) had 120-odd points; no
later sitting was convened yet. The year's schedule (harmonogram schôdzí)
is a document on the web site and is not read.

The programme does not say which day a point is taken: a point is dated to
its sitting's first day, or, for a sitting already open, to the day the
agenda is read (the point is still to be taken or under way), and the body
names the sitting. Points 9999 are the standing items (question time,
interpellations).

Refs are print keys ('9/1324'), the keys of sk_bills and
config/watchlist-sk.yaml. robots.txt: none (404), 11 October 2026.
"""

from __future__ import annotations

import datetime

from src import agenda
from src.http import FetchError

CC = "sk"
SOURCE = "the Národná rada's open data, Meetings and MeetingProgram"
BILLS = ("sk_bills", "bill_key", "title")
FEED = "sk-agenda"
TERM = 9
OPENDATA = "https://www.nrsr.sk/opendata/1/sk/"
MEETINGS = OPENDATA + "General/Meetings?termNr={0}".format(TERM)
PROGRAM = OPENDATA + "General/MeetingProgram?termNr={0}&meetingNr={1}"
WEB_PROGRAM = "https://www.nrsr.sk/web/Default.aspx?sid=schodze/program&CisSchodze={0}"


def upcoming(meetings, today):
    """Sittings that open on or after `today`, or are open on it."""
    out = []
    for m in meetings or []:
        begin = (m.get("beginDate") or "")[:10]
        end = (m.get("endDate") or "")[:10]
        if not begin:
            continue
        if begin >= today or (end and end >= today):
            out.append(m)
    return sorted(out, key=lambda m: m.get("beginDate") or "")


def parse_program(rows, meeting, today):
    """Points from one sitting's programme."""
    begin = (meeting.get("beginDate") or "")[:10]
    date = begin if begin >= today else today
    number = meeting.get("meetingNr")
    body = "Plenary, {0}".format(meeting.get("description") or "{0}. schôdza".format(number))
    if begin < today:
        body += " (open since {0})".format(begin)
    out = []
    for r in rows or []:
        title = r.get("description") or ""
        if not title.strip():
            continue
        point_nr = r.get("pointNr")
        notes = " ".join(x for x in (r.get("description2"), r.get("description3")) if x) or None
        bill = str(r.get("billNr") or "").strip()
        refs = ["{0}/{1}".format(TERM, b.strip()) for b in bill.replace(";", ",").split(",")
                if b.strip().isdigit()]
        out.append(agenda.point("{0}-{1}".format(number, r.get("id")), date, title, body,
                                "plenary", detail=notes, refs=refs,
                                url=WEB_PROGRAM.format(number),
                                status="Standing item" if point_nr == 9999 else None))
    return out


def fetch(client, today, days, log=print):
    end = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    try:
        meetings = client.get_json(MEETINGS, FEED, "meetings-term{0}".format(TERM))
    except (FetchError, ValueError) as exc:
        return agenda.fetched([], gaps=["Meetings unreadable: {0}".format(str(exc)[:120])])
    ahead = [m for m in upcoming(meetings, today) if (m.get("beginDate") or "")[:10] <= end]
    points, gaps = [], []
    for m in ahead:
        try:
            rows = client.get_json(PROGRAM.format(TERM, m.get("meetingNr")), FEED,
                                   "program-{0}".format(m.get("meetingNr")))
        except (FetchError, ValueError) as exc:
            gaps.append("programme of sitting {0} unreadable: {1}".format(
                m.get("meetingNr"), str(exc)[:80]))
            continue
        points += parse_program(rows, m, today)
    starts = [max((m.get("beginDate") or "")[:10], today) for m in ahead]
    note = None if ahead else "No sitting is convened yet; the next appears about a week before it opens"
    return agenda.fetched(points, next_sitting=min(starts) if starts else None, note=note,
                          gaps=gaps)
