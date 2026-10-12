#!/usr/bin/env python3
"""Spain's regional layer: the seventeen autonomous communities' laws from
the BOE, and the bills in passage in the regional parliaments whose own
sites list them.

    python3 tools/es_regions.py                       # every source
    python3 tools/es_regions.py --sources boe,an      # some of them
    python3 tools/es_regions.py --boe-days 30         # read further back
    python3 tools/es_regions.py --reclassify          # re-derive areas, offline
    python3 tools/es_regions.py --db /tmp/esr.db      # anywhere but the store

12 October 2026; see docs/spain-regions-scope.md for every measurement.

THE SOURCES, all keyless, all probed live and robots.txt read first:

  boe  www.boe.es/datosabiertos/api/boe/sumario/YYYYMMDD (JSON with
       Accept: application/json): one request per BOE issue, Monday to
       Saturday (a Sunday answers 404, which is not a gap). Section I
       ("Disposiciones generales") under a community's department is that
       community's laws, decree-laws and the odd decree, IN SPANISH FOR ALL
       SEVENTEEN, Catalan, Basque, Galician and Valencian laws included. 77
       such acts from 1 January to 9 October 2026 (the scope doc has the
       month-by-month count). /diario_boe/xml.php is disallowed by robots.txt
       and never read; the open-data API is not.
  an   Parlamento de Andalucía, the "Iniciativas en tramitación" RSS
       (ISO-8859-1): every legislative initiative in passage, with the
       expediente in the title ('13-26/PPL-000002. Proposición de Ley ...').
  cn   Parlamento de Canarias, /leyes/ ("Leyes en tramitación"), one HTML
       list by type. robots.txt asks for 3 seconds between pages and
       disallows /api/ (the open-data portal's CSV and JSON files live under
       /api/, so they are NOT read; scope doc, Waiting on Chris).
  ri   Parlamento de La Rioja, /actividad-parlamentaria/proyectos-de-ley:
       every government bill of the legislature with its status ('en
       tramitación', 'cerrado') and its entry date. Members' bills have no
       list there (the proposiciones page is empty, /iniciativas/ppl is 404).
  cb   Parlamento de Cantabria, /actividad/dossieres-legislativos: one
       numbered dossier per bill ('180/XI Legislatura') with its date.
  vc   Corts Valencianes, /ca-va/activitat/iniciative (first page, newest
       first): titles in VALENCIAN only (the /es/ path is 404), so they are
       stored with lang 'ca' and classified with the Catalan/Valencian list
       (config/taxonomy-ca.yaml, an unmeasured draft Chris approved on 12
       October 2026). Before that list they were stored unclassified and
       counted as a gap: the Spanish taxonomy is blind to Valencian.

CLASSIFICATION BY LANGUAGE (12 October 2026). A row is classified with the
list of the language its title is published in: 'es' (every BOE item, and
the Andalucía, Canarias, La Rioja and Cantabria lists) with taxonomy-es,
'ca' (Catalan or Valencian, whichever parliament) with taxonomy-ca. Any
other language ('eu', 'gl') has no list and is stored with areas NULL,
unclassified rather than "nothing found". `--reclassify` re-derives every
stored row the same way, so the Valencian rows stored before the Catalan
list existed are classified by one offline run.

Not read, and why (the scope doc has the detail): Madrid (Sucuri JavaScript
challenge), Navarra (Cloudflare challenge), Galicia (Akamai 403), Murcia
and Extremadura (robots.txt disallows everything), País Vasco, Illes Balears
and the Aragón tramitación database (no answer from the laptop), Cataluña
(Catalan only, open-data page 500), Castilla y León, Castilla-La Mancha and
Asturias (no machine-readable list of bills in passage). Their laws still
arrive through the BOE.

A dissolution, a new legislature or a list that changes shape shows as a
source with zero rows: that is a [gap] line and a gaps row, never silence.

Separation guarantee: writes esr_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.

Exit codes: 0 clean, 3 stored what it could and recorded gaps, 1 otherwise.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, es_regions_store as esr, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "es-regions"
TAXONOMY_ES = os.path.join(ROOT, "config", "taxonomy-es.yaml")
TAXONOMY_CA = os.path.join(ROOT, "config", "taxonomy-ca.yaml")
TAXONOMY_COUNTRY = "es"
# The languages a title can be classified in; see the docstring.
CLASSIFIED_LANGS = ("es", "ca")
HIDDEN_AREAS = (11,)   # migration: collated, never campaigned (repo-wide rule)
BUDGET_S = drain.DEFAULT_S

BOE_SUMARIO = "https://www.boe.es/datosabiertos/api/boe/sumario/{day}"
# A first run reads two weeks back; later runs read from the day after the
# newest issue read, re-reading the last REREAD_DAYS (a late correction).
BOE_FIRST_DAYS = 14
BOE_MAX_DAYS = 62
REREAD_DAYS = 2

SOURCES = {
    "an": ("https://www.parlamentodeandalucia.es/webdinamica/portal-web-parlamento/"
           "utilidades/sindicacionrss.do?contenido=Iniciativas"),
    "cn": "https://www.parcan.es/leyes/",
    "ri": "https://www.parlamento-larioja.org/actividad-parlamentaria/proyectos-de-ley",
    "cb": "https://parlamento-cantabria.es/actividad/dossieres-legislativos",
    "vc": "https://www.cortsvalencianes.es/ca-va/activitat/iniciative",
}
SOURCE_ORDER = ("boe", "an", "cn", "ri", "cb", "vc")
# robots.txt Crawl-delay where a site sets one (parcan.es: 3).
HOST_THROTTLE = {"www.parcan.es": 3.0, "www.boe.es": 1.0}


# --- small helpers ------------------------------------------------------------

def fold(text):
    """Strip tags, unescape, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def plain(text):
    """Lower case, accents folded: for matching only, never stored."""
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def iso(ddmmyyyy):
    """'30/9/2026' or '30/09/2026' -> '2026-09-30'; anything else -> None."""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", ddmmyyyy or "")
    if not m:
        return None
    return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), int(m.group(2)), int(m.group(1)))


