"""Querétaro: what the Legislature publishes in "La Sombra de Arteaga", the
state's official gazette, from its annual index (12 October 2026).

WHY THE GAZETTE. The Legislature's own list (legislaturaqueretaro.gob.mx)
answers only over plain HTTP, and the pipeline fetches nothing in the clear
(docs/mexico-regions-scope.md). The gazette is a different host, run by the
Executive's Secretaría de Gobierno, and answers over HTTPS. Adopted laws,
decrees and acuerdos only: no bills in passage.

SOURCE. lasombradearteaga.segobqueretaro.gob.mx (no robots.txt: 404, so no
rules; measured 12 October 2026). Its "Índices" page links one PDF per year
(getfile.php?p1=indice-2026.pdf, 1.4 MB on 12 October 2026, current to P.
O. No. 80 of 2 October). The index lists every edition ("P. O. No. 66   7
de agosto de 2026") and, under each issuing authority in capitals, the
title of each act. The reader keeps the acts under PODER LEGISLATIVO: "Ley
que reforma el artículo 80 de la Ley de Salud del Estado de Querétaro.",
"Decreto por el que la Sexagésima Primera Legislatura ...", "Acuerdo por el
que ... exhorta ...". One request a run (two in January, when last year's
index may still be growing).

KEY: the edition and the act's place under PODER LEGISLATIVO in it
('qro/po/2026/66/4'); the index only ever appends.
"""

from __future__ import annotations

import datetime
import re

from src.ingest.mxs_common import date, since_ok
from src.prov_fetch import Unreadable, pdf_text

READER = "La Sombra de Arteaga annual index (lasombradearteaga.segobqueretaro.gob.mx), PODER LEGISLATIVO acts"
BASE = "https://lasombradearteaga.segobqueretaro.gob.mx/"
INDEX = BASE + "getfile.php?p1=indice-{0}.pdf"
LEGISLATURE = "LXI"

EDITION = re.compile(r"P\.\s*O\.\s*No\.\s*(\d+)\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})")
STARTS = ("Ley", "Leyes", "Decreto", "Acuerdo", "Dictamen", "Convocatoria", "Reglamento",
          "Fe de erratas", "Declaratoria", "Resolución", "Lineamientos", "Aviso", "Código",
          "Minuta", "Iniciativa", "Informe", "Exhorto")
SPLIT = re.compile(r"(?<=[.»”\"])\s+(?=(?:" + "|".join(re.escape(s) for s in STARTS) + r")\b)")


def _header(line):
    s = line.strip()
    return len(s) >= 4 and not re.search(r"[a-záéíóúñü]", s) and re.search(r"[A-ZÁÉÍÓÚÑ]{3}", s)


def kind_of(title):
    t = title.lower()
    if t.startswith(("ley", "decreto", "código")):
        return "decreto"
    if t.startswith("acuerdo"):
        return "punto"
    return "other"


def parse_index(text, year):
    out = []
    text = (text or "").replace("=====PAGE", "\n")
    marks = list(EDITION.finditer(text))
    for i, m in enumerate(marks):
        block = text[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        lines = block.split("\n")
        try:
            at = next(k for k, ln in enumerate(lines) if ln.strip() == "PODER LEGISLATIVO")
        except StopIteration:
            continue
        body = []
        for ln in lines[at + 1:]:
            if _header(ln):
                break
            if ln.strip():
                body.append(ln.strip())
        joined = re.sub(r"\s+", " ", " ".join(body)).strip()
        if not joined:
            continue
        when = date(m.group(2))
        for n, title in enumerate(t.strip() for t in SPLIT.split(joined)):
            if not title:
                continue
            out.append({
                "state": "qro", "source_id": "po/{0}/{1}/{2}".format(year, m.group(1), n + 1),
                "legislature": LEGISLATURE, "kind": kind_of(title), "title": title,
                "presenter": "Poder Legislativo (La Sombra de Arteaga)", "party": None,
                "presented": when, "turno": None,
                "status": "Publicado en La Sombra de Arteaga (P. O. No. {0})".format(m.group(1)),
                "status_date": when, "url": INDEX.format(year),
            })
    return out


def collect(ctx, since, today=None):
    today = datetime.date.fromisoformat(today) if today else datetime.date.today()
    years = [today.year]
    if since and since[:4].isdigit() and int(since[:4]) < today.year and today.month == 1:
        years.insert(0, today.year - 1)
    out = []
    for year in years:
        raw = ctx.bytes(INDEX.format(year), "qro-indice-{0}".format(year))
        if raw is None:
            continue
        try:
            text = pdf_text(raw)
        except Unreadable as exc:
            ctx.gap("qro gazette: indice-{0}.pdf: {1}".format(year, exc))
            continue
        got = parse_index(text, year)
        if not got:
            ctx.gap("qro gazette: no PODER LEGISLATIVO entries in indice-{0}.pdf".format(year))
        out += got
    return [it for it in out if since_ok(it["presented"], since)]
