#!/usr/bin/env python3
"""Brazil's state assemblies: the bills of the Assembleias Legislativas whose
own sources can be read, with their stage, the votes they publish and the
members who sign them, into the brs_* tables.

    python3 tools/br_states.py                         # every source
    python3 tools/br_states.py --sources sp,mg         # some of them
    python3 tools/br_states.py --sources sapl:ro       # one SAPL house
    python3 tools/br_states.py --reclassify            # re-derive areas, offline
    python3 tools/br_states.py --db /tmp/brs.db        # anywhere but the store

13 October 2026; docs/brazil-regions-scope.md has every measurement.

THE SOURCES, all keyless, all probed live with robots.txt read first:

  sp   ALESP (São Paulo), the Assembly's open-data files (repositorioDados,
       updated daily): proposituras.zip (every propositura since the 1990s;
       PL, PLC, PEC and PDL of the current legislature are kept),
       documento_autor.zip (authors), documento_andamento_atual.zip (the
       current stage), deputados.xml (names and parties). About 26 MB a run.
       Committee votes, EACH MEMBER'S VOTE: comissoes_permanentes_reunioes.xml
       (3 MB) is read every run, and only when it shows a meeting newer than
       the last one read are comissoes_permanentes_votacoes.xml (67 MB),
       ..._deliberacoes.xml (12 MB) and comissoes.xml read; positions are kept
       for bills on our ground or watched. Nothing large is archived (the
       files are the Assembly's own, re-downloadable): the read is recorded
       in brs_reads with its newest date.
  mg   ALMG (Minas Gerais), the website's bill search
       (/atividade-parlamentar/projetos-de-lei/), newest first, ten a page,
       for PL, PLC and PEC: number, ementa, authors with party, situação.
       A second pass sorted by "data da última ação" catches bills that
       moved. A bill on our ground also has its page read (publication date,
       latest tramitação step). ALMG's open-data API (dadosabertos.almg.gov.br)
       is NOT read: its robots.txt disallows everything but the
       documentation.
  rj   ALERJ (Rio de Janeiro), the Lotus Notes view of the 2023-2027 bills
       (https://alerjln1.alerj.rj.gov.br/scpro2327.nsf/Internet/LeiInt; it
       answers plain HTTP too, but the repository never fetches over HTTP), fifteen a
       page, newest first: number, ementa, committees, date, author. The
       server is slow and drops connections; a failed page is a gap.
  sapl:<uf>  The Interlegis SAPL houses, one platform for many states: its
       documented REST API (/api/materia/materialegislativa/, filtered by
       type and by last update; /api/sessao/registrovotacao/ for plenary
       vote tallies; /api/materia/tramitacao/ and /api/base/autor/ for the
       bills on our ground). Every SAPL robots.txt asks Crawl-delay: 60, so
       each house costs about a minute a request; the houses are read in
       parallel, each within the run's budget. Read: Acre, Alagoas,
       Amazonas, Paraíba, Piauí, Rondônia, Tocantins; tried every run:
       Roraima and Maranhão (no answer from outside Brazil on 13 October).

  THE ALTERNATIVE ROUTES (second pass, 13 October 2026), for assemblies whose
  own search is blocked or missing; each item's edition line says "(via ...)":
  rn   ALRN, the JSON its Transparência Legislativa app loads: bills with
       author, party and stage; plenary results ("últimas votações").
  ce   ALECE, its proposições lists on www2 (one search per type, year and
       in-passage/decided): bills with author, stage and law number.
  pe   ALEPE, its open-data API's projetos (one XML a year).
  pa   ALEPA, its proposições search (a form POST; newest ten of a type,
       numbered gaps asked one by one).
  go   Goiás, adopted laws from the Casa Civil's legislation API.
  pr   Paraná, adopted laws from the Casa Civil's Sistema Estadual de
       Legislação (ALEP's bill search is behind reCAPTCHA, never bypassed;
       its documented open-data API answers only plain HTTP, which the
       repository never fetches).

Not read, and why (the scope doc has the detail): Rio Grande do Sul,
Espírito Santo, Amapá, Distrito Federal (no answer from outside Brazil, the
GitHub runners included; DF's SINJ search backend is disallowed by
robots.txt), Santa Catarina and Mato Grosso's bill report (answer GitHub's
runners only: a GitHub-side step is proposed, not built), Mato Grosso do
Sul (proof-of-work captcha), Sergipe (no list of bills), Bahia (ALBA's own
list stops in July 2025; the Casa Civil's LegislaBahia groups '*' with a
Disallow: / in its robots.txt, read as disallowed). LexML Brasil's SRU
search sits under /busca/, which its robots.txt disallows.

CLASSIFICATION: config/taxonomy-pt.yaml with country 'br' (accent-
sensitive; the titles are the assemblies' own Portuguese, ALERJ's in
capitals), plus config/watchlist-br-states.yaml by key.

ROBOTS.TXT AT RUN TIME: every request goes through src/robots_guard
(GuardedClient): robots.txt read once per host per run; a disallowed URL,
or a host whose robots.txt does not answer, is a [gap] line and a gaps row,
never fetched and never fatal; a Crawl-delay raises that host's interval.

Separation guarantee: writes the brs_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store (the fetching runs in parallel threads; all
writes happen afterwards, in the main thread).

Exit codes: 0 clean, 3 stored what it could and recorded gaps, 1 otherwise.
"""

from __future__ import annotations

import argparse
import datetime
import html
import io
import json
import os
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import brs_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from src.robots_guard import GuardedClient, RobotsRefused  # noqa: E402

FEED = "br-states"
TAXONOMY_PT = os.path.join(ROOT, "config", "taxonomy-pt.yaml")
TAXONOMY_COUNTRY = "br"
HIDDEN_AREAS = (11,)   # migration: collated, never campaigned (repo-wide rule)
BUDGET_S = 600
# The state legislatures sworn in on 1 February 2023 (the 20th in most
# states); bills before that are not kept.
LEGISLATURE_START = "2023-02-01"

# --- sources --------------------------------------------------------------------

SP_BASE = "https://www.al.sp.gov.br/repositorioDados/"
SP_FILES = {
    "proposituras": SP_BASE + "processo_legislativo/proposituras.zip",
    "autores": SP_BASE + "processo_legislativo/documento_autor.zip",
    "andamento": SP_BASE + "processo_legislativo/documento_andamento_atual.zip",
    "deputados": SP_BASE + "deputados/deputados.xml",
    "reunioes": SP_BASE + "processo_legislativo/comissoes_permanentes_reunioes.xml",
    "votacoes": SP_BASE + "processo_legislativo/comissoes_permanentes_votacoes.xml",
    "deliberacoes": SP_BASE + "processo_legislativo/comissoes_permanentes_deliberacoes.xml",
    "comissoes": SP_BASE + "processo_legislativo/comissoes.xml",
}
SP_PAGE = "https://www.al.sp.gov.br/propositura/?id={0}"
# ALESP's naturezas kept (naturezasSpl.xml): id -> (sigla, name).
SP_NATUREZAS = {
    "1": ("PL", "Projeto de lei"),
    "2": ("PLC", "Projeto de lei Complementar"),
    "4": ("PDL", "Projeto de decreto legislativo"),
    "5": ("PEC", "Proposta de emenda à Constituição"),
}
SP_NO_INFO = re.compile(r"tramita exclusivamente no Alesp Sem Papel", re.I)

MG_SEARCH = ("https://www.almg.gov.br/atividade-parlamentar/projetos-de-lei/"
             "?pesquisou=true&tipo={tipo}&ordem={ordem}{ano}{page}")
MG_BILL = "https://www.almg.gov.br/projetos-de-lei/{kind}/{number}/{year}"
# ALMG's search types: id -> (sigla, name).
MG_TYPES = (("5", "PL", "Projeto de Lei"), ("6", "PLC", "Projeto de Lei Complementar"),
            ("9", "PEC", "Proposta de Emenda à Constituição"))
MG_SEED_PAGES = 2       # a first read: the newest twenty of each type
MG_MAX_PAGES = 8        # later reads: until a page holds nothing new
MG_MOVED_PAGES = {"PL": 3, "PLC": 1, "PEC": 1}
MG_DETAIL_CAP = 12      # bill pages read per run (bills on our ground only)
# A list entry whose "ementa" is really the last action (ALMG prints the
# last action where a bill has no ementa, e.g. 'Distribuído a 2 comissões').
# Retries (13 October 2026): the ALMG host answers in the morning and times
# out for an hour at a time. A failed search page or bill page is asked again
# after these waits (seconds), within the run's budget; once a whole type's
# search has failed even so, the other types get one try each.
MG_RETRY_WAITS = (30, 90)
MG_ACTION = re.compile(r"^(Distribu[íi]d|Recebid|Proposi[çc][ãa]o recebida|Encaminhad|Anexad|"
                       r"Arquivad|Aprovad|Publicad)", re.I)

RJ_VIEW = "https://alerjln1.alerj.rj.gov.br/scpro2327.nsf/Internet/LeiInt?OpenForm{start}"
RJ_HOST = "https://alerjln1.alerj.rj.gov.br"
RJ_PAGE_ROWS = 15
RJ_SEED_PAGES = 2
RJ_MAX_PAGES = 6

