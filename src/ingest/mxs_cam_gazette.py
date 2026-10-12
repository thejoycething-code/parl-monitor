"""Campeche: the decrees and acuerdos of the Congress in the Periódico Oficial
del Estado (12 October 2026).

WHY THE GAZETTE. The Congress's site (www.congresocam.gob.mx) answers
robots.txt with `User-agent: *` / `Disallow: /` (only Googlebot allowed),
so it is never read (docs/mexico-regions-scope.md). The state's official
gazette is a different host, run by the Executive's Secretaría de Gobierno,
and prints everything the Legislature adopts in its "SECCIÓN LEGISLATIVA"
editions. Adopted decrees and acuerdos only: no bills in passage.

SOURCE. periodicooficial.campeche.gob.mx/sipoec/public (SIPOEC), no
robots.txt (404, so no rules; measured 12 October 2026). There is no
per-decree listing: each edition is one PDF. Two steps:

  1. the site's own full-text search, a plain GET form
     (documentos_avanzada?inicio=&fin=&contenido=), asked for "Palacio
     Legislativo" (every legislative act closes "Dado en el Palacio
     Legislativo") and "SECCIÓN LEGISLATIVA"; each answers about 12
     editions a page in roughly 30 seconds, with each edition's name
     (PO2748SS30092026: number, section, date) and its id;
  2. getDocumento/<id> gives the PDF's path under /periodicos/; the PDF is
     read with pypdf, kept only when its masthead says SECCIÓN LEGISLATIVA,
     and split into its DECRETO and ACUERDO blocks (number, the operative
     article's first words as the title).

A legislative edition is 300 KB to 2 MB. The window is clamped to the last
MAX_DAYS days and to MAX_PDFS editions a run, so a first run does not pull
a year of PDFs; anything cut is a gap line, never silent.

KEYS: a decree by its number in the legislature ('cam/po/LXV/decreto/285',
decree numbers run through a legislature); an acuerdo by edition and number
('cam/po/2748SS/acuerdo/38', the Diputación Permanente restarts its count).
"""

from __future__ import annotations

import datetime
import re
from urllib.parse import urlencode

from src.http import FetchError
from src.ingest.mxs_common import date, since_ok
from src.prov_fetch import Unreadable, pdf_text

READER = "Periódico Oficial (periodicooficial.campeche.gob.mx), SECCIÓN LEGISLATIVA editions"
BASE = "https://periodicooficial.campeche.gob.mx/sipoec/public/"
SEARCH = BASE + "documentos_avanzada"
QUERIES = ("Palacio Legislativo", "SECCIÓN LEGISLATIVA")
MAX_DAYS = 35
MAX_PDFS = 12
MAX_PAGES = 3
SEARCH_TIMEOUT = 90.0

EDITION = re.compile(r'data-id="(\d+)"[^>]*>\s*(PO(\d+)([A-Z]{2})(\d{2})(\d{2})(\d{4}))\s*<', re.I)
LEGISLATIVE = re.compile(r"SECCI[OÓ]N\s+LEGISLATIV\s*A", re.I)
BLOCK = re.compile(r"(?:^|\n)\s*(DECRETO|ACUERDO)\s*\n", re.S)
NUMBER = re.compile(r"\bN[UÚ]MERO\s+(\d+)\b", re.I)
OPERATIVE = re.compile(r"\b(ART[IÍ]CULO\s+(?:[UÚ]NICO|PRIMERO)|PRIMERO|[UÚ]NICO)\s*\.?\s*-+\s*", re.I)
LEGISLATURA = re.compile(r"\b(L[XVI]+)\s+Legislatura\b")
PAGE_HEAD = re.compile(r"PERI[OÓ]DICO OFICIAL DEL ESTADO\s*\nP[AÁ]G\.\s*\d+\s*\n[^\n]*\n[^\n]*\n")


def search_url(query, since, until, page=1):
    q = {"inicio": since, "fin": until, "contenido": query}
    if page > 1:
        q["page"] = page
    return SEARCH + "?" + urlencode(q)


def editions(markup):
    """[(id, name, number, section code, ISO date)] in a search page, unique."""
    seen, out = set(), []
    for m in EDITION.finditer(markup or ""):
        if m.group(1) in seen:
            continue
        seen.add(m.group(1))
        try:
            iso = datetime.date(int(m.group(7)), int(m.group(6)), int(m.group(5))).isoformat()
        except ValueError:
            iso = None
        out.append((m.group(1), m.group(2), m.group(3), m.group(4).upper(), iso))
    return out


