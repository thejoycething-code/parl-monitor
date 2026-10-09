#!/usr/bin/env python3
"""Honduras, Congreso Nacional: deputies, sessions and their agendas,
legislative files (expedientes), press releases and La Gaceta.

    python3 tools/hn_rollcalls.py                      # the weekly pull
    python3 tools/hn_rollcalls.py --reclassify         # re-derive areas, offline
    python3 tools/hn_rollcalls.py --taxonomy x.yaml    # classify with a draft list
    python3 tools/hn_rollcalls.py --db /tmp/hn.db      # anywhere but the store

The name follows the repo's convention (tools/<cc>_rollcalls.py), but THERE
ARE NO ROLL CALLS TO COLLECT. The Congreso's system carries a `resultado`
field on every agenda item and a `totalVotaciones` counter; on 9 October 2026
both were empty for the whole legislature. What it does publish, measured
live and keyless (docs/honduras-scope.md):

  * congresonacional.hn/api/matizzo/* -- the JSON the site's own pages call:
      - diputados: all 257 deputies (128 seats, propietarios and suplentes,
        though the API files all 257 as suplentes) with party and department;
      - sesiones?page=N&pageSize=100: every session, plenary and committee
        (362, 25 January 2025 to 23 September 2026);
      - sesiones/orden-del-dia?roomId=N: one session's agenda, each item
        with its legislative file's id and number when it has one;
      - expediente?estado=K: totals per stage and the TEN most recently
        touched files in that stage. There is no full listing: the 1,237
        files can only be met ten at a time per stage, or on an agenda.
  * api.congresonacional.hn/public/news/<limit>/<skip>/ -- the press
    releases (2,405 at 9 October 2026, about 150 a month), each with its
    body as Draft.js blocks inside an unsigned-to-us JWT whose payload is
    plain base64. Usually the first place a bill on our ground is named.
  * enag.gob.hn/index.php/gaceta-digital/<year>/<month>?start=N -- La
    Gaceta, the official journal, free since the Congreso's 2026 agreement
    with ENAG: one listing row per issue, its sumario printed in the row.
    The PDFs (up to 28 MB an issue) are NOT fetched.

CLASSIFICATION waits for a Spanish taxonomy. config/taxonomy-es.yaml is
read when it exists (the shared Spanish list the Spanish-language editions
are converging on, see docs/honduras-scope.md); until then areas stay NULL
-- unclassified, not "nothing found" -- and only config/watchlist-hn.yaml,
applied by expediente NUMBER, lends areas.

Separation guarantee: writes hn_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.

Exit codes: 0 clean, 3 stored what it could and recorded gaps, 1 otherwise.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, hn_store, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "hn-rollcalls"
SITE = "https://congresonacional.hn"
API = SITE + "/api/matizzo"
NEWS_API = "https://api.congresonacional.hn/public/news/{limit}/{skip}/"
GACETA = "https://enag.gob.hn"
GACETA_MONTH = GACETA + "/index.php/gaceta-digital/{year}/{month}"
TAXONOMY_ES = os.path.join(ROOT, "config", "taxonomy-es.yaml")
BUDGET_S = drain.DEFAULT_S
# One small government site behind each host; a request every 1.2 seconds
# keeps the first run's agenda backfill (about 360 sessions) near eight
# minutes and the weekly to a couple of dozen requests.
THROTTLE_S = 1.2
SESSIONS_PAGE = 100
NEWS_PAGE = 100
# The expediente stages, by the numeric code the endpoint accepts (it
# refuses the names: "The value 'Aprobado' is not valid."). 2, 4, 5, 7, 8
# and 9 return nothing.
ESTADOS = {0: "Iniciativa", 1: "EnComision", 3: "EnDebate", 6: "Aprobado"}
# Agendas re-read when the session is this recent: an item's status moves
# after the sitting (a plenary of 20 May still had items at status 0).
REREAD_DAYS = 21
# The legislature that began on 25 January 2026. The first run reads press
# releases back to here and no further.
NEWS_SINCE = "2026-01-25"
GACETA_SINCE = (2026, 1)
MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre")
HIDDEN_AREAS = (11,)   # migration: collated, never campaigned (repo-wide rule)


# --- small helpers ------------------------------------------------------------

def fold(text):
    """Strip tags, unescape, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def on_our_ground(areas):
    return bool(set(areas or []) - set(HIDDEN_AREAS))


