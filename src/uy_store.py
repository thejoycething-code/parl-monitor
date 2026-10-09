"""Tables for the Uruguay monitor (phase 1, 9 October 2026): the Cámara de
Representantes' roll of deputies, its pedidos de informes, its Diario de
Sesiones index, and every law promulgated, from IMPO.

See docs/uruguay-scope.md for what was measured and why. The schema follows
the US and Spain precedent (src/us_store.py, src/es_store.py): its own
module, idempotent statements, created by db.init_db so every store carries
it and db.TABLES stays true.

WHY THERE IS NO uy_votes TABLE. parlamento.gub.uy, which holds the bills
(asuntos), the Senate and every per-legislator page, refuses us with a 403
on every path, robots.txt included, from the laptop and from GitHub's
runners alike. And Uruguay does not record votes by name in the first
place: both chambers vote by show of hands or an anonymous electronic
register, and the Diario de Sesiones prints the totals ("Sesenta y cuatro
votos afirmativos y veintinueve votos negativos en noventa y tres
presentes"), never the names, even for the euthanasia law. Phase 1 stores
what CAN be read: see the scope document.

SEPARATION GUARANTEE. Nothing outside tools/uy_*.py writes these tables,
and nothing here touches another jurisdiction's table.

KEYS. Never a title.
  * a member is (chamber, name), the name exactly as the roll prints it,
    trailing padding stripped: 'ABBONDANZA MENDARO, FLORENCIA'. The open
    data publishes no member ID.
  * a pedido de informe is its oficio number within its legislature,
    'L50/01105', read off the oficio's own document path
    (docs/L50/Oficio/01105.pdf). Measured unique across all 2,526 rows.
  * a sitting is (chamber, diario number): the Diario de Sesiones' own
    running number, 4578.
  * a law is its number, 20431. Uruguay numbers laws in one series that
    never restarts, so the number alone is unique.

AREAS ARE NULL UNTIL A URUGUAYAN TAXONOMY EXISTS. NULL means unclassified,
'[]' means classified and on nobody's ground. The English taxonomy is not
used: it is blind to Spanish (docs/uruguay-scope.md).
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS uy_members (
        chamber      TEXT NOT NULL,       -- 'representantes' (the Senate is unreachable)
        name         TEXT NOT NULL,       -- 'ABDALA SCHWARZ, PABLO DANIEL', as printed
        party        TEXT,                -- 'Frente Amplio', 'Nacional', 'Colorado', ...
        departamento TEXT,
        hoja         TEXT,                -- the ballot (hoja de votación) elected on: '609'
        genero       TEXT,
        first_seen   TEXT,
        last_seen    TEXT,
        PRIMARY KEY (chamber, name)
    )""",
    """CREATE TABLE IF NOT EXISTS uy_questions (
        question_key TEXT PRIMARY KEY,    -- 'L50/01105'
        chamber      TEXT NOT NULL,       -- 'representantes'
        legislature  INTEGER,             -- 50
        date         TEXT,                -- ISO date filed
        organismo    TEXT,                -- the body asked: 'MINISTERIO DE SALUD PÚBLICA'
        autores      TEXT,                -- as printed, comma-separated names
        tema         TEXT,                -- the subject line
        estado       TEXT,                -- 'CONTESTADO', 'SIN CONTESTAR', 'VENCIDO', 'NO ENTREGADO'
        url_oficio   TEXT,
        url_respuesta TEXT,
        areas        TEXT,                -- JSON list, NULL = unclassified
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS uy_sittings (
        chamber      TEXT NOT NULL,       -- 'representantes'
        diario       INTEGER NOT NULL,    -- 4578
        legislature  TEXT,                -- 'L', 'XLIX', as printed (Roman)
        periodo      INTEGER,
        tipo         TEXT,                -- 'ORD'
        sesion       INTEGER,
        sesion_tipo  TEXT,                -- 'ORD', 'EXT', 'ESP'
        date         TEXT,                -- ISO date
        url          TEXT,                -- the Diario's PDF
        first_seen   TEXT,
        last_seen    TEXT,
        PRIMARY KEY (chamber, diario)
    )""",
    """CREATE TABLE IF NOT EXISTS uy_laws (
        law_number   INTEGER PRIMARY KEY, -- 20431
        year         INTEGER,             -- the year in IMPO's address: 20431-2025
        name         TEXT,                -- IMPO's nombreNorma: 'LEY DE MUERTE DIGNA; EUTANASIA'
        promulgated  TEXT,                -- ISO date
        published    TEXT,                -- ISO date in the Diario Oficial
        articles     INTEGER,
        text         TEXT,                -- the articles' text, first 6,000 characters
        url          TEXT,                -- https://www.impo.com.uy/bases/leyes/20431-2025
        areas        TEXT,                -- JSON list, NULL = unclassified
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS uy_questions_date ON uy_questions (date)",
    "CREATE INDEX IF NOT EXISTS uy_sittings_date ON uy_sittings (date)",
)

TABLES = ("uy_members", "uy_questions", "uy_sittings", "uy_laws")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- the Uruguayan watchlist, applied by KEY ---------------------------------
#
# Keys are 'ley:<number>' (a law, as IMPO numbers it) and 'asunto:<number>'
# (the Parliament's own asunto number, the ficha a bill lives under on
# parlamento.gub.uy). Asunto entries cannot be applied until that site
# answers us; they are kept so the bill is known by its key, never its title.

_WATCH = {}
WATCHLIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "config", "watchlist-uy.yaml")


def watchlist(path=None):
    """{key: (areas, why)} from config/watchlist-uy.yaml."""
    import yaml
    path = path or WATCHLIST
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {str(k): (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("watch") or {}).items()}
    return _WATCH[path]


def watch_areas(key, path=None):
    """The watched areas of one key ('ley:20431'), or []."""
    hit = watchlist(path).get(key or "")
    return list(hit[0]) if hit else []


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
