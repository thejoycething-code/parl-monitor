"""Peru: El Peruano's Normas Legales, national issuers: laws, supreme
decrees, ministerial and agency resolutions, and the draft norms published
for comment ("Disponen la publicación del proyecto de ...").

Probed 16 October 2026. diariooficial.elperuano.pe/Normas/Filtro answers
one read-only form POST (cddesde, cdhasta, day first, as the page's own
form sends it) with every norm published in the range: issuer heading,
title and number, date, sumilla (the official one-line summary) and a link
to the norm's own page on busquedas.elperuano.pe. About 500 norms a week.
robots.txt (diariooficial.elperuano.pe) disallows /NormasElperuano/,
/EdicionDigital/, /DatosAbiertos/, /Normas/NLactualizada and file folders;
the Filtro path is allowed. busquedas.elperuano.pe's robots.txt is
"Allow: /". The same route as tools/pe_regions.py, which takes the regional
governments' and Lima Metropolitana's norms from this listing; here the
regional and municipal issuers are left out and everything national kept.

doc_type: LEY, DECRETO LEGISLATIVO and DECRETO DE URGENCIA (law-force) are
'law'; a RESOLUCIÓN LEGISLATIVA (treaties, Congress's own acts) 'law' too;
supreme decrees and resolutions 'regulation'; a sumilla that publishes a
draft for comment ("publicación del proyecto de ...") 'regulation_draft',
and so does an extension of a draft's comment period ("Amplían plazo para
recibir comentarios"), kept without a closing date: the extension runs from
the end of the first period, which the extending norm does not date. Errata and conventions are 'publication'.

DEADLINES. The listing gives no comment period, so each draft's own page
is read (at most DETAIL_CAP a run): the resolution states it ("Establecer
el plazo de quince (15) días calendario, contado desde el día siguiente de
la publicación"; D.S. 009-2024-JUS sets 15 calendar days as the minimum).
The closing date is publication + N for calendar days counted from the
following day (publication + N - 1 if counted from the day itself); a
period in working days is not computed. A draft whose period cannot be
read is kept without a closing date.

Not used: gob.pe's per-institution "normas legales" pages (the gazette
already carries every national norm, a day or more earlier).
"""

from __future__ import annotations

import datetime
import html as htmlmod
import re

from src import gov_docs as G

CC = "pe"
TAXONOMIES = (("taxonomy-es.yaml", "pe"),)
FILTER = "https://diariooficial.elperuano.pe/Normas/Filtro"
DAYS = 21            # draft periods run 15 to 30 days
DETAIL_CAP = 40

ARTICLE = re.compile(r'<article class="edicionesoficiales_articulos(?:_dig)?">(.*?)</article>', re.S)
LOCAL = re.compile(r"^(GOBIERNO REGIONAL|MUNICIPALIDAD|INSTITUCIONES EDUCATIVAS)")
DRAFT = re.compile(r"(?i)(publicaci[oó]n|publicar|prepublicaci[oó]n)\s+(?:del?\s+|el\s+)?proyecto\b|"
                   r"consulta\s+p[uú]blica\s+(?:del?|el)\s+proyecto\b|"
                   r"(ampl[ií]an|ampliar|prorrogan?)\s+(?:el\s+)?plazo\s+(?:para\s+)?(?:la\s+)?"
                   r"(?:recibir|recepci[oó]n)")
EXTENSION = re.compile(r"(?i)(ampl[ií]an|ampliar|prorrogan?)\s+(?:el\s+)?plazo")
LAW = re.compile(r"^(LEY\b|DECRETO LEGISLATIVO|DECRETO DE URGENCIA|RESOLUCI[OÓ]N LEGISLATIVA)")
OTHER = re.compile(r"^(FE DE ERRATAS?|CONVENIO)")


def flat(fragment):
    return G.one_line(htmlmod.unescape(re.sub(r"<[^>]+>", " ", fragment or "")))


def filter_url(today):
    """The page's own form action carries today's date, month first."""
    d = datetime.date.fromisoformat(today)
    return "{0}?dateparam={1:02d}%2F{2:02d}%2F{3}%2000%3A00%3A00".format(FILTER, d.month, d.day, d.year)


def filter_fields(since, until):
    f = lambda d: datetime.date.fromisoformat(d).strftime("%d/%m/%Y")   # noqa: E731
    return {"cddesde": f(since), "cdhasta": f(until), "btnBuscar": "Filtrar", "tipo": ""}


def doc_type(title, sumilla):
    t = (title or "").upper()
    if DRAFT.search(sumilla or ""):
        return "regulation_draft"
    if LAW.search(t):
        return "law"
    if OTHER.search(t):
        return "publication"
    return "regulation"


SMALL = {"de", "la", "del", "los", "las", "y", "e", "en", "para", "por", "el", "a"}


def nice(name):
    words = (name or "").lower().split()
    return " ".join(w if (i and w in SMALL) else w[:1].upper() + w[1:] for i, w in enumerate(words))


