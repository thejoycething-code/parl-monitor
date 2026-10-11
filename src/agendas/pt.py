"""Portugal: the Assembleia da República's agenda (agenda.parlamento.pt).

The Agenda Parlamentar is a public calendar with no sign-in. Its calendar
handler answers a plain GET with JSON, one event per meeting, for a section
and a date range:

    /Index?handler=Calendar&Start=<date>&End=<date>&SectionId=<id>&Text=

Sections read: 4 the Plenário (each sitting's ORDEM DO DIA), 1 the Comissão
Permanente, 7 the committees (each meeting's ordem de trabalhos). An
event's `text` is the agenda as HTML; an initiative is printed as
'Projeto de Lei n.º 623/XVII/1.ª (PSD)' and linked to its page
(DetalheIniciativa.aspx?BID=356395, BID being the Assembleia's IniId).
Measured 11 October 2026: 6 plenary sittings from 14 to 28 October (the
sitting of 15 October takes three initiatives on medically assisted
procreation), 33 committee meetings in the next week. The site's Friendly
Captcha guards only its newsletter form; the calendar is not behind it.

One point per numbered item of the agenda ('1 - ...', '2. ...', 'A. ...',
or an HTML list item);
in an agenda with no numbered item, one per paragraph (a rapporteur, an
hour or a sub-list line stays with the paragraph above). A point's refs are
initiative keys ('XVII/J/623', the keys of pt_initiatives and
config/watchlist-pt.yaml) from the printed numbers, and the linked IniIds,
which `resolve` maps to keys through pt_initiatives.ini_id. Speaking-time
tables (lines like 'PSD', '6 m') are left out of the words kept.
"""

from __future__ import annotations

import datetime
import html
import re

from src import agenda
from src.http import FetchError

CC = "pt"
SOURCE = "the Assembleia's Agenda Parlamentar"
BILLS = ("pt_initiatives", "ini_key", "title")
FEED = "pt-agenda"
HOST = "https://agenda.parlamento.pt"
CALENDAR = HOST + "/Index?handler=Calendar&Start={0}&End={1}&SectionId={2}&Text="
SECTIONS = ((4, "plenary"), (1, "plenary"), (7, "committee"))
WEB = HOST + "/"

# The Assembleia's IniTipo letters by the words the agenda prints.
TYPES = (("projeto de lei", "J"), ("proposta de lei", "P"),
         ("projeto de resolução", "R"), ("proposta de resolução", "S"),
         ("projeto de deliberação", "D"), ("projeto de resolucao", "R"))
INI = re.compile(r"(Projeto de Lei|Proposta de Lei|Projeto de Resolu[çc][ãa]o|"
                 r"Proposta de Resolu[çc][ãa]o|Projeto de Delibera[çc][ãa]o)\s+(?:n\.?\s*[ºo°]\s*)?"
                 r"(\d+)\s*/\s*([IVXL]+)", re.I)
BID = re.compile(r"DetalheIniciativa\.aspx\?BID=(\d+)", re.I)
ITEM = re.compile(r"^(?:\d{1,2}\s*[-–.)]|[A-Z]\s*[.)–-]|Parte\s+[IVX]+\s*[-–:]?)\s+")
CONT = re.compile(r"^(?:Relator|Relatora|Deputad|Autor|Indica[çc][ãa]o|[-–•]|[a-z]\)|"
                  r"\d{1,2}h\d{0,2}|[a-zà-ú])")
SHORT = 14          # speaking-time table cells ('PSD* **', '6 m', 'Subtotal')


def lines_of(fragment):
    t = re.sub(r"(?i)<li[^>]*>", "\n1. ", fragment or "")      # a list item is an item
    t = re.sub(r"(?i)</p>|<br\s*/?>|</tr>|</li>|</h\d>", "\n", t)
    t = re.sub(r"(?i)<a[^>]*BID=(\d+)[^>]*>", r" [[BID=\1]] ", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " ")
    return [" ".join(x.split()) for x in t.split("\n") if x.strip()]


def type_letter(words):
    low = words.lower()
    for k, v in TYPES:
        if low.startswith(k):
            return v
    return None