# The SAPL houses: uf -> host. Order: population.
SAPL_HOSTS = {
    "pb": "sapl.al.pb.leg.br",
    "am": "sapl.al.am.leg.br",
    "al": "sapl.al.al.leg.br",
    "pi": "sapl.al.pi.leg.br",
    "ma": "sapl.al.ma.leg.br",
    "ro": "sapl.al.ro.leg.br",
    "to": "sapl.al.to.leg.br",
    "ac": "sapl.al.ac.leg.br",
    "rr": "sapl.al.rr.leg.br",
}
SAPL_FIRST_DAYS = 30     # a first read: bills updated in the last month
SAPL_REREAD_DAYS = 2     # later reads overlap the last by two days
SAPL_MAX_PAGES = 3       # of 100 bills each, per run
SAPL_DETAIL_CAP = 3      # tramitação reads per house per run (a minute each)
SAPL_AUTHOR_CAP = 2      # autor reads per house per run
SAPL_TYPES_DAYS = 28     # the type list is re-read every four weeks
SAPL_DELAY = 60.0        # every SAPL robots.txt asks this; the guard reads it too

# The alternative routes (second pass, 13 October 2026): see the readers below.
ALT_SOURCES = ("pr", "pe", "ce", "pa", "go", "rn")
SOURCE_ORDER = ("sp", "mg", "rj") + ALT_SOURCES + tuple("sapl:" + uf for uf in SAPL_HOSTS)

# Assemblies NOT read, and why (13 October 2026), for the edition's coverage
# line. docs/brazil-regions-scope.md has the measurements.
NOT_READ = {
    "rs": "no answer from outside Brazil, GitHub's runners included",
    "sc": "answers GitHub's runners only (a GitHub-side step is proposed)",
    "df": "no answer from outside Brazil; SINJ's search backend is disallowed by robots.txt",
    "es": "no answer from outside Brazil, GitHub's runners included",
    "mt": "its SAPL holds nothing recent; its bill report answers GitHub's runners only",
    "ms": "bill search behind a proof-of-work captcha",
    "ap": "no answer from outside Brazil, GitHub's runners included",
    "se": "no list of bills; its legislation host does not answer from outside Brazil",
    "ba": "ALBA's own list stops in July 2025; LegislaBahia's robots.txt disallows us",
}

HOST_THROTTLE = {"www.al.sp.gov.br": 2.0, "www.almg.gov.br": 2.0,
                 "alerjln1.alerj.rj.gov.br": 5.0,
                 "api-transparencialegislativa.al.rn.leg.br": 3.0, "www2.al.ce.gov.br": 3.0,
                 "dadosabertos.alepe.pe.gov.br": 3.0, "www.alepa.pa.gov.br": 3.0,
                 "legisla.casacivil.go.gov.br": 3.0, "www.legislacao.pr.gov.br": 5.0}


# --- small helpers ---------------------------------------------------------------

def fold(text):
    """Strip tags, unescape, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def plain(text):
    """Lower case, accents folded: for matching only, never stored."""
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def iso_dmy(text):
    """'14/08/2026' or '14/8/2026' -> '2026-08-14'; else None."""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text or "")
    if not m:
        return None
    return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), int(m.group(2)), int(m.group(1)))


def iso_mdy(text):
    """Lotus Notes' US dates: '10/08/2026' -> '2026-10-08'; else None."""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text or "")
    if not m:
        return None
    return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), int(m.group(1)), int(m.group(2)))


def decode(raw, default="utf-8"):
    """Bytes to text by the declared charset; UTF-8, then Latin-1, otherwise."""
    head = raw[:600].decode("ascii", errors="replace").lower()
    m = re.search(r"""encoding=["']([\w-]+)["']|charset=["']?([\w-]+)""", head)
    for enc in ([m.group(1) or m.group(2)] if m else []) + [default, "latin-1"]:
        try:
            return raw.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="replace")


def gap_text(e):
    return getattr(e, "reason", None) or str(getattr(e, "cause", e))[:160]


class Result:
    """What one source's fetch produced; written by the main thread."""

    def __init__(self, source, uf):
        self.source = source
        self.uf = uf
        self.bills = []        # dicts for brs_store.upsert_bill (with areas, terms, tier)
        self.votes = []        # dicts for brs_store.upsert_vote
        self.positions = {}    # vote_key -> [(member, party, position)]
        self.members = []      # (member_key, uf, name, party)
        self.stages = []       # (bill_key, status, status_date, committees): a stage-only update
        self.gaps = []
        self.status = "ok"
        self.detail = None
        self.through = None
        self.meta = None

    def gap(self, detail):
        self.gaps.append(detail)
        if self.status == "ok":
            self.status = "gap"


# --- classification ----------------------------------------------------------------

def load_taxonomy(path=None):
    path = path or TAXONOMY_PT
    return filt.load_taxonomy(path, country=TAXONOMY_COUNTRY) if os.path.exists(path) else None


def classify(tax, key, *texts, watch_path=None):
    """(areas or None, terms, tier). Areas None only when there is no
    taxonomy and the key is not watched."""
    res = filt.FilterResult()
    if tax is not None:
        res = filt.filter_item(tax, filt.Watchlist(entities=[], bill_titles=[], act_shorts=[]),
                               *[t for t in texts if t])
    res = brs_store.add_watch_areas(res, key, watch_path)
    if tax is None and not res.watchlist_hits:
        return None, [], None
    terms = list(res.matched_terms or []) + list(res.watchlist_hits or [])
    return sorted(set(res.issue_areas or [])), terms, res.tier


def on_our_ground(areas):
    return bool(set(areas or []) - set(HIDDEN_AREAS))


def classified(tax, b, watch_path=None):
    """The bill dict with areas, terms and tier added."""
    areas, terms, tier = classify(tax, b["bill_key"], b.get("title"), watch_path=watch_path)
    return dict(b, areas=areas, terms=terms, tier=tier)


# --- São Paulo (ALESP open data) ----------------------------------------------------

def _xml_rows(stream, tag):
    """Every <tag> element of an XML stream, as {child: text} dicts."""
    for _ev, el in ET.iterparse(stream):
        if el.tag == tag:
            yield {c.tag: (c.text or "").strip() for c in el}
            el.clear()


def _zip_stream(raw):
    z = zipfile.ZipFile(io.BytesIO(raw))
    return z.open(z.namelist()[0])


def parse_sp_proposituras(raw, since=LEGISLATURE_START):
    """{IdDocumento: bill dict} for the kept naturezas presented since `since`."""
    out = {}
    for d in _xml_rows(_zip_stream(raw), "propositura"):
        nat = SP_NATUREZAS.get(d.get("IdNatureza"))
        if not nat:
            continue
        presented = (d.get("DtPublicacao") or d.get("DtEntradaSistema") or "")[:10]
        if presented < since:
            continue
        try:
            number, year = int(d["NroLegislativo"]), int(d["AnoLegislativo"])
        except (KeyError, ValueError):
            continue
        doc = d.get("IdDocumento")
        out[doc] = {
            "bill_key": brs_store.bill_key("sp", nat[0], number, year), "uf": "sp", "source": "sp",
            "source_id": doc, "kind": nat[0], "kind_name": nat[1], "number": number, "year": year,
            "title": re.sub(r"\s+", " ", d.get("Ementa") or "").strip() or None,
            "presented": presented or None, "url": SP_PAGE.format(doc),
        }
    return out


def parse_sp_deputados(raw):
    """{IdSPL: (name, party)}, and the same keyed by IdDeputado. Only the
    name and party are read: deputados.xml also carries biographies, which
    are never stored."""
    out = {}
    for d in _xml_rows(io.BytesIO(raw), "Deputado"):
        name, party = d.get("NomeParlamentar") or None, d.get("Partido") or None
        for k in ("IdSPL", "IdDeputado"):
            if d.get(k):
                out[d[k]] = (name, party)
    return out


def parse_sp_autores(raw, wanted, parties):
    """{IdDocumento: 'Name (PARTY); Name'} for the wanted documents."""
    got = {}
    for d in _xml_rows(_zip_stream(raw), "DocumentoAutor"):
        doc = d.get("IdDocumento")
        if doc not in wanted:
            continue
        name = d.get("NomeAutor")
        if not name:
            continue
        party = (parties.get(d.get("IdAutor")) or (None, None))[1]
        label = "{0} ({1})".format(name, party) if party else name
        if label not in got.setdefault(doc, []):
            got[doc].append(label)
    return {k: "; ".join(v) for k, v in got.items()}


def parse_sp_andamento(raw, wanted):
    """{IdDocumento: (status, ISO date)}: the latest current-stage row."""
    best = {}
    for d in _xml_rows(_zip_stream(raw), "DocumentoAndamento"):
        doc = d.get("IdDocumento")
        if doc not in wanted:
            continue
        rank = ((d.get("Data") or "")[:10], int(d.get("NrOrdem") or 0) if (d.get("NrOrdem") or "0").isdigit() else 0)
        if doc in best and best[doc][0] >= rank:
            continue
        desc = re.sub(r"\s+", " ", d.get("Descricao") or "").strip()
        etapa = (d.get("NmEtapa") or "").strip()
        if SP_NO_INFO.search(desc):
            status = None
        elif etapa and etapa != "Não Identificada":
            status = "{0}: {1}".format(etapa, desc) if desc else etapa
        else:
            status = desc or None
        best[doc] = (rank, status, rank[0] or None)
    return {k: (v[1], v[2]) for k, v in best.items()}


def parse_sp_reunioes(raw):
    """{IdReuniao: (ISO date, IdComissao)} and the newest date."""
    out, newest = {}, None
    for d in _xml_rows(io.BytesIO(raw), "ReuniaoComissao"):
        date = (d.get("Data") or "")[:10] or None
        out[d.get("IdReuniao")] = (date, d.get("IdComissao"))
        if date and (newest is None or date > newest):
            newest = date
    return out, newest


