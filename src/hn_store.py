"""Tables for the Honduras monitor (phase 1, 9 October 2026): the Congreso
Nacional's deputies, sessions, session agendas (orden del día), legislative
files (expedientes), press releases, and the issues of La Gaceta.

See docs/honduras-scope.md for what was measured and why. The schema follows
the US and Spain precedent (src/us_store.py, src/es_store.py): its own
module, idempotent statements, created by db.init_db so every store carries
it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/hn_*.py writes these tables,
and nothing here touches another jurisdiction's table.

THERE ARE NO RECORDED VOTES. The Congreso's own system (the "matizzo" API
behind congresonacional.hn) has a `resultado` field on every agenda item and
a `totalVotaciones` counter on its dashboard; on 9 October 2026 the first
was null on all 1,000-odd items and the second was 0 for the whole year.
So there is no hn_divisions and no hn_votes: an item's `status` code is the
only trace of what happened to it, and its meaning is not published
(docs/honduras-scope.md lists the codes seen).

KEYS. A legislative file is keyed on the Congreso's own internal id
(`legislativeProjectId`, 1319) and carries its public number
(`EXP-2026-1241`), which is what the watchlist uses: a number is exact, a
title is not ("Reforma al artículo 5 de la Ley de reactivación económica"
appears twice on one agenda, as two files). An agenda item is its
`roomItemId`, a session its `roomId`, a press release its Mongo `_id`, an
issue of La Gaceta its printed number (37241).

PERSONAL DATA. The members endpoint also returns each deputy's national
identity number (`userDocument`) and e-mail. Neither is stored: the monitor
needs a name, a party and a department, and a DNI is not ours to keep.

AREAS ARE NULL UNTIL A SPANISH TAXONOMY EXISTS. NULL means unclassified,
'[]' means classified and on nobody's ground. The English taxonomy is not
used: it is blind to Spanish (measured: 0 of 871 agenda items).
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS hn_members (
        user_id      INTEGER PRIMARY KEY, -- the Congreso's own user id
        display_name TEXT,                -- 'GODOFREDO FAJARDO RAMÍREZ', as printed
        departamento TEXT,
        party        TEXT,
        role         TEXT,                -- 'VP', ... as printed; meaning not published
        is_active    INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS hn_sessions (
        room_id      INTEGER PRIMARY KEY,
        name         TEXT,                -- 'SESIÓN PLENARIA 20 DE MAYO DEL 2026'
        list_name    TEXT,                -- 'Plenaria' or the committee's name
        room_type    TEXT,                -- 'Ordinaria', ...
        room_state   TEXT,                -- 'Finalizada', ...
        schedule     TEXT,                -- 'YYYY-MM-DD HH:MM:SS', Tegucigalpa time
        schedule_end TEXT,
        youtube_url  TEXT,
        agenda_items INTEGER,             -- items on the last agenda read; NULL = not read
        agenda_read  TEXT,                -- ISO date the agenda was last read
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS hn_agenda_items (
        room_item_id INTEGER PRIMARY KEY,
        room_id      INTEGER NOT NULL,
        list_name    TEXT,                -- copied from the session, for reading alone
        name         TEXT,                -- the item, as printed
        item_type    INTEGER,             -- roomItemType: 4, 5, 6, 7 seen; unpublished meaning
        status       INTEGER,             -- 0, 1, 3, 4, 6 seen; unpublished meaning
        item_order   INTEGER,
        author_name  TEXT,
        project_id   INTEGER,             -- legislativeProjectId, or NULL
        project_number TEXT,              -- 'EXP-2026-0721', or NULL
        resultado    TEXT,                -- raw JSON; null on every item so far
        areas        TEXT,                -- JSON list, NULL = unclassified
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS hn_bills (
        project_id   INTEGER PRIMARY KEY, -- legislativeProjectId
        numero       TEXT,                -- 'EXP-2026-1241'
        titulo       TEXT,
        estado       TEXT,                -- 'Iniciativa', 'EnComision', 'EnDebate', 'Aprobado'; NULL if only seen on an agenda
        fecha        TEXT,                -- the API's fechaCreacion; moves with the estado (see scope)
        gaceta       TEXT,
        doc_file     TEXT,
        areas        TEXT,
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS hn_news (
        post_id      TEXT PRIMARY KEY,
        created_at   TEXT,                -- ISO timestamp, UTC
        title        TEXT,
        description  TEXT,
        body         TEXT,                -- plain text decoded from the Draft.js blocks
        areas        TEXT,
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS hn_gazette (
        issue        INTEGER PRIMARY KEY, -- La Gaceta's printed number: 37241
        date         TEXT,                -- ISO date of the issue
        summary      TEXT,                -- the listing's sumario text, as printed
        url          TEXT,                -- the PDF download link (not fetched: up to 28 MB)
        areas        TEXT,
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS hn_agenda_items_room ON hn_agenda_items (room_id)",
    "CREATE INDEX IF NOT EXISTS hn_agenda_items_project ON hn_agenda_items (project_id)",
    "CREATE INDEX IF NOT EXISTS hn_bills_numero ON hn_bills (numero)",
)

TABLES = ("hn_members", "hn_sessions", "hn_agenda_items", "hn_bills", "hn_news",
          "hn_gazette")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- the Honduran watchlist, applied by expediente NUMBER ---------------------

_WATCH = {}
WATCHLIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "config", "watchlist-hn.yaml")


def watchlist(path=None):
    """{numero: (areas, why)} from config/watchlist-hn.yaml."""
    import yaml
    path = path or WATCHLIST
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {str(k): (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("expedientes") or {}).items()}
    return _WATCH[path]


def watch_areas(numero, path=None):
    """The watched areas of one expediente number, or []."""
    hit = watchlist(path).get(numero or "")
    return list(hit[0]) if hit else []


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
