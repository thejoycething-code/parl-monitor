#!/usr/bin/env python3
"""Argentina's National Congress: members, expedientes, Senate roll calls.

    python3 tools/ar_rollcalls.py                     # the weekly pull
    python3 tools/ar_rollcalls.py --years 2024 2025 2026   # a backfill of Senate actas
    python3 tools/ar_rollcalls.py --dry-run           # read the listings, store nothing
    python3 tools/ar_rollcalls.py --reclassify        # re-derive areas, offline
    python3 tools/ar_rollcalls.py --db /tmp/ar.db --raw-dir /tmp/ar-raw   # a scratch run

PHASE 1 (9 October 2026). See docs/argentina-scope.md. No edition reads these
tables yet. Every source is open and keyless:

  * www.senado.gob.ar/votaciones/actas -- every Senate roll call of a year in
    one page (a plain form POST picks the year), and one detail page per acta
    (/votaciones/detalleActa/<id>) with EVERY senator's position, bloc and
    province. Sitting senators carry a link with the Senate's own ID; FORMER
    senators are printed without one, so they are resolved by exact name
    against the Senate's historic roster, and a name that matches no single
    ID is dropped and recorded as a gap, never stored under a guess.
  * www.senado.gob.ar/parlamentario/comisiones/verExp/<n>.<yy>/<origin>/<type>
    -- the expediente an acta names: its extracto, the Diputados number when
    it came from there, committees and the law number.
  * www.senado.gob.ar/micrositios/DatosAbiertos/ExportarListadoSenadores/json
    -- the sitting Senate.
  * datos.hcdn.gob.ar (CKAN) -- the Diputados register of expedientes
    ("Proyectos Parlamentarios", updated daily) and the diputados with their
    bloc spells, both through CKAN's datastore SQL endpoint.

DIPUTADOS ROLL CALLS ARE NOT COLLECTED. votaciones.hcdn.gob.ar, the only
place HCDN publishes them since 2019, never completed a TLS handshake from
the laptop (London) or from a GitHub runner on 9 October 2026. Each run asks
it once, briefly, and says what it got; a refusal is the known state and is
NOT a gap (it would turn every weekly red for a block we already know of).
If it ever answers, the log says so loudly.

DATOS.HCDN.GOB.AR TURNS AWAY A CLIENT WHOSE QUERY HANGS. On 9 October 2026
it stopped accepting connections from the laptop four times, for ten to
forty minutes, each time straight after a request that hung past a minute
(the 5 MB CSV download, aggregate and wide sorted SQL queries, an OFFSET
page), while a GitHub runner was answered throughout. A plain query for
one month of the register answered at once. So: one calendar month per
request, no ORDER BY and no OFFSET, at most DATOS_MAX_REQUESTS a run, one
every DATOS_THROTTLE_S seconds, and the first refusal ends the pull for the
run (a gap; the next run starts again). The weekly re-reads the last 45 days
(two or three months) and then walks the backfill one month further back
per spare request, newest first, until FIRST_PROYECTOS_DATE.

CLASSIFICATION. The English taxonomy is blind to Spanish (docs/germany-scope.md
made the same finding for German). Until Christopher approves a Spanish term
list and config/taxonomy-es.yaml is generated, the only areas stored are
config/watchlist-ar.yaml's, applied by expediente key. When that file exists
it is used automatically, and `--reclassify` re-derives every stored row.
Text is folded (accents and n-tilde removed) before matching, because HCDN
prints older titles in capitals without accents; the Spanish terms are
therefore written unaccented.

Separation guarantee: writes ar_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import html as htmllib
import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ar_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "ar-rollcalls"
TAXONOMY_ES = os.path.join(ROOT, "config", "taxonomy-es.yaml")

SENADO = "https://www.senado.gob.ar"
ACTAS = SENADO + "/votaciones/actas"
ACTA_DETAIL = SENADO + "/votaciones/detalleActa/{0}"
ACTA_PDF = SENADO + "/votaciones/verActaVotacion/{0}"
VER_EXP = SENADO + "/parlamentario/comisiones/verExp/{0}.{1:02d}/{2}/{3}"
SENATORS = SENADO + "/micrositios/DatosAbiertos/ExportarListadoSenadores/json"
SENATORS_HIST = SENADO + "/micrositios/DatosAbiertos/ExportarListadoSenadoresHistorico/json"

DATOS = "https://datos.hcdn.gob.ar/api/3/action/datastore_search_sql"
PROYECTOS_RES = "22b2d52c-7a0e-426b-ac0a-a3326c388ba6"   # Proyectos Parlamentarios
DIPUTADOS_RES = "169de2eb-465f-4007-a4c2-39a5ba4c0df3"   # Diputados, one row per bloc spell
DATOS_WINDOW_CAP = 5000     # rows; a month is about 650, so hitting this is a gap
DATOS_THROTTLE_S = 20.0
DATOS_MAX_REQUESTS = 8      # per run, members included; see the docstring
SENADO_THROTTLE_S = 1.0
VOTACIONES_HCDN = "https://votaciones.hcdn.gob.ar/"

# The parliamentary year runs 1 March to 28 February. The weekly re-reads the
# register from this many days back: HCDN publishes a Trámite Parlamentario
# a few days after entry and occasionally back-dates a correction.
PROYECTOS_LOOKBACK_DAYS = 45
FIRST_PROYECTOS_DATE = "2024-03-01"     # period 142, the start of phase 1's window

BUDGET_S = drain.DEFAULT_S
GAPS_EXIT = 3          # stored what it could, recorded gaps: jobs/ar-weekly.sh publishes
EXP_REPAIR_LIMIT = 25  # Senate expediente pages re-asked per run after a refusal
HIDDEN_AREAS = (11,)   # migration is collated, never campaigned (src/partner.py)

COUNT_WORDS = {"AFIRMATIVOS": "ayes", "NEGATIVOS": "noes", "ABSTENCIONES": "abstentions",
               "AUSENTES": "absent"}


def _squash(text):
    return re.sub(r"\s+", " ", text or "").strip() or None


def _text(fragment):
    return _squash(htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment or ""))) or ""


def _name_key(name):
    return " ".join(ar_store.fold(name).upper().replace(",", " , ").split())


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def full_year(yy):
    yy = int(yy)
    return yy if yy >= 1000 else (1900 + yy if yy >= 80 else 2000 + yy)


# --- keys ----------------------------------------------------------------------

def dip_key(exp):
    """'5346-D-2026' (HCDN's own form, zero-padded or not) -> 'dip/5346-D-2026'."""
    hit = re.match(r"^\s*0*(\d+)-([A-Z]+)-(\d{2,4})\s*$", exp or "")
    if not hit:
        return None
    return "dip/{0}-{1}-{2}".format(int(hit.group(1)), hit.group(2), full_year(hit.group(3)))


def sen_key(number, origin, year):
    return "sen/{0}-{1}-{2}".format(int(number), origin.upper(), full_year(year))


def parse_ver_exp_href(href):
    """'/parlamentario/comisiones/verExp/159.25/PE/PL' -> ('sen/159-PE-2025', 159, 'PE', 2025, 'PL')."""
    hit = re.search(r"verExp/(\d+)\.(\d+)/([A-Za-z]+)/([A-Za-z]+)", href or "")
    if not hit:
        return None
    n, yy, origin, tipo = hit.groups()
    return sen_key(n, origin, yy), int(n), origin.upper(), full_year(yy), tipo.upper()


def parse_hcd_crossref(text):
    """'Exp. HCD: 10-PE-24 Y OTROS OD 4' -> 'dip/10-PE-2024' (the first number)."""
    hit = re.search(r"Exp\.\s*HCD:\s*0*(\d+)-([A-Z]+)-(\d{2,4})", text or "")
    return "dip/{0}-{1}-{2}".format(int(hit.group(1)), hit.group(2), full_year(hit.group(3))) if hit else None


# --- Senate: the listing of actas ----------------------------------------------

def parse_actas(page):
    """The year's listing -> list of dicts, one per acta row."""
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 7:
            continue
        date_hit = re.search(r"display:none\">\s*(\d{8})\s*<", cells[0])
        if not date_hit:
            continue
        d = date_hit.group(1)
        title_cell = cells[2]
        title = _text(re.split(r"<a onclick=\"mostrar", title_cell)[0])
        exps, seen = [], set()
        for href in re.findall(r"href=\"(/parlamentario/comisiones/verExp/[^\"]+)\"", title_cell):
            parsed = parse_ver_exp_href(href)
            if parsed and parsed[0] not in seen:
                seen.add(parsed[0])
                exps.append(parsed)
        orders = ["OD-{1}/{0}".format(*o) for o in
                  re.findall(r"ordenDelDiaResultadoLink/(\d{4})/(\d+)", title_cell)]
        result = _text(re.sub(r"<span[^>]*display:none[^>]*>.*?</span>", " ", cells[4], flags=re.S))
        detail = re.search(r"detalleActa/(\d+)", row)
        pdf = re.search(r"verActaVotacion/(\d+)", row)
        acta_id = int(detail.group(1)) if detail else (int(pdf.group(1)) if pdf else None)
        try:
            number = int(_text(cells[1]))
        except ValueError:
            number = None
        date = "{0}-{1}-{2}".format(d[:4], d[4:6], d[6:])
        out.append({
            "date": date, "number": number, "title": title, "exps": exps, "orders": orders,
            "vote_type": _text(cells[3]) or None, "result": result or None,
            "majority": _text(cells[6]) or None, "acta_id": acta_id,
            "has_detail": bool(detail),
            "key": "sen-acta-{0}".format(acta_id) if acta_id else "sen-{0}-{1}".format(date, number),
        })
    return out


# --- Senate: one acta's detail page --------------------------------------------

def parse_acta_detail(page):
    """-> {'time', 'counts': {...}, 'votes': [{'id', 'name', 'bloc', 'province', 'position'}]}."""
    head = page.split("<tbody", 1)[0]
    flat = _text(head)
    time_hit = re.search(r"\d{2}/\d{2}/\d{4}\s*-\s*(\d{1,2}:\d{2})", flat)
    counts = {}
    for n, word in re.findall(r"(\d+)\s+(AFIRMATIVOS|NEGATIVOS|ABSTENCIONES|AUSENTES)\b", flat):
        counts.setdefault(COUNT_WORDS[word], int(n))
    votes = []
    body = page.split("<tbody", 1)[1] if "<tbody" in page else ""
    body = body.split("</tbody>", 1)[0]
    for row in re.findall(r"<tr>(.*?)</tr>", body, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 5:
            continue
        link = re.search(r"/senadores/senador/(\d+)", cells[0])
        votes.append({"id": link.group(1) if link else None, "name": _text(cells[1]),
                      "bloc": _text(cells[2]) or None, "province": _text(cells[3]) or None,
                      "position": _text(cells[4]) or None})
    return {"time": time_hit.group(1) if time_hit else None, "counts": counts, "votes": votes}


def parse_ver_exp(page):
    """An expediente page -> {'title', 'origin_name', 'tipo_name', 'exp_other', 'law'}."""
    flat = _text(re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S))
    title = origin = tipo = None
    # The summary table: N°, Origen, Tipo, Extracto. Its cells are never
    # closed (<td>...<td>...), so split on the opening tags.
    table = re.search(r"<th>\s*Extracto\s*</th>.*?<tbody>(.*?)</tbody>", page, re.S)
    if table:
        cells = [_text(c) for c in re.split(r"<td[^>]*>", table.group(1))[1:]]
        if len(cells) >= 4:
            origin, tipo, title = cells[1] or None, cells[2] or None, cells[3] or None
    law = re.search(r"NUMERO DE LEY:\s*(\d+)", flat)
    return {"title": _squash(title), "origin_name": origin, "tipo_name": tipo,
            "exp_other": parse_hcd_crossref(flat),
            "law": "Ley {0}".format(law.group(1)) if law else None}


# --- classification ------------------------------------------------------------

def load_terms(path=None):
    """The Spanish taxonomy if it has been generated, else an empty one: the
    English file would only produce false comfort (see the module docstring)."""
    path = path or TAXONOMY_ES
    if os.path.exists(path):
        return filt.load_taxonomy(path)
    return filt.Taxonomy(version="none", terms={}, exclusions=set())


def empty_watchlist():
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify_bill(tax, wl, exp_key, title, wl_path=None):
    text = ar_store.fold(title or "")
    res = filt.filter_item(tax, wl, text, title=text)
    return ar_store.add_watch_areas(res, exp_key, wl_path)


def classify_division(tax, wl, title, bill_areas):
    """(own FilterResult, combined areas)."""
    text = ar_store.fold(title or "")
    own = filt.filter_item(tax, wl, text, title=text)
    combined = set(own.issue_areas or [])
    for areas in bill_areas:
        combined |= set(areas or [])
    return own, sorted(combined)


def _bill_areas(conn, keys):
    out = []
    for k in keys or []:
        row = conn.execute("SELECT areas FROM ar_bills WHERE exp_key=?", (k,)).fetchone()
        out.append(json.loads(row[0] or "[]") if row else [])
    return out


# --- storing -------------------------------------------------------------------

def store_bill(conn, tax, wl, rec, today, wl_path=None):
    res = classify_bill(tax, wl, rec["exp_key"], rec.get("title"), wl_path)
    conn.execute(
        "INSERT INTO ar_bills (exp_key, chamber, number, origin, year, tipo, title, author, "
        "published, publication, proyecto_id, exp_other, law, areas, matched_terms, tier, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(exp_key) DO UPDATE SET "
        "tipo=COALESCE(excluded.tipo, ar_bills.tipo), title=COALESCE(excluded.title, ar_bills.title), "
        "author=COALESCE(excluded.author, ar_bills.author), "
        "published=COALESCE(excluded.published, ar_bills.published), "
        "publication=COALESCE(excluded.publication, ar_bills.publication), "
        "proyecto_id=COALESCE(excluded.proyecto_id, ar_bills.proyecto_id), "
        "exp_other=COALESCE(excluded.exp_other, ar_bills.exp_other), "
        "law=COALESCE(excluded.law, ar_bills.law), areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (rec["exp_key"], rec["chamber"], rec.get("number"), rec.get("origin"), rec.get("year"),
         rec.get("tipo"), rec.get("title"), rec.get("author"), rec.get("published"),
         rec.get("publication"), rec.get("proyecto_id"), rec.get("exp_other"), rec.get("law"),
         ar_store.dumps(res.issue_areas),
         ar_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
         res.tier, today, today))
    return res