def unwrap(payload, what):
    """The `data` of a matizzo reply; ValueError when it reports an error."""
    if not isinstance(payload, dict) or payload.get("isError") or "data" not in payload:
        raise ValueError("{0}: {1}".format(what, (payload or {}).get("message")
                                           if isinstance(payload, dict) else "not JSON"))
    return payload["data"]


def news_body(token):
    """Plain text of a press release body: the Draft.js blocks carried in the
    payload of a JWT. The signature is irrelevant to reading it."""
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        doc = json.loads(base64.urlsafe_b64decode(part.encode("ascii")).decode("utf-8"))
    except (AttributeError, IndexError, ValueError, UnicodeDecodeError):
        return ""
    blocks = doc.get("blocks") if isinstance(doc, dict) else None
    return "\n".join((b.get("text") or "").strip() for b in (blocks or [])
                     if isinstance(b, dict) and (b.get("text") or "").strip())


# --- classification ---------------------------------------------------------

def load_taxonomy(path=None):
    """The Spanish taxonomy, or None while none exists (areas stay NULL)."""
    path = path or TAXONOMY_ES
    return filt.load_taxonomy(path) if os.path.exists(path) else None


def empty_watchlist():
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify(tax, numero, *texts):
    """(areas or None, matched terms, tier) for one row's text plus the
    watchlist entry of its expediente NUMBER. areas is None only when there
    is no taxonomy AND no watchlist entry: unclassified, not empty."""
    watched = hn_store.watch_areas(numero) if numero else []
    if tax is None:
        if watched:
            return sorted(set(watched)), ["watch:" + numero], 2
        return None, [], None
    res = filt.filter_item(tax, empty_watchlist(), *[t for t in texts if t])
    areas = set(res.issue_areas or [])
    terms = list(res.matched_terms or [])
    tier = res.tier
    if watched:
        areas |= set(watched)
        terms.append("watch:" + numero)
        tier = tier or 2
    return sorted(areas), terms, tier


def _areas_sql(areas):
    return None if areas is None else hn_store.dumps(areas)


# --- parsers (pure, tested on fixtures) --------------------------------------

def parse_members(data):
    """Deputies from the diputados reply. The DNI and e-mail are dropped here,
    deliberately (src/hn_store.py)."""
    rows = data.get("diputados") if isinstance(data, dict) else data
    out = []
    for d in rows or []:
        if not isinstance(d, dict) or d.get("userId") is None:
            continue
        party = d.get("party")
        out.append({
            "user_id": int(d["userId"]),
            "display_name": (d.get("displayName") or "").strip() or None,
            "departamento": (d.get("departamento") or "").strip() or None,
            "party": ((party or {}).get("name") if isinstance(party, dict) else party) or None,
            "role": (d.get("role") or "").strip() or None,
            "is_active": 1 if d.get("isActive") else 0,
        })
    return out


def parse_sessions(data):
    out = []
    for s in (data or {}).get("items") or []:
        if s.get("roomId") is None:
            continue
        out.append({
            "room_id": int(s["roomId"]),
            "name": (s.get("name") or "").strip() or None,
            "list_name": s.get("listName"),
            "room_type": s.get("roomType"),
            "room_state": s.get("roomState"),
            "schedule": s.get("schedule"),
            "schedule_end": s.get("scheduleEnd"),
            "youtube_url": s.get("youtubeUrl") or None,
        })
    return out


def parse_agenda(data):
    """(list name, items) from an orden-del-dia reply."""
    items = []
    for it in (data or {}).get("items") or []:
        if it.get("roomItemId") is None:
            continue
        project = it.get("legislativeProject") or {}
        items.append({
            "room_item_id": int(it["roomItemId"]),
            "name": (it.get("name") or "").strip() or None,
            "item_type": it.get("roomItemType"),
            "author_name": it.get("authorName") or None,
            "project_id": it.get("legislativeProjectId"),
            "project_number": project.get("number") or None,
            "project_title": (project.get("title") or "").strip() or None,
            "resultado": None if it.get("resultado") is None
            else json.dumps(it.get("resultado"), ensure_ascii=False),
        })
    return (data or {}).get("userListName"), items


