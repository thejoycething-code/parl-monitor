"""The Dominican Republic's Congress, phase 1: the Camara de Diputados'
iniciativas, plenary sessions, recorded votes and each deputy's position,
from the Chamber's SIL Ciudadano. Built 9 October 2026; see
docs/dominican-republic-scope.md for every number behind it.

    python3 tools/do_rollcalls.py                    # bills, sessions, votes, members
    python3 tools/do_rollcalls.py --period 2020-2024 # also that period's iniciativas
    python3 tools/do_rollcalls.py --reclassify       # offline, after a taxonomy change

SOURCE: the JSON API behind the SIL Ciudadano front end
(https://www.diputadosrd.gob.do/sil/), open and keyless. Every request
carries `periodoId` (2761 = 2024-2028, 2760 = 2020-2024, from
`api/periodolegislativo/all`). Pages are ten rows and the size cannot be
changed.

  * Iniciativas: `api/iniciativa/getIniciativas?page=N&keyword=` (newest
    number first). The whole current period is re-read every week (about
    650 pages), so every status is current, as for Peru's proyectos.
  * Sessions: `api/sesion/sesiones?page=N&keyword=` (newest first); a
    session's votes: `api/sesion/votaciones?page=N&id=<sesionId>`.
  * A vote's iniciativas: `api/votacion/iniciativas/?page=1&id=<votacion>`.
    The motion text rarely names the bill ("Sometido a votacion el proyecto
    de ley, en segunda discusion"), so this link is what lets a vote inherit
    its bill's areas.
  * Positions: `api/votacion/legisladores/?page=N&id=<votacion>`, ten a
    page. Read for votes on our ground or on a watched bill, and for
    contested votes (any No) of the last CONTESTED_DAYS days.
  * Members: `api/legislador/legisladores?page=N&keyword=a` (the list needs
    a keyword; 'a' and 'o' between them return everyone), plus every
    deputy a vote record names.

CLASSIFICATION. `config/taxonomy-es.yaml` when it exists (Chris approves the
Spanish term list in the scope doc first); until then the English
`config/taxonomy.yaml`, which is blind to Spanish and is used only so the
plumbing runs. Text and terms are accent-folded before matching.
`config/watchlist-do.yaml` adds areas by iniciativa key, never by title.
A vote's areas are its motion's own plus those of the iniciativas it is
linked to.

Exit codes: 0 clean; 3 stored what it could and recorded gaps (the job
script publishes that run); anything else, nothing worth publishing.
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

from src import db, do_store, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "do-rollcalls"
HOST = "www.diputadosrd.gob.do"
API = "https://www.diputadosrd.gob.do/sil/api/"
HOST_THROTTLE_S = 1.0
PERIODS = {"2024-2028": 2761, "2020-2024": 2760}
CURRENT_PERIOD = "2024-2028"
TAXONOMY_ES = os.path.join(ROOT, "config", "taxonomy-es.yaml")
TAXONOMY_EN = os.path.join(ROOT, "config", "taxonomy.yaml")
# The country this collector matches for: a shared language list
# (taxonomy-es, -pt, -nl, -it, -fr, -atch) tags a country's own terms
# [only: ...] and filter.load_taxonomy keeps only ours (10 October 2026).
TAXONOMY_COUNTRY = "do"
BUDGET_S = 2700.0
HIDDEN_AREAS = (11,)   # migration is collated, never campaigned
PAGE = 10              # the SIL's fixed page size
CONTESTED_DAYS = 30    # contested votes older than this keep their header only
SESSION_LOOKBACK_DAYS = 21   # sessions this recent are re-read (late uploads)
MEMBER_KEYWORDS = ("a", "o")
BILL_NUMBER = re.compile(r"\b(\d{5})-(\d{4})-(\d{4})-CD\b")


# --- text helpers --------------------------------------------------------------

def fold(text):
    """Accents off, case kept: 'Proposición' -> 'Proposicion', 'ñ' -> 'n'."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _fold_tree(value):
    if isinstance(value, str):
        return fold(value)
    if isinstance(value, list):
        return [_fold_tree(v) for v in value]
    if isinstance(value, dict):
        return {k: _fold_tree(v) for k, v in value.items()}
    return value