def store_member(conn, key, chamber, today, name=None, bloc=None, province=None, alliance=None,
                 term_start=None, term_end=None, current=None, as_of=None):
    """Latest-wins on the descriptive fields, but only from a fact at least as
    new as the one stored (a 2024 acta must not overwrite a 2026 bloc)."""
    as_of = as_of or today
    newer = "COALESCE(excluded.as_of, '') >= COALESCE(ar_members.as_of, '')"
    conn.execute(
        "INSERT INTO ar_members (member_key, chamber, name, bloc, province, alliance, term_start, "
        "term_end, current, as_of, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(member_key) DO UPDATE SET "
        "name=CASE WHEN {n} THEN COALESCE(excluded.name, ar_members.name) ELSE ar_members.name END, "
        "bloc=CASE WHEN {n} THEN COALESCE(excluded.bloc, ar_members.bloc) ELSE ar_members.bloc END, "
        "province=COALESCE(ar_members.province, excluded.province), "
        "alliance=COALESCE(excluded.alliance, ar_members.alliance), "
        "term_start=COALESCE(excluded.term_start, ar_members.term_start), "
        "term_end=COALESCE(excluded.term_end, ar_members.term_end), "
        "current=COALESCE(excluded.current, ar_members.current), "
        "as_of=CASE WHEN {n} THEN excluded.as_of ELSE ar_members.as_of END, "
        "last_seen=excluded.last_seen".format(n=newer),
        (key, chamber, name, bloc, province, alliance, term_start, term_end, current, as_of,
         today, today))


