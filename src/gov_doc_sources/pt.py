"""Portugal: the Diário da República's daily RSS (Série I, and Série II
Parte C, the government's own acts), and the government's public
consultations on ConsultaLEX. Probed and built 16 October 2026
(docs/portugal-scope.md, "Government consultations and publications").

DIÁRIO DA REPÚBLICA (diariodarepublica.pt is an OutSystems single-page app:
every page, robots.txt included, answers the same JavaScript shell, so there
are no robots rules and no readable HTML). The official RSS feeds on
files.diariodarepublica.pt (listed on the site's "Subscrever RSS" page) are
plain XML:

  dr1   /rss/serie1-html.xml: the day's Série I (laws, decree-laws,
        portarias, Council of Ministers resolutions, decrees);
  dr2c  /rss/serie2&parte=c-html.xml: the day's Série II Parte C, the
        ministries' despachos and portarias (about 90 a day, most of them
        staff and delegation notices, so the precision gate does the work).

Each feed carries ONLY THE LATEST ISSUE (a date parameter is ignored), so a
weekly run sees one day in five; the step should run daily for the Diário
to be complete (see the scope doc). Each item: the act and its number in the
title, the issuing body and the summary run together in the description
(split here at the summary's first verb), the act's page as the link.

CONSULTALEX (www.consultalex.gov.pt, the government's consultation portal;
robots.txt answers 404, so no rules apply): the home page's cards, each with
the title, the description and a relative countdown ("Terminou | Há 15
dias", or the days left while open). Items open by postback only (no
addresses), so the closing date is worked out from the countdown and the
link is the portal. A draft decree-law or portaria out for consultation is
a 'regulation_draft', a draft law a 'bill_draft', anything else a
'consultation'.
"""

from __future__ import annotations

import datetime
import hashlib
import html as htmlmod
import re

from src import gov_docs as G

CC = "pt"
DR_RSS = "https://files.diariodarepublica.pt/rss/"
DR1 = DR_RSS + "serie1-html.xml"
DR2C = DR_RSS + "serie2&parte=c-html.xml"
CLEX = "https://www.consultalex.gov.pt/"

SKIP_KINDS = ("louvor", "aviso-extrato", "anuncio", "anuncio-procedimento")
LAW = ("lei", "lei organica", "lei constitucional", "decreto-lei", "decreto legislativo regional")
PUBLICATION = ("resolucao da assembleia da republica", "aviso", "acordao", "declaracao",
               "anuncio", "louvor", "relatorio", "parecer")
VERBS = (
    "Aprova|Procede|Estabelece|Determina|Altera|Retifica|Define|Regula|Fixa|Autoriza|Cria|"
    "Seleciona|Declara|Nomeia|Designa|Prorroga|Transpõe|Revoga|Atribui|Delega|Subdelega|Homologa|"
    "Exonera|Renova|Constitui|Reconhece|Concede|Classifica|Publica|Torna|Identifica|Assegura|"
    "Adota|Promove|Ratifica|Deixa|Suspende|Mantém|Confirma|Recomenda|Resolve|Elege|Abate|Consagra|"
    "Institui|Implementa|Extingue|Reforça|Clarifica|Atualiza|Regulamenta|Aprovação|Abertura|"
    "Procedimento|Lista|Homologação|Designação|Delegação|Subdelegação|Celebração|Constituição|"
    "Renovação|Promoção|Ingresso|Aplicação|Retificação|Aditamento|Alteração|Nomeação|Cessação|"
    "Autorização|Primeira|Segunda|Terceira|Quarta|Quinta|Sexta|Décima")
_VERB = re.compile(r"\s(?:" + VERBS + r")\b")


