#!/usr/bin/env python3
"""Guatemala, Congreso de la República: deputies, initiatives, plenary votes
and every deputy's position.

    python3 tools/gt_rollcalls.py                    # sessions since the X legislature began
    python3 tools/gt_rollcalls.py --since 2022-01-01 # further back
    python3 tools/gt_rollcalls.py --index-only       # session pages only, no vote pages
    python3 tools/gt_rollcalls.py --reclassify       # re-derive areas, offline
    python3 tools/gt_rollcalls.py --db /tmp/gt.db    # anywhere but the store

PHASE 1 (9 October 2026); see docs/guatemala-scope.md. Everything is the
Congreso's own public HTML, keyless, measured from a GitHub runner:

  * /seccion_informacion_legislativa/votaciones_pleno -- EVERY plenary
    session with electronic votes, 1,089 of them back to 2009, each linking
    eventos_votaciones/<session id>. One page, about 840 KB.
  * /eventos_votaciones/<session> -- the session's questions: text, number,
    timestamp, and links to detalle_de_votacion/<question>/<session> (HTML)
    and pdf_resultado_votacion/<question>/<session> (PDF, NOT fetched:
    robots.txt disallows *.pdf, and the HTML carries every position).
  * /detalle_de_votacion/<question>/<session> -- four tabs (favor, contra,
    ausencia, licencia), one row per deputy: name, presence, vote. All 160.
  * /seccion_informacion_legislativa/iniciativas -- the 500 most recent
    initiatives the plenary took notice of (number, date, summary), back to
    March 2023. An older initiative that a vote names (28 of the 106 voted
    on since January 2024) or the watchlist holds is read from
    /buscador_iniciativas/<number>, the same card for one initiative.
  * / (the home page) -- a card per sitting deputy: profile id, name, bloc,
    district. /diputados serves the same page.

THE LAPTOP IS REFUSED. www.congreso.gob.gt sits behind Imperva Incapsula,
which answered every request from the scoping laptop with a 403 challenge
page, while GitHub's runners got 200s with the same honest User-Agent. A
challenge is NEVER solved or worked around here: the run stops, records a
gap and exits 1, so nothing is published and (on the Mac Mini) the GitHub
backup runs at its slot. See the scope doc.

A VOTE NAMES ITS INITIATIVE BY NUMBER ONLY ("... APROBAR LA INICIATIVA DE LEY
6844"), so a division's areas come from its initiative's summary, joined on
the number. Procedural votes (agenda, minutes, motions) name none; their
positions are read too, because one of them can matter: the 15 March 2022
vote that shelved Decreto 18-2022 (iniciativa 5272) is labelled only
"APROBACIÓN DE PROYECTO DE ACUERDO".

CLASSIFICATION waits for a Spanish taxonomy (config/taxonomy-es.yaml, the
shared Spanish list proposed on the Spain branch, plus the Guatemalan
addendum in docs/guatemala-scope.md; generated only once Christopher
approves). Until then areas stay NULL and only config/watchlist-gt.yaml,
applied by initiative NUMBER, lends areas.

Separation guarantee: writes gt_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.

Exit codes: 0 clean, 3 stored what it could and recorded gaps, 1 otherwise
(including a bot challenge).
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

from src import db, drain, gt_store, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "gt-rollcalls"
BASE = "https://www.congreso.gob.gt"
SESSIONS_PAGE = BASE + "/seccion_informacion_legislativa/votaciones_pleno"
SESSION_PAGE = BASE + "/eventos_votaciones/{0}"
VOTE_PAGE = BASE + "/detalle_de_votacion/{0}/{1}"
INITIATIVES_PAGE = BASE + "/seccion_informacion_legislativa/iniciativas"
INITIATIVE_SEARCH = BASE + "/buscador_iniciativas/{0}"
MEMBERS_PAGE = BASE + "/"
TAXONOMY_ES = os.path.join(ROOT, "config", "taxonomy-es.yaml")
BUDGET_S = drain.DEFAULT_S
# The X legislature (2024-2028) was installed on 14 January 2024. The first
# run backfills from here: 195 sessions and their votes.
SINCE = "2024-01-14"
# Two seconds between requests: one government site, behind a WAF that
# already refuses some clients. A first-run backfill of the X legislature
# is spread over several runs by the budget.
THROTTLE_S = 2.0
# Sessions re-read even when already stored: a vote added to a session page
# after our first read is picked up within two weeks.
REREAD_DAYS = 14
HIDDEN_AREAS = (11,)   # migration: collated, never campaigned (repo-wide rule)
CHALLENGE_MARKERS = ("_Incapsula_Resource", "Incapsula incident ID",
                     "Attention Required! | Cloudflare", "cf-chl-")
POSITIONS = {"favor": "A FAVOR", "contra": "CONTRA", "ausencia": "AUSENTE",
             "licencia": "LICENCIA"}


class Challenged(Exception):
    """The host answered with a bot challenge. Never worked around."""


# --- small helpers ------------------------------------------------------------

def iso(ddmmyyyy):
    """'08/09/2026 12:59:43' -> '2026-09-08'; anything else -> None."""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", ddmmyyyy or "")
    if not m:
        return None
    return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), int(m.group(2)), int(m.group(1)))


MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
          "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
          "noviembre": 11, "diciembre": 12}


def iso_long(text):
    """'Martes, 08 de septiembre de 2026' -> '2026-09-08'; else None."""
    m = re.search(r"(\d{1,2}) de (\w+) de (\d{4})", text or "")
    if not m or m.group(2).lower() not in MONTHS:
        return None
    return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), MONTHS[m.group(2).lower()],
                                        int(m.group(1)))


def fold(text):
    """Strip tags, unescape, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def is_challenge(text):
    head = (text or "")[:4000]
    return any(m in head for m in CHALLENGE_MARKERS)


