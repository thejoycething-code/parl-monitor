"""Tables for the Dominican Republic Congress monitor (phase 1, 9 October
2026): the Camara de Diputados' iniciativas, plenary sessions, recorded
votes and each deputy's position, all from the Chamber's SIL Ciudadano.

See docs/dominican-republic-scope.md for what was measured and why. The
schema follows the US and Peru precedents (src/us_store.py, the Peru
branch's src/pe_store.py): its own module, idempotent statements, created by
db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/do_*.py writes these tables,
and nothing here touches another jurisdiction's table.

ONE CHAMBER'S SYSTEM, BOTH CHAMBERS' BILLS. The Chamber's SIL registers
every iniciativa that reaches the Chamber, including those begun in the
Senate (`origin` = 'Senado'), under a Chamber number. The Senate's own
system is a separate, login-fronted legacy application (the scope doc
explains why phase 1 does not use it), and its votes reach the public only
as totals in the actas. So `do_divisions` holds Chamber votes only.

KEYS. An iniciativa is the Chamber's own number string, exactly as the SIL
prints it: '06342-2024-2028-CD', '11466-2020-2024-CD'. The sequence
restarts each four-year period, so the bare number is never a key and the
title never is. `sil_id` is the SIL's internal id, used only to ask for the
record again. A member is 'cd/<legisladorId>' (the SIL's legislator id,
stable across periods). A session is the SIL's `sesionId`; a division is
'cd/<votacion id>', the SIL's own id for the vote.

POSITIONS ARE READ SELECTIVELY. The SIL serves a vote's positions ten
deputies a page, 19 requests per vote of a 190-member chamber, and most
votes are unanimous procedure (the order of the day, a committee transfer).
So every vote's header (counts, motion text) is stored, and positions are
read for votes on our ground, votes naming a watched iniciativa, and every
contested vote (any No or abstention). `positions_read` says which.

PARTY IS STORED PER VOTE: `do_votes.party` is the siglas the vote record
carries; `do_members.party` is only the latest seen.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS do_members (
        member_key   TEXT PRIMARY KEY,   -- 'cd/3680' (SIL legisladorId)
        legislador_id INTEGER NOT NULL,
        name         TEXT,               -- 'Abelardo Antonio Rutinel Arzeno', as the SIL prints it
        role         TEXT,               -- funcion: 'Diputado', 'Diputada', 'Senadora', ...
        party        TEXT,               -- siglas, latest seen: 'PRM', 'FP', 'PLD'
        province     TEXT,
        constituency TEXT,               -- circunscripcion
        period       TEXT,               -- '2024-2028'
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS do_bills (
        bill_key     TEXT PRIMARY KEY,   -- '06342-2024-2028-CD', never the title
        sil_id       INTEGER,            -- the SIL's own id (detail requests only)
        period       TEXT NOT NULL,      -- '2024-2028'
        kind         TEXT,               -- tipo: 'Proyecto de Ley', 'Resolución', ...
        origin       TEXT,               -- camaraInicio: 'Cámara de Diputados' / 'Senado'
        title        TEXT,               -- descripcion
        subject      TEXT,               -- materia, the SIL's own subject heading
        topic_group  TEXT,               -- grupo: 'Género / Familia', 'Justicia', ...
        status       TEXT,               -- estado, the Chamber's own words
        condition    TEXT,               -- condicion: 'VIGENTE', 'PERIMIDO', ...
        deposited    TEXT,               -- ISO date
        taken_up     TEXT,               -- fechaIniciado, ISO date
        law_number   TEXT,               -- numPromulgacion, once promulgated
        promulgated  TEXT,
        last_change  TEXT,               -- fechaUltimoCambioPrincipal, ISO
        areas        TEXT,               -- JSON list; taxonomy + watchlist-do by key
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS do_sessions (
        session_id   INTEGER PRIMARY KEY, -- SIL sesionId
        number       TEXT,               -- '00011-2026-SLO'
        date         TEXT,               -- ISO date
        kind         TEXT,               -- 'Ordinaria' / 'Extraordinaria'
        status       TEXT,
        legislature  TEXT,               -- '2026-SLO'
        period       TEXT,
        votes        INTEGER,            -- vote headers stored for it
        votes_read   TEXT,               -- date the vote list was read whole
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS do_divisions (
        division_key TEXT PRIMARY KEY,   -- 'cd/22790'
        session_id   INTEGER,
        session_number TEXT,
        number       TEXT,               -- numeroVotacion: '002'
        date         TEXT,               -- ISO date
        title        TEXT,               -- 'Sesión 011, Votación 002'
        motion       TEXT,               -- mocion, what was put to the vote
        yes          INTEGER,
        no           INTEGER,
        abstain      INTEGER,
        total_votes  INTEGER,            -- cantidadTotalVotos
        present      INTEGER,            -- cantidadPresentes
        members      INTEGER,            -- cantidadDelegados
        bill_refs    TEXT,               -- JSON list of bill_keys the motion names
        own_areas    TEXT,               -- JSON: matched on the motion itself
        areas        TEXT,               -- JSON: own + the named bills'
        matched_terms TEXT,
        tier         INTEGER,
        positions_read INTEGER DEFAULT 0, -- 1 once every position is stored
        positions    INTEGER,            -- how many were stored
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS do_votes (
        division_key TEXT NOT NULL,
        member_key   TEXT NOT NULL,      -- 'cd/<legisladorId>'
        name         TEXT,               -- as the vote record prints it: 'ABREU POLANCO ANA ...'
        party        TEXT,               -- AT THE VOTE: siglas
        position     TEXT,               -- votoId as the SIL gives it: 'SI', 'NO', 'SV', ...
        label        TEXT,               -- voto: 'SI', 'No Voto', ...
        PRIMARY KEY (division_key, member_key)
    )""",
    "CREATE INDEX IF NOT EXISTS do_votes_member ON do_votes (member_key)",
    "CREATE INDEX IF NOT EXISTS do_divisions_session ON do_divisions (session_id)",
)

TABLES = ("do_members", "do_bills", "do_sessions", "do_divisions", "do_votes")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- watchlist ---------------------------------------------------------------

WATCHLIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "config", "watchlist-do.yaml")


def watchlist(path=None):
    """{bill_key: (areas, why)} from config/watchlist-do.yaml. Keyed by the
    iniciativa number string, never the title."""
    import yaml
    path = path or WATCHLIST
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    out = {}
    for key, spec in (raw.get("bills") or {}).items():
        spec = spec or {}
        out[str(key)] = (sorted(int(a) for a in (spec.get("areas") or [])), spec.get("why"))
    return out


def add_watch_areas(res, bill_key, path=None, wl=None):
    """Union a watched iniciativa's areas into a FilterResult, in place, and
    say so in watchlist_hits so the stored row shows where the area came from."""
    hit = (wl if wl is not None else watchlist(path)).get(bill_key)
    if not hit:
        return res
    areas, _why = hit
    res.issue_areas = sorted(set(res.issue_areas or []) | set(areas))
    res.watchlist_hits = list(res.watchlist_hits or []) + ["watch:" + bill_key]
    if res.tier is None:
        res.tier = 2
    return res


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
