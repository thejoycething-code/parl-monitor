#!/usr/bin/env python3
"""El Salvador, Asamblea Legislativa: recorded plenary votes with every
deputy's position, the committee reports (dictámenes) and correspondence
(piezas) they decide, and the deputies.

    python3 tools/sv_rollcalls.py                    # the current legislature
    python3 tools/sv_rollcalls.py --index-only       # vote list and sessions, no PDFs
    python3 tools/sv_rollcalls.py --reclassify       # re-derive areas, offline
    python3 tools/sv_rollcalls.py --taxonomy x.yaml  # classify with a draft list
    python3 tools/sv_rollcalls.py --db /tmp/sv.db    # anywhere but the store

PHASE 1 (9 October 2026); see docs/el-salvador-scope.md. Every source is the
Asamblea's own public site (www.asamblea.gob.sv, Drupal), keyless, measured
live, answering the honest CitizenGO User-Agent:

  * sesion-plenaria/votaciones-ajax -- THE VOTE LIST, a DataTables
    server-side endpoint (GET, `start`/`length`, newest first): 6,710 votes
    from May 2012, each {documentofk, fecha, no_sesion, legislatura, leyenda}.
    The leyenda is the vote's only label and names no subject:
    "COMISION DE HACIENDA DICTAMEN # 267 FAVORABLE", "PIEZA 2A FS".
  * the vote PDF, sites/default/files/documents/votaciones/<GUID>.pdf
    (about 350 KB, a voting-system export saved from Word): totals, totals
    by party, and every deputy's position under SI / NO / ABST. / No Votado.
    Read with src/sv_pdf.py, stdlib only. NOT archived to data/raw (350 KB
    each, a dozen a week); the GUID URL is the provenance and the parsed
    positions are stored.
  * sesion-plenaria/historico-sesion-ajax -- POST {desde, hasta}: THE
    SESSION ARCHIVE, one day at a time (a fortnight's range timed out at
    74 s). JSON: the day's sessions (GUID, type, number) and the first
    session's documents, including `dicta` (number, committee, result,
    EXPEDIENTE, extract) and `piezas` (order, short title, extract). This is
    where a vote learns what it was about. A day appears in the archive some
    days after the sitting (7 October was not there on 9 October), so a day
    not yet archived is retried, not a gap, until ARCHIVE_GRACE_DAYS pass.
  * sesion-plenaria/get-archivos-ajax -- POST {sesion: GUID}: one session's
    documents, for the second session of a day with two (40 s a call).
  * asamblea/diputados -- the 60 sitting deputies, with GUID and party.

A vote is linked to its item by session and number: "DICTAMEN # 267" in
session 128 is the dictamen numbered 267 among session 128's dictámenes;
"PIEZA 2A FS" is pieza 2A of that session (DT = dispensa de trámite, the
vote to skip committee; FS = fondo de lo solicitado, the vote on the
substance).

CLASSIFICATION waits for a Spanish taxonomy (config/taxonomy-es.yaml, the
shared Spanish list proposed in docs/spain-scope.md and
docs/el-salvador-scope.md, generated only once Christopher approves it).
Until then areas stay NULL and only config/watchlist-sv.yaml, applied by
expediente or pieza KEY, lends areas.

Separation guarantee: writes sv_* tables and the shared gaps table only.
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, sv_pdf, sv_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "sv-rollcalls"
BASE = "https://www.asamblea.gob.sv"
VOTE_LIST = (BASE + "/sesion-plenaria/votaciones-ajax?draw=1&start={start}&length={length}"
             "&order%5B0%5D%5Bcolumn%5D=0&order%5B0%5D%5Bdir%5D=desc"
             "&columns%5B0%5D%5Bdata%5D=fecha&search%5Bvalue%5D=")
DAY_ARCHIVE = BASE + "/sesion-plenaria/historico-sesion-ajax"
SESSION_FILES = BASE + "/sesion-plenaria/get-archivos-ajax"
MEMBERS_PAGE = BASE + "/asamblea/diputados"
DOCS = BASE + "/sites/default/files/documents/{folder}/{fk}.pdf"
TAXONOMY_ES = os.path.join(ROOT, "config", "taxonomy-es.yaml")
# asamblea.gob.sv is one Drupal server for the whole public site, and its
# archive queries are slow (1 to 45 s measured); two seconds between calls.
THROTTLE_S = 2.0
LIST_PAGE = 500
# A sitting day missing from the archive this long after it happened is a
# gap; before that it is simply not filed yet and is retried.
ARCHIVE_GRACE_DAYS = 21
# Days re-read even when archived, in case documents are filed late.
REREAD_DAYS = 14
HIDDEN_AREAS = (11,)   # migration: collated, never campaigned (repo-wide rule)

# --- small helpers ------------------------------------------------------------

def iso(ddmmyyyy):
    """'07/10/2026' or '7/10/2026' -> '2026-10-07'; anything else -> None."""
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})", ddmmyyyy or "")
    if not m:
        return None
    return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), int(m.group(2)), int(m.group(1)))


def fold(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def on_our_ground(areas):
    return bool(set(areas or []) - set(HIDDEN_AREAS))


# --- the vote list ---------------------------------------------------------------

def classify_label(label):
    """(kind, number, stage, committee words) from a vote list label.

    'COMISION DE HACIENDA DICTAMEN # 267 FAVORABLE' -> ('dictamen', 267, None, 'HACIENDA')
    'COM. DE SALUD, ... DICT#13 APROBANDO INFORME'  -> ('dictamen', 13, None, 'SALUD, ...')
    'PIEZA 2A FS', 'Pieza 1A Dispensa de Tramites'  -> ('pieza', 2, 'FS'|'DT', None)
    anything else                                    -> ('other', None, None, None)
    """
    text = fold(label)
    up = text.upper()
    m = re.match(r"PIEZA\s*(\d+)\s*-?\s*A\b\s*(.*)", up)
    if m:
        rest = m.group(2)
        stage = None
        if re.match(r"(DT|DISPENSA)", rest):
            stage = "DT"
        elif re.match(r"(FS|FONDO)", rest):
            stage = "FS"
        return "pieza", int(m.group(1)), stage, None
    m = re.search(r"DICT(?:AMEN|\.)?\s*(?:No\.?|N[º°]|#)?\s*#?\s*(\d+)", up)
    if m:
        committee = re.sub(r"^(COMISION|COMISIÓN|COM\.)\s+(DE\s+)?", "", up[:m.start()]).strip(" ,-")
        return "dictamen", int(m.group(1)), None, committee or None
    return "other", None, None, None


def parse_vote_list(payload):
    """Rows of the DataTables JSON as dicts."""
    out = []
    for r in payload.get("data") or []:
        href = re.search(r"href=['\"]?([^'\"\s>]+)", r.get("leyenda") or "")
        url = href.group(1) if href else None
        if url and url.startswith("/"):
            url = BASE + url
        label = re.sub(r"\.pdf$", "", fold(r.get("leyenda")), flags=re.I).strip()
        kind, number, stage, committee = classify_label(label)
        try:
            session = int(r.get("no_sesion"))
        except (TypeError, ValueError):
            session = None
        out.append({"doc": r.get("documentofk"), "date": iso(r.get("fecha")),
                    "session": session, "legislature": r.get("legislatura"),
                    "label": label, "pdf_url": url, "kind": kind, "number": number,
                    "stage": stage, "committee": committee})
    return out


def total_of(payload):
    try:
        return int(payload.get("recordsTotal"))
    except (TypeError, ValueError):
        return None


# --- the session archive -------------------------------------------------------------

def parse_session_files(archivos):
    """(dictámenes, piezas, resumen_fk, agenda_fk) from one session's `archivos`."""
    archivos = archivos or {}
    dictamenes = []
    for d in archivos.get("dicta") or []:
        try:
            numero = int(d.get("numero_dictamen"))
        except (TypeError, ValueError):
            numero = None
        dictamenes.append({
            "comision_id": str(d.get("id") or ""), "comision": fold(d.get("nombre")),
            "numero": numero, "resultado": fold(d.get("tipo_resultado")),
            "expediente": fold(d.get("expediente")) or None, "extracto": fold(d.get("extracto")),
            "orden": _int(d.get("orden_plenaria")),
            "pdf_url": DOCS.format(folder="dictamenes", fk=d["documentofk"]) if d.get("documentofk") else None})
    piezas = []
    for p in archivos.get("piezas") or []:
        orden = _int(p.get("orden"))
        leyenda = fold(p.get("leyenda"))
        m = re.match(r"(\d+)\s*-?\s*A\b\s*-?\s*(.*)", leyenda)
        if m:
            orden = orden or int(m.group(1))
            leyenda = m.group(2).strip()
        piezas.append({
            "orden": orden, "leyenda": leyenda, "extracto": fold(p.get("extracto")),
            "pdf_url": DOCS.format(folder="correspondencia", fk=p["documentofk"]) if p.get("documentofk") else None})
    first = lambda k: ((archivos.get(k) or [{}])[0] or {}).get("documentofk")  # noqa: E731
    return dictamenes, piezas, first("resum"), first("agenda")


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def session_key(legislature, tipo, numero):
    return "{0}/{1}/{2}".format(legislature, tipo or "Ordinaria", numero)


