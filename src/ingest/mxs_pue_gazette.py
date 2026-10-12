"""Puebla: the decrees of the Congress published in the Periódico Oficial del
Estado, read from the Supreme Court's compilation of state legislation
(13 October 2026).

WHY NOT PUEBLA ITSELF. The Congress's site (congresopuebla.gob.mx and its
subdomains) sits behind a Cloudflare managed challenge, which is never solved
or bypassed; the Periódico Oficial (periodicooficial.puebla.gob.mx), the Orden
Jurídico Poblano, puebla.gob.mx and datos.puebla.gob.mx refuse TCP
connections from the UK, and the Wayback Machine holds no capture of the
gazette (docs/mexico-regions-scope.md, "Alternative routes").

SOURCE. The Suprema Corte de Justicia de la Nación's "Sistema de Consulta de
Ordenamientos" (legislacion.scjn.gob.mx), compiled by its Centro de
Documentación y Análisis, Archivos y Compilación de Leyes from the official
gazettes of every state. robots.txt: none (an IIS 404), so nothing is
disallowed; no login, key or token; the honest User-Agent is answered
(measured 12 and 13 October 2026). Its page "Búsqueda de las 50 reformas más
recientes" (buscador/paginas/wfReformasResultados.aspx, opened with the
q token its own home page links) lists the newest reforms; the page's own
form, posted back once with Ámbito = ESTATAL, Entidad = PUEBLA and 50 a page,
gives Puebla's 50 newest: ordinance title, date of publication in the
Periódico Oficial, category (DECRETO, DECLARATORIA, ACUERDO, REGLAMENTO),
edition and section, and the decree's operative words ("DECRETO / UNICO. SE
REFORMAN ... DE LA LEY ..."). Two requests a run (the page, then its
postback); no cookie is needed (the ViewState carries the form).

Measured 12 October 2026: 50 rows from 2 July to 2 October 2026, among them
33 decrees and one constitutional declaratoria (e.g. reforms of the Ley para
el Acceso de las Mujeres a una Vida Libre de Violencia, the Código Civil and
the Ley de los Derechos de Niñas, Niños y Adolescentes, published 28 July to
10 August). The Court's compilation runs a few weeks behind the gazette.

WHAT IS KEPT: the Legislature's acts only. DECRETO and DECLARATORIA rows
(laws are enacted by decree of the Congress; constitutional reforms by its
declaratoria), except rows on a REGLAMENTO (regulations are the governor's
or a council's, save the Congress's own Reglamento Interior), municipal
acuerdos and reglamentos, and decrees the Executive issues in its own name.
A gazette carries what the Congress ADOPTED, not bills in passage.

KEY: 'po/scjn/<12 hex>' (a hash of the ordinance, the publication date and
the decree's operative words; the Court gives a reform no public number), so
an item never collides with a congress item if the Congress lets us in
later. Title: the Court's words, upper case as printed.
"""

from __future__ import annotations

import hashlib
import html as _html
import re
from urllib.parse import urljoin

from src.ingest.mxs_common import clean, date, since_ok

READER = ("Periódico Oficial del Estado de Puebla, decrees of the Congress, as compiled by "
          "the SCJN (legislacion.scjn.gob.mx, 50 most recent reforms)")
PAGE = ("https://legislacion.scjn.gob.mx/buscador/paginas/wfReformasResultados.aspx"
        "?q=78tXSP4D9DqLbEkEfwPY3A==")
FORM = "ctl00$MainContentPlaceHolder$ucBusqueda1$"
AMBITO_ESTATAL = "1"
ENTIDAD_PUEBLA = "20"
LEGISLATURE = "LXII"
KEEP = ("DECRETO", "DECLARATORIA")

HIDDEN = re.compile(r'<input\b[^>]*type="hidden"[^>]*>', re.I)
ATTR = re.compile(r'\b(name|value)="([^"]*)"', re.I)
ROW_START = re.compile(r'<tr id="[^"]*gridReformasRecientes_DXDataRow\d+"')
TITLE = re.compile(r'lbTitulo">(.*?)</span>', re.S)
DETAIL = re.compile(r"""href=['"]?(wfOrdenamientoDetalle\.aspx\?q=[^'"\s>]+)""")
CELL2 = re.compile(r'<td colspan="2">(.*?)</td>', re.S)
OPERATIVE = re.compile(
    r"^(?:ART[IÍ]CULO\s+)?(?:[UÚ]NICO|PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[EÉ]PTIMO|"
    r"OCTAVO|NOVENO|D[EÉ]CIMO)\b|^SE\s+(?:REFORMA|ADICIONA|DEROGA|EXPIDE|APRUEBA|ABROGA|CREA)",
    re.I)
