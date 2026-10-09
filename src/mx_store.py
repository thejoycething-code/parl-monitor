"""Tables for the Mexico monitor (phase 1, 9 October 2026): the Chamber of
Deputies' members, iniciativas with their progress, recorded votes and
every deputy's position.

See docs/mexico-scope.md for what was measured and why. The schema follows
the US precedent (src/us_store.py): its own module, idempotent statements,
created by db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/mx_*.py writes these tables,
and nothing here touches another jurisdiction's table.

KEYS, NEVER TITLES.
  * A deputy is '<legislature>/<dipt>', '66/391': the Chamber's own
    information system (SITL, sitl.diputados.gob.mx) numbers deputies per
    legislature, and the same person in the next legislature is a new key.
  * An iniciativa is '<legislature>/<number>', '66/7223': the sequence
    number the Gaceta Parlamentaria prints at the end of every entry. The
    newest entries carry a PROVISIONAL number instead ('(783X)'), which is
    replaced within weeks; they are stored under '66/p/<gaceta anchor>' with
    provisional=1 and re-keyed in place when the real number appears (the
    Gaceta anchor is the link between the two). The watchlist only ever
    uses real numbers.
  * A division is 'dip-<legislature>-<votaciont>', 'dip-66-2': SITL's own
    vote id, unique across the legislature.

PARTY IS STORED PER VOTE: `mx_votes.party` is the parliamentary group SITL
filed that deputy under on that vote. `mx_members.party` is only the latest.

A LEGISLATURE ENDS ON 31 AUGUST OF ITS THIRD YEAR (the LXVI on 31 August
2027). Pending iniciativas do not all die then (Reglamento article 287
carries some over), so `mx_iniciativas.status` is what the board reads.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS mx_members (
        member_key   TEXT PRIMARY KEY,   -- '66/391': legislature/SITL dipt
        legislature  INTEGER NOT NULL,
        dipt         INTEGER NOT NULL,
        name         TEXT,               -- as SITL prints it: surnames first
        party        TEXT,               -- latest seen; see mx_votes.party
        entidad      TEXT,               -- the state
        distrito     TEXT,               -- 'Dtto. 6' or 'Circ. 3' (list seat)
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS mx_iniciativas (
        ini_key      TEXT PRIMARY KEY,   -- '66/7223', or '66/p/<anchor>' (provisional)
        legislature  INTEGER NOT NULL,
        number       INTEGER,            -- NULL while provisional
        provisional  INTEGER NOT NULL DEFAULT 0,
        kind         TEXT,               -- 'iniciativa' / 'minuta' (sent by the Senate)
        title        TEXT,
        presenter    TEXT,               -- the 'Presentada por' line, verbatim
        origin       TEXT,               -- diputados / senado / ejecutivo / congreso_local / ciudadanos / otro
        party        TEXT,               -- as printed after the presenter, if any
        turno        TEXT,               -- committee(s) it was sent to
        status       TEXT,               -- latest step: turnada, dictaminada, aprobada, ...
        status_lines TEXT,               -- JSON list: every progress line, verbatim
        presented    TEXT,               -- ISO date of the Gaceta issue
        period       TEXT,               -- the Gaceta list it came from: 'a3primero'
        gaceta_ref   TEXT,               -- '/Gaceta/66/2026/sep/20260901-II.html#Iniciativa3'
        vote_tables  TEXT,               -- JSON list of Gaceta vote tables it links to
        areas        TEXT,               -- JSON list; taxonomy-es (once approved) + watchlist-mx
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS mx_divisions (
        division_key TEXT PRIMARY KEY,   -- 'dip-66-2'
        chamber      TEXT NOT NULL,      -- 'diputados' (the Senate is blocked; see the scope doc)
        legislature  INTEGER NOT NULL,
        votaciont    INTEGER NOT NULL,   -- SITL's vote id
        pert         INTEGER,            -- SITL's period id
        period       TEXT,               -- 'Primer Período de Sesiones Ordinarias del Tercer Año'
        date         TEXT,               -- ISO date
        title        TEXT,               -- what was voted, as SITL prints it (upper case)
        favor        INTEGER,
        contra       INTEGER,
        abstencion   INTEGER,
        solo_asistencia INTEGER,         -- present, did not vote ('Quórum' in the Gaceta)
        ausente      INTEGER,
        total        INTEGER,
        groups       TEXT,               -- JSON {group: [favor, contra, abst, asist, ausente, total]}
        gaceta_tabla TEXT,               -- '/Gaceta/Votaciones/66/tabla1or1-1.php3', when matched
        ini_keys     TEXT,               -- JSON: iniciativas whose Gaceta entry links that table
        positions    INTEGER,            -- positions stored; NULL until the lists are read
        own_areas    TEXT,               -- JSON: matched on the vote's OWN title
        areas        TEXT,               -- JSON: own + its iniciativas' + watchlist-mx
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS mx_votes (
        division_key TEXT NOT NULL,
        member_key   TEXT NOT NULL,
        position     TEXT,               -- 'A favor' / 'En contra' / 'Abstención' / 'Solo asistencia' / 'Ausente'
        party        TEXT,               -- AT THE VOTE: 'MORENA', 'PAN', ...
        PRIMARY KEY (division_key, member_key)
    )""",
    "CREATE INDEX IF NOT EXISTS mx_votes_member ON mx_votes (member_key)",
    "CREATE INDEX IF NOT EXISTS mx_iniciativas_ref ON mx_iniciativas (gaceta_ref)",
)

TABLES = ("mx_members", "mx_iniciativas", "mx_divisions", "mx_votes")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- the Mexico watchlist, applied by iniciativa KEY -------------------------
#
# Keyed by the Gaceta's iniciativa number, never by title: Mexican titles
# are formulaic ("Que reforma el artículo 4o. de la Constitución...") and
# hundreds share their opening words. A vote carries no iniciativa number,
# so an entry may also name the SITL votes (votaciont) that decided it.

_WATCH = {}


def watchlist(path=None):
    """{ini_key: {"areas": [...], "why": str, "votaciones": [int, ...]}}."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-mx.yaml")
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {str(k): {"areas": list(v.get("areas") or []), "why": v.get("why"),
                                 "votaciones": [int(x) for x in (v.get("votaciones") or [])]}
                        for k, v in (raw.get("iniciativas") or {}).items()}
    return _WATCH[path]


def watched_votes(path=None):
    """{votaciont: (ini_key, areas)} from the watchlist's `votaciones` lists."""
    out = {}
    for key, spec in watchlist(path).items():
        for v in spec["votaciones"]:
            out[v] = (key, spec["areas"])
    return out


def add_watch_areas(res, ini_key, path=None):
    """Union a watched iniciativa's areas into a FilterResult, in place, and
    say so in watchlist_hits so the stored row shows where the area came from."""
    hit = watchlist(path).get(ini_key)
    if not hit:
        return res
    res.issue_areas = sorted(set(res.issue_areas or []) | set(hit["areas"]))
    res.watchlist_hits = list(res.watchlist_hits or []) + ["watch:" + ini_key]
    if res.tier is None:
        res.tier = 2
    return res


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