def dictamen_key(legislature, comision_id, numero):
    return "{0}/{1}/{2}".format(legislature, comision_id, numero)


def pieza_key(legislature, session, orden):
    return "{0}/{1}/{2}A".format(legislature, session, orden)


# --- the vote PDF --------------------------------------------------------------------

def parse_vote_pdf(raw):
    """The vote PDF as a dict, or None when no text could be read.

    {meeting, vote_name, started, totals: {SI, NO, ABST, No Votado},
     groups: {party: [yes, no]}, positions: [(name, party, position)]}

    THREE LAYOUTS in the 2024-2027 legislature alone, measured on
    9 October 2026, all from the same voting system:
      * to mid-2025: labels in Spanish ("Reunión:", "Nombre de Voto:",
        "Resultados de Votos Individuales"), group totals as a party line
        followed by "SI: n" lines, positions grouped by PARTY then position,
        one name a line in mixed case ("Francisco Lira"); the first page is
        an image of the totals with no text;
      * from about July 2025: Spanish labels, but group totals as one row
        a party ("NUEVAS IDEAS<tab>54<tab>0") and positions grouped by
        POSITION, each line "NAME<tab>PARTY" in capitals;
      * from about 2026: the same with English labels ("Meeting:",
        "Vote name:", "Individual Voting Results").
    One parser reads all three: labels in either language, a party set by a
    line that is only a party's name, a position by a header line, and a
    name line's own party suffix winning when it has one. Names are stored
    as printed: the layouts spell the same deputy differently."""
    pages = sv_pdf.pdf_lines(raw)
    lines = [ln for p in pages for ln in p]
    if not lines:
        return None
    out = {"meeting": None, "vote_name": None, "started": None, "totals": {},
           "groups": {}, "positions": []}
    section = None
    party = None
    position = None
    i = 0
    while i < len(lines):
        ln = lines[i]
        cells = [c.strip() for c in ln.split("\t")]
        head = cells[0]
        rest = " ".join(cells[1:]).strip()
        bare = re.sub(r"\s+", " ", ln.replace("\t", " ")).strip()
        if head in ("Meeting:", "Reunión:"):
            out["meeting"] = rest
        elif head in ("Vote name:", "Nombre de Voto:"):
            name = [rest]
            j = i + 1
            while j < len(lines) and not lines[j].startswith(_AFTER_NAME):
                name.append(lines[j].strip())
                j += 1
            out["vote_name"] = " ".join(n for n in name if n)
            i = j
            continue
        elif head in ("Vote start:", "Inicio de los votos:"):
            out["started"] = _iso_ts(rest)
        elif ln.startswith(("Total Voting Results", "Resultados de Votos Totales")):
            section, party, position = "totals", None, None
        elif ln.startswith(("Group Voting Results", "Resultados de Votos en Grupo")):
            section, party, position = "groups", None, None
        elif ln.startswith(("Individual Voting Results", "Resultados de Votos Individuales")):
            section, party, position = "individual", None, None
        elif section == "totals":
            num = next((c for c in cells[1:] if c.isdigit()), None)
            if head in _POS and num is not None:
                out["totals"][_POS[head]] = int(num)
        elif section == "groups":
            nums = [int(c) for c in cells[1:] if c.isdigit()]
            if _is_party(bare) and not nums:
                party = bare
                out["groups"].setdefault(party, [0, 0])
            elif head in _POS and party and nums:
                if _POS[head] in ("SI", "NO"):
                    out["groups"][party][0 if _POS[head] == "SI" else 1] = nums[0]
            elif nums and head not in _POS and not head.lower().startswith("total"):
                out["groups"][head] = nums[:2]
        elif section == "individual":
            if bare in _POS or (head in _POS and len(cells) == 1):
                position = _POS.get(bare) or _POS[head]
            elif _is_party(bare, out["groups"]):
                party, position = bare, None
            elif position and bare not in (".", ""):
                own = next((p for p in _parties(out["groups"]) if bare.upper().endswith(" " + p)), None)
                name = bare[:-len(own)].strip() if own else bare
                out["positions"].append((name, own or party, position))
        i += 1
    if "No Votado" not in out["totals"] and out["positions"]:
        out["totals"]["No Votado"] = sum(1 for p in out["positions"] if p[2] == "No Votado")
    return out