def parse_sp_comissoes(raw):
    return {d.get("IdComissao"): d.get("NomeComissao") or d.get("SiglaComissao")
            for d in _xml_rows(io.BytesIO(raw), "Comissao")}


def parse_sp_deliberacoes(raw, wanted):
    """{(IdReuniao, IdDocumento): 'APROVADO'} for the wanted documents."""
    return {(d.get("IdReuniao"), d.get("IdDocumento")): d.get("Deliberacao")
            for d in _xml_rows(io.BytesIO(raw), "ReuniaoComissaoDeliberacao")
            if d.get("IdDocumento") in wanted}


def sp_position_kind(voto):
    t = plain(voto)
    if t.startswith("favoravel"):
        return "yes"
    if t.startswith("contrari"):
        return "no"
    if t.startswith("absten"):
        return "abstain"
    return None


def parse_sp_votacoes(raw, wanted):
    """{(IdReuniao, IdDocumento): [(member, IdDeputado, position)]}."""
    out = {}
    for d in _xml_rows(io.BytesIO(raw), "ReuniaoComissaoVotacao"):
        doc = d.get("IdDocumento")
        if doc not in wanted:
            continue
        out.setdefault((d.get("IdReuniao"), doc), []).append(
            (d.get("Deputado"), d.get("IdDeputado"), (d.get("Voto") or "").strip()))
    return out


def fetch_sp(client, ctx):
    res = Result("sp", "sp")
    tax, budget, known = ctx["tax"], ctx["budget"], ctx["known"]

    def get(name):
        return client.get_bytes(SP_FILES[name], FEED, "sp-" + name, archive=False)

    try:
        props = parse_sp_proposituras(get("proposituras"))
    except (FetchError, zipfile.BadZipFile, ET.ParseError) as e:
        res.status, res.detail = "unreachable", "proposituras: " + gap_text(e)
        res.gap("ALESP " + res.detail)
        return res
    wanted = set(props)
    parties = {}
    try:
        parties = parse_sp_deputados(get("deputados"))
        seen = set()
        for k, (name, party) in parties.items():
            if name and (name, party) not in seen and len(k) > 6:   # IdSPL keys only
                seen.add((name, party))
                res.members.append(("sp/" + k, "sp", name, party))
    except (FetchError, ET.ParseError) as e:
        res.gap("ALESP deputados.xml: " + gap_text(e))
    authors, stages = {}, {}
    for name, parse in (("autores", lambda r: parse_sp_autores(r, wanted, parties)),
                        ("andamento", lambda r: parse_sp_andamento(r, wanted))):
        if budget.exhausted():
            res.gap("ALESP: time budget reached before " + name)
            break
        try:
            got = parse(get(name))
        except (FetchError, zipfile.BadZipFile, ET.ParseError) as e:
            res.gap("ALESP {0}: {1}".format(name, gap_text(e)))
            continue
        if name == "autores":
            authors = got
        else:
            stages = got
    for doc, b in props.items():
        b["authors"] = authors.get(doc)
        status, when = stages.get(doc, (None, None))
        b["status"], b["status_date"] = status, when
        res.bills.append(classified(tax, b, ctx.get("watch_path")))
        if b["presented"] and (res.through is None or b["presented"] > res.through):
            res.through = b["presented"]
    # Committee votes, only when a meeting is newer than the last read.
    meta = dict(ctx["meta"].get("sp") or {})
    ours = {b["source_id"]: b for b in res.bills
            if on_our_ground(b["areas"]) or b["bill_key"] in known["watched"]}
    try:
        meetings, newest = parse_sp_reunioes(get("reunioes"))
    except (FetchError, ET.ParseError) as e:
        res.gap("ALESP committee meetings: " + gap_text(e))
        res.meta = meta
        return res
    if newest and newest > (meta.get("last_meeting") or "") and ours:
        if budget.spent() > budget.seconds * 0.6:
            res.gap("ALESP committee votes: left for the next run (time budget)")
        else:
            try:
                votes = parse_sp_votacoes(get("votacoes"), set(ours))
                outcomes = parse_sp_deliberacoes(get("deliberacoes"), set(ours))
                committees = parse_sp_comissoes(get("comissoes"))
            except (FetchError, ET.ParseError) as e:
                res.gap("ALESP committee votes: " + gap_text(e))
            else:
                for (meeting, doc), rows in votes.items():
                    date, comissao = meetings.get(meeting, (None, None))
                    b = ours[doc]
                    counts = {"yes": 0, "no": 0, "abstain": 0}
                    pos = []
                    for member, dep_id, voto in rows:
                        k = sp_position_kind(voto)
                        if k:
                            counts[k] += 1
                        pos.append((member, (parties.get(dep_id) or (None, None))[1], voto))
                    vkey = "sp/c{0}/{1}".format(meeting, doc)
                    res.votes.append({
                        "vote_key": vkey, "uf": "sp", "bill_key": b["bill_key"], "date": date,
                        "body": committees.get(comissao) or "committee",
                        "description": "Committee vote on the rapporteur's report",
                        "result": outcomes.get((meeting, doc)), **counts})
                    res.positions[vkey] = pos
                meta["last_meeting"] = newest
    res.meta = meta
    return res


# --- Minas Gerais (ALMG website) ----------------------------------------------------

def parse_mg_list(text):
    """One ALMG search page: [{bill dict}]."""
    out = []
    for art in re.findall(r"<article\b.*?</article>", text, re.S):
        m = re.search(r'<h3>\s*<a href="/projetos-de-lei/([A-Z]+)/(\d+)/(\d{4})"', art)
        if not m:
            continue
        kind, number, year = m.group(1), int(m.group(2)), int(m.group(3))
        paras = re.findall(r'<p class="m-0 mb-2">(.*?)</p>', art, re.S)
        title = fold(paras[0]) if paras else None
        if title and (title.startswith("Autoria:") or MG_ACTION.search(title)):
            title = None
        authors = [fold(a) for a in re.findall(r"<span>(.*?)</span>",
                                               (re.search(r"<strong>Autoria:</strong>(.*?)</p>", art, re.S)
                                                or re.search(r"()", "")).group(1), re.S)]
        authors = [re.sub(r"^Deputad[oa]\s+", "", a).strip() for a in authors if a]
        status = re.search(r"<strong>Situação:</strong>(.*?)</p>", art, re.S)
        out.append({
            "bill_key": brs_store.bill_key("mg", kind, number, year), "uf": "mg", "source": "mg",
            "source_id": "{0}/{1}/{2}".format(kind, number, year), "kind": kind,
            "kind_name": next((n for _i, s, n in MG_TYPES if s == kind), None),
            "number": number, "year": year, "title": title,
            "authors": "; ".join(authors) or None,
            "status": fold(status.group(1)) if status else None,
            "url": MG_BILL.format(kind=kind, number=number, year=year),
        })
    return out


def parse_mg_bill(text):
    """An ALMG bill page: {presented, status, local, step_date, step}."""
    out = {}
    pub = re.search(r"Publicação</span>(.*?)<hr", text, re.S)
    if pub:
        out["presented"] = iso_dmy(fold(pub.group(1)))
    sit = re.search(r"Situação atual</span>(.*?)<hr", text, re.S)
    if sit:
        out["status"] = fold(sit.group(1)) or None
    loc = re.search(r'd-block">Local</span>(.*?)<hr', text, re.S)
    if loc:
        out["local"] = fold(loc.group(1)) or None
    step = re.search(r'<div class="step-content w-100">(.*?)</div>\s*</div>\s*</div>', text, re.S)
    if step:
        body = step.group(1)
        date = re.search(r'<span class="d-block">(\d{1,2}/\d{1,2}/\d{4})</span>', body)
        where = re.search(r'alert-heading">(.*?)</div>', body, re.S)
        rest = fold(re.sub(r'.*?<hr class="my-2">', "", body, count=1, flags=re.S))
        out["step_date"] = iso_dmy(date.group(1)) if date else None
        out["step"] = "{0}: {1}".format(fold(where.group(1)), rest) if where else rest
    return out


def with_retries(call, budget, waits, sleep):
    """call(), asked again after each of `waits` seconds when it fails with
    a FetchError (never a robots.txt refusal), as long as the budget leaves
    the wait and a minute besides."""
    for i in range(len(waits) + 1):
        try:
            return call()
        except RobotsRefused:
            raise
        except FetchError:
            if i == len(waits) or budget.seconds - budget.spent() < waits[i] + 60:
                raise
            sleep(waits[i])