def store_division(conn, a, detail, tax, wl, today, resolve=None):
    """Returns (areas, dropped names). A position whose senator cannot be
    identified is dropped and reported, never stored under a guessed ID."""
    keys = [e[0] for e in a["exps"]]
    own, areas = classify_division(tax, wl, a["title"], _bill_areas(conn, keys))
    counts = (detail or {}).get("counts") or {}
    url = ACTA_DETAIL.format(a["acta_id"]) if a["has_detail"] else (
        ACTA_PDF.format(a["acta_id"]) if a["acta_id"] else ACTAS)
    conn.execute(
        "INSERT INTO ar_divisions (division_key, chamber, acta_id, date, time, acta_number, title, "
        "vote_type, result, majority, exp_keys, orders, ayes, noes, abstentions, absent, has_detail, "
        "own_areas, areas, matched_terms, tier, source_url, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET time=COALESCE(excluded.time, ar_divisions.time), "
        "title=excluded.title, vote_type=excluded.vote_type, result=excluded.result, "
        "majority=excluded.majority, exp_keys=excluded.exp_keys, orders=excluded.orders, "
        "ayes=COALESCE(excluded.ayes, ar_divisions.ayes), noes=COALESCE(excluded.noes, ar_divisions.noes), "
        "abstentions=COALESCE(excluded.abstentions, ar_divisions.abstentions), "
        "absent=COALESCE(excluded.absent, ar_divisions.absent), "
        "has_detail=MAX(excluded.has_detail, ar_divisions.has_detail), "
        "own_areas=excluded.own_areas, areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, source_url=excluded.source_url, last_seen=excluded.last_seen",
        (a["key"], "senado", a["acta_id"], a["date"], (detail or {}).get("time"), a["number"],
         a["title"], a["vote_type"], a["result"], a["majority"], ar_store.dumps(keys),
         ar_store.dumps(a["orders"]), counts.get("ayes"), counts.get("noes"),
         counts.get("abstentions"), counts.get("absent"), int(bool(detail)),
         ar_store.dumps(own.issue_areas), ar_store.dumps(areas),
         ar_store.dumps(own.matched_terms), own.tier, url, today, today))
    dropped = []
    for v in (detail or {}).get("votes") or []:
        sid = v["id"] or (resolve(v["name"], a["date"]) if resolve else None)
        if not sid:
            dropped.append(v["name"] or "?")
            continue
        key = "sen/" + sid
        store_member(conn, key, "senado", today, name=v["name"], bloc=v["bloc"],
                     province=v["province"], as_of=a["date"])
        conn.execute("INSERT OR REPLACE INTO ar_votes (division_key, member_key, position, bloc, "
                     "province) VALUES (?,?,?,?,?)",
                     (a["key"], key, v["position"], v["bloc"], v["province"]))
    return areas, dropped


