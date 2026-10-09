#!/usr/bin/env python3
"""Chile's National Congress: deputies, senators, bills and recorded votes.

    python3 tools/cl_rollcalls.py                     # the current period (from 11 March 2026)
    python3 tools/cl_rollcalls.py --dry-run           # parse the newest Cámara vote, store nothing
    python3 tools/cl_rollcalls.py --reclassify        # re-derive areas, offline
    python3 tools/cl_rollcalls.py --senate-backfill   # Senate votes for every bill on our ground
    python3 tools/cl_rollcalls.py --db /tmp/cl.db     # anywhere but the store

PHASE 1 (9 October 2026). See docs/chile-scope.md. No edition reads these
tables yet. Every source is open and keyless:

  * opendata.camara.cl, the Cámara de Diputadas y Diputados' ASMX web
    services. They answer plain HTTP GET (no SOAP envelope needed):
      - WSLegislativo.asmx/retornarVotacionesXAnno?prmAnno=2026: every vote
        of a year (1,028 in 2026 to 7 October), counts and result, no names;
      - WSLegislativo.asmx/retornarVotacionDetalle?prmVotacionId=N: one vote
        with every deputy's position, keyed on the Cámara's deputy Id;
      - WSLegislativo.asmx/retornarProyectoLey?prmNumeroBoletin=15805-07:
        a bill and every Cámara vote on it, with the text put to the vote
        ("Articulo") and the trámite. The vote list itself says only
        "Boletín N° 15805-07", so this is where a vote's words come from;
      - WSLegislativo.asmx/retornarMocionesXAnno / retornarMensajesXAnno:
        every bill introduced in a year, titled;
      - WSDiputado.asmx/retornarDiputadosPeriodoActual: the 155 deputies,
        each with dated party spells (militancias).
  * tramitacion.senado.cl/wspublico, the Senate's XML services:
      - tramitacion.php?fecha=dd/mm/yyyy: every bill with movement since that
        date, both chambers, with the Senate's subject terms (materias),
        authors, stage, urgency AND every Senate vote with each senator's
        position. The slashes must be percent-encoded, and the service
        refuses a date more than a month back;
      - votaciones.php?boletin=15805: the Senate votes on one bill. It takes
        the NUMBER only; '15805-07' gets an HTML "No existe" page at HTTP 200.
  * www.senado.cl/senadoras-y-senadores/listado-de-senadoras-y-senadores:
    all 50 senators with PARLID and party, from the JSON the page embeds.
    The Senate's own senadores_vigentes.php lists only 31 (stale since the
    March 2026 renewal) and is the fallback.

WWW.CAMARA.CL REFUSES THE LAPTOP (a Cloudflare challenge, 403). Not worked
around (bot detection is never worked around in this repo); the open-data
host above carries what phase 1 needs.

ERROR PAGES ANSWER 200. Both chambers report "not found" in the body: the
Cámara with an xsi:nil element, the Senate with an HTML div. Every parser
here validates the root element and returns None on anything else.

A VOTE IS CLASSIFIED WITH ITS BILL. A vote's own text (the article or
motion put) lends `own_areas`; the bill's title and subject terms lend the
rest, as in the US. Joined by boletín, never by title.

CLASSIFICATION. config/taxonomy-es.yaml once Christopher approves the
Spanish terms proposed in docs/chile-scope.md; until then the English
taxonomy, which is nearly blind to Spanish, and every run says so. Text is
accent-folded before matching (the Senate writes "Abstencion", titles drop
accents inconsistently), so Spanish terms are written without accents.
config/watchlist-cl.yaml adds areas by boletín.

Separation guarantee: writes cl_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import cl_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "cl-rollcalls"
TAXONOMY_ES = os.path.join(ROOT, "config", "taxonomy-es.yaml")
TAXONOMY_EN = os.path.join(ROOT, "config", "taxonomy.yaml")

CAM = "https://opendata.camara.cl/camaradiputados/WServices/"
VOTES_YEAR = CAM + "WSLegislativo.asmx/retornarVotacionesXAnno?prmAnno={0}"
VOTE_DETAIL = CAM + "WSLegislativo.asmx/retornarVotacionDetalle?prmVotacionId={0}"
BILL = CAM + "WSLegislativo.asmx/retornarProyectoLey?prmNumeroBoletin={0}"
MOTIONS = CAM + "WSLegislativo.asmx/retornarMocionesXAnno?prmAnno={0}"
MESSAGES = CAM + "WSLegislativo.asmx/retornarMensajesXAnno?prmAnno={0}"
DEPUTIES = CAM + "WSDiputado.asmx/retornarDiputadosPeriodoActual"
SEN = "https://tramitacion.senado.cl/wspublico/"
SEN_SINCE = SEN + "tramitacion.php?fecha={0}"
SEN_VOTES = SEN + "votaciones.php?boletin={0}"
SENATORS_VIGENTES = SEN + "senadores_vigentes.php"
SENATORS_PAGE = "https://www.senado.cl/senadoras-y-senadores/listado-de-senadoras-y-senadores"

# The 2026-2030 period began on 11 March 2026 (legislatura 374). Earlier
# votes belong to the previous Cámara, whose deputies the current-period
# list does not carry; --since reaches back when wanted.
PERIOD_START = "2026-03-11"
# The Senate refuses a window over a month; 24 days answered (2.5 MB, 30 s)
# and 31 did not. Two weeks covers a missed run.
SENATE_DAYS = 14
SENATE_MAX_DAYS = 28
# Area 11 (migration) is tracked but not CitizenGO's ground for the edition.
HIDDEN_AREAS = (11,)
BUDGET_S = 2700.0

NS = "{http://opendata.camara.cl/camaradiputados/v1}"
XSI_NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"


# --- helpers -------------------------------------------------------------------

def fold(text):
    """Lower-case-preserving accent fold: 'Abstención' -> 'Abstencion', 'ñ' -> 'n'."""
    return "".join(c for c in unicodedata.normalize("NFKD", text or "")
                   if not unicodedata.combining(c))


def squash(text):
    return re.sub(r"\s+", " ", text or "").strip()


def norm_boletin(text):
    """'15.805-07' / '15805-07' -> '15805-07'; None when there is no boletín."""
    hit = re.search(r"(\d{1,2}\.?\d{3})\s*-\s*(\d{1,2})", text or "")
    return "{0}-{1}".format(hit.group(1).replace(".", ""), hit.group(2).zfill(2)) if hit else None


def boletin_number(boletin):
    return int(boletin.split("-", 1)[0])


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def _parse_xml(raw):
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        return None


def _c(el, name):
    """Child text in the Cámara namespace, stripped; None when absent."""
    if el is None:
        return None
    hit = el.find(NS + name)
    return hit.text.strip() if hit is not None and hit.text else None


def _ci(el, name):
    v = _c(el, name)
    return int(v) if v and v.lstrip("-").isdigit() else None


def _s(el, name):
    """Child text, Senate (no namespace)."""
    hit = el.find(name)
    return squash(hit.text) if hit is not None and hit.text else None


def senate_date(text):
    hit = re.match(r"(\d{2})/(\d{2})/(\d{4})", text or "")
    return "{0}-{1}-{2}".format(hit.group(3), hit.group(2), hit.group(1)) if hit else None


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def empty_watchlist():
    """The Chile watchlist is applied by BOLETÍN (cl_store.add_watch_areas)."""
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def taxonomy_path():
    return TAXONOMY_ES if os.path.exists(TAXONOMY_ES) else TAXONOMY_EN


def classify(tax, *fields):
    return filt.filter_item(tax, empty_watchlist(), *[fold(f) for f in fields if f])


# --- Cámara parsers ------------------------------------------------------------

def parse_vote_list(raw):
    """retornarVotacionesXAnno -> [vote dict], or None if not a vote list."""
    root = _parse_xml(raw)
    if root is None or root.tag != NS + "VotacionesColeccion":
        return None
    out = []
    for v in root.findall(NS + "Votacion"):
        out.append(_vote_head(v))
    return out


def _vote_head(v):
    desc = _c(v, "Descripcion")
    kind = _c(v, "Tipo")
    return {
        "id": _ci(v, "Id"), "description": desc, "date": _c(v, "Fecha"),
        "yes": _ci(v, "TotalSi"), "no": _ci(v, "TotalNo"),
        "abstain": _ci(v, "TotalAbstencion"), "paired": _ci(v, "TotalDispensado"),
        "quorum": _c(v, "Quorum"), "result": _c(v, "Resultado"), "kind": kind,
        "boletin": norm_boletin(desc) if desc and "olet" in desc else None,
    }


def parse_vote_detail(raw):
    """retornarVotacionDetalle -> vote dict with positions, or None."""
    root = _parse_xml(raw)
    if root is None or root.tag != NS + "Votacion" or _ci(root, "Id") is None:
        return None
    d = _vote_head(root)
    d["positions"] = []
    votos = root.find(NS + "Votos")
    for vt in (votos.findall(NS + "Voto") if votos is not None else []):
        dep = vt.find(NS + "Diputado")
        did = _c(dep, "Id")
        if not did:
            continue
        name = " ".join(x for x in (_c(dep, "Nombre"), _c(dep, "ApellidoPaterno"),
                                    _c(dep, "ApellidoMaterno")) if x)
        d["positions"].append({"member_key": "D-" + did, "source_id": did, "name": name,
                               "position": _c(vt, "OpcionVoto")})
    return d


def parse_bill(raw):
    """retornarProyectoLey -> bill dict with {vote id: (text, stage)}, or None."""
    root = _parse_xml(raw)
    if root is None or root.tag != NS + "ProyectoLey" or root.get(XSI_NIL) == "true":
        return None
    boletin = norm_boletin(_c(root, "NumeroBoletin"))
    if not boletin:
        return None
    votes = {}
    vs = root.find(NS + "Votaciones")
    for v in (vs.findall(NS + "VotacionProyectoLey") if vs is not None else []):
        vid = _ci(v, "Id")
        if vid is not None:
            votes[vid] = (squash(_c(v, "Articulo")), _c(v, "TramiteConstitucional"),
                          _c(v, "TipoVotacionProyectoLey"))
    subjects = []
    ms = root.find(NS + "Materias")
    for m in (list(ms) if ms is not None else []):
        name = _c(m, "Nombre") or (m.text or "").strip()
        if name:
            subjects.append(name)
    return {"boletin": boletin, "title": squash(_c(root, "Nombre")),
            "introduced": (_c(root, "FechaIngreso") or "")[:10] or None,
            "initiative": _c(root, "TipoIniciativa"), "origin": _c(root, "CamaraOrigen"),
            "subjects": subjects, "votes": votes}


def parse_bill_list(raw):
    """retornarMocionesXAnno / retornarMensajesXAnno -> [bill dict], or None."""
    root = _parse_xml(raw)
    if root is None or root.tag != NS + "ProyectosLeyColeccion":
        return None
    out = []
    for p in root.findall(NS + "ProyectoLey"):
        boletin = norm_boletin(_c(p, "NumeroBoletin"))
        if boletin:
            out.append({"boletin": boletin, "title": squash(_c(p, "Nombre")),
                        "introduced": (_c(p, "FechaIngreso") or "")[:10] or None,
                        "initiative": _c(p, "TipoIniciativa"),
                        "origin": _c(p, "CamaraOrigen")})
    return out


def parse_deputies(raw):
    """retornarDiputadosPeriodoActual -> [deputy dict with party spells], or None."""
    root = _parse_xml(raw)
    if root is None or root.tag != NS + "DiputadosPeriodoColeccion":
        return None
    out = []
    for dp in root.findall(NS + "DiputadoPeriodo"):
        d = dp.find(NS + "Diputado")
        did = _c(d, "Id")
        if not did:
            continue
        spells = []
        ms = d.find(NS + "Militancias")
        for m in (ms.findall(NS + "Militancia") if ms is not None else []):
            p = m.find(NS + "Partido")
            spells.append({"party": _c(p, "Alias") or _c(p, "Id"), "party_name": _c(p, "Nombre"),
                           "start": (_c(m, "FechaInicio") or "")[:10],
                           "end": (_c(m, "FechaTermino") or "")[:10] or None})
        spells.sort(key=lambda s: s["start"])
        name = " ".join(x for x in (_c(d, "Nombre"), _c(d, "Nombre2"), _c(d, "ApellidoPaterno"),
                                    _c(d, "ApellidoMaterno")) if x)
        out.append({"member_key": "D-" + did, "source_id": did, "name": name,
                    "sex": _c(d, "Sexo"), "spells": spells,
                    "party": spells[-1]["party"] if spells else None})
    return out


def party_on(spells, date):
    """The party alias of the spell covering an ISO date, or None."""
    day = (date or "")[:10]
    for s in spells or ():
        if s["start"] <= day and (not s["end"] or day <= s["end"]):
            return s["party"]
    return None


# --- Senate parsers ------------------------------------------------------------

def parse_senate_votes(el_or_raw):
    """A <votaciones> element (or raw votaciones.php bytes) -> [vote dict]."""
    root = el_or_raw
    if isinstance(el_or_raw, (bytes, str)):
        root = _parse_xml(el_or_raw)
        if root is None or root.tag != "votaciones":
            return None
    out = []
    for v in root.findall("votacion"):
        positions = []
        det = v.find("DETALLE_VOTACION")
        for vt in (det.findall("VOTO") if det is not None else []):
            name = _s(vt, "PARLAMENTARIO")
            if name:
                positions.append({"name": name, "position": _s(vt, "SELECCION")})
        out.append({"session": _s(v, "SESION"), "date": senate_date(_s(v, "FECHA")),
                    "text": _s(v, "TEMA"), "yes": _sint(v, "SI"), "no": _sint(v, "NO"),
                    "abstain": _sint(v, "ABSTENCION"), "paired": _sint(v, "PAREO"),
                    "quorum": _s(v, "QUORUM"), "kind": _s(v, "TIPOVOTACION"),
                    "stage": _s(v, "ETAPA"), "positions": positions})
    return out


def _sint(el, name):
    v = _s(el, name)
    return int(v) if v and v.isdigit() else None


def parse_senate_projects(raw):
    """tramitacion.php -> [bill dict with its Senate votes], or None (error page)."""
    root = _parse_xml(raw)
    if root is None or root.tag != "proyectos":
        return None
    out = []
    for p in root.findall("proyecto"):
        d = p.find("descripcion")
        if d is None:
            continue
        boletin = norm_boletin(_s(d, "boletin"))
        if not boletin:
            continue
        subjects = [squash(m.findtext("DESCRIPCION") or m.text or "")
                    for m in p.findall("materias/materia")]
        authors = [squash(a.findtext("PARLAMENTARIO") or a.text or "")
                   for a in p.findall("autores/autor")]
        votes_el = p.find("votaciones")
        out.append({
            "boletin": boletin, "title": _s(d, "titulo"),
            "introduced": senate_date(_s(d, "fecha_ingreso")),
            "initiative": _s(d, "iniciativa"), "origin": _s(d, "camara_origen"),
            "urgency": _s(d, "urgencia_actual"), "stage": _s(d, "etapa"),
            "substage": _s(d, "subetapa"), "law_number": _s(d, "leynro"),
            "status": _s(d, "estado"),
            "subjects": [s for s in subjects if s], "authors": [a for a in authors if a],
            "votes": parse_senate_votes(votes_el) if votes_el is not None else [],
        })
    return out


def parse_senators_page(html):
    """The senado.cl listing page -> [senator dict] from its embedded JSON, or None."""
    hit = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html or "", re.S)
    if not hit:
        return None
    try:
        data = json.loads(hit.group(1))
    except ValueError:
        return None
    found = {}

    def walk(o):
        if isinstance(o, dict):
            if "ID_PARLAMENTARIO" in o and o.get("CAMARA") == "S":
                found[o["ID_PARLAMENTARIO"]] = o
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    out = []
    for pid, o in sorted(found.items()):
        given, s1, s2 = squash(o.get("NOMBRE")), squash(o.get("APELLIDO_PATERNO")), \
            squash(o.get("APELLIDO_MATERNO"))
        out.append({"member_key": "S-{0}".format(pid), "source_id": str(pid),
                    "name": " ".join(x for x in (given, s1, s2) if x),
                    "given": given, "surname1": s1, "surname2": s2,
                    "party": squash(o.get("PARTIDO")) or None,
                    "region": squash(o.get("REGION")) or None,
                    "district": str(o.get("CIRCUNSCRIPCION_ID") or "") or None,
                    "sex": squash(o.get("SEXO_ETIQUETA")) or None})
    return out or None


def parse_senadores_vigentes(raw):
    root = _parse_xml(raw)
    if root is None or root.tag != "senadores":
        return None
    out = []
    for s in root.findall("senador"):
        pid = _s(s, "PARLID")
        if not pid:
            continue
        given, s1, s2 = _s(s, "PARLNOMBRE"), _s(s, "PARLAPELLIDOPATERNO"), \
            _s(s, "PARLAPELLIDOMATERNO")
        out.append({"member_key": "S-" + pid, "source_id": pid,
                    "name": " ".join(x for x in (given, s1, s2) if x),
                    "given": given, "surname1": s1, "surname2": s2,
                    "party": _s(s, "PARTIDO"), "region": _s(s, "REGION"),
                    "district": _s(s, "CIRCUNSCRIPCION"), "sex": None})
    return out


def _k(text):
    return fold(squash(text)).lower()


class SenatorIndex:
    """Resolve "Gatica B., María José" to a senator's member key.

    The Senate's vote records print surname, the initial of the second
    surname, and given names. Resolution narrows by first surname, then the
    initial, then the first given name; anything still ambiguous or unknown
    is NOT guessed (resolve returns None)."""

    def __init__(self, senators):
        self.senators = senators or []

    def resolve(self, printed):
        left, _, given = (printed or "").partition(",")
        tokens = squash(left).split(" ")
        initial = ""
        if tokens and re.fullmatch(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]?\.?", tokens[-1]) and len(tokens) > 1:
            initial = _k(tokens.pop()).rstrip(".")
        surname = _k(" ".join(tokens))
        cands = [s for s in self.senators if _k(s.get("surname1")) == surname]
        # Every printed part must agree, not just narrow: "Castro P., Juan"
        # (a senator until March 2026) is not "Castro G., Juan Luis", even
        # though the current list has only one Castro.
        if initial:
            cands = [s for s in cands if not _k(s.get("surname2"))
                     or _k(s.get("surname2"))[:1] == initial]
        first = (_k(given).split(" ") or [""])[0]
        if first:
            cands = [s for s in cands if (_k(s.get("given")).split(" ") or [""])[0] == first]
        return cands[0] if len(cands) == 1 else None


def senate_division_key(boletin, v, seen):
    """'senado-15805-<12 hex>': the Senate publishes no vote ID. Identical
    votes in one record (it happens: repeated motions) are told apart by
    their order, via `seen`."""
    basis = "|".join(squash(x or "") for x in (
        boletin, v.get("session"), v.get("date"), v.get("stage"), v.get("kind"), v.get("text")))
    n = seen.get(basis, 0)
    seen[basis] = n + 1
    if n:
        basis += "|{0}".format(n)
    return "senado-{0}-{1}".format(boletin_number(boletin),
                                   hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12])


# --- storing -------------------------------------------------------------------

MEMBER_UPSERT = (
    "INSERT INTO cl_members (member_key, chamber, source_id, name, party, sex, region, "
    "district, as_of, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
    "ON CONFLICT(member_key) DO UPDATE SET "
    "name=COALESCE(excluded.name, cl_members.name), "
    "party=CASE WHEN COALESCE(excluded.as_of,'') >= COALESCE(cl_members.as_of,'') "
    "THEN COALESCE(excluded.party, cl_members.party) ELSE cl_members.party END, "
    "sex=COALESCE(excluded.sex, cl_members.sex), "
    "region=COALESCE(excluded.region, cl_members.region), "
    "district=COALESCE(excluded.district, cl_members.district), "
    "as_of=MAX(COALESCE(excluded.as_of,''), COALESCE(cl_members.as_of,'')), "
    "last_seen=excluded.last_seen")


def store_member(conn, m, chamber, today, as_of=None):
    conn.execute(MEMBER_UPSERT, (m["member_key"], chamber, m.get("source_id"), m.get("name"),
                                 m.get("party"), m.get("sex"), m.get("region"),
                                 m.get("district"), as_of or today, today, today))
    for s in m.get("spells") or ():
        conn.execute("INSERT OR REPLACE INTO cl_party_spells (member_key, party, party_name, "
                     "start, end) VALUES (?,?,?,?,?)",
                     (m["member_key"], s["party"], s["party_name"], s["start"], s["end"]))


def classify_bill(tax, b):
    res = classify(tax, b.get("title") or "", *(b.get("subjects") or []))
    return cl_store.add_watch_areas(res, b["boletin"])


def store_bill(conn, tax, b, today):
    """Upsert a bill, merging what each source knows. Returns its areas."""
    row = conn.execute("SELECT title, subjects FROM cl_bills WHERE boletin=?",
                       (b["boletin"],)).fetchone()
    title = b.get("title") or (row[0] if row else None)
    subjects = b.get("subjects") or (json.loads(row[1] or "[]") if row else [])
    res = classify_bill(tax, {"boletin": b["boletin"], "title": title, "subjects": subjects})
    conn.execute(
        "INSERT INTO cl_bills (boletin, number, title, introduced, initiative, origin, stage, "
        "substage, status, urgency, law_number, subjects, authors, areas, matched_terms, tier, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(boletin) DO UPDATE SET "
        "title=COALESCE(excluded.title, cl_bills.title), "
        "introduced=COALESCE(excluded.introduced, cl_bills.introduced), "
        "initiative=COALESCE(excluded.initiative, cl_bills.initiative), "
        "origin=COALESCE(excluded.origin, cl_bills.origin), "
        "stage=COALESCE(excluded.stage, cl_bills.stage), "
        "substage=COALESCE(excluded.substage, cl_bills.substage), "
        "status=COALESCE(excluded.status, cl_bills.status), "
        "urgency=COALESCE(excluded.urgency, cl_bills.urgency), "
        "law_number=COALESCE(excluded.law_number, cl_bills.law_number), "
        "subjects=excluded.subjects, "
        "authors=CASE WHEN excluded.authors='[]' THEN cl_bills.authors ELSE excluded.authors END, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen",
        (b["boletin"], boletin_number(b["boletin"]), title, b.get("introduced"),
         b.get("initiative"), b.get("origin"), b.get("stage"), b.get("substage"),
         b.get("status"), b.get("urgency"), b.get("law_number") or None,
         cl_store.dumps(subjects), cl_store.dumps(b.get("authors")),
         cl_store.dumps(res.issue_areas),
         cl_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
         res.tier, today, today))
    return res.issue_areas


def bill_areas(conn, boletin):
    if not boletin:
        return []
    row = conn.execute("SELECT areas FROM cl_bills WHERE boletin=?", (boletin,)).fetchone()
    return json.loads(row[0] or "[]") if row else []


def classify_division(tax, text, bill_area_list):
    own = classify(tax, text or "")
    return own, sorted(set(own.issue_areas or []) | set(bill_area_list or []))


def store_division(conn, tax, d, today):
    """d: chamber, division_key, source_id, date, boletin, kind, description,
    text, stage, quorum, result, yes, no, abstain, paired, positions[member_key,
    position, party]. Returns the division's combined areas."""
    own, areas = classify_division(tax, d.get("text"), bill_areas(conn, d.get("boletin")))
    conn.execute(
        "INSERT INTO cl_divisions (division_key, chamber, source_id, date, boletin, kind, "
        "description, text, stage, quorum, result, yes, no, abstain, paired, own_areas, areas, "
        "matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET result=excluded.result, yes=excluded.yes, "
        "no=excluded.no, abstain=excluded.abstain, paired=excluded.paired, "
        "text=COALESCE(excluded.text, cl_divisions.text), "
        "stage=COALESCE(excluded.stage, cl_divisions.stage), "
        "own_areas=excluded.own_areas, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (d["division_key"], d["chamber"], d.get("source_id"), (d.get("date") or "")[:10] or None,
         d.get("boletin"), d.get("kind"), d.get("description"), d.get("text"), d.get("stage"),
         d.get("quorum"), d.get("result"), d.get("yes"), d.get("no"), d.get("abstain"),
         d.get("paired"), cl_store.dumps(own.issue_areas), cl_store.dumps(areas),
         cl_store.dumps(own.matched_terms), own.tier, today, today))
    for p in d.get("positions") or ():
        conn.execute("INSERT OR REPLACE INTO cl_votes (division_key, member_key, position, party) "
                     "VALUES (?,?,?,?)",
                     (d["division_key"], p["member_key"], p.get("position"), p.get("party")))
    return areas


