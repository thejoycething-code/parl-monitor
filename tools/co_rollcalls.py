#!/usr/bin/env python3
"""Colombia's Congress: proyectos de ley (both chambers), Cámara plenary
attendance, and the Senate's published plenary roll calls.

    python3 tools/co_rollcalls.py                     # the weekly pull
    python3 tools/co_rollcalls.py --dry-run           # read every source, store nothing
    python3 tools/co_rollcalls.py --reclassify        # re-derive areas, offline
    python3 tools/co_rollcalls.py --db /tmp/co.db --raw-dir /tmp/co-raw   # a scratch run

PHASE 1 (9 October 2026). See docs/colombia-scope.md. No edition reads these
tables yet. Every source is open and keyless:

  * www.camara.gov.co/wp-admin/admin-ajax.php, action get_proyectos_ley_page:
    the Cámara's own bill register, the list its /proyectos-de-ley/ page
    draws. A POST with the page's public nonce (read fresh from the page each
    run; it is the same for every anonymous visitor). 100 rows a page at
    most. Current to the day (426/2026C, filed 1 October, was listed on the
    9th).
  * www.datos.gov.co/resource/kcxp-nxum.json: the same register as open data
    (Socrata), with the 'objeto del proyecto' the listing lacks. It lags the
    site by about three weeks (refreshed 17 September 2026: 302 rows for
    2026-2027 against the site's 402), so the site is the list and the open
    data adds the objeto where it has one.
  * leyes.senado.gov.co/api/search_pdly.php and search_pal.php: the Senate's
    register of proyectos de ley and actos legislativos. A POST per
    legislatura; titles, authors, committee and status, no summary. The
    server drops the connection now and then, so each POST is tried four
    times.
  * www.datos.gov.co/resource/ucmr-52df.json: the Senate's plenary roll calls
    with every senator's yes or no. 16,733 positions, 14 February 2017 to
    25 September 2024; nothing since. Read whole every run (one request) so
    the day the Senate resumes publishing is noticed.
  * www.datos.gov.co/resource/48i3-vuny.json: Cámara plenary attendance, one
    row per representative, one column per sitting (nine sittings, 20 July
    to 25 August 2026, refreshed 18 September).

NO CURRENT ROLL CALLS. Neither chamber publishes the 2026-2030 Congress's
per-member votes in any structured form. They exist only in the Gaceta del
Congreso, months late, and the electronic register is printed there as an
IMAGE (docs/colombia-scope.md, "Votes"). This collector stores what is open;
the edition must say what it cannot see.

CLASSIFICATION: config/watchlist-co.yaml by bill key, and the Spanish
taxonomy (config/taxonomy-es.yaml) once Chris has approved it. Until that
file exists, no bill gets areas from its words. Matching folds accents on
both sides: Colombian titles drop them freely ("GENERO", "PROTECCION").

Separation guarantee: writes co_* tables and the shared gaps table only.
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
import time
import unicodedata
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import co_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "co-rollcalls"
TAXONOMY_ES = os.path.join(ROOT, "config", "taxonomy-es.yaml")
# The country this collector matches for: a shared language list
# (taxonomy-es, -pt, -nl, -it, -fr, -atch) tags a country's own terms
# [only: ...] and filter.load_taxonomy keeps only ours (10 October 2026).
TAXONOMY_COUNTRY = "co"
WATCHLIST = os.path.join(ROOT, "config", "watchlist-co.yaml")

CAMARA_PAGE = "https://www.camara.gov.co/proyectos-de-ley/"
CAMARA_AJAX = "https://www.camara.gov.co/wp-admin/admin-ajax.php"
CAMARA_BILL = "https://www.camara.gov.co/{0}/"
CAMARA_PER_PAGE = 100           # the server caps per_page at 100 (asked for 500, got 100)
SENADO_SEARCH = "https://leyes.senado.gov.co/api/search_{0}.php"   # pdly / pal
DATOS = "https://www.datos.gov.co/resource/{0}.json"
CAMARA_DATASET = "kcxp-nxum"
SENATE_VOTES_DATASET = "ucmr-52df"
ATTENDANCE_DATASET = "48i3-vuny"

# A proyecto may be considered in at most two legislaturas (Constitution,
# art. 162), so the live set is the current legislatura and the one before.
# The Cámara's own ids for them, from the <select> on its register page.
# Oldest first: a bill listed in both (the Senate's 2026-2027 search returns
# a 2025 bill still in passage) keeps the newer legislatura.
LEGISLATURAS = {"2025-2026": "13", "2026-2027": "20"}
POST_TRIES = 4
BUDGET_S = 1800
GAPS_EXIT = 3          # stored what it could, recorded gaps: jobs/co-weekly.sh publishes
HIDDEN_AREAS = {11}    # area 11 is collated, never campaigned


# --- small helpers -----------------------------------------------------------

def deaccent(text):
    """Strip accents, keep case: 'GÉNERO' -> 'GENERO'. Ñ becomes N, which is
    what an accentless title writes anyway."""
    norm = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in norm if not unicodedata.combining(ch))


def name_key(chamber, name):
    folded = re.sub(r"\s+", " ", deaccent(name or "").lower()).strip()
    return "{0}/{1}".format(chamber, folded) if folded else None


def _year(raw):
    year = int(raw)
    return year + 2000 if year < 100 else year


_NUMBER = re.compile(r"^\s*0*(\d+)\s*/\s*(\d{4}|\d{2})(?!\d)\s*([CS])?", re.I)


def bill_key(raw, default_chamber, acto=False):
    """'426/2026C' -> 'camara/2026/426'; '012/2025S' -> 'senado/2025/12';
    '289/26' (Senate register) -> 'senado/2026/289'; '152/26 Acum 157/26'
    -> 'senado/2026/152' (the first number is the bill the others joined).
    'No aplica', '' and None -> None.

    THE SENATE NUMBERS ACTOS LEGISLATIVOS IN A SERIES OF THEIR OWN: in
    2026-2027 the Senate's proyecto de ley 01/26 (animal protection) and its
    acto legislativo 01/26 (sport in article 52) are different bills. So a
    Senate acto legislativo is keyed 'senado/2026/AL1'. The Cámara numbers
    both kinds in one series (402 numbers, 402 bills, 2026-2027), so its keys
    carry no prefix."""
    hit = _NUMBER.match(raw or "")
    if not hit:
        return None
    number, year, letter = hit.groups()
    chamber = {"C": "camara", "S": "senado"}.get((letter or "").upper(), default_chamber)
    prefix = "AL" if (acto and chamber == "senado") else ""
    return "{0}/{1}/{2}{3}".format(chamber, _year(year), prefix, int(number))


def split_key(key):
    chamber, year, number = key.split("/")
    return chamber, int(year), int(number.replace("AL", ""))


def _is_acto(kind):
    return "acto legislativo" in deaccent(kind or "").lower()


_QUESTION_BILL = re.compile(
    r"((?:Proyecto\s+de\s+(?:Ley|Acto\s+Legislativo)|Acto\s+Legislativo)[^0-9]{0,40}?)"
    r"(?:n[uú]mero\s+|No\.?\s*|N[°º]\s*)?0*(\d+)\s+de\s+(\d{4})\s+(Senado|C[aá]mara)", re.I)


def question_bill(text):
    """The bill a roll-call question names: 'Ponencia Para Segundo Debate al
    Proyecto de Ley Orgánica 002 de 2016 Senado, 004 de 2016 Cámara.' ->
    'senado/2016/2'. The first number named wins. 'Proyecto de Acto
    Legislativo 38 de 2019 Senado' -> 'senado/2019/AL38'."""
    hit = _QUESTION_BILL.search(text or "")
    if not hit:
        return None
    lead, number, year, chamber = hit.groups()
    chamber = "senado" if chamber.lower().startswith("s") else "camara"
    acto = "acto" in lead.lower()
    return bill_key("{0}/{1}".format(number, year), chamber, acto)