def fetch_mg(client, ctx):
    res = Result("mg", "mg")
    tax, budget, known = ctx["tax"], ctx["budget"], ctx["known"]
    first = not ctx["read_ok"].get("mg")
    listed = {}
    sleep = ctx.get("sleep") or time.sleep
    waits = {"now": MG_RETRY_WAITS}

    def page(tipo, ordem, n, ano):
        # A search naming the year answers in about three seconds; one without
        # did not answer within the timeout (measured 13 October 2026), so
        # every search names the year.
        url = MG_SEARCH.format(tipo=tipo, ordem=ordem, ano="&ano={0}".format(ano),
                               page="" if n == 1 else "&pagina={0}".format(n))
        return with_retries(lambda: parse_mg_list(decode(client.get_bytes(
            url, FEED, "mg-{0}-{1}-{2}-{3}".format(tipo, ordem, ano, n)))), budget, waits["now"], sleep)

    def bill_page(url, key):
        return with_retries(lambda: parse_mg_bill(decode(client.get_bytes(
            url, FEED, "mg-bill-" + key.split("/", 1)[1].replace(" ", "-").replace("/", "-")))),
            budget, waits["now"], sleep)

    year = int(ctx["today"][:4])
    # In January and February a bill presented late last year is still news.
    years = [year] + ([year - 1] if int(ctx["today"][5:7]) <= 2 else [])
    failed = 0
    for tipo, kind, _name in MG_TYPES:
        try:
            for ano in years:
                for n in range(1, (MG_SEED_PAGES if first else MG_MAX_PAGES) + 1):
                    if budget.exhausted():
                        res.gap("ALMG: time budget reached in the {0} list".format(kind))
                        break
                    got = page(tipo, 0, n, ano)
                    fresh = [b for b in got if b["bill_key"] not in known["bills"]
                             and b["bill_key"] not in listed]
                    for b in got:
                        listed.setdefault(b["bill_key"], b)
                    if len(got) < 10 or (not first and not fresh):
                        break
                # Sorted by the date of the last action: this year's bills that moved.
                for n in range(1, MG_MOVED_PAGES[kind] + 1):
                    if budget.exhausted():
                        break
                    got = page(tipo, 3, n, ano)
                    for b in got:
                        listed.setdefault(b["bill_key"], b)
                    if len(got) < 10:
                        break
        except RobotsRefused as e:
            res.status, res.detail = "blocked", gap_text(e)
            res.gap("ALMG: " + res.detail)
            return res
        except FetchError as e:
            failed += 1
            waits["now"] = ()       # the host is down: one try each from here
            res.gap("ALMG {0} search: {1}".format(kind, gap_text(e)))
    if failed == len(MG_TYPES) and not listed:
        res.status, res.detail = "unreachable", res.gaps[-1] if res.gaps else "no answer"
        return res
    details = 0
    for key, b in listed.items():
        b = classified(tax, b, ctx.get("watch_path"))
        old = known["bills"].get(key)
        fresh = old is None or (b.get("status") and old[0] != b["status"])
        if (on_our_ground(b["areas"]) or key in known["watched"]) and fresh and details < MG_DETAIL_CAP \
                and not budget.exhausted():
            try:
                d = bill_page(b["url"], key)
                details += 1
                b["presented"] = d.get("presented")
                b["status"] = d.get("status") or b.get("status")
                if d.get("step_date"):
                    b["status_date"] = d["step_date"]
                b["committees"] = d.get("local")
            except FetchError as e:
                res.gap("ALMG bill page {0}: {1}".format(key, gap_text(e)))
        res.bills.append(b)
        if b.get("presented") and (res.through is None or b["presented"] > res.through):
            res.through = b["presented"]
    # Bills on our ground from earlier runs that this run's lists did not
    # show (an older bill that moved): their pages are re-read, oldest
    # check first, within the cap, and only the stage is updated.
    for key, (status, areas) in sorted(known["bills"].items()):
        if details >= MG_DETAIL_CAP or budget.exhausted():
            break
        if not key.startswith("mg/") or key in listed:
            continue
        if not (on_our_ground(json.loads(areas or "[]")) or key in known["watched"]):
            continue
        kind, num_year = key[3:].split(" ", 1)
        number, yr = num_year.split("/")
        try:
            d = bill_page(MG_BILL.format(kind=kind, number=number, year=yr), key)
            details += 1
        except FetchError as e:
            res.gap("ALMG bill page {0}: {1}".format(key, gap_text(e)))
            continue
        if d.get("status"):
            res.stages.append((key, d["status"], d.get("step_date"), d.get("local")))
    # Authors as members: 'Name (PARTY)'.
    for b in res.bills:
        for a in (b.get("authors") or "").split("; "):
            m = re.match(r"(.+?)\s*\(([^)]+)\)$", a)
            if m:
                res.members.append(("mg/name:" + m.group(1), "mg", m.group(1), m.group(2)))
    return res


# --- Rio de Janeiro (ALERJ Notes view) ----------------------------------------------

