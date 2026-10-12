"""Ciudad de México: the Congress's citizen portal of iniciativas (12 October 2026).

The official list on www.congresocdmx.gob.mx (iniciativas-218-5.html) stopped
on 7 November 2025. The Congress's citizen portal,
ciudadana.congresocdmx.gob.mx/Iniciativa/iniciativas, is current: cards
newest first, twenty to a page (?page=N, 108 pages on 12 October 2026), each
with the date ("8 oct 2026"), the text, "Suscrita por" (the author) and the
group, and a detail page /Iniciativa/iniciativa/<id>. Asked with our
client's JSON-first Accept header it returns the same page as JSON, which
also names the committee (nom_turnado); both forms are read. No status or
number: the portal's own id is the key ('cdmx/8328'). robots.txt on the
portal answers 404 (no rules). A run reads pages from the first until a page
holds nothing dated from `since` (a cap of MAX_PAGES).
"""

from __future__ import annotations

import json
import re

from src.ingest.mxs_common import clean, date, party_in, since_ok

READER = "citizen portal (ciudadana.congresocdmx.gob.mx), newest first"
BASE = "https://ciudadana.congresocdmx.gob.mx"
PAGE = BASE + "/Iniciativa/iniciativas?page={0}"
LEGISLATURE = "III"
MAX_PAGES = 120
CARD = re.compile(r"<article\b(.*?)</article>", re.S | re.I)


JSON_START = re.compile(r'\{\s*"iniciativa"\s*:')


def parse_json(markup):
    """The portal (CakePHP) answers our client's JSON-first Accept header with
    its serialised view: {"iniciativa": [{id_iniciativa, fecha, nombre,
    nom_suscrita, nom_partido, nom_turnado, ...}]}, after a deprecation
    notice printed as HTML (measured 12 October 2026). None when absent.
    `estatus` and `fecha_cierre` belong to the portal's citizen consultation,
    not to the legislative process, and are not stored."""
    m = JSON_START.search(markup or "")
    if not m:
        return None
    try:
        got = json.loads(markup[m.start():])
    except ValueError:
        try:
            got, _end = json.JSONDecoder().raw_decode(markup[m.start():])
        except ValueError:
            return None
    out = []
    for r in got.get("iniciativa") or []:
        ident, title = r.get("id_iniciativa"), clean(r.get("nombre"))
        if not ident or not title:
            continue
        author, group = clean(r.get("nom_suscrita")), clean(r.get("nom_partido"))
        out.append({
            "state": "cdmx", "source_id": str(ident), "legislature": LEGISLATURE,
            "kind": "iniciativa", "title": title,
            "presenter": "{0} ({1})".format(author, group) if author and group else author,
            "party": party_in(group), "presented": date(r.get("fecha")),
            "turno": clean(r.get("nom_turnado")), "status": None, "status_date": None,
            "url": BASE + "/Iniciativa/iniciativa/" + str(ident),
        })
    return out


def parse(markup):
    got = parse_json(markup)
    if got is not None:
        return got
    out = []
    for body in CARD.findall(markup or ""):
        ident = re.search(r"/Iniciativa/iniciativa/(\d+)", body, re.I)
        when = re.search(r"<time>(.*?)</time>", body, re.S | re.I)
        text = re.search(r"postcard__preview-txt[^>]*>(.*?)</div>", body, re.S | re.I)
        if not (ident and when and text):
            continue
        title = clean(text.group(1))
        if not title:
            continue
        who = re.search(r"Suscrita por:\s*<strong>(.*?)</strong>\s*</label>\s*\|\s*<label>(.*?)</label>",
                        body, re.S | re.I)
        author = clean(who.group(1)) if who else None
        group = clean(who.group(2)) if who else None
        out.append({
            "state": "cdmx", "source_id": ident.group(1), "legislature": LEGISLATURE,
            "kind": "iniciativa", "title": title,
            "presenter": "{0} ({1})".format(author, group) if author and group else author,
            "party": party_in(group), "presented": date(clean(when.group(1))), "turno": None,
            "status": None, "status_date": None,
            "url": BASE + "/Iniciativa/iniciativa/" + ident.group(1),
        })
    return out


def collect(ctx, since):
    got = []
    for n in range(1, MAX_PAGES + 1):
        if ctx.stop():
            break
        page = ctx.text(PAGE.format(n), "cdmx-iniciativas-{0}".format(n), archive=True)
        if page is None:
            break
        items = parse(page)
        if not items:
            if n == 1:
                ctx.gap("cdmx: the first portal page had no cards the reader recognises")
            break
        keep = [it for it in items if since_ok(it["presented"], since)]
        got += keep
        if not keep:
            break
    return got