def taxonomy_path():
    return TAXONOMY_ES if os.path.exists(TAXONOMY_ES) else TAXONOMY_EN


def load_taxonomy(path=None):
    """The taxonomy with every term accent-folded, through filter's own loader
    (so guards, vetoes and inner stars behave exactly as elsewhere)."""
    import yaml
    with open(path or taxonomy_path(), "r", encoding="utf-8") as handle:
        raw = _fold_tree(yaml.safe_load(handle))
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False,
                                     encoding="utf-8") as tmp:
        yaml.safe_dump(raw, tmp, allow_unicode=True)
    try:
        return filt.load_taxonomy(tmp.name, country=TAXONOMY_COUNTRY)
    finally:
        os.unlink(tmp.name)


def empty_watchlist():
    """watchlist-do is applied by KEY (do_store.add_watch_areas)."""
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _date(value):
    return (value or "")[:10] or None


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))
    print("[gap] " + detail)


def make_client():
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    client.set_host_throttle(HOST, HOST_THROTTLE_S)
    return client


def api(path, period_id, **params):
    query = "&".join("{0}={1}".format(k, v) for k, v in params.items())
    return "{0}{1}?{2}{3}periodoId={4}".format(API, path, query, "&" if query else "",
                                              period_id)


# --- bills -----------------------------------------------------------------------

def parse_bill(rec):
    return {
        "bill_key": (rec.get("numero") or "").strip(),
        "sil_id": rec.get("id"),
        "period": (rec.get("periodoRegistro") or "").strip() or None,
        "kind": (rec.get("tipo") or "").strip() or None,
        "origin": (rec.get("camaraInicio") or rec.get("origen") or "").strip() or None,
        "title": _clean(rec.get("descripcion")),
        "subject": (rec.get("materia") or "").strip() or None,
        "topic_group": (rec.get("grupo") or "").strip() or None,
        "status": (rec.get("estado") or "").strip() or None,
        "condition": (rec.get("condicion") or "").strip() or None,
        "deposited": _date(rec.get("fechaDeposito")),
        "taken_up": _date(rec.get("fechaIniciado")),
        "law_number": (str(rec.get("numPromulgacion")).strip()
                       if rec.get("numPromulgacion") not in (None, "") else None),
        "promulgated": _date(rec.get("fechaPromulgacion")),
        "last_change": (rec.get("fechaUltimoCambioPrincipal") or "")[:19] or None,
    }


def classify_bill(tax, wl, b, watch=None):
    text = fold(" ".join(x for x in (b["title"], b.get("subject") or "") if x))
    res = filt.filter_item(tax, wl, fold(b["title"]), text, title=fold(b["title"]))
    return do_store.add_watch_areas(res, b["bill_key"], wl=watch)


def store_bill(conn, b, res, today):
    if not b["period"]:
        hit = BILL_NUMBER.search(b["bill_key"])
        b["period"] = "{0}-{1}".format(hit.group(2), hit.group(3)) if hit else "?"
    conn.execute(
        "INSERT INTO do_bills (bill_key, sil_id, period, kind, origin, title, subject, "
        "topic_group, status, condition, deposited, taken_up, law_number, promulgated, "
        "last_change, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(bill_key) DO UPDATE SET sil_id=excluded.sil_id, kind=excluded.kind, "
        "origin=excluded.origin, title=excluded.title, subject=excluded.subject, "
        "topic_group=excluded.topic_group, status=excluded.status, "
        "condition=excluded.condition, deposited=excluded.deposited, "
        "taken_up=excluded.taken_up, law_number=excluded.law_number, "
        "promulgated=excluded.promulgated, last_change=excluded.last_change, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen",
        (b["bill_key"], b["sil_id"], b["period"], b["kind"], b["origin"], b["title"],
         b["subject"], b["topic_group"], b["status"], b["condition"], b["deposited"],
         b["taken_up"], b["law_number"], b["promulgated"], b["last_change"],
         do_store.dumps(res.issue_areas),
         do_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
         res.tier, today, today))


