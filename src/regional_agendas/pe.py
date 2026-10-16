"""Peru: the 25 regional councils and Lima Metropolitana's council, forward
business (regional_agenda, 16 October 2026; src/regional_agenda.py is the
interface, docs/peru-regions-scope.md "Forward agenda" has every measurement).

The past half (tools/pe_regions.py) reads the councils' ordenanzas and
acuerdos from El Peruano and gob.pe. Forward, the one machine-readable
route is the same platform: gob.pe's publication type 'Agenda de Sesión de
Consejo Regional' (type 91; Lima Metropolitana's 'Agenda de Sesión de Concejo
Municipal', type 93), a list of the agendas and convocations each council
uploads, with the sitting's date in the entry's own words ('Agenda de la
Sesión Ordinaria del pleno del Consejo Regional del 15 de Octubre del
2026'). The agenda itself is a PDF: each sitting found in the window is one
'to be announced' item, with the entry's title and summary as detail.

Measured on 16 October 2026 (one request per institution, robots.txt
disallows only /admin/ and ?sheet= URLs): thirteen of the 26 institutions
have used the type, six of them in 2026 (Lima region uploads about a week
ahead; Ica posts its convocations a few days ahead; Piura, Arequipa,
Lambayeque and Ayacucho upload on or after the sitting day). The other
thirteen have never used it: no route (their agendas go to Facebook, which is
not a route, or are not published). Region codes are config/pe-regions.yaml's
keys, as tools/pe_regions.py stores them.
"""

from __future__ import annotations

import html
import re
import urllib.parse

from src import regional_agenda as ra

CC = "pe"
TAXONOMIES = (("taxonomy-es.yaml", "pe"),)
THROTTLES = {"www.gob.pe": 3.0}
FEED = ra.feed(CC)

GOBPE = "https://www.gob.pe"
TYPE_URL = GOBPE + "/institucion/{0}/informes-publicaciones/tipos/{1}"
COUNCIL_TYPE = "91-agenda-de-sesion-de-consejo-regional"
LIMA_TYPE = "93-agenda-de-sesion-de-concejo-municipal"

MONTHS_ES = {m: i for i, m in enumerate(
    ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
     "octubre", "noviembre", "diciembre"), 1)}
MONTHS_ES["setiembre"] = 9

_ES_DATE = re.compile(r"\b(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚáéíóú]+)\s+(?:del?\s+)?(?:a[ñn]o\s+)?(\d{4})\b", re.I)
_NUM_DATE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b")


def es_date(text):
    """The first date in Spanish text: '15 de Octubre del 2026', '02 de
    setiembre 2026', '11 de setiembre de 2026', '15/10/2026'."""
    t = ra.one_line(text)
    found = []
    for m in _ES_DATE.finditer(t):
        mo = MONTHS_ES.get(m.group(2).lower())
        if mo:
            found.append((m.start(), ra.iso(m.group(1), mo, m.group(3))))
    for m in _NUM_DATE.finditer(t):
        found.append((m.start(), ra.iso(m.group(1), m.group(2), m.group(3))))
    found = [f for f in found if f[1]]
    return min(found)[1] if found else None


def parse_gobpe_list(page):
    """[(entry id, title, summary, published, url)] of a gob.pe publication-
    type list."""
    out = []
    for li in re.findall(r'<li class="hover:bg-gray-70[^"]*"[^>]*>(.*?)</li>', page or "", re.S):
        a = re.search(r'<a class="[^"]*card__mock[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', li, re.S)
        if not a:
            continue
        href, title = a.group(1), ra.one_line(ra.clean(a.group(2)))
        summary = re.search(r'<div class="relative z-10" id="p-filter-item-\d+">(.*?)</div>', li, re.S)
        published = re.search(r'<time[^>]*datetime="(\d{4}-\d{2}-\d{2})', li)
        eid = re.search(r"/informes-publicaciones/(\d+)-", href)
        out.append((eid.group(1) if eid else href, html.unescape(title),
                    ra.one_line(ra.clean(summary.group(1))) if summary else "",
                    published.group(1) if published else None, urllib.parse.urljoin(GOBPE, href)))
    return out


