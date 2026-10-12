"""Tabasco: the Congress's iniciativas table (WordPress, 12 October 2026).

congresotabasco.gob.mx/iniciativas/ is a Posts Table Pro table of the
`documento` post type with every row of the legislature in the page (601
rows of the LXV, newest first, about 620 KB, measured 12 October 2026):
number, Asunto, Turnado a, Presentada por, Fecha presentada (dd/mm/yyyy),
quarter, year and the document. A few Proposiciones con Punto de Acuerdo are
listed among them. robots.txt disallows only /wp-admin/ and a cache path.

KEY: the table's own number within the legislature, prefixed with it
('tab/LXV/603'); the WordPress post id is kept nowhere (the number is what
the Congress cites). There is no status column: the table records the turn
to committee only, and the edition shows these items as new.
"""

from __future__ import annotations

import re

from src.ingest.mxs_common import clean, date, hrefs, kind_of, party_in, rows, since_ok

READER = "iniciativas table (congresotabasco.gob.mx/iniciativas/)"
URL = "https://congresotabasco.gob.mx/iniciativas/"
LEGISLATURE = "LXV"


def parse(markup, legislature=LEGISLATURE):
    out = []
    for attrs, cells in rows(markup):
        if "post-row" not in attrs or len(cells) < 5:
            continue
        number, title = clean(cells[0]), clean(cells[1])
        if not number or not re.match(r"^\d+[A-Za-z]?$", number) or not title:
            continue
        docs = hrefs(cells[7]) if len(cells) > 7 else []
        presenter = clean(cells[3])
        out.append({
            "state": "tab", "source_id": "{0}/{1}".format(legislature, number),
            "legislature": legislature, "kind": kind_of(title), "title": title,
            "presenter": presenter, "party": party_in(presenter),
            "presented": date(clean(cells[4])), "turno": clean(cells[2]),
            "status": None, "status_date": None, "url": docs[0] if docs else None,
        })
    return out


def collect(ctx, since):
    page = ctx.text(URL, "tab-iniciativas", archive=True)
    if page is None:
        return []
    items = parse(page)
    if not items:
        ctx.gap("tab: the iniciativas table had no rows the reader recognises")
    return [it for it in items if since_ok(it["presented"], since)]