KNOWN_PARTIES = ("NUEVAS IDEAS", "ARENA", "PCN", "PDC", "VAMOS", "FMLN", "GANA",
                 "NUESTRO TIEMPO", "CD")
_POS = {"SI:": "SI", "SÍ:": "SI", "NO:": "NO", "ABST.": "ABST", "ABST:": "ABST",
        "No Votado": "No Votado", "No se Votó": "No Votado", "No se votó": "No Votado"}
_AFTER_NAME = ("Vote subject", "Vote start", "Asunto de votos", "Inicio de los votos", "Reunión",
               "Nombre de Agenda")


def _parties(groups=None):
    return sorted(set(groups or ()) | set(KNOWN_PARTIES), key=len, reverse=True)


def _is_party(text, groups=None):
    return text.upper() in KNOWN_PARTIES or text in (groups or {})


def _iso_ts(text):
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})\s*([ap])?", text or "", re.I)
    if not m:
        return None
    d, mo, y, h, mi, sec = (int(x) for x in m.groups()[:6])
    ampm = (m.group(7) or "").lower()
    if ampm == "p" and h < 12:
        h += 12
    elif ampm == "a" and h == 12:
        h = 0
    return "{0}-{1:02d}-{2:02d}T{3:02d}:{4:02d}:{5:02d}".format(y, mo, d, h, mi, sec)


