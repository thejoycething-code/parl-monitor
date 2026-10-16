"""Argentina: the Boletín Oficial's first section (laws, decrees, resolutions)
and the national public consultations, mirrored.

Probed 16 October 2026.

BOLETÍN OFICIAL (www.boletinoficial.gob.ar). robots.txt disallows only the
second section (companies and court notices: /seccion/segunda,
/detalleAviso/segunda/*); the first section is open. GET
/seccion/primera/YYYYMMDD lists one day's edition under its rubros (LEYES,
DECRETOS, DECISIONES ADMINISTRATIVAS, RESOLUCIONES, DISPOSICIONES, AVISOS
OFICIALES...): the issuing body and the norm's number only (about 55 avisos
a day). The listing has no summary, so an aviso's own page
(/detalleAviso/primera/<id>/<date>, the full text) is read for the words:
every law, decree and administrative decision, then resolutions and
dispositions of the bodies whose output touches our ground (PRIORITY), at
most DETAIL_CAP pages a run. The summary stored is the operative part
(from "DECRETA:", "RESUELVE:" or "DISPONE:"), capped. Avisos oficiales,
union and collective-agreement notices and the like are not listed. An aviso
whose page was not read keeps only issuer and number: listed, but never on
our ground. Each run reads the last DAYS days (the gazette appears on
working days).

doc_type: LEYES are 'law'; decrees, decisions, resolutions and
dispositions 'regulation'; a resolution opening the "Procedimiento de
Elaboración Participativa de Normas" (Decreto 1172/2003) is a
'regulation_draft' (its comment period runs in working days, so no closing
date is computed).

CONSULTATIONS. consultapublica.argentina.gob.ar is read every week by the
petitions step (src/petition_sources/ar.py, source 'cp', kind
'consultation'); its rows are mirrored here, closing dates and all.

Not used: InfoLEG's open data on datos.jus.gob.ar (robots.txt disallows
/api/ and asks a 10 s crawl delay; the dataset page answered 404).
"""

from __future__ import annotations

import datetime
import html as htmlmod
import re

from src import gov_docs as G
from src.gov_doc_sources._petitions_mirror import mirror_for

CC = "ar"
BO = "https://www.boletinoficial.gob.ar"
DAY = BO + "/seccion/primera/{0}"
AVISO = BO + "/detalleAviso/primera/{0}/{1}"
DAYS = 7             # the weekly job: one week of editions
DETAIL_CAP = 40

RUBROS = {
    "LEYES": "law",
    "DECRETOS": "regulation",
    "DECRETOS SINTETIZADOS": "regulation",
    "DECISIONES ADMINISTRATIVAS": "regulation",
    "DECISIONES ADMINISTRATIVAS SINTETIZADAS": "regulation",
    "RESOLUCIONES": "regulation",
    "RESOLUCIONES GENERALES": "regulation",
    "RESOLUCIONES CONJUNTAS": "regulation",
    "RESOLUCIONES SINTETIZADAS": "regulation",
    "DISPOSICIONES": "regulation",
    "DISPOSICIONES SINTETIZADAS": "regulation",
    "DISPOSICIONES CONJUNTAS": "regulation",
}
ALWAYS = ("LEYES", "DECRETOS", "DECISIONES ADMINISTRATIVAS")
PRIORITY = re.compile(r"(?i)\b(salud|capital humano|justicia|derechos humanos|ni[ñn]ez|familia|"
                      r"mujer|g[eé]nero|anmat|medicamentos|comunicaciones|discapacidad|"
                      r"sedronar|registro nacional de las personas)\b")
CLERICAL = re.compile(r"(?i)gesti[oó]n administrativa|derecho de autor")
PARTICIPATIVA = re.compile(r"(?i)elaboraci[oó]n participativa de normas")
OPERATIVE = re.compile(r"\b(DECRETA|RESUELVE|RESUELVEN|DISPONE|DISPONEN|[Ss]ancionan con fuerza de\s*[Ll]ey)\s*:")
TOPIC_RUBROS = {"LEYES": "Congreso de la Nación", "DECRETOS": "Poder Ejecutivo Nacional",
                "DECRETOS SINTETIZADOS": "Poder Ejecutivo Nacional",
                "DECISIONES ADMINISTRATIVAS": "Jefatura de Gabinete de Ministros",
                "DECISIONES ADMINISTRATIVAS SINTETIZADAS": "Jefatura de Gabinete de Ministros"}


SMALL = {"de", "la", "del", "los", "las", "y", "e", "en", "para", "por", "el", "a"}


def nice(name):
    """'MINISTERIO DE SALUD' -> 'Ministerio de Salud'."""
    words = (name or "").lower().split()
    return " ".join(w if (i and w in SMALL) else w[:1].upper() + w[1:] for i, w in enumerate(words))


def _clean(fragment):
    return G.one_line(htmlmod.unescape(re.sub(r"<[^>]+>", " ", fragment or "")))


