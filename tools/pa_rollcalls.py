#!/usr/bin/env python3
"""Panama, Asamblea Nacional: deputies, anteproyectos and proyectos de ley
with their stage history, and the plenary's orden del dia.

    python3 tools/pa_rollcalls.py                      # the weekly pull
    python3 tools/pa_rollcalls.py --reclassify         # re-derive areas, offline
    python3 tools/pa_rollcalls.py --taxonomy x.yaml    # classify with a draft list
    python3 tools/pa_rollcalls.py --db /tmp/pa.db      # anywhere but the store

PHASE 1 (9 October 2026); see docs/panama-scope.md. Every source is the
Asamblea's own public site, keyless, measured live:

  * segLegis, "Seguimiento Legislativo" (sistemas.asamblea.gob.pa) -- an
    ASP.NET Web Forms page. Its "Buscar todo" button lists every item of the
    current five-year term (931 on 9 October 2026, fichas 7403 to 8634,
    1 July 2024 onwards) newest first, 20 to a page; the next page is a
    postback of the previous page's own form, so the walk is strictly
    sequential (47 pages, 4.6 minutes measured). Each row carries the ficha,
    the presentation date, proyecto and anteproyecto numbers, title, current
    stage and proponent. "Ver etapas" (one more postback per row) returns
    the dated stage history; the text is at /segLegis/Documents/<ficha>.pdf.
  * /Data/Diputado/List -- JSON, every sitting deputy in one call
    (pageSize=100; 71 deputies).
  * /Data/OrdenDia/21/0/List -- JSON (DataTables, POST), every plenary orden
    del dia as a PDF link. The PDF has a text layer: its items read
    "Segundo Debate al Proyecto de Ley No. 724;" and are parsed when pypdf is
    installed (it is on the Mini and in the workflow).

NO RECORDED VOTES: the name is the edition's (tools/<cc>_rollcalls.py), the
content is not. The electronic-voting system is login-only; see
src/pa_store.py and the scope doc. The stage history says "APROBADO EN III
DEBATE" and nothing more.

ACCENTS. segLegis titles are capitals typed with or without accents
("ORGANICA DE EDUCACION" beside "ORGÁNICA DE EDUCACIÓN"), so a Spanish term
list would miss a third of its matches (measured: 28 against 19). Both the
title and the taxonomy's terms are accent-folded before matching, here and
nowhere else; the shared filter is untouched.

CLASSIFICATION waits for a Spanish taxonomy (config/taxonomy-es.yaml or a
Panama addendum, proposed in docs/panama-scope.md, generated only once
Christopher approves it). Until then areas stay NULL -- unclassified, not
"nothing found" -- and only config/watchlist-pa.yaml, applied by FICHA,
lends areas.

Separation guarantee: writes pa_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.

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
import tempfile
import time
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, pa_store, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "pa-rollcalls"
SITE = "https://www.asamblea.gob.pa"
SEGLEGIS = "https://sistemas.asamblea.gob.pa/segLegis/viewsPublico/SeguimientoLegislativo"
DOC_URL = "https://sistemas.asamblea.gob.pa/segLegis/Documents/{0}.pdf"
MEMBERS_URL = SITE + "/Data/Diputado/List?page=1&pageSize=100&search="
AGENDA_URL = SITE + "/Data/OrdenDia/21/0/List"
TAXONOMY_ES = os.path.join(ROOT, "config", "taxonomy-es.yaml")
# The country this collector matches for: a shared language list
# (taxonomy-es, -pt, -nl, -it, -fr, -atch) tags a country's own terms
# [only: ...] and filter.load_taxonomy keeps only ours (10 October 2026).
TAXONOMY_COUNTRY = "pa"
BUDGET_S = drain.DEFAULT_S
# segLegis answers a GET in about a second but a paging postback in 5 to 25
# seconds, and dropped TLS handshakes three times in one 47-page walk (9
# October 2026). Two seconds between requests and a patient retry ladder for
# the postbacks, which are read-only listings and safe to repeat.
THROTTLE_S = 2.0
POST_RETRY_WAITS = (10.0, 30.0, 90.0)
# Stage histories read per run at most. A history is read when a bill's stage
# moves, or once for a bill on our ground or on the watchlist; the cap keeps
# a first run (or a taxonomy arriving) from adding hundreds of postbacks.
MAX_STAGE_READS = 60
# Agenda PDFs read per run at most (newest first); the first run reads only
# the recent ones, the rest wait (they are history, not the week ahead).
MAX_AGENDA_PDFS = 15
AGENDA_LIST_LENGTH = 25
HIDDEN_AREAS = (11,)   # migration: collated, never campaigned (repo-wide rule)
SELECT_ANY = {"dlListTipoProponente": "\U0001F465 Seleccionar",
              "dListEtapa": "\U0001F4AC Seleccionar",
              "dlistComicion": "\U0001F4AC Seleccionar"}
MONTHS = {m: i + 1 for i, m in enumerate(
    ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
     "septiembre", "octubre", "noviembre", "diciembre"))}
MONTHS["setiembre"] = 9


# --- small helpers ------------------------------------------------------------

def fold(text):
    """Strip tags, unescape, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def deaccent(text):
    """'ORGÁNICA DE EDUCACIÓN' -> 'ORGANICA DE EDUCACION' (ñ -> n too)."""
    return "".join(c for c in unicodedata.normalize("NFD", text or "")
                   if unicodedata.category(c) != "Mn")