def parse_session_detail(data):
    """{roomItemId: (status, order)} from a sesiones/<id> reply: the agenda
    endpoint does not carry the status, the detail does."""
    out = {}
    for it in (data or {}).get("ordenDelDia") or []:
        if it.get("roomItemId") is not None:
            out[int(it["roomItemId"])] = (it.get("status"), it.get("order"))
    return out


def parse_expedientes(data):
    out = []
    for e in (data or {}).get("recientes") or []:
        if e.get("legislativeProjectId") is None:
            continue
        out.append({
            "project_id": int(e["legislativeProjectId"]),
            "numero": e.get("numero") or None,
            "titulo": (e.get("titulo") or "").strip() or None,
            "estado": e.get("estado") or None,
            "fecha": e.get("fechaCreacion") or None,
            "gaceta": e.get("gaceta") or None,
            "doc_file": e.get("docFile") or None,
        })
    return out


def parse_news(payload):
    """(total, posts) from a /public/news reply."""
    if not isinstance(payload, dict) or not payload.get("successed"):
        raise ValueError("news: reply not successful")
    posts = []
    for p in payload.get("posts") or []:
        if not p.get("_id"):
            continue
        posts.append({
            "post_id": p["_id"],
            "created_at": p.get("createdAt"),
            "title": re.sub(r"\s+", " ", p.get("title") or "").strip() or None,
            "description": re.sub(r"\s+", " ", p.get("description") or "").strip() or None,
            "body": news_body(p.get("body") or ""),
        })
    return payload.get("count"), posts


_GACETA_ROW = re.compile(r'class="edocman-document col-md-12"')
_GACETA_LINK = re.compile(r'href="(/index\.php/gaceta-digital/(\d{4})(\d{2})(\d{2})-(\d+)/download)"')
_GACETA_DESC = re.compile(r'edocman-description-details clearfix">(.*?)</div>', re.S)


def parse_gazette(page):
    """(issues, next start or None) from one month listing page. The title
    is typed by hand ('20260909 -37242', '20260912- 37245'); the download
    link is generated, so the issue is read off the link."""
    issues = []
    for block in _GACETA_ROW.split(page or "")[1:]:
        m = _GACETA_LINK.search(block)
        if not m:
            continue
        desc = _GACETA_DESC.search(block)
        issues.append({
            "issue": int(m.group(5)),
            "date": "{0}-{1}-{2}".format(m.group(2), m.group(3), m.group(4)),
            "summary": fold(desc.group(1)) if desc else None,
            "url": GACETA + m.group(1),
        })
    starts = sorted({int(s) for s in re.findall(r'[?&]start=(\d+)', page or "")})
    return issues, starts


# --- storers --------------------------------------------------------------------

def store_member(conn, m, today):
    conn.execute(
        """INSERT INTO hn_members (user_id, display_name, departamento, party, role,
               is_active, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET display_name=excluded.display_name,
               departamento=excluded.departamento, party=excluded.party,
               role=excluded.role, is_active=excluded.is_active,
               last_seen=excluded.last_seen""",
        (m["user_id"], m["display_name"], m["departamento"], m["party"], m["role"],
         m["is_active"], today, today))


def store_session(conn, s, today):
    conn.execute(
        """INSERT INTO hn_sessions (room_id, name, list_name, room_type, room_state,
               schedule, schedule_end, youtube_url, first_seen, last_seen)
           VALUES (?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(room_id) DO UPDATE SET name=excluded.name,
               list_name=excluded.list_name, room_type=excluded.room_type,
               room_state=excluded.room_state, schedule=excluded.schedule,
               schedule_end=excluded.schedule_end, youtube_url=excluded.youtube_url,
               last_seen=excluded.last_seen""",
        (s["room_id"], s["name"], s["list_name"], s["room_type"], s["room_state"],
         s["schedule"], s["schedule_end"], s["youtube_url"], today, today))