def parse_rj_view(text):
    """One page of ALERJ's bill view: [{bill dict}]."""
    out = []
    for row in re.findall(r'<tr valign="top">(.*?)</tr>', text, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 5:
            continue
        code = fold(cells[0])
        if not re.fullmatch(r"\d{11}", code):
            continue
        year, number = int(code[:4]), int(code[6:])
        href = re.search(r'href="([^"]+OpenDocument)"', row)
        body = fold(cells[2])
        title, _, rest = body.partition(" =>")
        committees = re.search(r"\{(.*?)\}", rest)
        out.append({
            "bill_key": brs_store.bill_key("rj", "PL", number, year), "uf": "rj", "source": "rj",
            "source_id": code, "kind": "PL", "kind_name": "Projeto de Lei",
            "number": number, "year": year, "title": title.strip() or None,
            "presented": iso_mdy(fold(cells[3])), "authors": fold(cells[4]) or None,
            "committees": re.sub(r"\s+", " ", committees.group(1)).strip() if committees else None,
            "url": RJ_HOST + html.unescape(href.group(1)) if href else None,
        })
    return out


def fetch_rj(client, ctx):
    res = Result("rj", "rj")
    tax, budget, known = ctx["tax"], ctx["budget"], ctx["known"]
    first = not ctx["read_ok"].get("rj")
    listed = {}
    for n in range(RJ_SEED_PAGES if first else RJ_MAX_PAGES):
        if budget.exhausted():
            res.gap("ALERJ: time budget reached after {0} page(s)".format(n))
            break
        start = "" if n == 0 else "&Start={0}".format(1 + n * RJ_PAGE_ROWS)
        try:
            got = parse_rj_view(decode(client.get_bytes(RJ_VIEW.format(start=start), FEED,
                                                        "rj-view-{0}".format(n + 1))))
        except RobotsRefused as e:
            res.status, res.detail = "blocked", gap_text(e)
            res.gap("ALERJ: " + res.detail)
            return res
        except FetchError as e:
            res.gap("ALERJ view page {0}: {1}".format(n + 1, gap_text(e)))
            if n == 0:
                res.status, res.detail = "unreachable", gap_text(e)
                return res
            break
        if not got:
            if n == 0:
                res.gap("ALERJ: the view parsed to no bills (page changed shape?)")
            break
        fresh = [b for b in got if b["bill_key"] not in known["bills"]]
        for b in got:
            listed.setdefault(b["bill_key"], b)
        if not first and not fresh:
            break
    for b in listed.values():
        res.bills.append(classified(tax, b, ctx.get("watch_path")))
        if b.get("presented") and (res.through is None or b["presented"] > res.through):
            res.through = b["presented"]
    return res


# --- the SAPL houses ------------------------------------------------------------------

def sapl_bill_type(descricao):
    """True for a SAPL type that is a bill: projeto de lei (any kind),
    proposta de emenda constitucional, projeto de decreto legislativo,
    projeto de código. Not resolutions, indicações or the TCE's anteprojetos."""
    t = plain(descricao).strip()
    return t.startswith(("projeto de lei", "proposta de emenda", "projeto de decreto legislativo",
                         "projeto de codigo"))


def sapl_types(rows):
    """{tipo id: sigla} for the bill types, a repeated sigla made unique
    with its id ('PEC', 'PEC-36')."""
    out, seen = {}, set()
    for r in sorted(rows, key=lambda r: int(r["id"])):
        if not sapl_bill_type(r.get("descricao")):
            continue
        sig = (r.get("sigla") or "").strip() or "T{0}".format(r["id"])
        if sig in seen:
            sig = "{0}-{1}".format(sig, r["id"])
        seen.add(sig)
        out[str(r["id"])] = [sig, (r.get("descricao") or "").strip()]
    return out


def parse_sapl_materia(uf, host, r, types):
    t = types.get(str(r.get("tipo")))
    if not t:
        return None
    try:
        number, year = int(r["numero"]), int(r["ano"])
    except (KeyError, TypeError, ValueError):
        return None
    return {
        "bill_key": brs_store.bill_key(uf, t[0], number, year), "uf": uf, "source": "sapl",
        "source_id": str(r["id"]), "kind": t[0], "kind_name": t[1], "number": number, "year": year,
        "title": re.sub(r"\s+", " ", r.get("ementa") or "").strip() or None,
        "index": (r.get("indexacao") or "").strip() or None,
        "presented": (r.get("data_apresentacao") or "")[:10] or None,
        "status": (r.get("resultado") or "").strip() or None,
        "url": "https://{0}/materia/{1}".format(host, r["id"]),
        "autor_ids": [str(a) for a in (r.get("autores") or [])],
        "updated": (r.get("data_ultima_atualizacao") or "")[:10] or None,
    }


def parse_sapl_tramitacao(row):
    """'PL nº 1 de 2026 | Proposição apresentada em Plenário | 06/10/2026'
    -> (status, ISO date)."""
    parts = [p.strip() for p in (row.get("__str__") or "").split("|")]
    if len(parts) >= 3:
        return parts[1] or None, iso_dmy(parts[-1])
    return None, None


def parse_sapl_vote(uf, r, bill_by_id):
    b = bill_by_id.get(str(r.get("materia")))
    if not b:
        return None
    text = re.sub(r"\s+", " ", r.get("__str__") or "").strip()
    result = text.rsplit("Votação:", 1)[1].strip() if "Votação:" in text else None
    return {
        "vote_key": "{0}/v{1}".format(uf, r["id"]), "uf": uf, "bill_key": b,
        "date": (r.get("data_hora") or "")[:10] or None, "body": "plenary",
        "description": text, "result": result,
        "yes": r.get("numero_votos_sim"), "no": r.get("numero_votos_nao"),
        "abstain": r.get("numero_abstencoes"),
    }


def fetch_sapl(client, ctx, uf):
    source = "sapl:" + uf
    host = SAPL_HOSTS[uf]
    res = Result(source, uf)
    tax, budget, known, today = ctx["tax"], ctx["budget"], ctx["known"], ctx["today"]
    meta = dict(ctx["meta"].get(source) or {})
    api = "https://{0}/api/".format(host)

    def left():
        return budget.seconds - budget.spent()

    def get(path, slug):
        if left() < SAPL_DELAY + 10:
            raise TimeoutError("time budget")
        return json.loads(decode(client.get_bytes(api + path, FEED, "sapl-{0}-{1}".format(uf, slug))))

    try:
        stale = (not meta.get("types") or (meta.get("types_at") or "") <
                 (datetime.date.fromisoformat(today) - datetime.timedelta(days=SAPL_TYPES_DAYS)).isoformat())
        if stale:
            data = get("materia/tipomaterialegislativa/?page_size=100", "tipos")
            meta["types"] = sapl_types(data.get("results") or [])
            meta["types_at"] = today
        types = meta["types"]
        if not types:
            res.status, res.detail = "gap", "no bill types in this house's SAPL"
            res.gap("{0}: {1}".format(brs_store.assembly(uf), res.detail))
            res.meta = meta
            return res
        last = meta.get("last_read")
        since = ((datetime.date.fromisoformat(last) - datetime.timedelta(days=SAPL_REREAD_DAYS))
                 if last else datetime.date.fromisoformat(today) - datetime.timedelta(days=SAPL_FIRST_DAYS))
        rows = []
        for n in range(1, SAPL_MAX_PAGES + 1):
            q = ("materia/materialegislativa/?tipo__in={0}&data_ultima_atualizacao__gte={1}"
                 "&o=-data_ultima_atualizacao&page_size=100&page={2}").format(
                     ",".join(sorted(types, key=int)), since.isoformat(), n)
            data = get(q, "materias-{0}".format(n))
            rows += data.get("results") or []
            if not (data.get("pagination") or {}).get("next_page"):
                break
        else:
            res.gap("{0}: more than {1} bills updated since {2}; the rest next run".format(
                brs_store.assembly(uf), SAPL_MAX_PAGES * 100, since.isoformat()))
        bills = [b for b in (parse_sapl_materia(uf, host, r, types) for r in rows) if b]
        votes = get("sessao/registrovotacao/?data_hora__gte={0}&page_size=100".format(
            since.isoformat()), "votos")
    except RobotsRefused as e:
        res.status, res.detail = ("unreachable" if e.host_skipped else "blocked"), gap_text(e)
        res.gap("{0}: {1}".format(brs_store.assembly(uf), res.detail))
        res.meta = meta
        return res
    except (FetchError, ValueError, TimeoutError) as e:
        res.status, res.detail = "unreachable", gap_text(e)
        res.gap("{0}: {1}".format(brs_store.assembly(uf), res.detail))
        res.meta = meta
        return res
    by_id = dict(known["source_ids"].get(uf, {}))
    details = authors = 0
    for b in bills:
        b = classified(tax, b, ctx.get("watch_path"))
        if b.get("index"):
            areas, terms, tier = classify(tax, b["bill_key"], b["title"], b["index"],
                                          watch_path=ctx.get("watch_path"))
            b.update(areas=areas, terms=terms, tier=tier)
        by_id[b["source_id"]] = b["bill_key"]
        ours = on_our_ground(b["areas"]) or b["bill_key"] in known["watched"]
        if ours and details < SAPL_DETAIL_CAP and left() > SAPL_DELAY + 10:
            try:
                data = get("materia/tramitacao/?materia={0}&o=-data_tramitacao&page_size=1".format(
                    b["source_id"]), "tram-" + b["source_id"])
                details += 1
                if data.get("results"):
                    b["status"], b["status_date"] = parse_sapl_tramitacao(data["results"][0])
            except (FetchError, ValueError, TimeoutError) as e:
                res.gap("{0} tramitação {1}: {2}".format(brs_store.assembly(uf), b["bill_key"], gap_text(e)))
        names = []
        for aid in b.get("autor_ids") or []:
            name = known["members"].get("{0}/autor:{1}".format(uf, aid))
            if name is None and ours and authors < SAPL_AUTHOR_CAP and left() > SAPL_DELAY + 10:
                try:
                    a = get("base/autor/{0}/".format(aid), "autor-" + aid)
                    authors += 1
                    name = (a.get("nome") or a.get("__str__") or "").strip() or None
                    if name:
                        res.members.append(("{0}/autor:{1}".format(uf, aid), uf, name, None))
                except (FetchError, ValueError, TimeoutError) as e:
                    res.gap("{0} autor {1}: {2}".format(brs_store.assembly(uf), aid, gap_text(e)))
            if name:
                names.append(name)
        b["authors"] = "; ".join(names) or None
        res.bills.append(b)
        if b.get("presented") and (res.through is None or b["presented"] > res.through):
            res.through = b["presented"]
    for r in votes.get("results") or []:
        v = parse_sapl_vote(uf, r, by_id)
        if v:
            res.votes.append(v)
    meta["last_read"] = today
    res.meta = meta
    return res


# --- the alternative routes (13 October 2026, second pass) -----------------------
#
# Assemblies whose own bill search is blocked or missing, read where they or
# their state publish the same record in a form a program may read (robots.txt
# asked every run; docs/brazil-regions-scope.md has what was tried per state):
#
#   rn  ALRN's Transparência Legislativa: the JSON its own web app loads
#       (api-transparencialegislativa.al.rn.leg.br; robots.txt sets no rules).
#   ce  ALECE's proposições lists (www2.al.ce.gov.br), one search a year and
#       type: in passage (T) and decided (D), with the law number.
#   pe  ALEPE's open-data API (dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/
#       projetos/?ano=): the XML ALEPE's own proposições app reads.
#   pa  ALEPA's proposições search (a plain form POST, newest ten of a type,
#       gaps filled by number).
#   go  Goiás: the laws ALEGO passed, from the Casa Civil's legislation portal
#       (legisla.casacivil.go.gov.br/api/v2): adopted laws only, no bills.
#   pr  Paraná: the laws ALEP passed, from the Casa Civil's Sistema Estadual de
#       Legislação (www.legislacao.pr.gov.br): adopted laws only. ALEP's own
#       bill search and its open-data API are not read (reCAPTCHA; the API is
#       plain HTTP only).

def _clean(text):
    """Collapse whitespace; the C0 control characters some sources leave
    where a quote or a dash was ('\\u001c', '\\u0013') become the character
    they stood for."""
    text = (text or "").replace("\u001c", "“").replace("\u001d", "”").replace("\u0013", "–")
    text = re.sub(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f]", "", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip() or None


def _int(text):
    """'24.564' or '58 -' -> 24564 / 58; None when there is no number."""
    m = re.search(r"\d[\d.]*", text or "")
    return int(m.group(0).replace(".", "")) if m else None


def _through(res, b):
    if b.get("presented") and (res.through is None or b["presented"] > res.through):
        res.through = b["presented"]


def _years(today):
    """This year, and last year too in January and February."""
    year = int(today[:4])
    return [year] + ([year - 1] if int(today[5:7]) <= 2 else [])


def _fail(res, label, e):
    res.status, res.detail = ("blocked" if isinstance(e, RobotsRefused) and not e.host_skipped
                              else "unreachable"), gap_text(e)
    res.gap("{0}: {1}".format(label, res.detail))
    return res


# Rio Grande do Norte (ALRN): the JSON the Transparência Legislativa app loads

RN_API = "https://api-transparencialegislativa.al.rn.leg.br/elegis-api-transp-legislativa/"
RN_PAGE = "https://transparencialegislativa.al.rn.leg.br/projeto/{0}"
RN_TYPES = {1: ("PL", "Projeto de Lei"), 2: ("PLC", "Projeto de Lei Complementar"),
            6: ("PDL", "Projeto de Decreto Legislativo"), 7: ("PEC", "Proposta de Emenda Constitucional")}
RN_PAGE_SIZE = 50
RN_MAX_PAGES = 3
RN_RESULT = {"A": "Aprovada", "R": "Rejeitada", "X": "Retirada de pauta", "N": "Não apreciada"}
RN_VIA = "ALRN's Transparência Legislativa"


def parse_rn_processo(r):
    """One ALRN processo -> (bill dict, member tuple or None), or None for a
    type that is not a bill."""
    prop = r.get("propositura") or {}
    t = RN_TYPES.get((prop.get("tipo") or {}).get("id"))
    if not t or prop.get("numero") is None or prop.get("ano") is None:
        return None
    ini = r.get("iniciativa") or {}
    par = ini.get("parlamentar") or {}
    party = (par.get("partido") or {}).get("nome")
    name = par.get("nomeParlamentar")
    if name:
        name = re.sub(r"^DEPUTAD[OA]\s+", "", name).strip()
        authors = "{0} ({1})".format(name, party) if party else name
    else:
        authors = _clean(ini.get("descricao"))
    pubs = [p for p in (r.get("publicacao") or []) if (p.get("situacaoProcesso") or {}).get("nome")]
    pubs.sort(key=lambda p: ((p.get("origem") or {}).get("data") or ""))
    status, when = None, None
    if pubs:
        status = _clean(pubs[-1]["situacaoProcesso"]["nome"])
        when = ((pubs[-1].get("origem") or {}).get("data") or "")[:10] or None
    if r.get("dataArquivamento"):
        status, when = "Arquivado", r["dataArquivamento"][:10]
    number, year = int(prop["numero"]), int(prop["ano"])
    b = {"bill_key": brs_store.bill_key("rn", t[0], number, year), "uf": "rn", "source": "rn",
         "source_id": str(r.get("id")), "kind": t[0], "kind_name": t[1], "number": number, "year": year,
         "title": _clean(r.get("ementa")), "authors": authors,
         "presented": (r.get("dataEntrada") or "")[:10] or None, "status": status,
         "status_date": when, "url": RN_PAGE.format(r.get("id"))}
    member = ("rn/{0}".format(par["id"]), "rn", name, party) if name and par.get("id") else None
    return b, member


def parse_rn_vote(r):
    """A processo of ALRN's 'últimas votações' -> vote dict (result only:
    the list prints no tally), or None."""
    got = parse_rn_processo(r)
    v = r.get("resultadoVotacao") or {}
    if not got or not v.get("id"):
        return None
    b = got[0]
    code = v.get("resultadoVotacao")
    return {"vote_key": "rn/v{0}".format(v["id"]), "uf": "rn", "bill_key": b["bill_key"],
            "date": (v.get("dataSituacaoAbertura") or "")[:10] or None, "body": "plenary",
            "description": "Plenary vote, sitting {0}".format((v.get("reuniao") or {}).get("id") or "?"),
            "result": RN_RESULT.get(code, code), "yes": None, "no": None, "abstain": None}


def fetch_rn(client, ctx):
    res = Result("rn", "rn")
    tax, budget, known = ctx["tax"], ctx["budget"], ctx["known"]
    first = not ctx["read_ok"].get("rn")
    listed = {}

    def get(path, slug):
        return json.loads(decode(client.get_bytes(RN_API + path, FEED, "rn-" + slug)))

    try:
        for tid, (kind, _name) in RN_TYPES.items():
            for n in range(1 if first else RN_MAX_PAGES):
                if budget.exhausted():
                    res.gap("ALRN: time budget reached in the {0} list".format(kind))
                    break
                data = get("processo?pagina={0}&tamanhoPagina={1}&tipoPropositura={2}".format(
                    n, RN_PAGE_SIZE, tid), "{0}-{1}".format(kind.lower(), n))
                rows = data.get("dados") or []
                fresh = 0
                for r in rows:
                    got = parse_rn_processo(r)
                    if not got:
                        continue
                    b, member = got
                    fresh += b["bill_key"] not in known["bills"] and b["bill_key"] not in listed
                    listed.setdefault(b["bill_key"], b)
                    if member:
                        res.members.append(member)
                if len(rows) < RN_PAGE_SIZE or not fresh:
                    break
        votes = get("processo/ultimas-votacoes?pagina=0&tamanhoPagina=50", "votos")
    except (FetchError, ValueError) as e:
        if not listed:
            return _fail(res, "ALRN (Rio Grande do Norte)", e)
        res.gap("ALRN: " + gap_text(e))
        votes = {}
    for r in votes.get("dados") or []:
        v = parse_rn_vote(r)
        if not v:
            continue
        got = parse_rn_processo(r)
        listed.setdefault(v["bill_key"], got[0])
        res.votes.append(v)
    for b in listed.values():
        b = classified(tax, b, ctx.get("watch_path"))
        res.bills.append(b)
        _through(res, b)
    return res


# Ceará (ALECE): the proposições lists on www2.al.ce.gov.br

CE_BASE = "https://www2.al.ce.gov.br/legislativo/proposicoes/"
CE_SEARCH = CE_BASE + "busca.php?nome={leg}_legislatura&tabela={table}&opcao={opcao}"
CE_TABLES = (("projeto_lei", "PL", "Projeto de Lei"), ("projeto_compl", "PLC", "Projeto de Lei Complementar"),
             ("projeto_emen", "PEC", "Proposta de Emenda Constitucional"),
             ("projeto_decre", "PDL", "Projeto de Decreto Legislativo"))
# The list's own abbreviations, spelled out.
CE_WORDS = (("tramit", "Tramitando"), ("delib", "Deliberado"), ("aprov", "Aprovado"),
            ("rejeit", "Rejeitado"), ("retir", "Retirado"), ("prejud", "Prejudicado"),
            ("arquiv", "Arquivado"), ("vetad", "Vetado"), ("veto", "Veto"), ("dil", "Em diligência"),
            ("sobrest", "Sobrestado"), ("visto", "Pedido de vista"), ("prazo", "Prazo"))


def ce_legislature(today):
    """The Ceará legislature in office: the 31st from 1 February 2023, a new
    one every four years."""
    y, m = int(today[:4]), int(today[5:7])
    return 31 + (y - 2023 - (1 if m < 2 else 0)) // 4


def _ce_word(text):
    t = plain(text).strip(" .-")
    if not t:
        return None
    for prefix, word in CE_WORDS:
        if t.startswith(prefix):
            return word
    return _clean(text)


def parse_ce_search(text, table, kind, kind_name, leg):
    """One ALECE search page -> [bill dict]. Cells: number, year (two
    digits), author, law number, ementa (capitals), situação, result, link."""
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 7:
            continue
        number, yy = _int(fold(cells[0])), _int(fold(cells[1]))
        if number is None or yy is None:
            continue
        year = yy + 2000 if yy < 100 else yy
        law = fold(cells[3]).strip(" -") or None
        words = [w for w in (_ce_word(fold(cells[5])), _ce_word(fold(cells[6]))) if w]
        status = ": ".join(words) or None
        if status and law:
            status += " (Lei nº {0})".format(law)
        code = re.search(r"codigo=(\d+)", row)
        out.append({
            "bill_key": brs_store.bill_key("ce", kind, number, year), "uf": "ce", "source": "ce",
            "source_id": code.group(1) if code else None, "kind": kind, "kind_name": kind_name,
            "number": number, "year": year, "title": _clean(fold(cells[4])),
            "authors": _clean(re.sub(r"^(AUTORIA:\s*)?(DEPUTAD[OA]\s+)?", "", fold(cells[2]))), "status": status,
            "url": (CE_BASE + "ver.php?nome={0}_legislatura&tabela={1}&codigo={2}".format(
                leg, table, code.group(1))) if code else None,
        })
    return out


def fetch_ce(client, ctx):
    res = Result("ce", "ce")
    tax, budget = ctx["tax"], ctx["budget"]
    leg = ce_legislature(ctx["today"])
    listed, failed, tried = {}, 0, 0
    for table, kind, name in CE_TABLES:
        for opcao in ("T", "D"):
            for year in _years(ctx["today"]):
                if budget.exhausted():
                    res.gap("ALECE: time budget reached in the {0} lists".format(kind))
                    break
                tried += 1
                try:
                    text = client.post_form(CE_SEARCH.format(leg=leg, table=table, opcao=opcao),
                                            {"pesquisa": "{0:02d}".format(year % 100), "escolha": "ano",
                                             "B1": "Busca"},
                                            FEED, "ce-{0}-{1}-{2}".format(kind.lower(), opcao, year),
                                            encoding="latin-1")
                except RobotsRefused as e:
                    return _fail(res, "ALECE (Ceará)", e)
                except FetchError as e:
                    failed += 1
                    res.gap("ALECE {0} {1} list: {2}".format(kind, opcao, gap_text(e)))
                    continue
                for b in parse_ce_search(text, table, kind, name, leg):
                    # A bill decided this year is in the D list; it wins.
                    if opcao == "D" or b["bill_key"] not in listed:
                        listed[b["bill_key"]] = b
    if tried and failed == tried:
        res.status, res.detail = "unreachable", res.gaps[-1] if res.gaps else "no answer"
        return res
    for b in listed.values():
        res.bills.append(classified(tax, b, ctx.get("watch_path")))
    # The lists print no dates: new bills are dated the day first listed.
    return res


# Pernambuco (ALEPE): the open-data API's projetos, one request a year

PE_URL = "https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/?ano={0}"
PE_PAGE = "https://proposicoes.alepe.pe.gov.br/proposicoes/detalhes?docid={0}&tipoprop=p"
PE_TYPES = {"PROJETO DE LEI ORDINARIA": ("PLO", "Projeto de Lei Ordinária"),
            "PROJETO DE LEI COMPLEMENTAR": ("PLC", "Projeto de Lei Complementar"),
            "PROPOSTA DE EMENDA A CONSTITUICAO": ("PEC", "Proposta de Emenda à Constituição"),
            "PROJETO DE DECRETO LEGISLATIVO": ("PDL", "Projeto de Decreto Legislativo")}


def parse_pe_projetos(raw):
    """ALEPE's projetos XML -> [bill dict] (bills only: no resolutions,
    budget laws keep their type name and are left out)."""
    out = []
    root = ET.fromstring(raw)
    for p in root.iter("projeto"):
        tipo = re.sub(r"\s+DESARQUIVAD[OA]$", "", plain(p.get("tipo")).upper().strip())
        t = PE_TYPES.get(tipo)
        if not t:
            continue
        try:
            number, year = int(p.get("numero")), int(p.get("ano"))
        except (TypeError, ValueError):
            continue
        authors = [a.get("nome") for a in p.iter("autor") if a.get("nome")]
        status = "Desarquivado" if "DESARQUIVAD" in (p.get("tipo") or "").upper() else None
        out.append({
            "bill_key": brs_store.bill_key("pe", t[0], number, year), "uf": "pe", "source": "pe",
            "source_id": p.get("docid"), "kind": t[0], "kind_name": t[1], "number": number, "year": year,
            "title": _clean(p.get("ementa")), "authors": "; ".join(authors) or None,
            "presented": iso_dmy(p.get("dataPublicacao")), "status": status,
            "url": PE_PAGE.format(p.get("docid")) if p.get("docid") else None,
        })
    return out


def fetch_pe(client, ctx):
    res = Result("pe", "pe")
    tax = ctx["tax"]
    for year in _years(ctx["today"]):
        try:
            raw = client.get_bytes(PE_URL.format(year), FEED, "pe-projetos-{0}".format(year), archive=False)
            bills = parse_pe_projetos(raw)
        except (FetchError, ET.ParseError) as e:
            if not res.bills:
                return _fail(res, "ALEPE (Pernambuco)", e)
            res.gap("ALEPE projetos {0}: {1}".format(year, gap_text(e)))
            continue
        for b in bills:
            b = classified(tax, b, ctx.get("watch_path"))
            res.bills.append(b)
            _through(res, b)
    return res


# Pará (ALEPA): the proposições search, a plain form POST

PA_URL = "https://www.alepa.pa.gov.br/Legislativo/Proposicoes"
PA_HOST = "https://www.alepa.pa.gov.br"
PA_TYPES = ((3, "PLO", "Projeto de Lei Ordinária"), (4, "PLC", "Projeto de Lei Complementar"),
            (2, "PEC", "Projeto de Emenda Constitucional"), (1, "PDL", "Projeto de Decreto Legislativo"))
PA_FILL_CAP = 12        # numbered gaps looked up one by one per run
PA_CARD = re.compile(r"""onCardClick\("([^"]+)"\)'\s*class='card-proposicao'>\s*<h3[^>]*>(.*?)</h3>\s*"""
                     r"""<span>(.*?)</span>\s*<p>(.*?)</p>""", re.S)


def parse_pa_cards(text):
    """ALEPA's result cards -> [bill dict]: author, 'PROJETO DE LEI
    ORDINÁRIA Nº 640/2026, DE 09/09/2026', ementa, detail link. The type is
    read off the card (cards of other types are left out)."""
    out = []
    names = {plain(n).upper(): (k, n) for _t, k, n in PA_TYPES}
    for link, author, head, ementa in PA_CARD.findall(text):
        m = re.search(r"^(.*?)\s+N[º°o]\s*(\d+)/(\d{4}),?\s*DE\s*(\d{1,2}/\d{1,2}/\d{4})", fold(head))
        t = names.get(plain(m.group(1)).upper().strip()) if m else None
        if not t:
            continue
        kind, kind_name = t
        m = re.search(r"N[º°o]\s*(\d+)/(\d{4}),?\s*DE\s*(\d{1,2}/\d{1,2}/\d{4})", fold(head))
        number, year = int(m.group(1)), int(m.group(2))
        sid = re.search(r"IdProposicao=(\d+)", link)
        author = _clean(fold(author))
        if author:
            author = re.sub(r"^DEP\.\s+", "", author)
        out.append({
            "bill_key": brs_store.bill_key("pa", kind, number, year), "uf": "pa", "source": "pa",
            "source_id": sid.group(1) if sid else None, "kind": kind, "kind_name": kind_name,
            "number": number, "year": year, "title": _clean(fold(ementa)), "authors": author,
            "presented": iso_dmy(m.group(3)), "url": PA_HOST + html.unescape(link),
        })
    return out


def fetch_pa(client, ctx):
    res = Result("pa", "pa")
    tax, budget, known = ctx["tax"], ctx["budget"], ctx["known"]
    first = not ctx["read_ok"].get("pa")
    year = int(ctx["today"][:4])
    listed = {}

    def search(tid, kind, name, numero=None):
        fields = {"Ano": str(year), "ComboBoxTipoProposicao_VI": str(tid), "ComboBoxTipoProposicao": str(tid)}
        if numero:
            fields["Numero"] = str(numero)
        text = client.post_form(PA_URL, fields, FEED, "pa-{0}-{1}{2}".format(
            kind.lower(), year, "-" + str(numero) if numero else ""))
        return [b for b in parse_pa_cards(text) if b["kind"] == kind]

    try:
        for tid, kind, name in PA_TYPES:
            if budget.exhausted():
                res.gap("ALEPA: time budget reached in the {0} search".format(kind))
                break
            got = search(tid, kind, name)
            for b in got:
                listed.setdefault(b["bill_key"], b)
            # The search shows the newest ten. Numbers between the last run's
            # newest and this page's oldest are asked one by one (a few a run).
            if first or len(got) < 10:
                continue
            prefix = "pa/{0} ".format(kind)
            seen = [int(k[len(prefix):].split("/")[0]) for k in known["bills"]
                    if k.startswith(prefix) and k.endswith("/{0}".format(year))]
            if not seen:
                continue
            low = min(b["number"] for b in got)
            missing = [n for n in range(max(seen) + 1, low)][:PA_FILL_CAP]
            for n in missing:
                if budget.exhausted():
                    break
                for b in search(tid, kind, name, numero=n):
                    listed.setdefault(b["bill_key"], b)
            if max(seen) + 1 + PA_FILL_CAP < low:
                res.gap("ALEPA {0}: more than {1} new since the last run; the rest next run".format(
                    kind, PA_FILL_CAP))
    except FetchError as e:
        if not listed:
            return _fail(res, "ALEPA (Pará)", e)
        res.gap("ALEPA: " + gap_text(e))
    for b in listed.values():
        b = classified(tax, b, ctx.get("watch_path"))
        res.bills.append(b)
        _through(res, b)
    return res


# Adopted laws from the states' own legislation portals (Goiás, Paraná)

def law_bill(uf, source, kind, kind_name, number, year, title, published, status, url, sid=None):
    """An adopted law as a brs_bills row: keyed like a bill, '<uf>/<Lei|LC|EC>
    <number>/<year>', its publication date as 'presented', so the edition
    shows it the week it is published."""
    return {"bill_key": brs_store.bill_key(uf, kind, number, year), "uf": uf, "source": source,
            "source_id": sid, "kind": kind, "kind_name": kind_name, "number": number, "year": year,
            "title": title, "presented": published, "status": status, "status_date": published,
            "url": url}


GO_URL = ("https://legisla.casacivil.go.gov.br/api/v2/pesquisa/legislacoes?page={page}"
          "&qtd_por_pagina=50&tipo_legislacao=2,1,13&ano={year}&ordenarPor=data")
GO_PAGE = "https://legisla.casacivil.go.gov.br/pesquisa_legislacao/{0}"
GO_KINDS = {"lei ordinaria": ("Lei", "Lei Ordinária"), "lei complementar": ("LC", "Lei Complementar"),
            "emenda constitucional": ("EC", "Emenda Constitucional")}
GO_MAX_PAGES = 3


def parse_go_laws(data):
    out = []
    for r in data.get("resultados") or []:
        k = GO_KINDS.get(plain((r.get("tipo_legislacao") or {}).get("nome")).strip())
        number, year = _int(r.get("numero")), r.get("ano")
        if not k or number is None or not year:
            continue
        diarios = r.get("diarios") or []
        published = iso_dmy((diarios[0] if diarios else {}).get("data_diario") or r.get("data_legislacao"))
        state = ((r.get("estado_legislacao") or {}).get("nome") or "").strip()
        status = "{0} publicada{1}{2}".format(
            k[1], " no Diário Oficial nº {0}".format(diarios[0]["numero"]) if diarios and diarios[0].get("numero")
            else "", " ({0})".format(state.lower()) if state else "")
        out.append(law_bill("go", "go", k[0], k[1], number, int(year), _clean(r.get("ementa")), published,
                            status, GO_PAGE.format(r.get("id")), str(r.get("id"))))
    return out


def fetch_go(client, ctx):
    res = Result("go", "go")
    tax, budget, known = ctx["tax"], ctx["budget"], ctx["known"]
    first = not ctx["read_ok"].get("go")
    listed = {}
    try:
        for year in _years(ctx["today"]):
            for page in range(1, (1 if first else GO_MAX_PAGES) + 1):
                if budget.exhausted():
                    break
                data = json.loads(decode(client.get_bytes(GO_URL.format(page=page, year=year), FEED,
                                                          "go-leis-{0}-{1}".format(year, page))))
                got = parse_go_laws(data)
                fresh = [b for b in got if b["bill_key"] not in known["bills"] and b["bill_key"] not in listed]
                for b in got:
                    listed.setdefault(b["bill_key"], b)
                if len(data.get("resultados") or []) < 50 or not fresh:
                    break
    except (FetchError, ValueError) as e:
        if not listed:
            return _fail(res, "Goiás laws (Casa Civil)", e)
        res.gap("Goiás laws: " + gap_text(e))
    for b in listed.values():
        b = classified(tax, b, ctx.get("watch_path"))
        res.bills.append(b)
        _through(res, b)
    return res


PR_LIST = ("https://www.legislacao.pr.gov.br/legislacao/listarAtosAno.do?action=listarAtos"
           "&anoAto={year}&isPaginado=false")
PR_PAGE = "https://www.legislacao.pr.gov.br/legislacao/listarAtosAno.do?action=exibir&codAto={0}"
# The system's act types: id -> (kind, name).
PR_TYPES = ((1, "Lei", "Lei"), (3, "LC", "Lei Complementar"), (9, "EC", "Emenda Constitucional"))


def parse_pr_laws(text):
    """The Sistema Estadual de Legislação's year list -> [law dict]: rows of
    'Lei 23.448 - 9 de setembro de 2026' (the type read off the epigraph:
    'Lei Complementar 270 - ...', 'Emenda Constitucional 58 - ...'), súmula,
    publication date."""
    out = []
    for code, epigrafe in re.findall(r'<div id="(\d+)_epigrafeAto">(.*?)</div>', text, re.S):
        m = re.search(r"^(.*?)\s*(\d[\d.]*)\s*-\s*.*?(\d{4})\s*$", fold(epigrafe))
        if not m:
            continue
        head = plain(m.group(1)).strip()
        kind, kind_name = next(((k, n) for _t, k, n in sorted(PR_TYPES, key=lambda t: -len(t[2]))
                                if head == plain(n)), (None, None))
        if not kind:
            continue
        m = re.search(r"(\d[\d.]*)\s*-\s*.*?(\d{4})\s*$", fold(epigrafe))
        sumula = re.search(r'<div id="{0}_descricaoItemAto">(.*?)</div>'.format(code), text, re.S)
        pub = re.search(r'<div id="{0}_dataPublicacao">(.*?)</div>'.format(code), text, re.S)
        published = iso_dmy(fold(pub.group(1))) if pub else None
        out.append(law_bill("pr", "pr", kind, kind_name, _int(m.group(1)), int(m.group(2)),
                            _clean(fold(sumula.group(1))) if sumula else None, published,
                            "{0} publicada".format(kind_name), PR_PAGE.format(code), code))
    return out


def fetch_pr(client, ctx):
    res = Result("pr", "pr")
    tax, budget = ctx["tax"], ctx["budget"]
    listed = {}
    try:
        for year in _years(ctx["today"]):
            for tid, kind, name in PR_TYPES:
                if budget.exhausted():
                    break
                fields = {"codTipoAto": str(tid), "codTipoAtoSelecionado": str(tid), "codOrgaoUnidade": "1100",
                          "codOrgaoUnidadeSelecionado": "1100", "isPaginado": "false", "site": "1"}
                text = client.post_form(PR_LIST.format(year=year), fields, FEED,
                                        "pr-{0}-{1}".format(kind.lower(), year))
                for b in parse_pr_laws(text):
                    if b["kind"] == kind:
                        listed.setdefault(b["bill_key"], b)
    except FetchError as e:
        if not listed:
            return _fail(res, "Paraná laws (Casa Civil)", e)
        res.gap("Paraná laws: " + gap_text(e))
    for b in listed.values():
        b = classified(tax, b, ctx.get("watch_path"))
        res.bills.append(b)
        _through(res, b)
    return res


ALT_FETCHERS = {"rn": fetch_rn, "ce": fetch_ce, "pe": fetch_pe, "pa": fetch_pa, "go": fetch_go,
                "pr": fetch_pr}


# --- writing -------------------------------------------------------------------------

def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))
    print("  [gap] " + detail)


