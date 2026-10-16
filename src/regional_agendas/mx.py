"""Mexico: the state congresses' forward business (regional_agenda, 16 October 2026).

The past half (tools/mxs_collect.py, src/mxs_store.py) lists what each
readable congress has tabled; this module reads what is BOOKED: the next
sesión and its orden del día, committee meetings and their subjects.
Region codes are src/mxs_store.STATES's ('cdmx', 'jal', ...), so the
renderer can join the two. Mexican congresses publish the orden del día a
day or two before a sesión, often as a PDF; most have no forward calendar at
all. Every route was probed live on 16 October 2026 with robots.txt read
first (docs/mexico-regions-scope.md, "Forward agenda").

  yuc   Yucatán: the home page's "Agenda de actividades" table (plenary and
        committee sesiones, newest first, with a link to each one's gaceta
        page) and, for a sesión in the window, its "Orden del Día" PDF (pypdf).
  jal   Jalisco: the Congress's Drupal calendar (agenda-parlamentaria/mes/
        YYYY-MM, one page a month; robots.txt Crawl-delay 10): sesiones and
        committee meetings booked, with time. The calendar carries no
        subjects, so each is 'to be announced'.
  chih  Chihuahua: sesiones.php's "Próxima Sesión" (date, time, title) and
        ordenDia.php, the next sesión's orden del día (HTML): named points
        when it carries any, else the booked sesión.
  qroo  Quintana Roo: the weekly committee agenda (/agenda/: date, time,
        committees, subjects) and the newest orden del día the home page
        links (/ordenesdia/<id>, HTML, numbered points).
  bcs   Baja California Sur: the period's "Orden del Día" category (Joomla,
        one article a sesión, linked from the home page) and the article of
        each sesión in the window (roman-numbered points).

Not read, each with its reason on every run: see REGIONS.
"""

from __future__ import annotations

import datetime
import html as _html
import re
import urllib.parse

from src import regional_agenda as ra
from src.http import FetchError

CC = "mx"
TAXONOMIES = (("taxonomy-es.yaml", "mx"),)
FEED = ra.feed(CC)

YUC = "https://congresoyucatan.gob.mx"
JAL_MONTH = "https://www.congresojal.gob.mx/agenda-parlamentaria/mes/{0}"
JAL = "https://www.congresojal.gob.mx"
CHIH = "https://www.congresochihuahua.gob.mx/"
QROO = "https://www.congresoqroo.gob.mx"
BCS = "https://www.cbcs.gob.mx"

THROTTLES = {"www.congresojal.gob.mx": 10.0, "congresoyucatan.gob.mx": 2.0,
             "www.congresochihuahua.gob.mx": 2.0, "www.congresoqroo.gob.mx": 2.0,
             "www.cbcs.gob.mx": 2.0}

YUC_PDF_CAP = 6


def _one(text):
    return ra.one_line(_html.unescape(text or ""))


def _hm(text):
    m = re.search(r"(\d{1,2})[:.](\d{2})", text or "")
    return "{0:02d}:{1}".format(int(m.group(1)), m.group(2)) if m else None


def es_date(text):
    """'15 DE OCTUBRE DE 2026', '13 de Octubre de 2026', '20 octubre 2026',
    'JUEVES 15 DE OCTUBRE DEL AÑO 2026' -> ISO."""
    t = _one(text)
    m = re.search(r"\b(\d{1,2})\s+(?:de\s+)?([A-Za-zÁÉÍÓÚáéíóú]{3,10})\s+(?:de(?:l)?\s+)?"
                  r"(?:(?:a[ñn]o)\s+)?(\d{4})\b", t, re.I)
    if m and ra.month(m.group(2).lower()):
        return ra.iso(m.group(1), m.group(2).lower(), m.group(3))
    return ra.find_date(t)


def _units(ctx, complete, meetings):
    if complete:
        return [ra.window(ctx.today, ctx.until)]
    return [ra.meeting(m) for m in meetings]


# --- an orden del día in plain text ---------------------------------------------------

_ROMAN = re.compile(r"^([IVXL]{1,6})\s*(?:\.-|\.|-|\))\s*(.*)$")
_LETTER = re.compile(r"^([A-Z])\)\s*(.*)$")
_NUM = re.compile(r"^(\d{1,2})\s*\.-\s*(.*)$")


