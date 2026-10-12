"""Baja California: the Congress's iniciativas table (12 October 2026).

www.congresobc.gob.mx/TrabajoLegislativo/Iniciativas is one HTML table
(about 3.9 MB) of every document of the XXV Legislature since 1 August 2024
(2,223 rows on 12 October 2026), newest first: session number, document
number, group or committee, type (INICIATIVA DE LEY, INICIATIVA DE REFORMA,
PROPOSICIÓN, ACUERDO, POSICIONAMIENTO), presenter, where it went or what
became of it ("COMISIONES", "APROBADO POR 23 VOTOS A FAVOR", "APROBADO EN
VOTACION ECONOMICA"), a recorded-vote link, the date (YYYY/MM/DD), the
description and the PDF. robots.txt answers 404: no rules.

KEY: 'XXV/<session>/<document>', the table's own two numbers. The group or
committee column (who brought it) is shown after the presenter, and is the
party only where it is a group's short name. The
outcome column is stored as the status, dated with the row's date, so an
item approved on the day it was presented reads as approved. Recorded votes
per member (Edocvotacion.aspx, behind an ASP.NET session) are not read yet.
Positionings (POSICIONAMIENTO) are speeches, not items, and are left out.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from src.ingest.mxs_common import clean, date, hrefs, rows, since_ok

READER = "iniciativas table (congresobc.gob.mx/TrabajoLegislativo/Iniciativas)"
URL = "https://www.congresobc.gob.mx/TrabajoLegislativo/Iniciativas"
LEGISLATURE = "XXV"
KINDS = {"PROPOSICI": "punto", "ACUERDO": "other", "DICTAMEN": "dictamen", "INICIATIVA": "iniciativa"}


def kind(tipo):
    t = (tipo or "").upper()
    return next((v for k, v in KINDS.items() if t.startswith(k)), "other")


def parse(markup):
    out = []
    for _attrs, cells in rows(markup):
        if len(cells) < 9:
            continue
        session, doc = clean(cells[0]), clean(cells[1])
        if not (session and doc and re.match(r"^\d+$", session) and re.match(r"^\d+$", doc)):
            continue
        tipo, title = clean(cells[3]), clean(cells[8])
        if not title or (tipo or "").upper().startswith("POSICIONAMIENTO"):
            continue
        presented = date(clean(cells[7]))
        group = clean(cells[2])
        outcome = clean(cells[5])
        pdfs = hrefs(cells[9]) if len(cells) > 9 else []
        out.append({
            "state": "bc", "source_id": "{0}/{1}/{2}".format(LEGISLATURE, session, doc),
            "legislature": LEGISLATURE, "kind": kind(tipo),
            "title": "{0}: {1}".format(tipo, title) if tipo else title,
            "presenter": "{0} ({1})".format(clean(cells[4]), group) if group and clean(cells[4])
            else (clean(cells[4]) or group),
            "party": group if group and len(group) <= 12 else None,
            "presented": presented, "turno": None,
            "status": outcome, "status_date": presented if outcome else None,
            "url": urljoin(URL, pdfs[0]) if pdfs else None,
        })
    return out


def collect(ctx, since):
    page = ctx.text(URL, "bc-iniciativas", archive=True)
    if page is None:
        return []
    items = parse(page)
    if not items:
        ctx.gap("bc: the iniciativas table had no rows the reader recognises")
    return [it for it in items if since_ok(it["presented"], since)]
