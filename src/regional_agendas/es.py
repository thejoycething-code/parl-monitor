"""Spain: the seventeen autonomous-community parliaments' forward business
(16 October 2026; src/regional_agenda.py is the interface,
docs/spain-regions-scope.md "Forward agenda" has every measurement).

The past half (tools/es_regions.py) reads laws from the BOE and four bill
lists; this module reads what each parliament has BOOKED: the weekly agenda,
the order of the day of each plenary and committee sitting, and the session
calendar of the period (a booked date with no order of the day yet is one
'to be announced' item). Region codes are tools/es_regions.py's
(src/es_regions_store.PARLIAMENTS), so the renderer can join the two.

Read (seven), all HTML or CSV, robots.txt read first, honest user agent:

  an  Parlamento de Andalucía: the weekly agenda (agendasemanal.do?id=N,
      every sitting with its numbered initiatives, '13-26/PNLC-000012') and
      the calendar of sessions by month (calendariodesesiones.do?fec=mes
      año, the Mesa's programme to December), ISO-8859-1.
  ct  Parlament de Catalunya: the agenda's month view filtered to sittings
      (p_categoria=SESSIO&p_mode=M), each sitting's 'Ordre del dia' page
      (numbered points with the 'Tram.' expediente) and the plenary annual
      calendar ('previst' days = planned plenaries). Catalan only:
      classified with config/taxonomy-ca.yaml (tools/es_regions.load_catalan's
      list). ISO-8859-1.
  vc  Corts Valencianes: the agenda list filtered to the parliamentary
      calendar (field_taxon_type_target_id=6), read in its SPANISH version
      (/es/actividad/actualidad/agenda), and each sitting's page with the
      convocation's numbered order of the day.
  cl  Cortes de Castilla y León: /Agenda/Semana?Fecha=DD-MM-YYYY (one page a
      week), each sitting's /Agenda/Evento page ('Orden del día'), and the
      plenary calendar (/Actividad/PlenosPrevistos, red cells). robots.txt
      disallows '/*agenda.do*' and '/*agenda.html*', not these paths.
  cn  Parlamento de Canarias: the period's calendar of plenaries and
      committees (/actividad/calendario/), the convened sittings
      (/reuniones/futuras.py) and each one's order of the day
      (/reuniones/asuntos.py?ID_SESION=N). robots.txt Crawl-delay 3.
  ar  Cortes de Aragón: this week's and next week's agenda
      (Semana-actual.2237.0.html, Proxima-semana.2335.0.html, realurl paths:
      robots.txt disallows '/*?id=*', so never index.php?id=), each sitting's
      'Acto programado' page, and the plenary calendar CSV the site's own
      page loads (/fileadmin/_DMZMedia/comunicacion/web/varios/calendario.csv).
  cb  Parlamento de Cantabria: /agenda-semana?date=YYYY-MM-DD, one page a
      week with each sitting's order of the day inline.

Not read (each says why on every run): Madrid (Sucuri firewall), Galicia
(Akamai 403), Navarra (Cloudflare challenge), Asturias (a "Voight-Kampff"
browser test since October 2026), Castilla-La Mancha (the agenda is an
iframe of /web2/paginas/calendario.php, which robots.txt disallows), Murcia
and Extremadura (robots.txt disallows everything), País Vasco and Illes
Balears (no answer from the laptop), La Rioja (the plenary calendar is an
encrypted PDF, the iCal export answers 500 and session pages carry the
attendance, not an order of the day).

Bodies: plenaries are 'Pleno' (Catalonia's 'Ple' too); committees keep the
parliament's own name ('Comisión de Educación', 'Comissió de la Infància',
'Ponència: Proposició de llei ...'). The Mesa, the Junta de Portavoces,
press conferences and institutional events are not business and are left
out. A sitting's meeting_id is '<date>:<body slug>', so a calendar
placeholder and the order of the day that replaces it share it.
"""

from __future__ import annotations

import csv
import datetime
import html as _html
import io
import re
import urllib.parse

from src import regional_agenda as ra
from src.http import FetchError

CC = "es"
TAXONOMIES = (("taxonomy-es.yaml", "es"),)
CATALAN = "taxonomy-ca.yaml"     # tools/es_regions.TAXONOMY_CA, the same list
THROTTLES = {"www.parcan.es": 3.0}
FEED = ra.feed(CC)

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")
MESOS = {"gener": 1, "febrer": 2, "març": 3, "marc": 3, "abril": 4, "maig": 5, "juny": 6,
         "juliol": 7, "agost": 8, "setembre": 9, "octubre": 10, "novembre": 11,
         "desembre": 12}


# --- shared helpers -------------------------------------------------------------

def decode(raw):
    """Bytes to text by the page's own charset declaration (several of these
    sites are ISO-8859-1); UTF-8 otherwise."""
    if isinstance(raw, str):
        return raw
    head = raw[:2000].decode("ascii", errors="replace").lower()
    m = re.search(r"""encoding=["']([\w-]+)["']|charset=["']?([\w-]+)""", head)
    enc = (m.group(1) or m.group(2)) if m else "utf-8"
    try:
        return raw.decode(enc)
    except (LookupError, UnicodeDecodeError):
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("iso-8859-1")


def fetch(client, url, slug, **kw):
    return decode(client.get_bytes(url, FEED, slug, **kw))