def iniciativa_in(title):
    """The initiative number a question names, or None.
    'DEL PROYECTO DE DECRETO QUE DISPONE APROBAR LA INICIATIVA DE LEY 6844' -> '6844';
    'APROBACIÓN DE MOCIÓN PRIVILEGIADA URGENCIA NACIONAL 6047' -> '6047';
    'APROBACIÓN DE MOCIÓN DE REVISIÓN 5272' -> '5272'."""
    t = title or ""
    m = re.search(r"INICIATIVA(?:\s+DE\s+LEY)?\s+(?:N[UÚ]MERO\s+|NO\.\s*)?(\d{3,5})", t, re.I)
    if not m:
        m = re.search(r"(?:URGENCIA NACIONAL|REVISI[OÓ]N)\D{0,12}(\d{4})\b", t, re.I)
    return m.group(1) if m else None


def division_key(question_id):
    return "gt-{0}".format(question_id)


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def on_our_ground(areas):
    return bool(set(areas or []) - set(HIDDEN_AREAS))


def fetch(client, url, slug):
    """GET a page; a challenge (as a 403 or as a 200 body) raises Challenged."""
    try:
        text = client.get_text(url, FEED, slug)
    except FetchError as exc:
        if "403" in str(exc.cause):
            raise Challenged("{0}: HTTP 403 (bot challenge or block)".format(url))
        raise
    if is_challenge(text):
        raise Challenged("{0}: the reply was a bot challenge page".format(url))
    return text


# --- parsers (pure; tested against fixtures) ----------------------------------

def parse_sessions(page):
    """The votaciones_pleno list -> [{session_id, tipo, numero, label, date}]."""
    out = []
    for row in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", page):
        m = re.search(r"eventos_votaciones/(\d+)", row)
        if not m:
            continue
        cells = [fold(c) for c in re.findall(r"(?s)<td[^>]*>(.*?)</td>", row)]
        if len(cells) < 3:
            continue
        num = re.match(r"\d+", cells[1])
        out.append({"session_id": m.group(1), "tipo": cells[0],
                    "numero": int(num.group(0)) if num else None,
                    "label": cells[2], "date": iso(cells[2])})
    return out


def parse_session(page):
    """One eventos_votaciones page -> [{question_id, number, date, time, title}]."""
    out = []
    for row in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", page):
        m = re.search(r"detalle_de_votacion/(\d+)/(\d+)", row)
        if not m:
            continue
        cells = [fold(c) for c in re.findall(r"(?s)<td[^>]*>(.*?)</td>", row)]
        if len(cells) < 3:
            continue
        num = re.match(r"\d+", cells[1])
        stamp = re.search(r"\d{1,2}:\d{2}(?::\d{2})?", cells[2])
        out.append({"question_id": m.group(1), "session_id": m.group(2),
                    "number": int(num.group(0)) if num else None,
                    "date": iso(cells[2]), "time": stamp.group(0) if stamp else None,
                    "title": cells[0], "iniciativa": iniciativa_in(cells[0])})
    return out