def pull_bills(conn, client, today, period=CURRENT_PERIOD, tax=None, wl=None, watch=None,
               log=print, budget=None):
    """Every iniciativa of a period, newest first. Returns (read, ours, gaps)."""
    tax = tax if tax is not None else load_taxonomy()
    wl = wl if wl is not None else empty_watchlist()
    watch = watch if watch is not None else do_store.watchlist()
    pid = PERIODS[period]
    read = ours = gaps = 0
    page, total = 1, None
    while total is None or (page - 1) * PAGE < total:
        if budget is not None and budget.exhausted():
            log(budget.disclose("iniciativa pages", page - 1))
            _gap(conn, today, "budget spent before iniciativas {0} page {1}".format(period, page))
            return read, ours, gaps + 1
        url = api("iniciativa/getIniciativas", pid, page=page, keyword="")
        try:
            reply = client.get_json(url, FEED, "bills-{0}-p{1}".format(period, page))
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "iniciativas {0} page {1}: {2}".format(period, page, exc))
            gaps += 1
            page += 1
            if total is None or gaps >= 5:
                break   # no first page, or the host is down: do not walk 600 pages of failures
            continue
        total = int(reply.get("total") or 0)
        rows = reply.get("results") or []
        if not rows:
            break
        for rec in rows:
            b = parse_bill(rec)
            if not b["bill_key"]:
                continue
            res = classify_bill(tax, wl, b, watch)
            store_bill(conn, b, res, today)
            read += 1
            ours += on_our_ground(res.issue_areas)
        if page % 50 == 0:
            conn.commit()
        page += 1
    conn.commit()
    return read, ours, gaps


def fetch_bill(conn, client, today, sil_id, period_id, tax, wl, watch):
    """One iniciativa by SIL id (a vote's bill from another period, say)."""
    url = api("iniciativa/iniciativa/{0}".format(sil_id), period_id)
    rec = client.get_json(url, FEED, "bill-{0}".format(sil_id))
    b = parse_bill(rec)
    if b["bill_key"]:
        store_bill(conn, b, classify_bill(tax, wl, b, watch), today)
    return b["bill_key"] or None


# --- members ---------------------------------------------------------------------

def parse_member(rec):
    lid = rec.get("legisladorId")
    party = (rec.get("partido") or {}).get("siglas")
    rep = rec.get("representacion") or {}
    return {
        "member_key": "cd/{0}".format(lid),
        "legislador_id": lid,
        "name": _clean(rec.get("nombreCompleto")
                       or "{0} {1}".format(rec.get("nombres") or "", rec.get("apellidos") or "")),
        "role": rec.get("funcion") or rep.get("funcion"),
        "party": (party or "").strip() or None,
        "province": rec.get("provincia") or rep.get("provincia"),
        "constituency": rec.get("circunscripcion") or rep.get("circunscripcion"),
        "period": rec.get("periodo") or rep.get("periodo"),
    }


def store_member(conn, m, today, overwrite_name=True):
    """Upsert; a vote record's name ('SURNAMES GIVEN') never replaces the
    member list's ('Given Surnames'), and empty fields never blank a known one."""
    name_sql = "excluded.name" if overwrite_name else "COALESCE(do_members.name, excluded.name)"
    conn.execute(
        "INSERT INTO do_members (member_key, legislador_id, name, role, party, province, "
        "constituency, period, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(member_key) DO UPDATE SET name={0}, "
        "role=COALESCE(excluded.role, do_members.role), "
        "party=COALESCE(excluded.party, do_members.party), "
        "province=COALESCE(excluded.province, do_members.province), "
        "constituency=COALESCE(excluded.constituency, do_members.constituency), "
        "period=COALESCE(excluded.period, do_members.period), "
        "last_seen=excluded.last_seen".format(name_sql),
        (m["member_key"], m["legislador_id"], m["name"], m["role"], m["party"],
         m["province"], m["constituency"], m["period"], today, today))


def is_legislator(m):
    role = (m.get("role") or "").lower()
    return role.startswith("diputad") or role.startswith("senador")