# --- the members page -----------------------------------------------------------------

def parse_members(page):
    """[{member_id, name, party, department, cargo}] from asamblea/diputados."""
    parties = dict(re.findall(
        r'<input[^>]+id="([0-9A-F-]{36})"[^>]+name="grupo-parlamentario"[^>]*/>\s*'
        r'<label[^>]*>\s*([^<]+?)\s*</label>', page))
    departments = dict(re.findall(
        r'<input[^>]+id="([0-9A-F-]{36})"[^>]+name="departamento"[^>]*/>\s*'
        r'<label[^>]*>\s*([^<]+?)\s*</label>', page))
    out = []
    for m in re.finditer(r'<a\s+id="diputado-([0-9A-F-]{36})"(.*?)</a>', page, re.S):
        block = m.group(2)
        title = re.search(r'title="([^"]+)"', block)
        dept = re.search(r'data-departamento="([^"]*)"', block)
        grp = re.search(r'data-grupo-parlamentario="([^"]*)"', block)
        cargo = re.search(r'diputado-index-cargo[^>]*>\s*([^<]+?)\s*<', block)
        out.append({"member_id": m.group(1),
                    "name": html.unescape(title.group(1)).strip() if title else None,
                    "party": parties.get(grp.group(1)) if grp else None,
                    "department": departments.get(dept.group(1)) if dept else None,
                    "cargo": cargo.group(1) if cargo else None})
    return out


# --- classification ---------------------------------------------------------------

def load_taxonomy(path=None):
    """The Spanish taxonomy, or None while none exists (areas stay NULL)."""
    path = path or TAXONOMY_ES
    return filt.load_taxonomy(path) if os.path.exists(path) else None


def classify(tax, keys, *texts):
    """(areas or None, matched terms, tier) for one item's text plus the
    watchlist entries of its KEYS (expediente, pieza key)."""
    keys = [k for k in keys if k]
    watched = sv_store.watch_areas(*keys)
    hit_keys = [k for k in keys if sv_store.watch_areas(k)]
    if tax is None:
        if watched:
            return watched, ["watch:" + k for k in hit_keys], 2
        return None, [], None
    res = filt.filter_item(tax, filt.Watchlist(entities=[], bill_titles=[], act_shorts=[]),
                           *[t for t in texts if t])
    areas = set(res.issue_areas or [])
    terms = list(res.matched_terms or [])
    tier = res.tier
    if watched:
        areas |= set(watched)
        terms += ["watch:" + k for k in hit_keys]
        tier = tier or 2
    return sorted(areas), terms, tier


# --- storing -----------------------------------------------------------------------

def store_session(conn, legislature, s, resumen_fk, agenda_fk, today):
    key = session_key(legislature, s.get("tipo"), s.get("sesion"))
    conn.execute(
        "INSERT INTO sv_sessions (session_key, legislature, tipo, numero, date, codigo, resumen_url, "
        "agenda_url, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(session_key) DO UPDATE SET date=excluded.date, codigo=excluded.codigo, "
        "resumen_url=COALESCE(excluded.resumen_url, sv_sessions.resumen_url), "
        "agenda_url=COALESCE(excluded.agenda_url, sv_sessions.agenda_url), last_seen=excluded.last_seen",
        (key, legislature, s.get("tipo"), _int(s.get("sesion")), iso(s.get("fecha")), s.get("codigo"),
         DOCS.format(folder="resumen", fk=resumen_fk) if resumen_fk else None,
         DOCS.format(folder="agenda", fk=agenda_fk) if agenda_fk else None, today, today))
    return key


