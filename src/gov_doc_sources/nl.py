"""The Netherlands: the government's letters to the Tweede Kamer, and the
Staatsblad (16 October 2026).

KAMERBRIEVEN ('kb'). Since 28 April 2026 most central government documents
appear only on open.overheid.nl (rijksoverheid.nl/documenten says so), whose
robots.txt refuses every crawler but Googlebot. The one complete, machine
readable stream of what ministers publish is the letters they send the
Tweede Kamer: Documents of Soort 'Brief regering' in the Tweede Kamer's Open
Data Portaal (gegevensmagazijn OData v4, documented, keyless, the source
tools/nl_rollcalls.py and tools/nl_chamber.py already read;
src/robots_guard.DOCUMENTED_APIS). Each has its subject (Onderwerp), date,
the signing minister or state secretary (DocumentActor 'Eerste
ondertekenaar', whose Functie names the ministry) and the Kamerstukdossier
it belongs to (its title is the summary classified with the subject).
Policy papers, evaluations, research reports and the government's answers
to the Kamer all arrive this way: 'publication', so the precision gate asks
tier 1. About 25 letters in ten days.

STAATSBLAD ('stb'). Acts and orders in council as made: the official
gazette on officielebekendmakingen.nl. Its search results are refused by
robots.txt (Disallow: /resultaten*, /zoeken/resultaat*), and KOOP's SRU
service (repository.overheid.nl/sru) and zoekservice.overheid.nl answer
`User-agent: * Disallow: /`. Allowed: the day's Staatsblad page
(www.officielebekendmakingen.nl/staatsblad, today's numbers) and each
publication's own page (zoek.officielebekendmakingen.nl/stb-YYYY-N.html),
whose Dublin Core meta tags carry the title, type (Wet, AMvB, Koninklijk
besluit), ministry and issue date. The numbers run in sequence through the
year, so the reader takes the highest number from the day's page (or, on a
day with none, probes from an estimate) and walks down, at most
STB_MAX_PAGES pages, until a publication is older than STB_LOOKBACK_DAYS.
A Wet is a 'law', everything else a 'regulation'.

NOT READ (robots.txt): internetconsultatie.nl (`User-agent: * Disallow: /`,
the government's consultation portal, so Dutch consultations and their
closing dates are not read), open.overheid.nl, repository.overheid.nl,
zoekservice.overheid.nl, linkeddata.overheid.nl, and data.overheid.nl's
CKAN API (/data/ disallowed). The Staatscourant (ministerial regulations)
has no allowed listing beyond the day's issue; rijksoverheid.nl's news
listing is rendered by JavaScript and its news sitemap holds two days.
"""

from __future__ import annotations

import datetime
import html
import re

from src import gov_docs as G

CC = "nl"
ODATA = "https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/Document"
KB_QUERY = ("?$filter=Soort eq 'Brief regering' and Verwijderd eq false and Datum ge {0}"
            "&$orderby=Datum desc&$select=Id,DocumentNummer,Onderwerp,Titel,Datum"
            "&$expand=DocumentActor($select=ActorNaam,Functie,Relatie),"
            "Kamerstukdossier($select=Nummer,Titel)")
KB_ITEM = "https://www.tweedekamer.nl/kamerstukken/brieven_regering/detail?id={0}&did={0}"
KB_MAX_PAGES = 10

STB_TODAY = "https://www.officielebekendmakingen.nl/staatsblad"
STB_ITEM = "https://zoek.officielebekendmakingen.nl/stb-{0}-{1}.html"
STB_MAX_PAGES = 40
STB_LOOKBACK_DAYS = 35
STB_PER_DAY = 1.12          # 322 numbers by 16 October 2026 (day 289)


# --- Kamerbrieven ---------------------------------------------------------------------

def _signer(actors):
    """The ministry, from the first signatory's Functie ('minister van Onderwijs,
    Cultuur en Wetenschap'); else the first Functie given."""
    actors = actors or []
    first = [a for a in actors if (a.get("Relatie") or "").lower().startswith("eerste")]
    for a in first + actors:
        if a.get("Functie"):
            return a["Functie"]
    return None


def parse_kamerbrieven(reply):
    out = []
    for r in reply.get("value") or []:
        num = r.get("DocumentNummer") or r.get("Id")
        title = r.get("Onderwerp") or r.get("Titel")
        if not num or not title:
            continue
        dossiers = [d for d in r.get("Kamerstukdossier") or [] if d.get("Titel")]
        summary = "; ".join("{0} ({1})".format(d["Titel"], d.get("Nummer")) for d in dossiers)
        out.append(G.entry("kb", num, title, "publication", body=_signer(r.get("DocumentActor")),
                           published=(r.get("Datum") or "")[:10], url=KB_ITEM.format(num),
                           summary=summary or None, status="Brief regering",
                           refs=[str(d.get("Nummer")) for d in dossiers if d.get("Nummer")]))
    return out


def kb_url(today):
    since = G.window_start(today)
    return (ODATA + KB_QUERY.format(since)).replace(" ", "%20").replace("'", "%27")