def parse_vote(page):
    """One detalle_de_votacion page -> {title, number, positions:[(name, estado,
    position)], yes, no, absent, leave}, or None when the tabs are missing."""
    panes = re.split(r'<div class="tab-pane[^"]*"\s+id="', page)[1:]
    if not panes:
        return None
    positions = []
    counts = {}
    for pane in panes:
        pid = pane.split('"', 1)[0].strip()
        if pid not in POSITIONS:
            continue
        rows = []
        for row in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", pane):
            cells = [fold(c) for c in re.findall(r"(?s)<td[^>]*>(.*?)</td>", row)]
            if cells and cells[0]:
                rows.append((cells[0], cells[1] if len(cells) > 1 else None, POSITIONS[pid]))
        counts[pid] = len(rows)
        positions.extend(rows)
    if not counts:
        return None
    q = re.search(r"Pregunta:\s*([^<]*)", page)
    n = re.search(r"N[úu]mero:\s*(\d+)", page)
    return {"title": fold(q.group(1)) if q else None,
            "number": int(n.group(1)) if n else None,
            "positions": positions, "yes": counts.get("favor", 0),
            "no": counts.get("contra", 0), "absent": counts.get("ausencia", 0),
            "leave": counts.get("licencia", 0)}


def parse_initiatives(page):
    """The iniciativas listing -> [{numero, detail_id, conocio_pleno, resumen, pdf_url}]."""
    out = []
    for card in re.split(r'<div class="card-header"', page)[1:]:
        card = re.split(r'<div class="col-xl-4', card)[0]
        num = re.search(r"Iniciativa:\s*</strong>\s*<strong>\s*(\d+)\s*</strong>", card)
        if not num:
            continue
        date = re.search(r"Conoci[óo] Pleno</label>\s*<p[^>]*>(.*?)</p>", card, re.S)
        summ = re.search(r"Resumen:\s*</label>.*?<p[^>]*>(.*?)</p>", card, re.S)
        if not summ:
            summ = re.search(r"Resumen:(.*?)(?:ver detalle|</div>)", card, re.S)
        det = re.search(r"detalle_pdf/iniciativas/(\d+)", card)
        pdf = re.search(r'href="([^"]*/info_legislativo/iniciativas/[^"]+\.pdf)"', card)
        resumen = fold(summ.group(1)) if summ else None
        if resumen:
            resumen = re.sub(r"\s*ver detalle.*$", "", resumen).strip() or None
        out.append({"numero": num.group(1), "detail_id": det.group(1) if det else None,
                    "conocio_pleno": iso_long(fold(date.group(1))) if date else None,
                    "resumen": resumen, "pdf_url": pdf.group(1) if pdf else None})
    return out


def parse_members(page):
    """The home page's deputy cards -> [{member_id, name, bloque, distrito}],
    one per profile id (the carousel repeats cards)."""
    out = {}
    for card in re.split(r'<div class="event-box', page)[1:]:
        m = re.search(r"perfil_diputado/(\d+)", card)
        name = re.search(r'(?s)<h6[^>]*>\s*<a[^>]*>(.*?)</a>', card)
        if not m or not name or m.group(1) in out:
            continue
        text = fold(card)
        nm = fold(name.group(1))
        rest = text.split(nm, 1)[1] if nm in text else text
        bl = re.search(r"Bloque:\s*(.+?)\s+Distrito:", rest)
        if bl:
            bloque = bl.group(1).strip()
        else:
            bare = re.search(r"^\s*(.+?)\s+Distrito:", rest)
            bloque = bare.group(1).strip() if bare else None
        di = re.search(r"Distrito:\s*(.+?)\s+VER PERFIL", rest)
        out[m.group(1)] = {"member_id": m.group(1), "name": nm, "bloque": bloque,
                           "distrito": di.group(1).strip() if di else None}
    return list(out.values())


# --- classification ---------------------------------------------------------------

def load_taxonomy(path=None):
    """The Spanish taxonomy, or None while none exists (areas stay NULL)."""
    path = path or TAXONOMY_ES
    return filt.load_taxonomy(path) if os.path.exists(path) else None