def parse_filter(page):
    """Entries for the national issuers in one Normas/Filtro reply."""
    out = []
    for a in ARTICLE.findall(page or ""):
        head = re.search(r"<h4>(.*?)</h4>", a, re.S)
        link = re.search(r'<h5>\s*<a href="([^"]+)">(.*?)</a>\s*</h5>', a, re.S)
        if not head or not link:
            continue
        issuer = re.sub(r"\s*Publicaci[oó]n Digital\s*$", "", flat(head.group(1)))
        if LOCAL.search(issuer.upper()):
            continue
        title = re.sub(r"\s*\[[^\]]*\]\s*$", "", flat(link.group(2)))
        when = re.search(r"Fecha:\s*([0-9/]+)", a)
        paras = [flat(p) for p in re.findall(r"<p>(.*?)</p>", a, re.S)]
        sumilla = next((p for p in reversed(paras) if re.search(r"\w", p)
                        and not p.startswith("Fecha:")), "")
        ident = link.group(1).rstrip("/").rsplit("/", 1)[-1]
        extra = "Edición Extraordinaria" in a
        out.append(G.entry("nl", ident, "{0}: {1}".format(title, sumilla) if sumilla else title,
                           doc_type(title, sumilla), body=nice(issuer),
                           published=when.group(1) if when else None, url=link.group(1),
                           status="El Peruano, Normas Legales" + (", edición extraordinaria"
                                                                   if extra else ""),
                           refs=[title]))
    return out


PERIOD = re.compile(r"(?i)plazo\b[^()]{0,250}?\((\d{1,3})\)\s+d[ií]as\s+"
                    r"(calendario|naturales|h[aá]biles)(.{0,200})")
BARE = re.compile(r"(?i)plazo\s+de\s+(\d{1,3})\s+d[ií]as\s+(calendario|naturales|h[aá]biles)(.{0,200})")


def closing_from_page(page, published):
    """(closing ISO date or None, status note) from a draft's own page: the last
    period it sets ("Establecer el plazo de quince (15) días calendario...", "El
    plazo para ... es de dieciocho (18) días calendario..."), skipping the
    general rule quoted in the recitals ("no debe ser menor a quince (15) días")."""
    text = flat(re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page or ""))
    best = None
    for m in sorted(list(PERIOD.finditer(text)) + list(BARE.finditer(text)), key=lambda m: m.start()):
        if "menor" in m.group(0)[:m.end(1) - m.start()].lower():
            continue
        best = m
    if not best or not published:
        return None, None
    days, kind, rest = int(best.group(1)), best.group(2).lower(), best.group(3).lower()
    if kind.startswith("h"):
        return None, "{0} días hábiles para comentarios (no fecha calculada)".format(days)
    following = "siguiente" in rest.split("public")[0]
    pub = datetime.date.fromisoformat(published)
    close = pub + datetime.timedelta(days=days if following else days - 1)
    return close.isoformat(), "{0} días calendario para comentarios".format(days)


def fetch(client, today, log=print):
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=DAYS - 1)).isoformat()
    try:
        page = client.post_form(filter_url(today), filter_fields(since, today), "pe-govdocs",
                                "normas-{0}-{1}".format(since, today), timeout=120, archive=True)
    except Exception as exc:                            # noqa: BLE001
        return G.fetched([], gaps=["El Peruano Normas Legales unreadable for {0} to {1}: {2}".format(
            since, today, str(exc)[:120])])
    if isinstance(page, bytes):
        page = page.decode("utf-8", "replace")
    entries = parse_filter(page)
    gaps, read = [], 0
    for e in entries:
        if e["doc_type"] != "regulation_draft" or e.get("closing_date"):
            continue
        if EXTENSION.search(e["title"]):
            # the extension counts from the end of the first period, which this norm
            # does not date: no closing date rather than a wrong one
            e["status"] += "; amplía el plazo de un proyecto anterior (sin fecha calculada)"
            continue
        if read >= DETAIL_CAP:
            log("  {0}-govdocs: more than {1} drafts; the rest kept without a closing "
                "date".format(CC, DETAIL_CAP))
            break
        read += 1
        try:
            own = client.get_text(e["url"], "pe-govdocs", "nl-" + e["doc_id"].split(":", 1)[1])
        except Exception as exc:                        # noqa: BLE001
            log("  pe-govdocs: {0} unreadable: {1}".format(e["url"], str(exc)[:100]))
            continue
        close, status = closing_from_page(own, e["published"])
        e["closing_date"] = close
        if status:
            e["status"] = "{0}; {1}".format(e["status"], status)
    return G.fetched(entries, gaps=gaps, note="national norms {0} to {1}, {2} draft page(s) read".format(
        since, today, read))


SOURCES = (
    G.Source(code="nl", name="El Peruano, Normas Legales (national issuers)",
             url="https://diariooficial.elperuano.pe/Normas", fetch=fetch),
)