# --- pulls ---------------------------------------------------------------------

def pull_members(conn, client, today, log=print):
    """Deputies (with party spells) and senators. Returns (deputies, senators,
    senator list for name resolution, gaps)."""
    gaps = 0
    deputies = []
    try:
        deputies = parse_deputies(client.get_bytes(DEPUTIES, FEED, "deputies")) or []
    except FetchError as exc:
        _gap(conn, today, "deputies: {0}".format(exc))
        log("  [gap] deputies: {0}".format(str(exc)[:80]))
        gaps += 1
    for d in deputies:
        store_member(conn, d, "camara", today)
    senators = None
    try:
        senators = parse_senators_page(client.get_text(SENATORS_PAGE, FEED, "senators-page"))
    except FetchError as exc:
        log("  senators page unavailable ({0}); falling back to senadores_vigentes".format(
            str(exc)[:60]))
    if not senators:
        try:
            senators = parse_senadores_vigentes(
                client.get_bytes(SENATORS_VIGENTES, FEED, "senadores-vigentes")) or []
            _gap(conn, today, "senators: listing page unparsed; used senadores_vigentes "
                              "({0}, stale)".format(len(senators)))
            log("  [gap] senators: used the stale senadores_vigentes list ({0})".format(
                len(senators)))
            gaps += 1
        except FetchError as exc:
            senators = []
            _gap(conn, today, "senators: {0}".format(exc))
            log("  [gap] senators: {0}".format(str(exc)[:80]))
            gaps += 1
    for s in senators:
        store_member(conn, s, "senado", today)
    conn.commit()
    return len(deputies), len(senators), senators, gaps