def orden_points(lines, header=()):
    """Numbered points of an orden del día -> [(label, text, section)]: a
    roman point with lettered sub-points is the section of its letters
    (each letter an item); a roman or numbered point without them is an
    item itself. Running page headers in `header` are dropped."""
    points = []          # [label, text, kind, parent]
    for raw in lines:
        line = _one(raw)
        if not line or line in header or re.match(r"^\d{1,3}$", line):
            continue
        lm = _LETTER.match(line)
        if lm and points and points[-1][2] == "sub" and len(points[-1][0]) == 1 and \
                ord(lm.group(1)) == ord(points[-1][0]) + 1:
            # 'I)' after 'H)' is the next letter, not the roman numeral one.
            points.append([lm.group(1), lm.group(2), "sub", points[-1][3]])
            continue
        m = _ROMAN.match(line) or _NUM.match(line)
        if m and (m.re is _NUM or len(m.group(2)) > 2):
            points.append([m.group(1), m.group(2), "top", None])
            continue
        m = _LETTER.match(line)
        if m and points:
            parent = next((p for p in reversed(points) if p[2] == "top"), None)
            points.append([m.group(1), m.group(2), "sub", parent])
            continue
        if points:
            points[-1][1] = (points[-1][1] + " " + line).strip()
    with_subs = {id(p[3]) for p in points if p[2] == "sub" and p[3] is not None}
    out = []
    for p in points:
        if p[2] == "top" and id(p) in with_subs:
            continue
        section = p[3][1].rstrip(" :") if p[3] is not None else None
        label = "{0}.{1}".format(p[3][0], p[0]) if p[3] is not None else p[0]
        out.append((label, p[1].strip(), section))
    return out


_ROUTINE = re.compile(r"^(?:lista de (?:asistencia|presentes)|pase de lista|declaratoria|"
                      r"verificaci[óo]n del qu[óo]rum|instalaci[óo]n|lectura.{0,40}\bacta\b|lectura (?:y aprobaci[óo]n )?"
                      r"(?:del orden|de la s[íi]ntesis|del acta)|lectura,? discusi[óo]n y (?:votaci[óo]n|"
                      r"aprobaci[óo]n) del acta|discusi[óo]n y votaci[óo]n de la s[íi]ntesis|"
                      r"correspondencia|turnos? a comisiones|asuntos generales|clausura|"
                      r"presentaci[óo]n de iniciativas de ley, decreto|lectura, discusi[óo]n y "
                      r"aprobaci[óo]n, en su caso, de los dict[áa]menes, informes)", re.I)


def is_routine(text):
    return bool(_ROUTINE.match(_one(text)))


def point_items(points, dated, body, meeting_id, url=None, item_time=None):
    """Items of an orden del día; None when it holds only the routine
    headings (the booked sesión is then 'to be announced')."""
    if not points or all(is_routine(t) for _l, t, _s in points):
        return None
    out = []
    for n, (label, text, section) in enumerate(points, 1):
        if not text:
            continue
        out.append(ra.item(dated, text[:1500], body, item_time=item_time, order=n,
                           meeting_id=meeting_id, detail=section, reference=None, url=url,
                           key="p-{0}-{1}".format(ra.slug(label, 10), ra.slug(text, 40))))
    return out


def pdf_text(raw):
    try:
        import io
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(raw))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:                                   # noqa: BLE001 - a bad PDF is a gap
        return ""


# --- Yucatán ---------------------------------------------------------------------------

def parse_yuc_agenda(page):
    """Home page 'Agenda de actividades' -> [dict(dated, time, kind, desc, url)]."""
    m = re.search(r'home-agenda-legislativa(.*?)</table>', page or "", re.S)
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", m.group(1) if m else "", re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 5:
            continue
        link = re.search(r'href="([^"]+)"', cells[4])
        out.append({"dated": _one(ra.clean(cells[0]))[:10], "time": _hm(ra.clean(cells[1])),
                    "kind": _one(ra.clean(cells[2])), "desc": _one(ra.clean(cells[3])),
                    "url": link.group(1) if link else None})
    return out


