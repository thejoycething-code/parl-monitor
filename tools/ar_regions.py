#!/usr/bin/env python3
"""Argentina's provincial legislatures: the 24 jurisdictions' laws and eleven
legislatures' bills (13 October 2026).

    python3 tools/ar_regions.py                        # the weekly read
    python3 tools/ar_regions.py --only saij caba       # some sources only
    python3 tools/ar_regions.py --saij-pages 12        # a deeper SAIJ read (a seed)
    python3 tools/ar_regions.py --dry-run
    python3 tools/ar_regions.py --reclassify
    python3 tools/ar_regions.py --db /tmp/ar.db

docs/argentina-regions-scope.md says how every source was measured. Ten
sources, read politely, each a few requests a week:

  LAWS (arp_laws), all 24 jurisdictions
  * saij      SAIJ's search (www.saij.gob.ar/busqueda): a JSON reply listing
              provincial laws newest first, with the official title, a
              sumario, the province and the Boletín Oficial's date. Four
              pages of 50 a week (about two months of laws; measured: 118
              laws from 17 provinces in the newest 200 rows, published one
              to three weeks before SAIJ lists them).
  * normas-gba  Buenos Aires province's normative system (the Boletín
              Oficial's, normas.gba.gob.ar): its newest laws, two pages.
              Earlier than SAIJ for the largest province.

  BILLS (arp_bills), eleven legislatures
  * ba-dip    Cámara de Diputados de la Provincia de Buenos Aires: the
              read-only search by "fecha de estado parlamentario" (a form
              POST), last LOOKBACK_DAYS days, 200 rows a page. Every
              expediente entering the chamber, the Senate's included (origin
              HS) and the Executive's (PE).
  * caba      Legislatura de la Ciudad: the expediente search's own XML web
              service (GetExpedienteAvanzada, a read-only POST), every
              expediente started in the last CABA_STATUS_DAYS days, so the
              stage (`ubicacion`, `descripcion`, `TieneSancion`) is
              refreshed for three months after entry.
  * cba       Legislatura de Córdoba (unicameral): Gestión Legislativa
              Digital's Asuntos Entrados, one page per session, read once
              (the cursor keeps the sessions read).
  * er-sen    Cámara de Senadores de Entre Ríos: the project list
              (buscador-proyectos), newest first, until a page is older
              than the window; it prints media sanción and sanción.
  * rn        Legislatura de Río Negro: the year's project list, 100 newest
              (GET; no date in the list, so new by first sight).
  * chu       Legislatura del Chubut: LARUS's public document API, 50 newest,
              with the current stage. Staff logins in the reply are dropped.
  * juj       Legislatura de Jujuy: the REST project list, 20 newest.
  * ctes-dip  Cámara de Diputados de Corrientes: the expediente list (five a
              page), until a page is older than the window.
  * sf-dip    Cámara de Diputados de Santa Fe (SIEL, added 13 October 2026):
              the expediente list (20 a page, newest first) until a page is
              older than the window, then the media-sanción and sanción
              lists (the search form, by state). SIEL's robots.txt names AI
              agents and has no '*' group: the reader stops before any
              request if a rule ever applies to OUR user agent.
  * sal-sen   Cámara de Senadores de Salta (added 13 October 2026): the
              project posts of its WordPress site (REST), 100 newest by
              entry and 50 approved by last change (a post moves category
              when approved).
  * sal-dip   Cámara de Diputados de Salta (added 13 October 2026): this
              year's approved laws, resolutions and declarations (three
              pages); its pending lists are empty and its intake is PDF.
  * sal-dip-ae  the same chamber's intake (added 13 October 2026): the
              Asuntos Entrados index, then each new sitting's PDF (at most
              SAL_AE_PDFS a run, read with pypdf), every project of law,
              resolution and declaration a new bill under the same
              'sal-dip:<expediente>' key the approved lists use. Read after
              sal-dip, and only for keys not stored yet, so an approval is
              never overwritten by the older intake line. The first read
              takes the newest PDFs only (a seed) and marks the older ones
              read.

NOT READ, and why (the scope doc has the measurements): the Buenos Aires
Senate's search carries a reCAPTCHA; Mendoza's Senate answers 403 and its
Chamber asks a 60 s Crawl-delay and timed out; Santa Fe's Senate did not
answer; Tucumán's expediente app did not
answer at first (it did later: not built yet). Misiones (JSON per deputy,
about 40 requests), Tierra del Fuego (a pending-business page), Neuquén,
San Juan, La Rioja and Chaco (PDFs or POST searches) are listed in the
scope doc as next steps; Santa Cruz's robots.txt rules out its pages,
Santiago del Estero has no site, San Luis's Diputados and La Pampa timed
out, Catamarca's Senate answered 403. Their laws arrive through SAIJ.

WHAT IS CLASSIFIED: the title or extracto (and a law's sumario), never full
texts; taxonomy-es with Argentina's country tag, plus watchlist-ar's
`provincial` section by key.

ROBOTS.TXT AT RUN TIME: every request goes through src/robots_guard's
GuardedClient (none of these is a documented API): robots.txt read once per
host per run; a refusal or an unreachable robots.txt is a [gap] line and an
arp_reads status, never fatal. A Crawl-delay raises that host's interval.

ONE WRITER AT A TIME on data/parl-monitor.db. Exit 3: stored what it could
and recorded gaps. --budget-seconds stops before the next source when out
of time (a gap).
"""

from __future__ import annotations

import argparse
import datetime
import html as htmllib
import json
import os
import re
import sys
import time
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import yaml  # noqa: E402

from src import ar_regions_store as store  # noqa: E402
from src import db  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from src.robots_guard import GuardedClient, RobotsRefused  # noqa: E402

FEED = "ar-regions"
LOOKBACK_DAYS = 14
CABA_STATUS_DAYS = 120
CBA_SESSION_DAYS = 28
ER_MAX_PAGES = 6
SAIJ_PAGES = 4
SAIJ_PAGE_SIZE = 50
NORMAS_PAGES = 2
BA_DIP_MAX_PAGES = 6
WATCHLIST = os.path.join(ROOT, "config", "watchlist-ar.yaml")
SUMMARY_CHARS = 2000
SOURCES = ("saij", "normas-gba", "ba-dip", "caba", "cba", "er-sen", "rn", "chu", "juj", "ctes-dip",
           "sf-dip", "sal-sen", "sal-dip", "sal-dip-ae")
CTES_MAX_PAGES = 8
SF_MAX_PAGES = 8
SAL_SEN_NEW = 100
SAL_SEN_MOVED = 50

SAIJ = ("https://www.saij.gob.ar/busqueda?o={offset}&p={size}&f=Total%7CTipo+de+Documento"
        "%2FLegislaci%C3%B3n%2FLey%7CJurisdicci%C3%B3n%2FLocal&s=fecha-rango%7CDESC&v=colapsada")
SAIJ_DOC = "https://www.saij.gob.ar/{0}/{1}"
NORMAS = ("https://normas.gba.gob.ar/resultados?page={page}&q%5Bsort%5D=by_publication_date_desc"
          "&q%5Bterms%5D%5Braw_type%5D=Law")
NORMAS_ROOT = "https://normas.gba.gob.ar"
BA_DIP = "https://www.hcdiputados-ba.gov.ar/index.php?page=proyectos&search=busquedaPorFecha&pagina={0}"
BA_DIP_HOME = "https://www.hcdiputados-ba.gov.ar/index.php?page=proyectosNormativas"
CABA = "https://parlamentaria.legislatura.gob.ar/webservices/Json.asmx/GetExpedienteAvanzada"
CABA_EXP = "https://parlamentaria.legislatura.gob.ar/pages/expediente.aspx?id={0}"
CBA_SESSIONS = "https://gld.legislaturacba.gob.ar/Publics/Asuntos.aspx"
ER_SEN = "https://www.senadoer.gob.ar/buscador-proyectos/"
ER_SEN_PAGE = "https://www.senadoer.gob.ar/buscador-proyectos/page/{0}/"

RN = ("https://web.legisrn.gov.ar/legislativa/proyectos/index?filter%5BCLASE%5D=P&filter%5BA%C3%91O%5D={0}"
      "&page=1&per-page=100")
RN_ROOT = "https://web.legisrn.gov.ar"
CHU = "https://larus.legislaturadelchubut.gob.ar/api/public/documentos?page=0&size=50&sort=id,desc"
JUJ = "https://www.legislaturajujuy.gov.ar/rest/index.php/labor/legislativa/proyectos/lista"
JUJ_SITE = "https://www.legislaturajujuy.gov.ar/"
CTES = "https://hcdcorrientes.gov.ar/?post_type=expedientes&paged={0}"

# Santa Fe Diputados, SIEL (added 13 October 2026, Chris: "Build it"). Its
# robots.txt names AI agents (ClaudeBot, Claude-User ...) and has no '*'
# group; our collector's own user agent is not named, so it is allowed. The
# reader stops the moment any rule covers our user agent (pull_sf_dip).
SF_ROOT = "https://siel.diputadossantafe.gov.ar/"
SF_LIST = "https://siel.diputadossantafe.gov.ar/index.php?i={0}&ord=DESC"
SF_SEARCH = "https://siel.diputadossantafe.gov.ar/index.php?go=le"
SF_DETAIL = "https://siel.diputadossantafe.gov.ar/index.php?go=d&id={0}"
# SIEL's stage lists read every week (the state code of its search form):
# media sanción and sanción, newest 20 of each.
SF_STAGES = (("11", "1/2 Sanción"), ("12", "Sancionado"))