def empty_watchlist():
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify(tax, numero, *texts):
    """(areas or None, terms, tier) for one row's text plus the watchlist entry
    of its initiative NUMBER. None only when there is no taxonomy AND no
    watchlist entry: unclassified, not empty."""
    watched = gt_store.watch_areas(numero) if numero else []
    if tax is None:
        if watched:
            return sorted(set(watched)), ["watch:" + str(numero)], 2
        return None, [], None
    res = filt.filter_item(tax, empty_watchlist(), *[t for t in texts if t])
    areas = set(res.issue_areas or [])
    terms = list(res.matched_terms or [])
    tier = res.tier
    if watched:
        areas |= set(watched)
        terms.append("watch:" + str(numero))
        tier = tier or 2
    return sorted(areas), terms, tier


def _initiative_areas(conn, numero):
    if not numero:
        return None
    row = conn.execute("SELECT areas FROM gt_initiatives WHERE numero=?", (numero,)).fetchone()
    return json.loads(row[0]) if row and row[0] is not None else None


def classify_division(conn, tax, d):
    """(own, combined, terms, tier): the vote's own text, then its initiative's
    areas. Here the own text almost never carries the subject."""
    own, terms, tier = classify(tax, d.get("iniciativa"), d.get("title"))
    parent = _initiative_areas(conn, d.get("iniciativa"))
    if parent is None and d.get("iniciativa") and tax is None:
        watched = gt_store.watch_areas(d["iniciativa"])
        parent = watched or None
    if own is None and parent is None:
        return None, None, terms, tier
    return own, sorted(set(own or []) | set(parent or [])), terms, tier


# --- storing ------------------------------------------------------------------------

def store_session(conn, s, today):
    conn.execute(
        "INSERT INTO gt_sessions (session_id, tipo, numero, date, label, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET tipo=excluded.tipo, "
        "numero=excluded.numero, date=excluded.date, label=excluded.label, "
        "last_seen=excluded.last_seen",
        (s["session_id"], s["tipo"], s["numero"], s["date"], s["label"], today, today))


def store_division(conn, d, tax, today):
    key = division_key(d["question_id"])
    own, combined, terms, tier = classify_division(conn, tax, d)
    conn.execute(
        "INSERT INTO gt_divisions (division_key, session_id, question_id, number, date, time, "
        "title, iniciativa, procedural, own_areas, areas, matched_terms, tier, first_seen, "
        "last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(division_key) DO UPDATE "
        "SET number=excluded.number, date=excluded.date, time=excluded.time, "
        "title=excluded.title, iniciativa=excluded.iniciativa, procedural=excluded.procedural, "
        "own_areas=excluded.own_areas, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (key, d["session_id"], d["question_id"], d.get("number"), d.get("date"), d.get("time"),
         d.get("title"), d.get("iniciativa"), 0 if d.get("iniciativa") else 1,
         None if own is None else gt_store.dumps(own),
         None if combined is None else gt_store.dumps(combined), gt_store.dumps(terms), tier,
         today, today))
    return key, combined


def store_positions(conn, key, v):
    conn.execute("DELETE FROM gt_votes WHERE division_key=?", (key,))
    conn.executemany(
        "INSERT OR REPLACE INTO gt_votes (division_key, name, name_key, estado, position) "
        "VALUES (?,?,?,?,?)",
        [(key, n, gt_store.name_key(n), e, p) for n, e, p in v["positions"]])
    conn.execute("UPDATE gt_divisions SET yes=?, no=?, absent=?, leave=?, positions=? "
                 "WHERE division_key=?",
                 (v["yes"], v["no"], v["absent"], v["leave"], len(v["positions"]), key))