def store_bill(conn, b, tax, today):
    """Upsert one legislative file. A row seen only on an agenda has no
    estado; a later expediente reading fills it, and an agenda sighting never
    blanks what the expediente endpoint said."""
    areas, terms, tier = classify(tax, b.get("numero"), b.get("titulo"))
    conn.execute(
        """INSERT INTO hn_bills (project_id, numero, titulo, estado, fecha, gaceta,
               doc_file, areas, matched_terms, tier, first_seen, last_seen)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(project_id) DO UPDATE SET
               numero=COALESCE(excluded.numero, numero),
               titulo=COALESCE(excluded.titulo, titulo),
               estado=COALESCE(excluded.estado, estado),
               fecha=COALESCE(excluded.fecha, fecha),
               gaceta=COALESCE(excluded.gaceta, gaceta),
               doc_file=COALESCE(excluded.doc_file, doc_file),
               areas=excluded.areas, matched_terms=excluded.matched_terms,
               tier=excluded.tier, last_seen=excluded.last_seen""",
        (b["project_id"], b.get("numero"), b.get("titulo"), b.get("estado"),
         b.get("fecha"), b.get("gaceta"), b.get("doc_file"), _areas_sql(areas),
         hn_store.dumps(terms), tier, today, today))
    return areas


def store_item(conn, room_id, list_name, it, status, order, tax, today):
    areas, terms, tier = classify(tax, it.get("project_number"), it.get("name"),
                                  it.get("project_title"))
    conn.execute(
        """INSERT INTO hn_agenda_items (room_item_id, room_id, list_name, name, item_type,
               status, item_order, author_name, project_id, project_number, resultado,
               areas, matched_terms, tier, first_seen, last_seen)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(room_item_id) DO UPDATE SET room_id=excluded.room_id,
               list_name=excluded.list_name, name=excluded.name,
               item_type=excluded.item_type,
               status=COALESCE(excluded.status, status),
               item_order=COALESCE(excluded.item_order, item_order),
               author_name=excluded.author_name, project_id=excluded.project_id,
               project_number=excluded.project_number, resultado=excluded.resultado,
               areas=excluded.areas, matched_terms=excluded.matched_terms,
               tier=excluded.tier, last_seen=excluded.last_seen""",
        (it["room_item_id"], room_id, list_name, it["name"], it["item_type"], status,
         order, it["author_name"], it["project_id"], it["project_number"],
         it["resultado"], _areas_sql(areas), hn_store.dumps(terms), tier, today, today))
    return areas


def store_news(conn, p, tax, today):
    areas, terms, tier = classify(tax, None, p["title"], p["description"], p["body"])
    conn.execute(
        """INSERT INTO hn_news (post_id, created_at, title, description, body, areas,
               matched_terms, tier, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(post_id) DO UPDATE SET created_at=excluded.created_at,
               title=excluded.title, description=excluded.description, body=excluded.body,
               areas=excluded.areas, matched_terms=excluded.matched_terms,
               tier=excluded.tier, last_seen=excluded.last_seen""",
        (p["post_id"], p["created_at"], p["title"], p["description"], p["body"],
         _areas_sql(areas), hn_store.dumps(terms), tier, today, today))
    return areas


def store_issue(conn, g, tax, today):
    areas, terms, tier = classify(tax, None, g["summary"])
    conn.execute(
        """INSERT INTO hn_gazette (issue, date, summary, url, areas, matched_terms, tier,
               first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(issue) DO UPDATE SET date=excluded.date, summary=excluded.summary,
               url=excluded.url, areas=excluded.areas, matched_terms=excluded.matched_terms,
               tier=excluded.tier, last_seen=excluded.last_seen""",
        (g["issue"], g["date"], g["summary"], g["url"], _areas_sql(areas),
         hn_store.dumps(terms), tier, today, today))
    return areas


# --- pulls ------------------------------------------------------------------------