# Salta (added 13 October 2026). The certificates were never the problem of
# a missing intermediate: senadosalta.gob.ar and www.diputadosalta.gob.ar
# serve complete Let's Encrypt chains that verify; www.senadosalta.gob.ar
# serves a self-signed proxy certificate and the bare diputadosalta.gob.ar
# a wildcard that does not cover it. So these two hostnames, verification on.
SAL_SEN_POSTS = ("https://senadosalta.gob.ar/wp-json/wp/v2/posts?categories={cats}&per_page={n}"
                 "&orderby={order}&order=desc&_fields=id,date,modified,link,title,categories,excerpt")
# WordPress categories of the Senate's project posts (measured 13 October
# 2026 from /wp-json/wp/v2/categories). A post moves from "en trámite" to
# "aprobados" when the chamber approves it (its date stays the entry date).
SAL_SEN_CATS = {52: ("declaracion", "En trámite"), 53: ("resolucion", "En trámite"),
                54: ("ley", "En trámite"), 56: ("ley", "Aprobado"),
                57: ("resolucion", "Aprobado"), 58: ("declaracion", "Aprobado")}
SAL_DIP_APPROVED = "https://www.diputadosalta.gob.ar/web/proyectos_aprobados_por_periodo?periodo={0}&tipo={1}"
SAL_DIP_ROOT = "https://www.diputadosalta.gob.ar"
# Salta Diputados' intake (13 October 2026, Chris: "Accept the watchlists, apply the terms after
# measuring", with the Salta step): the Asuntos Entrados index lists one PDF per
# sitting, newest first (2021 to date); each PDF lists the sitting's new
# projects of law, resolution and declaration with expediente, carátula,
# committees and authors. At most SAL_AE_PDFS new PDFs a run (one sitting a
# week; about 450 KB each), so the step stays inside the AR budget.
SAL_DIP_AE = SAL_DIP_ROOT + "/web/asuntos_entrados"
SAL_AE_PDFS = 2

# Per-host intervals (seconds), never lower than a Crawl-delay robots.txt asks.
DELAYS = {"www.saij.gob.ar": 3.0, "normas.gba.gob.ar": 3.0, "www.hcdiputados-ba.gov.ar": 5.0,
          "parlamentaria.legislatura.gob.ar": 3.0, "gld.legislaturacba.gob.ar": 5.0,
          "www.senadoer.gob.ar": 3.0, "web.legisrn.gov.ar": 3.0,
          "larus.legislaturadelchubut.gob.ar": 3.0, "www.legislaturajujuy.gov.ar": 3.0,
          "hcdcorrientes.gov.ar": 3.0, "siel.diputadossantafe.gov.ar": 5.0,
          "senadosalta.gob.ar": 3.0, "www.diputadosalta.gob.ar": 3.0}


# --- text helpers --------------------------------------------------------------------

def fold(text):
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().upper()


