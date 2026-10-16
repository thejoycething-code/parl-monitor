"""Italy: the Gazzetta Ufficiale's Serie Generale, and the government's
consultations on ParteciPa (mirrored). Probed and built 16 October 2026
(docs/italy-scope.md, "Government consultations and publications").

GAZZETTA UFFICIALE (www.gazzettaufficiale.it; robots.txt answers 404, so no
rules apply): the official RSS (/rss/SG) carries only the latest issue, so
the list of the last 30 days' issues (/30giorni/serie_generale, plain HTML)
is read, then each issue's sommario (/gazzetta/serie_generale/caricaDettaglio/
home?dataPubblicazioneGazzetta=...&numeroGazzetta=...): every act under its
rubrica (LEGGI ED ALTRI ATTI NORMATIVI, DECRETI PRESIDENZIALI, DECRETI,
DELIBERE E ORDINANZE MINISTERIALI, DECRETI E DELIBERE DI ALTRE AUTORITA',
CIRCOLARI) and its emettitore (the ministry or authority). ESTRATTI, SUNTI E
COMUNICATI (notices: medicine authorisations, exchange rates) and the
coordinated texts are not read. A legge, decreto-legge or decreto
legislativo is a 'law'; the other decrees and deliberations 'regulation'; a
circolare 'guidance'. The act's ELI address is the link.

PARTECIPA (partecipa.gov.it): src/petition_sources/it.py already stores the
open consultations in country_petitions (source 'partecipa', kind
'consultation') with their end dates; they are re-filed here as
'consultation' rows, no second fetch. The country petitions step runs first
in the weekly job, so the mirror is this week's read.

Not used: Normattiva (normattiva.it, robots.txt allows / but its search
pages are disallowed and no documented open-data API was found) duplicates
the Gazzetta for new acts.
"""

from __future__ import annotations

import re

from src import gov_docs as G

CC = "it"
GU = "https://www.gazzettaufficiale.it"
GU_30 = GU + "/30giorni/serie_generale"
GU_ISSUE = GU + "/gazzetta/serie_generale/caricaDettaglio/home?dataPubblicazioneGazzetta={0}&numeroGazzetta={1}"
GU_ELI = GU + "/eli/id/{0}/{1}/sg"
GU_ISSUES_MAX = 30

RUBRICHE = {
    "LEGGI ED ALTRI ATTI NORMATIVI": "regulation",
    "DECRETI PRESIDENZIALI": "regulation",
    "DECRETI, DELIBERE E ORDINANZE MINISTERIALI": "regulation",
    "DECRETI E DELIBERE DI ALTRE AUTORITA'": "regulation",
    "DECRETI E DELIBERE DI ALTRE AUTORITÀ": "regulation",
    "CIRCOLARI": "guidance",
}
LAW_WORDS = ("LEGGE", "DECRETO-LEGGE", "DECRETO LEGISLATIVO", "LEGGE COSTITUZIONALE")
SMALL = {"di", "del", "della", "delle", "dei", "degli", "e", "per", "la", "il", "lo", "le", "gli",
         "dell'", "con", "in", "a", "al", "alla"}


def nice_name(name):
    """"MINISTERO DELLA SALUTE" -> "Ministero della Salute"."""
    words = G.one_line(name).lower().split(" ")
    out = []
    for i, w in enumerate(words):
        if i and (w in SMALL or w.startswith("dell'")):
            out.append(w if w in SMALL else "dell'" + w[5:6].upper() + w[6:])
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out)


def parse_issue_list(page):
    """[(date ISO, number)] of the issues on the 30-day page, newest first."""
    got = set(re.findall(r"dataPubblicazioneGazzetta=(\d{4}-\d{2}-\d{2})&(?:amp;)?numeroGazzetta=(\d+)",
                         page or ""))
    return sorted(got, key=lambda x: (x[0], int(x[1])), reverse=True)


_BLOCK = re.compile(r'<span class="(rubrica|emettitore|risultato)">(.*?)(?=<span class="(?:rubrica|'
                    r'emettitore|risultato)">|<div class="footer|</body>)', re.S)
_CODE = re.compile(r"codiceRedazionale=([0-9A-Z]+)")


def _body_for(act, emettitore):
    if emettitore:
        return nice_name(emettitore)
    a = act.upper()
    if "PRESIDENTE DEL CONSIGLIO" in a:
        return "Presidenza del Consiglio dei Ministri"
    if "PRESIDENTE DELLA REPUBBLICA" in a:
        return "Presidente della Repubblica"
    if a.startswith(("DECRETO-LEGGE", "DECRETO LEGISLATIVO")):
        return "Governo (Consiglio dei Ministri)"
    if a.startswith("LEGGE"):
        return "Parlamento"
    return None