NOT_OPERATIVE = re.compile(r"^(?:NOTA|FUENTE|HTTP|TRANSITORIO|DECRETO$|DECLARATORIA$)", re.I)


def form_fields(page):
    """The page's hidden ASP.NET fields plus the Puebla search, as its own
    "Buscar" button posts them; None if the page carries no ViewState."""
    fields = {}
    for tag in HIDDEN.findall(page or ""):
        attrs = {k.lower(): _html.unescape(v) for k, v in ATTR.findall(tag)}
        if attrs.get("name"):
            fields[attrs["name"]] = attrs.get("value", "")
    if "__VIEWSTATE" not in fields:
        return None
    fields.update({FORM + "ddlAmbito": AMBITO_ESTATAL, FORM + "ddlEntidad": ENTIDAD_PUEBLA,
                   FORM + "ddlPageSize": "50", FORM + "Button1": "Buscar"})
    return fields


def _labelled(row, label):
    m = re.search(re.escape(label) + r":</span>\s*(.*?)</td>", row, re.S)
    return clean(m.group(1)) if m else None


def _operative(row):
    """The decree's operative words: the first paragraph after the category
    line, skipping the Court's NOTA / FUENTE lines."""
    for cell in CELL2.findall(row):
        if "font-weight: bold" in cell or "link2" in cell:
            continue
        lines = [x for x in (clean(y) for y in re.split(r"<br\s*/?>", cell)) if x]
        for line in lines:
            if OPERATIVE.search(line):
                return line
        for line in lines:                              # an unnumbered decree
            if not NOT_OPERATIVE.search(line):
                return line
    return None


def _legislative(category, title):
    t = (title or "").upper()
    if category not in KEEP:
        return False
    if t.startswith("REGLAMENTO") and "CONGRESO" not in t:
        return False
    if t.startswith("CODIGO REGLAMENTARIO") or "AYUNTAMIENTO" in t:
        return False
    if "EJECUTIVO" in t and "DECRETO" in t:
        return False
    return True


def _trim(text, limit=320):
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;") + " ..."


def parse(reply):
    """[item] for the Congress's decrees among the listed reforms."""
    out, seen = [], set()
    starts = [m.start() for m in ROW_START.finditer(reply or "")]
    for i, s in enumerate(starts):
        row = reply[s:starts[i + 1] if i + 1 < len(starts) else len(reply)]
        tm = TITLE.search(row)
        law = clean(tm.group(1)) if tm else None
        category = (_labelled(row, "Categoria") or "").upper()
        published = date(_labelled(row, "Fecha de publicación") or "")
        if not law or not published or not _legislative(category, law):
            continue
        op = _operative(row) or ""
        if law.upper() in _trim(op).upper():
            title = "{0}. {1}".format(category, _trim(op))
        elif op:
            title = "{0} ({1}). {2}".format(category, law, _trim(op))
        else:
            title = "{0}: {1}".format(category, law)
        digest = hashlib.sha1("|".join((law, published, op)).encode("utf-8")).hexdigest()[:12]
        if digest in seen:
            continue
        seen.add(digest)
        dm = DETAIL.search(row)
        out.append({
            "state": "pue", "source_id": "po/scjn/" + digest,
            "legislature": LEGISLATURE,
            "kind": "declaratoria" if category == "DECLARATORIA" else "decreto",
            "title": title,
            "presenter": "Congreso del Estado (Periódico Oficial, compiled by the SCJN)",
            "party": None, "presented": published, "turno": None,
            "status": "Publicado en el Periódico Oficial", "status_date": published,
            "url": urljoin(PAGE, _html.unescape(dm.group(1))) if dm else PAGE,
        })
    return out


def collect(ctx, since, today=None):
    page = ctx.text(PAGE, "pue-scjn-form")
    if page is None:
        return []                                       # the gap is recorded by ctx
    fields = form_fields(page)
    if fields is None:
        ctx.gap("pue (SCJN): the reforms page came without its form; nothing posted")
        return []
    reply = ctx.post_form(PAGE, fields, "pue-scjn-puebla")
    if reply is None:
        return []
    if "gridReformasRecientes" not in reply:
        why = ("a fault on the Court's side (\"Object reference not set\")"
               if "Object reference not set" in reply else "no results grid")
        ctx.gap("pue (SCJN): the Puebla search answered {0}".format(why))
        return []
    return [it for it in parse(reply) if since_ok(it["presented"], since)]