def text(fragment):
    """One line of plain text from an HTML fragment."""
    return ra.one_line(_html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")))


def no_comments(page):
    return re.sub(r"(?s)<!--.*?-->", " ", page or "")


_SMALL = {"de", "del", "la", "las", "el", "los", "y", "e", "o", "u", "a", "en", "con", "para",
          "por", "sus", "su", "al"}


def title_case(name):
    """'COMISIÓN DE EDUCACIÓN' -> 'Comisión de Educación' (only for names
    printed in capitals)."""
    if not name or name != name.upper():
        return name
    words = name.lower().split()
    return " ".join(w if (i and w in _SMALL) else w[:1].upper() + w[1:]
                    for i, w in enumerate(words))


_PLENO = re.compile(r"^(?:pleno|ple)\b", re.I)
_SKIP = re.compile(
    r"^(?:mesa\b|junta de portav|rueda|ruedas de prensa|conferència de premsa|conferencia de prensa|"
    r"la presidenta|el presidente|el president|la president|presidencia|presidència|"
    r"iluminaci|visita|acto|jornada|intergrup|reuni[óo]n|reunió|recepci|entrega|"
    r"lectura de|concierto|exposici)", re.I)


def body_name(name):
    """The body as stored: plenaries 'Pleno', committees as published."""
    name = title_case(ra.one_line(name)).strip(" .")
    if _PLENO.match(name):
        return "Pleno"
    return name


def is_business_body(name):
    """A plenary, committee, ponencia, subcommittee or the standing
    deputation; not the Mesa, the Junta de Portavoces or an event."""
    n = ra.one_line(name)
    if not n or _SKIP.match(n):
        return False
    return bool(re.match(r"(?i)^(?:pleno|ple\b|comisi[óo]n|comissi[óo]|ponencia|ponència|"
                         r"subcomisi|subcomissi|diputaci[óo]n? permanent|diputació permanent|"
                         r"grupo de trabajo|grup de treball|comisiones)", n))


def mid(dated, body):
    return "{0}:{1}".format(dated, ra.slug(body, 40))


_PRESENTADA = re.compile(
    r",?\s*(?:presentad[ao]s?|formulad[ao]s?|present(?:at|ada)) (?:per|por) "
    r"(?:(?!,\s*(?:instando|relativa|relativo|sobre|para|con el fin|a fin)\b).)*", re.I)
_TAIL = re.compile(r"(?:,\s*publicad[ao] en el Bolet[íi]n Oficial.*$|\s+B BOPCA n.*$|"
                   r"\.?\s+A propuesta de.*$|"
                   r"\s*\(RE n[úu]mero[^)]*\)\.?$)", re.I)


def short(business):
    """The point without the proponents' names and the bulletin reference:
    the full text goes in detail."""
    b = ra.one_line(business)
    s = _TAIL.sub("", b)
    s = _PRESENTADA.sub("", s).strip(" ,.;")
    s = re.sub(r"\s+E \[[^\]]+\]\.?$", "", s)
    s = re.sub(r"\s+E \[([^\]]+)\]", r" \1", s).strip(" ,.;")
    return s if len(s) >= 12 else b


def merge(detailed, placeholders):
    """Calendar placeholders, less those whose sitting has its order of the
    day (same date and body) among the detailed items."""
    have = {(it["dated"], ra.slug(it["body"], 40)) for it in detailed}
    seen, out = set(), []
    for it in placeholders:
        k = (it["dated"], ra.slug(it["body"], 40))
        if k in have or k in seen:
            continue
        seen.add(k)
        out.append(it)
    return list(detailed) + out


def months_between(start, end):
    """(year, month) for every month from start to end (ISO dates)."""
    y, m = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    out = []
    while (y, m) <= (ey, em):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def last_day(y, m):
    nxt = datetime.date(y + (m == 12), 1 if m == 12 else m + 1, 1)
    return (nxt - datetime.timedelta(days=1)).isoformat()


def monday(iso_date):
    d = datetime.date.fromisoformat(iso_date)
    return d - datetime.timedelta(days=d.weekday())


def numbered_points(lines):
    """[(order, text)] from lines '1. Text' / '1 Text', following
    continuation lines ('- A petición de ...') onto the point."""
    out = []
    for line in lines:
        line = ra.one_line(line)
        if not line:
            continue
        m = re.match(r"^(\d{1,2})\s*[.)-]?\s+(\S.*)$", line)
        if m:
            out.append([int(m.group(1)), m.group(2)])
        elif out:
            out[-1][1] += " " + line
    return [(n, t) for n, t in out]


# --- Andalucía -------------------------------------------------------------------

AN = "https://www.parlamentodeandalucia.es/webdinamica/portal-web-parlamento/actividadparlamentaria/"
AN_INDEX = AN + "agendasemanal.do"
AN_WEEK = AN + "agendasemanal.do?id={0}&numsemana={0}"
AN_CAL = AN + "calendariodesesiones.do"
AN_CAL_MONTH = AN + "calendariodesesiones.do?fec={0}%20{1}"


def parse_an_index(page, today):
    """[(id, title)] of the published weekly agendas still running or ahead:
    'AGENDA DEL 12 AL 16 DE OCTUBRE' (no year: the nearest one is taken)."""
    out = []
    t = datetime.date.fromisoformat(today)
    for aid, title in re.findall(r'href="agendasemanal\.do\?id=(\d+)&(?:amp;)?numsemana=\d+">([^<]+)</a>',
                                 page):
        m = re.search(r"AL\s+(\d{1,2})\s+DE\s+([A-ZÁÉÍÓÚa-záéíóú]+)", title, re.I)
        if not m or not ra.month(m.group(2)):
            continue
        mo, d = ra.month(m.group(2)), int(m.group(1))
        end = None
        for y in (t.year - 1, t.year, t.year + 1):
            try:
                cand = datetime.date(y, mo, d)
            except ValueError:
                continue
            if end is None or abs((cand - t).days) < abs((end - t).days):
                end = cand
        if end and end >= t:
            out.append((aid, ra.one_line(title)))
    return out


def parse_an_week(page, url=None):
    """Items of one weekly agenda: a sitting per '<strong class="h4">', its
    date from the anchor before it, its points from the <li> list."""
    page = no_comments(page)
    items = []
    marks = [(m.start(), m.group(1)) for m in re.finditer(r'<a name="(\d{4}-\d{2}-\d{2})"', page)]
    heads = list(re.finditer(r'<p class="mt-3">\s*<strong class="h4">(.*?)</strong>', page, re.S))
    for i, h in enumerate(heads):
        dated = None
        for pos, d in marks:
            if pos < h.start():
                dated = d
        raw_body = text(h.group(1))
        if not dated or not is_business_body(raw_body):
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(page)
        block = page[h.end():end]
        tm = re.search(r"<strong>Hora</strong>:\s*\d{4}-\d{2}-\d{2} (\d{2}:\d{2})", block)
        body = body_name(raw_body)
        meeting = mid(dated, body)
        heading, n = "", 0
        for li in re.findall(r"<li class='sindibujo'>(.*?)</li>", block, re.S):
            line = text(li)
            if not line:
                continue
            ref = re.search(r"numexp=([\w/-]+)", li)
            if line.endswith(":") and not ref:
                if not line.lower().startswith("debate agrupado"):
                    heading = line.rstrip(":")
                continue
            if re.match(r"^\d{1,2}:\d{2} horas$", line):
                continue
            n += 1
            point = re.sub(r"^-\s*", "", line)
            if ref:
                point = point.replace(ref.group(1), "").strip(" ,")
            business = "{0}: {1}".format(heading, point) if heading else point
            items.append(ra.item(dated, short(business), body, tm.group(1) if tm else None, n,
                                 meeting, detail=business, reference=ref.group(1) if ref else None,
                                 url=url))
        if n == 0:
            items.append(ra.item(dated, "", body, tm.group(1) if tm else None,
                                 meeting_id=meeting, url=url))
    return items


def parse_an_calendar_months(page):
    """[(year, month)] the calendar page offers ('fec=noviembre 2026')."""
    out = []
    for name, y in re.findall(r'calendariodesesiones\.do\?fec=([a-záéíóú]+)(?:\s|%20)(\d{4})', page):
        mo = ra.month(name)
        if mo and (int(y), mo) not in out:
            out.append((int(y), mo))
    return out


def parse_an_calendar(page, year, month, url=None):
    """Placeholders (or a subject in brackets) from one month of the
    calendar of sessions: plenaries and committees only."""
    items = []
    for day, cell in re.findall(r'<th scope="row">\s*(\d{1,2})\s*[^<]*</th>\s*<td[^>]*>(.*?)</td>',
                                page, re.S):
        dated = ra.iso(day, month, year)
        lines = [text(x) for x in re.findall(r"<li[^>]*>(.*?)</li>", cell, re.S)]
        for i, line in enumerate(lines):
            if not line or line.startswith("("):
                continue
            m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", line)
            name, subject = (m.group(1), m.group(2)) if m else (line, "")
            if not subject and i + 1 < len(lines) and lines[i + 1].startswith("("):
                subject = lines[i + 1].strip("() ")
            if re.match(r"(?i)^comparecencias", name):
                name, subject = "Comisiones", name
            if not is_business_body(name):
                continue
            body = body_name(name)
            items.append(ra.item(dated, subject, body, meeting_id=mid(dated, body), url=url))
    return items


def read_an(client, ctx):
    gaps, detailed, cal = [], [], []
    index = fetch(client, AN_INDEX, "an-agenda-index")
    for aid, title in parse_an_index(index, ctx.today):
        url = AN_WEEK.format(aid)
        try:
            detailed += parse_an_week(fetch(client, url, "an-agenda-" + aid), url)
        except FetchError as e:
            gaps.append("Andalucía weekly agenda {0}: {1}".format(title, str(e.cause)[:120]))
    offered = parse_an_calendar_months(fetch(client, AN_CAL, "an-calendar"))
    covered = None
    for y, m in months_between(ctx.today, ctx.until):
        if (y, m) not in offered or ctx.out_of_time():
            break
        url = AN_CAL_MONTH.format(MESES[m - 1], y)
        try:
            page = fetch(client, url, "an-calendar-{0}-{1:02d}".format(y, m))
        except FetchError as e:
            gaps.append("Andalucía calendar {0}-{1:02d}: {2}".format(y, m, str(e.cause)[:120]))
            break
        cal += parse_an_calendar(page, y, m, url)
        covered = min(last_day(y, m), ctx.until)
    items = [it for it in merge(detailed, cal) if ctx.in_window(it["dated"])]
    units = [ra.window(ctx.today, covered)] if covered and not gaps else []
    return ra.RegionRead(items, units, source="weekly agenda and calendar of sessions",
                         gaps=gaps)


# --- Cataluña ----------------------------------------------------------------------

CT = "https://www.parlament.cat"
CT_MONTH = CT + "/web/actualitat/agenda/index.html?p_categoria=SESSIO&p_hr=AGENDA&p_organ=&p_mode=M&p_data={0:02d}{1:02d}{2}"
CT_ANNUAL = CT + "/web/composicio/ple-parlament/calendari-anual/index.html"


def ca_month(name):
    n = ra._fold((name or "").strip(" .").lower())
    for k, v in MESOS.items():
        if ra._fold(k) == n:
            return v
    return None


def parse_ct_month(page):
    """Sittings of one month view: [{dated, time, body, od_url, cancelled}]."""
    head = re.search(r'<h2 class="titol_caixa"><span>\s*([^<\s]+) de (\d{4})', page)
    if not head or not ca_month(head.group(1)):
        return []
    month, year = ca_month(head.group(1)), int(head.group(2))
    out = []
    parts = re.split(r'<h3 class="sub_titol_caixa"><span>[^,<]*,\s*(\d{1,2})</span></h3>', page)
    for i in range(1, len(parts) - 1, 2):
        dated = ra.iso(parts[i], month, year)
        for ev in re.findall(r'<th rowspan="2" class="hora_lloc"[^>]*>(.*?)</td></tr>\s*<tr><td class="tema_acte">(.*?)</td></tr>',
                             parts[i + 1], re.S):
            head_html, rest = ev
            tm = re.search(r"(\d{1,2}:\d{2})h", head_html)
            name = re.search(r"<strong>(.*?)</strong>", head_html, re.S)
            od = re.search(r'href="(/web/actualitat/ordre-dia/index\.html\?p_od0=\d+)[^"]*"', rest)
            out.append({"dated": dated, "time": tm.group(1) if tm else None,
                        "name": text(name.group(1)) if name else "",
                        "od_url": CT + _html.unescape(od.group(1)) if od else None,
                        "cancelled": "Desconvocat" in rest})
    return out


def parse_ct_order(page):
    """[(order, business, reference)] of one 'Ordre del dia' page."""
    out = []
    for n, body in re.findall(r'<li><strong class="punt_ordre">(\d+)</strong>\s*<div[^>]*>(.*?)</div></li>',
                              page, re.S):
        paras = re.findall(r"<p>(.*?)</p>", body, re.S)
        if not paras:
            continue
        first = text(paras[0])
        ref = re.search(r"\(Tram\.\s*([\w/-]+)\s*\)", first)
        business = re.sub(r"\s*\(Tram\.[^)]*\)\s*$", "", first).strip()
        out.append((int(n), business, ref.group(1) if ref else None))
    return out


def parse_ct_annual(page, year=None):
    """Planned plenary days ('previst') of the annual calendar: ISO dates."""
    yr = re.search(r'<p class="any_mes">(\d{4})</p>', page)
    year = year or (int(yr.group(1)) if yr else None)
    out = []
    for name, table in re.findall(r"summary=\"Agenda d'esdeveniments ([^\"]+)\">(.*?)</table>", page, re.S):
        mo = ca_month(name)
        if not mo or not year:
            continue
        for day in re.findall(r'<td class="previst"><span>(\d{1,2})</span>', table):
            out.append(ra.iso(day, mo, year))
    return [d for d in out if d]


def read_ct(client, ctx):
    gaps, detailed, cal = [], [], []
    covered = None
    for y, m in months_between(ctx.today, ctx.until):
        url = CT_MONTH.format(1, m, y)
        try:
            page = fetch(client, url, "ct-agenda-{0}-{1:02d}".format(y, m))
        except FetchError as e:
            if covered is None:
                raise
            gaps.append("Cataluña agenda {0}-{1:02d}: {2}".format(y, m, str(e.cause)[:120]))
            break
        covered = min(last_day(y, m), ctx.until)
        for ev in parse_ct_month(page):
            if ev["cancelled"] or not ctx.in_window(ev["dated"]) or not is_business_body(ev["name"]):
                continue
            body = body_name(ev["name"])
            meeting = mid(ev["dated"], body)
            points = []
            if ev["od_url"] and not ctx.out_of_time():
                try:
                    points = parse_ct_order(fetch(client, ev["od_url"], "ct-ordre-" +
                                                  ev["od_url"].rsplit("=", 1)[-1]))
                except FetchError as e:
                    gaps.append("Cataluña order of the day {0} {1}: {2}".format(
                        ev["dated"], body[:40], str(e.cause)[:100]))
            for n, business, ref in points:
                detailed.append(ra.item(ev["dated"], business, body, ev["time"], n, meeting,
                                        reference=ref, url=ev["od_url"]))
            if not points:
                detailed.append(ra.item(ev["dated"], "", body, ev["time"], meeting_id=meeting,
                                        url=ev["od_url"] or url))
    try:
        for d in parse_ct_annual(fetch(client, CT_ANNUAL, "ct-calendari-anual")):
            cal.append(ra.item(d, "", "Pleno", meeting_id=mid(d, "Pleno"), url=CT_ANNUAL))
    except FetchError as e:
        gaps.append("Cataluña plenary annual calendar: {0}".format(str(e.cause)[:120]))
    items = [it for it in merge(detailed, cal) if ctx.in_window(it["dated"])
             and it["dated"] <= covered]
    return ra.RegionRead(items, [ra.window(ctx.today, covered)],
                         source="agenda (sittings), orders of the day, plenary annual calendar",
                         gaps=gaps)


# --- Comunitat Valenciana -----------------------------------------------------------

VC = "https://www.cortsvalencianes.es"
VC_LIST = VC + "/es/actividad/actualidad/agenda?field_taxon_type_target_id=6"


def parse_vc_list(page):
    """[{dated, time, name, url}] of one page of the calendar list."""
    out = []
    for row in re.split(r'<div class="item-event views-row">', page)[1:]:
        a = re.search(r'<div class="item-title"><span><a href="([^"]+)">(.*?)</a>', row, re.S)
        d = re.search(r'item-day-simple">\s*(\d{1,2})\s*</div>\s*<div class="item-month-simple">\s*([^<]+?)\s*</div>\s*'
                      r'<div class="item-year-simple">\s*(\d{4})', row)
        tm = re.search(r'hms-format-h-mm">\s*(\d{1,2}:\d{2})', row)
        if not a or not d:
            continue
        out.append({"dated": ra.iso(d.group(1), d.group(2), d.group(3)),
                    "time": tm.group(1) if tm else None, "name": text(a.group(2)),
                    "url": VC + a.group(1) if a.group(1).startswith("/") else a.group(1)})
    return out


def parse_vc_detail(page):
    """[(order, text)] of the convocation's order of the day."""
    body = re.search(r'(?s)field--name-body.*', page)
    if not body:
        return []
    lines = ra.clean(body.group(0)).splitlines()
    start = [i for i, l in enumerate(lines) if re.search(r"orden del d[íi]a|ordre del dia", l, re.I)]
    if not start:
        return []
    kept = []
    for line in lines[start[0] + 1:]:
        if re.match(r"(?i)^(?:palau|palacio) de les corts", line):
            break
        kept.append(line)
    return numbered_points(kept)


def read_vc(client, ctx):
    gaps, items, done = [], [], False
    for page_no in range(4):
        url = VC_LIST + ("&page={0}".format(page_no) if page_no else "")
        rows = parse_vc_list(fetch(client, url, "vc-agenda-list-{0}".format(page_no)))
        if not rows:
            break
        for r in rows:
            if not ctx.in_window(r["dated"]) or not is_business_body(r["name"]):
                continue
            body = body_name(r["name"])
            meeting = mid(r["dated"], body)
            points = []
            if not ctx.out_of_time():
                try:
                    points = parse_vc_detail(fetch(client, r["url"], "vc-" + r["url"].rsplit("/", 1)[-1]))
                except FetchError as e:
                    gaps.append("Corts Valencianes {0} {1}: {2}".format(r["dated"], body[:40],
                                                                        str(e.cause)[:100]))
            for n, t in points:
                items.append(ra.item(r["dated"], short(t), body, r["time"], n, meeting,
                                     detail=t, url=r["url"]))
            if not points:
                items.append(ra.item(r["dated"], "", body, r["time"], meeting_id=meeting,
                                     url=r["url"]))
        if min(r["dated"] or "9" for r in rows) < ctx.today:
            done = True
            break
    units = [ra.window(ctx.today, ctx.until)] if done else []
    return ra.RegionRead(items, units, source="agenda (parliamentary calendar), Spanish version",
                         gaps=gaps)


# --- Castilla y León -----------------------------------------------------------------

CL = "https://www.ccyl.es"
CL_WEEK = CL + "/Agenda/Semana?Fecha={0:%d-%m-%Y}"
CL_PLENOS = CL + "/Actividad/PlenosPrevistos"


def parse_cl_week(page):
    """[{dated, time, name, refs, url}] of one weekly agenda page."""
    out = []
    for row in re.findall(r"(?s)<tr>(.*?)</tr>", page):
        d = re.search(r"cc_agd_evento\"[^>]*>\s*(\d{2}/\d{2}/\d{4})", row)
        name = re.search(r'<strong class="cc_agd_EventoTexto">(.*?)</strong>', row, re.S)
        if not d or not name:
            continue
        tm = re.search(r'cc_agd_EventoHora">\s*(\d{1,2}:\d{2})', row)
        ev = re.search(r'href="(/Agenda/Evento\?NumeroSerieId=\d+)"', row, re.I)
        refs = re.search(r'cc_agd_EventoLineaOds">(.*?)</span>', row, re.S)
        out.append({"dated": ra.find_date(d.group(1)), "time": tm.group(1) if tm else None,
                    "name": text(name.group(1)), "refs": text(refs.group(1)) if refs else "",
                    "url": CL + ev.group(1) if ev else None})
    return out


def parse_cl_event(page):
    """[(order, text, reference)] of an event page's 'Orden del día'."""
    m = re.search(r'(?s)<div class="cc_agd_ODSEvento">(.*?)(?:<!-- inciativas|<h4)', page)
    if not m:
        return []
    out = []
    for p in re.findall(r'(?s)<p class="cc_agd_EventoOdsPunto\w*">(.*?)</p>', m.group(1)):
        t = text(p)
        n = re.match(r"^(\d{1,2})\.\s*(.*)$", t)
        if not n:
            continue
        ref = re.search(r"\b([A-Z]{2,5}/\d{4,6})\b", n.group(2))
        out.append((int(n.group(1)), n.group(2), ref.group(1) if ref else None))
    return out


def parse_cl_plenos(page):
    """Plenary days (red cells, '#F2674E') of the calendar of plenaries."""
    out = []
    for month, table in re.findall(r"(?s)<td>([A-Za-zé]+ \d{4})</td>\s*</tr>\s*</tbody>\s*</table>\s*(<table.*?</table>)",
                                   page):
        name, year = month.split()
        mo = ra.month(name)
        if not mo:
            continue
        for day in re.findall(r'background-color:\s*#F2674E;?"[^>]*>\s*(?:<strong>)?(\d{1,2})', table, re.I):
            out.append(ra.iso(day, mo, year))
    return [d for d in out if d]


def read_cl(client, ctx):
    gaps, detailed, cal = [], [], []
    week = monday(ctx.today)
    last = ctx.today
    while week.isoformat() <= ctx.until and not ctx.out_of_time():
        url = CL_WEEK.format(week)
        try:
            page = fetch(client, url, "cl-semana-" + week.isoformat())
        except FetchError as e:
            if week == monday(ctx.today):
                raise
            gaps.append("Castilla y León week of {0}: {1}".format(week, str(e.cause)[:120]))
            break
        for ev in parse_cl_week(page):
            if not ctx.in_window(ev["dated"]) or not is_business_body(ev["name"]):
                continue
            body = body_name(ev["name"])
            meeting = mid(ev["dated"], body)
            points = []
            if ev["url"]:
                try:
                    points = parse_cl_event(fetch(client, ev["url"], "cl-evento-" +
                                                  ev["url"].rsplit("=", 1)[-1]))
                except FetchError as e:
                    gaps.append("Castilla y León event {0} {1}: {2}".format(
                        ev["dated"], body[:40], str(e.cause)[:100]))
            for n, t, ref in points:
                detailed.append(ra.item(ev["dated"], short(t), body, ev["time"], n, meeting,
                                        detail=t, reference=ref, url=ev["url"]))
            if not points:
                detailed.append(ra.item(ev["dated"], "", body, ev["time"], meeting_id=meeting,
                                        detail=ev["refs"] or None, url=ev["url"] or url))
        last = min((week + datetime.timedelta(days=6)).isoformat(), ctx.until)
        week += datetime.timedelta(days=7)
    try:
        for d in parse_cl_plenos(fetch(client, CL_PLENOS, "cl-plenos-previstos")):
            cal.append(ra.item(d, "", "Pleno", meeting_id=mid(d, "Pleno"), url=CL_PLENOS))
    except FetchError as e:
        gaps.append("Castilla y León plenary calendar: {0}".format(str(e.cause)[:120]))
    items = [it for it in merge(detailed, cal) if ctx.in_window(it["dated"]) and it["dated"] <= last]
    return ra.RegionRead(items, [ra.window(ctx.today, last)],
                         source="weekly agenda, sitting pages and calendar of plenaries", gaps=gaps)


# --- Canarias -------------------------------------------------------------------------

CN = "https://www.parcan.es"
CN_CAL = CN + "/actividad/calendario/"
CN_FUTURE = CN + "/reuniones/futuras.py"
CN_SESSION = CN + "/reuniones/asuntos.py?ID_SESION={0}"


def cn_body(name):
    """'Gobernación, Desarrollo ...' -> 'Comisión de Gobernación, ...';
    'De Relaciones con ...' -> 'Comisión de Relaciones con ...'."""
    n = ra.one_line(name)
    if re.match(r"(?i)^(pleno|mesa|junta|ponencia|diputaci|comisi[óo]n|subcomisi)", n):
        return body_name(n)
    if re.match(r"(?i)^(de|del|sobre)\b", n):
        return "Comisión " + n[0].lower() + n[1:]
    return "Comisión de " + n


def parse_cn_calendar(page):
    """[(dated, time, name)] of the calendar of plenaries and committees,
    and the period's end ('Periodo de sesiones del 01/ago/2026 a 31/dic/2026')."""
    out = []
    period = re.search(r"Periodo de sesiones del [^<]*? a (\d{1,2})/([a-z]{3})/(\d{4})", page)
    end = ra.iso(period.group(1), period.group(2), period.group(3)) if period else None
    for sec in re.split(r'<h2 class="h2 text-center">', page)[1:]:
        h = re.match(r"\s*([A-Za-zé]+) de (\d{4})", sec)
        if not h or not ra.month(h.group(1)):
            continue
        mo, year = ra.month(h.group(1)), h.group(2)
        day = None
        for row in re.findall(r"(?s)<tr>(.*?)(?=<tr>|</table>)", sec):
            cells = re.findall(r"(?s)<td[^>]*>(.*?)</td>", row)
            if len(cells) < 3:
                continue
            dm = re.search(r"<b>\s*\w+,\s*(\d{1,2})", cells[0])
            if dm:
                day = dm.group(1)
            if not day:
                continue
            tm, name = text(cells[1]), text(cells[2])
            if re.match(r"^\d{1,2}:\d{2}$", tm) and name:
                out.append((ra.iso(day, mo, year), tm, name))
    return out, end


def parse_cn_future(page):
    return sorted(set(re.findall(r"asuntos\.py\?ID_SESION=(\d+)", page)))


def parse_cn_session(page):
    """(dated, time, name, [(order, business, reference, detail)])."""
    sec = re.search(r'(?s)<section aria-label="Asuntos de la sesi[óo]n">(.*?)</section>', page)
    if not sec:
        return None
    head = re.search(r'(?s)<span class="negrita">(.*?)<br>\s*(\d{1,2})/([a-z]{3})/(\d{4}), a las (\d{1,2}:\d{2})',
                     sec.group(1))
    if not head:
        return None
    name = text(head.group(1))
    dated = ra.iso(head.group(2), head.group(3), head.group(4))
    points, heading, n = [], "", 0
    paras = re.findall(r"(?s)<p>(.*?)</p>", sec.group(1))
    for p in paras:
        detail = ""
        if "Proponente:" in p:
            p, detail = p.split("Proponente:", 1)
            detail = "Proponente: " + text(detail)
        t = text(p)
        m = re.match(r"^(\d+(?:\.\d+)*)\.?\s*-\s*(.*)$", t)
        if not m:
            continue
        num, rest = m.group(1), m.group(2).strip()
        if rest.upper() == "ORDEN DEL DÍA" or not rest:
            continue
        if "." not in num and rest == rest.upper():
            heading = rest.capitalize()
            continue
        ref = re.search(r"\b(\d+L/[A-Z]+-\d+)\b", rest)
        business = rest.replace(ref.group(1), "").strip(" ;") if ref else rest
        if heading:
            business = "{0}: {1}".format(heading, business)
        n += 1
        points.append((n, business, ref.group(1) if ref else None, detail or None))
    return dated, head.group(5), name, points


def read_cn(client, ctx):
    gaps, detailed, cal = [], [], []
    rows, period_end = parse_cn_calendar(fetch(client, CN_CAL, "cn-calendario"))
    for dated, tm, name in rows:
        if not ctx.in_window(dated) or not is_business_body(cn_body(name)):
            continue
        body = cn_body(name)
        cal.append(ra.item(dated, "", body, tm or None, meeting_id=mid(dated, body), url=CN_CAL))
    for sid in parse_cn_future(fetch(client, CN_FUTURE, "cn-futuras")):
        if ctx.out_of_time():
            gaps.append("Canarias: time budget reached before every convened sitting was read")
            break
        url = CN_SESSION.format(sid)
        try:
            got = parse_cn_session(fetch(client, url, "cn-asuntos-" + sid))
        except FetchError as e:
            gaps.append("Canarias sitting {0}: {1}".format(sid, str(e.cause)[:120]))
            continue
        if not got:
            continue
        dated, tm, name, points = got
        body = cn_body(name)
        if not ctx.in_window(dated) or not is_business_body(body):
            continue
        meeting = mid(dated, body)
        for n, business, ref, detail in points:
            detailed.append(ra.item(dated, short(business), body, tm, n, meeting,
                                    detail=detail, reference=ref, url=url))
        if not points:
            detailed.append(ra.item(dated, "", body, tm, meeting_id=meeting, url=url))
    covered = min(period_end, ctx.until) if period_end else ctx.until
    items = [it for it in merge(detailed, cal) if ctx.in_window(it["dated"])]
    return ra.RegionRead(items, [ra.window(ctx.today, covered)],
                         source="calendar of plenaries and committees, convened sittings' orders "
                                "of the day", gaps=gaps)


# --- Aragón ---------------------------------------------------------------------------

AR = "https://www.cortesaragon.es"
AR_WEEKS = (AR + "/Semana-actual.2237.0.html?&no_cache=1",
            AR + "/Proxima-semana.2335.0.html?&no_cache=1")
AR_CSV = AR + "/fileadmin/_DMZMedia/comunicacion/web/varios/calendario.csv"


def parse_ar_week(page):
    """[{dated, time, name, url}] of one week page ('Agenda del 19.10.2026 al
    25.10.2026', a card per event)."""
    span = re.search(r"Agenda del (?:<span>)?\s*(\d{2})\.(\d{2})\.(\d{4})", page)
    if not span:
        return []
    start = datetime.date(int(span.group(3)), int(span.group(2)), int(span.group(1)))
    out = []
    for card in re.split(r'<div class="entry clearfix">', page)[1:]:
        d = re.search(r'<div class="entry-date">(\d{1,2})\s*<span>([A-Za-z]{3})', card)
        a = re.search(r'<h2[^>]*><a href="([^"]+)"[^>]*>(.*?)</a>', card, re.S)
        if not d or not a:
            continue
        mo = ra.month(d.group(2)) or {"ene": 1, "abr": 4, "ago": 8, "dic": 12}.get(d.group(2).lower())
        if not mo:
            continue
        year = start.year + (1 if mo < start.month else 0)
        tm = re.search(r'icon-time"></i>\s*(\d{1,2}:\d{2})', card)
        href = _html.unescape(a.group(1))
        out.append({"dated": ra.iso(d.group(1), mo, year), "time": tm.group(1) if tm else None,
                    "name": text(a.group(2)),
                    "url": href if href.startswith("http") else AR + "/" + href.lstrip("/")})
    return out


def parse_ar_event(page):
    """[(order, text)] of an 'Acto programado' page."""
    m = re.search(r'(?s)Acto programado</li>.*?</h\d>(.*?)(?:AGENDA DE HOY|class="widget)', page)
    chunk = m.group(1) if m else page
    lines = ra.clean(chunk).splitlines()
    return numbered_points([l for l in lines if not re.match(r"^\d{2}/\d{2}/\d{4}$|^\d{1,2}:\d{2}$", l)])


def parse_ar_csv(raw):
    """Plenary days of the calendar CSV (Acto, Fecha, Control)."""
    out = []
    for row in csv.DictReader(io.StringIO(raw)):
        acto, fecha = (row.get("Acto") or ""), (row.get("Fecha") or "").strip()
        if "sesión plenaria" not in acto.lower() and "sesion plenaria" not in acto.lower():
            continue
        d = fecha if re.match(r"^\d{4}-\d{2}-\d{2}$", fecha) else ra.find_date(fecha)
        if d:
            out.append(d)
    return out


def read_ar(client, ctx):
    gaps, detailed, cal = [], [], []
    for i, url in enumerate(AR_WEEKS):
        for ev in parse_ar_week(fetch(client, url, "ar-semana-{0}".format(i))):
            if not ctx.in_window(ev["dated"]) or not is_business_body(ev["name"]):
                continue
            body = body_name(ev["name"])
            meeting = mid(ev["dated"], body)
            points = []
            if not ctx.out_of_time():
                try:
                    uid = re.search(r"uid%5D=(\d+)", ev["url"])
                    points = parse_ar_event(fetch(client, ev["url"], "ar-acto-" +
                                                  (uid.group(1) if uid else "x")))
                except FetchError as e:
                    gaps.append("Aragón sitting {0} {1}: {2}".format(ev["dated"], body[:40],
                                                                    str(e.cause)[:100]))
            for n, t in points:
                detailed.append(ra.item(ev["dated"], short(t), body, ev["time"], n, meeting,
                                        detail=t, url=ev["url"]))
            if not points:
                detailed.append(ra.item(ev["dated"], "", body, ev["time"], meeting_id=meeting,
                                        url=ev["url"]))
    try:
        for d in parse_ar_csv(fetch(client, AR_CSV, "ar-calendario-plenos")):
            cal.append(ra.item(d, "", "Pleno", meeting_id=mid(d, "Pleno"), url=AR_CSV))
    except FetchError as e:
        gaps.append("Aragón plenary calendar: {0}".format(str(e.cause)[:120]))
    items = [it for it in merge(detailed, cal) if ctx.in_window(it["dated"])]
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)],
                         source="this and next week's agenda, sitting pages, plenary calendar CSV",
                         gaps=gaps)