def store_dictamen(conn, legislature, skey, d, tax, today):
    key = dictamen_key(legislature, d["comision_id"], d["numero"])
    areas, terms, tier = classify(tax, [d.get("expediente")], d.get("extracto"))
    conn.execute(
        "INSERT INTO sv_dictamenes (dictamen_key, legislature, comision_id, comision, numero, resultado, "
        "expediente, extracto, session_key, orden_plenaria, pdf_url, areas, matched_terms, tier, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(dictamen_key) DO UPDATE SET comision=excluded.comision, resultado=excluded.resultado, "
        "expediente=excluded.expediente, extracto=excluded.extracto, session_key=excluded.session_key, "
        "orden_plenaria=excluded.orden_plenaria, pdf_url=excluded.pdf_url, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (key, legislature, d["comision_id"], d["comision"], d["numero"], d["resultado"], d["expediente"],
         d["extracto"], skey, d["orden"], d["pdf_url"], None if areas is None else sv_store.dumps(areas),
         sv_store.dumps(terms), tier, today, today))
    return key


def store_pieza(conn, legislature, session_no, skey, p, tax, today):
    key = pieza_key(legislature, session_no, p["orden"])
    areas, terms, tier = classify(tax, [key], p.get("leyenda"), p.get("extracto"))
    conn.execute(
        "INSERT INTO sv_piezas (pieza_key, legislature, session_key, orden, leyenda, extracto, pdf_url, "
        "areas, matched_terms, tier, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(pieza_key) DO UPDATE SET leyenda=excluded.leyenda, extracto=excluded.extracto, "
        "pdf_url=excluded.pdf_url, areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen",
        (key, legislature, skey, p["orden"], p["leyenda"], p["extracto"], p["pdf_url"],
         None if areas is None else sv_store.dumps(areas), sv_store.dumps(terms), tier, today, today))
    return key


def store_division(conn, v, today):
    key = "sv-" + v["doc"]
    conn.execute(
        "INSERT INTO sv_divisions (division_key, legislature, session, date, label, kind, stage, pdf_url, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET session=excluded.session, date=excluded.date, "
        "label=excluded.label, kind=excluded.kind, stage=excluded.stage, pdf_url=excluded.pdf_url, "
        "last_seen=excluded.last_seen",
        (key, v["legislature"], v["session"], v["date"], v["label"], v["kind"], v["stage"],
         v["pdf_url"], today, today))
    return key


def store_positions(conn, key, parsed):
    conn.execute("DELETE FROM sv_votes WHERE division_key=?", (key,))
    conn.executemany("INSERT OR REPLACE INTO sv_votes (division_key, name, party, position) "
                     "VALUES (?,?,?,?)", [(key,) + p for p in parsed["positions"]])
    t = parsed["totals"]
    conn.execute(
        "UPDATE sv_divisions SET meeting=?, vote_name=?, started=?, yes=?, no=?, abstain=?, not_voted=?, "
        "groups=?, positions=? WHERE division_key=?",
        (parsed["meeting"], parsed["vote_name"], parsed["started"], t.get("SI"), t.get("NO"),
         t.get("ABST"), t.get("No Votado"), json.dumps(parsed["groups"], ensure_ascii=False),
         len(parsed["positions"]), key))


def _words(text):
    stop = {"DE", "Y", "LA", "EL", "E", "DEL", "COM", "COMISION", "COMISIÓN", "ESPECIAL", "EN"}
    t = fold(text).upper()
    t = t.translate(str.maketrans("ÁÉÍÓÚÜÑ", "AEIOUUN"))
    return {w for w in re.findall(r"[A-Z]+", t) if w not in stop and len(w) > 2}


def link_divisions(conn):
    """Join votes to the dictamen or pieza they decided, by session and number.
    Returns how many votes gained a link. Areas follow the item."""
    linked = 0
    rows = conn.execute(
        "SELECT division_key, legislature, session, date, label, kind FROM sv_divisions "
        "WHERE item_key IS NULL AND kind IN ('dictamen','pieza')").fetchall()
    for key, leg, session, date, label, kind in rows:
        skeys = [r[0] for r in conn.execute(
            "SELECT session_key FROM sv_sessions WHERE legislature=? AND numero=? AND date=?",
            (leg, session, date))]
        if not skeys:
            continue
        _, number, _, committee = classify_label(label)
        item = expediente = None
        if kind == "dictamen":
            cands = conn.execute(
                "SELECT dictamen_key, comision, expediente FROM sv_dictamenes WHERE numero=? AND session_key IN ({0})"
                .format(",".join("?" * len(skeys))), [number] + skeys).fetchall()
            if len(cands) > 1 and committee:
                want = _words(committee)
                cands = sorted(cands, key=lambda c: -len(want & _words(c[1])))[:1]
            if len(cands) == 1:
                item, expediente = cands[0][0], cands[0][2]
        else:
            cand = conn.execute(
                "SELECT pieza_key FROM sv_piezas WHERE orden=? AND session_key IN ({0})"
                .format(",".join("?" * len(skeys))), [number] + skeys).fetchall()
            if len(cand) == 1:
                item = cand[0][0]
        if item:
            conn.execute("UPDATE sv_divisions SET item_key=?, expediente=? WHERE division_key=?",
                         (item, expediente, key))
            linked += 1
    _division_areas(conn)
    return linked


