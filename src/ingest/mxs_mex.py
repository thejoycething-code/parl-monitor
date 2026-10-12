"""Estado de México: the Legislature's iniciativas list (12 October 2026).

legislacion.congresoedomex.gob.mx/asuntosparlamentarios/iniciativas is a
skeleton page that asks the same address again with the header
`X-Requested-With: XMLHttpRequest`, as every jQuery page does; that reply is
4.7 MB of HTML holding all 1,363 iniciativas of the LXII Legislature
(measured 12 October 2026), newest first. We send the same header the page
sends: nothing is bypassed, and robots.txt on the host allows everything.
Each entry: "No. 1363", the author with the group, the title, "Fecha de
presentación: 23 de septiembre, 2026", "Turnada a:" committees, the status
("En estudio", "Aprobada", "Dispensa") and the document. The main site's
own JSON (www.congresoedomex.gob.mx/backend/api/ordenes) answered 500.

KEY: the list's own number within the legislature ('mex/LXII/1363').
Recorded votes per deputy on decrees exist in HTML (votaciondecretos) and
are not read yet.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from src.http import FetchError
from src.ingest.mxs_common import clean, date, hrefs, kind_of, party_in, since_ok

READER = "iniciativas list (legislacion.congresoedomex.gob.mx/asuntosparlamentarios)"
URL = "https://legislacion.congresoedomex.gob.mx/asuntosparlamentarios/iniciativas"
LEGISLATURE = "LXII"
ENTRY = re.compile(r"No\.\s*(\d+)\s*<br>(.*?)</p>", re.S | re.I)
STATUS = re.compile(r"font-weight:\s*bolder[^>]*>\s*<b>(.*?)</b>", re.S | re.I)


def parse(markup, page_url=URL):
    out = []
    for number, body in ENTRY.findall(markup or ""):
        author = re.search(r"Autor:</span>\s*<b>(.*?)</b>", body, re.S | re.I)
        title = re.search(r"fa-scroll\"></i>(.*?)</span>", body, re.S | re.I)
        when = re.search(r"Fecha de presentaci[oó]n:(.*?)</span>", body, re.S | re.I)
        if not (title and when):
            continue
        turned = re.search(r"Turnada a:</span>(.*?)</span>", body, re.S | re.I)
        turno = None
        if turned:
            parts = [clean(p) for p in re.split(r"<br\s*/?>", turned.group(1))]
            turno = "; ".join(p for p in parts if p) or None
        status = STATUS.search(body)
        docs = hrefs(body)
        presenter = clean(author.group(1)) if author else None
        text = clean(title.group(1))
        out.append({
            "state": "mex", "source_id": "{0}/{1}".format(LEGISLATURE, number),
            "legislature": LEGISLATURE, "kind": kind_of(text), "title": text,
            "presenter": presenter.rstrip(".") if presenter else None,
            "party": party_in(presenter), "presented": date(clean(when.group(1))),
            "turno": turno, "status": clean(status.group(1)) if status else None,
            "status_date": None, "url": urljoin(page_url, docs[0]) if docs else None,
        })
    return out


def collect(ctx, since):
    if not ctx.allowed(URL):
        ctx.gap("robots.txt disallows {0}; not fetched".format(URL))
        return []
    try:
        page = ctx.client.get_text(URL, ctx.feed, "mex-iniciativas", archive=True,
                                   headers={"X-Requested-With": "XMLHttpRequest"})
    except FetchError as exc:
        ctx.gap("{0}: {1}".format(URL, exc.cause))
        return []
    items = parse(page)
    if not items:
        ctx.gap("mex: the iniciativas list had no entries the reader recognises")
    return [it for it in items if since_ok(it["presented"], since)]