def flat(fragment):
    text = re.sub(r"<br\s*/?>", " ", fragment or "", flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = htmllib.unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def dmy(text):
    """'9/10/2026 17:27:00', '30.09.2026', '29/09/2026' (day first) -> ISO."""
    m = re.search(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", text or "")
    if not m:
        return None
    try:
        return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    except ValueError:
        return None


def clip(text, n=SUMMARY_CHARS):
    text = (text or "").strip()
    return text if len(text) <= n else text[:n].rstrip()


KINDS = (
    ("ley", re.compile(r"\bLEY\b")),
    ("resolucion", re.compile(r"\bRESOLUCION\b")),
    ("declaracion", re.compile(r"\bDECLARACION\b")),
    ("comunicacion", re.compile(r"\bCOMUNICACION\b")),
    ("solicitud de informes", re.compile(r"\bSOLICITUD DE INFORMES\b|\bPEDIDO DE INFORMES\b")),
    ("decreto", re.compile(r"\bDECRETO\b")),
)


def kind_of(text):
    t = fold(text)
    for kind, pat in KINDS:
        if pat.search(t):
            return kind
    return None


# --- SAIJ ----------------------------------------------------------------------------

def parse_saij(reply):
    """Law rows from one SAIJ search reply (JSON text). Only
    'legislacion' documents with a known province and a number; SAIJ's
    'novedad' notes duplicate them and are skipped."""
    data = json.loads(reply)
    out = []
    for doc in (data.get("searchResults") or {}).get("documentResultList") or []:
        try:
            a = json.loads(doc.get("documentAbstract") or "{}").get("document") or {}
        except ValueError:
            continue
        meta, c = a.get("metadata") or {}, a.get("content") or {}
        if meta.get("document-content-type") != "legislacion":
            continue
        prov = store.SAIJ_PROVINCES.get(fold(c.get("provincia")))
        number = c.get("numero-norma")
        if not prov or not isinstance(number, int):
            continue
        pub = ((c.get("publicacion-codificada") or {}).get("publicacion-decodificada") or {})
        published = None
        if isinstance(pub, dict) and pub.get("fecha"):
            m = re.match(r"(\d{4}) (\d\d) (\d\d)", pub["fecha"])
            published = "{0}-{1}-{2}".format(*m.groups()) if m else None
        descs = []
        raw = (c.get("descriptores") or {}).get("descriptor") or []
        for d in (raw if isinstance(raw, list) else [raw]):
            # One descriptor comes as an object, several as a list (SAIJ's XML
            # turned JSON); a bare string is the term itself.
            term = d if isinstance(d, str) else ((d or {}).get("elegido") or {}).get("termino")
            if term and term not in descs:
                descs.append(term)
        friendly = (meta.get("friendly-url") or {}).get("description")
        out.append({
            "law_key": "{0}/ley/{1}".format(prov, number), "province": prov, "number": number,
            "sanctioned": (c.get("fecha") or "")[:10] or None, "published": published,
            "title": flat(c.get("titulo-norma")) or flat(c.get("sumario")),
            "summary": flat(c.get("sumario")), "descriptors": descs,
            "url": SAIJ_DOC.format(friendly, meta.get("uuid")) if friendly and meta.get("uuid") else None,
            "source": "saij"})
    return out


# --- normas.gba.gob.ar --------------------------------------------------------------------

NORMAS_ITEM = re.compile(r'href="(/ar-b/ley/(\d{4})/(\d+)/\d+)"')


def parse_normas(page):
    """Law rows from one normas.gba.gob.ar results page: number, the
    summary ('Resumen') and the publication date, by the link of each."""
    out = []
    links = list(NORMAS_ITEM.finditer(page or ""))
    for i, m in enumerate(links):
        end = links[i + 1].start() if i + 1 < len(links) else len(page)
        chunk = flat(page[m.start():end])
        summ = re.search(r"Resumen\s+(.*?)\s+Fecha de publicaci", chunk)
        pub = re.search(r"Fecha de publicaci[oó]n:\s*([0-9/]+)", chunk)
        number = int(m.group(3))
        out.append({"law_key": "ba/ley/{0}".format(number), "province": "ba", "number": number,
                    "sanctioned": None, "published": dmy(pub.group(1)) if pub else None,
                    "title": summ.group(1).strip() if summ else "", "summary": summ.group(1).strip() if summ else "",
                    "descriptors": [], "url": NORMAS_ROOT + m.group(1), "source": "normas-gba"})
    # The same law can be linked twice on a page (title and button).
    seen, uniq = set(), []
    for r in out:
        if r["law_key"] not in seen and r["title"]:
            seen.add(r["law_key"])
            uniq.append(r)
    return uniq


# --- Buenos Aires province, Diputados ---------------------------------------------------

BA_ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
BA_NUM = re.compile(r"cargarProyectoFecha\('([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)'\)")


def ba_dip_fields(since, until):
    return {"desde": since.isoformat(), "hasta": until.isoformat(), "pageSize": "200",
            "periodo": "", "origen": "", "numero": "", "alcance": ""}


def ba_dip_total(page):
    m = re.search(r"de un total de (\d+)", page or "")
    return int(m.group(1)) if m else None


def parse_ba_dip(page):
    out = []
    for row in BA_ROW.findall(page or ""):
        m = BA_NUM.search(row)
        if not m:
            continue
        periodo, origen, numero, alcance = (x.strip() for x in m.groups())
        row = re.sub(r"<!--.*?-->", "", row, flags=re.S)
        text = flat(row)
        kind = re.search(r"PROYECTO DE ([A-ZÁÉÍÓÚ ]+?)\s{0,}(?:Texto Original|Fecha|$)", text)
        paras = [flat(p) for p in re.findall(r"<p(?:\s[^>]*)?>(.*?)</p>", row, re.S)]
        pdf = re.search(r'href="(https://intranet\.hcdiputados-ba\.gov\.ar/proyectos/[^"]+\.pdf)"', row)
        title = next((p for p in paras if p and not re.match(r"(Fecha|Autor)", p)), "")
        title = re.sub(r"\.-$", ".", title)
        entered = re.search(r"Fecha Estado Parlamentario:\s*([0-9/]+)", text)
        author = re.search(r"Autor/es:\s*(.*?)(?:\s*Coautor|\s*$)", text)
        exp = "{0}-{1}/{2}".format(origen, numero, periodo)
        if alcance and alcance != "0":
            exp += "-{0}".format(alcance)
        out.append({"bill_key": "ba-dip:" + exp, "legislature": "ba-dip", "province": "ba",
                    "expediente": exp, "kind": kind_of("PROYECTO DE " + kind.group(1)) if kind else kind_of(text),
                    "title": title, "author": author.group(1).strip() if author else None,
                    "status": None, "committee": None,
                    "presented": dmy(entered.group(1)) if entered else None, "sanctioned": None,
                    "url": pdf.group(1) if pdf else BA_DIP_HOME})
    return out


# --- CABA ------------------------------------------------------------------------------------

def caba_fields(since, until):
    f = lambda d: d.strftime("%d/%m/%Y")
    return {"IdProyectoTipo": "", "IdAutoresInternos": "", "IdUbicacion": "", "IdEstado": "",
            "Sumario": "", "SumarioExacto": "0", "FechaDesde": f(since), "FechaHasta": f(until),
            "AnioParlamentario": "", "Limite": ""}


def _tag(block, name):
    m = re.search(r"<{0}>(.*?)</{0}>".format(name), block, re.S)
    return htmllib.unescape(m.group(1)).strip() if m else ""


def parse_caba(xml):
    out = []
    for block in re.findall(r"<expedienteAvanzado>(.*?)</expedienteAvanzado>", xml or "", re.S):
        exp = _tag(block, "nro_de_expediente")
        if not exp:
            continue
        author = _tag(block, "autor_des")
        co = _tag(block, "coautores_des")
        status = " · ".join(x for x in (_tag(block, "descripcion"), _tag(block, "ubicacion_des")) if x)
        out.append({"bill_key": "caba:" + exp, "legislature": "caba", "province": "caba",
                    "expediente": exp, "kind": kind_of(_tag(block, "tipo_proyecto_des")),
                    "title": re.sub(r"\s*\.-\s*$", ".", flat(_tag(block, "sumario"))),
                    "author": author + ("; " + co if co else "") if author else (co or None),
                    "status": status or None, "committee": _tag(block, "ubicacion_des") or None,
                    "presented": dmy(_tag(block, "fch_inicio")),
                    "sanctioned": 1 if _tag(block, "TieneSancion") == "1" else 0,
                    "url": CABA_EXP.format(_tag(block, "id_expediente"))})
    return out


# --- Córdoba ---------------------------------------------------------------------------------

CBA_SESSION = re.compile(r"Asuntos\.aspx\?id=([A-Za-z0-9_=-]+)")


def parse_cba_sessions(page):
    """[(session id, ISO date, label)] from the Asuntos Entrados index, as
    the table lists them ('... Unicameral 148 17 Ordinaria 07/10/2026 <link>')."""
    out, seen = [], set()
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page or "", re.S):
        m = CBA_SESSION.search(row)
        if not m or m.group(1) in seen:
            continue
        text = flat(row)
        when = dmy(text)
        label = re.search(r"Unicameral\s+(\d+)\s+(\d+)\s+(\w+)", text)
        seen.add(m.group(1))
        out.append((m.group(1), when, "{0} {1}".format(label.group(2), label.group(3)) if label else ""))
    return out


def parse_cba_session(page, session_date, url):
    out = []
    for m in re.finditer(r'HL_Expediente_\d+"\s+href="[^"]*"[^>]*>(\d+/[A-Z]/\d{2})</a>', page or ""):
        rest = page[m.end():m.end() + 6000]
        ext = re.search(r'L_Extracto_\d+">(.*?)</span>', rest, re.S)
        if not ext:
            continue
        nxt = re.search(r"HL_Expediente_\d+", rest)
        com = re.search(r'L_Comisiones_\d+">(.*?)</span>', rest, re.S)
        if com and nxt and com.start() > nxt.start():
            com = None
        exp = m.group(1)
        letter = exp.split("/")[1]
        title = flat(ext.group(1))
        author = re.search(r"iniciado por (?:el |la |los |las )?(?:Legislador(?:a|es|as)? )?(.*?)(?:,|$)", title)
        out.append({"bill_key": "cba:" + exp, "legislature": "cba", "province": "cba",
                    "expediente": exp,
                    "kind": {"L": "ley", "R": "resolucion", "D": "declaracion", "N": "nota",
                             "P": "pliego", "E": "ley"}.get(letter) or kind_of(title),
                    "title": title, "author": author.group(1).strip() if author else None,
                    "status": "Asunto entrado " + session_date if session_date else None,
                    "committee": re.sub(r"^Comisi[oó]n(?:es)?:\s*", "", flat(com.group(1))) if com else None,
                    "presented": session_date, "sanctioned": None, "url": url})
    seen, uniq = set(), []
    for r in out:
        if r["bill_key"] not in seen:
            seen.add(r["bill_key"])
            uniq.append(r)
    return uniq


# --- Entre Ríos, Senate ------------------------------------------------------------------------

ER_ARTICLE = re.compile(r'<article id="post-\d+" class="[^"]*type-proyectos[^"]*">(.*?)</article>', re.S)


def parse_er_sen(page):
    out = []
    for art in ER_ARTICLE.findall(page or ""):
        head = re.search(r'<a href="([^"]+)">\s*<h2>(.*?)</h2>', art, re.S)
        if not head:
            continue
        parts = [p.strip() for p in flat(head.group(2)).split("|")]
        if len(parts) < 3:
            continue
        nums = re.findall(r"\d+", parts[1])
        if not nums:
            continue
        cols = re.findall(r'<div class="col-12 col-md-[0-9][^"]*">(.*?)</div>', art, re.S)
        title = flat(cols[1]) if len(cols) > 1 else ""
        author = re.search(r"<span>Autor:\s*</span>(.*?)</p>", art, re.S)
        co = re.search(r"Coautor:?\s*</span>(.*?)</p>", art, re.S)
        com = re.search(r"<span>Comisi[oó]n:</span><br>(.*?)</p>", art, re.S)
        stages = re.findall(r"<span>(Media sanci[oó]n|Sancionado|Aprobado|Rechazado):</span><br>(.*?)</p>", art, re.S)
        status = "; ".join("{0} {1}".format(k, flat(v).strip(" |")) for k, v in stages) or None
        out.append({"bill_key": "er-sen:" + nums[-1], "legislature": "er-sen", "province": "er",
                    "expediente": parts[1], "kind": kind_of(parts[2]), "title": title,
                    "author": flat(author.group(1)) if author else None,
                    "status": status, "committee": flat(com.group(1)) if com else None,
                    "presented": dmy(parts[0]),
                    "sanctioned": 1 if any(k.startswith("Sancion") for k, _ in stages) else 0,
                    "url": head.group(1)})
    return out


# --- Río Negro, Chubut, Jujuy, Corrientes (added 13 October 2026) --------------------------

RN_ITEM = re.compile(r'<a href="(/legislativa/proyectos/ver\?c=P&amp;n=(\d+)&amp;a=(\d{4}))">'
                     r'Proyecto ([^<]*?) N\S* \d+/\d{4}</a>(.*?)</div>', re.S)


def parse_rn(page):
    """Río Negro's project list (one page of 100, newest first). No date in
    the list: a project is new by the day first listed."""
    out = []
    for m in RN_ITEM.finditer(page or ""):
        body = m.group(5)
        author = re.search(r"<b>Autor/es:</b>(.*?)</p>", body, re.S)
        title = flat(re.split(r"<p", body, 1)[0])
        exp = "{0}/{1}".format(m.group(2), m.group(3))
        out.append({"bill_key": "rn:" + exp, "legislature": "rn", "province": "rn", "expediente": exp,
                    "kind": kind_of(m.group(4)), "title": title,
                    "author": flat(author.group(1)) if author else None, "status": None,
                    "committee": None, "presented": None, "sanctioned": None,
                    "url": RN_ROOT + htmllib.unescape(m.group(1))})
    return out


def parse_chu(reply):
    """Chubut's public document API (LARUS). Staff logins in the reply
    (usuarioAlta, usuario) are never read or stored."""
    out = []
    for d in json.loads(reply or "[]"):
        ident = (d.get("identificador") or "").strip()
        if not ident:
            continue
        movs = [m for m in d.get("movimientos") or [] if m.get("actual")]
        stage = None
        if movs:
            m = movs[-1]
            stage = " · ".join(x for x in (((m.get("instancia") or {}).get("nombre")),
                                            flat(m.get("observaciones") or "").rstrip(" .-")) if x)
        authors = "; ".join(a.get("nombre") for a in d.get("autores") or [] if a.get("nombre"))
        out.append({"bill_key": "chu:" + ident, "legislature": "chu", "province": "chu",
                    "expediente": ident, "kind": kind_of((d.get("tipo") or {}).get("descripcion")),
                    "title": flat(d.get("extracto")), "author": authors or
                    ((d.get("origen") or {}).get("descripcion")), "status": stage,
                    "committee": None, "presented": (d.get("fechaAlta") or "")[:10] or None,
                    "sanctioned": None, "url": None})
    return out


def parse_juj(reply):
    """Jujuy's project list (REST, 20 newest). The list gives number, text
    and date; its 'forma' code is not labelled anywhere we read, so the
    kind is left unset."""
    data = json.loads(reply or "{}")
    out = []
    for r in (data.get("rows") if isinstance(data, dict) else data) or []:
        exp = (r.get("expediente") or "").strip()
        if not exp:
            continue
        out.append({"bill_key": "juj:" + exp, "legislature": "juj", "province": "juj", "expediente": exp,
                    "kind": None, "title": flat(r.get("proyecto")), "author": None, "status": None,
                    "committee": None, "presented": dmy(r.get("fecha")), "sanctioned": None,
                    "url": JUJ_SITE})
    return out


CTES_ARTICLE = re.compile(r'<article id="post-\d+" class="[^"]*type-expedientes[^"]*">(.*?)</article>', re.S)


def parse_ctes(page):
    """Corrientes Diputados' expediente list (five a page, newest first)."""
    out = []
    for art in CTES_ARTICLE.findall(page or ""):
        art = re.sub(r"<!--.*?-->", "", art, flags=re.S)
        cols = re.findall(r'<div class="col-md-\d col-table-resume"[^>]*>(.*?)</div>', art, re.S)
        if len(cols) < 4:
            continue
        num = flat(cols[0])
        if not re.match(r"^\d+$", num):
            continue
        fields = {flat(k): flat(v) for k, v in re.findall(
            r"<b>([^<:]{3,40}):</b>\s*</td>\s*<td[^>]*>(.*?)</td>", art, re.S)}
        approved = fields.get("Aprobación")
        out.append({"bill_key": "ctes-dip:" + num, "legislature": "ctes-dip", "province": "ctes",
                    "expediente": num, "kind": kind_of(flat(cols[1])), "title": flat(cols[3]),
                    "author": flat(cols[2]).rstrip(".") or None,
                    "status": ("Aprobado " + approved) if approved else None,
                    "committee": fields.get("Comisión", "").rstrip(".") or None,
                    "presented": dmy(fields.get("Ingreso H.C.D.")),
                    "sanctioned": 1 if approved else 0,
                    "url": "https://hcdcorrientes.gov.ar/expedientes/{0}/".format(num)})
    return out


# --- classification and the store -----------------------------------------------------------

# --- Santa Fe Diputados (SIEL) and Salta's two chambers (added 13 October 2026) ------

SF_ROW = re.compile(r'<tr class="odd gradeX">(.*?)</tr>', re.S)
SF_BLOC = re.compile(r"\*\s*([^*]{3,160}?)\s*\*\.?\s*$")
SF_DONE = ("SANCIONADO", "PROMULGADO", "APROBADO")


def sf_search_fields(state):
    """SIEL's read-only search form, by state only (the form's own fields)."""
    fields = {k: "" for k in ("numero", "estado", "comisionmenu", "tipoexpediente", "numerodeley",
                              "fechainicio", "fechafin", "idAutorDiputado", "idAutorSenador",
                              "idAutorDiputadoPrevio", "firmantes", "endescripcion")}
    fields.update({"estado": state, "Buscar": "Buscar"})
    return fields


def sf_columns(page):
    """SIEL's column order from the table head: the expediente list hides
    'Pasada' in an HTML comment, the search results show it."""
    head = re.search(r"<thead>(.*?)</thead>", re.sub(r"<!--.*?-->", "", page or "", flags=re.S), re.S)
    names = [fold(flat(h)) for h in re.findall(r"<th[^>]*>(.*?)</th>", head.group(1), re.S)] if head else []
    want = {"NUMERO": "number", "TIPO": "kind", "AUTOR": "author", "FECHA DE INGRESO": "entered",
            "ESTADO": "state", "DESCRIPCION": "desc"}
    cols = {want[n]: i for i, n in enumerate(names) if n in want}
    if len(cols) < len(want):
        cols = {"number": 0, "kind": 1, "author": 2, "entered": 3, "state": 4, "desc": 5}
    return cols


def parse_sf_dip(page, stage=False):
    """SIEL's expediente table (20 a page, newest number first): number,
    type, author, entry date, state, description (the bloc in asterisks at
    its end goes to the author), and the detail page's id. A sanctioned
    expediente's number cell also prints its law number."""
    out = []
    cols = sf_columns(page)
    for block in SF_ROW.findall(page or ""):
        block = re.sub(r"<!--.*?-->", "", block, flags=re.S)
        cells = [flat(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", block, re.S)]
        if len(cells) <= max(cols.values()):
            continue
        number_cell, kind, author, entered, state, desc = (
            cells[cols[k]] for k in ("number", "kind", "author", "entered", "state", "desc"))
        m = re.match(r"(\d+)\b(.*)", number_cell)
        if not m:
            continue
        number, law = m.group(1), re.search(r"LEY\s*Nro:?\s*(\d+)", m.group(2), re.I)
        bloc = SF_BLOC.search(desc)
        title = desc[:bloc.start()].strip(" .-") if bloc else desc
        if bloc:
            author = "{0} ({1})".format(author, bloc.group(1).strip()) if author else bloc.group(1).strip()
        if law and state:
            state = "{0} (Ley {1})".format(state, law.group(1))
        detail = re.search(r"index\.php\?go=d&(?:amp;)?id=(\d+)", block)
        out.append({"bill_key": "sf-dip:" + number, "legislature": "sf-dip", "province": "sf",
                    "expediente": number, "kind": kind_of(kind) or (fold(kind).lower() or None),
                    "title": title, "author": author or None, "status": state or None,
                    "committee": None, "presented": dmy(entered),
                    "sanctioned": 1 if fold(state).startswith(SF_DONE) else 0,
                    "url": SF_DETAIL.format(detail.group(1)) if detail else SF_ROOT,
                    "stage": stage})
    return out


SAL_EXPTE = re.compile(r"Expte\.?\s*N\s*[°ºo]?\s*\.?\s*(\d+)\s*-\s*([\d.]+)\s*/\s*(\d{2,4})\s*[–—-]+\s*"
                       r"(\d{1,2}/\d{1,2}/\d{2,4})?\s*[–—-]*\s*(.*)$", re.S)
SAL_AUTHOR = re.compile(r"^De(?:l| la| las| los)?\s+(?:se[ñn]or(?:a|es|as)?\s+)?Senador(?:a|es|as)?\s+(.*)$",
                        re.I | re.S)
SAL_AUTHOR_END = re.compile(r"(?i:,?\s+(?:que|declarar|declara|viendo|de conformidad|solicita\w*|ver[ií]a\w*|"
                            r"mediante|por el cual|para|sobre|a fin|instituir|crear|modificar)\b)"
                            r"|,\s+(?=[a-záéíóúñ])")
SAL_AUTHOR_JOIN = re.compile(r",?\s*\by\s+(?:l[oa]s?\s+|el\s+)?(?:se[ñn]or(?:a|es|as)?\s+)?(?:Senador(?:a|es|as)?\s+)?",
                             re.I)


SAL_OFFICE = re.compile(r"^Autor:\s*(C[áa]mara de Diputados|Poder Ejecutivo|Ministerio P[úu]blico|"
                        r"Corte de Justicia|Auditor[íi]a General de la Provincia|Tribunal de Cuentas)", re.I)


def sal_authors(excerpt):
    """'De los Señores Senadores A, B y C que ...' -> 'A, B, C'."""
    office = SAL_OFFICE.search(excerpt or "")
    if office:
        return office.group(1)
    m = SAL_AUTHOR.search(excerpt or "")
    if not m:
        return None
    rest = m.group(1)
    end = SAL_AUTHOR_END.search(rest)
    names = rest[:end.start()] if end else rest
    names = SAL_AUTHOR_JOIN.sub(", ", names).strip(" ,.")
    return names if 0 < len(names) <= 300 else None


def _year4(text):
    return text if len(text) == 4 else "20" + text


def short_dmy(text):
    """'08/10/26' or '08/10/2026' -> ISO."""
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})$", (text or "").strip())
    return dmy("{0}/{1}/{2}".format(m.group(1), m.group(2), _year4(m.group(3)))) if m else None


def parse_sal_sen(reply, stage=False):
    """Salta Senate's project posts (WordPress REST, JSON): the title is
    'Expte. N° 90-34.699/2026 – 08/10/26 – subject'; the category says the
    kind and whether it is still en trámite or approved; the excerpt opens
    with the authors."""
    out = []
    for post in json.loads(reply or "[]"):
        title = flat((post.get("title") or {}).get("rendered", ""))
        m = SAL_EXPTE.search(title)
        cats = [SAL_SEN_CATS[c] for c in post.get("categories") or [] if c in SAL_SEN_CATS]
        if not m or not cats:
            continue
        kind, state = cats[0]
        number = "{0}-{1}/{2}".format(m.group(1), m.group(2).replace(".", ""), _year4(m.group(3)))
        excerpt = flat((post.get("excerpt") or {}).get("rendered", ""))
        subject = m.group(5).strip(" –-")
        out.append({"bill_key": "sal-sen:" + number, "legislature": "sal-sen", "province": "sal",
                    "expediente": number, "kind": kind,
                    "title": "{0}: {1}".format(subject, excerpt) if excerpt and subject else (subject or excerpt),
                    "author": sal_authors(excerpt), "status": state,
                    "committee": None,
                    "presented": short_dmy(m.group(4)) or (post.get("date") or "")[:10] or None,
                    "sanctioned": 1 if state == "Aprobado" and kind != "ley" else 0,
                    "url": post.get("link"), "stage": stage})
    return out


SAL_DIP_ROW = re.compile(r'<a href="(/web/expediente/\d+)">([^<]+)</a></td>\s*<td[^>]*>([^<]*)</td>\s*'
                         r'<td>(.*?)</td>', re.S)


def parse_sal_dip(page, kind):
    """Salta Diputados' approved projects of one period and type (one page):
    number, entry date, title. Its pending lists answered '0 expedientes' on
    13 October 2026, so this is the chamber's stage list, not its intake."""
    out = []
    for href, number, entered, title in SAL_DIP_ROW.findall(page or ""):
        number = flat(number)
        out.append({"bill_key": "sal-dip:" + number, "legislature": "sal-dip", "province": "sal",
                    "expediente": number, "kind": kind, "title": flat(title), "author": None,
                    "status": "Aprobado", "committee": None, "presented": dmy(entered),
                    "sanctioned": 0 if kind == "ley" else 1, "url": SAL_DIP_ROOT + href,
                    "stage": True})
    return out


# --- Salta Diputados' Asuntos Entrados (PDF) ----------------------------------------

SAL_AE_ROW = re.compile(r'<a href="(/documentos_legislativos/(\d+)/download_file)">\s*Asuntos Entrados\s*</a>'
                        r'\s*</td>\s*<td[^>]*>\s*(\d{1,2}/\d{1,2}/\d{4})\s*</td>', re.S | re.I)
SAL_AE_KIND = re.compile(r"^PROYECTOS DE (LEY|RESOLUCI[OÓ]N|DECLARACI[OÓ]N)$")
SAL_AE_EXP = re.compile(r"Expediente:\s*(\d+)\s*-\s*([\d.]+)\s*/\s*(\d{2,4})")
SAL_AE_FIELD = re.compile(r"^(Carátula|A las? Comisi[oó]n(?:es)?|Autor(?:a|es|as)?)\s*:\s*(.*)$")
SAL_AE_ROMAN = re.compile(r"^[IVXL]+$")
SAL_AE_MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
                 "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11,
                 "diciembre": 12}