def pull_new_bills(conn, client, tax, today, years, log=print):
    """Every bill introduced in the given years (both chambers), titled by the
    Cámara. Returns (read, on our ground, gaps)."""
    read = ours = gaps = 0
    for year in years:
        for url, label in ((MOTIONS, "mociones"), (MESSAGES, "mensajes")):
            try:
                bills = parse_bill_list(client.get_bytes(url.format(year), FEED,
                                                         "{0}-{1}".format(label, year)))
            except FetchError as exc:
                _gap(conn, today, "{0} {1}: {2}".format(label, year, exc))
                log("  [gap] {0} {1}: {2}".format(label, year, str(exc)[:70]))
                gaps += 1
                continue
            if bills is None:
                _gap(conn, today, "{0} {1}: not a bill list".format(label, year))
                gaps += 1
                continue
            for b in bills:
                ours += on_our_ground(store_bill(conn, tax, b, today))
                read += 1
            conn.commit()
    return read, ours, gaps


def pull_camara(conn, client, tax, today, since=PERIOD_START, log=print, limit=None,
                budget=None):
    """Every Cámara vote since `since` not yet stored, with positions.
    Returns (stored, on our ground, gaps). Resumes from the store."""
    stored = ours = gaps = 0
    have = {r[0] for r in conn.execute(
        "SELECT source_id FROM cl_divisions WHERE chamber='camara'")}
    spells = {}
    for mk, party, start, end in conn.execute(
            "SELECT member_key, party, start, end FROM cl_party_spells"):
        spells.setdefault(mk, []).append({"party": party, "start": start, "end": end})
    this_year = int(today[:4])
    for year in range(int(since[:4]), this_year + 1):
        try:
            votes = parse_vote_list(client.get_bytes(VOTES_YEAR.format(year), FEED,
                                                     "votaciones-{0}".format(year)))
        except FetchError as exc:
            _gap(conn, today, "Cámara votes {0}: {1}".format(year, exc))
            log("  [gap] Cámara votes {0}: {1}".format(year, str(exc)[:70]))
            gaps += 1
            continue
        if votes is None:
            _gap(conn, today, "Cámara votes {0}: not a vote list".format(year))
            gaps += 1
            continue
        new = sorted((v for v in votes if (v["date"] or "") >= since and v["id"] is not None
                      and str(v["id"]) not in have), key=lambda v: (v["date"], v["id"]))
        bills = {}
        for v in new:
            if limit is not None and stored >= limit:
                log("  fetch cap ({0}) reached; the rest lands on the next run "
                    "-- disclosed, not silent".format(limit))
                return stored, ours, gaps
            if budget is not None and budget.exhausted():
                log(budget.disclose("Cámara votes", stored))
                return stored, ours, gaps
            b = v["boletin"]
            if b and b not in bills:
                try:
                    bills[b] = parse_bill(client.get_bytes(BILL.format(b), FEED, "bill-" + b))
                except FetchError as exc:
                    _gap(conn, today, "bill {0}: {1}".format(b, exc))
                    log("  [gap] bill {0}: {1}".format(b, str(exc)[:70]))
                    gaps += 1
                    bills[b] = None
                if bills[b]:
                    store_bill(conn, tax, bills[b], today)
            try:
                d = parse_vote_detail(client.get_bytes(VOTE_DETAIL.format(v["id"]), FEED,
                                                       "vote-{0}".format(v["id"]),
                                                       archive=False))
            except FetchError as exc:
                # Stop the year rather than skip: the next run resumes here.
                _gap(conn, today, "Cámara vote {0}: {1}".format(v["id"], exc))
                log("  [gap] Cámara vote {0}: {1}".format(v["id"], str(exc)[:70]))
                gaps += 1
                break
            if d is None:
                _gap(conn, today, "Cámara vote {0}: not a vote".format(v["id"]))
                gaps += 1
                continue
            text, stage, _vt = (bills.get(b) or {}).get("votes", {}).get(v["id"], (None, None, None))
            for p in d["positions"]:
                p["party"] = party_on(spells.get(p["member_key"]), v["date"])
                if not conn.execute("SELECT 1 FROM cl_members WHERE member_key=?",
                                    (p["member_key"],)).fetchone():
                    # A deputy of an earlier period: name from the vote, no party.
                    store_member(conn, {"member_key": p["member_key"],
                                        "source_id": p["source_id"], "name": p["name"]},
                                 "camara", today, as_of=v["date"][:10])
            areas = store_division(conn, tax, {
                "division_key": "camara-{0}".format(v["id"]), "chamber": "camara",
                "source_id": str(v["id"]), "date": v["date"], "boletin": b,
                "kind": v["kind"], "description": v["description"], "text": text,
                "stage": stage, "quorum": v["quorum"], "result": v["result"],
                "yes": v["yes"], "no": v["no"], "abstain": v["abstain"],
                "paired": v["paired"], "positions": d["positions"]}, today)
            conn.commit()
            stored += 1
            ours += on_our_ground(areas)
    return stored, ours, gaps


