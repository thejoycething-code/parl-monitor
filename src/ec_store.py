"""Tables for the Ecuador monitor (phase 1, 9 October 2026): the Asamblea
Nacional's plenary votes, every member's position, the member register and
the sitting roster with party.

See docs/ecuador-scope.md for what was measured and why. The schema follows
the US and Spain precedent (src/us_store.py, the spain branch's es_store):
its own module, idempotent statements, created by db.init_db so every store
carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/ec_*.py writes these tables, and
nothing here touches another jurisdiction's table.

KEYS. A division is 'ec-<votingId>', 'ec-1004966': the Asamblea's own vote
number in its datos parlamentarios service (datos.asambleanacional.gob.ec),
unique across periods. Never a title: the same "Conocer y resolver respecto
del Informe para Segundo Debate del Proyecto de Ley ..." heads every vote on
a bill, and the vote's `theme` field is sometimes stale (three votes on the
identity-law objection of 25 January 2024 carry the theme "Himno Nacional de
la República del Ecuador"; the real subject is in `proposal`).

NO BILL NUMBER ON A VOTE. The vote service names the bill only in prose.
Bills carry a code ('AN-2024-3009') and a trámite number ('453797') in the
bill systems, but the open bill portal stopped at 2 August 2024 and its
successor needs a login (docs/ecuador-scope.md). So the watchlist is keyed
by division key for now, never by title.

A MEMBER IS A NAME. Positions come as {firstName, lastname, territorial}
with no member id and no party; the member register (`ec_members`, keyed on
the service's own id) does not cover every voter (alternates who sat for a
day are missing), so a position is stored under the name as printed,
'URRESTA GUZMÁN JHAJAIRA ESTEFANÍA' (surnames first, as the register orders
them). `name_key` is the accent-folded, sorted token set, which is what
joins a vote, the register and the roster: the register swaps the two name
fields relative to the vote file, and the roster page writes given names
first in mixed case.

PARTY IS NOT IN THE VOTE. `ec_roster` is the sitting 151 from the plenary
page, with the party read off each member's avatar ('adn',
'revolucion-ciudadana', 'pachakutik', 'psc', or a bare list number such as
'26' that the page does not label). It is the party NOW, not at the vote.

ONLY THOSE WHO VOTED ARE LISTED. A vote's detail lists SI, NO, ABSTENCION
(and BLANCO when used) and its row count equals the four totals; members
absent or not voting are not listed at all.

AREAS ARE NULL UNTIL A SPANISH TAXONOMY EXISTS. NULL means unclassified,
'[]' classified and on nobody's ground. The English taxonomy matched none
of 1,927 votes (docs/ecuador-scope.md).
"""

from __future__ import annotations

import json
import os
import unicodedata

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS ec_members (
        member_id    INTEGER PRIMARY KEY, -- the datos service's own id
        name         TEXT NOT NULL,       -- surnames then given names, as printed
        name_key     TEXT NOT NULL,       -- folded sorted tokens (see docstring)
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ec_roster (
        name         TEXT PRIMARY KEY,    -- 'Adrián Ernesto Castro Piedra', as the page prints it
        name_key     TEXT NOT NULL,
        constituency TEXT,                -- 'Azuay', 'Nacional', 'Exterior: ...'
        party_slug   TEXT,                -- from the avatar: 'adn', 'revolucion-ciudadana', '26'
        party        TEXT,                -- label when the slug is known, else NULL
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ec_divisions (
        division_key TEXT PRIMARY KEY,    -- 'ec-1004966'
        voting_id    INTEGER NOT NULL,
        period_id    INTEGER,             -- the service's period: 8 = 2025-2029
        session      INTEGER,             -- plenary session number
        voted_at     TEXT,                -- UTC timestamp as served
        date         TEXT,                -- ISO date in Ecuador (UTC-5)
        theme        TEXT,                -- the agenda item (sometimes stale)
        proposal     TEXT,                -- what was put to the vote
        yes          INTEGER,
        no           INTEGER,
        blank        INTEGER,
        abstain      INTEGER,
        positions    INTEGER,             -- positions stored; NULL until the detail is read
        own_areas    TEXT,                -- JSON: matched on the vote's own text
        areas        TEXT,                -- JSON: own + watchlist; NULL = unclassified
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ec_votes (
        division_key TEXT NOT NULL,
        name         TEXT NOT NULL,       -- surnames then given names, as printed
        name_key     TEXT NOT NULL,
        position     TEXT NOT NULL,       -- 'SI' / 'NO' / 'ABSTENCION' / 'BLANCO'
        seat         TEXT,                -- the service's `territorial` field, as printed
        PRIMARY KEY (division_key, name)
    )""",
    "CREATE INDEX IF NOT EXISTS ec_divisions_date ON ec_divisions (date)",
    "CREATE INDEX IF NOT EXISTS ec_votes_member ON ec_votes (name_key)",
)

# X8 (10 October 2026): the constitutional court's rulings on our ground, one
# shape for every country (src/courts.py); written only by tools/ec_courts.py.
from src import courts as _courts  # noqa: E402

SCHEMA = SCHEMA + _courts.schema("ec")

TABLES = ("ec_members", "ec_roster", "ec_divisions", "ec_votes", "ec_rulings")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


def name_key(*parts):
    """'URRESTA GUZMÁN', 'Jhajaira Estefanía' -> 'ESTEFANIA GUZMAN JHAJAIRA URRESTA'.

    Accents folded, upper case, tokens sorted: the register, the vote file
    and the roster page order and case the same name differently.
    """
    text = " ".join(p for p in parts if p)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(sorted(text.upper().split()))


# --- the Ecuador watchlist, applied by division KEY -------------------------
#
# A key is exact, a title is not. Bills join the file when a bill source
# with stable numbers is available (docs/ecuador-scope.md, phase 2).

_WATCH = {}
WATCHLIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "config", "watchlist-ec.yaml")


def watchlist(path=None):
    """{division_key: (areas, why)} from config/watchlist-ec.yaml."""
    import yaml
    path = path or WATCHLIST
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {str(k): (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("divisions") or {}).items()}
    return _WATCH[path]


def watch_areas(division_key, path=None):
    """The watched areas of one division, or []."""
    hit = watchlist(path).get(division_key or "")
    return list(hit[0]) if hit else []


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
