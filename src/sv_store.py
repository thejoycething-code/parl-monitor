"""Tables for the El Salvador monitor (phase 1, 9 October 2026): the Asamblea
Legislativa's deputies, plenary sessions, committee reports (dictámenes),
incoming correspondence (piezas), recorded votes and every deputy's position.

See docs/el-salvador-scope.md for what was measured and why. The schema
follows the US and Spain precedent: its own module, idempotent statements,
created by db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/sv_*.py writes these tables, and
nothing here touches another jurisdiction's table.

KEYS, never titles.
  * A bill's own ID is the Asamblea's EXPEDIENTE number, '755-9-2026-1',
    printed on every dictamen. The watchlist is keyed by it.
  * A dictamen is '<legislature>/<committee id>/<number>',
    '2024-2027/97/266': numbers run per committee within a legislature.
  * A pieza (a piece of correspondence: an initiative, a request) is
    '<legislature>/<session>/<order>A', '2024-2027/128/2A', the number the
    plenary reads it under. A pieza approved the same day "con dispensa de
    trámite" never goes to committee and is never seen with an expediente,
    so its pieza key is the only key it ever has.
  * A recorded vote is 'sv-<document GUID>', the GUID the Asamblea files the
    vote's PDF under. The vote list carries nothing else stable.

A DEPUTY'S NAME IN A VOTE IS SHORT. The vote PDFs print "KALEFF BONILLA",
the members page "Kaleff ... Bonilla ...". Positions are stored under the
name the vote printed, with the party the vote printed beside it; the
members table is the roster, joined later if a surface needs it.

AREAS ARE NULL UNTIL A SPANISH TAXONOMY EXISTS. NULL means unclassified,
'[]' means classified and on nobody's ground. The English taxonomy is blind
to Spanish (docs/germany-scope.md, docs/el-salvador-scope.md).
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS sv_members (
        member_id    TEXT PRIMARY KEY,    -- the Asamblea's GUID for the deputy
        name         TEXT NOT NULL,       -- full name as the members page prints it
        party        TEXT,                -- 'NI', 'ARENA', 'PCN', 'PDC', 'VAMOS' (latest seen)
        department   TEXT,
        cargo        TEXT,                -- 'Diputado propietario' / 'Diputada suplente'
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS sv_sessions (
        session_key  TEXT PRIMARY KEY,    -- '2024-2027/Ordinaria/128'
        legislature  TEXT NOT NULL,
        tipo         TEXT,                -- 'Ordinaria', 'Extraordinaria', 'Solemne', 'Instalación'
        numero       INTEGER,
        date         TEXT,                -- ISO
        codigo       TEXT,                -- the Asamblea's GUID for the session
        resumen_url  TEXT,                -- the session summary PDF
        agenda_url   TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS sv_dictamenes (
        dictamen_key TEXT PRIMARY KEY,    -- '2024-2027/97/266'
        legislature  TEXT NOT NULL,
        comision_id  TEXT,
        comision     TEXT,                -- 'Hacienda y Especial del Presupuesto'
        numero       INTEGER,
        resultado    TEXT,                -- 'Favorable', 'Desfavorable', 'Archivo', ...
        expediente   TEXT,                -- '755-9-2026-1': the bill's own ID
        extracto     TEXT,                -- what the report is about, as printed
        session_key  TEXT,
        orden_plenaria INTEGER,
        pdf_url      TEXT,
        areas        TEXT,                -- JSON list, NULL = unclassified
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS sv_piezas (
        pieza_key    TEXT PRIMARY KEY,    -- '2024-2027/128/2A'
        legislature  TEXT NOT NULL,
        session_key  TEXT,
        orden        INTEGER,
        leyenda      TEXT,                -- the short title
        extracto     TEXT,                -- the full extract read to the plenary
        pdf_url      TEXT,
        areas        TEXT,
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS sv_divisions (
        division_key TEXT PRIMARY KEY,    -- 'sv-<document GUID>'
        legislature  TEXT NOT NULL,
        session      INTEGER,
        date         TEXT,                -- ISO
        label        TEXT,                -- the vote list's own words
        kind         TEXT,                -- 'dictamen', 'pieza', 'other'
        stage        TEXT,                -- pieza: 'DT' dispensa de trámite, 'FS' fondo
        item_key     TEXT,                -- dictamen_key or pieza_key once linked
        expediente   TEXT,
        pdf_url      TEXT,
        meeting      TEXT,                -- 'PLENARIA ORDINARIA #129', from the PDF
        vote_name    TEXT,                -- from the PDF
        started      TEXT,                -- ISO timestamp, from the PDF
        yes          INTEGER,
        no           INTEGER,
        abstain      INTEGER,
        not_voted    INTEGER,
        groups       TEXT,                -- JSON {party: [yes, no]}
        positions    INTEGER,             -- positions stored; NULL until the PDF is read
        areas        TEXT,                -- JSON: the linked item's; NULL = unclassified
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS sv_votes (
        division_key TEXT NOT NULL,
        name         TEXT NOT NULL,       -- as the vote PDF printed it
        party        TEXT,                -- AT THE VOTE
        position     TEXT,                -- 'SI' / 'NO' / 'ABST' / 'No Votado'
        PRIMARY KEY (division_key, name)
    )""",
    """CREATE TABLE IF NOT EXISTS sv_vote_days (
        day          TEXT PRIMARY KEY,    -- ISO date asked of the session archive
        legislature  TEXT,
        sessions     INTEGER,             -- sessions the archive returned (0: none)
        archived     INTEGER,             -- 1 answered; 0 retry; -1 vote day never filed (gap)
        fetched_at   TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS sv_divisions_item ON sv_divisions (item_key)",
    "CREATE INDEX IF NOT EXISTS sv_dictamenes_expediente ON sv_dictamenes (expediente)",
    "CREATE INDEX IF NOT EXISTS sv_votes_member ON sv_votes (name)",
)

TABLES = ("sv_members", "sv_sessions", "sv_dictamenes", "sv_piezas",
          "sv_divisions", "sv_votes", "sv_vote_days")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- the watchlist, applied by KEY ----------------------------------------------
#
# Expedientes first (a bill's own ID); pieza keys only for items fast-tracked
# with dispensa de trámite, which never receive a visible expediente.

_WATCH = {}
WATCHLIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "config", "watchlist-sv.yaml")


def watchlist(path=None):
    """{key: (areas, why)} from config/watchlist-sv.yaml (expedientes and piezas)."""
    import yaml
    path = path or WATCHLIST
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        out = {}
        for section in ("expedientes", "piezas"):
            for k, v in (raw.get(section) or {}).items():
                out[str(k)] = (list((v or {}).get("areas") or []), (v or {}).get("why"))
        _WATCH[path] = out
    return _WATCH[path]


def watch_areas(*keys, path=None):
    """The watched areas of any of these keys, or []."""
    areas = set()
    wl = watchlist(path)
    for k in keys:
        hit = wl.get(k or "")
        if hit:
            areas |= set(hit[0])
    return sorted(areas)


def dumps(values):
    return json.dumps(values if values is not None else [], ensure_ascii=False)