def fold(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").lower()


def split_emitter(desc):
    """('Economia e Coesão Territorial', 'Procede à ...') from a description."""
    d = G.one_line(desc)
    m = _VERB.search(d)
    if m and m.start() <= 200:
        return d[:m.start()].strip(" -") or None, d[m.start():].strip()
    if " - " in d[:120]:
        return d.split(" - ", 1)[0], d
    return None, d


def dr_type(act):
    head = fold(act).split(" n.")[0].strip()
    if head in LAW:
        return "law"
    if head.startswith(PUBLICATION):
        return "publication"
    return "regulation"


def parse_dr_rss(xml, series):
    """[entry] for one Diário RSS feed (series 'I' or 'II-C')."""
    out = []
    for item in re.findall(r"<item>(.*?)</item>", xml or "", re.S):
        title = re.search(r"<title>(.*?)</title>", item, re.S)
        desc = re.search(r"<description[^>]*>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</description>",
                         item, re.S)
        link = re.search(r"<link>\s*(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?\s*</link>", item, re.S)
        if not title or not link:
            continue
        title = G.one_line(htmlmod.unescape(title.group(1)))
        url = link.group(1).strip()
        m = re.search(r"/detalhe/([^/]+)/([^/?#]+)", url)
        if not m:
            continue
        kind = m.group(1)
        if kind in SKIP_KINDS:
            continue
        act = title.split(" - ")[0].strip()
        day = re.search(r"de (\d{4}-\d{2}-\d{2})\s*$", title)
        body, summary = split_emitter(htmlmod.unescape(desc.group(1)) if desc else "")
        out.append(G.entry("dr1" if series == "I" else "dr2c", "{0}/{1}".format(kind, m.group(2)),
                           "{0}: {1}".format(act, summary) if summary else act, dr_type(act),
                           body=body, published=day.group(1) if day else None, url=url,
                           summary=summary, status="Diário da República, Série " + series))
    return out


def _dr_fetch(url, series, slug):
    def fetch(client, today, log=print):
        try:
            xml = client.get_text(url, "pt-govdocs", slug)
        except Exception as exc:                        # noqa: BLE001
            return G.fetched([], gaps=["{0}: {1}".format(url, str(exc)[:160])])
        got = parse_dr_rss(xml, series)
        issue = re.search(r"<description>([^<]*)</description>", xml or "")
        note = "{0} acts from {1} (latest issue only)".format(
            len(got), G.one_line(issue.group(1)) if issue else "the feed")
        gaps = [] if got or "<channel>" in (xml or "") else ["{0}: not an RSS feed".format(url)]
        return G.fetched(got, note=note, gaps=gaps)
    return fetch


fetch_dr1 = _dr_fetch(DR1, "I", "dr-serie1")
fetch_dr2c = _dr_fetch(DR2C, "II-C", "dr-serie2-c")


# --- ConsultaLEX ---------------------------------------------------------------------

_CARD = re.compile(r'<div\s+id="[^"]*"\s+class="card[ "].*?(?=<div\s+id="[^"]*"\s+class="card[ "]|'
                   r'<footer|</form>|\Z)', re.S)


def _span(card, suffix):
    m = re.search(r'<span id="[^"]*' + suffix + r'"[^>]*>(.*?)</span>', card, re.S)
    return G.text(m.group(1)) if m else None


def clex_type(title, desc):
    t = fold("{0} {1}".format(title, desc))
    if re.search(r"\b(proposta|projeto|anteprojeto) de lei\b", t):
        return "bill_draft"
    if re.search(r"\b(decreto-lei|portaria|decreto regulamentar|regulamento)\b", t):
        return "regulation_draft"
    return "consultation"


def parse_consultalex(page, today):
    """[entry] for the cards on the ConsultaLEX home page."""
    out, seen = [], set()
    t0 = datetime.date.fromisoformat(today)
    for card in _CARD.findall(page or ""):
        title = _span(card, r"Title")
        if not title:
            continue
        desc = _span(card, r"Description") or ""
        block = re.search(r'class="card--dias-terminar">(.*?)</div\s*>\s*</div\s*>', card, re.S)
        words = G.text(block.group(1)) if block else ""
        n = re.search(r"(\d+)\s*dias?", words, re.I)
        closing = None
        if n:
            days = int(n.group(1))
            past = re.search(r"terminou|h[aá]\s+\d", fold(words))
            closing = (t0 - datetime.timedelta(days=days) if past
                       else t0 + datetime.timedelta(days=days)).isoformat()
        elif re.search(r"\bhoje\b", fold(words)):
            closing = today
        icon = re.search(r'class="icon icon-([a-z0-9-]+)', card)
        key = hashlib.sha1(fold(title).encode("utf-8")).hexdigest()[:12]
        if key in seen:
            continue
        seen.add(key)
        out.append(G.entry("clex", key, title, clex_type(title, desc),
                           body="Governo (ConsultaLEX{0})".format(
                               ", área " + icon.group(1) if icon else ""),
                           closing_date=closing, url=CLEX, summary=desc,
                           status=words or None))
    return out


def fetch_consultalex(client, today, log=print):
    try:
        page = client.get_text(CLEX, "pt-govdocs", "consultalex-home")
    except Exception as exc:                            # noqa: BLE001
        return G.fetched([], gaps=["ConsultaLEX unreadable: {0}".format(str(exc)[:160])])
    got = parse_consultalex(page, today)
    open_now = sum(1 for e in got if (e["closing_date"] or "") >= today)
    return G.fetched(got, note="{0} consultations on the home page, {1} open".format(
        len(got), open_now))


SOURCES = (
    G.Source(code="dr1", name="Diário da República, Série I (latest issue)", url=DR1,
             fetch=fetch_dr1),
    G.Source(code="dr2c", name="Diário da República, Série II Parte C (latest issue)", url=DR2C,
             fetch=fetch_dr2c),
    G.Source(code="clex", name="ConsultaLEX public consultations", url=CLEX,
             fetch=fetch_consultalex),
)