def parse_day(page, day):
    """[(rubro, entry)] from one /seccion/primera/YYYYMMDD page."""
    out = []
    parts = re.split(r'<h5 class="seccion-rubro[^"]*">', page or "")
    for part in parts[1:]:
        rubro = _clean(part.split("<", 1)[0]).upper()
        kind = RUBROS.get(rubro)
        if not kind:
            continue
        seen = set()
        for m in re.finditer(r'<a href="/detalleAviso/primera/(\d+)/(\d{8})"[^>]*>\s*'
                             r'<div class="linea-aviso">(.*?)</div>', part, re.S):
            ident, date, block = m.group(1), m.group(2), m.group(3)
            if ident in seen:
                continue
            seen.add(ident)
            body = _clean((re.search(r'<p class="item">(.*?)</p>', block, re.S) or [None, ""])[1])
            details = [_clean(x) for x in re.findall(r"<small>(.*?)</small>", block, re.S)]
            norm = details[0] if details else rubro.title()
            published = "{0}-{1}-{2}".format(date[:4], date[4:6], date[6:])
            kind_here = kind
            if rubro == "LEYES" and norm.lower().startswith("decreto"):
                # the decree that promulgates the law, listed beside it
                kind_here, rubro_body = "regulation", "Poder Ejecutivo Nacional"
            else:
                rubro_body = TOPIC_RUBROS.get(rubro)
            if rubro_body:
                # laws, decrees and decisions are listed under their subject, not their issuer
                title = "{0}: {1}".format(norm, nice(body)) if body else norm
                issuer = rubro_body
            else:
                title = "{0} ({1})".format(norm, nice(body)) if body else norm
                issuer = nice(body)
            out.append((rubro, G.entry("bo", ident, title, kind_here, body=issuer or None,
                                       published=published, url=AVISO.format(ident, date),
                                       status="Boletín Oficial, primera sección, " + rubro.lower(),
                                       refs=details[1:2])))
    return out


def parse_aviso(page):
    """{text, operative} from an aviso's own page."""
    m = re.search(r'<div id="cuerpoDetalleAviso"[^>]*>(.*?)</div>', page or "", re.S)
    if not m:
        return {}
    raw = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", m.group(1))
    text = _clean(raw)
    op = OPERATIVE.search(text)
    operative = text[op.end():] if op else text
    operative = re.split(r"\be\. \d{2}/\d{2}/\d{4}", operative)[0]
    return {"text": text, "operative": G.one_line(operative)[:G.SUMMARY_CAP]}


def _wanted(rubro, e):
    if any(rubro.startswith(r) for r in ALWAYS):
        return 0
    body = e.get("body") or ""
    return 1 if PRIORITY.search(body) and not CLERICAL.search(body) else None


def fetch(client, today, log=print):
    end = datetime.date.fromisoformat(today)
    listed, gaps, days_read = [], [], 0
    for i in range(DAYS):
        d = end - datetime.timedelta(days=i)
        if d.weekday() >= 5:
            continue
        try:
            page = client.get_text(DAY.format(d.strftime("%Y%m%d")), "ar-govdocs",
                                   "bo-primera-" + d.isoformat())
        except Exception as exc:                        # noqa: BLE001
            gaps.append("Boletín Oficial {0} unreadable: {1}".format(d.isoformat(), str(exc)[:120]))
            continue
        days_read += 1
        listed += [(r, e) for r, e in parse_day(page, d) if e["published"] == d.isoformat()]
    order = sorted((w, n) for n, (r, e) in enumerate(listed)
                   for w in [_wanted(r, e)] if w is not None)
    read = 0
    for _, n in order:
        if read >= DETAIL_CAP:
            break
        rubro, e = listed[n]
        read += 1
        try:
            got = parse_aviso(client.get_text(e["url"], "ar-govdocs",
                                              "bo-aviso-" + e["doc_id"].split(":", 1)[1]))
        except Exception as exc:                        # noqa: BLE001
            log("  ar-govdocs: aviso {0} unreadable: {1}".format(e["url"], str(exc)[:100]))
            continue
        e["summary"] = got.get("operative") or None
        if PARTICIPATIVA.search(got.get("text") or "") and e["doc_type"] == "regulation":
            e["doc_type"] = "regulation_draft"
            e["status"] += "; Elaboración Participativa de Normas"
    if not days_read:
        return G.fetched([], gaps=gaps or ["no Boletín Oficial day readable"])
    return G.fetched([e for _, e in listed], gaps=gaps, note="first section, {0} edition(s) read, "
                     "{1} of {2} wanted aviso page(s) read for their words (cap {3})".format(
                         days_read, read, len(order), DETAIL_CAP))


SOURCES = (
    G.Source(code="bo", name="Boletín Oficial, primera sección",
             url="https://www.boletinoficial.gob.ar/seccion/primera", fetch=fetch),
    G.Source(code="cp", name="national public consultations (consultapublica, mirrored)",
             url="https://consultapublica.argentina.gob.ar/",
             mirror=mirror_for("cp", "consultation")),
)