MONTHS_EN = {m: i + 1 for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}


def rfc822_iso(text):
    """'Tue, 8 Sep 2026 09:00:00 +0200' -> '2026-09-08'; else None."""
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})\w*\s+(\d{4})", text or "")
    if not m or m.group(2).lower() not in MONTHS_EN:
        return None
    return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), MONTHS_EN[m.group(2).lower()],
                                        int(m.group(1)))


def decode(raw):
    """Bytes to text by the XML or HTML declaration; UTF-8 otherwise."""
    head = raw[:400].decode("ascii", errors="replace").lower()
    m = re.search(r"""encoding=["']([\w-]+)["']|charset=["']?([\w-]+)""", head)
    enc = (m.group(1) or m.group(2)) if m else "utf-8"
    try:
        return raw.decode(enc)
    except (LookupError, UnicodeDecodeError):
        return raw.decode("utf-8", errors="replace")


def aslist(x):
    return x if isinstance(x, list) else ([x] if x else [])


def kind_of(text):
    """The kind of bill, from its title or its type code."""
    t = plain(text)
    for start, kind in (("proyecto de ley", "proyecto de ley"), ("projecte de llei", "proyecto de ley"),
                        ("pojecte de llei", "proyecto de ley"),
                        ("proposicion de ley", "proposición de ley"),
                        ("proposicio de llei", "proposición de ley"),
                        ("iniciativa legislativa popular", "ilp"),
                        ("decreto ley", "decreto-ley"), ("decreto-ley", "decreto-ley")):
        if t.startswith(start) or start in t[:40]:
            return kind
    return None