def parse_sal_ae_index(page):
    """[(document id, ISO date, PDF url)] from the Asuntos Entrados index,
    newest first as the page lists them."""
    out = []
    for href, doc_id, when in SAL_AE_ROW.findall(page or ""):
        out.append((doc_id, dmy(when), SAL_DIP_ROOT + href))
    return out


def sal_pdf_text(blob):
    """The PDF's text in pypdf's layout mode (the plain mode splits words at
    kerning gaps, "E rradicación"); pypdf is imported only here."""
    try:
        import io
        import pypdf
    except ImportError:
        raise ValueError("pypdf is not installed: Salta's Asuntos Entrados (PDF) are not read")
    try:
        reader = pypdf.PdfReader(io.BytesIO(blob))
        pages = list(reader.pages)
    except Exception as exc:                 # pypdf raises a zoo of types
        raise ValueError("unreadable PDF: {0}".format(str(exc)[:100]))
    out = []
    for page in pages:
        if "/Contents" not in page:          # a blank page (layout mode trips on it)
            continue
        try:
            out.append(page.extract_text(extraction_mode="layout") or "")
        except Exception:                    # one odd page: the plain mode, else nothing
            try:
                out.append(page.extract_text() or "")
            except Exception:
                continue
    return "\n".join(out)


def _sal_ae_heading(line):
    """A section heading of the document: a roman numeral, or a line in
    capitals (two words or more) such as 'DICTAMEN DE COMISIÓN' or
    'INCORPORADOS EN ASUNTOS ENTRADOS DURANTE LA SESIÓN (25-08-2026)'."""
    if SAL_AE_ROMAN.match(line):
        return True
    words = re.findall(r"[^\W\d_]+", line)
    return len(words) >= 2 and not re.search(r"[a-záéíóúñ]", line) and "EXPEDIENTE" not in line


