"""Argentina: the 24 provincial legislatures' forward business
(regional_agenda, 16 October 2026; src/regional_agenda.py is the interface,
docs/argentina-regions-scope.md "Forward agenda" has every measurement).

The past half (tools/ar_regions.py) reads laws (SAIJ) and bills; this
module reads what the legislatures have BOOKED: committee meetings with
their temario, and sessions. Region codes are src/ar_regions_store.PROVINCES',
so the renderer can join.

Read (three), robots.txt asked for every request, honest user agent:

  caba  Legislatura de la Ciudad: the parliamentary calendar's own XML web
        services on parlamentaria.legislatura.gob.ar (the host
        tools/ar_regions.py already reads; robots.txt answers 404, no rules):
        GetAgendasMesCurso (the agenda days in a range), GetAgendasDiaById
        (each day's committee meetings: committee, hour, room, notes, and the
        expedientes when the temario is loaded) and GetSesionesMesCurso (the
        sessions booked). Protocol and cultural events in the same calendar
        (no committee) are left out. The agenda of a day is published one or
        two working days ahead.
  ba    Buenos Aires, Cámara de Diputados: the home page's activity list
        (about ten days ahead): committee meetings with date, hour, room and
        the 'orden del día' PDF on intranet.hcdiputados-ba.gov.ar, whose
        ASUNTO is read when pypdf is installed (the addressees, members'
        names, are never read or stored); without pypdf, or for a meeting
        with no PDF, the meeting is 'to be announced'. Guided visits, courses
        and talks are left out. The Senate (legislativa.senado-ba.gov.ar) puts
        a reCAPTCHA on its forms: not read.
  cba   Córdoba: the Legislatura's WordPress agenda (legislaturacba.gob.ar/
        agenda/, a JetEngine month calendar of 'eventos' posts) and the posts'
        own REST entries (/wp-json/wp/v2/eventos?include=...): each committee
        meeting's temario ('Proyecto de Ley 47973/L/26, iniciado por ...').
        The calendar page shows the current month only.

Not read (each says why on every run): Santa Fe (Diputados' site answers
with its own JSON whose 'eventos_calendario' was empty; the Senate does not
answer), Mendoza (the Senate answers 403; Diputados asks a 60-second crawl
delay and lists business only in PDF session diaries), and the rest, whose
legislatures publish orders of the day as PDFs, Facebook posts or not at all
(docs/argentina-regions-scope.md).
"""

from __future__ import annotations

import calendar
import datetime
import html
import io
import re
import urllib.parse

from src import regional_agenda as ra
from src.http import FetchError

CC = "ar"
TAXONOMIES = (("taxonomy-es.yaml", "ar"),)
THROTTLES = {"parlamentaria.legislatura.gob.ar": 3.0, "www.hcdiputados-ba.gov.ar": 5.0,
             "intranet.hcdiputados-ba.gov.ar": 5.0, "legislaturacba.gob.ar": 3.0}
FEED = ra.feed(CC)
PLENARY = "Sesión"

MONTHS_ES = {m: i for i, m in enumerate(
    ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
     "octubre", "noviembre", "diciembre"), 1)}


def _units(ctx, failed, read_meetings, until=None):
    if not failed:
        return [ra.window(ctx.today, until or ctx.until)]
    return [ra.meeting(m) for m in read_meetings]


# --- CABA: the parliamentary calendar's XML web services --------------------------

CABA_WS = "https://parlamentaria.legislatura.gob.ar/webservices/Json.asmx/"
CABA_AGENDAS = CABA_WS + "GetAgendasMesCurso"
CABA_DAY = CABA_WS + "GetAgendasDiaById"
CABA_SESSIONS = CABA_WS + "GetSesionesMesCurso"
CABA_CALENDAR = "https://parlamentaria.legislatura.gob.ar/pages/calendar.aspx"


def _epoch(iso_date):
    d = datetime.date.fromisoformat(iso_date)
    return int(datetime.datetime(d.year, d.month, d.day, tzinfo=datetime.timezone.utc).timestamp())