# --- Cantabria ------------------------------------------------------------------------

CB = "https://parlamento-cantabria.es"
CB_WEEK = CB + "/agenda-semana?date={0}"


def parse_cb_week(page, url=None):
    """Items of one week page: a heading per day ('20 de Octubre'), an
    <article> per event with its order of the day inline."""
    span = re.search(r"Semana del \d{1,2}(?: de [A-Za-z]+)? al \d{1,2} de ([A-Za-z]+) de (\d{4})", page)
    if not span:
        return []
    year, end_month = int(span.group(2)), ra.month(span.group(1))
    items = []
    parts = re.split(r'<span class="date">(\d{1,2}) de ([A-Za-z]+)</span>', page)
    for i in range(1, len(parts) - 2, 3):
        mo = ra.month(parts[i + 1])
        if not mo:
            continue
        y = year - 1 if (mo == 12 and end_month == 1) else year
        dated = ra.iso(parts[i], mo, y)
        for art in re.findall(r'(?s)<article[^>]*node--type-evento[^>]*>(.*?)</article>', parts[i + 2]):
            name = re.search(r'(?s)field--name-title[^>]*>(.*?)</span>', art)
            if not name or not is_business_body(text(name.group(1))):
                continue
            body = body_name(text(name.group(1)))
            tm = re.search(r'date-display-single">\s*(\d{1,2}:\d{2})', art)
            meeting = mid(dated, body)
            n = 0
            for p in re.findall(r"(?s)<p[^>]*>(.*?)</p>", art):
                t = text(p)
                m = re.match(r"^(\d{1,2})\.\s*(.*)$", t)
                if not m:
                    continue
                n += 1
                refs = re.findall(r"\[(\d+L/[\d-]+)\]", t)
                items.append(ra.item(dated, short(m.group(2)), body, tm.group(1) if tm else None,
                                     int(m.group(1)), meeting, detail=m.group(2),
                                     reference=refs[-1] if refs else None, url=url))
            if n == 0:
                items.append(ra.item(dated, "", body, tm.group(1) if tm else None,
                                     meeting_id=meeting, url=url))
    return items