# --- Senate: members -------------------------------------------------------------

def parse_senators(raw):
    rows = json.loads(raw)["table"]["rows"]
    out = []
    for r in rows:
        name = "{0}, {1}".format((r.get("APELLIDO") or "").strip(), (r.get("NOMBRE") or "").strip())
        out.append({"id": str(r["ID"]).strip(), "name": name, "bloc": _squash(r.get("BLOQUE")),
                    "province": _squash(r.get("PROVINCIA")),
                    "alliance": _squash(r.get("PARTIDO O ALIANZA")),
                    "start": r.get("D_REAL") or r.get("D_LEGAL"), "end": r.get("C_LEGAL")})
    return out


def pull_senators(conn, client, today):
    senators = parse_senators(client.get_bytes(SENATORS, FEED, "senadores").decode("utf-8"))
    if len(senators) < 60:
        raise ValueError("the Senate roster listed {0} senators, expected 72".format(len(senators)))
    conn.execute("UPDATE ar_members SET current=0 WHERE chamber='senado'")
    for s in senators:
        store_member(conn, "sen/" + s["id"], "senado", today, name=s["name"], bloc=s["bloc"],
                     province=s["province"], alliance=s["alliance"], term_start=s["start"],
                     term_end=s["end"], current=1)
    conn.commit()
    return len(senators)