def pull_members(conn, client, today, period=CURRENT_PERIOD, log=print):
    """The SIL's legislator list, under each keyword. Returns (stored, gaps).
    The list also holds the institutions that may propose laws (Poder
    Ejecutivo, Suprema Corte, Junta Central Electoral); those are skipped."""
    pid = PERIODS[period]
    seen, gaps = set(), 0
    for kw in MEMBER_KEYWORDS:
        page, total = 1, None
        while total is None or (page - 1) * PAGE < total:
            url = api("legislador/legisladores", pid, page=page, keyword=kw)
            try:
                reply = client.get_json(url, FEED, "members-{0}-p{1}".format(kw, page))
            except (FetchError, ValueError) as exc:
                _gap(conn, today, "members '{0}' page {1}: {2}".format(kw, page, exc))
                gaps += 1
                break
            total = int(reply.get("total") or 0)
            rows = reply.get("results") or []
            if not rows:
                break
            for rec in rows:
                m = parse_member(rec)
                if m["legislador_id"] and is_legislator(m) and m["member_key"] not in seen:
                    m["period"] = m["period"] or period
                    store_member(conn, m, today)
                    seen.add(m["member_key"])
            page += 1
    conn.commit()
    log("do-rollcalls: {0} legislator(s) from the SIL list".format(len(seen)))
    return len(seen), gaps


# --- sessions and votes ------------------------------------------------------------

def parse_session(rec, period):
    return {
        "session_id": rec["sesionId"],
        "number": rec.get("numeroSesion"),
        "date": _date(rec.get("fecha")),
        "kind": rec.get("tipo"),
        "status": rec.get("estado"),
        "legislature": rec.get("legislatura"),
        "period": period,
    }


def parse_division(rec):
    votos = rec.get("votos") or {}
    asis = rec.get("asistencias") or {}
    sesion = rec.get("sesion") or {}
    motion = (rec.get("mocion") or "").strip()
    return {
        "division_key": "cd/{0}".format(rec["id"]),
        "votacion_id": rec["id"],
        "session_id": rec.get("sesionId"),
        "session_number": sesion.get("numero"),
        "number": rec.get("numeroVotacion"),
        "date": _date(rec.get("fecha")),
        "title": _clean(rec.get("titulo")),
        "motion": motion,
        "yes": votos.get("cantidadVotosSi"),
        "no": votos.get("cantidadVotosNo"),
        "abstain": votos.get("cantidadVotosAbastencion"),
        "total_votes": votos.get("cantidadTotalVotos"),
        "present": asis.get("cantidadPresentes"),
        "members": asis.get("cantidadDelegados"),
        "linked_number": (rec.get("iniciativaNumero") or "").strip() or None,
    }


def motion_bill_refs(motion):
    """Iniciativa numbers the motion names itself, in order, deduplicated."""
    out = []
    for hit in BILL_NUMBER.finditer(motion or ""):
        key = hit.group(0)
        if key not in out:
            out.append(key)
    return out


def bill_areas(conn, keys):
    areas = set()
    for key in keys:
        row = conn.execute("SELECT areas FROM do_bills WHERE bill_key=?", (key,)).fetchone()
        if row and row[0]:
            areas.update(json.loads(row[0]))
    return sorted(areas)


def classify_division(tax, wl, d, linked_areas):
    own = filt.filter_item(tax, wl, fold(d["motion"]), title="")
    return own, sorted(set(own.issue_areas or []) | set(linked_areas or []))


def is_contested(d):
    return bool((d.get("no") or 0) > 0 or (d.get("abstain") or 0) > 0)


def wants_positions(d, areas, refs, watch, today, contested_days=CONTESTED_DAYS):
    if on_our_ground(areas) or any(r in watch for r in refs):
        return True
    if not is_contested(d) or not d.get("date"):
        return False
    age = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(d["date"])).days
    return age <= contested_days


def store_division(conn, d, refs, own, areas, today):
    conn.execute(
        "INSERT INTO do_divisions (division_key, session_id, session_number, number, date, "
        "title, motion, yes, no, abstain, total_votes, present, members, bill_refs, "
        "own_areas, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET session_number=excluded.session_number, "
        "number=excluded.number, date=excluded.date, title=excluded.title, "
        "motion=excluded.motion, yes=excluded.yes, no=excluded.no, abstain=excluded.abstain, "
        "total_votes=excluded.total_votes, present=excluded.present, members=excluded.members, "
        "bill_refs=excluded.bill_refs, own_areas=excluded.own_areas, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (d["division_key"], d["session_id"], d["session_number"], d["number"], d["date"],
         d["title"], d["motion"], d["yes"], d["no"], d["abstain"], d["total_votes"],
         d["present"], d["members"], do_store.dumps(refs), do_store.dumps(own.issue_areas),
         do_store.dumps(areas), do_store.dumps(own.matched_terms), own.tier, today, today))