def pull_votes(conn, client, today, since=SINCE, tax=None, log=print, budget=None,
               index_only=False, limit=None):
    """Read the session list, every session page not yet read (and the last
    REREAD_DAYS), then every vote page whose positions are not stored.
    Returns (sessions read, divisions stored, vote pages read, gaps)."""
    gaps = 0
    try:
        page = fetch(client, SESSIONS_PAGE, "sessions")
    except FetchError as exc:
        _gap(conn, today, "session list: {0}".format(exc))
        log("  [gap] session list: {0}".format(str(exc)[:90]))
        return 0, 0, 0, 1
    sessions = [s for s in parse_sessions(page)
                if s["date"] and s["date"] >= since and s["date"] <= today
                and s["tipo"] != "Prueba Sistema"]
    if not sessions:
        _gap(conn, today, "session list carried no session since {0}".format(since))
        log("  [gap] session list carried no session since {0}".format(since))
        return 0, 0, 0, 1
    for s in sessions:
        store_session(conn, s, today)
    conn.commit()
    done = {r[0] for r in conn.execute(
        "SELECT session_id FROM gt_sessions WHERE fetched_at IS NOT NULL")}
    cutoff = (datetime.date.fromisoformat(today) - datetime.timedelta(days=REREAD_DAYS)).isoformat()
    todo = sorted((s for s in sessions if s["session_id"] not in done or s["date"] >= cutoff),
                  key=lambda s: (s["date"], int(s["session_id"])))
    log("gt-rollcalls: {0} session(s) since {1}, {2} to read".format(len(sessions), since, len(todo)))
    read = stored = 0
    for s in todo:
        if budget is not None and budget.exhausted():
            log(budget.disclose("sessions", read))
            break
        try:
            spage = fetch(client, SESSION_PAGE.format(s["session_id"]), "session-" + s["session_id"])
        except FetchError as exc:
            _gap(conn, today, "session {0}: {1}".format(s["session_id"], exc))
            log("  [gap] session {0}: {1}".format(s["session_id"], str(exc)[:90]))
            gaps += 1
            continue
        votes = parse_session(spage)
        for v in votes:
            v["date"] = v.get("date") or s["date"]
            store_division(conn, v, tax, today)
            stored += 1
        # A session with no votes is real (a solemn sitting); listed=0 says
        # it was read, not missed.
        conn.execute("UPDATE gt_sessions SET listed=?, fetched_at=? WHERE session_id=?",
                     (len(votes), today, s["session_id"]))
        conn.commit()
        read += 1
    pages = 0
    if not index_only:
        pages, g = pull_positions(conn, client, today, since=since, log=log, budget=budget,
                                  limit=limit)
        gaps += g
    return read, stored, pages, gaps


def pull_positions(conn, client, today, since=SINCE, log=print, budget=None, limit=None):
    """Every stored vote since `since` whose positions are not stored yet.
    Returns (vote pages read, gaps)."""
    pages = gaps = 0
    pending = conn.execute(
        "SELECT division_key, question_id, session_id FROM gt_divisions "
        "WHERE positions IS NULL AND date >= ? ORDER BY date, CAST(question_id AS INTEGER)",
        (since,)).fetchall()
    for key, qid, sid in pending:
        if limit is not None and pages >= limit:
            log("  fetch cap ({0}) reached; the rest lands on the next run "
                "-- disclosed, not silent".format(limit))
            break
        if budget is not None and budget.exhausted():
            log(budget.disclose("vote pages", pages))
            break
        try:
            vpage = fetch(client, VOTE_PAGE.format(qid, sid), "vote-" + qid)
        except FetchError as exc:
            _gap(conn, today, "{0}: {1}".format(key, exc))
            log("  [gap] {0}: {1}".format(key, str(exc)[:90]))
            gaps += 1
            continue
        v = parse_vote(vpage)
        if v is None:
            _gap(conn, today, "{0}: the vote page carried no positions".format(key))
            log("  [gap] {0}: the vote page carried no positions".format(key))
            gaps += 1
            continue
        store_positions(conn, key, v)
        conn.commit()
        pages += 1
    return pages, gaps


def store_initiative(conn, i, tax, today):
    areas, terms, tier = classify(tax, i["numero"], i.get("resumen"))
    conn.execute(
        "INSERT INTO gt_initiatives (numero, detail_id, conocio_pleno, resumen, pdf_url, areas, "
        "matched_terms, tier, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(numero) DO UPDATE SET detail_id=excluded.detail_id, "
        "conocio_pleno=excluded.conocio_pleno, resumen=excluded.resumen, "
        "pdf_url=excluded.pdf_url, areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen",
        (i["numero"], i.get("detail_id"), i.get("conocio_pleno"), i.get("resumen"),
         i.get("pdf_url"), None if areas is None else gt_store.dumps(areas),
         gt_store.dumps(terms), tier, today, today))
    return areas


def pull_initiatives(conn, client, today, tax=None, log=print):
    """Returns (read, on our ground, gaps)."""
    try:
        page = fetch(client, INITIATIVES_PAGE, "initiatives")
    except FetchError as exc:
        _gap(conn, today, "initiatives: {0}".format(exc))
        log("  [gap] initiatives: {0}".format(str(exc)[:90]))
        return 0, 0, 1
    items = parse_initiatives(page)
    if not items:
        _gap(conn, today, "initiatives: the listing carried no initiative")
        log("  [gap] initiatives: the listing carried no initiative")
        return 0, 0, 1
    ours = 0
    for i in items:
        ours += on_our_ground(store_initiative(conn, i, tax, today))
    conn.commit()
    return len(items), ours, 0


