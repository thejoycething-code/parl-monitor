"""Tamaulipas: the Congress's iniciativas, one table per period (12 October 2026).

congresotamaulipas.gob.mx/TrabajoLegislativo/Iniciativas/Iniciativas.asp
links one listing per period of the 66th Legislature
(ListadoIniciativas.asp?IdPeriodoCongreso=<n>&Legislatura=66; 110 to 121
on 12 October 2026, 118 the current one). Each listing is an HTML table:
the PDF (LEG66_INICIATIVA_<folio>_<dd-mm-yyyy>.pdf, which carries the
folio), Fecha Recepción, Epígrafe, Promoventes ("Name(PARTY)"), Turnos and
Estatus ("En estudio", "Dictaminado", "Resuelto"). A run reads the index,
then each period it links, and keeps rows received from `since`; the period
links always come from the index, never typed here. robots.txt carries only
Cloudflare's content-signal preamble, with no rules and no signal set.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from src.ingest.mxs_common import clean, date, hrefs, kind_of, party_in, rows, since_ok

READER = "iniciativas listings by period (congresotamaulipas.gob.mx)"
INDEX = "https://congresotamaulipas.gob.mx/TrabajoLegislativo/Iniciativas/Iniciativas.asp"
LEGISLATURE = "66"
FOLIO = re.compile(r"INICIATIVA_(\d+)_", re.I)
PERIOD = re.compile(r"ListadoIniciativas\.asp\?IdPeriodoCongreso=(\d+)&(?:amp;)?Legislatura=(\d+)")


def periods(markup, legislature=LEGISLATURE):
    """[(period id, url)] the index links for the legislature, newest first."""
    got = {int(p): urljoin(INDEX, "ListadoIniciativas.asp?IdPeriodoCongreso={0}&Legislatura={1}"
                           .format(p, leg))
           for p, leg in PERIOD.findall(markup or "") if leg == legislature}
    return sorted(got.items(), reverse=True)


def parse(markup):
    out = []
    for _attrs, cells in rows(markup):
        if len(cells) != 6:
            continue
        docs = hrefs(cells[0])
        m = FOLIO.search(docs[0]) if docs else None
        title, presented = clean(cells[2]), date(clean(cells[1]))
        if not m or not title or not presented:
            continue
        presenter = clean(cells[3])
        turno = clean(re.sub(r"\)\s*\(", "; ", cells[4] or "")).strip("() ") if cells[4] else None
        out.append({
            "state": "tamps", "source_id": "{0}/{1}".format(LEGISLATURE, m.group(1)),
            "legislature": LEGISLATURE, "kind": kind_of(title), "title": title,
            "presenter": presenter, "party": party_in(presenter), "presented": presented,
            "turno": turno or None, "status": clean(cells[5]), "status_date": None,
            "url": urljoin(INDEX, docs[0]),
        })
    return out


def collect(ctx, since):
    index = ctx.text(INDEX, "tamps-index", encoding="latin-1")
    if index is None:
        return []
    listed = periods(index)
    if not listed:
        ctx.gap("tamps: the index links no period listing for legislature " + LEGISLATURE)
        return []
    got = []
    for pid, url in listed:
        if ctx.stop():
            break
        page = ctx.text(url, "tamps-periodo-{0}".format(pid), encoding="latin-1",
                        archive=True)
        if page is None:
            continue
        items = parse(page)
        keep = [it for it in items if since_ok(it["presented"], since)]
        got += keep
        if items and not keep:
            break          # newest first: an older period holds nothing newer
    return got