def xml_records(text, tag):
    """[{field: text}] of every <tag> record of an ASP.NET XML reply."""
    out = []
    for block in re.findall(r"<{0}>(.*?)</{0}>".format(tag), text or "", re.S):
        rec = {}
        for name, value in re.findall(r"<(\w+)>(.*?)</\1>", block, re.S):
            rec[name] = ra.one_line(ra.clean(html.unescape(value)).replace("\n", " "))
        for name in re.findall(r"<(\w+)\s*/>", block):
            rec.setdefault(name, "")
        out.append(rec)
    return out


def parse_caba_agendas(text):
    """[(agenda id, date)] of GetAgendasMesCurso."""
    return [(r.get("id"), r.get("start")) for r in xml_records(text, "events") if r.get("id")]


def caba_title(name):
    """'TRÁNSITO Y TRANSPORTE' -> 'Comisión de Tránsito y Transporte';
    a 'JUNTA ...' keeps its own word."""
    n = ra.one_line(name)
    small = {"y", "e", "de", "del", "la", "las", "los", "el", "en", "a", "o", "u", "para", "con"}
    words = [w.lower() if (w.lower() in small and k) else w.capitalize() for k, w in enumerate(n.split())]
    t = " ".join(words)
    return t if re.match(r"(?i)(junta|comisi)", t) else "Comisión de " + t


def parse_caba_day(text):
    """The committee meetings of one agenda day: [(meeting id, date, time,
    body, notes, kind, room, [(reference, business)])]."""
    meetings = {}
    for r in xml_records(text, "eventsDay"):
        if not r.get("NombreComision"):
            continue                      # protocol, cultural and institutional events
        mid = r.get("id_comision_reunion")
        m = meetings.setdefault(mid, [mid, r.get("FechaAgenda") or r.get("FechaAgenda"),
                                      r.get("HoraDefinitiva") or None, caba_title(r["NombreComision"]),
                                      r.get("NotasReunion") or r.get("Temario") or "",
                                      r.get("comision_reunion_tipo") or "",
                                      " ".join(x for x in (r.get("Salon"), r.get("Ubicacion")) if x), []])
        if r.get("Sumario"):
            business = r["Sumario"]
            if r.get("TipoDeProyecto"):
                business = "{0}: {1}".format(r["TipoDeProyecto"], business)
            m[7].append((r.get("NroExpediente") or None, business))
    return [tuple(m) for m in meetings.values()]


def parse_caba_sessions(text):
    """[(session id, date, kind)] of GetSesionesMesCurso."""
    return [(r.get("id_sesion_lp"), r.get("fch_sesion_lp"), r.get("dsc_sesion_tipo") or "")
            for r in xml_records(text, "sesiones") if r.get("fch_sesion_lp")]


def caba_items(meetings, ctx):
    out = []
    for mid, dated, tm, body, notes, kind, room, expedientes in meetings:
        if not ctx.in_window(dated):
            continue
        meeting_id = "caba-reunion-{0}".format(mid)
        detail = "; ".join(x for x in ("Reunión de " + kind if kind and kind != "Diputados" else "", room) if x)
        if expedientes:
            for order, (ref, business) in enumerate(expedientes, 1):
                out.append(ra.item(dated, business, body, item_time=tm, order=order, meeting_id=meeting_id,
                                   reference=ref, detail=detail, url=CABA_CALENDAR))
        elif notes:
            out.append(ra.item(dated, notes, body, item_time=tm, order=1, meeting_id=meeting_id,
                               detail=detail, url=CABA_CALENDAR))
        else:
            out.append(ra.item(dated, "", body, item_time=tm, meeting_id=meeting_id, detail=detail,
                               url=CABA_CALENDAR))
    return out


