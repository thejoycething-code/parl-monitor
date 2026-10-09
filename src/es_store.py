"""Tables for the Spain monitor (phase 1, 9 October 2026): the Congreso de
los Diputados' members, legislative initiatives, plenary votes and every
deputy's position.

See docs/spain-scope.md for what was measured and why. The schema follows the
US precedent (src/us_store.py): its own module, idempotent statements,
created by db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/es_*.py writes these tables,
and nothing here touches another jurisdiction's table.

KEYS. An initiative is '<legislature>/<type>/<number>', '15/122/000001': the
Congreso's own expediente number, which restarts every legislature, so the
legislature is part of the key. A division is
'congreso-<legislature>-<session>-<vote>', 'congreso-15-202-1', from the
path the Congreso publishes it under. Never a title: a dozen motions a year
share the title "Proposición no de Ley relativa a ...".

A DEPUTY HAS NO PUBLISHED ID. The open data names a deputy only by
"Surname Surname, Forename", in the members files and in every vote file
alike, so a member is (legislature, name), exactly as printed. The vote
stores the name it printed; the join is on that string.

THE GROUP IS STORED PER VOTE, as party is in Canada and the US:
`es_votes.grupo` is the parliamentary group code the vote file printed
('GP', 'GS', 'GVOX'). `es_members.grupo` is only the latest seen.

AN INITIATIVE DIES WITH ITS LEGISLATURE. A dissolution ends every pending
initiative (it 'caduca'), whatever its record says; the open data marks
most of them 'Concluido - (Caducado)' within days, but on 9 October 2026,
three days after the dissolution of 6 October, 109 proposiciones de ley still
read 'Pleno, Toma en consideración'. `es_initiatives.legislature` is what a
board must read, never `situacion`.

AREAS ARE NULL UNTIL A SPANISH TAXONOMY EXISTS. NULL means unclassified,
'[]' means classified and on nobody's ground. The English taxonomy is not
used: it is blind to Spanish, as it was to German (docs/spain-scope.md).
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS es_members (
        legislature  INTEGER NOT NULL,
        name         TEXT NOT NULL,       -- 'Abascal Conde, Santiago', as printed
        circunscripcion TEXT,
        formacion    TEXT,                -- electoral list: 'PSC-PSOE', 'VOX'
        grupo        TEXT,                -- parliamentary group, latest seen (full name)
        alta         TEXT,                -- ISO date the seat was taken
        baja         TEXT,                -- ISO date it was left; NULL while sitting
        first_seen   TEXT,
        last_seen    TEXT,
        PRIMARY KEY (legislature, name)
    )""",
    """CREATE TABLE IF NOT EXISTS es_initiatives (
        initiative_key TEXT PRIMARY KEY,  -- '15/122/000001'
        legislature  INTEGER NOT NULL,
        expediente   TEXT NOT NULL,       -- '122/000001', as the Congreso prints it
        tipo         TEXT,                -- 'Proyecto de ley', 'Proposición de ley de ...'
        objeto       TEXT,                -- the title, whitespace folded
        autor        TEXT,
        presentada   TEXT,                -- ISO date
        calificada   TEXT,
        tipo_tramitacion TEXT,
        comision     TEXT,
        situacion    TEXT,                -- the Congreso's own words; see the docstring
        resultado    TEXT,
        tramitacion  TEXT,                -- the procedural history, as printed
        bocg         TEXT,                -- first BOCG link
        areas        TEXT,                -- JSON list, NULL = unclassified
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS es_divisions (
        division_key TEXT PRIMARY KEY,    -- 'congreso-15-202-1'
        chamber      TEXT NOT NULL,       -- 'congreso' (the Senado refuses us; see scope)
        legislature  INTEGER NOT NULL,
        session      INTEGER NOT NULL,
        vote_number  INTEGER NOT NULL,
        date         TEXT,                -- ISO date
        session_title TEXT,               -- 'Sesión Plenaria número 202'
        section      TEXT,                -- 'Proposiciones no de Ley.'
        title        TEXT,                -- the item voted on
        subgroup     TEXT,                -- 'Votación separada por puntos. Punto 1.', 'Enmiendas ...'
        expediente   TEXT,                -- '162/000814', or NULL
        initiative_key TEXT,              -- '15/162/000814', or NULL
        assent       INTEGER,             -- 1 when agreed by assent (no positions)
        present      INTEGER,
        yes          INTEGER,
        no           INTEGER,
        abstain      INTEGER,
        not_voting   INTEGER,
        json_url     TEXT,                -- the vote file; positions are read from it
        positions    INTEGER,             -- positions stored; NULL until the file is read
        own_areas    TEXT,                -- JSON: matched on the vote's OWN text
        areas        TEXT,                -- JSON: own + its initiative's; NULL = unclassified
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS es_votes (
        division_key TEXT NOT NULL,
        name         TEXT NOT NULL,       -- as the vote file printed it
        grupo        TEXT,                -- AT THE VOTE: 'GP', 'GS', 'GVOX', ...
        position     TEXT,                -- 'Sí' / 'No' / 'Abstención' / 'No vota'
        seat         TEXT,                -- '-1' for a remote (telematic) vote
        PRIMARY KEY (division_key, name)
    )""",
    """CREATE TABLE IF NOT EXISTS es_vote_days (
        legislature  INTEGER NOT NULL,
        day          TEXT NOT NULL,       -- ISO date of a day with votes
        listed       INTEGER,             -- vote files the day's page listed
        fetched_at   TEXT,
        PRIMARY KEY (legislature, day)
    )""",
    "CREATE INDEX IF NOT EXISTS es_divisions_initiative ON es_divisions (initiative_key)",
    "CREATE INDEX IF NOT EXISTS es_votes_member ON es_votes (name)",
)

TABLES = ("es_members", "es_initiatives", "es_divisions", "es_votes", "es_vote_days")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- the Spanish watchlist, applied by initiative KEY -----------------------
#
# As in the US: a key is exact, a title is not. "Proposición no de Ley
# relativa a ..." opens hundreds of titles a legislature.

_WATCH = {}
WATCHLIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "config", "watchlist-es.yaml")


def watchlist(path=None):
    """{initiative_key: (areas, why)} from config/watchlist-es.yaml."""
    import yaml
    path = path or WATCHLIST
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {str(k): (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("initiatives") or {}).items()}
    return _WATCH[path]


def watch_areas(initiative_key, path=None):
    """The watched areas of one initiative, or []."""
    hit = watchlist(path).get(initiative_key or "")
    return list(hit[0]) if hit else []


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