class HistoricRoster:
    """Name -> Senate ID for senators printed without a link (former members).
    Fetched once, only when such a name appears. A name with several IDs is
    narrowed by the term that covers the vote's date; still ambiguous, it is
    refused."""

    def __init__(self, client=None, raw=None):
        self.client = client
        self._rows = None if raw is None else json.loads(raw)["table"]["rows"]
        self.failed = None

    def rows(self):
        if self._rows is None and self.failed is None:
            try:
                raw = self.client.get_bytes(SENATORS_HIST, FEED, "senadores-historico")
                self._rows = json.loads(raw.decode("utf-8"))["table"]["rows"]
            except (FetchError, ValueError, KeyError) as exc:
                self.failed = str(exc)
                self._rows = []
        return self._rows or []

    def __call__(self, name, date):
        key = _name_key(name)
        hits = [r for r in self.rows() if _name_key(r.get("SENADOR")) == key]
        ids = {str(r["ID"]).strip() for r in hits}
        if len(ids) > 1:
            hits = [r for r in hits if (r.get("INICIO PERIODO REAL") or "") <= date
                    <= (r.get("CESE PERIODO REAL") or "9999")]
            ids = {str(r["ID"]).strip() for r in hits}
        return ids.pop() if len(ids) == 1 else None


# --- Senate: actas ---------------------------------------------------------------

def fetch_senate_expediente(conn, client, today, tax, wl, exp_key, number, origin, eyear, tipo,
                            log=print, wl_path=None):
    """Read one expediente page and store it. Stored even when refused (with
    no title), so the acta's link resolves and the repair pass finds it.
    Returns False on a refusal (a gap is recorded)."""
    ok = True
    try:
        exp = parse_ver_exp(client.get_text(
            VER_EXP.format(number, eyear % 100, origin, tipo), FEED,
            "senado-exp-{0}-{1}-{2}".format(origin, number, eyear)))
    except FetchError as exc:
        _gap(conn, today, "senado expediente {0}: {1}".format(exp_key, exc))
        log("  [gap] expediente {0}: {1}".format(exp_key, str(exc)[:70]))
        exp, ok = {}, False
    store_bill(conn, tax, wl, {"exp_key": exp_key, "chamber": "senado", "number": number,
                               "origin": origin, "year": eyear, "tipo": tipo,
                               "title": exp.get("title"), "exp_other": exp.get("exp_other"),
                               "law": exp.get("law")}, today, wl_path)
    return ok


def pull_senate(conn, client, today, years, tax, wl, log=print, budget=None, wl_path=None,
                limit=None):
    stats = {"listed": 0, "new": 0, "ours": 0, "gaps": 0, "votes": 0, "dropped": 0,
             "expedientes": 0}
    resolve = HistoricRoster(client)
    have = {k: d for k, d in conn.execute("SELECT division_key, has_detail FROM ar_divisions "
                                          "WHERE chamber='senado'")}
    fetched_exps = set()
    done = 0
    # Repair first: an expediente whose page was refused on an earlier run is
    # stored with no title, and no new acta may ever name it again.
    for exp_key, number, origin, eyear, tipo in conn.execute(
            "SELECT exp_key, number, origin, year, tipo FROM ar_bills WHERE chamber='senado' "
            "AND title IS NULL AND number IS NOT NULL LIMIT ?", (EXP_REPAIR_LIMIT,)).fetchall():
        fetched_exps.add(exp_key)
        if not fetch_senate_expediente(conn, client, today, tax, wl, exp_key, number, origin,
                                       eyear, tipo, log, wl_path):
            stats["gaps"] += 1
        stats["expedientes"] += 1
    for year in years:
        try:
            page = client.post_form(ACTAS, {"busqueda_actas[anio]": str(year),
                                            "busqueda_actas[titulo]": ""},
                                    FEED, "senado-actas-{0}".format(year), archive=True)
        except FetchError as exc:
            _gap(conn, today, "senado actas {0}: {1}".format(year, exc))
            log("  [gap] senado actas {0}: {1}".format(year, str(exc)[:80]))
            stats["gaps"] += 1
            continue
        actas = parse_actas(page)
        stats["listed"] += len(actas)
        if not actas and "detalleActa" in page:
            _gap(conn, today, "senado actas {0}: listing changed shape".format(year))
            log("  [gap] senado actas {0}: rows present but none parsed".format(year))
            stats["gaps"] += 1
        for a in actas:
            if a["key"] in have and (have[a["key"]] or not a["has_detail"]):
                continue                      # a vote is final: read once
            if budget is not None and budget.exhausted():
                log(budget.disclose("actas", done))
                return stats
            if limit is not None and done >= limit:
                return stats
            for exp_key, number, origin, eyear, tipo in a["exps"]:
                if exp_key in fetched_exps:
                    continue
                row = conn.execute("SELECT title FROM ar_bills WHERE exp_key=?", (exp_key,)).fetchone()
                if row and row[0]:
                    continue
                fetched_exps.add(exp_key)
                if not fetch_senate_expediente(conn, client, today, tax, wl, exp_key, number, origin,
                                               eyear, tipo, log, wl_path):
                    stats["gaps"] += 1
                stats["expedientes"] += 1
            detail = None
            if a["has_detail"]:
                try:
                    detail = parse_acta_detail(client.get_text(
                        ACTA_DETAIL.format(a["acta_id"]), FEED, "senado-acta-{0}".format(a["acta_id"])))
                except FetchError as exc:
                    _gap(conn, today, "senado acta {0}: {1}".format(a["acta_id"], exc))
                    log("  [gap] acta {0}: {1}".format(a["acta_id"], str(exc)[:70]))
                    stats["gaps"] += 1
                    continue                  # not stored: the next run tries again
                if not detail["votes"]:
                    _gap(conn, today, "senado acta {0}: no positions parsed".format(a["acta_id"]))
                    log("  [gap] acta {0}: no positions parsed".format(a["acta_id"]))
                    stats["gaps"] += 1
                    continue
            areas, dropped = store_division(conn, a, detail, tax, wl, today, resolve=resolve)
            if dropped:
                _gap(conn, today, "senado acta {0}: {1} position(s) with no identifiable senator: "
                     "{2}".format(a["acta_id"], len(dropped), "; ".join(dropped[:5])))
                log("  [gap] acta {0}: {1} unidentified senator(s)".format(a["acta_id"], len(dropped)))
                stats["gaps"] += 1
                stats["dropped"] += len(dropped)
            stats["new"] += 1
            stats["ours"] += on_our_ground(areas)
            stats["votes"] += len((detail or {}).get("votes") or []) - len(dropped)
            done += 1
            conn.commit()
    if resolve.failed:
        log("  historic roster unavailable: {0}".format(resolve.failed[:80]))
    return stats


