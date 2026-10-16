"""Spain: the BOE's general provisions and the ministries' public
participation pages (consulta pública previa, audiencia e información
pública). Probed and built 16 October 2026 (docs/spain-scope.md, "Government
consultations and publications").

BOE (www.boe.es/datosabiertos/api/boe/sumario/YYYYMMDD, the BOE's documented
open-data API, JSON with Accept: application/json, keyless): one request per
issue, Monday to Saturday (a day with no issue answers 404, not a gap).
Section I ("Disposiciones generales") under a national department: laws,
royal decree-laws, royal decrees, orders, resolutions and treaties. The
autonomous communities' acts in the same section are left to
tools/es_regions.py (esr_laws). BOE_DAYS issues back are read each run (a
weekly run overlaps the last four weeks). robots.txt (the * group) does not
touch /datosabiertos/; /diario_boe/xml.php is disallowed and never read.

PARTICIPACIÓN PÚBLICA: there is no single list (administracion.gob.es only
links the 22 ministries' pages, and asks for one request a minute between
01:00 and 06:45 GMT). Each ministry on our ground is read on its own host:

  igualdad   www.igualdad.gob.es (WordPress): audiencia and consulta lists,
             "Participación del DD/MM/YYYY al DD/MM/YYYY" per item;
  sanidad    www.sanidad.gob.es: audiencia and consultas, "Fecha de inicio /
             finalización de envío de aportaciones: 2 de octubre de 2026";
  mpr        www.mpr.gob.es (Presidencia and Relaciones con las Cortes):
             consulta previa and audiencia lists, dates split into cells;
  justicia   www.mjusticia.gob.es/es/ciudadania/normas-tramitacion: the
             Justicia area's open procedures, free text dates;
  educacion  www.educacionfpydeportes.gob.es: the list has no dates, so an
             item page is read for the items whose title is on our ground;
  juventud   www.juventudeinfancia.gob.es and
  dsca       www.dsca.gob.es (Derechos Sociales): the TLS handshake fails
             from the laptop's Python (LibreSSL 2.8.3), so they are read
             with the same generic parser and fail loud until they answer.

A consulta pública previa is a 'consultation' (no text exists yet); an
audiencia on an anteproyecto de ley is a 'bill_draft', on a proyecto de real
decreto or orden a 'regulation_draft'. The closing date is the end of the
participation period, as printed.
"""

from __future__ import annotations

import datetime
import hashlib
import html as htmlmod
import json
import re
import unicodedata
import urllib.parse

from src import gov_docs as G

CC = "es"
BOE_SUMARIO = "https://www.boe.es/datosabiertos/api/boe/sumario/{0}"
BOE_DAYS = 31
NATIONAL = ("MINISTERIO", "JEFATURA DEL ESTADO", "PRESIDENCIA DEL GOBIERNO", "CORTES GENERALES")
ITEM_PAGES_MAX = 40

IGUALDAD = "https://www.igualdad.gob.es/servicios/participacion/"
SANIDAD = "https://www.sanidad.gob.es/normativa/"
MPR = "https://www.mpr.gob.es/servicios/participacion/"
JUSTICIA = "https://www.mjusticia.gob.es/es/ciudadania/normas-tramitacion"
EDUCACION = "https://www.educacionfpydeportes.gob.es"
EDUCACION_LIST = EDUCACION + "/servicios-al-ciudadano/informacion-publica.html"
JUVENTUD = "https://www.juventudeinfancia.gob.es/es/participacion-publica"
DSCA = "https://www.dsca.gob.es/es/servicio-a-la-ciudadania/participacion-publica/proy-normativos"

SMALL = {"de", "del", "la", "las", "los", "el", "y", "e", "para", "con", "en", "a"}


def aslist(x):
    return x if isinstance(x, list) else ([x] if x else [])


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").lower()


def nice_name(name):
    """'MINISTERIO DE SANIDAD' -> 'Ministerio de Sanidad'."""
    words = G.one_line(name).lower().split(" ")
    return " ".join(w if (i and w in SMALL) else w[:1].upper() + w[1:]
                    for i, w in enumerate(words))