def iso_dmy(value):
    """'08-10-2026' -> '2026-10-08'; anything else -> None."""
    m = re.match(r"\s*(\d{1,2})-(\d{1,2})-(\d{4})\s*$", value or "")
    if not m:
        return None
    return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), int(m.group(2)), int(m.group(1)))


def iso_spanish(value):
    """'24-noviembre-2025' or '8 DE OCTUBRE DE 2026' -> ISO; else None."""
    v = deaccent(value or "").lower()
    m = re.search(r"(\d{1,2})[-\s]+(?:de\s+)?([a-z]+)[-\s]+(?:de\s+)?(\d{4})", v)
    if not m or m.group(2) not in MONTHS:
        return None
    return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))


def term_for(iso_date):
    """The five-year term an ISO date falls in: '2024-2029' for 2024-07-01 to
    2029-06-30. Panama's Asamblea is installed on 1 July of 1999, 2004, ..."""
    if not iso_date:
        return None
    y = int(iso_date[:4])
    start = y - ((y - 1999) % 5)
    if iso_date < "{0}-07-01".format(start):
        start -= 5
    return "{0}-{1}".format(start, start + 5)


def to_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def on_our_ground(areas):
    return bool(set(areas or []) - set(HIDDEN_AREAS))


# --- segLegis: the Web Forms page ----------------------------------------------