def yuc_body(row):
    if "pleno" in row["desc"].lower() or row["kind"].lower().startswith("sesi"):
        return "Pleno"
    d = row["desc"]
    return d if d.lower().startswith("comisi") else "Comisión de " + d


def parse_yuc_session(page):
    """A gaceta/sesiones-pleno page -> the 'Orden del Día' PDF URL, if any."""
    for href, label in re.findall(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', page or "", re.S):
        if "orden" in (href + ra.clean(label)).lower():
            return urllib.parse.urljoin(YUC + "/", href.replace(" ", "%20"))
    m = re.search(r'href="(/storage/[^"]*ORDEN[^"]*\.pdf)"', page or "", re.I)
    return urllib.parse.urljoin(YUC + "/", m.group(1).replace(" ", "%20")) if m else None


_YUC_HEADER = {"GOBIERNO DEL ESTADO DE YUCATAN", "GOBIERNO DEL ESTADO DE  YUCATAN", "PODER LEGISLATIVO",
               "LXIV LEGISLATURA DEL ESTADO", "LIBRE Y SOBERANO"}


def repair_pdf_caps(text):
    """pypdf splits some capitals around accented letters ('P ÉRDIDA',
    'RELACIÓ N'): join them back."""
    text = re.sub(r"\b([A-ZÑ]) ([ÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ]+)", r"\1\2", text or "")
    return re.sub(r"([A-Z][ÁÉÍÓÚ]) ([A-Z]{1,2})\b", r"\1\2", text)


def parse_yuc_orden(text):
    text = repair_pdf_caps(text)
    lines = []
    for l in (text or "").split("\n"):
        l = re.sub(r"^DE YUCATAN\s+", "", l.strip())     # the masthead runs into the first line
        lines.append(l)
    return orden_points(lines, header=_YUC_HEADER)


def read_yuc(client, ctx):
    rows = parse_yuc_agenda(client.get_text(YUC + "/", FEED, "yuc-home"))
    items, gaps, ok, meetings, pdfs = [], [], True, [], 0
    for row in rows:
        if not ctx.in_window(row["dated"]):
            continue
        body = yuc_body(row)
        mid = "yuc-{0}".format(row["url"].rstrip("/").rsplit("/", 1)[-1] if row["url"] else
                               "{0}-{1}".format(row["dated"], ra.slug(body, 30)))
        got = None
        if row["url"] and pdfs < YUC_PDF_CAP and not ctx.out_of_time():
            try:
                pdf = parse_yuc_session(client.get_text(row["url"], FEED, mid))
                if pdf:
                    pdfs += 1
                    got = point_items(parse_yuc_orden(pdf_text(client.get_bytes(pdf, FEED, mid + "-od"))),
                                      row["dated"], body, mid, url=pdf, item_time=row["time"])
            except FetchError as exc:
                gaps.append("yuc: {0} {1}: {2}".format(row["dated"], body, exc))
                ok = False
        items += got or [ra.item(row["dated"], "", body, item_time=row["time"], meeting_id=mid,
                                 detail=row["kind"], url=row["url"])]
        meetings.append(mid)
    return ra.RegionRead(items, _units(ctx, ok, meetings),
                         source="congresoyucatan.gob.mx agenda + orden del día PDFs", gaps=gaps)


# --- Jalisco ------------------------------------------------------------------------------

_JAL_KEEP = re.compile(r"^(?:sesi[óo]n|comisi[óo]n|comisiones|diputaci[óo]n permanente|pleno|"
                       r"junta de coordinaci[óo]n)", re.I)
_JAL_DROP = re.compile(r"adquisiciones|rueda de prensa|entrega de|presentaci[óo]n de libro", re.I)


def parse_jal_month(page):
    """A month of the calendar -> [(dated, time, title, url)] for every entry."""
    out = []
    for href, title, stamp in re.findall(
            r'views-field-title">\s*<span class="field-content"><a href="([^"]+)">(.*?)</a>.*?'
            r'content="(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})', page or "", re.S):
        out.append((stamp[:10], stamp[11:16], _one(ra.clean(title)), urllib.parse.urljoin(JAL, href)))
    return out


def jal_items(entries, ctx):
    out, seen = [], set()
    for dated, time, title, url in entries:
        if not ctx.in_window(dated) or not _JAL_KEEP.match(title) or _JAL_DROP.search(title):
            continue
        if (dated, time, title) in seen:
            continue
        seen.add((dated, time, title))
        body = re.sub(r"\s*\((?:telem[áa]tica|presencial|h[íi]brida)[^)]*\)\s*$", "", title, flags=re.I)
        if re.match(r"^(sesi[óo]n|pleno)", body, re.I):
            body = "Pleno"
        out.append(ra.item(dated, "", body, item_time=time,
                           meeting_id="jal-{0}-{1}-{2}".format(dated, time.replace(":", ""),
                                                             ra.slug(body, 30)),
                           detail=title, url=url))
    return out


def read_jal(client, ctx):
    entries, d = [], ctx.today_date.replace(day=1)
    while d.isoformat() <= ctx.until:
        entries += parse_jal_month(client.get_text(JAL_MONTH.format(d.strftime("%Y-%m")), FEED,
                                                   "jal-{0}".format(d.strftime("%Y-%m"))))
        d = (d + datetime.timedelta(days=32)).replace(day=1)
    return ra.RegionRead(jal_items(entries, ctx), [ra.window(ctx.today, ctx.until)],
                         source="congresojal.gob.mx agenda parlamentaria (month calendar)",
                         note="the calendar carries no subjects: sesiones and committee meetings "
                              "are booked slots")


# --- Chihuahua ----------------------------------------------------------------------------

def parse_chih_next(page):
    """sesiones.php -> (date, time, title) of the 'Próxima Sesión', or None."""
    m = re.search(r"Próxima Sesi[óo]n:?\s*</h3>\s*<h2>(.*?)</h2>\s*<p>(.*?)</p>", page or "", re.S)
    if not m:
        return None
    return es_date(m.group(1)), _hm(m.group(1)), _one(ra.clean(m.group(2)))


def parse_chih_orden(page):
    text = ra.clean(page or "")
    i = text.find("ORDEN DEL DÍA")
    j = text.find("Buzón electrónico")
    body = text[i + len("ORDEN DEL DÍA"):j if j > i else None] if i >= 0 else ""
    return orden_points(body.split("\n"))


def read_chih(client, ctx):
    nxt = parse_chih_next(client.get_text(CHIH + "sesiones.php", FEED, "chih-sesiones"))
    items, gaps = [], []
    if nxt and ctx.in_window(nxt[0]):
        dated, time, title = nxt
        mid = "chih-{0}".format(dated)
        got = None
        try:
            got = point_items(parse_chih_orden(client.get_text(CHIH + "ordenDia.php", FEED,
                                                               "chih-orden")),
                              dated, "Pleno", mid, url=CHIH + "ordenDia.php", item_time=time)
        except FetchError as exc:
            gaps.append("chih: orden del día: {0}".format(exc))
        items = got or [ra.item(dated, "", "Pleno", item_time=time, meeting_id=mid,
                                detail=title[:300], url=CHIH + "sesiones.php")]
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)] if not gaps else
                         [ra.meeting(i["meeting_id"]) for i in items[:1]],
                         source="congresochihuahua.gob.mx próxima sesión + ordenDia.php",
                         note="the next sesión only", gaps=gaps)