# --- Diputados: the register and the members (datos.hcdn.gob.ar) ----------------

def _sql_url(sql):
    return DATOS + "?" + urllib.parse.urlencode({"sql": sql})


def proyectos_sql(start, end):
    """One calendar window of the register: a plain filter, no ORDER BY and
    no OFFSET (see the docstring: a query that hangs gets the client
    turned away)."""
    return ('SELECT "PROYECTO_ID","TITULO","PUBLICACION_FECHA","PUBLICACION_ID","CAMARA_ORIGEN",'
            '"EXP_DIPUTADOS","EXP_SENADO","TIPO","AUTOR" FROM "{0}" WHERE "PUBLICACION_FECHA" >= '
            "'{1}' AND \"PUBLICACION_FECHA\" < '{2}' LIMIT {3}".format(
                PROYECTOS_RES, start, end, DATOS_WINDOW_CAP))


def _month_start(d):
    return d.replace(day=1)


def _next_month(d):
    return (d.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)


def register_windows(today, newest=None, oldest=None, first=FIRST_PROYECTOS_DATE,
                     lookback=PROYECTOS_LOOKBACK_DAYS):
    """The month windows a run should read, in order: the refresh (the last
    `lookback` days before the newest stored date, newest month first), then
    the backfill (every month before the oldest stored one, back to `first`,
    newest first). With nothing stored it is all backfill, from this month."""
    t = datetime.date.fromisoformat(today)
    floor = _month_start(datetime.date.fromisoformat(first))
    out = []
    if newest:
        since = datetime.date.fromisoformat(newest) - datetime.timedelta(days=lookback)
        m = _month_start(t)
        while m >= _month_start(since):
            out.append((max(m, since).isoformat(), _next_month(m).isoformat()))
            m = _month_start(m - datetime.timedelta(days=1))
        # The oldest stored month is read again whole (a run that stopped
        # mid-backfill may have read only its end), unless it is the floor:
        # then the backfill is done.
        m = _month_start(datetime.date.fromisoformat(oldest or first))
        if m <= floor:
            return out
    else:
        m = _month_start(t)
    while m >= floor:
        if (m.isoformat(), _next_month(m).isoformat()) not in out:
            out.append((m.isoformat(), _next_month(m).isoformat()))
        m = _month_start(m - datetime.timedelta(days=1))
    return out


def proyecto_record(r):
    """A register row -> an ar_bills record keyed on the Diputados number.
    Rows with no Diputados number (none seen, but the column allows it) are
    skipped by the caller."""
    key = dip_key(r.get("EXP_DIPUTADOS"))
    if not key:
        return None
    n, origin, year = key[4:].split("-")
    sen = r.get("EXP_SENADO") or ""
    hit = re.match(r"^\s*0*(\d+)-([A-Z]+)-(\d{2,4})\s*$", sen)
    return {"exp_key": key, "chamber": "diputados", "number": int(n), "origin": origin,
            "year": int(year), "tipo": _squash(r.get("TIPO")),
            # The register carries HTML entities in some titles ("20&deg; ANIVERSARIO").
            "title": _squash(htmllib.unescape(r.get("TITULO") or "")),
            "author": _squash(htmllib.unescape(r.get("AUTOR") or "")), "published": (r.get("PUBLICACION_FECHA") or "")[:10] or None,
            "publication": r.get("PUBLICACION_ID") or None, "proyecto_id": r.get("PROYECTO_ID") or None,
            "exp_other": sen_key(*hit.groups()) if hit else None}