def pages_in(markup):
    m = re.search(r"Pagina\s+\d+\s+de\s+(\d+)", markup or "")
    return int(m.group(1)) if m else 1


def _flat(text):
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def title_of(kind, number, block):
    """The act's own first operative words, cut at 'para quedar como sigue'."""
    body = block[NUMBER.search(block).end():] if NUMBER.search(block) else block
    m = OPERATIVE.search(body)
    words = _flat(body[m.end():] if m else body)
    for stop in (", para quedar como sigue", " para quedar como sigue", " para quedar como siguen"):
        if stop in words:
            words = words.split(stop, 1)[0]
            break
    if len(words) > 420:
        words = words[:420].rsplit(" ", 1)[0] + " ..."
    label = "Decreto" if kind == "DECRETO" else "Acuerdo"
    return "{0} número {1}: {2}".format(label, number, words.rstrip(" .:;,")) if words else None


def parse_edition(text, name, iso):
    """Items (decrees, acuerdos) in one edition's text; [] unless the masthead
    says SECCIÓN LEGISLATIVA."""
    head = (text or "")[:1500]
    if not LEGISLATIVE.search(head):
        return []
    text = PAGE_HEAD.sub("\n", text.replace("=====PAGE", ""))
    leg = LEGISLATURA.search(text)
    legislature = leg.group(1) if leg else None
    edition_date = date(head) or iso
    marks = list(BLOCK.finditer(text))
    out = []
    for i, m in enumerate(marks):
        block = text[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        num = NUMBER.search(block[:3000])
        if not num:
            continue
        kind = m.group(1).upper()
        title = title_of(kind, num.group(1), block)
        if not title:
            continue
        code = name[2:-8]                      # 'PO2748SS30092026' -> '2748SS'
        if kind == "DECRETO" and legislature:
            sid = "po/{0}/decreto/{1}".format(legislature, num.group(1))
        else:
            sid = "po/{0}/{1}/{2}".format(code, kind.lower(), num.group(1))
        out.append({
            "state": "cam", "source_id": sid, "legislature": legislature,
            "kind": "decreto" if kind == "DECRETO" else "other", "title": title,
            "presenter": "Congreso del Estado (Periódico Oficial)", "party": None,
            "presented": edition_date, "turno": None,
            "status": "Publicado en el Periódico Oficial ({0})".format(name),
            "status_date": edition_date, "url": None,
        })
    return out


def collect(ctx, since, today=None):
    today = today or datetime.date.today().isoformat()
    floor = (datetime.date.fromisoformat(today) - datetime.timedelta(days=MAX_DAYS)).isoformat()
    start = max(since or floor, floor)
    found = {}
    for query in QUERIES:
        for page in range(1, MAX_PAGES + 1):
            if ctx.stop():
                break
            url = search_url(query, start, today, page)
            if not ctx.allowed(url):
                ctx.gap("robots.txt disallows {0}; not fetched".format(url))
                break
            try:
                markup = ctx.client.get_text(url, ctx.feed, "cam-search", archive=False,
                                             timeout=SEARCH_TIMEOUT)
            except FetchError as exc:
                ctx.gap("cam gazette search ({0}): {1}".format(query, exc.cause))
                break
            for ed in editions(markup):
                found.setdefault(ed[0], ed)
            if page >= pages_in(markup):
                break
    wanted = sorted((ed for ed in found.values() if since_ok(ed[4], start)),
                    key=lambda ed: ed[4] or "", reverse=True)
    if len(wanted) > MAX_PDFS:
        ctx.gap("cam gazette: {0} legislative editions in the window, {1} read this run "
                "(the oldest wait)".format(len(wanted), MAX_PDFS))
        wanted = wanted[:MAX_PDFS]
    out = []
    for doc_id, name, _num, _sec, iso in wanted:
        if ctx.stop():
            break
        path = ctx.text(BASE + "getDocumento/" + doc_id, "cam-doc-" + doc_id)
        path = (path or "").strip().strip('"').replace("\\/", "/")
        if not path.lower().endswith(".pdf"):
            if path:
                ctx.gap("cam gazette: no PDF path for {0}".format(name))
            continue
        url = BASE + "periodicos/" + path
        raw = ctx.bytes(url, "cam-" + name)
        if raw is None:
            continue
        try:
            text = pdf_text(raw, pages=range(0, 40))
        except Unreadable as exc:
            ctx.gap("cam gazette: {0}: {1}".format(name, exc))
            continue
        for it in parse_edition(text, name, iso):
            it["url"] = url
            out.append(it)
    return out