def store_result(conn, res, today, now):
    """Write one source's result. Returns (bills, new, on our ground)."""
    seed = conn.execute("SELECT 1 FROM brs_reads WHERE source=? AND last_ok IS NOT NULL",
                        (res.source,)).fetchone() is None
    for member_key, uf, name, party in res.members:
        brs_store.upsert_member(conn, member_key, uf, name, party, today)
    new = ours = 0
    for b in res.bills:
        is_new, _changed = brs_store.upsert_bill(conn, b, b.get("areas"), b.get("terms"),
                                                 b.get("tier"), today, seed)
        new += is_new
        ours += on_our_ground(b.get("areas"))
    for key, status, when, committees in res.stages:
        old = conn.execute("SELECT status FROM brs_bills WHERE bill_key=?", (key,)).fetchone()
        if old is None:
            continue
        if (old[0] or "") != status:
            conn.execute("UPDATE brs_bills SET status=?, status_date=?, "
                         "committees=COALESCE(?, committees), last_seen=? WHERE bill_key=?",
                         (status, when or today, committees, today, key))
        else:
            conn.execute("UPDATE brs_bills SET last_seen=? WHERE bill_key=?", (today, key))
    keys = {b["bill_key"] for b in res.bills}
    for v in res.votes:
        if v["bill_key"] not in keys and not conn.execute(
                "SELECT 1 FROM brs_bills WHERE bill_key=?", (v["bill_key"],)).fetchone():
            continue
        brs_store.upsert_vote(conn, v, today)
        if v["vote_key"] in res.positions:
            brs_store.replace_positions(conn, v["vote_key"], res.positions[v["vote_key"]])
    for g in res.gaps:
        _gap(conn, today, g)
    status = res.status
    detail = res.detail or ("; ".join(res.gaps)[:300] if res.gaps else None)
    brs_store.record_read(conn, res.source, res.uf, status, detail, len(res.bills), new,
                          res.through, now, res.meta)
    conn.commit()
    return len(res.bills), new, ours