def pull_proyectos(conn, client, today, tax, wl, since=None, log=print, wl_path=None,
                   budget=None, max_requests=DATOS_MAX_REQUESTS):
    """The register, a calendar month per request (register_windows). Stops
    at the first refusal (one gap) or quietly at `max_requests`, saying so.
    `since` forces a re-read from that date instead. Returns (rows, on our
    ground, gaps)."""
    if since:
        windows = register_windows(today, newest=today, oldest=FIRST_PROYECTOS_DATE, lookback=(
            datetime.date.fromisoformat(today) - datetime.date.fromisoformat(since)).days)
    else:
        newest, oldest = conn.execute("SELECT MAX(published), MIN(published) FROM ar_bills "
                                      "WHERE chamber='diputados'").fetchone()
        windows = register_windows(today, newest=newest, oldest=oldest)
    rows, ours = 0, 0
    for asked, (start, end) in enumerate(windows):
        if asked >= max_requests or (budget is not None and budget.exhausted()):
            log("  register: stopped after {0} month(s), {1} left (the host's ration); "
                "they are read on later runs -- disclosed, not silent".format(asked, len(windows) - asked))
            return rows, ours, 0
        try:
            payload = client.get_json(_sql_url(proyectos_sql(start, end)), FEED,
                                      "hcdn-proyectos-{0}".format(start))
            recs = payload["result"]["records"]
        except (FetchError, KeyError, TypeError, ValueError) as exc:
            _gap(conn, today, "hcdn proyectos {0} to {1}: {2}".format(start, end, exc))
            conn.commit()
            log("  [gap] hcdn proyectos {0}: {1}".format(start, str(exc)[:80]))
            return rows, ours, 1
        if len(recs) >= DATOS_WINDOW_CAP:
            _gap(conn, today, "hcdn proyectos {0}: {1} rows, the window cap; some may be "
                 "missing".format(start, len(recs)))
            log("  [gap] hcdn proyectos {0}: hit the window cap".format(start))
            return rows, ours, 1
        for r in recs:
            rec = proyecto_record(r)
            if not rec:
                continue
            res = store_bill(conn, tax, wl, rec, today, wl_path)
            rows += 1
            ours += on_our_ground(res.issue_areas)
        conn.commit()
    return rows, ours, 0


def diputados_sql(today):
    return ('SELECT "ID","APELLIDO","NOMBRE","DISTRITO","INICIO","FIN","BLOQUE","BLOQUE_INICIO",'
            '"BLOQUE_FIN" FROM "{0}" WHERE "FIN" >= \'{1}\' LIMIT 2000'.format(DIPUTADOS_RES, today))


def pull_diputados(conn, client, today):
    """The sitting chamber: every spell whose mandate is open today. A member
    is current when one of their bloc spells is open."""
    recs = client.get_json(_sql_url(diputados_sql(today)), FEED, "hcdn-diputados")["result"]["records"]
    current = {}
    for r in recs:
        if (r.get("BLOQUE_FIN") or "9999") < today or (r.get("BLOQUE_INICIO") or "") > today:
            continue
        current[r["ID"]] = r
    if len(current) < 200:
        raise ValueError("HCDN listed {0} sitting diputados, expected 257".format(len(current)))
    conn.execute("UPDATE ar_members SET current=0 WHERE chamber='diputados'")
    for hid, r in current.items():
        store_member(conn, "dip/" + hid, "diputados", today,
                     name="{0}, {1}".format(r["APELLIDO"].strip(), r["NOMBRE"].strip()),
                     bloc=_squash(r.get("BLOQUE")), province=_squash(r.get("DISTRITO")),
                     term_start=(r.get("INICIO") or "")[:10] or None,
                     term_end=(r.get("FIN") or "")[:10] or None, current=1)
    conn.commit()
    return len(current)


def knock_votaciones(client, log=print):
    """One short request to the Diputados roll-call site. Never a gap."""
    try:
        client._opener.open(  # noqa: SLF001 -- a probe, deliberately outside the retry ladder
            __import__("urllib.request").request.Request(
                VOTACIONES_HCDN, headers={"User-Agent": client.user_agent}), timeout=20).read(2048)
    except Exception as exc:  # noqa: BLE001 -- any refusal is the known state
        log("ar-rollcalls: votaciones.hcdn.gob.ar still unreachable ({0}); Diputados roll calls "
            "not collected (known, see docs/argentina-scope.md)".format(type(exc).__name__))
        return False
    log("ar-rollcalls: VOTACIONES.HCDN.GOB.AR ANSWERED. The Diputados roll-call collector can "
        "now be built: tell Christopher.")
    return True


# --- offline ---------------------------------------------------------------------

