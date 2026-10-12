"""Yucatán: the Congress's iniciativas table (12 October 2026).

congresoyucatan.gob.mx/gaceta/iniciativas is one HTML table of every
iniciativa since 2015 (1,384 rows, 398 of the LXIV, about 1.5 MB, measured
12 October 2026), oldest first, with columns LEGISLATURA, DESCRIPCIÓN, FECHA
PRESENTADA (ISO), PRESENTADA POR, FECHA TURNADA, COMISIÓN PERMANENTE and the
document. There is no folio and no status column. robots.txt allows all.

KEY. The source has no number, so an item is keyed by the document's own
upload id, the hex prefix of its file name under /storage/uploadCey/
('096dff' in '096dff_30-SEP-26 REF-LEY DE VICTIMAS.pdf'); a row without a
document is keyed by a short hash of its date and description. Status is
"Turnada a comisión" with its date, the only step the table records.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import quote, urljoin

from src.ingest.mxs_common import clean, date, hrefs, kind_of, party_in, rows, since_ok

READER = "Gaceta iniciativas table (congresoyucatan.gob.mx/gaceta/iniciativas)"
URL = "https://congresoyucatan.gob.mx/gaceta/iniciativas"
UPLOAD = re.compile(r"/uploadCey/([0-9a-f]{5,12})_", re.I)


def source_id(doc, presented, title):
    m = UPLOAD.search(doc or "")
    if m:
        return m.group(1).lower()
    return "h" + hashlib.sha1("{0}|{1}".format(presented, title).encode("utf-8")).hexdigest()[:10]


def parse(markup):
    out = []
    for _attrs, cells in rows(markup):
        if len(cells) < 6:
            continue
        leg, title = clean(cells[0]), clean(cells[1])
        presented = date(clean(cells[2]))
        if not title or not presented or not re.match(r"^[LXVI]+$", leg or ""):
            continue
        docs = hrefs(cells[6]) if len(cells) > 6 else []
        doc = docs[0] if docs else None
        turned = date(clean(cells[4]))
        presenter = clean(cells[3])
        out.append({
            "state": "yuc", "source_id": source_id(doc, presented, title), "legislature": leg,
            "kind": kind_of(title), "title": title, "presenter": presenter,
            "party": party_in(presenter), "presented": presented, "turno": clean(cells[5]),
            "status": "Turnada a comisión" if turned else None, "status_date": turned,
            "url": quote(urljoin(URL, doc), safe=":/?=&%") if doc else None,
        })
    return out


def collect(ctx, since):
    page = ctx.text(URL, "yuc-iniciativas", archive=True)
    if page is None:
        return []
    items = parse(page)
    if not items:
        ctx.gap("yuc: the iniciativas table had no rows the reader recognises")
    return [it for it in items if since_ok(it["presented"], since)
            or since_ok(it["status_date"] or "", since)]