def store_senate_votes(conn, tax, boletin, votes, index, today, unresolved):
    """Store one bill's Senate votes. Returns (stored, on our ground)."""
    stored = ours = 0
    seen = {}
    for v in votes or ():
        key = senate_division_key(boletin, v, seen)
        positions = []
        for p in v["positions"]:
            s = index.resolve(p["name"])
            if s:
                mk, party = s["member_key"], s.get("party")
            else:
                mk, party = "S-?" + _k(p["name"]), None
                unresolved.add(p["name"])
                if not conn.execute("SELECT 1 FROM cl_members WHERE member_key=?",
                                    (mk,)).fetchone():
                    store_member(conn, {"member_key": mk, "name": p["name"]}, "senado",
                                 today, as_of=v["date"])
            positions.append({"member_key": mk, "position": p["position"], "party": party})
        areas = store_division(conn, tax, {
            "division_key": key, "chamber": "senado", "source_id": v["session"],
            "date": v["date"], "boletin": boletin, "kind": v["kind"],
            "description": None, "text": v["text"], "stage": v["stage"],
            "quorum": v["quorum"], "result": None, "yes": v["yes"], "no": v["no"],
            "abstain": v["abstain"], "paired": v["paired"], "positions": positions}, today)
        stored += 1
        ours += on_our_ground(areas)
    return stored, ours