def pull_missing_initiatives(conn, client, today, tax=None, log=print, budget=None):
    """Initiatives a stored vote names, or the watchlist holds, that the
    500-card listing did not carry: one search page each, then the votes on
    them re-derive their areas. Returns (read, gaps)."""
    wanted = {r[0] for r in conn.execute(
        "SELECT DISTINCT iniciativa FROM gt_divisions WHERE iniciativa IS NOT NULL")}
    wanted |= set(gt_store.watchlist().keys())
    have = {r[0] for r in conn.execute("SELECT numero FROM gt_initiatives")}
    read = gaps = 0
    for numero in sorted(wanted - have, key=int):
        if budget is not None and budget.exhausted():
            log(budget.disclose("initiative searches", read))
            break
        try:
            page = fetch(client, INITIATIVE_SEARCH.format(numero), "initiative-" + numero)
        except FetchError as exc:
            _gap(conn, today, "initiative {0}: {1}".format(numero, exc))
            log("  [gap] initiative {0}: {1}".format(numero, str(exc)[:90]))
            gaps += 1
            continue
        hits = [i for i in parse_initiatives(page) if i["numero"] == numero]
        if not hits:
            _gap(conn, today, "initiative {0}: the search found no such initiative".format(numero))
            log("  [gap] initiative {0}: the search found no such initiative".format(numero))
            gaps += 1
            continue
        store_initiative(conn, hits[0], tax, today)
        for key, title in conn.execute(
                "SELECT division_key, title FROM gt_divisions WHERE iniciativa=?", (numero,)).fetchall():
            own, combined, terms, tier = classify_division(
                conn, tax, {"iniciativa": numero, "title": title})
            conn.execute("UPDATE gt_divisions SET own_areas=?, areas=?, matched_terms=?, tier=? "
                         "WHERE division_key=?",
                         (None if own is None else gt_store.dumps(own),
                          None if combined is None else gt_store.dumps(combined),
                          gt_store.dumps(terms), tier, key))
        conn.commit()
        read += 1
    return read, gaps


def pull_members(conn, client, today, log=print):
    """Returns (records, gaps)."""
    try:
        page = fetch(client, MEMBERS_PAGE, "members")
    except FetchError as exc:
        _gap(conn, today, "members: {0}".format(exc))
        log("  [gap] members: {0}".format(str(exc)[:90]))
        return 0, 1
    members = parse_members(page)
    if len(members) < 100:
        # 160 seats; a short roster is a changed page, not a smaller Congress.
        _gap(conn, today, "members: only {0} deputy card(s) on the page".format(len(members)))
        log("  [gap] members: only {0} deputy card(s) on the page".format(len(members)))
        if not members:
            return 0, 1
    for m in members:
        conn.execute(
            "INSERT INTO gt_members (member_id, name, name_key, bloque, distrito, first_seen, "
            "last_seen) VALUES (?,?,?,?,?,?,?) ON CONFLICT(member_id) DO UPDATE SET "
            "name=excluded.name, name_key=excluded.name_key, bloque=excluded.bloque, "
            "distrito=excluded.distrito, last_seen=excluded.last_seen",
            (m["member_id"], m["name"], gt_store.name_key(m["name"]), m["bloque"],
             m["distrito"], today, today))
    conn.commit()
    return len(members), 0 if len(members) >= 100 else 1


