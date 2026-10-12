"""Chihuahua: the Congress's Proceso Legislativo listing (12 October 2026).

www.congresochihuahua.gob.mx/biblioteca/procesoLegislativo.php lists every
asunto of the LXVIII Legislature, newest first, ten to a page (1,196
results on 12 October 2026), each with its Asunto number, the text, the
promoventes with their party in brackets, the date presented ("06 octubre
2026"), the committee it was sent to ("Se Turnó a") and its status
("Pendiente", "Dictaminada"). A run reads pages from the first until a page
holds nothing dated from `since` (a cap of MAX_PAGES), following the
listing's own "pag" links. robots.txt allows us (it names only AI and SEO
crawlers).

A full export of the legislature (seguimientoAsuntosXLS.php, one 20 MB HTML
table of 52 columns with every turn, dictamen and publication date) exists
and would give stage moves; it is not read yet (docs/mexico-regions-scope.md).
"""

from __future__ import annotations

import re

from src.ingest.mxs_common import clean, date, hrefs, kind_of, party_in, since_ok

READER = "Proceso Legislativo listing (congresochihuahua.gob.mx/biblioteca), newest first"
BASE = "https://www.congresochihuahua.gob.mx/biblioteca/"
LEGISLATURE_ID = 68
LEGISLATURE = "LXVIII"
PAGE = (BASE + "procesoLegislativo.php?pag={0}&idlegislatura={1}&idanio=&idperiodo=&palabra="
        "&idestatusiniciativa=&idhistorialdiputado=&iniciativa=&idcomision=&decreto=&acuerdo="
        "&iniciativaCU=&buscar=&turno=")
MAX_PAGES = 120
ARTICLE = re.compile(r'<div class="title5">\s*Asunto\s+(\d+)\s*</div>(.*?)</figure>', re.S | re.I)


def field(body, label):
    m = re.search(r"<strong>\s*" + label + r"[^<]*</strong>(.*?)</p>", body, re.S | re.I)
    return clean(m.group(1)) if m else None


def parse(markup):
    out = []
    for number, body in ARTICLE.findall(markup or ""):
        m = re.search(r"<p[^>]*>(.*?)</p>", body, re.S)
        title = clean(m.group(1)) if m else None
        if not title:
            continue
        presenter = field(body, r"Iniciador o Promovente")
        docs = [h for h in hrefs(body) if "archivosIniciativas" in h]
        status = field(body, r"Estatus")
        out.append({
            "state": "chih", "source_id": "{0}/{1}".format(LEGISLATURE, number),
            "legislature": LEGISLATURE, "kind": kind_of(title), "title": title,
            "presenter": presenter, "party": party_in(presenter),
            "presented": date(field(body, r"Fecha de presentaci")),
            "turno": field(body, r"Se Turn"), "status": status, "status_date": None,
            "url": docs[0] if docs else None,
        })
    return out


def collect(ctx, since):
    got = []
    for n in range(1, MAX_PAGES + 1):
        if ctx.stop():
            break
        page = ctx.text(PAGE.format(n, LEGISLATURE_ID), "chih-proceso-{0}".format(n),
                        archive=True)
        if page is None:
            break
        items = parse(page)
        if not items:
            if n == 1:
                ctx.gap("chih: the first listing page had no asuntos the reader recognises")
            break
        keep = [it for it in items if since_ok(it["presented"], since)]
        got += keep
        if not keep:
            break
    return got