CODE_KINDS = {"PL": "proyecto de ley", "PPL": "proposición de ley", "ILP": "ilp",
              "ILPA": "ilp", "DL": "decreto-ley", "PPLE": "proposición de ley",
              "PLEN": "proposición de ley"}


def code_kind(expediente):
    m = re.search(r"/([A-Z]+)-\d", expediente or "")
    return CODE_KINDS.get(m.group(1)) if m else None


def rank_of(title):
    """'ley', 'decreto-ley', 'decreto legislativo', 'decreto', 'correction' or 'other'."""
    t = plain(title)
    if t.startswith(("correccion", "correcion")):
        return "correction"
    if re.match(r"decreto[\s-]+ley\b", t):
        return "decreto-ley"
    if t.startswith("decreto legislativo"):
        return "decreto legislativo"
    if t.startswith("ley"):
        return "ley"
    if t.startswith("decreto"):
        return "decreto"
    return "other"


def region_of_department(name):
    t = plain(name).upper().replace("Ñ", "N")
    if t.startswith("CIUDAD"):
        return None
    for word, code in esr.BOE_DEPARTMENTS:
        if word in t:
            return code
    return None


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))
    print("  [gap] " + detail)


def _read(conn, source, now, items, status, last_day=None):
    conn.execute(
        "INSERT INTO esr_reads (source, last_seen, last_day, items, status) VALUES (?,?,?,?,?) "
        "ON CONFLICT(source) DO UPDATE SET last_seen=excluded.last_seen, "
        "last_day=COALESCE(excluded.last_day, esr_reads.last_day), items=excluded.items, "
        "status=excluded.status", (source, now, last_day, items, status))


# --- classification ---------------------------------------------------------------

def load_taxonomy(path=None):
    path = path or TAXONOMY_ES
    return filt.load_taxonomy(path, country=TAXONOMY_COUNTRY) if os.path.exists(path) else None


_CATALAN = {}


def load_catalan(path=None):
    """The Catalan/Valencian list, loaded once per path (None if absent)."""
    path = path or TAXONOMY_CA
    if path not in _CATALAN:
        _CATALAN[path] = (filt.load_taxonomy(path, country=TAXONOMY_COUNTRY)
                          if os.path.exists(path) else None)
    return _CATALAN[path]


def taxonomy_for(tax, lang):
    """The taxonomy for a title in `lang`. `tax` is the Spanish taxonomy (as
    every caller has always passed it) or a {lang: taxonomy} mapping; a
    Catalan title gets taxonomy-ca unless the mapping names another."""
    if isinstance(tax, dict):
        if lang in tax:
            return tax[lang]
        return load_catalan() if lang == "ca" else None
    if lang == "es":
        return tax
    if lang == "ca":
        return load_catalan()
    return None


def classify(tax, *texts):
    """(areas or None, terms, tier). None when there is no taxonomy."""
    if tax is None:
        return None, [], None
    res = filt.filter_item(tax, filt.Watchlist(entities=[], bill_titles=[], act_shorts=[]),
                           *[t for t in texts if t])
    return sorted(set(res.issue_areas or [])), list(res.matched_terms or []), res.tier


def on_our_ground(areas):
    return bool(set(areas or []) - set(HIDDEN_AREAS))


# --- the BOE ---------------------------------------------------------------------

def parse_boe(data, day):
    """Every community act in section I of one BOE issue, as dicts."""
    out = []
    sumario = (data.get("data") or {}).get("sumario") or {}
    for diario in aslist(sumario.get("diario")):
        for sec in aslist(diario.get("seccion")):
            if str(sec.get("codigo")) != "1":
                continue
            for dep in aslist(sec.get("departamento")):
                if not dep:
                    continue
                region = region_of_department(dep.get("nombre"))
                if not region:
                    continue
                pairs = [(ep.get("nombre"), it) for ep in aslist(dep.get("epigrafe")) if ep
                         for it in aslist(ep.get("item"))]
                pairs += [(None, it) for it in aslist(dep.get("item"))]
                for heading, it in pairs:
                    if not it or not it.get("identificador"):
                        continue
                    pdf = it.get("url_pdf")
                    out.append({
                        "boe_id": it["identificador"], "region": region,
                        "department": str(dep.get("codigo") or "") or None,
                        "published": day, "rank": rank_of(it.get("titulo")),
                        "title": fold(it.get("titulo")), "heading": fold(heading) or None,
                        "url_html": it.get("url_html"),
                        "url_pdf": pdf.get("texto") if isinstance(pdf, dict) else pdf,
                    })
    return out


