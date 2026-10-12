"""Oaxaca: the Congress's iniciativas and acuerdos, one table per year (12 October 2026).

congresooaxaca.gob.mx/iniciativas-acuerdos/<year>.html ('primero' for the
LXVI Legislature's first year, 19 November 2024 to 11 November 2025;
'segundo' for the second, 899 to 1887 on 12 October 2026) is one HTML
table: No., FECHA SESIÓN, TIPO (Iniciativa, Proposición con Punto de
Acuerdo, Oficio), PROPONENTE, PARTIDO, CONTENIDO, the document, TURNADO and
ESTADO QUE GUARDA ("En Estudio", "Aprobado"). The richest of the states.
robots.txt answers 404 (no rules). A run reads the current year's page, and
the next one's when it exists (a 404 is not a gap). Oficios (letters from
other authorities) are left out.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from src.ingest.mxs_common import clean, date, hrefs, kind_of, party_in, rows, since_ok
from src.http import FetchError

READER = "iniciativas y acuerdos tables by year (congresooaxaca.gob.mx)"
BASE = "https://congresooaxaca.gob.mx/iniciativas-acuerdos/"
YEARS = ("segundo", "tercero")      # the current year, and the next once it opens
LEGISLATURE = "LXVI"
# The LXVI's documents live on docs66.; on 12 October 2026 'tercero.html'
# still held the LXV's third year (2023, documents on docs65.), so a row
# whose document is on another legislature's host is not ours.
DOCS_HOST = "docs66."


def doc_url(href, page_url=BASE):
    """The site is a mirrored export: '../../../docs66.congresooaxaca.gob.mx/x.pdf'
    means https://docs66.congresooaxaca.gob.mx/x.pdf."""
    m = re.search(r"(docs\d+\.congresooaxaca\.gob\.mx/.*)$", href)
    return "https://" + m.group(1) if m else urljoin(page_url, href)


def parse(markup, page_url=BASE):
    out = []
    for _attrs, cells in rows(markup):
        cells = [c for i, c in enumerate(cells) if i % 2 == 0] if len(cells) >= 17 else cells
        if len(cells) < 9:
            continue
        number, tipo = clean(cells[0]), clean(cells[2])
        if not number or not re.match(r"^\d+$", number) or (tipo or "").upper() == "OFICIO":
            continue
        title = clean(cells[5])
        if not title:
            continue
        docs = hrefs(cells[6])
        if docs and re.search(r"docs\d+\.congresooaxaca", docs[0]) and DOCS_HOST not in docs[0]:
            continue                 # an older legislature's row (see the docstring)
        presenter = clean(cells[3])
        party = clean(cells[4])
        out.append({
            "state": "oax", "source_id": "{0}/{1}".format(LEGISLATURE, number),
            "legislature": LEGISLATURE,
            "kind": "punto" if "PUNTO" in (tipo or "").upper() else (
                "other" if (tipo or "").upper().startswith("ACUERDO") else kind_of(tipo or title)),
            "title": title, "presenter": presenter,
            "party": None if not party or "," in party else (
                party_in(party) or (party if len(party) <= 12 else None)),
            "presented": date(clean(cells[1])), "turno": clean(cells[7]),
            "status": clean(cells[8]), "status_date": None,
            "url": doc_url(docs[0], page_url) if docs else None,
        })
    return out


def collect(ctx, since):
    got = []
    for year in YEARS:
        url = BASE + year + ".html"
        if not ctx.allowed(url):
            ctx.gap("robots.txt disallows {0}; not fetched".format(url))
            continue
        try:
            page = ctx.client.get_text(url, ctx.feed, "oax-" + year, archive=True)
        except FetchError as exc:
            if "404" in str(exc.cause) and year != YEARS[0]:
                continue                     # next year's page not open yet
            ctx.gap("{0}: {1}".format(url, exc.cause))
            continue
        items = parse(page, url)
        if not items and year == YEARS[0]:
            ctx.gap("oax: the {0} year table had no rows the reader recognises".format(year))
        got += [it for it in items if since_ok(it["presented"], since)]
    return got
