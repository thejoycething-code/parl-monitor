"""Durango: the decrees in the Periódico Oficial del Estado (12 October 2026).

WHY THE GAZETTE. The Congress's site (congresodurango.gob.mx) answers UK
addresses with Wordfence's 503 "access from your area has been limited",
and its listings are PDFs (docs/mexico-regions-scope.md). The state's
official gazette is a different host, run by the Secretaría General de
Gobierno, answers from the UK, and prints a table of contents for every
edition in plain HTML. Adopted decrees only: no bills in passage.

SOURCE. periodicooficial.durango.gob.mx (a Next.js site; robots.txt 404, so
no rules; measured 12 October 2026):

  * the home page lists the twelve newest editions (about six weeks: the
    gazette appears on Thursdays and Sundays, plus extraordinary numbers),
    each a link /periodicos/<uuid> with its number and date;
  * each edition page carries its contents as a table: Asunto (DECRETO,
    ACUERDO, CONVOCATORIA ...), Número, Contiene, page.

The reader keeps the DECRETO rows ("DECRETO 445 POR EL QUE SE REFORMA ...").
Decrees in Durango are issued by the Legislature (the Executive's acts are
acuerdos, reglamentos, convenios), so each is reported as the Congress's,
with the gazette named as the source.

KEY: the decree number ('dgo/po/decreto/445'; the LXX Legislature numbers
its decrees in one run), or the edition and row when a row has no number
('dgo/po/<uuid>/<row>').
"""

from __future__ import annotations

import re

from src.ingest.mxs_common import clean, date, since_ok

READER = "Periódico Oficial (periodicooficial.durango.gob.mx), decrees in each edition's contents"
BASE = "https://periodicooficial.durango.gob.mx"
HOME = BASE + "/"
MAX_EDITIONS = 12

CARD = re.compile(r'<a href="(/periodicos/[0-9a-f-]{36})"')
ROW = re.compile(r'<div class="grid grid-cols-5">(.*?)(?=<div class="grid grid-cols-5|</section>|$)', re.S)
SPAN = re.compile(r"<span[^>]*>(.*?)</span>", re.S)
CONTAINS = re.compile(r'<div class="\s*col-span-2[^"]*"[^>]*>(.*?)</div>', re.S)
WHEN = re.compile(r"Lugar y Fecha:.*?</p>", re.S)
NUMBER_IN_TITLE = re.compile(r"^DECRETO\s+(?:No\.?\s*)?(\d+)\b", re.I)


def editions(markup):
    """[(path, ISO date, label)] for the edition cards of the home page."""
    out, seen = [], set()
    pieces = CARD.split(markup or "")
    # split() alternates [before, path, after, path, after ...]
    for i in range(1, len(pieces), 2):
        path = pieces[i]
        if path in seen:
            continue
        seen.add(path)
        text = clean(pieces[i + 1][:4000] if i + 1 < len(pieces) else "") or ""
        label = re.search(r"No\.\s*\d+(?:\s*EXT)?", text)
        out.append((path, date(text), label.group(0) if label else None))
    return out


SCRIPT = re.compile(r"<script\b.*?</script>", re.S | re.I)


def parse_edition(markup, path):
    # The page repeats its contents as React Server Component data inside
    # <script> tags; read the rendered HTML only.
    markup = SCRIPT.sub("", markup or "")
    m = WHEN.search(markup)
    when = date(clean(m.group(0))) if m else None
    out = []
    for i, row in enumerate(ROW.findall(markup or "")):
        spans = [clean(s) or "" for s in SPAN.findall(row)]
        if not spans or spans[0].upper() != "DECRETO":
            continue
        number = spans[1] if len(spans) > 1 else ""
        cont = CONTAINS.search(row)
        body = clean(cont.group(1)) if cont else None
        if not body:
            continue
        title = "DECRETO {0} {1}".format(number, body).replace("  ", " ") if number else \
            "DECRETO " + body
        n = NUMBER_IN_TITLE.search(title)
        sid = "po/decreto/{0}".format(n.group(1)) if n else "po/{0}/{1}".format(
            path.rsplit("/", 1)[-1], i)
        out.append({
            "state": "dgo", "source_id": sid, "legislature": "LXX", "kind": "decreto",
            "title": title, "presenter": "Congreso del Estado (Periódico Oficial)",
            "party": None, "presented": when, "turno": None,
            "status": "Publicado en el Periódico Oficial", "status_date": when,
            "url": BASE + path,
        })
    return out


def collect(ctx, since):
    home = ctx.text(HOME, "dgo-gazette-home")
    if home is None:
        return []
    eds = editions(home)
    if not eds:
        ctx.gap("dgo gazette: the home page listed no editions the reader recognises")
        return []
    out = []
    for path, when, _label in eds[:MAX_EDITIONS]:
        if when and not since_ok(when, since):
            continue
        if ctx.stop():
            break
        page = ctx.text(BASE + path, "dgo-gazette-" + path.rsplit("/", 1)[-1][:8])
        if page is None:
            continue
        out += [it for it in parse_edition(page, path) if since_ok(it["presented"], since)]
    oldest = min((w for _p, w, _l in eds[:MAX_EDITIONS] if w), default=None)
    if since and oldest and oldest > since:
        ctx.log("  dgo gazette: the home page reaches back to {0} only; earlier editions "
                "are not listed there".format(oldest))
    return out