def store_law(conn, tax, law, today):
    areas, terms, tier = classify(taxonomy_for(tax, "es"), law["title"], law["heading"])
    conn.execute(
        "INSERT INTO esr_laws (boe_id, region, department, published, rank, title, heading, "
        "url_html, url_pdf, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(boe_id) DO UPDATE SET "
        "region=excluded.region, department=excluded.department, published=excluded.published, "
        "rank=excluded.rank, title=excluded.title, heading=excluded.heading, "
        "url_html=excluded.url_html, url_pdf=excluded.url_pdf, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (law["boe_id"], law["region"], law["department"], law["published"], law["rank"],
         law["title"], law["heading"], law["url_html"], law["url_pdf"],
         None if areas is None else esr.dumps(areas), esr.dumps(terms), tier, today, today))
    return areas


def boe_days(conn, today, days=None):
    """The issue dates to read, oldest first."""
    end = datetime.date.fromisoformat(today)
    if days:
        start = end - datetime.timedelta(days=int(days) - 1)
    else:
        row = conn.execute("SELECT last_day FROM esr_reads WHERE source='boe'").fetchone()
        if row and row[0]:
            start = datetime.date.fromisoformat(row[0]) - datetime.timedelta(days=REREAD_DAYS)
        else:
            start = end - datetime.timedelta(days=BOE_FIRST_DAYS - 1)
        start = max(start, end - datetime.timedelta(days=BOE_MAX_DAYS - 1))
    out, d = [], start
    while d <= end:
        if d.weekday() != 6:   # the BOE does not publish on Sundays
            out.append(d)
        d += datetime.timedelta(days=1)
    return out


def pull_boe(conn, client, today, tax, budget, days=None):
    """(issues read, acts stored, on our ground, gaps)."""
    read = stored = ours = gaps = 0
    newest = None
    for d in boe_days(conn, today, days):
        if budget.exhausted():
            print(budget.disclose("BOE issue(s)", read))
            break
        ymd = d.strftime("%Y%m%d")
        try:
            text = client.get_text(BOE_SUMARIO.format(day=ymd), FEED, "boe-sumario-" + ymd,
                                   headers={"Accept": "application/json"})
        except FetchError as e:
            if "404" in str(e.cause):
                continue   # no issue that day (a holiday): not a gap
            _gap(conn, today, "BOE sumario {0}: {1}".format(d.isoformat(), str(e.cause)[:120]))
            gaps += 1
            continue
        try:
            data = json.loads(text)
        except ValueError:
            _gap(conn, today, "BOE sumario {0}: not JSON".format(d.isoformat()))
            gaps += 1
            continue
        read += 1
        newest = d.isoformat()
        for law in parse_boe(data, d.isoformat()):
            areas = store_law(conn, tax, law, today)
            stored += 1
            ours += on_our_ground(areas)
    _read(conn, "boe", today, stored, "ok" if not gaps else "gaps", newest)
    conn.commit()
    return read, stored, ours, gaps


# --- the regional parliaments' lists -------------------------------------------------