def read_caba(client, ctx):
    start, end = _epoch(ctx.today), _epoch(ctx.until) + 86399
    days = parse_caba_agendas(client.post_form(CABA_AGENDAS, {"start": str(start), "end": str(end)},
                                               FEED, "caba-agendas"))
    items, gaps, failed, read_ids = [], [], False, []
    for agenda_id, dated in sorted(days, key=lambda d: d[1] or ""):
        if not ctx.in_window(dated) or ctx.out_of_time():
            continue
        try:
            reply = client.post_form(CABA_DAY, {"idAgenda": agenda_id}, FEED, "caba-day")
        except FetchError as exc:
            failed = True
            gaps.append("CABA agenda {0} ({1}): {2}".format(agenda_id, dated, str(exc)[:160]))
            continue
        got = caba_items(parse_caba_day(reply), ctx)
        items += got
        read_ids += sorted({i["meeting_id"] for i in got})
    try:
        sessions = parse_caba_sessions(client.post_form(
            CABA_SESSIONS, {"start": str(start * 1000), "end": str(end * 1000)}, FEED, "caba-sessions"))
        for sid, dated, kind in sessions:
            if ctx.in_window(dated):
                mid = "caba-sesion-{0}".format(sid)
                items.append(ra.item(dated, "", PLENARY, meeting_id=mid,
                                     detail="Sesión {0}".format(kind.lower()).strip(), url=CABA_CALENDAR))
                read_ids.append(mid)
    except FetchError as exc:
        failed = True
        gaps.append("CABA sessions: {0}".format(str(exc)[:160]))
    return ra.RegionRead(items, _units(ctx, failed, read_ids),
                         source="parlamentaria.legislatura.gob.ar calendar web services", gaps=gaps)


# --- Buenos Aires: Cámara de Diputados ------------------------------------------------

BA = "https://www.hcdiputados-ba.gov.ar/"


def parse_ba_home(page, base=BA):
    """The committee meetings in the home page's activity list:
    [(date, time, committee, description, room, orden del día URL)]."""
    page = re.sub(r"(?is)<svg\b.*?</svg>", "", page or "")
    out = []
    for block in re.split(r'<div class="actividad\b[^>]*>', page)[1:]:
        title = re.search(r'<a class="text-info" href="(index\.php\?page=comision[^"]*)"[^>]*>(.*?)</a>', block, re.S)
        date = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", block)
        if not (title and date):
            continue
        lines = [l for l in ra.clean(block).splitlines() if l.strip()]
        tm = re.search(r"\b(\d{1,2}):(\d{2})\s*hs", block)
        name = ra.one_line(ra.clean(title.group(2)))
        rest = [l for l in lines if l != name and not re.search(r"\d{2}/\d{2}/\d{4}|^\d{1,2}:\d{2}\s*hs|^Ver orden", l)]
        od = re.search(r'href="(https://intranet\.hcdiputados-ba\.gov\.ar/reuniones/[^"]+\.pdf[^"]*)"', block)
        d, mth, y = date.group(1).split("/")
        out.append((ra.iso(d, mth, y), "{0:02d}:{1}".format(int(tm.group(1)), tm.group(2)) if tm else None,
                    name, rest[0] if rest else "", rest[1] if len(rest) > 1 else None,
                    html.unescape(od.group(1)) if od else None))
    return out


def ba_body(name):
    n = ra.one_line(name)
    return caba_title(re.sub(r"(?i)^comisi[oó]n de\s+", "", n)) if re.match(r"(?i)comisi", n) else n


_BA_EXP = re.compile(r"\b([A-Z]{1,2}-\d+/\d{2}-\d{2})-\d+\.-\s*EXPEDIENTE\s*\n")
_BA_KIND = re.compile(r"^PROYECTOS? DE (LEY|DECLARACI[ÓO]N|RESOLUCI[ÓO]N|SOLICITUD DE INFORMES?)\b", re.M)