def parse_issue(page, day):
    """[entry] for the acts in one Serie Generale sommario."""
    out, rubrica, emettitore = [], None, None
    for kind, chunk in _BLOCK.findall(page or ""):
        if kind == "rubrica":
            rubrica, emettitore = G.text(chunk).upper(), None
            continue
        if kind == "emettitore":
            emettitore = G.text(chunk)
            continue
        dtype = RUBRICHE.get(rubrica or "")
        if not dtype:
            continue
        code = _CODE.search(chunk)
        act = re.search(r'<span class="data">(.*?)</span>', chunk, re.S)
        if not code or not act:
            continue
        act = G.text(act.group(1))
        links = re.findall(r"<a [^>]*>(.*?)</a>", chunk, re.S)
        desc = ""
        if len(links) > 1:
            desc = re.sub(r'<span class="(riferimento|pagina)">.*?</span>', " ", links[1], flags=re.S)
            desc = re.sub(r"\(\s*" + code.group(1) + r"\s*\)", " ", G.text(desc)).strip()
        if rubrica == "LEGGI ED ALTRI ATTI NORMATIVI" and act.upper().startswith(LAW_WORDS):
            dtype = "law"
        title = act + (": " + desc if desc else "")
        out.append(G.entry("gu", code.group(1), title[:400], dtype, body=_body_for(act, emettitore),
                           published=day, url=GU_ELI.format(day.replace("-", "/"), code.group(1)),
                           summary=desc, status="Serie Generale: " + rubrica.capitalize()))
    return out


def fetch_gu(client, today, log=print):
    try:
        listing = client.get_text(GU_30, "it-govdocs", "gu-30giorni")
    except Exception as exc:                            # noqa: BLE001
        return G.fetched([], gaps=["Gazzetta 30-day list unreadable: {0}".format(str(exc)[:160])])
    issues = parse_issue_list(listing)[:GU_ISSUES_MAX]
    if not issues:
        return G.fetched([], gaps=["Gazzetta 30-day list: no issues found (layout changed?)"])
    out, gaps, read = [], [], 0
    seen = set()
    for day, num in issues:
        try:
            page = client.get_text(GU_ISSUE.format(day, num), "it-govdocs", "gu-sg-{0}-{1}".format(
                day, num))
        except Exception as exc:                        # noqa: BLE001
            gaps.append("Gazzetta SG {0} n. {1}: {2}".format(day, num, str(exc)[:120]))
            continue
        read += 1
        got = parse_issue(page, day)
        if not got:
            gaps.append("Gazzetta SG {0} n. {1}: no acts parsed".format(day, num))
        for e in got:
            if e["doc_id"] not in seen:
                seen.add(e["doc_id"])
                out.append(e)
    return G.fetched(out, note="{0} Serie Generale issues read, {1} acts".format(read, len(out)),
                     gaps=gaps)


def mirror_partecipa(conn, cc, today):
    start = G.window_start(today)
    try:
        rows = conn.execute(
            "SELECT item_id, title, summary, status, opened, closes, body, url FROM "
            "country_petitions WHERE cc = ? AND source = 'partecipa' AND kind = 'consultation' "
            "AND (closes >= ? OR opened >= ?)", (cc, start, start)).fetchall()
    except Exception as exc:                            # noqa: BLE001
        return G.fetched([], gaps=["country_petitions unreadable: {0}".format(str(exc)[:160])])
    out = []
    for r in rows:
        key = str(r[0]).split(":", 1)[-1]
        out.append(G.entry("partecipa", key, r[1], "consultation", body=r[6] or "Governo (ParteciPa)",
                           published=r[4], closing_date=r[5], url=r[7], summary=r[2],
                           status=r[3]))
    last = conn.execute("SELECT MAX(last_seen) FROM country_petitions WHERE cc = ? AND "
                        "source = 'partecipa'", (cc,)).fetchone()[0]
    return G.fetched(out, note="mirrored from country_petitions (ParteciPa, last read {0})".format(
        last))


SOURCES = (
    G.Source(code="gu", name="Gazzetta Ufficiale, Serie Generale", url=GU_30, fetch=fetch_gu),
    G.Source(code="partecipa", name="ParteciPa consultations (mirrored)",
             url="https://partecipa.gov.it/processes", mirror=mirror_partecipa),
)