def _sal_ae_kind(text):
    m = re.search(r"Proyectos? de (Ley|Resoluci[oó]n|Declaraci[oó]n)", text or "", re.I)
    if not m:
        return None
    word = fold(m.group(1))
    return "ley" if word == "LEY" else ("resolucion" if word.startswith("RESOLU") else "declaracion")


def sal_ae_session_date(text):
    m = re.search(r"(\d{1,2}) de ([a-z]+) de (\d{4})", fold(text[:2000]).lower())
    if not m or m.group(2) not in SAL_AE_MONTHS:
        return None
    try:
        return datetime.date(int(m.group(3)), SAL_AE_MONTHS[m.group(2)], int(m.group(1))).isoformat()
    except ValueError:
        return None


def parse_sal_ae(text, when=None, url=None):
    """Every project of law, resolution and declaration in one sitting's
    Asuntos Entrados (pypdf's text): the PROYECTOS DE ... sections, the
    projects added during the sitting and the documents section (each names
    its kind), and the Senate's bills in revision among the communications.
    Notes, decrees and committee reports ('Exptes.') are skipped."""
    when = when or sal_ae_session_date(text or "")
    out, kind, cur, field = [], None, None, None

    def close():
        if cur and cur.get("title"):
            note = " ".join(cur.pop("_note", []))
            status = "Entrado"
            if re.search(r"archivo", note, re.I):
                status = "Entrado y archivado"
            authors = re.sub(r"\bDip\.\s*", "", " ".join(cur["_author"])).strip(" .-–")
            out.append({"bill_key": "sal-dip:" + cur["expediente"], "legislature": "sal-dip",
                        "province": "sal", "expediente": cur["expediente"], "kind": cur["kind"],
                        "title": re.sub(r"\s+", " ", " ".join(cur["title"])).strip(),
                        "author": re.sub(r"\s*[-–]\s*", "; ", re.sub(r"\s+", " ", authors)) or None,
                        "status": status,
                        "committee": re.sub(r"\s+", " ", " ".join(cur["_committee"])).strip() or None,
                        "presented": when, "sanctioned": 0, "url": url, "stage": False})

    for raw in (text or "").splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line or re.fullmatch(r"\d{1,3}", line):
            continue
        m = SAL_AE_KIND.match(line)
        if m:
            close()
            cur, field = None, None
            kind = {"LEY": "ley"}.get(m.group(1), "resolucion" if m.group(1).startswith("RESOLU")
                                      else "declaracion")
            continue
        if _sal_ae_heading(line):
            close()
            # projects added during the sitting may name no kind: 'proyecto'
            cur, field, kind = None, None, ("proyecto" if line.startswith("INCORPORADOS") else None)
            continue
        if re.fullmatch(r"Proyectos? de (Ley|Resoluci[oó]n|Declaraci[oó]n)", line, re.I):
            close()
            cur, field, kind = None, None, _sal_ae_kind(line)
            continue
        m = SAL_AE_EXP.search(line)
        if m and line.lstrip("0123456789. ").startswith("Expediente"):
            close()
            cur, field = None, None
            this = _sal_ae_kind(line[m.end():]) or kind
            if this is None:
                continue
            year = m.group(3)[-2:]
            cur = {"expediente": "{0}-{1}/{2}".format(m.group(1), m.group(2).replace(".", ""), year),
                   "kind": this, "title": [], "_committee": [], "_author": [], "_note": []}
            continue
        if cur is None:
            continue
        if line.startswith("---"):
            field = "_note"
            cur["_note"].append(line.strip("- "))
            continue
        m = SAL_AE_FIELD.match(line)
        if m:
            label = m.group(1).lower()
            field = "title" if label.startswith("car") else ("_committee" if label.startswith("a la")
                                                            else "_author")
            cur[field].append(m.group(2))
            continue
        if field:
            cur[field].append(line)
    close()
    return out


def load_taxonomy(path=None):
    from src import filter as filt
    path = path or os.path.join(ROOT, "config", "taxonomy-es.yaml")
    if not os.path.exists(path):
        return None
    return filt.load_taxonomy(path, country="ar")


