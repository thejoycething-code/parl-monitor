"""Brazil: the Senate's e-Cidadania (citizens' ideas and the public vote on
bills) and the federal government's Brasil Participativo consultations.

Probed 11 October 2026. www12.senado.leg.br's robots.txt allows everything;
its pages are slow (20 to 60 seconds), so reads have a long timeout and only
the top of each listing is read.

IDEIA LEGISLATIVA: /ecidadania/pesquisaideia?situacao=5&p=N lists the open
ideas (about 5,600, 100 a page), most supported first: title, id and
support count ("13.067 apoios"). An idea with 20,000 supports within four
months becomes a Sugestão Legislativa, debated by the Senate's human-rights
committee (CDH). The first IDEA_PAGES pages (the 500 best supported) are
read: an idea below them is far from the threshold. An idea on our ground
gets its page read once: its description and the deadline for its 20,000
supports ("Data limite para receber 20.000 apoios").

CONSULTA PÚBLICA: /ecidadania/pesquisamateria?p=N lists every bill before
the Senate with its public vote, SIM and NÃO (about 7,700, the most voted
first). The id is the Senate's codigoMateria. Every bill in progress takes
votes, so there is no closing date; the first CONSULTA_PAGES pages are read.
The total of votes is stored as the count, so a bill on our ground whose
vote jumps in a week is shown (SURGE in src/petitions.py).

BRASIL PARTICIPATIVO (brasilparticipativo.presidencia.gov.br, Decidim;
robots.txt allows /): POST /api GraphQL, every participatory process with
its dates (194; 69 open on 11 October). Agencies' standing containers that
run for years (end dates in 2035 or 2060) are left out.

Not covered: the Câmara's enquetes (no listing, only per bill, and small),
Participa+Brasil (closed).
"""

from __future__ import annotations

import datetime
import html as htmlmod
import json
import re

from src import petitions as P

CC = "br"
EC = "https://www12.senado.leg.br/ecidadania/"
IDEAS = EC + "pesquisaideia?situacao=5&p={0}"
IDEA = EC + "visualizacaoideia?id={0}"
BILLS = EC + "pesquisamateria?p={0}"
BILL = EC + "visualizacaomateria?id={0}"
BP = "https://brasilparticipativo.presidencia.gov.br/api"
BP_ITEM = "https://brasilparticipativo.presidencia.gov.br/processes/{0}"
IDEA_PAGES = 5
CONSULTA_PAGES = 3
TIMEOUT = 120
MAX_SPAN_DAYS = 730      # a process running longer than two years is a standing container
IDEA_THRESHOLDS = ((20000, "becomes a Sugestão Legislativa, debated by the CDH"),)


def _text(fragment):
    return P.one_line(htmlmod.unescape(re.sub(r"<[^>]+>", " ", fragment or "")))


def parse_ideas(page):
    out = []
    for art in re.findall(r'<article class="resumo-ideia">(.*?)</article>', page, re.S):
        m = re.search(r'visualizacaoideia\?id=(\d+)">(.*?)</a>', art, re.S)
        if not m:
            continue
        spans = re.findall(r"<span>(.*?)</span>", art, re.S)
        out.append(P.entry("ideia", m.group(1), _text(m.group(2)), kind="idea",
                           status="Aberta", signatures=spans[0] if spans else None,
                           body="Senado Federal (CDH)", url=IDEA.format(m.group(1))))
    return out


def parse_idea(page):
    """{text, closes, signatures, status} from an idea's page."""
    out = {}
    m = re.search(r'font-size:24px;[^>]*>.*?</div></b>\s*<div[^>]*>(.*?)</div>', page, re.S)
    if m:
        out["text"] = _text(m.group(1))
    m = re.search(r"Data limite para receber[^<]*</div>\s*<div[^>]*>\s*(\d{2}/\d{2}/\d{4})", page)
    if m:
        out["closes"] = P.iso(m.group(1))
    m = re.search(r'<span class="contabilizacao">([\d.]+)</span>', page)
    if m:
        out["signatures"] = P.number(m.group(1))
    m = re.search(r'title="Situação da Ideia">.*?<em>(.*?)</em>', page, re.S)
    if m:
        out["status"] = _text(m.group(1))
    return out