def parse_an(text):
    """Andalucía's RSS: [{expediente, title, presented, url, kind}]."""
    out = []
    for item in re.findall(r"<item>(.*?)</item>", text, re.S):
        def tag(name):
            m = re.search(r"<{0}>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</{0}>".format(name), item, re.S)
            return fold(m.group(1)) if m else ""
        title = tag("title")
        m = re.match(r"(\d+-\d+/[A-Z]+-\d+)\.\s*(.*)", title)
        if not m:
            continue
        exp, rest = m.group(1), m.group(2).strip()
        url = re.sub(r"&(desc|utm_\w+)=[^&]*", "", tag("link")).strip()
        out.append({"expediente": exp, "title": rest, "presented": rfc822_iso(tag("pubDate")),
                    "url": url or None, "kind": code_kind(exp) or kind_of(rest),
                    "status": "en tramitación", "proponent": None, "lang": "es"})
    return out


CN_LABELS = {"proyecto de ley": "Proyecto de Ley", "proposición de ley": "Proposición de Ley",
             "decreto-ley": "Decreto ley", "ilp": "Iniciativa legislativa popular"}


def parse_cn(text):
    """Canarias' /leyes/: one section per type, one <li> per bill."""
    out = []
    for sec in re.findall(r'<section aria-label="([^"]*)">(.*?)</section>', text, re.S):
        label, body = sec
        for m in re.finditer(r'<li>\s*<strong>\s*<a href="([^"]+)">\s*([^<]+?)\s*</a>\s*</strong>(.*?)</li>',
                             body, re.S):
            href, exp, rest = m.group(1), m.group(2), fold(m.group(3))
            kind = code_kind(exp) or kind_of(label)
            lead = CN_LABELS.get(kind)
            if lead and rest and not kind_of(rest):
                rest = "{0} {1}{2}".format(lead, rest[0].lower() if re.match(r"(De|Del|Por|Sobre)\b", rest)
                                           else rest[0], rest[1:])
            out.append({"expediente": exp, "title": rest,
                        "presented": None, "url": "https://www.parcan.es" + href
                        if href.startswith("/") else href, "kind": kind,
                        "status": "en tramitación", "proponent": None, "lang": "es"})
    return out


def parse_ri(text):
    """La Rioja's proyectos de ley: number, title, status, entry date, proponent."""
    out = []
    for part in text.split('<div class="item visualIEFloatFix">')[1:]:
        num = re.search(r'<h1 class="h2-size">\s*([^<]+?)\s*</h1>', part)
        link = re.search(r'<a href="([^"]+)" class="summary url">\s*(.*?)\s*</a>', part, re.S)
        if not num or not link:
            continue
        status = re.search(r'class="[^"]*\blabel">\s*([^<]+?)\s*</p>', part)
        date = re.search(r'medium-2 columns">\s*(\d{1,2}/\d{1,2}/\d{4})', part)
        prop = re.search(r"Proponentes:</h3>\s*<ul>\s*<li>(.*?)</li>", part, re.S)
        title = fold(link.group(2))
        if title.upper().startswith("PROYECTO DE LEY"):
            title = "Proyecto de Ley" + title[len("PROYECTO DE LEY"):]
        out.append({"expediente": fold(num.group(1)), "title": title,
                    "presented": iso(date.group(1)) if date else None, "url": link.group(1),
                    "kind": code_kind(fold(num.group(1))) or kind_of(title),
                    "status": fold(status.group(1)) if status else None,
                    "proponent": fold(prop.group(1)).strip(" -") if prop else None, "lang": "es"})
    return out


def parse_cb(text):
    """Cantabria's legislative dossiers: '180/XI Legislatura', title, date."""
    out = []
    for li in re.findall(r'<li class="list-group-item node-bop">(.*?)</li>', text, re.S):
        num = re.search(r'<a href="([^"]+)"[^>]*>\s*(\d+)/([IVXL]+) Legislatura\s*</a>', li)
        title = re.search(r'views-field-field-t-tulo">\s*<div class="field-content">(.*?)</div>', li, re.S)
        when = re.search(r'datetime="(\d{4}-\d{2}-\d{2})', li)
        if not num or not title:
            continue
        t = fold(title.group(1))
        out.append({"expediente": "{0}/{1}".format(num.group(2), num.group(3)), "title": t,
                    "presented": when.group(1) if when else None,
                    "url": "https://parlamento-cantabria.es" + num.group(1)
                    if num.group(1).startswith("/") else num.group(1),
                    "kind": kind_of(t), "status": None, "proponent": None, "lang": "es"})
    return out