def load_watch(path=WATCHLIST):
    """{key: areas} from the `provincial` section of watchlist-ar (law keys
    'ba/ley/15625' or bill keys 'caba:3199-D-2026')."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    sect = raw.get("provincial") or {}
    return {str(k): list((v or {}).get("areas") or []) for k, v in sect.items()}


def classify(tax, watch, key, title, summary=""):
    areas, terms, tier = [], [], None
    if tax is not None:
        from src import filter as filt
        res = filt.filter_item(tax, filt.Watchlist(entities=[], bill_titles=[], act_shorts=[]),
                               title or "", summary or "")
        areas, terms, tier = sorted(set(res.issue_areas or [])), list(res.matched_terms or []), res.tier
    if key in watch:
        areas = sorted(set(areas) | set(watch[key]))
        terms = terms + ["watch:" + key]
        tier = 1
    return areas, terms, tier


def _row(conn, table, keycol, key):
    cur = conn.execute("SELECT * FROM {0} WHERE {1}=?".format(table, keycol), (key,))
    got = cur.fetchone()
    return dict(zip([d[0] for d in cur.description], got)) if got else None


def upsert_law(conn, row, tax, watch, today):
    """Insert or merge one law. SAIJ's title, sanction date and URL win;
    another source fills a publication date SAIJ lacks and adds itself to
    `source`. Returns (new, areas)."""
    old = _row(conn, "arp_laws", "law_key", row["law_key"])
    if old:
        saij = row["source"] == "saij"
        srcs = set((old["source"] or "").split("+")) | {row["source"]}
        merged = {
            "number": row["number"],
            "sanctioned": row["sanctioned"] or old["sanctioned"],
            "published": old["published"] or row["published"] if not saij else (row["published"] or old["published"]),
            "title": row["title"] if saij else (old["title"] or row["title"]),
            "summary": max([old["summary"] or "", row["summary"] or ""], key=len),
            "descriptors": store.dumps(row["descriptors"]) if row["descriptors"] else old["descriptors"],
            "url": row["url"] if (saij or not old["url"]) else old["url"],
            "source": "+".join(s for s in ("saij", "normas-gba") if s in srcs),
        }
    else:
        merged = {"number": row["number"], "sanctioned": row["sanctioned"],
                  "published": row["published"], "title": row["title"], "summary": row["summary"],
                  "descriptors": store.dumps(row["descriptors"]), "url": row["url"],
                  "source": row["source"]}
    summary = merged["summary"] if merged["summary"] != merged["title"] else ""
    areas, terms, tier = classify(tax, watch, row["law_key"], merged["title"], summary)
    conn.execute(
        "INSERT INTO arp_laws (law_key, province, number, sanctioned, published, title, summary, "
        "descriptors, url, source, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(law_key) DO UPDATE SET "
        "number=excluded.number, sanctioned=excluded.sanctioned, published=excluded.published, "
        "title=excluded.title, summary=excluded.summary, descriptors=excluded.descriptors, "
        "url=excluded.url, source=excluded.source, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (row["law_key"], row["province"], merged["number"], merged["sanctioned"],
         merged["published"], clip(merged["title"], 600), clip(merged["summary"]) or None,
         merged["descriptors"], merged["url"], merged["source"], store.dumps(areas),
         json.dumps(terms, ensure_ascii=False), tier, today, today))
    return old is None, areas


def upsert_bill(conn, row, tax, watch, today, seed=False):
    """Insert or update one expediente: the latest read's status, committee
    and sanction flag win; the title, author and dates fill what was empty.
    Returns (new, areas)."""
    old = _row(conn, "arp_bills", "bill_key", row["bill_key"])
    if old:
        merged = {k: (row[k] if row.get(k) not in (None, "") else old[k])
                  for k in ("kind", "title", "author", "status", "committee", "presented",
                            "sanctioned", "url")}
        if old["presented"] and row["legislature"] == "cba":
            merged["presented"] = old["presented"]    # the session it entered, not a later one
        seed_flag = old["seed"]
        if row.get("status") and old["status"] and row["status"] != old["status"]:
            moved, prev = today, old["status"]
        else:
            moved, prev = old["moved"], old["prev_status"]
    else:
        merged = {k: row.get(k) for k in ("kind", "title", "author", "status", "committee",
                                          "presented", "sanctioned", "url")}
        seed_flag = 1 if seed else 0
        moved = prev = None
        if row.get("stage") and not seed:
            # First seen in a stage list (a chamber's approved or media-sanción
            # list), after the source's first read: the stage is the news.
            moved = today
    areas, terms, tier = classify(tax, watch, row["bill_key"], merged["title"])
    conn.execute(
        "INSERT INTO arp_bills (bill_key, legislature, province, expediente, kind, title, author, "
        "status, committee, presented, sanctioned, url, areas, matched_terms, tier, first_seen, "
        "last_seen, seed, moved, prev_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(bill_key) DO UPDATE SET kind=excluded.kind, title=excluded.title, "
        "author=excluded.author, status=excluded.status, committee=excluded.committee, "
        "presented=excluded.presented, sanctioned=excluded.sanctioned, url=excluded.url, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen, moved=excluded.moved, prev_status=excluded.prev_status",
        (row["bill_key"], row["legislature"], row["province"], row["expediente"], merged["kind"],
         clip(merged["title"], 1200), clip(merged["author"] or "", 300) or None, merged["status"],
         merged["committee"], merged["presented"], merged["sanctioned"], merged["url"],
         store.dumps(areas), json.dumps(terms, ensure_ascii=False), tier, today, today, seed_flag,
         moved, prev))
    return old is None, areas


def reclassify(conn, tax, watch):
    n = 0
    for key, title, summary in conn.execute("SELECT law_key, title, summary FROM arp_laws").fetchall():
        areas, terms, tier = classify(tax, watch, key, title, summary if summary != title else "")
        conn.execute("UPDATE arp_laws SET areas=?, matched_terms=?, tier=? WHERE law_key=?",
                     (store.dumps(areas), json.dumps(terms, ensure_ascii=False), tier, key))
        n += 1
    for key, title in conn.execute("SELECT bill_key, title FROM arp_bills").fetchall():
        areas, terms, tier = classify(tax, watch, key, title)
        conn.execute("UPDATE arp_bills SET areas=?, matched_terms=?, tier=? WHERE bill_key=?",
                     (store.dumps(areas), json.dumps(terms, ensure_ascii=False), tier, key))
        n += 1
    conn.commit()
    return n


def visible(areas):
    return [a for a in areas if a != 11]


def first_read(conn, source):
    return conn.execute("SELECT 1 FROM arp_reads WHERE source=? AND status='ok'",
                        (source,)).fetchone() is None


def record_read(conn, source, today, items, status, cursor=None):
    conn.execute(
        "INSERT INTO arp_reads (source, last_seen, items, status, cursor) VALUES (?,?,?,?,?) "
        "ON CONFLICT(source) DO UPDATE SET last_seen=excluded.last_seen, items=excluded.items, "
        "status=excluded.status, cursor=COALESCE(excluded.cursor, arp_reads.cursor)",
        (source, today, items, status, cursor))
    conn.commit()


def read_cursor(conn, source):
    got = conn.execute("SELECT cursor FROM arp_reads WHERE source=?", (source,)).fetchone()
    try:
        return json.loads(got[0]) if got and got[0] else []
    except ValueError:
        return []


class Run:
    """One run's shared state: the client, the store, the classifier."""

    def __init__(self, conn, client, today, tax, watch, log=print):
        self.conn, self.client, self.today = conn, client, today
        self.tax, self.watch, self.log = tax, watch, log
        self.gaps = 0
        for host, s in DELAYS.items():
            client.set_host_throttle(host, s)

    def gap(self, source, detail):
        self.gaps += 1
        self.log("  [gap] {0}: {1}".format(source, detail))
        db.record_gap(self.conn, FEED, "{0}: {1}".format(source, detail)[:300], self.today.isoformat())
        record_read(self.conn, source, self.today.isoformat(), 0, "failed: " + detail[:120])

    def laws(self, rows):
        new = ours = 0
        for r in rows:
            is_new, areas = upsert_law(self.conn, r, self.tax, self.watch, self.today.isoformat())
            new += is_new
            if is_new and visible(areas):
                ours += 1
                self.log("  [provincial law] {0} {1}: {2}".format(r["law_key"], visible(areas), r["title"][:80]))
        self.conn.commit()
        return new, ours

    def bills(self, rows, seed):
        new = ours = 0
        for r in rows:
            is_new, areas = upsert_bill(self.conn, r, self.tax, self.watch, self.today.isoformat(), seed)
            new += is_new
            if is_new and visible(areas):
                ours += 1
                self.log("  [provincial bill] {0} {1}: {2}".format(r["bill_key"], visible(areas), r["title"][:80]))
        self.conn.commit()
        return new, ours


def _fail(exc):
    return exc.reason if isinstance(exc, RobotsRefused) else str(exc)[:150]


def pull_saij(run, pages=SAIJ_PAGES):
    rows = []
    for i in range(pages):
        url = SAIJ.format(offset=i * SAIJ_PAGE_SIZE, size=SAIJ_PAGE_SIZE)
        try:
            reply = run.client.get_text(url, FEED, "saij-{0}".format(i), timeout=60)
            got = parse_saij(reply)
        except (FetchError, ValueError) as exc:
            if not rows:
                run.gap("saij", "SAIJ search unreadable: " + _fail(exc))
                return
            run.log("  saij: stopped at page {0}: {1}".format(i + 1, _fail(exc)))
            break
        rows += got
        if len(got) == 0:
            break
    if not rows:
        run.gap("saij", "SAIJ returned no provincial laws; its reply may have changed")
        return
    new, ours = run.laws(rows)
    record_read(run.conn, "saij", run.today.isoformat(), len(rows), "ok")
    run.log("ar-regions: SAIJ {0} provincial law(s), {1} new, {2} new on our ground.".format(len(rows), new, ours))