def parse_position(rec):
    leg = rec.get("legislador") or {}
    lid = leg.get("legisladorId")
    if not lid:
        return None
    return {
        "member_key": "cd/{0}".format(lid),
        "legislador_id": lid,
        "name": _clean(leg.get("nombreCompleto")
                       or "{0} {1}".format(leg.get("nombres") or "", leg.get("apellidos") or "")),
        "party": ((leg.get("partido") or {}).get("siglas") or "").strip() or None,
        "position": (rec.get("votoId") or "").strip() or None,
        "label": (rec.get("voto") or "").strip() or None,
    }


def pull_positions(conn, client, today, d, period_id):
    """Every deputy's position on one vote. Returns the count stored; raises
    FetchError (the caller records the gap, and the vote stays unread)."""
    rows, page, total = [], 1, None
    while total is None or (page - 1) * PAGE < total:
        url = api("votacion/legisladores/", period_id, page=page, id=d["votacion_id"])
        reply = client.get_json(url, FEED, "positions-{0}-p{1}".format(d["votacion_id"], page))
        total = int(reply.get("total") or 0)
        batch = reply.get("results") or []
        if not batch:
            break
        rows.extend(batch)
        page += 1
    stored = 0
    for rec in rows:
        p = parse_position(rec)
        if not p:
            continue
        conn.execute("INSERT OR REPLACE INTO do_votes (division_key, member_key, name, party, "
                     "position, label) VALUES (?,?,?,?,?,?)",
                     (d["division_key"], p["member_key"], p["name"], p["party"],
                      p["position"], p["label"]))
        store_member(conn, {"member_key": p["member_key"], "legislador_id": p["legislador_id"],
                            "name": p["name"], "role": None, "party": p["party"],
                            "province": None, "constituency": None, "period": None},
                     today, overwrite_name=False)
        stored += 1
    conn.execute("UPDATE do_divisions SET positions_read=1, positions=? WHERE division_key=?",
                 (stored, d["division_key"]))
    return stored


def linked_bills(conn, client, today, d, period_id, tax, wl, watch):
    """The iniciativas the SIL links to a vote, as bill keys, fetching any
    the store does not hold yet. Raises FetchError."""
    url = api("votacion/iniciativas/", period_id, page=1, id=d["votacion_id"])
    reply = client.get_json(url, FEED, "vote-bills-{0}".format(d["votacion_id"]))
    keys = []
    for rec in reply.get("results") or []:
        key = (rec.get("iniciativaNumero") or (rec.get("iniciativa") or {}).get("numero") or "").strip()
        sil_id = rec.get("iniciativaId")
        if not key:
            continue
        if sil_id and not conn.execute("SELECT 1 FROM do_bills WHERE bill_key=?", (key,)).fetchone():
            try:
                fetch_bill(conn, client, today, sil_id, period_id, tax, wl, watch)
            except (FetchError, ValueError):
                pass   # the key still stands; its areas arrive with the next bill pass
        if key not in keys:
            keys.append(key)
    return keys


def session_votes(client, sid, period_id):
    """Every vote header of a session (paged). Raises FetchError."""
    out, page, total = [], 1, None
    while total is None or (page - 1) * PAGE < total:
        url = api("sesion/votaciones", period_id, page=page, id=sid)
        reply = client.get_json(url, FEED, "session-votes-{0}-p{1}".format(sid, page))
        total = int(reply.get("total") or 0)
        rows = reply.get("results") or []
        if not rows:
            break
        out.extend(rows)
        page += 1
    return out