def snapshot(conn):
    """What the fetchers may read of the store, taken before they start."""
    bills, watched, source_ids = {}, set(brs_store.watchlist()), {}
    for key, uf, sid, status, areas in conn.execute(
            "SELECT bill_key, uf, source_id, status, areas FROM brs_bills"):
        bills[key] = (status, areas)
        if sid:
            source_ids.setdefault(uf, {})[sid] = key
    members = {k: n for k, n in conn.execute("SELECT member_key, name FROM brs_members")}
    meta, read_ok = {}, {}
    for source, m, last_ok in conn.execute("SELECT source, meta, last_ok FROM brs_reads"):
        try:
            meta[source] = json.loads(m) if m else {}
        except ValueError:
            meta[source] = {}
        read_ok[source] = bool(last_ok)
    return {"bills": bills, "watched": watched, "source_ids": source_ids,
            "members": members}, meta, read_ok


def make_client(throttle_hosts=HOST_THROTTLE, budget=None):
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"), throttle=1.0, max_retries=2)
    for host, s in throttle_hosts.items():
        client.set_host_throttle(host, s)
    for host in SAPL_HOSTS.values():
        client.set_host_throttle(host, SAPL_DELAY)
    # robots.txt is asked on THIS run, per host, before any request; a
    # Crawl-delay above the throttle raises that host's interval.
    return GuardedClient(client, FEED, budget=budget)