def parse_ba_od(text):
    """[(reference, business)] of an orden del día: each expediente ('D-2521/
    25-26-01.- EXPEDIENTE' + author + extract) as 'Proyecto de ley: creando
    ...', else the ASUNTO's own lines. The addressees, the signature and the
    authors' names are never kept."""
    m = re.search(r"ASUNTO:\s*(.*)", text or "", re.S)
    if not m:
        return []
    body = re.split(r"\n\s*Dip\.\s", m.group(1))[0]
    body = re.sub(r"(?m)^\s*(SECRETAR[IÍ]A LEGISLATIVA|DEPARTAMENTO DE COMUNICACIONES OFICIALES)\s*$", "", body)
    exps = list(_BA_EXP.finditer(body))
    out = []
    if exps:
        for k, e in enumerate(exps):
            end = exps[k + 1].start() if k + 1 < len(exps) else len(body)
            chunk = body[e.end():end]
            kinds = list(_BA_KIND.finditer(body[:e.start()]))
            chunk = _BA_KIND.split(chunk)[0]
            extract = ra.one_line(chunk)
            if ". " in extract:
                extract = extract.split(". ", 1)[1]          # drop the author's name
            extract = extract.rstrip(".- ")
            if not extract:
                continue
            kind = "Proyecto de {0}".format(kinds[-1].group(1).lower()) if kinds else "Expediente"
            out.append((e.group(1), "{0}: {1}".format(kind, extract[:1].upper() + extract[1:].lower())))
        return out
    points, cur = [], []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("-"):
            if cur:
                points.append(" ".join(cur))
            cur = [line.lstrip("-• ").strip()]
        else:
            cur.append(line)
    if cur:
        points.append(" ".join(cur))
    return [(None, ra.one_line(p)) for p in points
            if p and not re.match(r"(?i)aprobaci[oó]n del acta|se tratar[aá]n los siguientes", p)]


def pdf_text(data):
    """The text of a PDF with pypdf, or None when pypdf is not installed."""
    try:
        import pypdf
    except ImportError:
        return None
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    except Exception:                                    # noqa: BLE001 - a bad PDF is a TBA
        return ""


def read_ba(client, ctx):
    rows = parse_ba_home(client.get_text(BA, FEED, "ba-home"))
    items, gaps, failed, read_ids, last = [], [], False, [], None
    no_pdf_reader = pdf_down = False
    for dated, tm, name, desc, room, od in rows:
        last = max(last or dated, dated)
        if not ctx.in_window(dated):
            continue
        body = ba_body(name)
        mid = "ba-{0}-{1}-{2}".format(dated, (tm or "").replace(":", ""), ra.slug(body, 40))
        points = []
        if od and (pdf_down or ctx.out_of_time()):
            failed = True                 # not asked: its stored rows are kept
            continue
        if od:
            try:
                text = pdf_text(client.get_bytes(od, FEED, "ba-od", archive=False))
                if text is None:
                    no_pdf_reader = True
                else:
                    points = parse_ba_od(text)
            except FetchError as exc:
                failed = pdf_down = True  # one slow PDF host is not asked again this run
                gaps.append("Buenos Aires {0} {1}: {2}".format(dated, body, str(exc)[:160]))
                continue
        detail = "; ".join(x for x in (desc, room) if x)
        if points:
            for order, (ref, p) in enumerate(points, 1):
                items.append(ra.item(dated, p, body, item_time=tm, order=order, meeting_id=mid,
                                     reference=ref, detail=detail, url=od))
        else:
            items.append(ra.item(dated, "", body, item_time=tm, meeting_id=mid, detail=detail, url=od or BA))
        read_ids.append(mid)
    until = min(last, ctx.until) if last and last >= ctx.today else ctx.today
    return ra.RegionRead(items, _units(ctx, failed, read_ids, until=until),
                         source="hcdiputados-ba.gov.ar activity list (committee meetings, orden del día PDFs)",
                         note="pypdf not installed: orden del día not read" if no_pdf_reader else "",
                         gaps=gaps)


# --- Córdoba ---------------------------------------------------------------------------

CBA = "https://legislaturacba.gob.ar"
CBA_AGENDA = CBA + "/agenda/"
CBA_EVENTS = CBA + "/wp-json/wp/v2/eventos?include={0}&per_page=50"


