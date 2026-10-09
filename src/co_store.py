"""Tables for the Colombia Congress monitor (phase 1, 9 October 2026):
proyectos de ley from both chambers, Cámara plenary attendance, members, and
the Senate's published plenary roll calls with every senator's position.

See docs/colombia-scope.md for what was measured and why. Own module, as for
Canada, the US and Australia: idempotent statements, created by db.init_db so
every store carries them and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/co_*.py writes these tables, and
nothing here touches another jurisdiction's table.

KEYS. A proyecto is '<chamber>/<year>/<number>' in the chamber that gave the
number: 'camara/2026/426', 'senado/2026/289'. Numbers restart every
legislatura year, and a bill that crosses chambers carries a number in each,
so one bill can have two rows, linked by `other_key`. Never a title: the
Cámara files several bills a year under the same nickname
("TARIFA ESPECIAL PARA ENTIDADES RELIGIOSAS" is both 058/2026C and 361/2026C).

A member is '<chamber>/<folded name>': no source shared by both chambers
carries a stable member ID (docs/colombia-scope.md, "Members").

AREAS ARE EMPTY UNTIL A SPANISH TAXONOMY IS APPROVED. The English taxonomy
matched 2 of 2,405 Cámara bills of the last four legislaturas. Until
config/taxonomy-es.yaml exists, `areas` holds only what
config/watchlist-co.yaml gives a bill by its key.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS co_bills (
        bill_key      TEXT PRIMARY KEY,   -- 'camara/2026/426'
        chamber       TEXT NOT NULL,      -- 'camara' / 'senado': the chamber that numbered it
        year          INTEGER NOT NULL,
        number        INTEGER NOT NULL,
        other_key     TEXT,               -- the same bill's number in the other chamber
        kind          TEXT,               -- 'Ley Ordinaria', 'Acto Legislativo', ...
        nickname      TEXT,               -- the Cámara's short name ('LEY LOS PADRES EDUCAN')
        title         TEXT,
        objeto        TEXT,               -- 'objeto del proyecto' (Cámara open data only)
        status        TEXT,               -- the chamber's own estado, verbatim
        origin        TEXT,               -- 'Cámara' / 'Senado'
        committee     TEXT,
        legislatura   TEXT,               -- '2026-2027'
        authors       TEXT,
        filed_at      TEXT,
        url           TEXT,
        source        TEXT,               -- which feed last wrote the row
        areas         TEXT,               -- JSON list; taxonomy-es (when approved) + watchlist-co by key
        matched_terms TEXT,               -- JSON list
        tier          INTEGER,
        first_seen    TEXT,
        last_seen     TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS co_members (
        member_key  TEXT PRIMARY KEY,     -- 'camara/abasolo gomez alejandra gabriela'
        chamber     TEXT NOT NULL,
        name        TEXT,
        party       TEXT,                 -- latest seen
        department  TEXT,
        source      TEXT,
        first_seen  TEXT,
        last_seen   TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS co_attendance (
        member_key  TEXT NOT NULL,
        session     TEXT NOT NULL,        -- the open-data column: 'sesi_n_plenaria_cp_20_07_2026'
        date        TEXT,                 -- '2026-07-20'
        joint       INTEGER,              -- 1 for a joint sitting (Congreso pleno, 'CP')
        status      TEXT,                 -- 'ASISTIO', 'EXCUSA', ... verbatim
        PRIMARY KEY (member_key, session)
    )""",
    """CREATE TABLE IF NOT EXISTS co_divisions (
        division_key TEXT PRIMARY KEY,    -- 'senado-2017-02-14-<hash of the question>'
        chamber      TEXT NOT NULL,
        date         TEXT NOT NULL,
        question     TEXT,                -- what was put, verbatim
        bill_key     TEXT,                -- parsed from the question; NULL when it names none
        yes          INTEGER,
        no           INTEGER,
        source       TEXT,
        areas        TEXT,                -- the bill's, by key
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS co_votes (
        division_key TEXT NOT NULL,
        member_key   TEXT NOT NULL,
        position     TEXT NOT NULL,       -- 'yes' / 'no' (the Senate file carries no other value)
        PRIMARY KEY (division_key, member_key)
    )""",
    "CREATE INDEX IF NOT EXISTS co_divisions_bill ON co_divisions(bill_key)",
    "CREATE INDEX IF NOT EXISTS co_votes_member ON co_votes(member_key)",
)


def ensure_schema(conn):
    for statement in SCHEMA:
        conn.execute(statement)
    conn.commit()
    return conn


def dumps(value):
    return json.dumps(sorted(set(value or [])) if isinstance(value, (list, set, tuple))
                      else value, ensure_ascii=False)


# --- the Colombian watchlist, applied by bill KEY -----------------------------

_WATCH = {}


def watchlist(path=None):
    """{bill_key: (areas, why)} from config/watchlist-co.yaml."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-co.yaml")
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {k: (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("bills") or {}).items()}
    return _WATCH[path]