def sessions_to_read(conn, client, today, period, log=print):
    """Session list, newest first, until the sessions are older than the
    lookback and already read. Stores every session seen. Raises FetchError
    on the first page only."""
    pid = PERIODS[period]
    cutoff = (datetime.date.fromisoformat(today)
              - datetime.timedelta(days=SESSION_LOOKBACK_DAYS)).isoformat()
    todo, page, total = [], 1, None
    while total is None or (page - 1) * PAGE < total:
        url = api("sesion/sesiones", pid, page=page, keyword="")
        reply = client.get_json(url, FEED, "sessions-{0}-p{1}".format(period, page))
        total = int(reply.get("total") or 0)
        rows = reply.get("results") or []
        if not rows:
            break
        stop = False
        for rec in rows:
            s = parse_session(rec, period)
            known = conn.execute("SELECT votes_read FROM do_sessions WHERE session_id=?",
                                 (s["session_id"],)).fetchone()
            conn.execute(
                "INSERT INTO do_sessions (session_id, number, date, kind, status, legislature, "
                "period, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(session_id) DO UPDATE SET number=excluded.number, "
                "date=excluded.date, kind=excluded.kind, status=excluded.status, "
                "legislature=excluded.legislature, last_seen=excluded.last_seen",
                (s["session_id"], s["number"], s["date"], s["kind"], s["status"],
                 s["legislature"], s["period"], today, today))
            if known and known[0] and (s["date"] or "") < cutoff:
                stop = True
                continue
            todo.append(s)
        if stop:
            break
        page += 1
    conn.commit()
    # Oldest first, so a budget cut leaves a clean frontier for the next run.
    return sorted(todo, key=lambda s: (s["date"] or "", s["session_id"]))


def pull_votes(conn, client, today, period=CURRENT_PERIOD, tax=None, wl=None, watch=None,
               log=print, budget=None, contested_days=CONTESTED_DAYS):
    """Sessions not yet read (and the recent ones again), their votes, each
    vote's iniciativas, and positions where wanted.
    Returns (divisions, ours, positions_read, gaps)."""
    tax = tax if tax is not None else load_taxonomy()
    wl = wl if wl is not None else empty_watchlist()
    watch = watch if watch is not None else do_store.watchlist()
    pid = PERIODS[period]
    stored = ours = with_positions = gaps = 0
    try:
        todo = sessions_to_read(conn, client, today, period, log=log)
    except (FetchError, ValueError) as exc:
        _gap(conn, today, "session list {0}: {1}".format(period, exc))
        return 0, 0, 0, 1
    for s in todo:
        if budget is not None and budget.exhausted():
            log(budget.disclose("votes", stored))
            _gap(conn, today, "budget spent before session {0} ({1}) was read".format(
                s["number"], s["date"]))
            return stored, ours, with_positions, gaps + 1
        try:
            recs = session_votes(client, s["session_id"], pid)
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "votes of session {0}: {1}".format(s["number"], exc))
            gaps += 1
            continue
        complete = True
        for rec in recs:
            d = parse_division(rec)
            row = conn.execute("SELECT bill_refs, positions_read FROM do_divisions "
                               "WHERE division_key=?", (d["division_key"],)).fetchone()
            if row is not None:
                refs = json.loads(row[0] or "[]")
            else:
                try:
                    refs = linked_bills(conn, client, today, d, pid, tax, wl, watch)
                except (FetchError, ValueError) as exc:
                    _gap(conn, today, "iniciativas of vote {0}: {1}".format(d["division_key"], exc))
                    gaps += 1
                    complete = False
                    continue
            for key in motion_bill_refs(d["motion"]) + ([d["linked_number"]] if d["linked_number"] else []):
                if key not in refs:
                    refs.append(key)
            own, areas = classify_division(tax, wl, d, bill_areas(conn, refs))
            store_division(conn, d, refs, own, areas, today)
            stored += 1
            ours += on_our_ground(areas)
            if (row is None or not row[1]) and wants_positions(d, areas, refs, watch, today,
                                                               contested_days):
                try:
                    pull_positions(conn, client, today, d, pid)
                    with_positions += 1
                except (FetchError, ValueError) as exc:
                    _gap(conn, today, "positions of vote {0}: {1}".format(d["division_key"], exc))
                    gaps += 1
            conn.commit()
        conn.execute("UPDATE do_sessions SET votes=?, votes_read=? WHERE session_id=?",
                     (len(recs), today if complete else None, s["session_id"]))
        conn.commit()
    return stored, ours, with_positions, gaps


