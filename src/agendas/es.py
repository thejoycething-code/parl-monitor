"""Spain: the Congreso de los Diputados' weekly agenda.

No structured feed (docs/spain-scope.md): the agenda is HTML,
`/es/agenda` with `_agenda_mvcPath=agendaSemanal` and a day of the week
wanted, the whole week ('Agenda completa') with a heading per day ('Lunes
14 de septiembre de 2026') and a row per meeting: the time, the body and
its business in the Congreso's words, and links to the committee's order
of the day. The collector reads this week and the next ones the window
reaches, one page a week. Measured 9 October 2026 (the week of 14
September, the XV sitting): 60-odd rows a week, committees and plenary.

ES6: the Cortes were dissolved on 6 October 2026 and the XVI legislature
convenes on 23 December, so until then the agenda holds the Diputación
Permanente, the Mesa and events; the section fills when the XVI sits, with
no edit here. Initiative numbers printed in a row ('122/000123') become
keys with the legislature ('16/122/000123'), the keys of es_initiatives
and config/watchlist-es.yaml.
"""

from __future__ import annotations

import datetime
import html
import re

from src import agenda
from src.http import FetchError

CC = "es"
SOURCE = "the Congreso's weekly agenda page"
BILLS = ("es_initiatives", "initiative_key", "objeto")
FEED = "es-agenda"
BASE = "https://www.congreso.es"
WEEK = (BASE + "/es/agenda?p_p_id=agenda&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view"
        "&_agenda_mvcPath=agendaSemanal&_agenda_tipoagenda=1&_agenda_dia={d}&_agenda_mes={m}"
        "&_agenda_anio={y}")
ACCEPT = {"Accept": "text/html,application/xhtml+xml"}
XVI_CONVENES = "2026-12-23"
MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")

DAY_HEAD = re.compile(r"(?is)<h3>\s*(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|"
                      r"domingo)\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})\s*</h3>")
TR = re.compile(r"(?s)<tr>(.*?)</tr>")
TD = re.compile(r"(?s)<td[^>]*>(.*?)</td>")
DIVS = re.compile(r"(?s)<div[^>]*>(.*?)</div>")
EXP = re.compile(r"\b(\d{3}/\d{6})\b")
LEG = re.compile(r"idLegislaturaElegida=(\d+)")
SESSION = re.compile(r"idOrgano=(\d+)&(?:amp;)?idSesion=(\d+)")
TIME = re.compile(r"(\d{1,2}):(\d{2})")
# The links' own words, which say nothing about the business.
BOILER = re.compile(r"\s*\b(?:Ver directo|YouTube|Nota de prensa|Ver acta del \S+)\s*\.?", re.I)


def text_of(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment or "")
    return " ".join(html.unescape(t).replace(" ", " ").split())


def legislature(date, page):
    m = LEG.search(page or "")
    if m:
        return int(m.group(1))
    return 16 if (date or "") >= XVI_CONVENES else 15


def kind_of(text):
    low = text.lower()
    if low.startswith(("pleno", "sesión plenaria", "sesion plenaria")):
        return "plenary"
    if low.startswith(("comisión", "comision", "subcomisión", "ponencia")):
        return "committee"
    if low.startswith("diputación permanente") or low.startswith("diputacion permanente"):
        return "plenary"
    return "other"


def parse_week(page):
    """Points from one week's page."""
    out = []
    heads = list(DAY_HEAD.finditer(page or ""))
    for i, h in enumerate(heads):
        try:
            date = datetime.date(int(h.group(3)), MONTHS.index(h.group(2).lower()) + 1,
                                 int(h.group(1))).isoformat()
        except ValueError:
            continue
        stop = heads[i + 1].start() if i + 1 < len(heads) else len(page)
        for n, tr in enumerate(TR.findall(page[h.end():stop]), 1):
            cells = TD.findall(tr)
            if len(cells) < 2:
                continue
            divs = [text_of(d) for d in DIVS.findall(cells[1])] or [text_of(cells[1])]
            text = BOILER.sub("", divs[0]).strip(" .")
            if not text or text.lower().startswith("sin convocatoria"):
                continue
            text += "."
            place = divs[1] if len(divs) > 1 else None
            t = TIME.search(text_of(cells[0]))
            time = "{0:02d}:{1}".format(int(t.group(1)), t.group(2)) if t else None
            body = text.split(".")[0].strip()[:120] or None
            leg = legislature(date, tr)
            refs = ["{0}/{1}".format(leg, x) for x in EXP.findall(text)]
            s = SESSION.search(tr)
            item_id = ("{0}-org{1}-s{2}".format(date, s.group(1), s.group(2)) if s
                       else "{0}-{1}-{2}".format(date, time or "x", n))
            link = re.search(r'href="(https://www\.congreso\.es/actualidad/sesiones[^"]+)"', tr)
            out.append(agenda.point(item_id, date, text, body, kind_of(text), time, place,
                                    refs=refs, url=html.unescape(link.group(1)) if link else None))
    return out


def weeks(today, days):
    """The Monday of each week the window touches."""
    d = datetime.date.fromisoformat(today)
    end = d + datetime.timedelta(days=days)
    monday = d - datetime.timedelta(days=d.weekday())
    out = []
    while monday <= end:
        out.append(monday)
        monday += datetime.timedelta(days=7)
    return out


def fetch(client, today, days, log=print):
    end = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    points, gaps = [], []
    for monday in weeks(today, days):
        try:
            page = client.get_text(WEEK.format(d=monday.day, m=monday.month, y=monday.year),
                                   FEED, "semana-{0}".format(monday.isoformat()),
                                   headers=ACCEPT)
        except FetchError as exc:
            gaps.append("week of {0} unreadable: {1}".format(monday, str(exc)[:80]))
            continue
        points += [p for p in parse_week(page) if today <= p["date"] <= end]
    plenary = sorted(p["date"] for p in points if p["kind"] == "plenary")
    note = None
    if today < XVI_CONVENES:
        note = "The Cortes are dissolved; the XVI legislature convenes on 23 December 2026"
    return agenda.fetched(points, next_sitting=plenary[0] if plenary else None, note=note,
                          gaps=gaps)
