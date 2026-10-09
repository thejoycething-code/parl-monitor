"""Tables for the Argentine National Congress monitor (phase 1, 9 October
2026): members of both chambers, expedientes (bills and other projects),
Senate roll calls and every senator's position.

See docs/argentina-scope.md for what was measured and why. The schema follows
the US and Australian precedent (src/us_store.py): its own module, idempotent
statements, created by db.init_db so every store carries it and db.TABLES
stays true.

SEPARATION GUARANTEE. Nothing outside tools/ar_*.py writes these tables, and
nothing here touches another jurisdiction's table.

KEYS. Titles are never keys: the Diputados register alone holds dozens of
"DECLARAR DE INTERES..." items a week with near-identical titles.
  * An expediente is '<chamber>/<the chamber's own number>':
      'dip/5346-D-2026'  -- a Diputados expediente, as HCDN prints it
      'sen/1725-S-2026'  -- a Senate expediente (the Senate prints 'S-1725/26')
      'sen/159-PE-2025'  -- the executive's bill as the SENATE numbered it
    The chamber prefix is not decoration: each chamber numbers incoming items
    on its own, so the executive's message 159/25 in the Senate and message
    159/25 in Diputados are different documents. A bill that passes one
    chamber is given a NEW number in the other ('CD-33/25' in the Senate is
    '10-PE-2024' in Diputados); `exp_other` keeps the crosswalk when a source
    prints it.
  * A member is '<chamber>/<the chamber's own ID>': 'sen/546' is the Senate's
    senator ID (its URLs, photos and open-data roster all use it); 'dip/<id>'
    is the HCDN open-data diputado ID.
  * A Senate division is 'sen-acta-<id>', the Senate's own acta ID (its
    detail page and PDF both use it). The few rows published without either
    are 'sen-<date>-<acta number>'.

BLOC IS STORED PER VOTE, as party is in Canada and the US: `ar_votes.bloc` is
the bloc the Senate printed on that acta. Argentine blocs split and rename
often (the 2025-2027 Senate has fourteen); `ar_members.bloc` is only the
latest seen.

A BILL LAPSES ON A CALENDAR, NOT WITH A PARLIAMENT. Under Ley 13.640 (as
amended) a bill with no sanction lapses after its parliamentary year of entry
and the next (a year runs 1 March to 28 February; HCDN numbers them, 144 is
2026-27), with longer once one chamber has passed it. Nothing in a record
says so; `ar_bills.year` is what a board reads. To be confirmed by Chris's
Argentine contacts before any board relies on it.
"""

from __future__ import annotations

import json
import os
import unicodedata

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS ar_members (
        member_key   TEXT PRIMARY KEY,   -- 'sen/546', 'dip/<HCDN id>'
        chamber      TEXT NOT NULL,      -- 'senado' / 'diputados'
        name         TEXT,               -- 'ABAD, MAXIMILIANO' as the chamber prints it
        bloc         TEXT,               -- latest seen; see ar_votes.bloc
        province     TEXT,               -- district: the province or CABA
        alliance     TEXT,               -- 'PARTIDO O ALIANZA' (Senate roster)
        term_start   TEXT,
        term_end     TEXT,
        current      INTEGER,            -- 1 while on the chamber's current roster
        as_of        TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ar_bills (
        exp_key      TEXT PRIMARY KEY,   -- 'dip/5346-D-2026', 'sen/159-PE-2025'
        chamber      TEXT NOT NULL,      -- the chamber whose number this is
        number       INTEGER,
        origin       TEXT,               -- D, S, PE, JGM, OV, CD ... as printed
        year         INTEGER,            -- four digits
        tipo         TEXT,               -- LEY, RESOLUCION, DECLARACION, PL, PC ...
        title        TEXT,               -- the extracto / TITULO, which IS the summary
        author       TEXT,
        published    TEXT,               -- Trámite Parlamentario date (Diputados) or entry date
        publication  TEXT,               -- 'HCDN144TP150': period 144, TP no. 150
        proyecto_id  TEXT,               -- HCDN's internal 'HCDN295211'
        exp_other    TEXT,               -- the other chamber's key, when printed
        law          TEXT,               -- 'Ley 27801' once sanctioned, when printed
        areas        TEXT,               -- JSON list; terms + watchlist-ar by key
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ar_divisions (
        division_key TEXT PRIMARY KEY,   -- 'sen-acta-2623'
        chamber      TEXT NOT NULL,      -- 'senado' (Diputados: see the scope doc)
        acta_id      INTEGER,
        date         TEXT,               -- ISO date of the session
        time         TEXT,               -- 'HH:MM' from the detail page
        acta_number  INTEGER,            -- 'Nro.': restarts every session
        title        TEXT,               -- 'Modernización Laboral. Titulo I.'
        vote_type    TEXT,               -- 'EN GENERAL', 'EN PARTICULAR', ...
        result       TEXT,               -- the Senate's own word: AFIRMATIVO, NEGATIVO, EMPATE ...
        majority     TEXT,               -- 'SIMPLE', 'DOS TERCIOS', ...
        exp_keys     TEXT,               -- JSON list of 'sen/...' keys the acta names
        orders       TEXT,               -- JSON list of 'OD-699/2025' (Orden del Día)
        ayes         INTEGER,
        noes         INTEGER,
        abstentions  INTEGER,
        absent       INTEGER,
        has_detail   INTEGER,            -- 0 when only the PDF was published
        own_areas    TEXT,               -- JSON: matched on the acta's OWN title
        areas        TEXT,               -- JSON: own + its expedientes'
        matched_terms TEXT,
        tier         INTEGER,
        source_url   TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ar_votes (
        division_key TEXT NOT NULL,
        member_key   TEXT NOT NULL,
        position     TEXT,               -- AFIRMATIVO / NEGATIVO / ABSTENCION / AUSENTE / ...
        bloc         TEXT,               -- AT THE VOTE
        province     TEXT,
        PRIMARY KEY (division_key, member_key)
    )""",
    "CREATE INDEX IF NOT EXISTS ar_votes_member ON ar_votes (member_key)",
)

TABLES = ("ar_members", "ar_bills", "ar_divisions", "ar_votes")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


def fold(text):
    """Accent-blind, n-tilde-blind text for matching. HCDN prints older
    titles in capitals with no accents ('IDENTIDAD DE GENERO') and newer
    ones in sentence case with them ('identidad de género'); the Senate
    always accents. The filter does not fold accents, so the AR collector
    folds the TEXT and the Spanish terms are written unaccented (see the
    scope doc's proposed list)."""
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c))


# --- the Argentine watchlist, applied by expediente KEY ----------------------

_WATCH = {}


def watchlist(path=None):
    """{exp_key: (areas, why)} from config/watchlist-ar.yaml."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-ar.yaml")
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {k: (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("expedientes") or {}).items()}
    return _WATCH[path]


def add_watch_areas(res, exp_key, path=None):
    """Union a watched expediente's areas into a FilterResult, in place, and
    say so in watchlist_hits so the stored row shows where the area came from."""
    hit = watchlist(path).get(exp_key)
    if not hit:
        return res
    areas, _why = hit
    res.issue_areas = sorted(set(res.issue_areas or []) | set(areas))
    res.watchlist_hits = list(res.watchlist_hits or []) + ["watch:" + exp_key]
    if res.tier is None:
        res.tier = 2
    return res


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
