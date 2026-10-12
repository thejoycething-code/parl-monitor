"""San Luis Potosí: the decrees the Congress publishes in the Periódico Oficial
del Estado "Plan de San Luis" (12 October 2026).

WHY THE GAZETTE. The Congress's own site (congresosanluis.gob.mx) answers
every request with a Sucuri JavaScript challenge, which is never solved or
bypassed (docs/mexico-regions-scope.md). The state's official gazette is a
different host, run by the Secretaría General de Gobierno, and publishes
every decree the Legislature adopts, under the issuing authority "Congreso
del Estado". Adopted decrees only: no bills in passage.

SOURCE. periodicooficial.slp.gob.mx, robots.txt `User-agent: *` /
`Disallow:` (everything allowed, measured 12 October 2026). Its "Consulta
del periódico" page (/menu/consulta/periodico) is a Vue app that reads the
site's own JSON with no key, token or login:

    GET /api/publicacion/busqueda/filtro/gt?fechaInicio=YYYY-MM-DD
        &fechaFin=YYYY-MM-DD&autoridadId=287&tipo=disposiciones
        &tipoPalabra=titulo&order=recent

(autoridadId 287 is "Congreso del Estado" in /api/autoridad/gt). One reply
for the whole window: 34 decrees from 10 August to 9 October 2026, 381 from
September 2025, in about a second. The page loads Google's reCAPTCHA
script, but the search API answered without any token; nothing was solved.
The site rate-limits bursts ("Numero de solicitudes excedidas"), so a run
asks once.

KEY: the gazette's own publication id, under 'po/' ('slp/po/20020'), so a
gazette item never collides with a congress item if the Congress lets us in
later. Title: the gazette's own words ("DECRETO 0611.- Que reforma ...").
"""

from __future__ import annotations

from urllib.parse import urlencode

from src.http import FetchError
from src.ingest.mxs_common import clean, date, since_ok

READER = "Periódico Oficial (periodicooficial.slp.gob.mx), decrees issued by the Congreso del Estado"
API = "https://periodicooficial.slp.gob.mx/api/publicacion/busqueda/filtro/gt"
PAGE = "https://periodicooficial.slp.gob.mx/menu/consulta/periodico"
CONGRESO = 287
LEGISLATURE = "LXIV"


def search_url(since, until):
    return API + "?" + urlencode({
        "fechaInicio": since, "fechaFin": until, "autoridadId": CONGRESO,
        "tipo": "disposiciones", "tipoPalabra": "titulo", "order": "recent"})


def parse(reply):
    out = []
    groups = (reply or {}).get("agrupadas") or {}
    for name, rows in groups.items():
        if name == "ordinaria_2" or not isinstance(rows, list):
            continue                                   # judicial and other notices
        for r in rows:
            if not isinstance(r, dict) or r.get("id") is None:
                continue
            if r.get("id_emisor") not in (None, CONGRESO) and \
                    "congreso" not in (r.get("autoridad_emisora") or "").lower():
                continue
            title = clean(r.get("titulo"))
            if not title:
                continue
            out.append({
                "state": "slp", "source_id": "po/{0}".format(r["id"]),
                "legislature": LEGISLATURE, "kind": "decreto", "title": title,
                "presenter": "Congreso del Estado (Periódico Oficial)", "party": None,
                "presented": date(r.get("fecha_publicacion")), "turno": None,
                "status": "Publicado en el Periódico Oficial",
                "status_date": date(r.get("fecha_publicacion")), "url": PAGE,
            })
    return out


def collect(ctx, since, today=None):
    import datetime
    until = today or datetime.date.today().isoformat()
    url = search_url(since or "2025-09-01", until)
    if not ctx.allowed(url):
        ctx.gap("robots.txt disallows {0}; not fetched".format(url))
        return []
    try:
        reply = ctx.client.get_json(url, ctx.feed, "slp-gazette", archive=False)
    except (FetchError, ValueError) as exc:
        ctx.gap("slp gazette: {0}".format(getattr(exc, "cause", exc)))
        return []
    if not isinstance(reply, dict) or "agrupadas" not in reply:
        ctx.gap("slp gazette: the search API answered without its 'agrupadas' lists")
        return []
    return [it for it in parse(reply) if since_ok(it["presented"], since)]
