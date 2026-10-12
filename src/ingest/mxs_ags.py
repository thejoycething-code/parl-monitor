"""Aguascalientes: the Congress's Agenda Legislativa JSON (12 October 2026).

congresoags.gob.mx's iniciativas page fills its table from
/LegislativeAgenda/GetPagedData (a DataTables back end, no key):
legislatureId=66, promotionTypeId=3 (iniciativas), page and pageSize,
newest first (1,194 iniciativas of the LXVI on 12 October 2026). Each record
carries agendaNumber ('IN_LXVI_1231'), the text (which names the author and
group), presentationDate, turnDate, the committees and the resolution
("PENDIENTE", "APROBADO", "DECRETO"). robots.txt answers 404 (no rules).
A run reads pages of 100 until a page holds nothing dated from `since`.
"""

from __future__ import annotations

from src.ingest.mxs_common import clean, date, kind_of, party_in, since_ok

READER = "Agenda Legislativa JSON (congresoags.gob.mx/LegislativeAgenda), newest first"
BASE = "https://congresoags.gob.mx/LegislativeAgenda/"
PAGE = BASE + "GetPagedData?legislatureId={0}&promotionTypeId=3&page={1}&pageSize=100&searchTerm="
LEGISLATURE_ID = 66
MAX_PAGES = 15
BY = __import__("re").compile(r"presentad[ao]s? por (?:el |la |los |las )?(.+?)\.?$", 2)


def parse(reply):
    out = []
    for r in (reply or {}).get("data") or []:
        ident, text = r.get("agendaNumber") or r.get("id"), clean(r.get("content"))
        if not ident or not text:
            continue
        by = BY.search(text)
        presenter = by.group(1) if by else None
        committees = "; ".join(clean(c.get("description")) or "" for c in r.get("commissions") or [])
        resolution = clean(r.get("resolution"))
        out.append({
            "state": "ags", "source_id": str(ident), "legislature": "LXVI",
            "kind": "decreto" if (resolution or "").upper() == "DECRETO" else kind_of(text),
            "title": text, "presenter": presenter, "party": party_in(presenter),
            "presented": date(r.get("presentationDate")), "turno": committees or None,
            "status": resolution, "status_date": None,
            "url": BASE + "Download?id={0}".format(r["id"]) if r.get("id") else None,
        })
    return out


def collect(ctx, since):
    got = []
    for n in range(1, MAX_PAGES + 1):
        if ctx.stop():
            break
        url = PAGE.format(LEGISLATURE_ID, n)
        if not ctx.allowed(url):
            ctx.gap("robots.txt disallows {0}; not fetched".format(url))
            break
        try:
            reply = ctx.client.get_json(url, ctx.feed, "ags-agenda-{0}".format(n))
        except Exception as exc:  # noqa: BLE001 -- FetchError or a reply that is not JSON
            ctx.gap("{0}: {1}".format(url, getattr(exc, "cause", exc)))
            break
        items = parse(reply)
        if not items:
            if n == 1:
                ctx.gap("ags: the agenda JSON returned no iniciativas")
            break
        keep = [it for it in items if since_ok(it["presented"], since)]
        got += keep
        if not keep:
            break
    return got