def _date(raw):
    """'2026 Sep 11 12:00:00 AM', '2026/10/06', '2026-07-20', '1/10/2026' -> ISO, else None."""
    raw = (raw or "").strip()
    for fmt in ("%Y %b %d %I:%M:%S %p", "%Y/%m/%d", "%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def _post(client, url, fields, slug, log=print, sleep=time.sleep):
    """post_form never retries (a POST is not obviously safe to repeat). These
    are read-only searches, and leyes.senado.gov.co drops the connection now
    and then (one of eleven POSTs on 9 October 2026), so try a few times."""
    last = None
    for attempt in range(POST_TRIES):
        try:
            return client.post_form(url, fields, FEED, slug, archive=True)
        except FetchError as exc:
            last = exc
            if attempt + 1 < POST_TRIES:
                log("  retry {0}/{1} {2}: {3}".format(attempt + 1, POST_TRIES - 1, slug,
                                                      str(exc.cause)[:60]))
                sleep(5 * (attempt + 1))
    raise last


# --- classification ----------------------------------------------------------

def load_taxonomy_es(path=TAXONOMY_ES):
    """The Spanish taxonomy with every term accent-folded, or None when the
    file does not exist (it is generated only once Chris approves the list)."""
    if not os.path.exists(path):
        return None
    tax = filt.load_taxonomy(path, country=TAXONOMY_COUNTRY)
    for tiers in tax.terms.values():
        for tier, compiled in tiers.items():
            refolded = []
            for term, _pattern, _cs, guards, vetoes in compiled:
                pattern, cs = filt._compile_term(deaccent(term))
                refolded.append((term, pattern, cs, guards, vetoes))
            tiers[tier] = refolded
    return tax


# The watchlist is applied by key below, so the filter itself gets no entities.
_NO_WATCH = filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify(tax, key, *texts, wl_path=None):
    """(areas, matched_terms, tier) for one bill: the taxonomy over its own
    words (accents folded) and the watchlist by key."""
    areas, terms, tier = set(), [], None
    if tax is not None:
        text = deaccent(" ".join(t for t in texts if t))
        res = filt.filter_item(tax, _NO_WATCH, text)
        areas |= set(res.issue_areas or [])
        terms += list(res.matched_terms or [])
        tier = res.tier
    watched = co_store.watchlist(wl_path or WATCHLIST).get(key)
    if watched:
        areas |= set(watched[0])
        terms.append("watchlist-co:" + key)
        tier = 1 if tier is None else min(tier, 1)
    return sorted(areas), terms, tier


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


# --- the Cámara register -----------------------------------------------------

def parse_camara_items(items, legislatura=None):
    """Rows of the Cámara AJAX listing -> bill dicts."""
    out = []
    for it in items or []:
        key = bill_key(it.get("nro_camara"), "camara")
        if not key:
            continue
        authors = "; ".join(part.split("||")[1] for part in (it.get("autores_pack") or "").split("::")
                            if part.count("||") >= 1)
        others = (it.get("otros_autores") or "").strip()
        out.append({
            "bill_key": key, "other_key": bill_key(it.get("nro_senado"), "senado", _is_acto(it.get("tipo"))),
            "kind": it.get("tipo"), "nickname": (it.get("proyecto") or "").strip() or None,
            "title": (it.get("titulo") or "").strip() or None, "objeto": None,
            "status": it.get("estado"), "origin": it.get("origen"),
            "committee": "; ".join(p.split("||")[1] for p in (it.get("comisiones_pack") or "").split("::")
                                   if p.count("||") >= 1) or None,
            "legislatura": it.get("vigencia") or legislatura,
            "authors": "; ".join(x for x in (authors, others) if x) or None,
            "filed_at": None,
            "url": CAMARA_BILL.format(it["link_web"]) if it.get("link_web") else None,
            "source": "camara.gov.co",
        })
    return out


def parse_camara_datos(rows):
    """Rows of datos.gov.co kcxp-nxum -> {bill_key: bill dict}."""
    out = {}
    for r in rows or []:
        key = bill_key(r.get("no_c_mara"), "camara")
        if not key:
            continue
        link = r.get("link_del_proyecto")
        out[key] = {
            "bill_key": key, "other_key": bill_key(r.get("no_senado"), "senado", _is_acto(r.get("tipo_de_ley"))),
            "kind": r.get("tipo_de_ley"), "nickname": (r.get("proyecto") or "").strip() or None,
            "title": (r.get("t_tulo") or "").strip() or None,
            "objeto": (r.get("objeto_del_proyecto") or "").strip() or None,
            "status": r.get("estado_de_ley"), "origin": r.get("origen_de_ley"),
            "committee": r.get("comisi_n_es_"), "legislatura": r.get("legislatura"),
            "authors": r.get("autores"), "filed_at": _date(r.get("fecha_c_mara")),
            "url": link.get("url") if isinstance(link, dict) else link,
            "source": "datos.gov.co/" + CAMARA_DATASET,
        }
    return out


def camara_nonce(page_html):
    hit = re.search(r'PL_NONCE\s*:\s*"([0-9a-f]+)"', page_html or "")
    return hit.group(1) if hit else None


def pull_camara(client, legislaturas=LEGISLATURAS, log=print, sleep=time.sleep):
    """(bills, gap details) from the Cámara site, then the open data merged in."""
    bills, gaps = {}, []
    try:
        nonce = camara_nonce(client.get_text(CAMARA_PAGE, FEED, "camara-proyectos-page", archive=False))
    except FetchError as exc:
        nonce, gaps = None, gaps + ["camara register page: {0}".format(exc)]
    if nonce is None and not gaps:
        gaps.append("camara register page: no PL_NONCE (page changed?)")
    for leg, leg_id in (legislaturas.items() if nonce else []):
        page, pages = 1, 1
        while page <= pages:
            try:
                raw = _post(client, CAMARA_AJAX, {
                    "action": "get_proyectos_ley_page", "_ajax_nonce": nonce, "page": page,
                    "per_page": CAMARA_PER_PAGE, "term": "", "comision": "", "tipo": "All",
                    "estado": "All", "origen": "All", "legislatura": leg_id, "ley_numero": "",
                    "ley_fecha": "", "comision_adv": "All"},
                    "camara-{0}-p{1}".format(leg, page), log=log, sleep=sleep)
                body = json.loads(raw)
                if not body.get("success"):
                    raise ValueError("success=false: {0}".format(str(body)[:80]))
            except (FetchError, ValueError) as exc:
                gaps.append("camara register {0} page {1}: {2}".format(leg, page, exc))
                break
            data = body.get("data") or {}
            pages = int(data.get("total_pages") or 0)
            for b in parse_camara_items(data.get("items"), leg):
                bills[b["bill_key"]] = b
            page += 1
    # The open data: the objeto for bills the site listed, and the whole row
    # for any it did not (the site failed, or a bill fell off its listing).
    where = "legislatura in({0})".format(",".join("'{0}'".format(x) for x in legislaturas))
    url = DATOS.format(CAMARA_DATASET) + "?$limit=50000&$where=" + quote(where)
    try:
        datos = parse_camara_datos(client.get_json(url, FEED, "datos-" + CAMARA_DATASET))
    except (FetchError, ValueError) as exc:
        datos, gaps = {}, gaps + ["datos.gov.co {0}: {1}".format(CAMARA_DATASET, exc)]
    for key, row in datos.items():
        if key in bills:
            bills[key]["objeto"] = row["objeto"]
            bills[key]["filed_at"] = row["filed_at"]
        else:
            bills[key] = row
    return list(bills.values()), gaps


# --- the Senate register -----------------------------------------------------

def parse_senado(body, legislatura, kind):
    out = []
    for r in (body or {}).get("data") or []:
        key = bill_key(r.get("numero_senado"), "senado", kind == "pal")
        if not key:
            continue
        out.append({
            "bill_key": key, "other_key": bill_key(r.get("numero_camara"), "camara"),
            "kind": "Acto Legislativo" if kind == "pal" else "Proyecto de Ley",
            "nickname": None, "title": (r.get("titulo") or "").strip() or None, "objeto": None,
            "status": r.get("estado"), "origin": None,
            "committee": (r.get("comision") or "").strip() or None, "legislatura": legislatura,
            "authors": (r.get("autor") or "").strip() or None, "filed_at": None,
            "url": "https://leyes.senado.gov.co/api/get_detalle_{0}.php?id={1}".format(kind, r.get("id")),
            "source": "leyes.senado.gov.co",
        })
    return out


def pull_senado(client, legislaturas=LEGISLATURAS, log=print, sleep=time.sleep):
    bills, gaps = {}, []
    for leg in legislaturas:
        for kind in ("pdly", "pal"):
            slug = "senado-{0}-{1}".format(kind, leg)
            try:
                body = json.loads(_post(client, SENADO_SEARCH.format(kind), {"legislatura": leg},
                                        slug, log=log, sleep=sleep))
            except (FetchError, ValueError) as exc:
                gaps.append("senado register {0} {1}: {2}".format(kind, leg, exc))
                continue
            rows = parse_senado(body, leg, kind)
            if int(body.get("total_results") or 0) != len(body.get("data") or []):
                gaps.append("senado register {0} {1}: total_results {2} but {3} rows".format(
                    kind, leg, body.get("total_results"), len(body.get("data") or [])))
            for b in rows:
                bills[b["bill_key"]] = b
    return list(bills.values()), gaps


# --- storing bills -----------------------------------------------------------

def store_bill(conn, tax, b, today, wl_path=None):
    chamber, year, number = split_key(b["bill_key"])
    areas, terms, tier = classify(tax, b["bill_key"], b.get("nickname"), b.get("title"),
                                  b.get("objeto"), wl_path=wl_path)
    cols = ("other_key", "kind", "nickname", "title", "objeto", "status", "origin", "committee",
            "legislatura", "authors", "filed_at", "url", "source")
    conn.execute(
        "INSERT INTO co_bills (bill_key, chamber, year, number, {0}, areas, matched_terms, tier, "
        "first_seen, last_seen) VALUES (?,?,?,?,{1},?,?,?,?,?) ON CONFLICT(bill_key) DO UPDATE SET "
        "{2}, areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen".format(
            ", ".join(cols), ",".join("?" * len(cols)),
            ", ".join("{0}=COALESCE(excluded.{0}, co_bills.{0})".format(c) for c in cols)),
        (b["bill_key"], chamber, year, number) + tuple(b.get(c) for c in cols)
        + (co_store.dumps(areas), co_store.dumps(terms), tier, today, today))
    return areas


# --- Cámara attendance -------------------------------------------------------

_SESSION = re.compile(r"^sesi_n_plenaria_(cp_)?(\d{2})_(\d{2})_(\d{4})(?:_\d+)?$")


def parse_attendance(rows):
    """(members, attendance) from datos.gov.co 48i3-vuny: one row per
    representative ('sesion' holds the NAME), one column per sitting."""
    members, marks = [], []
    for r in rows or []:
        key = name_key("camara", r.get("sesion"))
        if not key:
            continue
        members.append({"member_key": key, "chamber": "camara", "name": r.get("sesion"),
                        "party": r.get("partido_politico"), "department": r.get("departamento"),
                        "source": "datos.gov.co/" + ATTENDANCE_DATASET})
        for col, val in r.items():
            hit = _SESSION.match(col)
            if not hit:
                continue
            cp, dd, mm, yyyy = hit.groups()
            marks.append({"member_key": key, "session": col,
                          "date": "{0}-{1}-{2}".format(yyyy, mm, dd), "joint": 1 if cp else 0,
                          "status": (val or "").strip() or None})
    return members, marks


def store_member(conn, m, today):
    conn.execute(
        "INSERT INTO co_members (member_key, chamber, name, party, department, source, first_seen, "
        "last_seen) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(member_key) DO UPDATE SET "
        "name=excluded.name, party=COALESCE(excluded.party, co_members.party), "
        "department=COALESCE(excluded.department, co_members.department), "
        "source=excluded.source, last_seen=excluded.last_seen",
        (m["member_key"], m["chamber"], m["name"], m.get("party"), m.get("department"),
         m.get("source"), today, today))


def pull_attendance(conn, client, today):
    rows = client.get_json(DATOS.format(ATTENDANCE_DATASET) + "?$limit=5000", FEED,
                           "datos-" + ATTENDANCE_DATASET)
    members, marks = parse_attendance(rows)
    for m in members:
        store_member(conn, m, today)
    conn.executemany(
        "INSERT INTO co_attendance (member_key, session, date, joint, status) VALUES (?,?,?,?,?) "
        "ON CONFLICT(member_key, session) DO UPDATE SET status=excluded.status",
        [(x["member_key"], x["session"], x["date"], x["joint"], x["status"]) for x in marks])
    return len(members), len({x["session"] for x in marks})


# --- the Senate's published roll calls ---------------------------------------

def division_key(chamber, date, question):
    digest = hashlib.sha1((question or "").strip().encode("utf-8")).hexdigest()[:10]
    return "{0}-{1}-{2}".format(chamber, date, digest)


def parse_senate_votes(rows):
    """Rows of datos.gov.co ucmr-52df (fecha, fullname, proyecto, vote) ->
    {division_key: division}. One division is one question on one day."""
    divisions = {}
    for r in rows or []:
        date = _date(r.get("fecha"))
        question = (r.get("proyecto") or "").strip()
        member = name_key("senado", r.get("fullname"))
        vote = (r.get("vote") or "").strip().lower()
        if not (date and question and member):
            continue
        key = division_key("senado", date, question)
        d = divisions.setdefault(key, {"division_key": key, "chamber": "senado", "date": date,
                                       "question": question, "bill_key": question_bill(question),
                                       "votes": {}, "names": {}})
        d["votes"][member] = {"si": "yes", "sí": "yes", "no": "no"}.get(vote, vote)
        d["names"][member] = r.get("fullname").strip()
    return divisions


def _bill_areas(conn, key):
    row = conn.execute("SELECT areas FROM co_bills WHERE bill_key=?", (key,)).fetchone() if key else None
    return json.loads(row[0] or "[]") if row else []


def pull_senate_votes(conn, client, today):
    rows = client.get_json(DATOS.format(SENATE_VOTES_DATASET) + "?$limit=100000", FEED,
                           "datos-" + SENATE_VOTES_DATASET)
    divisions = parse_senate_votes(rows)
    for d in divisions.values():
        for member, name in d["names"].items():
            conn.execute("INSERT INTO co_members (member_key, chamber, name, source, first_seen, "
                         "last_seen) VALUES (?,?,?,?,?,?) ON CONFLICT(member_key) DO UPDATE SET "
                         "last_seen=excluded.last_seen",
                         (member, "senado", name, "datos.gov.co/" + SENATE_VOTES_DATASET, today, today))
        yes = sum(1 for v in d["votes"].values() if v == "yes")
        no = sum(1 for v in d["votes"].values() if v == "no")
        conn.execute(
            "INSERT INTO co_divisions (division_key, chamber, date, question, bill_key, yes, no, "
            "source, areas, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(division_key) DO UPDATE SET yes=excluded.yes, no=excluded.no, "
            "bill_key=excluded.bill_key, last_seen=excluded.last_seen",
            (d["division_key"], "senado", d["date"], d["question"], d["bill_key"], yes, no,
             "datos.gov.co/" + SENATE_VOTES_DATASET,
             co_store.dumps(_bill_areas(conn, d["bill_key"])), today, today))
        conn.executemany(
            "INSERT INTO co_votes (division_key, member_key, position) VALUES (?,?,?) "
            "ON CONFLICT(division_key, member_key) DO UPDATE SET position=excluded.position",
            [(d["division_key"], m, v) for m, v in d["votes"].items()])
    latest = max((d["date"] for d in divisions.values()), default=None)
    return len(divisions), sum(len(d["votes"]) for d in divisions.values()), latest


# --- reclassify, summary, main -----------------------------------------------

def reclassify(conn, tax=None, wl_path=None, log=print):
    """Re-derive every stored bill's areas (taxonomy-es + watchlist-co), then
    let divisions inherit from their bills. Offline."""
    tax = load_taxonomy_es() if tax is None else tax
    n = 0
    for key, nick, title, objeto in conn.execute(
            "SELECT bill_key, nickname, title, objeto FROM co_bills").fetchall():
        areas, terms, tier = classify(tax, key, nick, title, objeto, wl_path=wl_path)
        conn.execute("UPDATE co_bills SET areas=?, matched_terms=?, tier=? WHERE bill_key=?",
                     (co_store.dumps(areas), co_store.dumps(terms), tier, key))
        n += 1
    for dkey, bkey in conn.execute("SELECT division_key, bill_key FROM co_divisions").fetchall():
        conn.execute("UPDATE co_divisions SET areas=? WHERE division_key=?",
                     (co_store.dumps(_bill_areas(conn, bkey)), dkey))
    conn.commit()
    log("co-rollcalls: reclassified {0} bill(s){1}".format(
        n, "" if tax is not None else " (no config/taxonomy-es.yaml yet: watchlist-co only)"))
    return n


def summary(conn, log=print):
    def n(sql):
        return conn.execute(sql).fetchone()[0]

    def ours(table):
        return sum(1 for (a,) in conn.execute("SELECT areas FROM {0}".format(table))
                   if on_our_ground(json.loads(a or "[]")))

    log("store: co_bills {0} ({1} on our ground; camara {2}, senado {3}), co_members {4}, "
        "co_attendance {5}, co_divisions {6} ({7} on our ground), co_votes {8}".format(
            n("SELECT COUNT(*) FROM co_bills"), ours("co_bills"),
            n("SELECT COUNT(*) FROM co_bills WHERE chamber='camara'"),
            n("SELECT COUNT(*) FROM co_bills WHERE chamber='senado'"),
            n("SELECT COUNT(*) FROM co_members"), n("SELECT COUNT(*) FROM co_attendance"),
            n("SELECT COUNT(*) FROM co_divisions"), ours("co_divisions"),
            n("SELECT COUNT(*) FROM co_votes")))


def make_client(raw_dir=None):
    client = HttpClient(raw_dir=raw_dir or os.path.join(ROOT, "data", "raw"))
    # Small government servers: a second between requests to each.
    for host in ("www.camara.gov.co", "leyes.senado.gov.co", "www.datos.gov.co"):
        client.set_host_throttle(host, 1.0)
    return client


def run(conn, client, today, tax=None, log=print, sleep=time.sleep, budget=None,
        do_bills=True, do_attendance=True, do_votes=True):
    """One weekly pull. Returns the number of gaps recorded."""
    gaps = 0
    if do_bills:
        for name, puller in (("camara", pull_camara), ("senado", pull_senado)):
            bills, g = puller(client, log=log, sleep=sleep)
            for b in bills:
                store_bill(conn, tax, b, today)
            for detail in g:
                _gap(conn, today, detail)
                log("  [gap] " + detail[:110])
            gaps += len(g)
            conn.commit()
            log("co-rollcalls: {0} register: {1} bill(s), {2} on our ground, {3} gap(s)".format(
                name, len(bills),
                sum(1 for b in bills if on_our_ground(_bill_areas(conn, b["bill_key"]))), len(g)))
    if do_attendance:
        try:
            members, sessions = pull_attendance(conn, client, today)
            log("co-rollcalls: Cámara attendance: {0} representative(s), {1} sitting(s)".format(
                members, sessions))
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "attendance {0}: {1}".format(ATTENDANCE_DATASET, exc))
            log("  [gap] attendance: {0}".format(str(exc)[:90]))
            gaps += 1
        conn.commit()
    if do_votes:
        try:
            divisions, votes, latest = pull_senate_votes(conn, client, today)
            log("co-rollcalls: Senate published roll calls: {0} division(s), {1} position(s), "
                "latest {2}".format(divisions, votes, latest))
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "senate votes {0}: {1}".format(SENATE_VOTES_DATASET, exc))
            log("  [gap] senate votes: {0}".format(str(exc)[:90]))
            gaps += 1
        conn.commit()
    return gaps


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", help="archive raw payloads here instead of data/raw "
                    "(for a scratch run beside --db)")
    ap.add_argument("--no-bills", action="store_true")
    ap.add_argument("--no-attendance", action="store_true")
    ap.add_argument("--no-votes", action="store_true")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored bills and divisions, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true",
                    help="read every source into a throwaway in-memory store")
    args = ap.parse_args()
    today = datetime.date.today().isoformat()
    if args.reclassify:
        conn = db.init_db(db.connect(args.db))
        reclassify(conn)
        summary(conn)
        conn.close()
        return 0
    client = make_client(args.raw_dir)
    conn = db.init_db(db.connect(":memory:" if args.dry_run else args.db))
    tax = load_taxonomy_es()
    if tax is None:
        print("co-rollcalls: no config/taxonomy-es.yaml yet; areas come from watchlist-co only")
    gaps = run(conn, client, today, tax=tax, budget=drain.Budget(args.budget_seconds),
               do_bills=not args.no_bills, do_attendance=not args.no_attendance,
               do_votes=not args.no_votes)
    reclassify(conn, tax=tax, log=lambda *_: None)
    summary(conn)
    conn.close()
    return GAPS_EXIT if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