def pull_members(conn, client, today, log=print):
    try:
        data = unwrap(client.get_json(API + "/diputados", FEED, "diputados"), "diputados")
    except (FetchError, ValueError) as exc:
        _gap(conn, today, "diputados: {0}".format(exc))
        conn.commit()
        log("  [gap] diputados: {0}".format(exc))
        return 0, 1
    members = parse_members(data)
    for m in members:
        store_member(conn, m, today)
    conn.commit()
    return len(members), 0


def pull_sessions(conn, client, today, log=print):
    """Every session, page by page. Returns (sessions, gaps)."""
    seen, page, total = 0, 1, None
    while True:
        url = "{0}/sesiones?page={1}&pageSize={2}".format(API, page, SESSIONS_PAGE)
        try:
            data = unwrap(client.get_json(url, FEED, "sesiones-p{0}".format(page)), "sesiones")
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "sesiones page {0}: {1}".format(page, exc))
            conn.commit()
            log("  [gap] sesiones page {0}: {1}".format(page, exc))
            return seen, 1
        rows = parse_sessions(data)
        for s in rows:
            store_session(conn, s, today)
        seen += len(rows)
        total = data.get("total") or 0
        if not rows or page * SESSIONS_PAGE >= total:
            break
        page += 1
    conn.commit()
    return seen, 0


def sessions_to_read(conn, today, limit=None):
    """Sessions whose agenda is unread, or recent enough that statuses move."""
    cutoff = (datetime.date.fromisoformat(today)
              - datetime.timedelta(days=REREAD_DAYS)).isoformat()
    rows = conn.execute(
        """SELECT room_id FROM hn_sessions
           WHERE agenda_read IS NULL OR substr(schedule, 1, 10) >= ?
           ORDER BY (agenda_read IS NOT NULL), schedule DESC""", (cutoff,)).fetchall()
    ids = [r[0] for r in rows]
    return ids[:limit] if limit else ids


def pull_agendas(conn, client, today, tax=None, log=print, budget=None, limit=None):
    """Agenda (orden del día) and item statuses (the session detail) for each
    session due. Returns (sessions read, items stored, on our ground, gaps)."""
    read = stored = ours = gaps = 0
    due = sessions_to_read(conn, today, limit)
    for room_id in due:
        if budget is not None and budget.exhausted():
            log(budget.disclose("agenda(s)", read))
            break
        try:
            agenda = unwrap(client.get_json(
                "{0}/sesiones/orden-del-dia?roomId={1}".format(API, room_id),
                FEED, "orden-{0}".format(room_id)), "orden-del-dia")
            detail = unwrap(client.get_json(
                "{0}/sesiones/{1}".format(API, room_id), FEED, "sesion-{0}".format(room_id)),
                "sesion")
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "session {0}: {1}".format(room_id, exc))
            log("  [gap] session {0}: {1}".format(room_id, exc))
            gaps += 1
            continue
        list_name, items = parse_agenda(agenda)
        statuses = parse_session_detail(detail)
        for it in items:
            if it["project_id"]:
                store_bill(conn, {"project_id": it["project_id"],
                                  "numero": it["project_number"],
                                  "titulo": it["project_title"]}, tax, today)
            status, order = statuses.get(it["room_item_id"], (None, None))
            areas = store_item(conn, room_id, list_name, it, status, order, tax, today)
            stored += 1
            ours += on_our_ground(areas)
        conn.execute("UPDATE hn_sessions SET agenda_items=?, agenda_read=? WHERE room_id=?",
                     (len(items), today, room_id))
        conn.commit()
        read += 1
    return read, stored, ours, gaps


def pull_expedientes(conn, client, today, tax=None, log=print):
    """The ten most recently touched files in each stage. Returns (read, ours, gaps)."""
    read = ours = gaps = 0
    for code, name in ESTADOS.items():
        try:
            data = unwrap(client.get_json("{0}/expediente?estado={1}".format(API, code),
                                          FEED, "expediente-{0}".format(code)), "expediente")
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "expediente estado {0}: {1}".format(name, exc))
            log("  [gap] expediente estado {0}: {1}".format(name, exc))
            gaps += 1
            continue
        for b in parse_expedientes(data):
            ours += on_our_ground(store_bill(conn, b, tax, today))
            read += 1
    conn.commit()
    return read, ours, gaps