def parse_vc(text):
    """Corts Valencianes' legislative initiatives (Valencian titles)."""
    out = []
    blocks = re.split(r'<div class="js-views-accordion-group-header">', text)[1:]
    for b in blocks:
        title = re.search(r'<p class="item-title-simple">(.*?)</p>', b, re.S)
        ext = re.search(r'consulta_legista#[^"]*?/id/(\d+)"', b)
        boc = re.search(r'BOC\s+(\d+)\s*-\s*(\d{1,2}/\d{1,2}/\d{4})', b)
        typ = re.search(r'field-taxon-initiative[^>]*>\s*<div class="field-content">\s*<a[^>]*>([^<]+)</a>', b)
        prop = re.search(r'Proponent:\s*</span>\s*<div class="field-content">([^<]+)</div>', b)
        if not title or not ext:
            continue
        t = fold(title.group(1))
        out.append({"expediente": ext.group(1), "title": t,
                    "presented": iso(boc.group(2)) if boc else None,
                    "url": "https://www.cortsvalencianes.es/consulta_legista#activitat/parlamentaria/"
                           "detall/id/" + ext.group(1),
                    "kind": kind_of(fold(typ.group(1)) if typ else t),
                    "status": "BOC {0}".format(boc.group(1)) if boc else None,
                    "proponent": fold(prop.group(1)) if prop else None, "lang": "ca"})
    return out


PARSERS = {"an": parse_an, "cn": parse_cn, "ri": parse_ri, "cb": parse_cb, "vc": parse_vc}


def store_bill(conn, tax, region, b, today, seed):
    key = "{0}:{1}".format(region, b["expediente"])
    areas, terms, tier = classify(taxonomy_for(tax, b["lang"]), b["title"])
    conn.execute(
        "INSERT INTO esr_bills (bill_key, region, expediente, kind, title, status, presented, "
        "proponent, url, lang, areas, matched_terms, tier, first_seen, last_seen, seed) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(bill_key) DO UPDATE SET "
        "kind=excluded.kind, title=excluded.title, status=excluded.status, "
        "presented=COALESCE(excluded.presented, esr_bills.presented), "
        "proponent=COALESCE(excluded.proponent, esr_bills.proponent), url=excluded.url, "
        "lang=excluded.lang, areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen",
        (key, region, b["expediente"], b["kind"], b["title"], b["status"], b["presented"],
         b["proponent"], b["url"], b["lang"], None if areas is None else esr.dumps(areas),
         esr.dumps(terms), tier, today, today, 1 if seed else 0))
    return areas


def pull_list(conn, client, today, tax, region):
    """(rows listed, on our ground, gaps) for one parliament's list."""
    url = SOURCES[region]
    seed = conn.execute("SELECT 1 FROM esr_reads WHERE source=? AND status='ok'",
                        (region,)).fetchone() is None
    try:
        raw = client.get_bytes(url, FEED, "list-" + region)
    except FetchError as e:
        _gap(conn, today, "{0}: {1}".format(esr.PARLIAMENTS[region], str(e.cause)[:120]))
        _read(conn, region, today, 0, "failed: " + str(e.cause)[:80])
        conn.commit()
        return 0, 0, 1
    bills = PARSERS[region](decode(raw))
    if not bills:
        _gap(conn, today, "{0}: the list parsed to no bills (page changed shape?)".format(
            esr.PARLIAMENTS[region]))
        _read(conn, region, today, 0, "empty")
        conn.commit()
        return 0, 0, 1
    ours = 0
    for b in bills:
        ours += on_our_ground(store_bill(conn, tax, region, b, today, seed))
    _read(conn, region, today, len(bills), "ok")
    conn.commit()
    return len(bills), ours, 0


