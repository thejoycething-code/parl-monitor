"""Argentina: the Senate's agenda of activities.

`www.senado.gob.ar/parlamentario/Agenda/AgendaWeb/<d>,<m>,<yyyy>` is plain
HTML (docs/argentina-scope.md, "Agendas"): the page for a day shows that
whole week, a heading per day ('Martes 13 de octubre') and a block per
event ('14:00 h - Reunión de la Comisión ...') with its Temario. Committee
meetings, sessions and cultural events share the list; only the
classification decides what reaches the edition. One page a week; measured
10 October 2026: 12 events in the week of 12 October, two committee
meetings with a Temario.

Expedientes named in a Temario become store keys: Senate 'S-1234/26' or
'1234-S-2026' -> 'sen/1234-S-2026', Diputados '1234-D-2026' ->
'dip/1234-D-2026' (ar_bills, config/watchlist-ar.yaml).

The Chamber of Deputies' committee agenda (www.hcdn.gob.ar) is not read
here: AR4 lets the scheduled monitor read that host, but no session probed
its agenda pages for this step, and its robots.txt names Claude agents.
"""

from __future__ import annotations

import datetime
import html
import re

from src import agenda
from src.http import FetchError

CC = "ar"
SOURCE = "the Senate's agenda of activities"
BILLS = ("ar_bills", "exp_key", "title")
FEED = "ar-agenda"
HOST = "https://www.senado.gob.ar"
WEEK = HOST + "/parlamentario/Agenda/AgendaWeb/{d},{m},{y}"
MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")

DAY = re.compile(r"(?i)\b(?:lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|"
                 r"domingo)\s+(\d{1,2})\s+de\s+(\w+)")
EVENT = re.compile(r'(?s)<div class="mods agendaCulturales[^"]*" id="(\d+)"[^>]*>(.*?)'
                   r'(?=<div class="mods agendaCulturales|\Z)')
HEAD = re.compile(r'(?s)<span class="textReg16_blueTit2">\s*(.*?)</span>')
CNT = re.compile(r'(?s)<div class="cnt"[^>]*>(.*)')
EXP_A = re.compile(r"\b(S|PE|CD|OV|P|D)\s*-?\s*(\d{1,5})\s*/\s*(\d{2,4})\b")
EXP_B = re.compile(r"\b(\d{1,5})\s*-\s*(S|PE|CD|OV|P|D)\s*-\s*(\d{4})\b")


def text_of(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment or "")
    return " ".join(html.unescape(t).replace("﻿", "").replace(" ", " ").split())


def exp_key(origin, number, year):
    year = int(year)
    if year < 100:                       # 'PE 854/97' is 1997, 'S-1234/26' 2026
        year += 2000 if year <= 60 else 1900
    chamber = "dip" if origin == "D" else "sen"
    return "{0}/{1}-{2}-{3}".format(chamber, int(number), origin, year)


def refs_of(text):
    out = [exp_key(o, n, y) for o, n, y in EXP_A.findall(text)]
    out += [exp_key(o, n, y) for n, o, y in EXP_B.findall(text)]
    return out


def parse_week(page, year):
    """Points from one week page: every event under its day."""
    out = []
    marks = []                                    # (offset, iso date)
    # Day headings sit in their own <p><span>; find them in the raw page so
    # offsets line up with the event blocks.
    for m in re.finditer(r"(?s)<span[^>]*>\s*([^<]{4,40}?\d{1,2}\s+de\s+[^<]{3,30}?)\s*</span>",
                         page or ""):
        d = DAY.search(" ".join(html.unescape(m.group(1)).split()))
        if not d or d.group(2).lower() not in MONTHS:
            continue
        try:
            iso = datetime.date(year, MONTHS.index(d.group(2).lower()) + 1,
                                int(d.group(1))).isoformat()
        except ValueError:
            continue
        marks.append((m.start(), iso))
    for ev in EVENT.finditer(page or ""):
        before = [iso for off, iso in marks if off < ev.start()]
        if not before:
            continue
        date = before[-1]
        head = HEAD.search(ev.group(2))
        heading = text_of(head.group(1)) if head else ""
        if not heading or heading == "TITULO":
            continue
        t = re.match(r"(\d{1,2}):(\d{2})", heading)
        time = "{0:02d}:{1}".format(int(t.group(1)), t.group(2)) if t else None
        title = re.sub(r"^[\d:]+(?:\s*(?:a|y)\s*[\d:]+)?\s*h\s*-\s*", "", heading)
        cnt = CNT.search(ev.group(2))
        body_text = text_of(cnt.group(1)) if cnt else ""
        temario = body_text.split("Lugar:")[0].strip() or None
        kind = ("committee" if "comisi" in title.lower() else
                "plenary" if "sesi" in title.lower() else "other")
        if kind == "other":
            continue          # guided visits, concerts, balcony lights: not business
        # A committee is classified on its Temario alone: its name ('Relaciones
        # Exteriores y Culto') is not its business.
        out.append(agenda.point(ev.group(1), date, title, "Senado, " + (
            "committee" if kind == "committee" else "session"),
            kind, time, temario, refs=refs_of(temario or ""),
            url=WEEK.format(d=int(date[8:]), m=int(date[5:7]), y=date[:4]),
            text=(temario or "") if kind == "committee" else None))
    return out


def fetch(client, today, days, log=print):
    d = datetime.date.fromisoformat(today)
    end = d + datetime.timedelta(days=days)
    monday = d - datetime.timedelta(days=d.weekday())
    points, gaps = [], []
    while monday <= end:
        try:
            page = client.get_text(WEEK.format(d=monday.day, m=monday.month, y=monday.year),
                                   FEED, "semana-{0}".format(monday.isoformat()))
            points += [p for p in parse_week(page, monday.year)
                       if today <= p["date"] <= end.isoformat()]
        except FetchError as exc:
            gaps.append("week of {0} unreadable: {1}".format(monday, str(exc)[:80]))
        monday += datetime.timedelta(days=7)
    sessions = sorted(p["date"] for p in points if p["kind"] == "plenary")
    return agenda.fetched(points, next_sitting=sessions[0] if sessions else None, gaps=gaps)
