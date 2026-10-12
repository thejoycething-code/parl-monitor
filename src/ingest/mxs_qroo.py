"""Quintana Roo: the Congress's iniciativas list (12 October 2026).

congresoqroo.gob.mx/iniciativas/?legislatura=XVIII&page=N is an HTML list
(about 43 to a page, newest first by sitting date, 480 iniciativas of the
XVIII Legislature on 12 October 2026): the sitting date ("8 de Octubre de
2026"), the status ("Turnada", ...), the title with its author, the PDF,
"Turnada a" and "Promotor(es)". robots.txt answers 404 (no rules); the host
sits behind Cloudflare and answered our honest User-Agent with no challenge.

KEY: from the PDF's file name: the sequence number at its start in the
older uploads ('1421._INICIATIVA_471_...' -> 'qroo/XVIII/1421'), the whole
stem in the newer ones ('qroo/XVIII/INI-XVIII-20260925-132215'). The site's JSON API
(/api/v1/iniciativas/) carries no dates and only half the items, so it is
not read.
"""

from __future__ import annotations

import re

from src.ingest.mxs_common import clean, date, kind_of, party_in, since_ok

READER = "iniciativas list (congresoqroo.gob.mx/iniciativas), newest first"
LEGISLATURE = "XVIII"
PAGE = "https://congresoqroo.gob.mx/iniciativas/?legislatura={0}&ente=&search_text=&page={1}"
MAX_PAGES = 15
ITEM = re.compile(r'<li class="collection-item">(.*?)</li>', re.S)
FILE = re.compile(r"/(\d+)\.?_[^/\"]*\.pdf", re.I)


def file_id(href):
    """The key from the PDF's file name: its leading sequence number in the
    older uploads ('1421._INICIATIVA_471_...' -> '1421'), else the whole
    stem of the newer ones ('INI-XVIII-20260925-132215')."""
    m = FILE.search(href or "")
    if m:
        return m.group(1)
    stem = re.search(r"/([A-Za-z0-9-]{8,})\.pdf$", href or "", re.I)
    return stem.group(1) if stem else None


def tags(body, label):
    m = re.search(label + r"\s*</strong></span>(.*?)(?:<br>\s*<(?:span class=\"fecha-coleccion\"|div class=\"row\")|$)",
                  body, re.S | re.I)
    if not m:
        return None
    got = [clean(t) for t in re.findall(r'<span class="etiqueta[^"]*">(.*?)</span>', m.group(1), re.S)]
    return "; ".join(g for g in got if g) or None


def parse(markup):
    out = []
    for body in ITEM.findall(markup or ""):
        when = re.search(r'class="fecha-documento[^"]*">(.*?)</span>', body, re.S)
        link = re.search(r'<p class="texto-coleccion"><a href="([^"]+)"[^>]*>(.*?)</a>', body, re.S)
        if not (when and link):
            continue
        ident = file_id(link.group(1))
        title = clean(link.group(2))
        if not (ident and title):
            continue
        status = re.search(r'class="etiqueta estilo-etiqueta[^"]*">(.*?)</span>', body, re.S)
        promoters = tags(body, r"Promotor\(es\):")
        out.append({
            "state": "qroo", "source_id": "{0}/{1}".format(LEGISLATURE, ident),
            "legislature": LEGISLATURE, "kind": kind_of(title), "title": title,
            "presenter": promoters, "party": party_in(title),
            "presented": date(clean(when.group(1))), "turno": tags(body, r"Turnada a:"),
            "status": clean(status.group(1)) if status else None, "status_date": None,
            "url": link.group(1),
        })
    return out


def collect(ctx, since):
    got = []
    for n in range(1, MAX_PAGES + 1):
        if ctx.stop():
            break
        page = ctx.text(PAGE.format(LEGISLATURE, n), "qroo-iniciativas-{0}".format(n), archive=True)
        if page is None:
            break
        items = parse(page)
        if not items:
            if n == 1:
                ctx.gap("qroo: the first list page had no iniciativas the reader recognises")
            break
        keep = [it for it in items if since_ok(it["presented"], since)]
        got += keep
        if not keep:
            break
    return got