def reclassify(conn, tax=None, log=print, wl_path=None):
    """Re-derive expediente areas, then division areas. Bills first: divisions
    inherit from them."""
    tax = tax if tax is not None else load_terms()
    wl = empty_watchlist()
    changed_b = changed_d = 0
    for key, title, areas in conn.execute("SELECT exp_key, title, areas FROM ar_bills").fetchall():
        res = classify_bill(tax, wl, key, title, wl_path)
        new = ar_store.dumps(res.issue_areas)
        changed_b += new != (areas or "[]")
        conn.execute("UPDATE ar_bills SET areas=?, matched_terms=?, tier=? WHERE exp_key=?",
                     (new, ar_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, key))
    for key, title, exps, areas in conn.execute(
            "SELECT division_key, title, exp_keys, areas FROM ar_divisions").fetchall():
        own, combined = classify_division(tax, wl, title, _bill_areas(conn, json.loads(exps or "[]")))
        new = ar_store.dumps(combined)
        changed_d += new != (areas or "[]")
        conn.execute("UPDATE ar_divisions SET own_areas=?, areas=?, matched_terms=?, tier=? "
                     "WHERE division_key=?",
                     (ar_store.dumps(own.issue_areas), new, ar_store.dumps(own.matched_terms),
                      own.tier, key))
    conn.commit()
    log("ar-rollcalls: reclassified (terms: {0}); {1} expediente(s) and {2} division(s) "
        "changed area".format(tax.version, changed_b, changed_d))
    return changed_b, changed_d


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = lambda t: sum(on_our_ground(json.loads(a or "[]"))  # noqa: E731
                         for (a,) in conn.execute("SELECT areas FROM {0}".format(t)))
    log("  store: {0} expediente(s) ({1} Diputados, {2} Senate), {3} on our ground; "
        "{4} Senate division(s), {5} on our ground; {6} member(s) ({7} sitting), "
        "{8} position(s)".format(
            n("SELECT COUNT(*) FROM ar_bills"),
            n("SELECT COUNT(*) FROM ar_bills WHERE chamber='diputados'"),
            n("SELECT COUNT(*) FROM ar_bills WHERE chamber='senado'"), ours("ar_bills"),
            n("SELECT COUNT(*) FROM ar_divisions"), ours("ar_divisions"),
            n("SELECT COUNT(*) FROM ar_members"),
            n("SELECT COUNT(*) FROM ar_members WHERE current=1"),
            n("SELECT COUNT(*) FROM ar_votes")))


def make_client(raw_dir=None):
    client = HttpClient(raw_dir=raw_dir or os.path.join(ROOT, "data", "raw"), max_retries=1)
    client.set_host_throttle("datos.hcdn.gob.ar", DATOS_THROTTLE_S)
    client.set_host_throttle("www.senado.gob.ar", SENADO_THROTTLE_S)
    return client


def default_years(today):
    """The Senate listing is by calendar year. In January and February the
    previous year's last sessions may still be landing, so read both."""
    d = datetime.date.fromisoformat(today)
    return [d.year - 1, d.year] if d.month <= 2 else [d.year]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", help="archive raw payloads here instead of data/raw "
                    "(for a scratch run beside --db)")
    ap.add_argument("--years", type=int, nargs="+",
                    help="Senate listing years to read (default: the current one)")
    ap.add_argument("--since", help="read the Diputados register from this date (YYYY-MM-DD)")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--no-senate", action="store_true")
    ap.add_argument("--no-proyectos", action="store_true")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored expedientes and divisions, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--limit", type=int, help="stop after this many new actas")
    ap.add_argument("--dry-run", action="store_true",
                    help="read the current year's Senate listing, store nothing")
    args = ap.parse_args()
    client = make_client(args.raw_dir)
    today = datetime.date.today().isoformat()
    if args.dry_run:
        year = default_years(today)[-1]
        actas = parse_actas(client.post_form(ACTAS, {"busqueda_actas[anio]": str(year),
                                                     "busqueda_actas[titulo]": ""}, FEED, "dry"))
        print("ar-rollcalls: Senate {0}: {1} acta(s) listed, {2} with a detail page, the last on "
              "{3}".format(year, len(actas), sum(a["has_detail"] for a in actas),
                           max((a["date"] for a in actas), default="-")))
        knock_votaciones(client)
        return 0
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn)
        summary(conn)
        conn.close()
        return 0
    tax = load_terms()
    wl = empty_watchlist()
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    if not args.no_members:
        for label, fn in (("senadores", pull_senators), ("diputados", pull_diputados)):
            try:
                count = fn(conn, client, today)
                print("ar-rollcalls: {0} sitting {1}".format(count, label))
            except (FetchError, ValueError, KeyError, TypeError) as exc:
                _gap(conn, today, "members {0}: {1}".format(label, exc))
                conn.commit()
                print("  [gap] members {0}: {1}".format(label, str(exc)[:80]))
                gaps += 1
    if not args.no_proyectos:
        rows, ours, g = pull_proyectos(conn, client, today, tax, wl, since=args.since, budget=budget,
                                       max_requests=DATOS_MAX_REQUESTS - (0 if args.no_members else 1))
        gaps += g
        print("ar-rollcalls: {0} Diputados expediente(s) read, {1} on our ground; {2} gap(s)".format(
            rows, ours, g))
    if not args.no_senate:
        s = pull_senate(conn, client, today, args.years or default_years(today), tax, wl,
                        budget=budget, limit=args.limit)
        gaps += s["gaps"]
        print("ar-rollcalls: Senate: {0} acta(s) listed, {1} new, {2} on our ground; {3} "
              "position(s), {4} dropped as unidentified; {5} expediente(s) read; {6} gap(s)".format(
                  s["listed"], s["new"], s["ours"], s["votes"], s["dropped"], s["expedientes"],
                  s["gaps"]))
    knock_votaciones(client)
    # Divisions inherit from expedientes, and an expediente can gain an area
    # after its division was stored (a watchlist entry): settle both.
    reclassify(conn, tax)
    summary(conn)
    conn.close()
    return GAPS_EXIT if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
