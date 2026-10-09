"""Tables for the Guatemala monitor (phase 1, 9 October 2026): the Congreso
de la República's deputies, initiatives, plenary votes and every deputy's
position.

See docs/guatemala-scope.md for what was measured and why. The schema follows
the US and Spain precedent (src/us_store.py, src/es_store.py): its own
module, idempotent statements, created by db.init_db so every store carries
it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/gt_*.py writes these tables,
and nothing here touches another jurisdiction's table.

KEYS. An initiative is its registration number, '6844': the Congreso numbers
initiatives in ONE sequence across legislatures (5272 was registered in 2017,
6859 in 2026), so the number alone is unique. A session is the site's own
event id (eventos_votaciones/41385). A division is 'gt-<question id>', the
id in detalle_de_votacion/<question>/<session>. Never a title: every vote on
a bill reads "... DEL PROYECTO DE DECRETO QUE DISPONE APROBAR LA INICIATIVA
DE LEY 6844", and the subject appears nowhere in the vote.

A DEPUTY'S ID IS NOT ON THE VOTE. The member cards carry perfil_diputado/<id>
and print the name forename first ('Luis Fernando Aguirre Estrada'); the
vote pages print it surname first ('Aguirre Estrada Luis Fernando') with no
id. `name_key` (the folded words, sorted) joins the two.

THE BLOC IS NOT ON THE VOTE PAGE. The HTML vote page lists name, presence
and vote only; the bloc at the vote is printed in the PDF of the same vote,
which this collector does not fetch (robots.txt disallows *.pdf; see the
scope doc). `gt_members.bloque` is the latest seen, NOT the bloc at an old
vote: deputies change bloc often in Guatemala.

AREAS ARE NULL UNTIL A SPANISH TAXONOMY EXISTS. NULL means unclassified,
'[]' means classified and on nobody's ground.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS gt_members (
        member_id    TEXT PRIMARY KEY,    -- perfil_diputado/<id>
        name         TEXT NOT NULL,       -- forename first, as the card prints it
        name_key     TEXT NOT NULL,       -- folded words, sorted; joins gt_votes
        bloque       TEXT,                -- latest seen ('VAMOS', 'Independiente')
        distrito     TEXT,                -- 'Lista Nacional', 'Guatemala', ...
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS gt_initiatives (
        numero       TEXT PRIMARY KEY,    -- '6844'
        detail_id    TEXT,                -- detalle_pdf/iniciativas/<id>
        conocio_pleno TEXT,               -- ISO date the plenary took notice
        resumen      TEXT,                -- the listing's summary, as printed
        pdf_url      TEXT,                -- the text (under /assets/uploads/, NOT fetched)
        areas        TEXT,                -- JSON list, NULL = unclassified
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS gt_sessions (
        session_id   TEXT PRIMARY KEY,    -- eventos_votaciones/<id>
        tipo         TEXT,                -- 'Ordinaria', 'Extraordinaria', 'Solemne'
        numero       INTEGER,             -- restarts every legislative year
        date         TEXT,                -- ISO date
        label        TEXT,                -- 'No. 42, Fase 1, Fecha 08/09/2026 12:59:43'
        listed       INTEGER,             -- votes the session page listed; NULL until read
        fetched_at   TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS gt_divisions (
        division_key TEXT PRIMARY KEY,    -- 'gt-51365'
        session_id   TEXT NOT NULL,
        question_id  TEXT NOT NULL,
        number       INTEGER,             -- 'NÚMERO PREGUNTA' within the session
        date         TEXT,                -- ISO date
        time         TEXT,                -- as printed; 12-hour clock without AM/PM
        title        TEXT,                -- the question, as printed
        iniciativa   TEXT,                -- the initiative number the title names, or NULL
        procedural   INTEGER,             -- 1 when no initiative is named
        yes          INTEGER,
        no           INTEGER,
        absent       INTEGER,
        leave        INTEGER,             -- 'LICENCIA / EXCUSA'
        positions    INTEGER,             -- positions stored; NULL until read
        own_areas    TEXT,
        areas        TEXT,                -- own + its initiative's; NULL = unclassified
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS gt_votes (
        division_key TEXT NOT NULL,
        name         TEXT NOT NULL,       -- surname first, as the vote page prints it
        name_key     TEXT NOT NULL,
        estado       TEXT,                -- 'PRESENTE' / 'AUSENTE' / 'LICENCIA / EXCUSA'
        position     TEXT,                -- 'A FAVOR' / 'CONTRA' / 'AUSENTE' / 'LICENCIA'
        PRIMARY KEY (division_key, name)
    )""",
    "CREATE INDEX IF NOT EXISTS gt_divisions_iniciativa ON gt_divisions (iniciativa)",
    "CREATE INDEX IF NOT EXISTS gt_votes_member ON gt_votes (name_key)",
)

TABLES = ("gt_members", "gt_initiatives", "gt_sessions", "gt_divisions", "gt_votes")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


def name_key(name):
    """'Aguirre Estrada Luis Fernando' and 'Luis Fernando Aguirre Estrada'
    -> the same key: accents and case folded, words sorted."""
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return " ".join(sorted(re.findall(r"[a-z0-9]+", text)))


# --- the Guatemalan watchlist, applied by initiative NUMBER -----------------

_WATCH = {}
WATCHLIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "config", "watchlist-gt.yaml")


def watchlist(path=None):
    """{numero: (areas, why)} from config/watchlist-gt.yaml."""
    import yaml
    path = path or WATCHLIST
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {str(k): (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("initiatives") or {}).items()}
    return _WATCH[path]


def watch_areas(numero, path=None):
    hit = watchlist(path).get(str(numero or ""))
    return list(hit[0]) if hit else []


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