def hidden_fields(page):
    """The page's hidden form state (__VIEWSTATE and friends)."""
    out = {}
    for m in re.finditer(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', page):
        out[m.group(1)] = html.unescape(m.group(2))
    return out


def form_fields(page, target="", argument="", extra=None):
    """The fields a postback from `page` sends: its hidden state, the empty
    filters, and the control that fired."""
    fields = hidden_fields(page)
    fields.update({"txtProyecto": "", "txtAnteproyecto": "", "txtTitulo": ""})
    fields.update(SELECT_ANY)
    fields["__EVENTTARGET"] = target
    fields["__EVENTARGUMENT"] = argument
    fields.update(extra or {})
    return fields


def parse_rows(page):
    """Every bill row of a segLegis results page, as dicts.

    The grid's last <tr> is its pager, a nested table of page links; a row
    counts only when its date cell is a date."""
    t = re.search(r'id="dataTable">(.*?)</table>\s*</div>', page, re.S) or \
        re.search(r'id="dataTable">(.*)', page, re.S)
    if not t:
        return []
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t.group(1), re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 9:
            continue
        cells = [fold(x) for x in tds]
        presented = iso_dmy(cells[2])
        ficha = to_int(cells[3])
        if not presented or not ficha:
            continue
        button = re.search(r'name="(dataTable\$ctl\d+\$Button3)"', tds[1])
        out.append({
            "ficha": ficha, "presented": presented,
            "proyecto": to_int(cells[4]), "anteproyecto": to_int(cells[5]),
            "title": cells[6] or None, "stage": cells[7] or None,
            "proponent": re.sub(r"\s*,\s*", ", ", cells[8]) or None,
            "has_document": 1 if "Button2" in tds[0] else 0,
            "stages_button": button.group(1) if button else None})
    return out


def next_page_number(page, current):
    """current + 1 when the pager links to it, else None (the last page)."""
    n = current + 1
    if re.search(r"Page\$%d&#39;" % n, page) or re.search(r"Page\$%d'" % n, page):
        return n
    return None


def parse_stages(page):
    """The 'Ver etapas' modal -> [(seq, iso date, stage, comment)], oldest
    first (the page prints newest first, numbered from 1)."""
    t = re.search(r'id="GridView1"[^>]*>(.*?)</table>', page, re.S)
    if not t:
        return []
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t.group(1), re.S):
        tds = [fold(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(tds) < 4 or not to_int(tds[0]):
            continue
        rows.append((to_int(tds[0]), iso_spanish(tds[1]), tds[2] or None, tds[3] or None))
    rows.sort(key=lambda r: -r[0])
    return [(i + 1, d, s, c) for i, (_n, d, s, c) in enumerate(rows)]


class SegLegis:
    """The postback conversation with segLegis. The client's post_form does
    not retry (a POST is not obviously safe to repeat); these postbacks are
    read-only listings, so this retries them on a patient ladder."""

    def __init__(self, client, sleep=time.sleep, waits=POST_RETRY_WAITS):
        self.client, self.sleep, self.waits = client, sleep, waits

    def first(self):
        return self.client.get_text(SEGLEGIS, FEED, "seglegis-form")

    def post(self, page, slug, target="", argument="", extra=None, archive=True):
        fields = form_fields(page, target, argument, extra)
        last = None
        for wait in (0.0,) + tuple(self.waits):
            if wait:
                self.sleep(wait)
            try:
                return self.client.post_form(SEGLEGIS, fields, FEED, slug, archive=archive)
            except FetchError as exc:
                last = exc
        raise last

    def show_all(self, page):
        return self.post(page, "seglegis-page-1", extra={"btnMostrarTodo": "\U0001F50E"})

    def page(self, page, n):
        return self.post(page, "seglegis-page-{0}".format(n), "dataTable", "Page${0}".format(n))

    def stages(self, page, row):
        return self.post(page, "seglegis-stages-{0}".format(row["ficha"]),
                         extra={row["stages_button"]: "Ver etapas"})


# --- classification ---------------------------------------------------------------

def load_taxonomy(path=None):
    """The Spanish taxonomy, accent-folded, or None while none exists."""
    path = path or TAXONOMY_ES
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        text = deaccent(fh.read())
    fd, tmp = tempfile.mkstemp(suffix=".yaml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        return filt.load_taxonomy(tmp, country=TAXONOMY_COUNTRY)
    finally:
        os.unlink(tmp)


def empty_watchlist():
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify(tax, ficha, title):
    """(areas or None, matched terms, tier). areas is None only when there is
    no taxonomy AND no watchlist entry: unclassified, not empty."""
    watched = pa_store.watch_areas(ficha)
    if tax is None:
        if watched:
            return sorted(set(watched)), ["watch:{0}".format(ficha)], 2
        return None, [], None
    res = filt.filter_item(tax, empty_watchlist(), deaccent(title or ""))
    areas = set(res.issue_areas or [])
    terms = list(res.matched_terms or [])
    tier = res.tier
    if watched:
        areas |= set(watched)
        terms.append("watch:{0}".format(ficha))
        tier = tier or 2
    return sorted(areas), terms, tier


# --- storing ---------------------------------------------------------------------

def store_bill(conn, row, tax, today):
    """Upsert one bill row. Returns (areas, stage_moved, stages_read)."""
    prev = conn.execute("SELECT stage, stage_seen, stages_read FROM pa_bills WHERE ficha=?",
                        (row["ficha"],)).fetchone()
    areas, terms, tier = classify(tax, row["ficha"], row["title"])
    moved = prev is not None and (prev[0] or "") != (row["stage"] or "")
    stage_seen = today if (prev is None or moved) else prev[1]
    conn.execute(
        "INSERT INTO pa_bills (ficha, term, proyecto, anteproyecto, presented, title, stage, "
        "proponent, has_document, doc_url, stage_seen, areas, matched_terms, tier, first_seen, "
        "last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(ficha) DO UPDATE SET term=excluded.term, proyecto=excluded.proyecto, "
        "anteproyecto=excluded.anteproyecto, presented=excluded.presented, title=excluded.title, "
        "stage=excluded.stage, proponent=excluded.proponent, has_document=excluded.has_document, "
        "doc_url=excluded.doc_url, stage_seen=excluded.stage_seen, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (row["ficha"], term_for(row["presented"]), row["proyecto"], row["anteproyecto"],
         row["presented"], row["title"], row["stage"], row["proponent"], row["has_document"],
         DOC_URL.format(row["ficha"]) if row["has_document"] else None, stage_seen,
         None if areas is None else pa_store.dumps(areas), pa_store.dumps(terms), tier,
         today, today))
    return areas, moved, (prev[2] if prev else None)


def store_stages(conn, ficha, stages, today):
    conn.execute("DELETE FROM pa_bill_stages WHERE ficha=?", (ficha,))
    conn.executemany("INSERT INTO pa_bill_stages (ficha, seq, date, stage, comment) "
                     "VALUES (?,?,?,?,?)", [(ficha,) + s for s in stages])
    conn.execute("UPDATE pa_bills SET stages_read=? WHERE ficha=?", (today, ficha))


def wants_stages(row, areas, moved, stages_read):
    """Read a bill's history when its stage moved since the last run, or once
    for a bill on our ground (or watched) whose history was never read."""
    if not row.get("stages_button"):
        return False
    if moved:
        return True
    return stages_read is None and on_our_ground(areas)


def pull_bills(conn, client, today, tax=None, log=print, budget=None,
               max_stages=MAX_STAGE_READS, seg=None, max_pages=None):
    """Walk every segLegis page of the current term. Returns
    (pages, bills, on our ground, stage histories read, gaps)."""
    seg = seg or SegLegis(client)
    try:
        page = seg.show_all(seg.first())
    except FetchError as exc:
        _gap(conn, today, "segLegis list: {0}".format(exc))
        log("  [gap] segLegis list: {0}".format(str(exc)[:90]))
        return 0, 0, 0, 0, 1
    n, pages, bills, ours, histories, gaps = 1, 0, 0, 0, 0, 0
    while True:
        rows = parse_rows(page)
        if not rows:
            _gap(conn, today, "segLegis page {0} listed no bill".format(n))
            log("  [gap] segLegis page {0} listed no bill".format(n))
            gaps += 1
            break
        pages += 1
        for row in rows:
            areas, moved, stages_read = store_bill(conn, row, tax, today)
            bills += 1
            ours += on_our_ground(areas)
            if histories < max_stages and wants_stages(row, areas, moved, stages_read) and \
                    not (budget is not None and budget.exhausted()):
                try:
                    stages = parse_stages(seg.stages(page, row))
                except FetchError as exc:
                    _gap(conn, today, "segLegis stages {0}: {1}".format(row["ficha"], exc))
                    log("  [gap] segLegis stages {0}: {1}".format(row["ficha"], str(exc)[:80]))
                    gaps += 1
                    continue
                if stages:
                    store_stages(conn, row["ficha"], stages, today)
                    histories += 1
        conn.commit()
        nxt = next_page_number(page, n)
        if nxt is None:
            break
        if max_pages is not None and pages >= max_pages:
            log("  page cap ({0}) reached; the rest is read next run".format(max_pages))
            break
        if budget is not None and budget.exhausted():
            log(budget.disclose("segLegis pages", pages))
            _gap(conn, today, "segLegis walk stopped by the budget after page {0}".format(n))
            gaps += 1
            break
        try:
            page = seg.page(page, nxt)
        except FetchError as exc:
            # The walk cannot resume mid-way: each page is a postback of the
            # one before. Record it; the next run walks again from page 1.
            _gap(conn, today, "segLegis page {0}: {1}".format(nxt, exc))
            log("  [gap] segLegis page {0}: {1}".format(nxt, str(exc)[:90]))
            gaps += 1
            break
        n = nxt
    return pages, bills, ours, histories, gaps


# --- members ---------------------------------------------------------------------

def parse_members(payload):
    out = []
    for r in (payload or {}).get("data") or []:
        p = r.get("Persona") or {}
        name = fold(p.get("Nombre_Completo")) or fold(
            "{0} {1}".format(p.get("Nombres") or "", p.get("Apellidos") or ""))
        mid = to_int(r.get("ID"))
        if not name or mid is None:
            continue
        out.append({"member_id": mid, "name": name,
                    "party": fold(r.get("Partido")) or None,
                    "province": fold(r.get("Provincia")) or None,
                    "circuit": fold(r.get("Circuito")) or None,
                    "substitutes": fold(r.get("Suplentes")) or None,
                    "slug": fold(r.get("Slug")) or None})
    return out


def pull_members(conn, client, today, log=print):
    """Every sitting deputy. Returns (count, gaps)."""
    try:
        payload = client.get_json(MEMBERS_URL, FEED, "members")
    except (FetchError, ValueError) as exc:
        _gap(conn, today, "members: {0}".format(exc))
        log("  [gap] members: {0}".format(str(exc)[:90]))
        return 0, 1
    members = parse_members(payload)
    total = to_int((payload or {}).get("totalRecords"))
    gaps = 0
    if total is not None and total != len(members):
        _gap(conn, today, "members: {0} listed, {1} read".format(total, len(members)))
        log("  [gap] members: {0} listed, {1} read".format(total, len(members)))
        gaps += 1
    for m in members:
        conn.execute(
            "INSERT INTO pa_members (member_id, name, party, province, circuit, substitutes, slug, "
            "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(member_id) DO UPDATE "
            "SET name=excluded.name, party=excluded.party, province=excluded.province, "
            "circuit=excluded.circuit, substitutes=excluded.substitutes, slug=excluded.slug, "
            "last_seen=excluded.last_seen",
            (m["member_id"], m["name"], m["party"], m["province"], m["circuit"],
             m["substitutes"], m["slug"], today, today))
    conn.commit()
    return len(members), gaps


# --- the orden del dia -------------------------------------------------------------

AGENDA_FORM = ("draw=1&start=0&length={0}&order[0][column]=0&order[0][dir]=desc"
               "&columns[0][data]=ID&columns[0][orderable]=true")


def agenda_date(name, published):
    """The sitting date an orden del dia names, checked against the day it
    was published. The names carry typos: 'LUNES 31 DE AGOSTO DE 2025' was
    published on 2026-08-31 (and 31 August is a Monday only in 2026), so a
    named date more than 60 days from publication keeps its day and month
    and takes the publication's year."""
    pub = (published or "")[:10] or None
    named = iso_spanish(name)
    if not named or not pub or not re.match(r"\d{4}-\d{2}-\d{2}$", pub):
        return named or pub
    try:
        gap = abs((datetime.date.fromisoformat(named) - datetime.date.fromisoformat(pub)).days)
        if gap > 60:
            fixed = pub[:4] + named[4:]
            datetime.date.fromisoformat(fixed)
            return fixed
    except ValueError:
        return pub
    return named


def parse_agenda_list(payload):
    out = []
    for r in (payload or {}).get("data") or []:
        doc_id = to_int(r.get("ID"))
        url = (r.get("Url") or "").strip()
        if doc_id is None or not url:
            continue
        name = fold(r.get("Nombre"))
        out.append({"doc_id": doc_id, "name": name or None,
                    "date": agenda_date(name, r.get("FechaEdit")),
                    "url": url if url.startswith("http") else SITE + url})
    return out


_ITEM = re.compile(
    r"(?m)^\s*(?P<no>\d{1,3})\s*\.\s*(?P<debate>Primer|Segundo|Tercer)\s+Debate\s+al\s+"
    r"(?P<kind>Proyecto|Anteproyecto)\s+de\s+Ley\s*[.,]?\s*(?:N(?:o|º|°|úm)?\.?\s*)?(?P<num>\d+)"
    r"\s*;?\s*(?P<susp>\(\s*Suspendido\s*\))?",
    re.I)


def parse_agenda_text(text):
    """The orden del dia's text -> [{item_no, debate, kind, number, title,
    suspended}]. Each item is 'N. Segundo Debate al Proyecto de Ley No. 724;'
    followed by the title, up to the next numbered line or page header."""
    text = (text or "").replace("\r", "")
    matches = list(_ITEM.finditer(text))
    items = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end]
        body = re.split(r"(?m)^\s*\d{1,3}\s*\.\s+\S|^\s*\d+\s*\n\s*Orden de D", body)[0]
        body = re.sub(r"(?m)^\s*\d+\s*$", " ", body)
        body = re.sub(r"Orden de D[ií]a\s+\S+\s+\d+\s+de\s+\w+\s+de\s+\d{4}", " ", body)
        title = re.sub(r"\s+", " ", body).strip(" ;.") or None
        items.append({"item_no": int(m.group("no")), "debate": m.group("debate").capitalize(),
                      "kind": m.group("kind").capitalize(), "number": int(m.group("num")),
                      "title": title, "suspended": 1 if m.group("susp") else 0})
    return items


def pdf_text(raw):
    """Text of a PDF, or None when pypdf is missing or the file will not read."""
    try:
        import logging
        import pypdf
    except ImportError:
        return None
    logging.getLogger("pypdf").setLevel(logging.CRITICAL)
    try:
        reader = pypdf.PdfReader(io.BytesIO(raw))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:  # noqa: BLE001 -- a bad PDF is a gap, not a crash
        return None


def store_agenda_items(conn, doc_id, date, items):
    term = term_for(date)
    conn.execute("DELETE FROM pa_agenda_items WHERE doc_id=?", (doc_id,))
    for it in items:
        col = "proyecto" if it["kind"] == "Proyecto" else "anteproyecto"
        row = conn.execute("SELECT ficha FROM pa_bills WHERE term=? AND {0}=? "
                           "ORDER BY ficha DESC LIMIT 1".format(col),
                           (term, it["number"])).fetchone()
        conn.execute("INSERT OR REPLACE INTO pa_agenda_items (doc_id, item_no, debate, kind, "
                     "number, title, suspended, ficha) VALUES (?,?,?,?,?,?,?,?)",
                     (doc_id, it["item_no"], it["debate"], it["kind"], it["number"],
                      it["title"], it["suspended"], row[0] if row else None))
    conn.execute("UPDATE pa_agenda SET items=? WHERE doc_id=?", (len(items), doc_id))


def pull_agenda(conn, client, today, log=print, max_pdfs=MAX_AGENDA_PDFS, budget=None):
    """The newest orden del dia documents, and the bill items of those not
    yet read. Returns (listed, pdfs read, items, gaps)."""
    try:
        fields = [tuple(kv.split("=", 1))
                  for kv in AGENDA_FORM.format(AGENDA_LIST_LENGTH).split("&")]
        payload = client.post_form(AGENDA_URL, fields, FEED, "agenda-list", archive=True)
        docs = parse_agenda_list(json.loads(payload))
    except (FetchError, ValueError) as exc:
        _gap(conn, today, "orden del dia list: {0}".format(exc))
        log("  [gap] orden del dia list: {0}".format(str(exc)[:90]))
        return 0, 0, 0, 1
    for d in docs:
        conn.execute("INSERT INTO pa_agenda (doc_id, date, name, url, first_seen, last_seen) "
                     "VALUES (?,?,?,?,?,?) ON CONFLICT(doc_id) DO UPDATE SET date=excluded.date, "
                     "name=excluded.name, url=excluded.url, last_seen=excluded.last_seen",
                     (d["doc_id"], d["date"], d["name"], d["url"], today, today))
    conn.commit()
    pending = conn.execute("SELECT doc_id, date, url FROM pa_agenda WHERE items IS NULL "
                           "ORDER BY doc_id DESC LIMIT ?", (max_pdfs,)).fetchall()
    read = items = gaps = 0
    for doc_id, date, url in pending:
        if budget is not None and budget.exhausted():
            log(budget.disclose("orden del dia PDFs", read))
            break
        try:
            raw = client.get_bytes(url, FEED, "agenda-{0}".format(doc_id))
        except FetchError as exc:
            _gap(conn, today, "orden del dia {0}: {1}".format(doc_id, exc))
            log("  [gap] orden del dia {0}: {1}".format(doc_id, str(exc)[:90]))
            gaps += 1
            continue
        text = pdf_text(raw)
        if text is None:
            log("  orden del dia {0}: no text (pypdf missing or unreadable); "
                "listed, items not parsed".format(doc_id))
            continue
        parsed = parse_agenda_text(text)
        store_agenda_items(conn, doc_id, date, parsed)
        conn.commit()
        read += 1
        items += len(parsed)
    return len(docs), read, items, gaps


# --- offline -----------------------------------------------------------------------

def reclassify(conn, tax=None, log=print):
    changed = 0
    for ficha, title, areas in conn.execute(
            "SELECT ficha, title, areas FROM pa_bills").fetchall():
        new, terms, tier = classify(tax, ficha, title)
        new_s = None if new is None else pa_store.dumps(new)
        changed += new_s != areas
        conn.execute("UPDATE pa_bills SET areas=?, matched_terms=?, tier=? WHERE ficha=?",
                     (new_s, pa_store.dumps(terms), tier, ficha))
    conn.commit()
    log("pa-rollcalls: reclassified; {0} bill(s) changed area".format(changed))
    return changed


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = sum(on_our_ground(json.loads(a)) for (a,) in conn.execute(
        "SELECT areas FROM pa_bills WHERE areas IS NOT NULL"))
    log("  store: {0} bill(s), {1} on our ground, {2} unclassified, {3} with a stage history; "
        "{4} member(s); {5} orden(es) del dia, {6} agenda item(s)".format(
            n("SELECT COUNT(*) FROM pa_bills"), ours,
            n("SELECT COUNT(*) FROM pa_bills WHERE areas IS NULL"),
            n("SELECT COUNT(*) FROM pa_bills WHERE stages_read IS NOT NULL"),
            n("SELECT COUNT(*) FROM pa_members"), n("SELECT COUNT(*) FROM pa_agenda"),
            n("SELECT COUNT(*) FROM pa_agenda_items")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"),
                    help="where raw responses are archived (default data/raw)")
    ap.add_argument("--taxonomy", help="classify with this taxonomy file "
                                       "(default config/taxonomy-es.yaml when it exists)")
    ap.add_argument("--no-bills", action="store_true")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--no-agenda", action="store_true")
    ap.add_argument("--max-pages", type=int, help="stop the segLegis walk after this many pages")
    ap.add_argument("--max-stages", type=int, default=MAX_STAGE_READS,
                    help="stage histories read at most (default %(default)s)")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored bills, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    args = ap.parse_args()
    tax = load_taxonomy(args.taxonomy)
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn, tax)
        summary(conn)
        conn.close()
        return 0
    if tax is None:
        print("pa-rollcalls: no Spanish taxonomy yet (config/taxonomy-es.yaml); "
              "areas stay NULL, only watchlist-pa lends areas")
    client = HttpClient(raw_dir=args.raw_dir, throttle=THROTTLE_S)
    today = datetime.date.today().isoformat()
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    if not args.no_members:
        n, g = pull_members(conn, client, today)
        gaps += g
        print("pa-rollcalls: {0} deputy record(s), {1} gap(s)".format(n, g))
    if not args.no_bills:
        pages, bills, ours, hist, g = pull_bills(conn, client, today, tax=tax, budget=budget,
                                                 max_stages=args.max_stages,
                                                 max_pages=args.max_pages)
        gaps += g
        print("pa-rollcalls: {0} segLegis page(s), {1} bill(s) read, {2} on our ground, "
              "{3} stage histor(ies) read, {4} gap(s)".format(pages, bills, ours, hist, g))
    if not args.no_agenda:
        listed, read, items, g = pull_agenda(conn, client, today, budget=budget)
        gaps += g
        print("pa-rollcalls: {0} orden(es) del dia listed, {1} read, {2} bill item(s), "
              "{3} gap(s)".format(listed, read, items, g))
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