# --- Quintana Roo -------------------------------------------------------------------------

def parse_qroo_agenda(page):
    """The weekly agenda -> [dict(dated, time, event, bodies, subjects)]."""
    out, dated = [], None
    for m in re.finditer(r'<tr class="(tr_encabezado|tr_agenda)">(.*?)</tr>', page or "", re.S):
        if m.group(1) == "tr_encabezado":
            dated = es_date(ra.clean(m.group(2)))
            continue
        row = m.group(2)
        hora = re.search(r'class="hora_inicio">(.*?)</p>', row, re.S)
        event = re.search(r'<h5 class="evento">(.*?)</h5>', row, re.S)
        bodies = [_one(ra.clean(b)).rstrip(".") for b in re.findall(
            r'<li(?! class="diputado")[^>]*>(.*?)</li>',
            (re.search(r'<ul class="lista_titulo">(.*?)</ul>', row, re.S) or [None, ""])[1]
            if re.search(r'<ul class="lista_titulo">', row) else "", re.S)]
        asunto = re.search(r'<td class="td_asunto">(.*?)</td>', row, re.S)
        subjects = [_one(ra.clean(s)) for s in re.findall(r"<li[^>]*>(.*?)</li>",
                                                          asunto.group(1) if asunto else "", re.S)]
        if not subjects and asunto:
            subjects = [l for l in ra.clean(asunto.group(1)).split("\n") if l and not
                        re.match(r"^Para (?:atender|tratar)", l)]
        out.append({"dated": dated, "time": _hm(ra.clean(hora.group(1))) if hora else None,
                    "event": _one(ra.clean(event.group(1))) if event else "",
                    "bodies": [b for b in bodies if b], "subjects": [s for s in subjects if s]})
    return out