def fetch_one(source, ctx, client_factory):
    client = client_factory()
    try:
        if source == "sp":
            return fetch_sp(client, ctx)
        if source == "mg":
            return fetch_mg(client, ctx)
        if source == "rj":
            return fetch_rj(client, ctx)
        if source in ALT_FETCHERS:
            return ALT_FETCHERS[source](client, ctx)
        return fetch_sapl(client, ctx, source.split(":", 1)[1])
    except RobotsRefused as e:
        res = Result(source, source.split(":")[-1] if ":" in source else source)
        res.status, res.detail = "blocked", gap_text(e)
        res.gap("{0}: {1}".format(source, res.detail))
        return res
    except Exception as e:  # noqa: BLE001 -- one source never costs the others
        res = Result(source, source.split(":")[-1] if ":" in source else source)
        res.status, res.detail = "gap", "{0}: {1}".format(type(e).__name__, str(e)[:160])
        res.gap("{0} failed: {1}".format(source, res.detail))
        return res


def run(conn, sources, tax, today, budget, client_factory, now=None, workers=None, sleep=None):
    now = now or datetime.datetime.now().isoformat(timespec="seconds")
    known, meta, read_ok = snapshot(conn)
    ctx = {"tax": tax, "budget": budget, "known": known, "meta": meta, "read_ok": read_ok,
           "today": today, "sleep": sleep}
    with ThreadPoolExecutor(workers or max(1, len(sources))) as ex:
        results = list(ex.map(lambda s: fetch_one(s, ctx, client_factory), sources))
    gaps = 0
    for res in results:
        n, new, ours = store_result(conn, res, today, now)
        gaps += len(res.gaps)
        print("br-states {0}: {1} bill(s) listed, {2} new, {3} on our ground, {4} vote(s), "
              "{5} gap(s) [{6}]".format(res.source, n, new, ours, len(res.votes), len(res.gaps),
                                         res.status))
    return results, gaps


def reclassify(conn, tax, watch_path=None):
    n = ours = 0
    for key, title in conn.execute("SELECT bill_key, title FROM brs_bills").fetchall():
        areas, terms, tier = classify(tax, key, title, watch_path=watch_path)
        conn.execute("UPDATE brs_bills SET areas=?, matched_terms=?, tier=? WHERE bill_key=?",
                     (None if areas is None else brs_store.dumps(areas), brs_store.dumps(terms),
                      tier, key))
        n += 1
        ours += on_our_ground(areas)
    conn.commit()
    print("br-states: {0} bill(s) reclassified, {1} on our ground".format(n, ours))
    return n, ours


def summary(conn):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    print("br-states store: {0} state bill(s) from {1} assembly(ies), {2} vote(s), {3} position(s)".format(
        n("SELECT COUNT(*) FROM brs_bills"), n("SELECT COUNT(DISTINCT uf) FROM brs_bills"),
        n("SELECT COUNT(*) FROM brs_votes"), n("SELECT COUNT(*) FROM brs_positions")))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"),
                    help="store path (default: the shared store)")
    ap.add_argument("--sources", help="comma-separated: " + ",".join(SOURCE_ORDER))
    ap.add_argument("--taxonomy", help="a taxonomy file (default config/taxonomy-pt.yaml)")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive every stored bill's areas, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--date", help="ISO date to stamp the run with (tests)")
    args = ap.parse_args(argv)
    tax = load_taxonomy(args.taxonomy)
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn, tax)
        summary(conn)
        conn.close()
        return 0
    wanted = [s.strip() for s in args.sources.split(",")] if args.sources else list(SOURCE_ORDER)
    for s in wanted:
        if s not in SOURCE_ORDER:
            print("br-states: unknown source {0!r}".format(s))
            return 1
    today = args.date or datetime.date.today().isoformat()
    budget = drain.Budget(args.budget_seconds)
    _results, gaps = run(conn, wanted, tax, today, budget, lambda: make_client(budget=budget))
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
