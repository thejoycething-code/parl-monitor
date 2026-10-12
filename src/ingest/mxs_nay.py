"""Nayarit: the Congress's Proceso Legislativo JSON (12 October 2026).

procesolegislativo.congresonayarit.gob.mx is a Vue app over a JSON host the
app itself calls, with no key: utics.congresonayarit.gob.mx/iniciativas/
tabla/XXXIV returns every iniciativa of the XXXIV Legislature in one array
(371 on 12 October 2026, about 300 KB): numero, descripcion,
fecha_recepcion, origen (the author), fecha_pleno, turno_a_comision,
dictamen, estatus and the PDF. robots.txt answers 404 on that host.

KEY: 'XXXIV/<numero>'. The status ("En estudio", "Dictaminada") is the
source's own; the record's updated_at dates a change of status.
"""

from __future__ import annotations

from src.ingest.mxs_common import clean, date, kind_of, party_in, since_ok

READER = "Proceso Legislativo JSON (utics.congresonayarit.gob.mx), whole legislature"
LEGISLATURE = "XXXIV"
URL = "https://utics.congresonayarit.gob.mx/iniciativas/tabla/" + LEGISLATURE


def parse(reply):
    out = []
    for r in reply if isinstance(reply, list) else []:
        number, text = r.get("numero"), clean(r.get("descripcion"))
        if number is None or not text or r.get("visible") == 0:
            continue
        status = clean(r.get("estatus"))
        changed = date(r.get("updated_at"))
        created = date(r.get("created_at"))
        presenter = clean(r.get("origen"))
        out.append({
            "state": "nay", "source_id": "{0}/{1}".format(r.get("legislatura") or LEGISLATURE, number),
            "legislature": r.get("legislatura") or LEGISLATURE, "kind": kind_of(text),
            "title": text, "presenter": presenter, "party": party_in(presenter),
            "presented": date(r.get("fecha_recepcion")),
            "turno": clean(r.get("turno_a_comision")), "status": status,
            # updated_at moves when the record is edited after it was entered.
            "status_date": changed if changed and changed != created else None,
            "url": r.get("iniciativa") or None,
        })
    return out


def collect(ctx, since):
    if not ctx.allowed(URL):
        ctx.gap("robots.txt disallows {0}; not fetched".format(URL))
        return []
    try:
        reply = ctx.client.get_json(URL, ctx.feed, "nay-iniciativas")
    except Exception as exc:  # noqa: BLE001
        ctx.gap("{0}: {1}".format(URL, getattr(exc, "cause", exc)))
        return []
    items = parse(reply)
    if not items:
        ctx.gap("nay: the iniciativas JSON returned no items")
    return [it for it in items if since_ok(it["presented"], since)
            or since_ok(it["status_date"] or "", since)]