def qroo_agenda_items(rows, ctx):
    out = []
    for r in rows:
        if not ctx.in_window(r["dated"]):
            continue
        body = " / ".join(r["bodies"]) or r["event"] or "Comisión"
        mid = "qroo-{0}-{1}-{2}".format(r["dated"], (r["time"] or "").replace(":", ""),
                                        ra.slug(body, 30))
        if not r["subjects"]:
            out.append(ra.item(r["dated"], "", body, item_time=r["time"], meeting_id=mid,
                               detail=r["event"], url=QROO + "/agenda/"))
        for n, s in enumerate(r["subjects"], 1):
            out.append(ra.item(r["dated"], s[:1500], body, item_time=r["time"], order=n,
                               meeting_id=mid, detail=r["event"], url=QROO + "/agenda/"))
    return out


def parse_qroo_orden(page):
    """An /ordenesdia/<id> page -> (date, time, title, [(label, text, None)])."""
    t = page or ""
    title = re.search(r'<h3 class="titulo-seccion-1[^"]*">(.*?)</h3>', t, re.S)
    when = re.search(r'fecha-orden-dia">(.*?)</div>', t, re.S)
    when_text = ra.clean(when.group(1)) if when else ""
    points = [(n, _one(ra.clean(p)), None) for n, p in re.findall(
        r'<span class="vineta">\s*(\d+)\.-\s*</span>\s*<p>(.*?)</p>', t, re.S)]
    return es_date(when_text), _hm(when_text), _one(ra.clean(title.group(1))) if title else "", points


def read_qroo(client, ctx):
    items, gaps, ok = [], [], True
    agenda = client.get_text(QROO + "/agenda/", FEED, "qroo-agenda")
    items += qroo_agenda_items(parse_qroo_agenda(agenda), ctx)
    meetings = sorted({i["meeting_id"] for i in items})
    try:
        home = client.get_text(QROO + "/", FEED, "qroo-home")
        ids = sorted({int(i) for i in re.findall(r'href="/ordenesdia/(\d+)"', home)}, reverse=True)
        for oid in ids[:2]:
            url = "{0}/ordenesdia/{1}".format(QROO, oid)
            dated, time, title, points = parse_qroo_orden(client.get_text(url, FEED,
                                                                          "qroo-orden-{0}".format(oid)))
            if not ctx.in_window(dated):
                continue
            mid = "qroo-orden-{0}".format(oid)
            items += point_items(points, dated, "Pleno", mid, url=url, item_time=time) or [
                ra.item(dated, "", "Pleno", item_time=time, meeting_id=mid, detail=title, url=url)]
            meetings.append(mid)
    except FetchError as exc:
        gaps.append("qroo: orden del día: {0}".format(exc))
        ok = False
    # The weekly agenda covers its own week only: the window is read in full
    # when nothing failed (later weeks are not published yet).
    return ra.RegionRead(items, _units(ctx, ok, meetings),
                         source="congresoqroo.gob.mx agenda semanal + ordenesdia",
                         note="weekly committee agenda (this week) and the newest orden del día",
                         gaps=gaps)


# --- Baja California Sur ---------------------------------------------------------------------