def refs_of(text):
    refs = []
    for words, num, leg in INI.findall(text):
        letter = type_letter(words)
        if letter:
            refs.append("{0}/{1}/{2}".format(leg.upper(), letter, int(num)))
    refs += ["bid:{0}".format(b) for b in re.findall(r"\[\[BID=(\d+)\]\]", text)]
    return refs


def clean(text):
    return " ".join(re.sub(r"\[\[BID=\d+\]\]", " ", text).split())


def parse_event(ev, kind):
    """Points from one calendar event."""
    x = ev.get("extendedProps") or {}
    start = ev.get("start") or ""
    date, time = start[:10] or None, start[11:16] or None
    plenary = kind == "plenary"
    section = x.get("sectionName") or ""
    if plenary:
        body = "Plenário" if "Permanente" not in section else "Comissão Permanente"
    else:
        body = ev.get("title") or section or "Comissão"
    meeting = " ".join(y for y in (body, x.get("subtitle")) if y)
    lines = [ln for ln in lines_of(x.get("text")) if len(clean(ln)) > SHORT or "[[BID" in ln]
    lines = [ln for ln in lines if clean(ln).upper() not in ("ORDEM DO DIA", "ORDEM DE TRABALHOS")]
    groups, cur = [], None
    for ln in lines:
        if ITEM.match(clean(ln)) or cur is None:
            cur = []
            groups.append(cur)
        cur.append(ln)
    if not any(ITEM.match(clean(g[0])) for g in groups):
        # No numbered items: each paragraph is a point, a speaker, a
        # rapporteur, an hour or a sub-list line staying with the one above.
        groups = []
        for ln in lines:
            if groups and CONT.match(clean(ln)):
                groups[-1].append(ln)
            else:
                groups.append([ln])
    out = []
    for n, g in enumerate(groups, 1):
        words = [clean(ln) for ln in g if clean(ln)]
        if not words:
            continue
        title = ITEM.sub("", words[0]).strip() or words[0]
        if INI.match(title) and len(words) > 1:      # the number, then its title
            title = "{0}: {1}".format(title, words[1])
            rest = words[2:]
        else:
            rest = words[1:]
        while len(title) < 20 and rest:                # 'Parte II - 11h30', then the business
            title = "{0} {1}".format(title, rest.pop(0))
        detail = " ".join(rest)[:1500] or None
        out.append(agenda.point("{0}-{1}".format(ev.get("id"), n), date, title, meeting,
                                kind, time, detail, refs=refs_of(" ".join(g)), url=WEB))
    if not out and (ev.get("title") or section):
        out.append(agenda.point("{0}-0".format(ev.get("id")), date, ev.get("title") or section,
                                meeting, kind, time, url=WEB))
    return out


def resolve(conn, refs):
    """'bid:356395' (the IniId the agenda links) to its pt_initiatives key."""
    out = []
    for r in refs:
        if not r.startswith("bid:"):
            continue
        try:
            got = conn.execute("SELECT ini_key FROM pt_initiatives WHERE ini_id = ?",
                               (int(r[4:]),)).fetchone()
        except Exception:                          # noqa: BLE001 - table missing
            return out
        if got and got[0]:
            out.append(got[0])
    return out


def fetch(client, today, days, log=print):
    end = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    points, gaps, sittings = [], [], []
    for section, kind in SECTIONS:
        try:
            reply = client.get_json(CALENDAR.format(today, end, section), FEED,
                                    "calendar-{0}-s{1}".format(today, section))
        except (FetchError, ValueError) as exc:
            gaps.append("section {0} unreadable: {1}".format(section, str(exc)[:100]))
            continue
        for ev in reply or []:
            date = (ev.get("start") or "")[:10]
            if not date or not (today <= date <= end):
                continue
            if kind == "plenary":
                sittings.append(date)
            points += parse_event(ev, kind)
    sittings.sort()
    note = None if sittings else "No plenary sitting is scheduled in the weeks read"
    return agenda.fetched(points, next_sitting=sittings[0] if sittings else None, note=note,
                          gaps=gaps)
