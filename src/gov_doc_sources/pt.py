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
weekly run sees one day in five. So the feeds are ALSO READ DAILY (Chris, 16
October 2026), by the daily job (jobs/vote-briefs-daily.sh ->
tools/country_gov_docs.py pt --daily -> daily() below): each day's issue
is parsed and matched against the taxonomy, and every act with any match
(or a watchlist key) is kept in the committed ledger
data/gov-docs-daily/pt.json, keyed by doc_id (deduplicated), LEDGER_DAYS
deep. The daily job reads and writes no store (it is `mini_run: no-store`:
no 895 MB pull for a ~5 s read), so the weekly gov_docs step (and the
GitHub backup's) reads the ledger beside the latest issue and stores both
in gov_docs, the precision gate deciding as for any other row; the weekly
read stays as the backstop for a day the daily job missed. Each item: the act and its number in the
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
import json
import os
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


def _dr_read(client, url, series, slug):
    """(entries, note, gaps) for one feed's latest issue."""
    try:
        xml = client.get_text(url, "pt-govdocs", slug)
    except Exception as exc:                            # noqa: BLE001
        return [], None, ["{0}: {1}".format(url, str(exc)[:160])]
    got = parse_dr_rss(xml, series)
    issue = re.search(r"<description>([^<]*)</description>", xml or "")
    note = "{0} acts from {1} (latest issue)".format(
        len(got), G.one_line(issue.group(1)) if issue else "the feed")
    gaps = [] if got or "<channel>" in (xml or "") else ["{0}: not an RSS feed".format(url)]
    return got, note, gaps


def _dr_fetch(url, series, slug, code):
    def fetch(client, today, log=print):
        got, note, gaps = _dr_read(client, url, series, slug)
        ids = {e["doc_id"] for e in got}
        extra = [e for e in ledger_entries(code) if e["doc_id"] not in ids]
        if extra:
            note = "{0}; {1} more from the daily reads".format(note or "feed unread", len(extra))
        return G.fetched(got + extra, note=note, gaps=gaps)
    return fetch


fetch_dr1 = _dr_fetch(DR1, "I", "dr-serie1", "dr1")
fetch_dr2c = _dr_fetch(DR2C, "II-C", "dr-serie2-c", "dr2c")


# --- the daily read (no store) --------------------------------------------------------

LEDGER_PATH = os.path.join(G.ROOT, "data", "gov-docs-daily", "pt.json")
LEDGER_DAYS = 35              # a missed weekly and then some; older rows are in the store
DAILY_FEEDS = (("dr1", DR1, "I", "dr-serie1"), ("dr2c", DR2C, "II-C", "dr-serie2-c"))
_CLASS_KEYS = ("areas", "matched_terms", "tier", "watch_keys", "preclassified")


def load_ledger(path=None):
    """{doc_id: entry} from the committed ledger ({} when absent or unreadable)."""
    path = path or LEDGER_PATH
    try:
        with open(path, encoding="utf-8") as fh:
            got = json.load(fh)
    except (OSError, ValueError):
        return {}
    return got.get("entries", {}) if isinstance(got, dict) else {}


def ledger_entries(code, path=None):
    """The ledger's entries of one source, as reader entries (unclassified)."""
    out = []
    for doc_id, e in sorted(load_ledger(path).items()):
        if e.get("source") == code and doc_id == e.get("doc_id"):
            out.append({k: v for k, v in e.items() if k not in _CLASS_KEYS + ("seen",)})
    return out


def daily(client, today, log=print, path=None, config_dir=None):
    """Read today's issue of both feeds into the ledger. Returns (read, added, gaps)."""
    path = path or LEDGER_PATH
    taxes = G.taxonomies(CC, config_dir)
    wl = G.watchlist(CC, config_dir)
    ledger = load_ledger(path)
    read = added = 0
    gaps = []
    for code, url, series, slug in DAILY_FEEDS:
        got, note, g = _dr_read(client, url, series, slug)
        gaps += ["{0}: {1}".format(code, x) for x in g]
        read += len(got)
        kept = 0
        for e in got:
            c = G.classify(e, taxes, wl)
            if not (c.get("areas") or c.get("watch_keys")):
                continue
            kept += 1
            if e["doc_id"] not in ledger:
                added += 1
                ledger[e["doc_id"]] = dict(e, seen=today)
            else:
                ledger[e["doc_id"]] = dict(e, seen=ledger[e["doc_id"]].get("seen") or today)
        log("pt-govdocs daily {0}: {1}; {2} matching the taxonomy".format(code, note or "unread", kept))
    floor = (datetime.date.fromisoformat(today) - datetime.timedelta(days=LEDGER_DAYS)).isoformat()
    ledger = {k: v for k, v in ledger.items()
              if max(v.get("published") or "", v.get("seen") or "") >= floor}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"updated": today, "keep_days": LEDGER_DAYS, "entries": ledger}, fh,
                  ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)
    log("pt-govdocs daily: {0} acts read, {1} new in the ledger ({2} held)".format(
        read, added, len(ledger)))
    return read, added, gaps


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
    G.Source(code="dr1", name="Diário da República, Série I (latest issue + daily reads)",
             url=DR1,
             fetch=fetch_dr1),
    G.Source(code="dr2c", name="Diário da República, Série II Parte C (latest issue + daily reads)",
             url=DR2C,
             fetch=fetch_dr2c),
    G.Source(code="clex", name="ConsultaLEX public consultations", url=CLEX,
             fetch=fetch_consultalex),
)