# --- reclassify -------------------------------------------------------------------

def reclassify(conn, tax):
    """(rows, Catalan/Valencian bills classified, of which on our ground)."""
    n = catalan = catalan_ours = 0
    for boe_id, title, heading in conn.execute(
            "SELECT boe_id, title, heading FROM esr_laws").fetchall():
        areas, terms, tier = classify(taxonomy_for(tax, "es"), title, heading)
        conn.execute("UPDATE esr_laws SET areas=?, matched_terms=?, tier=? WHERE boe_id=?",
                     (None if areas is None else esr.dumps(areas), esr.dumps(terms), tier, boe_id))
        n += 1
    for key, title, lang in conn.execute(
            "SELECT bill_key, title, lang FROM esr_bills").fetchall():
        areas, terms, tier = classify(taxonomy_for(tax, lang), title)
        conn.execute("UPDATE esr_bills SET areas=?, matched_terms=?, tier=? WHERE bill_key=?",
                     (None if areas is None else esr.dumps(areas), esr.dumps(terms), tier, key))
        n += 1
        if lang == "ca" and areas is not None:
            catalan += 1
            catalan_ours += on_our_ground(areas)
    conn.commit()
    print("es-regions: {0} row(s) reclassified; {1} Catalan/Valencian bill(s) classified, {2} on "
          "our ground".format(n, catalan, catalan_ours))
    return n, catalan, catalan_ours


def summary(conn):
    laws = conn.execute("SELECT COUNT(*) FROM esr_laws").fetchone()[0]
    bills = conn.execute("SELECT COUNT(*) FROM esr_bills").fetchone()[0]
    print("es-regions store: {0} regional act(s) from the BOE, {1} regional bill(s) listed".format(
        laws, bills))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", help="store path (default: the shared store)")
    ap.add_argument("--sources", help="comma-separated: " + ",".join(SOURCE_ORDER))
    ap.add_argument("--boe-days", type=int, help="read this many days back from today")
    ap.add_argument("--taxonomy", help="a taxonomy file (default config/taxonomy-es.yaml)")
    ap.add_argument("--taxonomy-ca", help="the Catalan/Valencian list "
                                          "(default config/taxonomy-ca.yaml)")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive every stored row's areas, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--date", help="ISO date to stamp the run with (tests)")
    args = ap.parse_args(argv)
    tax = {"es": load_taxonomy(args.taxonomy), "ca": load_catalan(args.taxonomy_ca)}
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn, tax)
        summary(conn)
        conn.close()
        return 0
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"), throttle=1.0)
    for host, s in HOST_THROTTLE.items():
        client.set_host_throttle(host, s)
    today = args.date or datetime.date.today().isoformat()
    budget = drain.Budget(args.budget_seconds)
    wanted = [s.strip() for s in args.sources.split(",")] if args.sources else list(SOURCE_ORDER)
    gaps = 0
    for src in wanted:
        if src not in SOURCE_ORDER:
            print("es-regions: unknown source {0!r}".format(src))
            return 1
        if budget.exhausted():
            print(budget.disclose("source(s)", wanted.index(src)))
            _gap(conn, today, "time budget reached before {0}".format(src))
            gaps += 1
            break
        if src == "boe":
            r, s, o, g = pull_boe(conn, client, today, tax, budget, args.boe_days)
            print("es-regions boe: {0} issue(s) read, {1} regional act(s), {2} on our ground, "
                  "{3} gap(s)".format(r, s, o, g))
        else:
            n, o, g = pull_list(conn, client, today, tax, src)
            print("es-regions {0}: {1} bill(s) listed, {2} on our ground, {3} gap(s)".format(
                src, n, o, g))
        gaps += g
    conn.commit()
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