def pull_news(conn, client, today, tax=None, log=print, budget=None, since=NEWS_SINCE):
    """Press releases, newest first, until a page holds nothing new or the
    first run reaches `since`. Returns (read, new, ours, gaps)."""
    read = new = ours = 0
    skip = 0
    while True:
        if budget is not None and budget.exhausted():
            log(budget.disclose("press release page(s)", skip // NEWS_PAGE))
            break
        url = NEWS_API.format(limit=NEWS_PAGE, skip=skip)
        try:
            total, posts = parse_news(client.get_json(url, FEED, "news-{0}".format(skip)))
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "news skip {0}: {1}".format(skip, exc))
            conn.commit()
            log("  [gap] news skip {0}: {1}".format(skip, exc))
            return read, new, ours, 1
        fresh = 0
        oldest = None
        for p in posts:
            known = conn.execute("SELECT 1 FROM hn_news WHERE post_id=?",
                                 (p["post_id"],)).fetchone()
            fresh += not known
            ours += on_our_ground(store_news(conn, p, tax, today))
            read += 1
            oldest = min(oldest or p["created_at"] or "", p["created_at"] or "")
        new += fresh
        conn.commit()
        skip += NEWS_PAGE
        if not posts or fresh == 0 or (oldest and oldest[:10] < since) \
                or (total is not None and skip >= total):
            break
    return read, new, ours, 0


def gazette_months(conn, today):
    """(year, month) pairs to read: the current and previous month, or every
    month since GACETA_SINCE on the first run (no issue stored yet)."""
    d = datetime.date.fromisoformat(today)
    cur = (d.year, d.month)
    prev = (d.year - 1, 12) if d.month == 1 else (d.year, d.month - 1)
    if conn.execute("SELECT COUNT(*) FROM hn_gazette").fetchone()[0]:
        return [prev, cur]
    months, (y, m) = [], GACETA_SINCE
    while (y, m) <= cur:
        months.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return months


def pull_gazette(conn, client, today, tax=None, log=print, budget=None):
    """La Gaceta's issues, month by month. Returns (issues, ours, gaps)."""
    read = ours = gaps = 0
    for year, month in gazette_months(conn, today):
        start, done = 0, set()
        while start is not None and start not in done:
            if budget is not None and budget.exhausted():
                log(budget.disclose("Gaceta page(s)", read))
                conn.commit()
                return read, ours, gaps
            done.add(start)
            url = GACETA_MONTH.format(year=year, month=MONTHS[month - 1])
            if start:
                url += "?start={0}".format(start)
            try:
                page = client.get_text(url, FEED, "gaceta-{0}-{1:02d}-{2}".format(
                    year, month, start))
            except FetchError as exc:
                _gap(conn, today, "gaceta {0}-{1:02d} start {2}: {3}".format(
                    year, month, start, exc))
                log("  [gap] gaceta {0}-{1:02d}: {2}".format(year, month, exc))
                gaps += 1
                break
            issues, starts = parse_gazette(page)
            for g in issues:
                ours += on_our_ground(store_issue(conn, g, tax, today))
                read += 1
            later = [s for s in starts if s > start]
            start = later[0] if later and issues else None
    conn.commit()
    return read, ours, gaps


def reclassify(conn, tax=None, log=print):
    """Re-derive every row's areas, offline, after a taxonomy or watchlist change."""
    changed = 0
    specs = (
        ("hn_bills", "project_id", "numero", ("titulo",)),
        ("hn_agenda_items", "room_item_id", "project_number", ("name",)),
        ("hn_news", "post_id", None, ("title", "description", "body")),
        ("hn_gazette", "issue", None, ("summary",)),
    )
    for table, key, num, cols in specs:
        sel = ", ".join([key, num or "NULL", "areas"] + list(cols))
        for row in conn.execute("SELECT {0} FROM {1}".format(sel, table)).fetchall():
            texts = list(row[3:])
            if table == "hn_agenda_items":
                t = conn.execute("SELECT titulo FROM hn_bills WHERE numero=?",
                                 (row[1],)).fetchone() if row[1] else None
                texts.append(t[0] if t else None)
            areas, terms, tier = classify(tax, row[1], *texts)
            new = _areas_sql(areas)
            changed += new != row[2]
            conn.execute("UPDATE {0} SET areas=?, matched_terms=?, tier=? WHERE {1}=?".format(
                table, key), (new, hn_store.dumps(terms), tier, row[0]))
    conn.commit()
    log("hn-rollcalls: reclassified; {0} row(s) changed area".format(changed))
    return changed


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731

    def ours(table):
        rows = conn.execute("SELECT areas FROM {0} WHERE areas IS NOT NULL".format(table))
        return sum(on_our_ground(json.loads(a)) for (a,) in rows)
    log("  store: {0} member(s); {1} session(s), {2} with agenda read; {3} agenda item(s), "
        "{4} on our ground, {5} with a resultado; {6} expediente(s), {7} on our ground; "
        "{8} press release(s), {9} on our ground; {10} Gaceta issue(s), {11} on our "
        "ground".format(
            n("SELECT COUNT(*) FROM hn_members"), n("SELECT COUNT(*) FROM hn_sessions"),
            n("SELECT COUNT(*) FROM hn_sessions WHERE agenda_read IS NOT NULL"),
            n("SELECT COUNT(*) FROM hn_agenda_items"), ours("hn_agenda_items"),
            n("SELECT COUNT(*) FROM hn_agenda_items WHERE resultado IS NOT NULL"),
            n("SELECT COUNT(*) FROM hn_bills"), ours("hn_bills"),
            n("SELECT COUNT(*) FROM hn_news"), ours("hn_news"),
            n("SELECT COUNT(*) FROM hn_gazette"), ours("hn_gazette")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--taxonomy", help="classify with this taxonomy file "
                                       "(default config/taxonomy-es.yaml when it exists)")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--no-sessions", action="store_true", help="skips agendas too")
    ap.add_argument("--no-expedientes", action="store_true")
    ap.add_argument("--no-news", action="store_true")
    ap.add_argument("--no-gazette", action="store_true")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for every stored row, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--limit", type=int, help="read at most this many agendas")
    args = ap.parse_args()
    tax = load_taxonomy(args.taxonomy)
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn, tax)
        summary(conn)
        conn.close()
        return 0
    if tax is None:
        print("hn-rollcalls: no Spanish taxonomy yet (config/taxonomy-es.yaml); "
              "areas stay NULL, only watchlist-hn lends areas")
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"), throttle=THROTTLE_S)
    today = datetime.date.today().isoformat()
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    if not args.no_members:
        n, g = pull_members(conn, client, today)
        gaps += g
        print("hn-rollcalls: {0} deputy record(s), {1} gap(s)".format(n, g))
    if not args.no_expedientes:
        n, o, g = pull_expedientes(conn, client, today, tax=tax)
        gaps += g
        print("hn-rollcalls: {0} recent expediente(s) read, {1} on our ground, "
              "{2} gap(s)".format(n, o, g))
    if not args.no_news:
        n, new, o, g = pull_news(conn, client, today, tax=tax, budget=budget)
        gaps += g
        print("hn-rollcalls: {0} press release(s) read, {1} new, {2} on our ground, "
              "{3} gap(s)".format(n, new, o, g))
    if not args.no_gazette:
        n, o, g = pull_gazette(conn, client, today, tax=tax, budget=budget)
        gaps += g
        print("hn-rollcalls: {0} Gaceta issue(s) read, {1} on our ground, "
              "{2} gap(s)".format(n, o, g))
    if not args.no_sessions:
        n, g = pull_sessions(conn, client, today)
        gaps += g
        print("hn-rollcalls: {0} session(s) listed, {1} gap(s)".format(n, g))
        r, s, o, g = pull_agendas(conn, client, today, tax=tax, budget=budget,
                                  limit=args.limit)
        gaps += g
        print("hn-rollcalls: {0} agenda(s) read, {1} item(s) stored, {2} on our ground, "
              "{3} gap(s)".format(r, s, o, g))
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
