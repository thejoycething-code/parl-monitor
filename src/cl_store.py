"""Tables for the Chile National Congress monitor (phase 1, 9 October 2026):
deputies and senators, bills (proyectos de ley) keyed by boletín, recorded
votes in both chambers and every member's position.

See docs/chile-scope.md for what was measured and why. The schema follows
the US precedent (src/us_store.py): its own module, idempotent statements,
created by db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/cl_*.py writes these tables,
and nothing here touches another jurisdiction's table.

KEYS.
  * A bill is its BOLETÍN, '15805-07': the number the Congress gives a bill
    on entry, shared by both chambers and the BCN, with the committee suffix.
    Never the title: Chile files dozens of near-identical "Modifica la ley N°
    20.370 ..." bills a year.
  * A member is '<chamber>-<source id>': 'D-803' is the Cámara's own deputy
    Id, 'S-1110' the Senate's PARLID. A Senate vote names its senators only
    as "Gatica B., María José"; a name the senator list cannot resolve is kept
    as 'S-?<folded name>' rather than guessed (and counted in the summary).
  * A Cámara division is 'camara-<Votacion Id>'. The Senate publishes no vote
    ID at all, so a Senate division is 'senado-<boletín number>-<12 hex>', a
    hash of the session, date, stage, kind and the vote's own text.

PARTY IS STORED PER VOTE. The Cámara gives each deputy's militancias with
dates, so `cl_votes.party` is the party on the day of the vote. The Senate
gives only the current party, so a Senate vote carries the party at the time
of collection; that is weaker and the scope doc says so.

RESULTS ARE STORED IN THE SOURCE'S OWN WORDS. The Cámara labels some split
votes "Unánime" (59-67 on 12 May 2025, vote 82260): never derive a verdict
from that field without the counts beside it.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS cl_members (
        member_key   TEXT PRIMARY KEY,   -- 'D-803' (Cámara Id), 'S-1110' (Senate PARLID)
        chamber      TEXT NOT NULL,      -- 'camara' / 'senado'
        source_id    TEXT,               -- the chamber's own ID; NULL if unresolved
        name         TEXT,               -- 'René Alinco Bustos'
        party        TEXT,               -- latest seen; see cl_votes.party
        sex          TEXT,
        region       TEXT,
        district     TEXT,               -- distrito (Cámara) or circunscripción (Senado)
        as_of        TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS cl_party_spells (
        member_key   TEXT NOT NULL,
        party        TEXT NOT NULL,      -- the Cámara's alias: 'PC', 'IND', 'REP'
        party_name   TEXT,
        start        TEXT NOT NULL,      -- ISO date
        end          TEXT,               -- ISO date, NULL when open
        PRIMARY KEY (member_key, start)
    )""",
    """CREATE TABLE IF NOT EXISTS cl_bills (
        boletin      TEXT PRIMARY KEY,   -- '15805-07'
        number       INTEGER NOT NULL,   -- 15805: what the Senate's vote service takes
        title        TEXT,
        introduced   TEXT,               -- ISO date
        initiative   TEXT,               -- 'Moción' (members) / 'Mensaje' (the President)
        origin       TEXT,               -- chamber of origin, as printed
        stage        TEXT,               -- Senate 'etapa': 'Segundo trámite constitucional (Senado)'
        substage     TEXT,
        status       TEXT,               -- 'En tramitación', 'Publicado', 'Archivado' ...
        urgency      TEXT,               -- current urgency: 'Suma', 'Discusión inmediata'
        law_number   TEXT,               -- once published
        subjects     TEXT,               -- JSON list: the Senate's materias
        authors      TEXT,               -- JSON list of names as printed
        areas        TEXT,               -- JSON list; taxonomy + watchlist-cl by boletín
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS cl_divisions (
        division_key TEXT PRIMARY KEY,   -- 'camara-90328' / 'senado-15805-1a2b3c4d5e6f'
        chamber      TEXT NOT NULL,      -- 'camara' / 'senado'
        source_id    TEXT,               -- the Cámara's Votacion Id; the Senate's session '29/372'
        date         TEXT,               -- ISO date (Cámara: date and time)
        boletin      TEXT,               -- NULL for resolutions, agreements, procedure
        kind         TEXT,               -- Cámara Tipo ('Proyecto de Ley', 'Proyecto de Resolución'),
                                         -- Senate TIPOVOTACION ('Discusión general')
        description  TEXT,               -- Cámara Descripcion: 'Boletín N° 15805-07'
        text         TEXT,               -- what was voted: Cámara Articulo, Senate TEMA
        stage        TEXT,               -- trámite constitucional / etapa
        quorum       TEXT,
        result       TEXT,               -- the source's own words, never derived
        yes          INTEGER,
        no           INTEGER,
        abstain      INTEGER,
        paired       INTEGER,            -- Cámara TotalDispensado / Senate PAREO
        own_areas    TEXT,               -- JSON: matched on the vote's OWN text
        areas        TEXT,               -- JSON: own + the bill's
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS cl_votes (
        division_key TEXT NOT NULL,
        member_key   TEXT NOT NULL,
        position     TEXT,               -- the source's word: 'Afirmativo', 'En Contra', 'Si', 'Pareo'
        party        TEXT,               -- AT THE VOTE (Cámara); at collection (Senado)
        PRIMARY KEY (division_key, member_key)
    )""",
    "CREATE INDEX IF NOT EXISTS cl_divisions_bill ON cl_divisions (boletin)",
    "CREATE INDEX IF NOT EXISTS cl_votes_member ON cl_votes (member_key)",
)

TABLES = ("cl_members", "cl_party_spells", "cl_bills", "cl_divisions", "cl_votes")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- the Chile watchlist, applied by BOLETÍN ---------------------------------
#
# Keyed, never titled, as in the US: the Chilean euthanasia bill is called
# "Sobre muerte digna y cuidados paliativos", and "cuidados paliativos" alone
# would also claim every palliative-care funding bill.

_WATCH = {}


def watchlist(path=None):
    """{boletin: (areas, why)} from config/watchlist-cl.yaml."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-cl.yaml")
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {str(k): (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("bills") or {}).items()}
    return _WATCH[path]


def add_watch_areas(res, boletin, path=None):
    """Union a watched bill's areas into a FilterResult, in place."""
    hit = watchlist(path).get(boletin or "")
    if not hit:
        return res
    areas, _why = hit
    res.issue_areas = sorted(set(res.issue_areas or []) | set(areas))
    res.watchlist_hits = list(res.watchlist_hits or []) + ["watch:" + boletin]
    if res.tier is None:
        res.tier = 2
    return res


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