def last_page(page):
    m = re.search(r'title="último"[^>]*href="[^"]*[?&](?:amp;)?p=(\d+)', page) or \
        re.search(r'href="[^"]*[?&](?:amp;)?p=(\d+)"[^>]*title="último"', page)
    return int(m.group(1)) if m else 1


def parse_bills(page):
    out = []
    for block in re.findall(r'<div class="resumo-materia">(.*?)</figure>', page, re.S):
        m = re.search(r'<header>\s*<a href="visualizacaomateria\?id=(\d+)">(.*?)</a>', block, re.S)
        if not m:
            continue
        ementa = re.search(r"<section><a [^>]*>(.*?)</a></section>", block, re.S)
        nums = re.findall(r"<span>([\d.]+)</span>", block)
        yes = P.number(nums[0]) if nums else None
        no = P.number(nums[1]) if len(nums) > 1 else None
        ident = _text(m.group(2))
        out.append(P.entry("consulta", m.group(1), "{0}: {1}".format(
            ident, _text(ementa.group(1)) if ementa else ""), kind="public_vote",
            status="em tramitação", yes_count=yes, no_count=no,
            signatures=(yes or 0) + (no or 0) if nums else None, thresholds=(),
            body="Senado Federal", refs=[ident], url=BILL.format(m.group(1))))
    return out


Q_PROCESSES = ('{ participatoryProcesses { id slug title { translation(locale:"pt-BR") } '
               'subtitle { translation(locale:"pt-BR") } startDate endDate } }')


def parse_processes(reply, today):
    out = []
    for r in ((reply.get("data") or {}).get("participatoryProcesses") or []):
        start, end = r.get("startDate"), r.get("endDate")
        if not end or end < today or (start and start > today):
            continue
        if start and P._days(start, end) is not None and P._days(start, end) > MAX_SPAN_DAYS:
            continue
        out.append(P.entry("bp", r.get("slug") or r.get("id"),
                           (r.get("title") or {}).get("translation"), kind="consultation",
                           summary=(r.get("subtitle") or {}).get("translation"),
                           status="aberta", opened=start, closes=end,
                           body="Governo federal (Brasil Participativo)",
                           url=BP_ITEM.format(r.get("slug"))))
    return out


def _pages(client, url, parse, pages, slug):
    entries, gaps, last = [], [], pages
    for p in range(1, pages + 1):
        if p > last:
            break
        try:
            raw = client.get_text(url.format(p), "br-petitions", "{0}-{1}".format(slug, p),
                                  timeout=TIMEOUT)
        except Exception as exc:                    # noqa: BLE001
            gaps.append("{0} page {1} unreadable: {2}".format(slug, p, str(exc)[:110]))
            break
        got = parse(raw)
        if not got:
            break
        entries += got
        last = min(pages, last_page(raw))
    return entries, gaps


def fetch_ideas(client, today, log=print):
    entries, gaps = _pages(client, IDEAS, parse_ideas, IDEA_PAGES, "ideias")
    return P.fetched(entries, gaps=gaps, note="the {0} best-supported open ideas".format(
        len(entries)))


def detail_idea(client, e, log=print):
    return parse_idea(client.get_text(e["url"], "br-petitions",
                                      "ideia-" + e["item_id"].split(":")[-1], timeout=TIMEOUT))


def fetch_bills(client, today, log=print):
    entries, gaps = _pages(client, BILLS, parse_bills, CONSULTA_PAGES, "consultas")
    return P.fetched(entries, gaps=gaps, note="the {0} most-voted bills".format(len(entries)))


def fetch_processes(client, today, log=print):
    try:
        reply = client.post_json(BP, json.dumps({"query": Q_PROCESSES}), "br-petitions",
                                 "brasil-participativo", timeout=TIMEOUT)
    except Exception as exc:                        # noqa: BLE001
        return P.fetched([], gaps=["Brasil Participativo unreadable: {0}".format(str(exc)[:140])])
    return P.fetched(parse_processes(reply, today), note="open processes, standing containers left out")


SOURCES = (
    P.Source(code="ideia", name="e-Cidadania ideas (Senate)", kind="idea", fetch=fetch_ideas,
             detail=detail_idea, thresholds=IDEA_THRESHOLDS),
    P.Source(code="consulta", name="e-Cidadania public vote on bills (Senate)",
             kind="public_vote", fetch=fetch_bills),
    P.Source(code="bp", name="Brasil Participativo consultations", kind="consultation",
             fetch=fetch_processes),
)