def short_id(text):
    return hashlib.sha1(G.one_line(text).lower().encode("utf-8")).hexdigest()[:12]


# --- the BOE ---------------------------------------------------------------------

def boe_type(title):
    t = fold(title)
    if re.match(r"(ley organica|ley \d|ley,|real decreto-ley|real decreto legislativo)", t):
        return "law"
    if re.match(r"(instrumento de ratificacion|instrumento de adhesion|acuerdo |canje de notas|"
                r"convenio |tratado )", t):
        return "law"
    return "regulation"


def parse_boe(data, day):
    """[entry] for the national departments' acts in section I of one issue."""
    out = []
    sumario = (data.get("data") or {}).get("sumario") or {}
    for diario in aslist(sumario.get("diario")):
        for sec in aslist(diario.get("seccion")):
            if str(sec.get("codigo")) != "1":
                continue
            for dep in aslist(sec.get("departamento")):
                name = G.one_line((dep or {}).get("nombre")).upper()
                if not name.startswith(NATIONAL):
                    continue
                pairs = [(ep.get("nombre"), it) for ep in aslist(dep.get("epigrafe")) if ep
                         for it in aslist(ep.get("item"))]
                pairs += [(None, it) for it in aslist(dep.get("item"))]
                for heading, it in pairs:
                    if not it or not it.get("identificador"):
                        continue
                    out.append(G.entry("boe", it["identificador"], it.get("titulo"),
                                       boe_type(it.get("titulo")), body=nice_name(name),
                                       published=day, url=it.get("url_html"), summary=heading,
                                       status="BOE sección I"))
    return out


def boe_days(today, days=BOE_DAYS):
    end = datetime.date.fromisoformat(today)
    for n in range(days):
        d = end - datetime.timedelta(days=n)
        if d.weekday() != 6:            # no BOE on Sundays
            yield d


def fetch_boe(client, today, log=print):
    out, gaps, read = [], [], 0
    for d in boe_days(today):
        ymd = d.strftime("%Y%m%d")
        try:
            text = client.get_text(BOE_SUMARIO.format(ymd), "es-govdocs", "boe-sumario-" + ymd,
                                   headers={"Accept": "application/json"})
        except Exception as exc:                        # noqa: BLE001
            msg = str(getattr(exc, "cause", exc))
            if "404" in msg:
                continue                # no issue that day
            gaps.append("BOE sumario {0}: {1}".format(d.isoformat(), msg[:140]))
            if "robots" in str(exc).lower():
                break
            continue
        try:
            out += parse_boe(json.loads(text), d.isoformat())
            read += 1
        except (TypeError, ValueError, AttributeError) as exc:
            gaps.append("BOE sumario {0} unparsable: {1}".format(d.isoformat(), str(exc)[:120]))
    return G.fetched(out, note="{0} BOE issues read, {1} national acts in section I".format(
        read, len(out)), gaps=gaps)


# --- the ministries' participation pages ----------------------------------------------