def sitting_date(title, summary):
    """The sitting's date: the summary's ('... del 15 de Octubre del 2026'),
    else the title's ('Convocatoria ...: lunes 17 agosto 2026')."""
    d = es_date(summary) or es_date(title)
    if d:
        return d
    m = re.search(r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b", title + " " + summary)
    if m and MONTHS_ES.get(m.group(2).lower()):
        return ra.iso(m.group(1), MONTHS_ES[m.group(2).lower()], m.group(3))
    return None


def items_from_list(rows, ctx, code, body):
    out, seen = [], set()
    for eid, title, summary, published, url in rows:
        if re.match(r"(?i)reprogramad[ao]", title):
            continue                      # moved: the new convocation is its own entry
        dated = sitting_date(title, summary)
        if not ctx.in_window(dated):
            continue
        kind = "extraordinaria" if re.search(r"(?i)extraordinaria|\bext\b", title + " " + summary) else (
            "ordinaria" if re.search(r"(?i)ordinaria", title + summary) else "")
        mid = "{0}:{1}:sesion{2}".format(code, dated, "-" + kind if kind else "")
        if mid in seen:                   # a reprogrammed convocation: the newest entry stands
            continue
        seen.add(mid)
        out.append(ra.item(dated, "", body, meeting_id=mid,
                           detail="; ".join(x for x in (title, summary) if x), url=url))
    return out


def gobpe_reader(code, slug, type_slug=COUNCIL_TYPE, body="Consejo Regional"):
    def read(client, ctx):
        url = TYPE_URL.format(slug, type_slug)
        rows = parse_gobpe_list(client.get_text(url, FEED, "agenda-" + code))
        newest = max((r[3] for r in rows if r[3]), default=None)
        return ra.RegionRead(items_from_list(rows, ctx, code, body), [ra.window(ctx.today, ctx.until)],
                             source="gob.pe {0} ('Agenda de Sesión', type {1})".format(slug, type_slug.split("-")[0]),
                             note="agenda as PDF: sittings to be announced; newest upload {0}".format(
                                 newest or "none"))
    read.__name__ = "read_" + code.replace("-", "_")
    return read


NO_TYPE = ("gob.pe's 'Agenda de Sesión de Consejo Regional' list for this council is empty (16 October "
           "2026): agendas and convocations go to Facebook (not a route) or are not published")


def _no(name):
    return ra.region(name, status="no-route", note=NO_TYPE)


REGIONS = {
    "lima-metropolitana": ra.region("Lima Metropolitana", reader=gobpe_reader(
        "lima-metropolitana", "munilima", LIMA_TYPE, body="Concejo Metropolitano")),
    "piura": ra.region("Piura", reader=gobpe_reader("piura", "regionpiura")),
    "la-libertad": ra.region("La Libertad", reader=gobpe_reader("la-libertad", "regionlalibertad")),
    "arequipa": ra.region("Arequipa", reader=gobpe_reader("arequipa", "regionarequipa")),
    "cajamarca": _no("Cajamarca"),
    "junin": _no("Junín"),
    "cusco": ra.region("Cusco", reader=gobpe_reader("cusco", "regioncusco")),
    "lambayeque": ra.region("Lambayeque", reader=gobpe_reader("lambayeque", "regionlambayeque")),
    "puno": _no("Puno"),
    "callao": ra.region("Callao", reader=gobpe_reader("callao", "regioncallao")),
    "ancash": _no("Áncash"),
    "loreto": _no("Loreto"),
    "ica": ra.region("Ica", reader=gobpe_reader("ica", "regionica")),
    "lima": ra.region("Lima (region)", reader=gobpe_reader("lima", "regionlima")),
    "san-martin": _no("San Martín"),
    "huanuco": _no("Huánuco"),
    "ayacucho": ra.region("Ayacucho", reader=gobpe_reader("ayacucho", "regionayacucho")),
    "ucayali": _no("Ucayali"),
    "apurimac": _no("Apurímac"),
    "amazonas": ra.region("Amazonas", reader=gobpe_reader("amazonas", "regionamazonas")),
    "huancavelica": _no("Huancavelica"),
    "tacna": _no("Tacna"),
    "pasco": _no("Pasco"),
    "tumbes": ra.region("Tumbes", reader=gobpe_reader("tumbes", "regiontumbes")),
    "moquegua": ra.region("Moquegua", reader=gobpe_reader("moquegua", "regionmoquegua")),
    "madre-de-dios": _no("Madre de Dios"),
}
