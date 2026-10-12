"""Chiapas: the Congress's Trabajo Legislativo table (12 October 2026).

web.congresochiapas.gob.mx/trabajo-legislativo/trabajo-legislativo is one
HTML page (about 1.8 MB, 2,284 rows back to 2017; "ULTIMA ACTUALIZACIÓN 08
DE OCTUBRE DE 2026" on 12 October 2026) with one table per legislature, the
current one (LXIX) first, newest first: a display number, the title (the
author is inside it, "PRESENTADA POR ..."), the date (dd.mm.yyyy) and the
documents of each stage (iniciativa INI_<n>.pdf, oficio de turnado, dictamen,
minuta, decreto), with a "✓ Aprobado" row under an approved item. No
committee or party column. robots.txt disallows only Joomla's system paths.

KEY: the number in the iniciativa's own file name ('chis/LXIX/1173' from
INI_1173.pdf), not the display number, which shifts as items are added.
Status is the approval mark when present, else the furthest stage document
listed ("Dictamen publicado", "Turnada"); the table dates none of them.
"""

from __future__ import annotations

import re

from src.ingest.mxs_common import clean, date, hrefs, kind_of, party_in, rows, since_ok

READER = "Trabajo Legislativo table (web.congresochiapas.gob.mx), current legislature"
URL = "https://web.congresochiapas.gob.mx/trabajo-legislativo/trabajo-legislativo"
LEGISLATURE = "LXIX"
INI = re.compile(r"/INI_(\d+[A-Z]?)\.pdf", re.I)
BY = re.compile(r",?\s*PRESENTADA POR (?:EL |LA |LOS |LAS )?(.+?)\.?$", re.I)


def current_table(markup):
    """The first legislature's table only (the page lists older ones after it)."""
    start = (markup or "").find("<table")
    end = (markup or "").find("</table>", start)
    return markup[start:end] if start >= 0 and end > start else ""


def stage(docs):
    joined = " ".join(docs).upper()
    if "INI_DEC_" in joined:
        return "Decreto publicado"
    if "INI_MIN_" in joined:
        return "Minuta"
    if "INI_DIC_" in joined:
        return "Dictamen"
    if "INI_OFI_" in joined:
        return "Turnada (oficio de turnado)"
    return None


def parse(markup):
    out = []
    for _attrs, cells in rows(current_table(markup)):
        if len(cells) == 1 and out:
            mark = clean(cells[0])
            if mark and "aprobad" in mark.lower():
                out[-1]["status"] = mark.lstrip("✓ ").strip()
            continue
        if len(cells) < 8:
            continue
        title, presented = clean(cells[1]), date(clean(cells[2]))
        docs = [h for c in cells[3:] for h in hrefs(c)]
        m = next((INI.search(h) for h in docs if INI.search(h)), None)
        if not (title and presented and m):
            continue
        by = BY.search(title)
        presenter = by.group(1).strip() if by else None
        out.append({
            "state": "chis", "source_id": "{0}/{1}".format(LEGISLATURE, m.group(1)),
            "legislature": LEGISLATURE,
            "kind": "decreto" if stage(docs) == "Decreto publicado" else kind_of(title),
            "title": title, "presenter": presenter, "party": party_in(presenter),
            "presented": presented, "turno": None, "status": stage(docs), "status_date": None,
            "url": docs[0].split("?")[0] if docs else None,
        })
    return out


def collect(ctx, since):
    page = ctx.text(URL, "chis-trabajo", archive=True)
    if page is None:
        return []
    items = parse(page)
    if not items:
        ctx.gap("chis: the Trabajo Legislativo table had no rows the reader recognises")
    return [it for it in items if since_ok(it["presented"], since)]