def reclassify(conn, tax=None, log=print):
    """Re-derive initiative areas, then division areas, offline. Initiatives
    first: divisions inherit."""
    ci = cd = 0
    for numero, resumen, areas in conn.execute(
            "SELECT numero, resumen, areas FROM gt_initiatives").fetchall():
        new, terms, tier = classify(tax, numero, resumen)
        new_s = None if new is None else gt_store.dumps(new)
        ci += new_s != areas
        conn.execute("UPDATE gt_initiatives SET areas=?, matched_terms=?, tier=? WHERE numero=?",
                     (new_s, gt_store.dumps(terms), tier, numero))
    for key, ini, title, areas in conn.execute(
            "SELECT division_key, iniciativa, title, areas FROM gt_divisions").fetchall():
        own, combined, terms, tier = classify_division(conn, tax, {"iniciativa": ini, "title": title})
        new_s = None if combined is None else gt_store.dumps(combined)
        cd += new_s != areas
        conn.execute("UPDATE gt_divisions SET own_areas=?, areas=?, matched_terms=?, tier=? "
                     "WHERE division_key=?",
                     (None if own is None else gt_store.dumps(own), new_s,
                      gt_store.dumps(terms), tier, key))
    conn.commit()
    log("gt-rollcalls: reclassified; {0} initiative(s) and {1} division(s) changed area".format(ci, cd))
    return ci, cd


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731

    def ours(table):
        rows = conn.execute("SELECT areas FROM {0} WHERE areas IS NOT NULL".format(table))
        return sum(on_our_ground(json.loads(a)) for (a,) in rows)
    log("  store: {0} initiative(s), {1} on our ground; {2} session(s); {3} division(s), "
        "{4} on our ground, {5} procedural, {6} without positions yet; {7} member(s), "
        "{8} position(s)".format(
            n("SELECT COUNT(*) FROM gt_initiatives"), ours("gt_initiatives"),
            n("SELECT COUNT(*) FROM gt_sessions"),
            n("SELECT COUNT(*) FROM gt_divisions"), ours("gt_divisions"),
            n("SELECT COUNT(*) FROM gt_divisions WHERE procedural=1"),
            n("SELECT COUNT(*) FROM gt_divisions WHERE positions IS NULL"),
            n("SELECT COUNT(*) FROM gt_members"), n("SELECT COUNT(*) FROM gt_votes")))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", default=SINCE, help="ISO date; sessions before it are ignored")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--taxonomy", help="classify with this taxonomy file "
                                       "(default config/taxonomy-es.yaml when it exists)")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--no-initiatives", action="store_true")
    ap.add_argument("--no-votes", action="store_true")
    ap.add_argument("--index-only", action="store_true",
                    help="read session pages (questions, numbers) but no vote pages")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored initiatives and divisions, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--limit", type=int, help="stop after this many vote pages")
    args = ap.parse_args(argv)
    tax = load_taxonomy(args.taxonomy)
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn, tax)
        summary(conn)
        conn.close()
        return 0
    if tax is None:
        print("gt-rollcalls: no Spanish taxonomy yet (config/taxonomy-es.yaml); "
              "areas stay NULL, only watchlist-gt lends areas")
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"), throttle=THROTTLE_S)
    today = datetime.date.today().isoformat()
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    try:
        # Initiatives before votes: a division inherits its initiative's areas.
        if not args.no_initiatives:
            read, ours, g = pull_initiatives(conn, client, today, tax=tax)
            gaps += g
            print("gt-rollcalls: {0} initiative(s) read, {1} on our ground, {2} gap(s)".format(
                read, ours, g))
        if not args.no_votes:
            # The index first, then the older initiatives its votes name (so a
            # backfill classifies before it spends its budget on positions),
            # then the positions.
            ns, nd, _, g = pull_votes(conn, client, today, since=args.since, tax=tax,
                                      budget=budget, index_only=True)
            gaps += g
            print("gt-rollcalls: {0} session(s) read, {1} division(s) stored, {2} gap(s)".format(
                ns, nd, g))
        if not args.no_initiatives:
            n, g = pull_missing_initiatives(conn, client, today, tax=tax, budget=budget)
            gaps += g
            print("gt-rollcalls: {0} older initiative(s) read by number, {1} gap(s)".format(n, g))
        if not args.no_votes and not args.index_only:
            nv, g = pull_positions(conn, client, today, since=args.since, budget=budget,
                                   limit=args.limit)
            gaps += g
            print("gt-rollcalls: {0} vote page(s) read, {1} gap(s)".format(nv, g))
        if not args.no_members:
            n, g = pull_members(conn, client, today)
            gaps += g
            print("gt-rollcalls: {0} member record(s), {1} gap(s)".format(n, g))
    except Challenged as exc:
        # Never solved, never retried with another User-Agent: recorded, and
        # the run fails so nothing is published from a refused run.
        _gap(conn, today, "bot challenge, not worked around: {0}".format(exc))
        conn.commit()
        print("  [gap] bot challenge, not worked around: {0}".format(exc))
        print("gt-rollcalls: refused by the host; nothing more requested this run")
        summary(conn)
        conn.close()
        return 1
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