def read_cb(client, ctx):
    items = []
    week = monday(ctx.today)
    last = ctx.today
    gaps = []
    while week.isoformat() <= ctx.until and not ctx.out_of_time():
        url = CB_WEEK.format(week.isoformat())
        try:
            page = fetch(client, url, "cb-semana-" + week.isoformat())
        except FetchError as e:
            if week == monday(ctx.today):
                raise
            gaps.append("Cantabria week of {0}: {1}".format(week, str(e.cause)[:120]))
            break
        items += parse_cb_week(page, url)
        last = min((week + datetime.timedelta(days=6)).isoformat(), ctx.until)
        week += datetime.timedelta(days=7)
    items = [it for it in items if ctx.in_window(it["dated"])]
    return ra.RegionRead(items, [ra.window(ctx.today, last)],
                         source="weekly agenda with orders of the day", gaps=gaps)


# --- the seventeen ----------------------------------------------------------------------

REGIONS = {
    "an": ra.region("Andalucía", reader=read_an),
    "ct": ra.region("Cataluña", reader=read_ct, langs=[CATALAN]),
    "md": ra.region("Madrid", status="blocked",
                    note="asambleamadrid.es answers every path, robots.txt included, with a Sucuri "
                         "firewall page (403 / JavaScript challenge); never bypassed. No open-data "
                         "copy of the agenda found (datos.comunidad.madrid's API is robots-disallowed)"),
    "vc": ra.region("Comunitat Valenciana", reader=read_vc),
    "ga": ra.region("Galicia", status="blocked",
                    note="parlamentodegalicia.gal (and .es) answer Akamai 403 'Access Denied' on "
                         "every path, robots.txt included"),
    "cl": ra.region("Castilla y León", reader=read_cl),
    "pv": ra.region("País Vasco", status="no-route",
                    note="legebiltzarra.eus does not answer from the laptop (connect timeout, 12 and "
                         "16 October 2026); re-probe from GitHub's runners"),
    "cn": ra.region("Canarias", reader=read_cn),
    "cm": ra.region("Castilla-La Mancha", status="blocked",
                    note="the agenda is an iframe of /web2/paginas/calendario.php and robots.txt "
                         "disallows /web2/paginas/"),
    "mc": ra.region("Murcia", status="blocked",
                    note="asambleamurcia.es robots.txt: 'Disallow: /' for every agent"),
    "ar": ra.region("Aragón", reader=read_ar),
    "ib": ra.region("Illes Balears", status="no-route",
                    note="parlamentib.es does not answer from the laptop (connect timeout, 12 and 16 "
                         "October 2026); re-probe from GitHub's runners"),
    "ex": ra.region("Extremadura", status="blocked",
                    note="asambleaex.es robots.txt: 'Disallow: /' for every agent (Crawl-delay 60)"),
    "as": ra.region("Asturias", status="blocked",
                    note="jgpa.es answers every path with a 'Voight-Kampff Browser Test' bot "
                         "challenge (403) since October 2026; never bypassed"),
    "nc": ra.region("Navarra", status="blocked",
                    note="parlamentodenavarra.es answers a Cloudflare 'Just a moment...' challenge; "
                         "parlamentonavarra.es does not answer"),
    "cb": ra.region("Cantabria", reader=read_cb),
    "ri": ra.region("La Rioja", status="no-route",
                    note="the plenary calendar is an encrypted PDF, the sessions iCal export "
                         "(ics_view) answers 500, and session pages list attendance, not an order "
                         "of the day; the agenda RSS mixes past sessions and institutional events"),
}
