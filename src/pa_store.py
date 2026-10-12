"""Tables for the Panama monitor (phase 1, 9 October 2026): the Asamblea
Nacional's deputies, its anteproyectos and proyectos de ley with their stage
history, and the plenary's orden del dia.

See docs/panama-scope.md for what was measured and why. The schema follows
the US and Spain precedent (src/us_store.py, src/es_store.py): its own
module, idempotent statements, created by db.init_db so every store carries
it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/pa_*.py writes these tables,
and nothing here touches another jurisdiction's table.

NO RECORDED VOTES. The Asamblea votes electronically ("Asamblea 507",
prensa507.asamblea.gob.pa) and projects the board in the chamber, but every
endpoint that returns a session, a vote or a deputy's position answers 401
`invalidSession` without a login, and the public press page shows only the
current day's votes, live. There is therefore no pa_divisions or pa_votes
table: a table we cannot fill would read as "no votes" rather than "no
access". Add them the day a public source exists.

KEYS. A bill is its FICHA, the integer the Asamblea's legislative-tracking
system (segLegis, "Seguimiento Legislativo") gives every item: 8633. An item
starts as an anteproyecto (a deputy's or citizen's draft) and, once
"prohijado" (adopted by a committee) or tabled by the Executive, also gets a
proyecto number; both numbers RESTART every five-year term (the current one
began on 1 July 2024), and two items of one term can share a title, so
neither the numbers nor the title are keys. The ficha is global and stable.
The orden del dia cites a bill as "Proyecto de Ley No. 724", so agenda items
store that number and join on (term, proyecto).

AREAS ARE NULL UNTIL A SPANISH TAXONOMY EXISTS. NULL means unclassified,
'[]' means classified and on nobody's ground. The English taxonomy is not
used: it is blind to Spanish (docs/panama-scope.md).
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS pa_members (
        member_id    INTEGER PRIMARY KEY, -- the Asamblea site's own deputy ID
        name         TEXT NOT NULL,       -- 'MARCOS ENRIQUE CASTILLERO BARAHONA', as printed
        party        TEXT,                -- 'Partido Revolucionario Democrático', 'Libre Postulación'
        province     TEXT,
        circuit      TEXT,                -- electoral circuit, '6-3'
        substitutes  TEXT,                -- suplentes, as printed
        slug         TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS pa_bills (
        ficha        INTEGER PRIMARY KEY, -- segLegis ficha: 8633
        term         TEXT NOT NULL,       -- '2024-2029': the five-year term numbers restart in
        proyecto     INTEGER,             -- proyecto de ley number, NULL until it has one
        anteproyecto INTEGER,             -- anteproyecto number; 0 when it never was one
        presented    TEXT,                -- ISO date of presentation
        title        TEXT,                -- whitespace folded
        stage        TEXT,                -- 'Preliminar', 'Primer Debate', ..., 'Ley', 'Archivado'
        proponent    TEXT,                -- 'H.D ALAIN ALBENIS CEDEÑO HERRERA', a ministry, ...
        has_document INTEGER,             -- 1 when segLegis offers the text
        doc_url      TEXT,                -- https://sistemas.asamblea.gob.pa/segLegis/Documents/<ficha>.pdf
        stage_seen   TEXT,                -- ISO date we first saw the current stage
        stages_read  TEXT,                -- ISO date the stage history was last read; NULL never
        areas        TEXT,                -- JSON list, NULL = unclassified
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS pa_bill_stages (
        ficha        INTEGER NOT NULL,
        seq          INTEGER NOT NULL,    -- 1 = oldest
        date         TEXT,                -- ISO date
        stage        TEXT,                -- 'Segundo Debate'
        comment      TEXT,                -- 'APROBADO EN II DEBATE', 'PENDIENTE DE II DEBATE'
        PRIMARY KEY (ficha, seq)
    )""",
    """CREATE TABLE IF NOT EXISTS pa_agenda (
        doc_id       INTEGER PRIMARY KEY, -- the site's orden-del-dia document ID
        date         TEXT,                -- ISO sitting date, from the document's name
        name         TEXT,                -- 'ORDEN DEL DÍA JUEVES 8 DE OCTUBRE DE 2026'
        url          TEXT,
        items        INTEGER,             -- bill items parsed; NULL until the PDF is read
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS pa_agenda_items (
        doc_id       INTEGER NOT NULL,
        item_no      INTEGER NOT NULL,    -- the agenda's own number
        debate       TEXT,                -- 'Primer', 'Segundo', 'Tercer'
        kind         TEXT,                -- 'Proyecto' or 'Anteproyecto'
        number       INTEGER,             -- the proyecto (or anteproyecto) number, this term
        title        TEXT,
        suspended    INTEGER,             -- 1 when printed '(Suspendido)'
        ficha        INTEGER,             -- joined on (term, number); NULL when unmatched
        PRIMARY KEY (doc_id, item_no)
    )""",
    "CREATE INDEX IF NOT EXISTS pa_bills_proyecto ON pa_bills (term, proyecto)",
    "CREATE INDEX IF NOT EXISTS pa_agenda_items_ficha ON pa_agenda_items (ficha)",
)

TABLES = ("pa_members", "pa_bills", "pa_bill_stages", "pa_agenda", "pa_agenda_items")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- the Panamanian watchlist, applied by FICHA ----------------------------------

_WATCH = {}
WATCHLIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "config", "watchlist-pa.yaml")


def watchlist(path=None):
    """{ficha (int): (areas, why)} from config/watchlist-pa.yaml."""
    import yaml
    path = path or WATCHLIST
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {int(k): (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("bills") or {}).items()}
    return _WATCH[path]


def watch_areas(ficha, path=None):
    """The watched areas of one bill, or []."""
    try:
        hit = watchlist(path).get(int(ficha))
    except (TypeError, ValueError):
        return []
    return list(hit[0]) if hit else []


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