def parse_bcs_category_url(home):
    """The current period's 'orden-del-dia' category, from the home page."""
    for href in re.findall(r'href="([^"]*/orden-del-dia)"', home or ""):
        return urllib.parse.urljoin(BCS + "/", href)
    return None


def parse_bcs_category(page):
    """-> [(dated, title, url)] newest first."""
    out = []
    for href, title in re.findall(r'href="([^"]*/orden-del-dia/\d+-[^"]+)"[^>]*>\s*([^<]+)', page or ""):
        out.append((es_date(title), _one(title), urllib.parse.urljoin(BCS + "/", href)))
    seen, res = set(), []
    for r in out:
        if r[2] not in seen:
            seen.add(r[2])
            res.append(r)
    return res


def parse_bcs_article(page):
    """An orden del día article -> (time, [(label, text, section)])."""
    m = re.search(r'<section class="article-body">(.*?)</section>', page or "", re.S)
    body = m.group(1) if m else ""
    text = ra.clean(body)
    time = _hm(re.search(r"A LAS (\d{1,2}:\d{2})", text).group(1)) if re.search(
        r"A LAS (\d{1,2}:\d{2})", text) else None
    i = text.find("D Í A")
    lines = text[i + 5:].split("\n") if i >= 0 else text.split("\n")
    return time, orden_points(lines)


def read_bcs(client, ctx):
    cat = parse_bcs_category_url(client.get_text(BCS + "/", FEED, "bcs-home"))
    if not cat:
        raise FetchError(BCS, FEED, "bcs-home", 1, "no 'orden-del-dia' category linked from the home page")
    rows = parse_bcs_category(client.get_text(cat, FEED, "bcs-ordenes"))
    items, gaps, ok, meetings = [], [], True, []
    for dated, title, url in rows:
        if not ctx.in_window(dated):
            continue
        mid = "bcs-{0}".format(url.rsplit("/", 1)[-1].split("-", 1)[0])
        try:
            time, points = parse_bcs_article(client.get_text(url, FEED, mid))
        except FetchError as exc:
            gaps.append("bcs: {0}: {1}".format(title, exc))
            ok = False
            continue
        items += point_items(points, dated, "Pleno", mid, url=url, item_time=time) or [
            ra.item(dated, "", "Pleno", item_time=time, meeting_id=mid, detail=title, url=url)]
        meetings.append(mid)
    return ra.RegionRead(items, _units(ctx, ok, meetings),
                         source="cbcs.gob.mx Orden del Día (one article a sesión)", gaps=gaps)


# --- the regions ---------------------------------------------------------------------------

_UK = ("does not answer UK addresses (tools/mxs_collect.py, 12 October 2026; asked again on 16 "
       "October); jobs/mx-collect.sh runs on GitHub's runners, where it may answer, but no "
       "capture could be obtained to verify a parser, so no reader")

