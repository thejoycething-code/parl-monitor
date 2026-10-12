"""Sinaloa: the Congress's Gaceta app and its public JSON API (12 October 2026).

www.congresosinaloa.gob.mx/iniciativas/ embeds an AngularJS app at
gaceta.congresosinaloa.gob.mx, which reads a JSON API the page itself calls,
with no key or login: POST /api/obtenerIniciativas {"nu_legislatura": "65"}
returns every iniciativa of the legislature in one reply (1,883 items, about
3.2 MB, measured 12 October 2026), with date presented, author, committee,
both resolutions, the approval and publication dates and the vote totals.
There is no paging, so a run reads the whole list and keeps what is dated
from `since` (presented, or with a resolution, approval or publication
dated from then). The gaceta host has no robots.txt (404).

Status, verbatim from the source: the latest of the iniciativa's resolution
("Se Toma en Consideración"), the dictamen's ("Se Aprueba") and the
publication in the Periódico Oficial, each with its date.
"""

from __future__ import annotations

import json

from src.ingest.mxs_common import clean, date, kind_of, party_in, since_ok

READER = "Gaceta API (gaceta.congresosinaloa.gob.mx), every iniciativa of the legislature"
API = "https://gaceta.congresosinaloa.gob.mx/api/"
LEGISLATURE = "65"
ROMAN = {"64": "LXIV", "65": "LXV", "66": "LXVI"}
PDF = "https://gaceta.congresosinaloa.gob.mx:3001/pdfs/iniciativas/{0}/Iniciativa_{1}.pdf"


def status_of(r):
    """(status words, ISO date) of the latest step the record carries."""
    steps = []
    ini = clean(r.get("resolucionini"))
    if ini:
        steps.append((date(r.get("fechaini1")) or date(r.get("determinacion")), 0, ini))
    dic = clean(r.get("resoluciondic"))
    if dic:
        steps.append((date(r.get("fechaaprobacion")) or date(r.get("fechadic1")), 1,
                      "Dictamen: " + dic))
    pub = date(r.get("fechaPubli"))
    if pub:
        dec = clean(r.get("decreto"))
        steps.append((pub, 2, "Publicado en el Periódico Oficial" + (
            " (Decreto {0})".format(dec) if dec else "")))
    if not steps:
        return None, None
    dated = [s for s in steps if s[0]]
    if not dated:
        return steps[-1][2], None
    when, _order, words = max(dated)
    return words, when


def parse(reply, legislature=LEGISLATURE):
    out = []
    got = reply if isinstance(reply, list) else []
    if isinstance(reply, dict):
        for k in ("grupo", "individual", "conjunto"):
            got += reply.get(k) or []
    for r in got:
        rid = r.get("id")
        title = clean(r.get("iniciativa"))
        if rid is None or not title:
            continue
        status, when = status_of(r)
        leg = clean(r.get("legis")) or legislature
        presenter = clean(r.get("presentada"))
        out.append({
            "state": "sin", "source_id": str(rid), "legislature": ROMAN.get(leg, leg),
            "kind": "decreto" if date(r.get("fechaPubli")) else kind_of(title),
            "title": title, "presenter": presenter, "party": party_in(presenter),
            "presented": date(r.get("fecha")), "turno": clean(r.get("comisiones")),
            "status": status, "status_date": when,
            "url": PDF.format(leg, rid) if r.get("pdf") else None,
        })
    return out


def collect(ctx, since):
    reply = ctx.post_json(API + "obtenerIniciativas",
                          json.dumps({"nu_legislatura": LEGISLATURE}), "sin-iniciativas")
    if reply is None:
        return []
    items = parse(reply)
    if not items:
        ctx.gap("sin: the iniciativas API answered with no items")
    return [it for it in items
            if since_ok(it["presented"], since) or since_ok(it["status_date"] or "", since)]