def pull_normas(run, pages=NORMAS_PAGES):
    rows = []
    for i in range(1, pages + 1):
        try:
            page = run.client.get_text(NORMAS.format(page=i), FEED, "normas-gba-{0}".format(i))
        except FetchError as exc:
            if not rows:
                run.gap("normas-gba", "normas.gba.gob.ar unreadable: " + _fail(exc))
                return
            break
        rows += parse_normas(page)
    if not rows:
        run.gap("normas-gba", "normas.gba.gob.ar listed no laws; its markup may have changed")
        return
    new, ours = run.laws(rows)
    record_read(run.conn, "normas-gba", run.today.isoformat(), len(rows), "ok")
    run.log("ar-regions: normas.gba {0} law(s), {1} new, {2} new on our ground.".format(len(rows), new, ours))


def pull_ba_dip(run, since):
    seed = first_read(run.conn, "ba-dip")
    rows, total, page_no = [], None, 1
    while page_no <= BA_DIP_MAX_PAGES:
        try:
            page = run.client.post_form(BA_DIP.format(page_no), ba_dip_fields(since, run.today), FEED,
                                        "ba-dip-{0}-{1}".format(since.isoformat(), page_no),
                                        timeout=120, archive=True)
        except FetchError as exc:
            if not rows:
                run.gap("ba-dip", "Diputados (Buenos Aires) search unreadable: " + _fail(exc))
                return
            run.log("  ba-dip: stopped at page {0}: {1}".format(page_no, _fail(exc)))
            break
        got = parse_ba_dip(page)
        total = total or ba_dip_total(page)
        rows += got
        if not got or total is None or len(rows) >= total:
            break
        page_no += 1
    if not rows and "NO SE REGISTRAN DATOS" not in (page or ""):
        run.gap("ba-dip", "Diputados (Buenos Aires) listed nothing; its markup may have changed")
        return
    new, ours = run.bills(rows, seed)
    record_read(run.conn, "ba-dip", run.today.isoformat(), len(rows), "ok")
    run.log("ar-regions: Diputados (Buenos Aires) {0} expediente(s) since {1}, {2} new, {3} new on our "
            "ground.".format(len(rows), since, new, ours))


def pull_caba(run):
    seed = first_read(run.conn, "caba")
    since = run.today - datetime.timedelta(days=CABA_STATUS_DAYS)
    try:
        xml = run.client.post_form(CABA, caba_fields(since, run.today), FEED,
                                   "caba-{0}".format(since.isoformat()), timeout=120, archive=True)
    except FetchError as exc:
        run.gap("caba", "Legislatura (CABA) expediente service unreadable: " + _fail(exc))
        return
    rows = parse_caba(xml)
    if not rows and "ArrayOfExpedienteAvanzado" not in (xml or ""):
        run.gap("caba", "Legislatura (CABA) service returned no expedientes; it may have changed")
        return
    new, ours = run.bills(rows, seed)
    record_read(run.conn, "caba", run.today.isoformat(), len(rows), "ok")
    run.log("ar-regions: Legislatura (CABA) {0} expediente(s) started since {1}, {2} new, {3} new on "
            "our ground.".format(len(rows), since, new, ours))


def pull_cba(run):
    seed = first_read(run.conn, "cba")
    try:
        index = run.client.get_text(CBA_SESSIONS, FEED, "cba-sessions")
    except FetchError as exc:
        run.gap("cba", "Legislatura (Córdoba) Asuntos Entrados unreadable: " + _fail(exc))
        return
    sessions = parse_cba_sessions(index)
    if not sessions:
        run.gap("cba", "Legislatura (Córdoba) listed no sessions; its markup may have changed")
        return
    done = set(read_cursor(run.conn, "cba"))
    horizon = (run.today - datetime.timedelta(days=CBA_SESSION_DAYS)).isoformat()
    todo = [s for s in sessions if s[1] and horizon <= s[1] <= run.today.isoformat() and s[0] not in done]
    rows, read = [], []
    for sid, when, label in sorted(todo, key=lambda s: s[1]):
        url = "{0}?id={1}".format(CBA_SESSIONS, sid)
        try:
            page = run.client.get_text(url, FEED, "cba-session-{0}".format(when))
        except FetchError as exc:
            run.gap("cba", "Córdoba session of {0} unreadable: {1}".format(when, _fail(exc)))
            continue
        got = parse_cba_session(page, when, url)
        rows += got
        if got:
            read.append(sid)
    new, ours = run.bills(rows, seed)
    keep = sorted(done | set(read))[-200:]
    record_read(run.conn, "cba", run.today.isoformat(), len(rows), "ok", json.dumps(keep))
    run.log("ar-regions: Legislatura (Córdoba) {0} session(s) read, {1} asunto(s), {2} new, {3} new on "
            "our ground.".format(len(read), len(rows), new, ours))


def pull_er_sen(run, since):
    seed = first_read(run.conn, "er-sen")
    rows = []
    for page_no in range(1, ER_MAX_PAGES + 1):
        url = ER_SEN if page_no == 1 else ER_SEN_PAGE.format(page_no)
        try:
            page = run.client.get_text(url, FEED, "er-sen-{0}".format(page_no))
        except FetchError as exc:
            if not rows:
                run.gap("er-sen", "Senado (Entre Ríos) project list unreadable: " + _fail(exc))
                return
            break
        got = parse_er_sen(page)
        rows += got
        dates = [r["presented"] for r in got if r["presented"]]
        if not got or (dates and min(dates) < since.isoformat()):
            break
    if not rows:
        run.gap("er-sen", "Senado (Entre Ríos) listed no projects; its markup may have changed")
        return
    new, ours = run.bills(rows, seed)
    record_read(run.conn, "er-sen", run.today.isoformat(), len(rows), "ok")
    run.log("ar-regions: Senado (Entre Ríos) {0} project(s), {1} new, {2} new on our ground.".format(
        len(rows), new, ours))


def _simple(run, source, label, fetch, parse):
    """One request, one parse, one store: the shape of the four sources
    added on 13 October 2026."""
    seed = first_read(run.conn, source)
    try:
        rows = parse(fetch())
    except (FetchError, ValueError) as exc:
        run.gap(source, "{0} unreadable: {1}".format(label, _fail(exc)))
        return
    if not rows:
        run.gap(source, "{0} listed nothing; its reply may have changed".format(label))
        return
    new, ours = run.bills(rows, seed)
    record_read(run.conn, source, run.today.isoformat(), len(rows), "ok")
    run.log("ar-regions: {0} {1} expediente(s), {2} new, {3} new on our ground.".format(
        label, len(rows), new, ours))


def pull_rn(run):
    _simple(run, "rn", "Legislatura (Río Negro)",
            lambda: run.client.get_text(RN.format(run.today.year), FEED, "rn-{0}".format(run.today.year)),
            parse_rn)


def pull_chu(run):
    _simple(run, "chu", "Legislatura (Chubut)",
            lambda: run.client.get_text(CHU, FEED, "chu-documentos"), parse_chu)


def pull_juj(run):
    _simple(run, "juj", "Legislatura (Jujuy)",
            lambda: run.client.get_text(JUJ, FEED, "juj-proyectos"), parse_juj)


def pull_ctes(run, since):
    seed = first_read(run.conn, "ctes-dip")
    rows = []
    for page_no in range(1, CTES_MAX_PAGES + 1):
        try:
            page = run.client.get_text(CTES.format(page_no), FEED, "ctes-dip-{0}".format(page_no))
        except FetchError as exc:
            if not rows:
                run.gap("ctes-dip", "Diputados (Corrientes) unreadable: " + _fail(exc))
                return
            break
        got = parse_ctes(page)
        rows += got
        dates = [r["presented"] for r in got if r["presented"]]
        if not got or (dates and min(dates) < since.isoformat()):
            break
    if not rows:
        run.gap("ctes-dip", "Diputados (Corrientes) listed nothing; its markup may have changed")
        return
    new, ours = run.bills(rows, seed)
    record_read(run.conn, "ctes-dip", run.today.isoformat(), len(rows), "ok")
    run.log("ar-regions: Diputados (Corrientes) {0} expediente(s), {1} new, {2} new on our ground.".format(
        len(rows), new, ours))


def pull_sf_dip(run, since):
    """Santa Fe Diputados (SIEL): the newest expedientes, 20 a page, until a
    page is older than the window; then the media-sanción and sanción lists
    (one search each). Before any of it: if robots.txt has ANY rule that
    applies to our user agent (a '*' group, or a group naming us), or cannot
    be read, SIEL is not read at all this run (Chris, 13 October 2026)."""
    if hasattr(run.client, "disallows_for_us"):
        covering = run.client.disallows_for_us(SF_ROOT)
    else:
        covering = ["this client does not read robots.txt"]
    if covering:
        run.gap("sf-dip", "SIEL not read: robots.txt has a rule covering our user agent, or could "
                "not be checked ({0}); stopped".format(", ".join(covering)[:120]))
        return
    seed = first_read(run.conn, "sf-dip")
    rows = []
    for page_no in range(SF_MAX_PAGES):
        url = SF_ROOT if page_no == 0 else SF_LIST.format(page_no * 20)
        try:
            page = run.client.get_text(url, FEED, "sf-dip-{0}".format(page_no + 1))
        except FetchError as exc:
            if not rows:
                run.gap("sf-dip", "Diputados (Santa Fe) SIEL unreadable: " + _fail(exc))
                return
            run.log("  sf-dip: stopped at page {0}: {1}".format(page_no + 1, _fail(exc)))
            break
        got = parse_sf_dip(page)
        rows += got
        dates = [r["presented"] for r in got if r["presented"]]
        if not got or (dates and min(dates) < since.isoformat()):
            break
    if not rows:
        run.gap("sf-dip", "Diputados (Santa Fe) SIEL listed nothing; its markup may have changed")
        return
    staged = 0
    for state, label in SF_STAGES:
        try:
            page = run.client.post_form(SF_SEARCH, sf_search_fields(state), FEED,
                                        "sf-dip-state-{0}".format(state), archive=True)
        except FetchError as exc:
            run.gap("sf-dip", "SIEL's {0} list unreadable: {1}".format(label, _fail(exc)))
            if isinstance(exc, RobotsRefused):
                break
            continue
        got = parse_sf_dip(page, stage=True)
        staged += len(got)
        rows += got
    new, ours = run.bills(rows, seed)
    record_read(run.conn, "sf-dip", run.today.isoformat(), len(rows), "ok")
    run.log("ar-regions: Diputados (Santa Fe) {0} expediente(s) ({1} from its stage lists), {2} new, "
            "{3} new on our ground.".format(len(rows), staged, new, ours))