def parse_cba_calendar(page):
    """(month's first day, [(date, post id)]) of the JetEngine month calendar."""
    cap = re.search(r'jet-calendar-caption__name">\s*([a-záéíóú]+)\s+(\d{4})', page or "", re.I)
    if not cap or cap.group(1).lower() not in MONTHS_ES:
        return None, []
    y, mth = int(cap.group(2)), MONTHS_ES[cap.group(1).lower()]
    out = []
    cells = re.split(r'<td class="jet-calendar-week__day', page)
    for cell in cells[1:]:
        if cell.startswith(" day-pad") or cell.startswith(' day-pad'):
            continue
        day = re.search(r'jet-calendar-week__day-date">\s*(\d+)', cell)
        if not day:
            continue
        d = ra.iso(day.group(1), mth, y)
        for pid in re.findall(r'data-post-id="(\d+)"', cell):
            if (d, pid) not in out:
                out.append((d, pid))
    return datetime.date(y, mth, 1).isoformat(), out


_CBA_REF = re.compile(r"\b(\d{4,6}/[A-Z]/\d{2})\b")


def parse_cba_event(post):
    """(body, [(reference, business)]) of one 'eventos' REST entry."""
    title = ra.one_line(html.unescape(re.sub(r"<[^>]+>", " ", (post.get("title") or {}).get("rendered", ""))))
    content = (post.get("content") or {}).get("rendered", "")
    content = content.split("Nómina de autoridades")[0]
    points = []
    for line in ra.clean(content).splitlines():
        line = ra.one_line(line)
        if not line or ra.one_line(line).lower() == title.lower() or re.match(r"(?i)^temas a tratar:?$", line):
            continue
        line = re.sub(r"(?i)^temas a tratar:?\s*", "", line)
        for part in re.split(r"\s+[–-]\s+(?=(?:Proyecto|Expt|Expte|Pliego|Nota)\b)", line):
            part = re.sub(r"(?<=[a-z])(?=\d{4,6}/[A-Z]/\d{2})", " ", part)
            ref = _CBA_REF.search(part)
            points.append((ref.group(1) if ref else None, part.strip(" –-")))
    return re.sub(r"\s+", " ", title), points


def read_cba(client, ctx):
    month_start, cells = parse_cba_calendar(client.get_text(CBA_AGENDA, FEED, "cba-agenda"))
    if not month_start:
        raise FetchError(CBA_AGENDA, FEED, "cba-agenda", 1, "the agenda calendar was not found on the page")
    wanted = [(d, pid) for d, pid in cells if ctx.in_window(d)]
    items = []
    if wanted:
        posts = client.get_json(CBA_EVENTS.format(",".join(pid for _, pid in wanted)), FEED, "cba-events")
        by_id = {str(p.get("id")): p for p in posts or []}
        for dated, pid in wanted:
            post = by_id.get(pid)
            if not post:
                continue
            body, points = parse_cba_event(post)
            mid = "cba-evento-{0}".format(pid)
            url = post.get("link") or CBA_AGENDA
            if points:
                for order, (ref, business) in enumerate(points, 1):
                    items.append(ra.item(dated, business, body, order=order, meeting_id=mid, reference=ref, url=url))
            else:
                items.append(ra.item(dated, "", body, meeting_id=mid, url=url))
    d = datetime.date.fromisoformat(month_start)
    month_end = d.replace(day=calendar.monthrange(d.year, d.month)[1]).isoformat()
    until = min(month_end, ctx.until)
    units = [ra.window(ctx.today, until)] if until >= ctx.today else []
    return ra.RegionRead(items, units, source="legislaturacba.gob.ar agenda (WordPress calendar and REST)",
                         note="the calendar shows the current month only (to {0})".format(month_end))


# --- the 24 jurisdictions ---------------------------------------------------------------