def _division_areas(conn):
    """A vote's areas are its item's: the label names no subject."""
    conn.execute(
        "UPDATE sv_divisions SET areas=(SELECT areas FROM sv_dictamenes WHERE dictamen_key=item_key), "
        "matched_terms=(SELECT matched_terms FROM sv_dictamenes WHERE dictamen_key=item_key), "
        "tier=(SELECT tier FROM sv_dictamenes WHERE dictamen_key=item_key) WHERE kind='dictamen' AND item_key IS NOT NULL")
    conn.execute(
        "UPDATE sv_divisions SET areas=(SELECT areas FROM sv_piezas WHERE pieza_key=item_key), "
        "matched_terms=(SELECT matched_terms FROM sv_piezas WHERE pieza_key=item_key), "
        "tier=(SELECT tier FROM sv_piezas WHERE pieza_key=item_key) WHERE kind='pieza' AND item_key IS NOT NULL")


# --- pulling -------------------------------------------------------------------------

def pull_vote_list(conn, client, today, legislature=None, log=print, full=False):
    """Read the vote list newest first; store the current legislature's rows.
    Stops at the first page holding a vote already stored (unless `full`).
    Returns the legislature read."""
    start = 0
    seen_old = False
    total = None
    stored = 0
    while True:
        payload = client.get_json(VOTE_LIST.format(start=start, length=LIST_PAGE), FEED,
                                  "votaciones-{0}".format(start))
        total = total_of(payload) if total is None else total
        rows = parse_vote_list(payload)
        if not rows:
            break
        if legislature is None:
            legislature = rows[0]["legislature"]
        for v in rows:
            if v["legislature"] != legislature or not v["doc"]:
                continue
            if conn.execute("SELECT 1 FROM sv_divisions WHERE division_key=?", ("sv-" + v["doc"],)).fetchone():
                seen_old = True
            store_division(conn, v, today)
            stored += 1
        conn.commit()
        past = any(v["legislature"] != legislature for v in rows)
        start += LIST_PAGE
        if past or (seen_old and not full) or len(rows) < LIST_PAGE or (total and start >= total):
            break
    log("  vote list: {0} rows of the {1} legislature read ({2} on the site in all)"
        .format(stored, legislature, total))
    return legislature


def legislature_start(legislature):
    """'2024-2027' -> '2024-05-01': a Salvadoran legislature takes office on
    1 May (Constitution, art. 124)."""
    m = re.match(r"(\d{4})-\d{4}$", legislature or "")
    return "{0}-05-01".format(m.group(1)) if m else None


def days_to_read(conn, today, legislature):
    """Every calendar day of the legislature the archive has not answered
    for, plus the last REREAD_DAYS, newest first. Not only the vote days:
    MEASURED on 9 October 2026, sessions 41 to 64 (late January to mid-July
    2025) and 98 published no recorded vote at all, yet the archive has
    their dictámenes and piezas."""
    today_d = datetime.date.fromisoformat(today)
    reread_from = today_d - datetime.timedelta(days=REREAD_DAYS)
    start = legislature_start(legislature)
    first = datetime.date.fromisoformat(start) if start else reread_from
    done = {r[0]: r[1] for r in conn.execute("SELECT day, archived FROM sv_vote_days")}
    out = []
    d = today_d
    while d >= first:
        iso_d = d.isoformat()
        state = done.get(iso_d)
        if d >= reread_from or state is None or state == 0:
            out.append(iso_d)
        d -= datetime.timedelta(days=1)
    return out


