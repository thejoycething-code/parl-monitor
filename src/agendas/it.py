"""Italy: the Camera's calendar of the Assembly's work.

Neither SPARQL endpoint carries the forward agenda (docs/italy-scope.md).
The Camera publishes its monthly calendar, set by the conference of group
leaders and updated through the month ('Calendario n. 43 ottobre',
'Aggiornamento del Calendario n. 42'), as HTML: the agenda page lists the
calendars, newest first, and each one is served whole by
`/leg19/proxy19/calendari_assemblea?file=<id>`. Measured 10 October 2026:
the October calendar, 106 KB, every day from 5 to 30 October, each item
linking the Atto Camera it takes ('n. 2830' -> '19/C.2830').

camera.it answers "format json not implemented yet" to the default
Accept header, so these requests send Accept: text/html.

The Senate's calendar is not read: senato.it refuses us
(docs/italy-scope.md). Committee convocations are a later step.
"""

from __future__ import annotations

import datetime
import html
import re

from src import agenda
from src.http import FetchError

CC = "it"
SOURCE = "the Camera's calendar of the Assembly's work"
BILLS = ("it_bills", "bill_key", "title")
FEED = "it-agenda"
LEG = 19
HOST = "https://www.camera.it"
INDEX = HOST + "/leg{0}/76?active_tab_3806=4184".format(LEG)
CALENDAR = HOST + "/leg{0}/proxy19/calendari_assemblea?file={{0}}".format(LEG)
ACCEPT = {"Accept": "text/html,application/xhtml+xml"}
MONTHS = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
          "settembre", "ottobre", "novembre", "dicembre")

OPTION = re.compile(r'<option[^>]*value="([^"]+)"[^>]*>([^<]*)</option>')
ROW = re.compile(r'(?s)<td class="ventiX100">(.*?)</td>\s*<td class="ottantaX100">(.*?)</td>')
PARA = re.compile(r"(?s)<p[^>]*>(.*?)</p>")
ATTO = re.compile(r"tipoDoc=pdl&(?:amp;)?idDocumento=([0-9]+(?:-[A-Z]+)?)")
DAY = re.compile(r"\b(\d{1,2})\b")
YEAR = re.compile(r"\((?:\w+)\s+(\d{4})\)")


def text_of(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment or "")
    return " ".join(html.unescape(t).replace("​", "").replace(" ", " ").split())


def calendars(index_html):
    """[(file id, label)] from the agenda page, as listed (newest first)."""
    return [(v, " ".join(html.unescape(t).split())) for v, t in OPTION.findall(index_html or "")
            if v.startswith(("comunicazioni.", "lavori."))]


def heading_date(text, year):
    """'Martedì 13 (ore 9-13,30 ...) e mercoledì 14 ottobre' -> the first day,
    with the month named in the heading."""
    low = text.lower()
    month = next((i + 1 for i, m in enumerate(MONTHS) if m in low), None)
    day = DAY.search(low)
    if not month or not day:
        return None
    try:
        return datetime.date(year, month, int(day.group(1))).isoformat()
    except ValueError:
        return None


def parse(page, cal_id, year=None):
    """Points from one calendar."""
    if year is None:
        m = YEAR.search(text_of(page[:3000]))
        year = int(m.group(1)) if m else datetime.date.today().year
    out = []
    for i, (head, cell) in enumerate(ROW.findall(page or ""), 1):
        head_text = text_of(head)
        date = heading_date(head_text, year)
        when = re.search(r"\((?:ore\s*)?([^)]*)\)", head_text)
        for j, para in enumerate(PARA.findall(cell), 1):
            title = text_of(para)
            if not title:
                continue
            refs = ["{0}/C.{1}".format(LEG, n) for n in ATTO.findall(para)]
            out.append(agenda.point("{0}-{1}-{2}".format(cal_id.split(".")[-1], i, j), date,
                                    title,
                                    "Camera, Assembly", "plenary",
                                    detail=head_text if when else None, refs=refs,
                                    url=CALENDAR.format(cal_id)))
    return out


def fetch(client, today, days, log=print):
    try:
        index = client.get_text(INDEX, FEED, "calendari-{0}".format(today), headers=ACCEPT)
    except FetchError as exc:
        return agenda.fetched([], gaps=["calendar list unreadable: {0}".format(str(exc)[:120])])
    cals = calendars(index)
    if not cals:
        return agenda.fetched([], gaps=["the agenda page lists no calendar"])
    cal_id, label = cals[0]
    try:
        page = client.get_text(CALENDAR.format(cal_id), FEED, "calendario-" + cal_id,
                               headers=ACCEPT)
    except FetchError as exc:
        return agenda.fetched([], gaps=["calendar {0} unreadable: {1}".format(
            cal_id, str(exc)[:100])])
    points = [p for p in parse(page, cal_id) if p["date"] and p["date"] >= today]
    end = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    points = [p for p in points if p["date"] <= end]
    dates = sorted(p["date"] for p in points)
    note = "From {0}".format(label)
    if not points:
        note += "; nothing in it from today on (the next month's calendar is set at its start)"
    return agenda.fetched(points, next_sitting=dates[0] if dates else None, note=note)
