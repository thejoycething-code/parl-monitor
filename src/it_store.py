"""Tables for the Italian Parliament monitor (phase 1, 9 October 2026):
bills of both chambers, the recorded votes of the Senato and the Camera dei
Deputati, and every member's position on the votes on our ground.

See docs/italy-scope.md for what was measured and why. The schema follows the
US precedent (src/us_store.py): its own module, idempotent statements, created
by db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/it_*.py writes these tables, and
nothing here touches another jurisdiction's table.

KEYS.
  * A bill is one READING of a bill in one chamber, as Parliament numbers it:
    '19/S.1056' or '19/C.2628' (legislature / chamber.number, with the letter
    suffix of a later reading kept: '19/C.2822-B'). It is the number on the
    vote titles and on both chambers' sites. `id_ddl` is the Senate's own ID
    for the bill across all its readings, which is how C.887 and the S.824
    it became are known to be one bill. Titles are never keys: dozens of
    bills are called "Modifica all'articolo 12 della legge 19 febbraio 2004,
    n. 40".
  * A division is the chamber's own vote ID: 'senato-19-167-42' (legislature,
    sitting, vote, as dati.senato.it numbers it) or 'camera-vs19_723_001'
    (the dati.camera.it identifier, which Openpolis carries unchanged).
  * A member is 'S:<dati.senato.it senator ID>' or 'C:<Openpolis membership
    ID>' ('S:32600', 'C:207'). The two chambers have separate identity
    schemes; a member who moves chamber has two keys. The Openpolis slug is
    not used: it carries the birth date and reads '...-none' until Openpolis
    has one, so it can change under a stored vote.

GROUP IS STORED PER VOTE, as party is in Canada and the US: Italian members
change parliamentary group often. `it_votes.grp` is the group at the vote;
`it_members.grp` is only the latest.

POSITIONS ARE STORED FOR EVERY VOTE since X15 (Chris, 10 October 2026), our
ground first. Before that, ONLY FOR VOTES ON OUR GROUND. The 19th legislature has
about 1.6 million Senate positions and 9.6 million Camera positions (Openpolis
count); storing them all would treble the store for votes nobody reads. A
division on our ground with `positions_fetched = 0` is fetched on the next
run, so a taxonomy change that brings an old vote onto our ground heals
itself.

A BILL LAPSES WITH ITS LEGISLATURE. The 19th ends by October 2027 at the
latest; every pending bill dies and comes back, if at all, under a new
number. `it_bills.legislature` is what a board reads, never `status`.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS it_members (
        member_key   TEXT PRIMARY KEY,   -- 'S:32600' / 'C:207'
        chamber      TEXT NOT NULL,      -- 'senato' / 'camera'
        name         TEXT,
        grp          TEXT,               -- latest group seen; see it_votes.grp
        groups       TEXT,               -- JSON [{from, to, grp}], Senate only (dati.senato.it)
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS it_bills (
        bill_key     TEXT PRIMARY KEY,   -- '19/S.1056', '19/C.2628', '19/C.2822-B'
        legislature  INTEGER NOT NULL,
        chamber      TEXT NOT NULL,      -- 'S' / 'C'
        number       TEXT NOT NULL,      -- '1056', '2822-B'
        id_ddl       TEXT,               -- the Senate's ID for the bill across readings
        title        TEXT,
        short_title  TEXT,               -- the Senate's titoloBreve
        nature       TEXT,               -- 'ordinaria', 'di conversione di decreto-legge', ...
        initiative   TEXT,               -- the Senate's descrIniziativa (who presented it)
        presented    TEXT,
        status       TEXT,               -- the Senate's own words: 'approvato', 'assorbito', ...
        status_date  TEXT,
        law          TEXT,               -- 'Legge 30/2024' once enacted
        subjects     TEXT,               -- JSON: TESEO subject terms at the 'Generale' level
        areas        TEXT,               -- JSON list; taxonomy + watchlist-it by key
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS it_divisions (
        division_key TEXT PRIMARY KEY,   -- 'senato-19-167-42' / 'camera-vs19_723_001'
        chamber      TEXT NOT NULL,      -- 'senato' / 'camera'
        legislature  INTEGER NOT NULL,
        sitting      INTEGER,
        number       INTEGER,            -- the vote's number within its sitting
        date         TEXT,
        title        TEXT,               -- the chamber's label: 'Em. 1.1', 'Votazione finale'
        bill_key     TEXT,               -- '19/C.887', or NULL (motions, procedure)
        bill_keys    TEXT,               -- JSON: every reading the vote names (joint texts)
        bill_inferred INTEGER DEFAULT 0, -- 1: Camera vote whose title names no bill; see it_rollcalls
        is_final     INTEGER,
        outcome      TEXT,               -- the source's own words, never derived
        ayes         INTEGER,
        noes         INTEGER,
        abstentions  INTEGER,
        own_areas    TEXT,               -- JSON: matched on the vote's OWN text
        areas        TEXT,               -- JSON: own + the bill's
        matched_terms TEXT,
        tier         INTEGER,
        positions_fetched INTEGER DEFAULT 0,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS it_votes (
        division_key TEXT NOT NULL,
        member_key   TEXT NOT NULL,
        position     TEXT,               -- aye / no / abstain / present / mission / absent / secret
        grp          TEXT,               -- AT THE VOTE
        PRIMARY KEY (division_key, member_key)
    )""",
    "CREATE INDEX IF NOT EXISTS it_divisions_bill ON it_divisions (bill_key)",
    "CREATE INDEX IF NOT EXISTS it_votes_member ON it_votes (member_key)",
)

TABLES = ("it_members", "it_bills", "it_divisions", "it_votes")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- the Italian watchlist, applied by bill KEY ----------------------------
#
# As in the US (src/us_store.py), never by title: Italian bill titles name
# the statute they amend, so "legge 19 febbraio 2004, n. 40" is the title of
# a dozen bills, some of them on surrogacy and some on IVF access.

_WATCH = {}


def watchlist(path=None):
    """{bill_key: (areas, why)} from config/watchlist-it.yaml."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-it.yaml")
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {k: (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("bills") or {}).items()}
    return _WATCH[path]


def add_watch_areas(res, bill_key, path=None):
    """Union a watched bill's areas into a FilterResult, in place, and say so
    in watchlist_hits so the stored row shows where the area came from."""
    hit = watchlist(path).get(bill_key)
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