def pull_sal_sen(run):
    """Salta Senate: the newest project posts (by entry), then the approved
    ones by last change (a post moves category when approved)."""
    seed = first_read(run.conn, "sal-sen")
    pending = ",".join(str(c) for c, v in SAL_SEN_CATS.items() if v[1] == "En trámite")
    approved = ",".join(str(c) for c, v in SAL_SEN_CATS.items() if v[1] == "Aprobado")
    asks = ((SAL_SEN_POSTS.format(cats=pending + "," + approved, n=SAL_SEN_NEW, order="date"),
             "sal-sen-new", False),
            (SAL_SEN_POSTS.format(cats=approved, n=SAL_SEN_MOVED, order="modified"),
             "sal-sen-approved", True))
    rows = []
    for url, slug, stage in asks:
        try:
            got = parse_sal_sen(run.client.get_text(url, FEED, slug), stage=stage)
        except (FetchError, ValueError) as exc:
            if not rows:
                run.gap("sal-sen", "Senado (Salta) project posts unreadable: " + _fail(exc))
                return
            run.gap("sal-sen", "Senado (Salta) approved posts unreadable: " + _fail(exc))
            break
        rows += got
    if not rows:
        run.gap("sal-sen", "Senado (Salta) listed no projects; its reply may have changed")
        return
    # one row per expediente: the approved read (later) wins over the intake read
    keyed = {}
    for r in rows:
        keyed[r["bill_key"]] = r if r["bill_key"] not in keyed or r["stage"] else keyed[r["bill_key"]]
    new, ours = run.bills(list(keyed.values()), seed)
    record_read(run.conn, "sal-sen", run.today.isoformat(), len(keyed), "ok")
    run.log("ar-regions: Senado (Salta) {0} project(s), {1} new, {2} new on our ground.".format(
        len(keyed), new, ours))


def pull_sal_dip(run):
    """Salta Diputados: this year's approved projects (laws, resolutions,
    declarations), one page each; its intake lists are empty and its Asuntos
    Entrados are PDFs (scope doc)."""
    seed = first_read(run.conn, "sal-dip")
    rows, failed = [], []
    for tipo, kind in (("ley", "ley"), ("resolucion", "resolucion"), ("declaracion", "declaracion")):
        url = SAL_DIP_APPROVED.format(run.today.year, tipo)
        try:
            rows += parse_sal_dip(run.client.get_text(url, FEED, "sal-dip-{0}-{1}".format(
                tipo, run.today.year)), kind)
        except FetchError as exc:
            failed.append("{0}: {1}".format(tipo, _fail(exc)))
            if isinstance(exc, RobotsRefused):
                break
    if not rows:
        run.gap("sal-dip", "Diputados (Salta) approved lists unreadable or empty: " + "; ".join(failed))
        return
    for f in failed:
        run.log("  sal-dip: {0}".format(f))
    new, ours = run.bills(rows, seed)
    record_read(run.conn, "sal-dip", run.today.isoformat(), len(rows), "ok")
    run.log("ar-regions: Diputados (Salta) {0} approved project(s) of {1}, {2} new, {3} new on our "
            "ground.".format(len(rows), run.today.year, new, ours))


def pull_sal_dip_ae(run):
    """Salta Diputados' intake: the Asuntos Entrados index, then each new
    sitting's PDF (at most SAL_AE_PDFS a run), as new bills. Keys already
    stored (an approved list saw them first) are left alone."""
    seed = first_read(run.conn, "sal-dip-ae")
    try:
        index = run.client.get_text(SAL_DIP_AE, FEED, "sal-dip-ae-index")
    except FetchError as exc:
        run.gap("sal-dip-ae", "Diputados (Salta) Asuntos Entrados index unreadable: " + _fail(exc))
        return
    docs = parse_sal_ae_index(index)
    if not docs:
        run.gap("sal-dip-ae", "Diputados (Salta) Asuntos Entrados listed no sitting; its markup may have changed")
        return
    done = set(read_cursor(run.conn, "sal-dip-ae"))
    todo = [d for d in docs if d[0] not in done][:SAL_AE_PDFS]
    if seed:
        # the first read: the newest sittings only; the archive is not news
        done |= {d[0] for d in docs[SAL_AE_PDFS:]}
    rows, read = [], []
    for doc_id, when, url in todo:
        try:
            blob = run.client.get_bytes(url, FEED, "sal-dip-ae-{0}".format(doc_id))
            got = parse_sal_ae(sal_pdf_text(blob), when, url)
        except (FetchError, ValueError) as exc:
            run.gap("sal-dip-ae", "Diputados (Salta) Asuntos Entrados of {0} unreadable: {1}".format(
                when, _fail(exc) if isinstance(exc, FetchError) else str(exc)[:150]))
            if isinstance(exc, RobotsRefused):
                break
            continue
        read.append(doc_id)
        if not got:
            run.log("  sal-dip-ae: the Asuntos Entrados of {0} listed no project".format(when))
        rows += got
    stored = {r[0] for r in run.conn.execute(
        "SELECT bill_key FROM arp_bills WHERE legislature='sal-dip'").fetchall()}
    fresh = [r for r in rows if r["bill_key"] not in stored]
    new, ours = run.bills(fresh, seed)
    keep = sorted(done | set(read), key=lambda x: int(x) if x.isdigit() else 0)[-300:]
    if read or not todo:
        record_read(run.conn, "sal-dip-ae", run.today.isoformat(), len(rows), "ok", json.dumps(keep))
    run.log("ar-regions: Diputados (Salta) Asuntos Entrados: {0} sitting(s) read, {1} project(s), {2} new, "
            "{3} new on our ground.".format(len(read), len(rows), new, ours))


def collect(conn, client, today, sources=SOURCES, tax=None, watch=None, saij_pages=SAIJ_PAGES,
            deadline=None, log=print):
    """Read every source in `sources`; returns the number of gaps."""
    run = Run(conn, client, today, tax, watch or {}, log)
    since = today - datetime.timedelta(days=LOOKBACK_DAYS)
    steps = {"saij": lambda: pull_saij(run, saij_pages), "normas-gba": lambda: pull_normas(run),
             "ba-dip": lambda: pull_ba_dip(run, since), "caba": lambda: pull_caba(run),
             "cba": lambda: pull_cba(run), "er-sen": lambda: pull_er_sen(run, since),
             "rn": lambda: pull_rn(run), "chu": lambda: pull_chu(run), "juj": lambda: pull_juj(run),
             "ctes-dip": lambda: pull_ctes(run, since), "sf-dip": lambda: pull_sf_dip(run, since),
             "sal-sen": lambda: pull_sal_sen(run), "sal-dip": lambda: pull_sal_dip(run),
             "sal-dip-ae": lambda: pull_sal_dip_ae(run)}
    for name in SOURCES:
        if name not in sources:
            continue
        if deadline is not None and time.monotonic() > deadline:
            run.gap(name, "not read: out of budget; the next run reads it")
            continue
        steps[name]()
    return run.gaps


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--only", nargs="+", choices=SOURCES, help="read these sources only")
    ap.add_argument("--saij-pages", type=int, default=SAIJ_PAGES)
    ap.add_argument("--budget-seconds", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reclassify", action="store_true")
    args = ap.parse_args(argv)
    started = time.monotonic()
    tax, watch = load_taxonomy(), load_watch()
    conn = db.init_db(db.connect(":memory:" if args.dry_run else args.db))
    if args.reclassify:
        print("ar-regions: {0} row(s) reclassified".format(reclassify(conn, tax, watch)))
        return 0
    # robots.txt asked on THIS run, per host, before any request; a refusal is a gap.
    client = GuardedClient(HttpClient(raw_dir=args.raw_dir, throttle=1.0), FEED)
    deadline = started + args.budget_seconds if args.budget_seconds else None
    gaps = collect(conn, client, datetime.date.today(), tuple(args.only or SOURCES), tax, watch,
                   args.saij_pages, deadline)
    if args.dry_run:
        print("ar-regions: dry run, nothing stored.")
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