def pull_senate(conn, client, tax, today, senators, days=SENATE_DAYS, log=print,
                backfill=False, budget=None):
    """Bills with Senate-side movement in the last `days`, with their Senate
    votes; then, on a backfill, the Senate votes of every bill on our ground.
    Returns (bills, votes, on our ground, unresolved names, gaps)."""
    index = SenatorIndex(senators)
    unresolved = set()
    nbills = nvotes = ours = gaps = 0
    days = min(days, SENATE_MAX_DAYS)
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=days))
    url = SEN_SINCE.format(quote(since.strftime("%d/%m/%Y"), safe=""))
    try:
        projects = parse_senate_projects(client.get_bytes(url, FEED, "tramitacion-since-" +
                                                          since.isoformat(), timeout=180))
    except FetchError as exc:
        projects = None
        log("  [gap] Senate tramitación since {0}: {1}".format(since, str(exc)[:70]))
    if projects is None:
        _gap(conn, today, "Senate tramitación since {0}: no project list".format(since))
        gaps += 1
        projects = []
    for p in projects:
        store_bill(conn, tax, p, today)
        nbills += 1
        s, o = store_senate_votes(conn, tax, p["boletin"], p["votes"], index, today, unresolved)
        nvotes += s
        ours += o
        conn.commit()
    if backfill:
        done = {p["boletin"] for p in projects}
        for boletin, areas in conn.execute("SELECT boletin, areas FROM cl_bills").fetchall():
            if boletin in done or not on_our_ground(json.loads(areas or "[]")):
                continue
            if budget is not None and budget.exhausted():
                log(budget.disclose("Senate backfill bills", nbills))
                break
            try:
                votes = parse_senate_votes(client.get_bytes(
                    SEN_VOTES.format(boletin_number(boletin)), FEED, "senate-votes-" + boletin))
            except FetchError as exc:
                _gap(conn, today, "Senate votes {0}: {1}".format(boletin, exc))
                gaps += 1
                continue
            if votes is None:
                continue        # "No existe": a bill the Senate has not seen
            s, o = store_senate_votes(conn, tax, boletin, votes, index, today, unresolved)
            nvotes += s
            ours += o
            conn.commit()
    return nbills, nvotes, ours, sorted(unresolved), gaps


