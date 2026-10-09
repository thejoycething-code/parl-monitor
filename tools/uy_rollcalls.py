#!/usr/bin/env python3
"""Uruguay: the Cámara de Representantes' deputies, pedidos de informes and
Diario de Sesiones index, and every law promulgated (IMPO).

    python3 tools/uy_rollcalls.py                      # everything
    python3 tools/uy_rollcalls.py --no-laws            # the Cámara's files only
    python3 tools/uy_rollcalls.py --from-law 20380     # walk IMPO from a number
    python3 tools/uy_rollcalls.py --reclassify         # re-derive areas, offline
    python3 tools/uy_rollcalls.py --taxonomy x.yaml    # classify with a draft list
    python3 tools/uy_rollcalls.py --db /tmp/uy.db      # anywhere but the store

PHASE 1 (9 October 2026); see docs/uruguay-scope.md. Named `_rollcalls` for
the country-branch convention, but there are NO ROLL CALLS TO COLLECT:
Uruguay votes by show of hands or an anonymous electronic register, and the
Diario de Sesiones prints totals only. What is read, all keyless and
measured live:

  * documentos.diputados.gub.uy/docs/ -- the Cámara de Representantes' own
    open-data files, regenerated daily (Last-Modified moves every evening):
      DAdiputadosNomina2.json  the roll: 348 names (titulares and suplentes,
                               not told apart), party, department, ballot;
      DApedidosInformes.json   every pedido de informe of the legislature
                               (2,526 on 9 October 2026), the deputies'
                               written questions to the executive;
      DAdiarioSesiones.json    the Diario de Sesiones index, with PDF links.
    Published as UTF-8 (read as utf-8-sig, so a byte-order mark would not
    matter).
  * www.impo.com.uy/bases/leyes/<n>-<year>?json=true -- each law as JSON
    (ISO-8859-1, with raw line breaks inside strings, so parsed with
    strict=False). Laws are numbered in one series; the walk asks for the
    next number under the last law's year, then the year after. A wrong year
    answers 200 with an HTML page, not a 404, so a hit is a JSON body, never
    a status code. IMPO's robots.txt sets Crawl-delay: 10, honoured per host.

NOT READ, AND WHY: parlamento.gub.uy (bills, the Senate, committees,
legislators) answers 403 to every path, robots.txt included, from the laptop
and from GitHub's runners. The block is recorded, never worked around.

CLASSIFICATION is the shared Spanish taxonomy (config/taxonomy-es.yaml,
approved 10 October 2026, X1/X4), loaded for country "uy", plus
config/watchlist-uy.yaml applied by key ('ley:20431'). ACCENTS ARE FOLDED ON BOTH SIDES: the
Parliament writes titles in capitals and often drops the accents
("ADOPCION", "GENERO"), and src/filter.py matches accents exactly, so this
module folds the taxonomy's terms and the text alike (measured: 19 bills
matched folded against 15 unfolded in the 402-title snapshot).

Separation guarantee: writes uy_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.

Exit codes: 0 clean, 3 stored what it could and recorded gaps, 1 otherwise.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import tempfile
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, uy_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "uy-rollcalls"
DIP = "https://documentos.diputados.gub.uy/docs/"
MEMBERS_URL = DIP + "DAdiputadosNomina2.json"
QUESTIONS_URL = DIP + "DApedidosInformes.json"
SITTINGS_URL = DIP + "DAdiarioSesiones.json"
IMPO = "https://www.impo.com.uy"
LAW_URL = IMPO + "/bases/leyes/{n}-{y}"
# The shared Spanish list (X1, 10 October 2026); Uruguay's own terms are
# tagged [only: uy] in it.
TAXONOMY_UY = os.path.join(ROOT, "config", "taxonomy-es.yaml")
# The country this collector matches for: a shared language list
# (taxonomy-es, -pt, -nl, -it, -fr, -atch) tags a country's own terms
# [only: ...] and filter.load_taxonomy keeps only ours (10 October 2026).
TAXONOMY_COUNTRY = "uy"
BUDGET_S = drain.DEFAULT_S
THROTTLE_S = 1.0
IMPO_CRAWL_DELAY = 10.0     # www.impo.com.uy/robots.txt, measured 9 October 2026
# The first walk starts here: Ley 20.380 was promulgated on 25 September
# 2024, so the backfill covers the whole of the L legislature (from
# 15 February 2025) with a margin. About 150 laws at ten seconds each.
START_LAW = 20380
# Consecutive numbers that answer nothing before the walk stops. IMPO
# publishes a law some days after promulgation and not always in order.
MAX_MISSES = 3
# Holes below the newest stored law re-asked each run, at most.
MAX_HOLES = 10
TEXT_CHARS = 6000
HIDDEN_AREAS = (11,)   # migration: collated, never campaigned (repo-wide rule)
CHAMBER = "representantes"
ROMAN = {"L": 50, "XLIX": 49, "XLVIII": 48, "XLVII": 47, "XLVI": 46, "LI": 51}


# --- small helpers ------------------------------------------------------------

def deaccent(text):
    """'GÉNERO' -> 'GENERO', 'Niñez' -> 'Ninez'. Both sides of a match are
    folded this way (see the module docstring)."""
    return "".join(c for c in unicodedata.normalize("NFD", text or "")
                   if unicodedata.category(c) != "Mn")


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def iso_date(value):
    """'2026/07/14', '14/07/2026', an epoch in milliseconds (the older
    Diario rows), or None -> ISO date or None."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return datetime.datetime.utcfromtimestamp(value / 1000.0).date().isoformat()
    s = str(value).strip()
    m = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", s)
    if m:
        return "{0}-{1:02d}-{2:02d}".format(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def load_json_bytes(raw, encoding="utf-8-sig"):
    return json.loads(raw.decode(encoding), strict=False)


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def on_our_ground(areas):
    return bool(set(areas or []) - set(HIDDEN_AREAS))


def question_key(url_oficio):
    """'https://documentos.diputados.gub.uy/docs/L50/Oficio/01105.pdf' -> 'L50/01105'."""
    m = re.search(r"/(L\d+)/Oficio/([^/.]+)\.pdf", url_oficio or "", re.I)
    return "{0}/{1}".format(m.group(1), m.group(2)) if m else None


# --- classification ---------------------------------------------------------------

def _fold_obj(obj):
    if isinstance(obj, str):
        return deaccent(obj)
    if isinstance(obj, list):
        return [_fold_obj(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _fold_obj(v) for k, v in obj.items()}
    return obj


def load_taxonomy(path=None):
    """The Uruguayan taxonomy with every term accent-folded, or None while
    none exists (areas stay NULL)."""
    import yaml
    path = path or TAXONOMY_UY
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        raw = _fold_obj(yaml.safe_load(fh))
    fd, tmp = tempfile.mkstemp(suffix=".yaml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            yaml.safe_dump(raw, fh, allow_unicode=True)
        return filt.load_taxonomy(tmp, country=TAXONOMY_COUNTRY)
    finally:
        os.unlink(tmp)


def empty_watchlist():
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify(tax, key, *texts):
    """(areas or None, matched terms, tier). areas is None only when there
    is no taxonomy AND no watchlist entry: unclassified, not empty."""
    watched = uy_store.watch_areas(key) if key else []
    if tax is None:
        if watched:
            return sorted(set(watched)), ["watch:" + key], 2
        return None, [], None
    res = filt.filter_item(tax, empty_watchlist(), *[deaccent(t) for t in texts if t])
    areas = set(res.issue_areas or [])
    terms = list(res.matched_terms or [])
    tier = res.tier
    if watched:
        areas |= set(watched)
        terms.append("watch:" + key)
        tier = tier or 2
    return sorted(areas), terms, tier


# --- parsers (pure, tested on fixtures) -------------------------------------------

def parse_members(records):
    out = []
    for r in records or []:
        name = clean(r.get("Nombre"))
        if not name:
            continue
        hoja = r.get("HojaVotacion")
        if isinstance(hoja, float) and hoja.is_integer():
            hoja = int(hoja)
        out.append({"name": name, "party": clean(r.get("PartidoPolitico")) or None,
                    "departamento": clean(r.get("Departamento")) or None,
                    "hoja": None if hoja in (None, "") else str(hoja),
                    "genero": clean(r.get("Genero")) or None})
    return out


def parse_questions(records):
    out = []
    for r in records or []:
        key = question_key(r.get("URLoficio"))
        if not key:
            continue
        leg = re.match(r"L(\d+)/", key)
        out.append({"question_key": key, "legislature": int(leg.group(1)) if leg else None,
                    "date": iso_date(r.get("Fecha")), "organismo": clean(r.get("Organismo")) or None,
                    "autores": clean(r.get("Autores")) or None, "tema": clean(r.get("Tema")) or None,
                    "estado": clean(r.get("Estado")) or None,
                    "url_oficio": r.get("URLoficio") or None,
                    "url_respuesta": r.get("URLcontestacion") or None})
    return out


def parse_sittings(records):
    out = []
    for r in records or []:
        try:
            diario = int(r.get("Diario"))
        except (TypeError, ValueError):
            continue
        def _int(v):
            try:
                return int(v)
            except (TypeError, ValueError):
                return None
        out.append({"diario": diario, "legislature": clean(str(r.get("Legislatura") or "")) or None,
                    "periodo": _int(r.get("Periodo")), "tipo": clean(r.get("Tipo")) or None,
                    "sesion": _int(r.get("Sesion")), "sesion_tipo": clean(r.get("SesionTipo")) or None,
                    "date": iso_date(r.get("SesionFecha")), "url": r.get("URL") or None})
    return out


def parse_law(raw):
    """One IMPO law reply -> dict, or None when the reply is not a law (the
    HTML page a wrong year gets)."""
    body = raw.lstrip()
    if not body.startswith(b"{"):
        return None
    try:
        d = load_json_bytes(raw, "latin-1")
    except ValueError:
        return None
    if str(d.get("tipoNorma", "")).strip().lower() != "ley":
        return None
    arts = d.get("articulos") or []
    text = clean(" ".join(clean(a.get("textoArticulo")) for a in arts))
    return {"law_number": int(d["nroNorma"]), "year": int(d["anioNorma"]),
            "name": clean(d.get("nombreNorma")) or None,
            "promulgated": iso_date(d.get("fechaPromulgacion")),
            "published": iso_date(d.get("fechaPublicacion")),
            "articles": len(arts), "text": text[:TEXT_CHARS]}


# --- store -----------------------------------------------------------------------

def store_members(conn, members, today):
    for m in members:
        conn.execute(
            "INSERT INTO uy_members (chamber, name, party, departamento, hoja, genero, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(chamber, name) DO UPDATE SET party=excluded.party, "
            "departamento=excluded.departamento, hoja=excluded.hoja, genero=excluded.genero, "
            "last_seen=excluded.last_seen",
            (CHAMBER, m["name"], m["party"], m["departamento"], m["hoja"], m["genero"], today, today))


def store_question(conn, q, tax, today):
    areas, terms, tier = classify(tax, None, q["tema"])
    conn.execute(
        "INSERT INTO uy_questions (question_key, chamber, legislature, date, organismo, autores, tema, "
        "estado, url_oficio, url_respuesta, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(question_key) DO UPDATE SET "
        "date=excluded.date, organismo=excluded.organismo, autores=excluded.autores, tema=excluded.tema, "
        "estado=excluded.estado, url_oficio=excluded.url_oficio, url_respuesta=excluded.url_respuesta, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen",
        (q["question_key"], CHAMBER, q["legislature"], q["date"], q["organismo"], q["autores"],
         q["tema"], q["estado"], q["url_oficio"], q["url_respuesta"],
         None if areas is None else uy_store.dumps(areas), uy_store.dumps(terms), tier, today, today))
    return areas


def store_sittings(conn, sittings, today):
    for s in sittings:
        conn.execute(
            "INSERT INTO uy_sittings (chamber, diario, legislature, periodo, tipo, sesion, sesion_tipo, "
            "date, url, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(chamber, diario) DO UPDATE SET legislature=excluded.legislature, "
            "periodo=excluded.periodo, tipo=excluded.tipo, sesion=excluded.sesion, "
            "sesion_tipo=excluded.sesion_tipo, date=excluded.date, url=excluded.url, "
            "last_seen=excluded.last_seen",
            (CHAMBER, s["diario"], s["legislature"], s["periodo"], s["tipo"], s["sesion"],
             s["sesion_tipo"], s["date"], s["url"], today, today))


def store_law(conn, law, tax, today):
    key = "ley:{0}".format(law["law_number"])
    areas, terms, tier = classify(tax, key, law["name"], law["text"])
    conn.execute(
        "INSERT INTO uy_laws (law_number, year, name, promulgated, published, articles, text, url, "
        "areas, matched_terms, tier, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(law_number) DO UPDATE SET year=excluded.year, name=excluded.name, "
        "promulgated=excluded.promulgated, published=excluded.published, articles=excluded.articles, "
        "text=excluded.text, url=excluded.url, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (law["law_number"], law["year"], law["name"], law["promulgated"], law["published"],
         law["articles"], law["text"], LAW_URL.format(n=law["law_number"], y=law["year"]),
         None if areas is None else uy_store.dumps(areas), uy_store.dumps(terms), tier, today, today))
    return areas


# --- pulls -----------------------------------------------------------------------

def _get(conn, client, today, url, slug, log):
    try:
        return load_json_bytes(client.get_bytes(url, FEED, slug))
    except (FetchError, ValueError) as exc:
        _gap(conn, today, "{0}: {1}".format(slug, str(exc)[:200]))
        log("  [gap] {0}: {1}".format(slug, str(exc)[:120]))
        return None


def pull_members(conn, client, today, log=print):
    records = _get(conn, client, today, MEMBERS_URL, "members", log)
    if records is None:
        return 0, 1
    members = parse_members(records)
    store_members(conn, members, today)
    conn.commit()
    return len(members), 0


def pull_questions(conn, client, today, tax=None, log=print):
    records = _get(conn, client, today, QUESTIONS_URL, "pedidos-informe", log)
    if records is None:
        return 0, 0, 1
    read = ours = 0
    for q in parse_questions(records):
        read += 1
        ours += on_our_ground(store_question(conn, q, tax, today))
    conn.commit()
    return read, ours, 0


def pull_sittings(conn, client, today, log=print):
    records = _get(conn, client, today, SITTINGS_URL, "diario-sesiones", log)
    if records is None:
        return 0, 1
    sittings = parse_sittings(records)
    store_sittings(conn, sittings, today)
    conn.commit()
    return len(sittings), 0


def fetch_law(client, n, year):
    """The law numbered n under `year`, or None. Raises FetchError for
    anything but a not-found (a 404 means the address has no law)."""
    url = LAW_URL.format(n=n, y=year) + "?json=true"
    try:
        raw = client.get_bytes(url, FEED, "law-{0}-{1}".format(n, year), archive=False)
    except FetchError as exc:
        if getattr(exc.cause, "code", None) == 404:
            return None
        raise
    law = parse_law(raw)
    if law is not None and hasattr(client, "_archive"):
        # Archived only when it IS a law: the wrong-year HTML page is not
        # provenance, and the walk asks two addresses for every number.
        client._archive(raw, FEED, "law-{0}-{1}".format(n, year))
    return law


def law_plan(conn, start=None):
    """(holes below the newest stored law, first number to walk, year to try)."""
    rows = conn.execute("SELECT law_number, year FROM uy_laws ORDER BY law_number").fetchall()
    first = start or START_LAW
    if not rows:
        return [], first, None
    have = {r[0] for r in rows}
    top, year = rows[-1]
    holes = [n for n in range(max(first, rows[0][0]), top) if n not in have][:MAX_HOLES]
    return holes, max(top + 1, first), year


def pull_laws(conn, client, today, tax=None, start=None, budget=None, log=print):
    """Ask IMPO for each law after the newest stored one. Returns (stored,
    on our ground, gaps)."""
    client.set_host_throttle("www.impo.com.uy", IMPO_CRAWL_DELAY)
    holes, n, year = law_plan(conn, start)
    this_year = datetime.date.today().year
    stored = ours = 0

    def one(num, yr):
        # The year of the last law found, then the next; with nothing found
        # yet, the last three years (START_LAW is a 2024 law).
        years = (yr, yr + 1) if yr else range(this_year - 2, this_year + 1)
        for y in years:
            if y > this_year:
                break
            law = fetch_law(client, num, y)
            if law is not None:
                return law
        return None

    try:
        for h in holes:
            law = one(h, year - 1 if year else None)
            if law:
                ours += on_our_ground(store_law(conn, law, tax, today))
                stored += 1
        misses = 0
        while misses < MAX_MISSES:
            if budget is not None and budget.exhausted():
                log(budget.disclose("laws", stored))
                break
            law = one(n, year)
            if law is None:
                misses += 1
            else:
                misses = 0
                year = law["year"]
                ours += on_our_ground(store_law(conn, law, tax, today))
                stored += 1
                conn.commit()
            n += 1
    except FetchError as exc:
        conn.commit()
        _gap(conn, today, "IMPO law {0}: {1}".format(n, str(exc)[:200]))
        log("  [gap] IMPO law {0}: {1}".format(n, str(exc)[:120]))
        return stored, ours, 1
    conn.commit()
    return stored, ours, 0


# --- offline -----------------------------------------------------------------------

def reclassify(conn, tax=None, log=print):
    """Re-derive question and law areas, offline, after a taxonomy or
    watchlist change."""
    changed = 0
    for key, tema, areas in conn.execute(
            "SELECT question_key, tema, areas FROM uy_questions").fetchall():
        new, terms, tier = classify(tax, None, tema)
        new_s = None if new is None else uy_store.dumps(new)
        changed += new_s != areas
        conn.execute("UPDATE uy_questions SET areas=?, matched_terms=?, tier=? WHERE question_key=?",
                     (new_s, uy_store.dumps(terms), tier, key))
    for num, name, text, areas in conn.execute(
            "SELECT law_number, name, text, areas FROM uy_laws").fetchall():
        new, terms, tier = classify(tax, "ley:{0}".format(num), name, text)
        new_s = None if new is None else uy_store.dumps(new)
        changed += new_s != areas
        conn.execute("UPDATE uy_laws SET areas=?, matched_terms=?, tier=? WHERE law_number=?",
                     (new_s, uy_store.dumps(terms), tier, num))
    conn.commit()
    log("uy-rollcalls: reclassified; {0} row(s) changed area".format(changed))
    return changed


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731

    def ours(table):
        rows = conn.execute("SELECT areas FROM {0} WHERE areas IS NOT NULL".format(table))
        return sum(on_our_ground(json.loads(a)) for (a,) in rows)
    log("  store: {0} member(s); {1} pedido(s) de informe, {2} on our ground; {3} sitting(s); "
        "{4} law(s), newest {5}, {6} on our ground".format(
            n("SELECT COUNT(*) FROM uy_members"), n("SELECT COUNT(*) FROM uy_questions"),
            ours("uy_questions"), n("SELECT COUNT(*) FROM uy_sittings"),
            n("SELECT COUNT(*) FROM uy_laws"), n("SELECT MAX(law_number) FROM uy_laws"),
            ours("uy_laws")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--taxonomy", help="classify with this taxonomy file "
                                       "(default config/taxonomy-es.yaml when it exists)")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--no-questions", action="store_true")
    ap.add_argument("--no-sittings", action="store_true")
    ap.add_argument("--no-laws", action="store_true")
    ap.add_argument("--from-law", type=int, help="first law number to walk (default {0}, "
                                                 "or after the newest stored)".format(START_LAW))
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored questions and laws, offline")
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
        print("uy-rollcalls: no Spanish taxonomy yet (config/taxonomy-es.yaml); "
              "areas stay NULL, only watchlist-uy lends areas")
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"), throttle=THROTTLE_S)
    today = datetime.date.today().isoformat()
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    if not args.no_members:
        n, g = pull_members(conn, client, today)
        gaps += g
        print("uy-rollcalls: {0} member record(s), {1} gap(s)".format(n, g))
    if not args.no_questions:
        read, ours, g = pull_questions(conn, client, today, tax=tax)
        gaps += g
        print("uy-rollcalls: {0} pedido(s) de informe read, {1} on our ground, {2} gap(s)".format(
            read, ours, g))
    if not args.no_sittings:
        n, g = pull_sittings(conn, client, today)
        gaps += g
        print("uy-rollcalls: {0} Diario de Sesiones record(s), {1} gap(s)".format(n, g))
    if not args.no_laws:
        n, ours, g = pull_laws(conn, client, today, tax=tax, start=args.from_law, budget=budget)
        gaps += g
        print("uy-rollcalls: {0} law(s) stored from IMPO, {1} on our ground, {2} gap(s)".format(
            n, ours, g))
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