def pull_days(conn, client, today, legislature, tax=None, log=print, budget=None):
    """Ask the session archive about every day of the legislature not yet
    answered, and the last REREAD_DAYS. Returns (days with sessions read, gaps).

    sv_vote_days.archived: 1 answered (sessions may be 0: no sitting);
    0 nothing yet but recent, asked again next run; -1 a day WITH recorded
    votes still missing from the archive after ARCHIVE_GRACE_DAYS (a gap,
    recorded once)."""
    today_d = datetime.date.fromisoformat(today)
    vote_days = {r[0] for r in conn.execute(
        "SELECT DISTINCT date FROM sv_divisions WHERE legislature=?", (legislature,))}
    read = gaps = asked = 0
    for day in days_to_read(conn, today, legislature):
        if budget and budget.exhausted():
            log(budget.disclose("archive days", asked))
            break
        asked += 1
        try:
            text = client.post_form(DAY_ARCHIVE, {"desde": day, "hasta": day}, FEED,
                                    "historico-" + day, archive=True)
            payload = json.loads(text)
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "session archive {0}: {1}".format(day, str(exc)[:200]))
            log("  [gap] session archive {0}: {1}".format(day, str(exc)[:120]))
            gaps += 1
            continue
        sessions = payload.get("sesiones") or []
        if not payload.get("validar") or not sessions:
            # The archive answers the same way for "no sitting" and "not
            # filed yet". Only a day with recorded votes is known to have sat.
            late = (today_d - datetime.date.fromisoformat(day)).days > ARCHIVE_GRACE_DAYS
            state = 0
            if late and day in vote_days:
                state = -1
                _gap(conn, today, "session archive {0}: votes recorded, no session filed {1} days on"
                     .format(day, ARCHIVE_GRACE_DAYS))
                log("  [gap] session archive {0}: votes recorded but no session filed".format(day))
                gaps += 1
            elif late:
                state = 1
            elif day in vote_days:
                log("  {0}: not in the archive yet; asked again next run".format(day))
            conn.execute("INSERT INTO sv_vote_days (day, legislature, sessions, archived, fetched_at) "
                         "VALUES (?,?,0,?,?) ON CONFLICT(day) DO UPDATE SET archived=excluded.archived, "
                         "fetched_at=excluded.fetched_at", (day, legislature, state, today))
            conn.commit()
            continue
        for n, s in enumerate(sessions):
            archivos = payload.get("archivos") if n == 0 else None
            if n > 0:
                try:
                    more = json.loads(client.post_form(SESSION_FILES, {"sesion": s.get("codigo")}, FEED,
                                                       "archivos-" + str(s.get("codigo")), archive=True))
                    archivos = more.get("archivos")
                except (FetchError, ValueError) as exc:
                    _gap(conn, today, "session files {0}: {1}".format(s.get("codigo"), str(exc)[:200]))
                    gaps += 1
                    continue
            leg = s.get("legislatura") or legislature
            dictamenes, piezas, resumen, agenda = parse_session_files(archivos)
            skey = store_session(conn, leg, s, resumen, agenda, today)
            for d in dictamenes:
                if d["numero"] is not None:
                    store_dictamen(conn, leg, skey, d, tax, today)
            for p in piezas:
                if p["orden"] is not None:
                    store_pieza(conn, leg, _int(s.get("sesion")), skey, p, tax, today)
        conn.execute("INSERT INTO sv_vote_days (day, legislature, sessions, archived, fetched_at) "
                     "VALUES (?,?,?,1,?) ON CONFLICT(day) DO UPDATE SET sessions=excluded.sessions, "
                     "archived=1, fetched_at=excluded.fetched_at", (day, legislature, len(sessions), today))
        conn.commit()
        read += 1
    return read, gaps


def pull_positions(conn, client, today, legislature, log=print, budget=None, limit=None):
    """Fetch and parse every stored vote's PDF not yet read. Returns (read, gaps)."""
    rows = conn.execute(
        "SELECT division_key, pdf_url FROM sv_divisions WHERE legislature=? AND positions IS NULL "
        "AND pdf_url IS NOT NULL ORDER BY date DESC", (legislature,)).fetchall()
    read = gaps = 0
    for key, url in rows:
        if budget and budget.exhausted():
            log(budget.disclose("vote PDFs", read))
            break
        if limit is not None and read >= limit:
            break
        try:
            raw = client.get_bytes(url, FEED, key, archive=False)
        except FetchError as exc:
            _gap(conn, today, "vote PDF {0}: {1}".format(key, str(exc)[:200]))
            log("  [gap] vote PDF {0}: {1}".format(key, str(exc)[:120]))
            gaps += 1
            continue
        parsed = parse_vote_pdf(raw)
        if not parsed or not parsed["positions"]:
            _gap(conn, today, "vote PDF {0}: no positions read".format(key))
            log("  [gap] vote PDF {0}: no positions read".format(key))
            gaps += 1
            continue
        store_positions(conn, key, parsed)
        conn.commit()
        read += 1
    return read, gaps


def pull_members(conn, client, today, log=print):
    page = client.get_text(MEMBERS_PAGE, FEED, "diputados")
    members = parse_members(page)
    for m in members:
        conn.execute(
            "INSERT INTO sv_members (member_id, name, party, department, cargo, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?) ON CONFLICT(member_id) DO UPDATE SET name=excluded.name, "
            "party=excluded.party, department=excluded.department, cargo=excluded.cargo, "
            "last_seen=excluded.last_seen",
            (m["member_id"], m["name"], m["party"], m["department"], m["cargo"], today, today))
    conn.commit()
    log("  members: {0} deputies".format(len(members)))
    return len(members)