# --- reclassify and summary ----------------------------------------------------

def reclassify(conn, tax, log=print):
    """Re-derive bill areas, then division areas, offline. Bills first."""
    changed_b = changed_d = 0
    for boletin, title, subjects, areas in conn.execute(
            "SELECT boletin, title, subjects, areas FROM cl_bills").fetchall():
        res = classify_bill(tax, {"boletin": boletin, "title": title,
                                  "subjects": json.loads(subjects or "[]")})
        new = cl_store.dumps(res.issue_areas)
        changed_b += new != (areas or "[]")
        conn.execute("UPDATE cl_bills SET areas=?, matched_terms=?, tier=? WHERE boletin=?",
                     (new, cl_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, boletin))
    for key, boletin, text, areas in conn.execute(
            "SELECT division_key, boletin, text, areas FROM cl_divisions").fetchall():
        own, combined = classify_division(tax, text, bill_areas(conn, boletin))
        new = cl_store.dumps(combined)
        changed_d += new != (areas or "[]")
        conn.execute("UPDATE cl_divisions SET own_areas=?, areas=?, matched_terms=?, tier=? "
                     "WHERE division_key=?",
                     (cl_store.dumps(own.issue_areas), new, cl_store.dumps(own.matched_terms),
                      own.tier, key))
    conn.commit()
    log("cl-rollcalls: reclassified; {0} bill(s) and {1} division(s) changed area".format(
        changed_b, changed_d))
    return changed_b, changed_d


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = lambda sql: sum(on_our_ground(json.loads(a or "[]"))  # noqa: E731
                           for (a,) in conn.execute(sql))
    log("  store: {0} bill(s), {1} on our ground; {2} Cámara vote(s), {3} on our ground; "
        "{4} Senate vote(s), {5} on our ground; {6} member(s), {7} position(s)".format(
            n("SELECT COUNT(*) FROM cl_bills"), ours("SELECT areas FROM cl_bills"),
            n("SELECT COUNT(*) FROM cl_divisions WHERE chamber='camara'"),
            ours("SELECT areas FROM cl_divisions WHERE chamber='camara'"),
            n("SELECT COUNT(*) FROM cl_divisions WHERE chamber='senado'"),
            ours("SELECT areas FROM cl_divisions WHERE chamber='senado'"),
            n("SELECT COUNT(*) FROM cl_members"), n("SELECT COUNT(*) FROM cl_votes")))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--taxonomy", help="taxonomy yaml (default: taxonomy-es when it exists)")
    ap.add_argument("--since", default=PERIOD_START, help="first Cámara vote date (ISO)")
    ap.add_argument("--bill-years", default=None,
                    help="years of introduced bills to read, comma-separated "
                         "(default: this year and last)")
    ap.add_argument("--senate-days", type=int, default=SENATE_DAYS)
    ap.add_argument("--senate-backfill", action="store_true",
                    help="also read the Senate votes of every bill on our ground")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--no-bills", action="store_true")
    ap.add_argument("--no-camara", action="store_true")
    ap.add_argument("--no-senate", action="store_true")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored bills and divisions, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--limit", type=int, help="stop after this many Cámara votes")
    ap.add_argument("--dry-run", action="store_true",
                    help="parse the newest Cámara vote of this year, store nothing")
    args = ap.parse_args(argv)
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    today = datetime.date.today().isoformat()
    tax_path = args.taxonomy or taxonomy_path()
    if tax_path == TAXONOMY_EN:
        print("cl-rollcalls: config/taxonomy-es.yaml not approved yet; classifying with the "
              "English taxonomy, which is nearly blind to Spanish (areas PROVISIONAL)")
    tax = filt.load_taxonomy(tax_path)
    if args.dry_run:
        votes = parse_vote_list(client.get_bytes(VOTES_YEAR.format(today[:4]), FEED, "dry",
                                                 archive=False)) or []
        if not votes:
            print("cl-rollcalls: no Cámara vote this year")
            return 1
        v = max(votes, key=lambda x: x["date"] or "")
        d = parse_vote_detail(client.get_bytes(VOTE_DETAIL.format(v["id"]), FEED, "dry",
                                               archive=False))
        print("cl-rollcalls: Cámara vote {0} ({1}): {2}".format(
            v["id"], v["date"], "{0} position(s), {1}".format(len(d["positions"]), v["description"])
            if d else "NOT A VOTE"))
        return 0
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn, tax)
        summary(conn)
        conn.close()
        return 0
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    senators = []
    if not args.no_members:
        nd, ns, senators, g = pull_members(conn, client, today)
        gaps += g
        print("cl-rollcalls: {0} deputies, {1} senators".format(nd, ns))
    else:
        senators = [{"member_key": mk, "name": nm, "party": party, "given": None,
                     "surname1": None, "surname2": None}
                    for mk, nm, party in conn.execute(
                        "SELECT member_key, name, party FROM cl_members WHERE chamber='senado' "
                        "AND source_id IS NOT NULL")]
    if not args.no_bills:
        years = ([int(y) for y in args.bill_years.split(",") if y.strip()] if args.bill_years
                 else [int(today[:4]) - 1, int(today[:4])])
        read, ours, g = pull_new_bills(conn, client, tax, today, years)
        gaps += g
        print("cl-rollcalls: {0} introduced bill(s) read ({1}), {2} on our ground, "
              "{3} gap(s)".format(read, ",".join(map(str, years)), ours, g))
    if not args.no_camara:
        stored, ours, g = pull_camara(conn, client, tax, today, since=args.since,
                                      limit=args.limit, budget=budget)
        gaps += g
        print("cl-rollcalls: {0} new Cámara vote(s), {1} on our ground, {2} gap(s)".format(
            stored, ours, g))
    if not args.no_senate:
        first = not conn.execute("SELECT 1 FROM cl_divisions WHERE chamber='senado' "
                                 "LIMIT 1").fetchone()
        nb, nv, ours, unresolved, g = pull_senate(
            conn, client, tax, today, senators, days=args.senate_days,
            backfill=args.senate_backfill or first, budget=budget)
        gaps += g
        print("cl-rollcalls: {0} bill(s) with Senate movement, {1} Senate vote(s) read, "
              "{2} on our ground, {3} gap(s)".format(nb, nv, ours, g))
        if unresolved:
            print("cl-rollcalls: {0} senator name(s) not resolved, kept unguessed: {1}".format(
                len(unresolved), "; ".join(unresolved[:10])))
    summary(conn)
    conn.close()
    # 3: stored what it could and recorded gaps (the job still publishes).
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