# --- offline -------------------------------------------------------------------------

def reclassify(conn, tax=None, log=print):
    """Re-derive bill areas, then division areas, offline. Bills first."""
    tax = tax if tax is not None else load_taxonomy()
    wl = empty_watchlist()
    watch = do_store.watchlist()
    changed_b = changed_d = 0
    for key, title, subject, areas in conn.execute(
            "SELECT bill_key, title, subject, areas FROM do_bills").fetchall():
        res = classify_bill(tax, wl, {"bill_key": key, "title": title or "",
                                      "subject": subject}, watch)
        new = do_store.dumps(res.issue_areas)
        changed_b += new != (areas or "[]")
        conn.execute("UPDATE do_bills SET areas=?, matched_terms=?, tier=? WHERE bill_key=?",
                     (new, do_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, key))
    for key, motion, refs, areas in conn.execute(
            "SELECT division_key, motion, bill_refs, areas FROM do_divisions").fetchall():
        own, combined = classify_division(tax, wl, {"motion": motion or ""},
                                          bill_areas(conn, json.loads(refs or "[]")))
        new = do_store.dumps(combined)
        changed_d += new != (areas or "[]")
        conn.execute("UPDATE do_divisions SET own_areas=?, areas=?, matched_terms=?, tier=? "
                     "WHERE division_key=?",
                     (do_store.dumps(own.issue_areas), new, do_store.dumps(own.matched_terms),
                      own.tier, key))
    conn.commit()
    log("do-rollcalls: reclassified; {0} bill(s) and {1} vote(s) changed area".format(
        changed_b, changed_d))
    return changed_b, changed_d


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = lambda t: sum(on_our_ground(json.loads(a or "[]"))  # noqa: E731
                         for (a,) in conn.execute("SELECT areas FROM {0}".format(t)))
    log("  store: {0} iniciativa(s), {1} on our ground; {2} session(s); {3} vote(s), "
        "{4} on our ground, {5} with positions; {6} position(s); {7} member(s)".format(
            n("SELECT COUNT(*) FROM do_bills"), ours("do_bills"),
            n("SELECT COUNT(*) FROM do_sessions"),
            n("SELECT COUNT(*) FROM do_divisions"), ours("do_divisions"),
            n("SELECT COUNT(*) FROM do_divisions WHERE positions_read=1"),
            n("SELECT COUNT(*) FROM do_votes"),
            n("SELECT COUNT(*) FROM do_members")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--period", action="append", choices=sorted(PERIODS),
                    help="also read this period's iniciativas (2020-2024: the last Congress)")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--no-bills", action="store_true")
    ap.add_argument("--no-votes", action="store_true")
    ap.add_argument("--contested-days", type=int, default=CONTESTED_DAYS,
                    help="read positions of contested votes this recent (default %(default)s)")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored iniciativas and votes, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    args = ap.parse_args()
    today = datetime.date.today().isoformat()
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn)
        summary(conn)
        conn.close()
        return 0
    client = make_client()
    tax = load_taxonomy()
    print("do-rollcalls: taxonomy {0}".format(os.path.basename(taxonomy_path())))
    wl = empty_watchlist()
    watch = do_store.watchlist()
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    if not args.no_bills:
        for period in [CURRENT_PERIOD] + [p for p in (args.period or []) if p != CURRENT_PERIOD]:
            read, ours, g = pull_bills(conn, client, today, period=period, tax=tax, wl=wl,
                                       watch=watch, budget=budget)
            gaps += g
            print("do-rollcalls: {0} iniciativa(s) of {1} read, {2} on our ground, "
                  "{3} gap(s)".format(read, period, ours, g))
    if not args.no_votes:
        stored, ours, pos, g = pull_votes(conn, client, today, tax=tax, wl=wl, watch=watch,
                                          budget=budget, contested_days=args.contested_days)
        gaps += g
        print("do-rollcalls: {0} vote(s) stored, {1} on our ground, {2} with positions read, "
              "{3} gap(s)".format(stored, ours, pos, g))
    if not args.no_members:
        _n, g = pull_members(conn, client, today)
        gaps += g
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