def reclassify(conn, tax=None, log=print):
    for key, leg, exp, extracto in conn.execute(
            "SELECT dictamen_key, legislature, expediente, extracto FROM sv_dictamenes").fetchall():
        areas, terms, tier = classify(tax, [exp], extracto)
        conn.execute("UPDATE sv_dictamenes SET areas=?, matched_terms=?, tier=? WHERE dictamen_key=?",
                     (None if areas is None else sv_store.dumps(areas), sv_store.dumps(terms), tier, key))
    for key, leyenda, extracto in conn.execute(
            "SELECT pieza_key, leyenda, extracto FROM sv_piezas").fetchall():
        areas, terms, tier = classify(tax, [key], leyenda, extracto)
        conn.execute("UPDATE sv_piezas SET areas=?, matched_terms=?, tier=? WHERE pieza_key=?",
                     (None if areas is None else sv_store.dumps(areas), sv_store.dumps(terms), tier, key))
    _division_areas(conn)
    conn.commit()
    log("  reclassified")


def summary(conn, log=print):
    def count(sql):
        return conn.execute(sql).fetchone()[0]
    log("store: sv_divisions {0} ({1} with positions, {2} linked), sv_votes {3}, sv_dictamenes {4}, "
        "sv_piezas {5}, sv_sessions {6}, sv_members {7}".format(
            count("SELECT COUNT(*) FROM sv_divisions"),
            count("SELECT COUNT(*) FROM sv_divisions WHERE positions IS NOT NULL"),
            count("SELECT COUNT(*) FROM sv_divisions WHERE item_key IS NOT NULL"),
            count("SELECT COUNT(*) FROM sv_votes"), count("SELECT COUNT(*) FROM sv_dictamenes"),
            count("SELECT COUNT(*) FROM sv_piezas"), count("SELECT COUNT(*) FROM sv_sessions"),
            count("SELECT COUNT(*) FROM sv_members")))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--legislature", help="default: the newest in the vote list ('2024-2027')")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--taxonomy", help="classify with this taxonomy file instead of config/taxonomy-es.yaml")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--index-only", action="store_true", help="vote list and sessions, no vote PDFs")
    ap.add_argument("--full-list", action="store_true", help="read the whole vote list, not just new pages")
    ap.add_argument("--reclassify", action="store_true", help="re-derive areas offline and stop")
    ap.add_argument("--budget-seconds", type=float, default=drain.DEFAULT_S)
    ap.add_argument("--limit", type=int, help="stop after this many vote PDFs")
    args = ap.parse_args(argv)

    today = datetime.date.today().isoformat()
    conn = db.init_db(db.connect(args.db))
    tax = load_taxonomy(args.taxonomy)
    print("sv-rollcalls: taxonomy {0}".format(args.taxonomy or (TAXONOMY_ES if tax else "none (areas stay NULL)")))
    if args.reclassify:
        reclassify(conn, tax)
        summary(conn)
        return 0

    client = HttpClient(raw_dir=args.raw_dir, throttle=THROTTLE_S, default_timeout=120)
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    try:
        full = args.full_list or not conn.execute("SELECT 1 FROM sv_divisions LIMIT 1").fetchone()
        leg = pull_vote_list(conn, client, today, args.legislature, full=full)
    except (FetchError, ValueError) as exc:
        print("sv-rollcalls: the vote list failed: {0}".format(exc))
        return 1
    if not args.no_members:
        try:
            pull_members(conn, client, today)
        except FetchError as exc:
            _gap(conn, today, "members page: {0}".format(str(exc)[:200]))
            print("  [gap] members page: {0}".format(str(exc)[:120]))
            gaps += 1
    # The archive gets at most half the clock: on a backfill its slow calls
    # (up to 45 s each) would otherwise starve the vote PDFs every run.
    day_budget = drain.Budget(args.budget_seconds / 2.0)
    read, g = pull_days(conn, client, today, leg, tax, budget=day_budget)
    gaps += g
    print("  session archive: {0} sitting days read".format(read))
    if not args.index_only:
        read, g = pull_positions(conn, client, today, leg, budget=budget, limit=args.limit)
        gaps += g
        print("  vote PDFs: {0} read".format(read))
    n = link_divisions(conn)
    conn.commit()
    print("  linked {0} votes to their dictamen or pieza".format(n))
    summary(conn)
    print("sv-rollcalls: done, {0} gap(s)".format(gaps))
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