def fetch_kamerbrieven(client, today, log=print):
    url, out, pages, gaps = kb_url(today), [], 0, []
    while url and pages < KB_MAX_PAGES:
        try:
            reply = client.get_json(url, "nl-govdocs", "kb-{0}".format(pages))
        except Exception as exc:                        # noqa: BLE001
            gaps.append("Kamerbrieven page {0} unreadable: {1}".format(pages + 1, str(exc)[:160]))
            break
        out += parse_kamerbrieven(reply)
        pages += 1
        url = reply.get("@odata.nextLink")
    if url and pages >= KB_MAX_PAGES:
        gaps.append("Kamerbrieven: stopped after {0} pages".format(pages))
    return G.fetched(out, note="{0} letters from the government in the window ({1} page(s))"
                     .format(len(out), pages), gaps=gaps)


# --- Staatsblad -----------------------------------------------------------------------

def stb_numbers(page, year):
    """The Staatsblad numbers of `year` listed on the day's page."""
    return sorted({int(n) for n in re.findall(r"stb-{0}-(\d+)\.html".format(year), page or "")})


def _meta(page, name):
    m = re.search(r'<meta name="{0}"[^>]*content="([^"]*)"'.format(re.escape(name)), page or "")
    return html.unescape(m.group(1)).strip() if m else None


def parse_stb(page, year, number):
    """One entry from a publication's own page; None when it has no title."""
    title = _meta(page, "DC.title")
    if not title:
        return None
    kind = None
    for m in re.finditer(r'<meta name="DC.type" data-scheme="([^"]*)" content="([^"]*)"', page):
        if m.group(1) == "OVERHEIDop.Staatsblad":
            kind = html.unescape(m.group(2))
    body = _meta(page, "DC.creator") or _meta(page, "DCTERMS.publisher")
    issued = _meta(page, "DCTERMS.issued") or _meta(page, "DCTERMS.available")
    dossier = _meta(page, "OVERHEIDop.behandeldDossier")
    category = _meta(page, "OVERHEID.category")
    doc_type = "law" if (kind or "").lower() in ("wet", "rijkswet") else "regulation"
    return G.entry("stb", "{0}-{1}".format(year, number), title, doc_type, body=body,
                   published=issued, url=STB_ITEM.format(year, number),
                   summary=category, status="Staatsblad {0}, {1} ({2})".format(year, number, kind or "?"),
                   refs=[dossier] if dossier else ())


def _stb_page(client, year, number):
    """The page, or None when the number does not exist (404)."""
    try:
        return client.get_text(STB_ITEM.format(year, number), "nl-govdocs",
                               "stb-{0}-{1}".format(year, number), archive=False)
    except Exception as exc:                            # noqa: BLE001
        if "404" in str(exc):
            return None
        raise


def fetch_staatsblad(client, today, log=print):
    day = datetime.date.fromisoformat(today)
    year = day.year
    stop = (day - datetime.timedelta(days=STB_LOOKBACK_DAYS)).isoformat()
    budget = STB_MAX_PAGES
    pages = {}
    try:
        top_list = stb_numbers(client.get_text(STB_TODAY, "nl-govdocs", "stb-today"), year)
    except Exception as exc:                            # noqa: BLE001
        return G.fetched([], gaps=["Staatsblad day page unreadable: {0}".format(str(exc)[:160])])
    if top_list:
        top = top_list[-1]
    else:
        # No Staatsblad today (a weekend): probe from an estimate.
        guess = max(1, int(day.timetuple().tm_yday * STB_PER_DAY))
        page = _stb_page(client, year, guess)
        budget -= 1
        step = 1 if page is not None else -1
        top = guess if page is not None else None
        if page is not None:
            pages[guess] = page
        n = guess
        while budget > 0 and n > 1:
            n += step
            page = _stb_page(client, year, n)
            budget -= 1
            if step == 1:
                if page is None:
                    break
                pages[n], top = page, n
            elif page is not None:
                pages[n], top = page, n
                break
        if top is None:
            return G.fetched([], gaps=["Staatsblad: no publication of {0} found near number {1}"
                                       .format(year, guess)])
    out, n, missing = [], top, 0
    while n >= 1 and budget > 0:
        page = pages.get(n)
        if page is None:
            page = _stb_page(client, year, n)
            budget -= 1
        n -= 1
        if page is None:
            missing += 1
            continue
        e = parse_stb(page, year, n + 1)
        if e is None:
            missing += 1
            continue
        if e["published"] and e["published"] < stop:
            break
        out.append(e)
    else:
        if budget <= 0:
            log("  nl-govdocs-stb: page budget ({0}) spent at Staatsblad {1}, {2}".format(
                STB_MAX_PAGES, year, n + 1))
    note = "Staatsblad {0}, {1} down to {2}: {3} publication(s){4}".format(
        year, top, n + 1, len(out), ", {0} number(s) missing".format(missing) if missing else "")
    return G.fetched(out, note=note)


SOURCES = (
    G.Source(code="kb", name="Kamerbrieven (letters from the government to the Tweede Kamer)",
             url=ODATA, fetch=fetch_kamerbrieven),
    G.Source(code="stb", name="Staatsblad (acts and orders in council)", url=STB_TODAY,
             fetch=fetch_staatsblad),
)