_STRIP = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.S | re.I)
_PART = re.compile(r"<[^>]+>")
_ANCHOR = re.compile(r'<a\s[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.S | re.I)


def segments(page):
    """The page's visible text, one segment per run of text between tags."""
    body = _STRIP.sub(" ", page or "")
    body = body.replace("​", "").replace("﻿", "")
    out = []
    for raw in _PART.split(body):
        s = G.one_line(htmlmod.unescape(raw).replace("​", ""))
        if s:
            out.append(s)
    return out


def anchors(page, base):
    """{anchor text: absolute href} (first one wins)."""
    got = {}
    for href, inner in _ANCHOR.findall((page or "").replace("​", "")):
        t = G.text(inner)
        href = htmlmod.unescape(href)
        if not t or href.startswith(("#", "mailto:", "javascript:")):
            continue
        if not href.startswith("http"):
            m = re.match(r"(https?://[^/]+)(/.*)?$", base)
            root = m.group(1)
            if href.startswith("/"):
                href = root + href
            else:
                folder = base.rsplit("/", 1)[0] + "/"
                href = folder + href
            while "/../" in href:
                href = re.sub(r"/[^/]+/\.\./", "/", href, count=1)
        got.setdefault(t, href.replace(" ", "%20"))
    return got


_SEP = r"[\s|]+"
_D = r"(\d{1,2}/\d{1,2}/\d{4})"
_LONG = r"(\d{1,2}" + _SEP + r"de" + _SEP + r"[^\W\d_]+" + _SEP + r"de" + _SEP + r"\d{4})"
RANGES = (
    # 'Participación del 07/10/2026 al 19/10/2026', also split into cells
    re.compile(r"\bdel" + _SEP + _D + _SEP + r"al" + _SEP + _D),
    # 'del 25 de septiembre al 16 de octubre de 2026'
    re.compile(r"\bdel" + _SEP + r"(\d{1,2})" + _SEP + r"de" + _SEP + r"([^\W\d_]+)"
               r"(?:" + _SEP + r"de" + _SEP + r"(\d{4}))?" + _SEP + r"al" + _SEP + _LONG),
    # 'Fecha de inicio de envío de aportaciones: 2 de octubre de 2026 | Fecha de finalización ...'
    re.compile(r"Fecha de inicio[^|:]*:" + r"[\s|]*" + _LONG + r".{0,300}?Fecha (?:de finalizaci"
               r"[oó]n|l[ií]mite)[^|:]*:" + r"[\s|]*" + _LONG, re.S),
)
_LABEL = re.compile(r"(correo|buz[oó]n|fecha|documentaci|plazo|periodo|per[ií]odo|participaci[oó]n|"
                    r"aportaciones|memoria de an[aá]lisis|^proyecto$|tr[aá]mites? (de )?(consulta|"
                    r"audiencia)|abiertos?\b|cerrados?\b|no existen)", re.I)


def _range(m, idx):
    """(start ISO, end ISO) from a RANGES match."""
    if idx == 0:
        return G.iso(m.group(1)), G.iso(m.group(2))
    if idx == 1:
        end = G.long_date(re.sub(r"[\s|]+", " ", m.group(4)))
        if not end:
            return None, None
        month = G.month_number(m.group(2))
        year = int(m.group(3)) if m.group(3) else int(end[:4])
        if not m.group(3) and month and month > int(end[5:7]):
            year -= 1
        try:
            start = datetime.date(year, month, int(m.group(1))).isoformat() if month else None
        except ValueError:
            start = None
        return start, end
    return (G.long_date(re.sub(r"[\s|]+", " ", m.group(1))),
            G.long_date(re.sub(r"[\s|]+", " ", m.group(2))))


def _heading_kind(seg):
    """'consulta' / 'audiencia' for a section heading segment, else None."""
    f = fold(seg)
    if len(seg) > 120:
        return None
    if "consulta publica previa" in f and ("tramites" in f or "abiert" in f or seg.isupper()):
        return "consulta"
    if "audiencia" in f and ("tramites" in f or "abiert" in f):
        return "audiencia"
    return None


def parse_participation(page, url, kind, body, code):
    """[entry] from one ministry page: every participation period printed on
    it, titled by the nearest text before it that is not a label. kind is
    'consulta', 'audiencia' or 'mixed' (the page's headings decide)."""
    segs = segments(page)
    links = anchors(page, url)
    joined = "|".join(segs)
    starts, pos = [], 0
    for s in segs:
        starts.append(pos)
        pos += len(s) + 1
    found = []
    for idx, rx in enumerate(RANGES):
        for m in rx.finditer(joined):
            found.append((m.start(), m.end(), idx, m))
    found.sort(key=lambda f: f[0])
    out, seen, last_end = [], set(), 0
    for begin, end, idx, m in found:
        if begin < last_end:
            continue
        si = max(i for i, p in enumerate(starts) if p <= begin)
        title = None
        for j in range(si - 1, max(-1, si - 9), -1):
            if starts[j] + len(segs[j]) <= last_end:
                break
            s = segs[j]
            if len(s) < 25 or "@" in s or _LABEL.search(s[:60]):
                continue
            title = s
            break
        last_end = end
        if not title:
            continue
        start, close = _range(m, idx)
        if not close:
            continue
        key = fold(title)
        if key in seen:
            continue
        seen.add(key)
        k = kind
        if kind == "mixed":
            k = "audiencia"
            for j in range(si, -1, -1):
                h = _heading_kind(segs[j])
                if h:
                    k = h
                    break
        href = links.get(title)
        path = fold(href or "")
        if "audiencia" in path:
            k = "audiencia"
        elif "consulta" in path:
            k = "consulta"
        out.append(G.entry(code, slug_of(href) if href else short_id(title), title,
                           doc_type(title, k), body=body, published=start, closing_date=close,
                           url=href or url,
                           status=("consulta pública previa" if k == "consulta"
                                   else "audiencia e información pública")))
    return out


def slug_of(href):
    tail = urllib.parse.unquote(href.rstrip("/").rsplit("/", 1)[-1])
    tail = re.sub(r"\.(html?|aspx|pdf)$", "", tail, flags=re.I)
    tail = re.sub(r"[^A-Za-z0-9_.-]+", "-", fold(tail)).strip("-")
    return tail[:80] if len(tail) >= 6 else short_id(href)


def doc_type(title, kind):
    if kind == "consulta":
        return "consultation"
    t = fold(title)
    if re.search(r"\banteproyecto de ley|\bproyecto de ley\b", t):
        return "bill_draft"
    if re.search(r"real decreto|\borden\b|reglamento|\bdecreto\b|estatuto", t):
        return "regulation_draft"
    return "consultation"


def _pages(client, pages, code, body, log):
    out, gaps = [], []
    for url, kind in pages:
        try:
            page = client.get_text(url, "es-govdocs", "{0}-{1}".format(code, short_id(url)))
        except Exception as exc:                        # noqa: BLE001
            gaps.append("{0}: {1}".format(url, str(getattr(exc, "reason", None)
                                                    or getattr(exc, "cause", exc))[:160]))
            continue
        got = parse_participation(page, url, kind, body, code)
        if not got:
            gaps.append("{0}: answered but no participation period parsed".format(url))
        have = {e["doc_id"] for e in out}
        out += [e for e in got if e["doc_id"] not in have]
    return G.fetched(out, note="{0} procedures listed".format(len(out)), gaps=gaps)


def _source(code, body, pages):
    def fetch(client, today, log=print):
        return _pages(client, pages, code, body, log)
    fetch.__name__ = "fetch_" + code
    return fetch


fetch_igualdad = _source("igualdad", "Ministerio de Igualdad", (
    (IGUALDAD + "audienciapublica/", "audiencia"), (IGUALDAD + "consultapublica/", "consulta")))
fetch_sanidad = _source("sanidad", "Ministerio de Sanidad", (
    (SANIDAD + "audiencia/home.htm", "audiencia"), (SANIDAD + "consultas/home.htm", "consulta")))
fetch_mpr = _source("mpr", "Ministerio de la Presidencia, Justicia y Relaciones con las Cortes", (
    (MPR + "consultaprevia/Paginas/index.aspx", "consulta"),
    (MPR + "audienciapublica/Paginas/index.aspx", "audiencia")))
fetch_justicia = _source(
    "justicia", "Ministerio de la Presidencia, Justicia y Relaciones con las Cortes (Justicia)",
    ((JUSTICIA, "mixed"),))
fetch_juventud = _source("juventud", "Ministerio de Juventud e Infancia", ((JUVENTUD, "mixed"),))
fetch_dsca = _source("dsca", "Ministerio de Derechos Sociales, Consumo y Agenda 2030",
                     ((DSCA, "mixed"),))


# --- Educación: a list without dates, item pages for the ones on our ground ------------

_EDU_ITEM = re.compile(r'<a\s[^>]*href="(/servicios-al-ciudadano/informacion-publica/'
                       r'(consulta-publica-previa|audiencia-informacion-publica)/abiertos/'
                       r'[^"]+\.html)"[^>]*>(.*?)</a>', re.S | re.I)


def parse_educacion_list(page):
    """[(url, kind, title)] for the open procedures on the Educación page."""
    out, seen = [], set()
    for href, folder, inner in _EDU_ITEM.findall(page or ""):
        title = G.text(inner)
        if not title or href in seen:
            continue
        seen.add(href)
        out.append((EDUCACION + href, "consulta" if folder.startswith("consulta") else "audiencia",
                    title))
    return out


_START = re.compile(r"Fecha de inicio[^|:]*:[\s|]*" + _LONG)
_END = re.compile(r"Fecha (?:de finalizaci[oó]n|l[ií]mite)[^|:]*:[\s|]*" + _LONG)


def parse_educacion_item(page):
    """(start ISO, closing ISO) from an item page."""
    joined = "|".join(segments(page))
    s, e = _START.search(joined), _END.search(joined)
    return (G.long_date(re.sub(r"[\s|]+", " ", s.group(1))) if s else None,
            G.long_date(re.sub(r"[\s|]+", " ", e.group(1))) if e else None)


def _looks_ours(title, taxes, wl):
    probe = G.classify(G.entry("x", "probe", title, "consultation"), taxes, wl)
    return G.on_ground(probe)


def fetch_educacion(client, today, log=print, taxes=None, wl=None):
    body = "Ministerio de Educación, Formación Profesional y Deportes"
    try:
        page = client.get_text(EDUCACION_LIST, "es-govdocs", "educacion-list")
    except Exception as exc:                            # noqa: BLE001
        return G.fetched([], gaps=["{0}: {1}".format(EDUCACION_LIST, str(exc)[:160])])
    items = parse_educacion_list(page)
    if taxes is None:
        taxes, wl = G.taxonomies(CC), G.watchlist(CC)
    out, gaps, read = [], [], 0
    for url, kind, title in items:
        start = close = None
        if read < ITEM_PAGES_MAX and _looks_ours(title, taxes, wl or {}):
            read += 1
            try:
                start, close = parse_educacion_item(
                    client.get_text(url, "es-govdocs", "educacion-" + short_id(url)))
            except Exception as exc:                    # noqa: BLE001
                gaps.append("{0}: {1}".format(url, str(exc)[:120]))
        out.append(G.entry("educacion", slug_of(url), title, doc_type(title, kind), body=body,
                           published=start or today, closing_date=close, url=url,
                           status=("consulta pública previa" if kind == "consulta"
                                   else "audiencia e información pública") + " (abierto)"))
    return G.fetched(out, note="{0} open procedures, {1} item pages read".format(len(items), read),
                     gaps=gaps)


SOURCES = (
    G.Source(code="boe", name="BOE, section I (national general provisions)",
             url="https://www.boe.es/datosabiertos/api/boe/sumario/", fetch=fetch_boe),
    G.Source(code="igualdad", name="Ministerio de Igualdad, participación pública",
             url=IGUALDAD, fetch=fetch_igualdad),
    G.Source(code="sanidad", name="Ministerio de Sanidad, participación pública",
             url=SANIDAD + "portada/home.htm", fetch=fetch_sanidad),
    G.Source(code="mpr", name="Presidencia y Relaciones con las Cortes, participación pública",
             url=MPR + "Paginas/area-presidencia.aspx", fetch=fetch_mpr),
    G.Source(code="justicia", name="Justicia, participación pública", url=JUSTICIA,
             fetch=fetch_justicia),
    G.Source(code="educacion", name="Ministerio de Educación, FP y Deportes, participación pública",
             url=EDUCACION_LIST, fetch=fetch_educacion),
    G.Source(code="juventud", name="Ministerio de Juventud e Infancia, participación pública",
             url=JUVENTUD, fetch=fetch_juventud),
    G.Source(code="dsca", name="Ministerio de Derechos Sociales, participación pública",
             url=DSCA, fetch=fetch_dsca),
)