REGIONS = {
    "ba": ra.region("Buenos Aires", reader=read_ba),
    "caba": ra.region("Ciudad Autónoma de Buenos Aires", reader=read_caba),
    "cba": ra.region("Córdoba", reader=read_cba),
    "sf": ra.region("Santa Fe", status="no-route",
                    note="Diputados' site answers with its own JSON, whose 'eventos_calendario' was empty "
                         "on 16 October 2026; orders of the day are not published as a list; the Senate "
                         "(senadosantafe.gob.ar) does not answer from the laptop"),
    "mza": ra.region("Mendoza", status="blocked",
                     note="the Senate (senadomendoza.gob.ar) answers 403 to our requests; Diputados "
                          "(hcdmza.gob.ar) asks a 60-second crawl delay and lists business only in PDF "
                          "session diaries"),
    "tuc": ra.region("Tucumán", status="no-route",
                     note="the Legislatura's site is a React app with no agenda feed found; the expediente "
                          "app (app2.legislaturadetucuman.gob.ar) has no forward agenda"),
    "er": ra.region("Entre Ríos", status="no-route",
                    note="Senate WordPress has bills, no session or committee agenda; Diputados "
                         "(hcder.gov.ar) does not answer from the laptop"),
    "sal": ra.region("Salta", status="no-route",
                     note="Senate and Diputados publish bills and Asuntos Entrados PDFs after each sitting; "
                          "no forward agenda found"),
    "mis": ra.region("Misiones", status="no-route",
                     note="diputadosmisiones.gov.ar has expedientes per member; no session or committee "
                          "agenda found"),
    "cha": ra.region("Chaco", status="no-route",
                     note="labor parlamentaria only as PDFs; segleg is a GeneXus app (AJAX POST) with no "
                          "agenda view"),
    "ctes": ra.region("Corrientes", status="no-route",
                      note="Diputados' WordPress lists expedientes; the Senate's órdenes del día are PDFs; "
                           "no machine-readable forward agenda"),
    "sde": ra.region("Santiago del Estero", status="no-route",
                     note="no legislature site resolves (13 October 2026)"),
    "sj": ra.region("San Juan", status="no-route",
                    note="órdenes del día are announced by RSS with PDF links only after they are set; "
                         "the PDFs are not parsed (phase 2)"),
    "juj": ra.region("Jujuy", status="no-route",
                     note="the Legislatura's JSON lists projects; no session or committee agenda endpoint "
                          "found"),
    "rn": ra.region("Río Negro", status="no-route",
                    note="web.legisrn.gov.ar lists projects; sessions are announced as news posts only"),
    "nqn": ra.region("Neuquén", status="no-route",
                     note="session diaries as PDFs; the CKAN open-data API is disallowed by robots.txt"),
    "fsa": ra.region("Formosa", status="no-route",
                     note="legislaturaformosa.gob.ar publishes laws only"),
    "chu": ra.region("Chubut", status="no-route",
                     note="the larus public API lists documents; no agenda endpoint found; session "
                          "orders appear on the session page after the sitting"),
    "sl": ra.region("San Luis", status="no-route",
                    note="the Senate site is members-only; Diputados (diputados.sanluis.gov.ar) does not "
                         "answer from the laptop"),
    "cat": ra.region("Catamarca", status="blocked",
                     note="the Senate (sitiosenado.catamarca.gob.ar) answers 403; Diputados posts bills as "
                          "news, no agenda"),
    "lr": ra.region("La Rioja", status="no-route",
                    note="session diaries as PDFs only"),
    "lp": ra.region("La Pampa", status="no-route",
                    note="camaradediputados.lapampa.gob.ar does not answer from the laptop (try from the "
                         "Mini)"),
    "sc": ra.region("Santa Cruz", status="blocked",
                    note="robots.txt disallows '/*?' and every page is a '?page_id=' URL; SILEG needs a "
                         "login"),
    "tdf": ra.region("Tierra del Fuego", status="no-route",
                     note="buscar.legistdf.gob.ar's sumario lists pending business, not dated sittings "
                          "(Crawl-delay 10); no forward agenda"),
}