REGIONS = {
    "mex": ra.region("Estado de México", status="no-route", note=(
        "legislacion.congresoedomex.gob.mx lists sesiones and committee 'reuniones' only once "
        "held (newest 8 October 2026, with votes); the Gaceta is published after the sitting")),
    "cdmx": ra.region("Ciudad de México", status="no-route", note=(
        "www.congresocdmx.gob.mx presents a certificate for another name, so robots.txt cannot be "
        "read and nothing there is fetched; the citizen portal (ciudadana.) answered 500 and has "
        "no sesiones view")),
    "jal": ra.region("Jalisco", reader=read_jal),
    "ver": ra.region("Veracruz", status="no-route", note="www.legisver.gob.mx " + _UK),
    "pue": ra.region("Puebla", status="blocked", note=(
        "congresopuebla.gob.mx serves a Cloudflare managed challenge on every page (never "
        "bypassed)")),
    "gto": ra.region("Guanajuato", status="no-route", note="www.congresogto.gob.mx " + _UK),
    "nl": ra.region("Nuevo León", status="no-route", note="www.hcnl.gob.mx " + _UK),
    "chis": ra.region("Chiapas", status="no-route", note=(
        "web.congresochiapas.gob.mx/trabajo-legislativo/sesiones (a 1.8 MB page) lists sesiones "
        "with their orden del día only from the day they are held (newest 14 October 2026)")),
    "mich": ra.region("Michoacán", status="no-route", note="congresomich.gob.mx " + _UK),
    "oax": ra.region("Oaxaca", status="no-route", note=(
        "the home page links a 2022 comparecencias calendar and sesionesdips.html (past "
        "sittings); no orden del día ahead found")),
    "chih": ra.region("Chihuahua", reader=read_chih),
    "gro": ra.region("Guerrero", status="no-route", note=(
        "per-sitting gacetas on a third-party host (sialgro.dcrsoft.com.mx), posted after the "
        "sitting")),
    "tamps": ra.region("Tamaulipas", status="no-route", note=(
        "www.congresotamaulipas.gob.mx timed out in the TLS handshake on 16 October 2026; no "
        "agenda page known (its iniciativas list is read by tools/mxs_collect.py)")),
    "bc": ra.region("Baja California", status="no-route", note=(
        "www.congresobc.gob.mx: robots.txt did not answer (TLS timeout) on 16 October 2026, so "
        "nothing there is fetched; no agenda page known")),
    "coah": ra.region("Coahuila", status="no-route", note=(
        "www.congresocoahuila.gob.mx answered a parked-domain page on 16 October 2026; the "
        "congress's JSF statistics site has no agenda")),
    "son": ra.region("Sonora", status="no-route", note=(
        "congresoson.gob.mx did not resolve from the laptop on 16 October 2026; only the "
        "votacion-electronica API (iniciativas, no sesiones) is known")),
    "hgo": ra.region("Hidalgo", status="no-route", note=(
        "congresohidalgo.gob.mx gaceta pages per sitting, posted with the sitting; no agenda "
        "ahead found")),
    "slp": ra.region("San Luis Potosí", status="blocked", note=(
        "congresosanluis.gob.mx serves a Sucuri JavaScript challenge (never bypassed)")),
    "sin": ra.region("Sinaloa", status="no-route", note=(
        "/orden-del-dia/ is an iframe of the gaceta app (gaceta.congresosinaloa.gob.mx/#/hoy, "
        "AngularJS); its public JSON endpoint for the day's orden was not identified")),
    "qro": ra.region("Querétaro", status="no-route", note=(
        "legislaturaqueretaro.gob.mx answers plain HTTP only (the https port refuses), and the "
        "pipeline fetches nothing in the clear")),
    "yuc": ra.region("Yucatán", reader=read_yuc),
    "mor": ra.region("Morelos", status="no-route", note=(
        "Gaceta DOCX/PDFs posted months after the sitting")),
    "qroo": ra.region("Quintana Roo", reader=read_qroo),
    "dgo": ra.region("Durango", status="blocked", note=(
        "congresodurango.gob.mx: Wordfence geo block (503) from the UK, never bypassed")),
    "tab": ra.region("Tabasco", status="no-route", note=(
        "congresotabasco.gob.mx (WordPress) lists sesiones ordinarias and actas after the "
        "sitting; no orden del día ahead found on the home page")),
    "ags": ra.region("Aguascalientes", status="no-route", note=(
        "the 'agenda legislativa' (LegislativeAgenda) is the list of iniciativas, not a calendar; "
        "the home page is 17 MB and carries no sesión ahead")),
    "zac": ra.region("Zacatecas", status="no-route", note="www.congresozac.gob.mx " + _UK),
    "tlax": ra.region("Tlaxcala", status="no-route", note=(
        "congresodetlaxcala.gob.mx/sesiones-congreso/ carries injected gambling spam and lists "
        "past sesiones only (16 October 2026); not read")),
    "nay": ra.region("Nayarit", status="no-route", note=(
        "www.congresonayarit.gob.mx: robots.txt did not answer (TLS timeout) on 16 October 2026; "
        "the utics. JSON read for iniciativas has no sesiones")),
    "cam": ra.region("Campeche", status="blocked", note=(
        "www.congresocam.gob.mx robots.txt: User-agent: * Disallow: /")),
    "col": ra.region("Colima", status="no-route", note=(
        "www.congresocol.gob.mx presented a certificate that does not verify on 16 October 2026, "
        "so robots.txt cannot be read and nothing is fetched")),
    "bcs": ra.region("Baja California Sur", reader=read_bcs),
}
