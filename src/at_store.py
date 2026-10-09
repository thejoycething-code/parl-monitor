"""Tables for the Austrian Parliament monitor (phase 1, 9 October 2026):
members of the Nationalrat and Bundesrat, every Verhandlungsgegenstand of the
current Gesetzgebungsperiode, and the votes recorded on the ones on our ground.

See docs/austria-scope.md for what was measured and why. The schema follows
the US precedent (src/us_store.py): its own module, idempotent statements,
created by db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/at_*.py writes these tables, and
nothing here touches another jurisdiction's table.

KEYS. An item is its Parliament path without the prefix: '/gegenstand/
XXVIII/I/525' is 'XXVIII/I/525' (the 525th Regierungsvorlage of the 28th
Gesetzgebungsperiode). Bundesrat items carry 'BR' where the period goes:
'BR/A-BR/434'. Never a title: the same title is printed on a Regierungsvorlage,
its committee report, its Abänderungsantrag and the Nationalrat's Beschluss in
the Bundesrat, which are four items with four keys. A member is their PAD,
the Parliament's own person ID ('/person/88386' is '88386').

VOTES ARE RECORDED BY KLUB. The Nationalrat and the Bundesrat vote by
standing up, and the record names the Klubs (Fraktionen in the Bundesrat)
for and against, never the members. Only a namentliche Abstimmung names
members (5 in the Nationalrat in this period, measured); those names sit in
the Stenographisches Protokoll and are phase 1b. So `at_votes` is one row
per division and Klub, and `at_divisions.roll_call` marks the five.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS at_members (
        pad          TEXT PRIMARY KEY,   -- '88386'
        name         TEXT,               -- 'Auer Katrin, Mag.' as the list prints it
        chamber      TEXT,               -- 'NR' / 'BR', latest seen
        klub         TEXT,               -- 'SPÖ', 'NEOS', 'OF' (ohne Fraktion), latest seen
        wahlkreis    TEXT,
        bundesland   TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS at_items (
        item_key     TEXT PRIMARY KEY,   -- 'XXVIII/I/525'
        gp           TEXT NOT NULL,      -- 'XXVIII'
        chamber      TEXT NOT NULL,      -- 'NR' / 'BR'
        ityp         TEXT,               -- 'I', 'A', 'UEA', 'J', 'BNR', 'A-BR' ...
        inr          INTEGER,
        art          TEXT,               -- 'RV', 'A(E)', 'UEA', 'J', 'BNR' ...
        art_long     TEXT,               -- 'Regierungsvorlage: Bundes(verfassungs)gesetz'
        title        TEXT,               -- Betreff, the short title
        description  TEXT,               -- the long title, from the history page when read
        citation     TEXT,               -- '525 d.B.', '1026/A(E)'
        status       INTEGER,            -- 1 eingelangt .. 5 abgeschlossen
        last_date    TEXT,               -- ISO date of the latest parliamentary step
        introduced   TEXT,               -- ISO date it reached the chamber
        persons      TEXT,               -- JSON list of PADs (introducers / askers)
        klubs        TEXT,               -- JSON list of their Klubs
        topics       TEXT,               -- JSON: the Parliament's Themen
        headwords    TEXT,               -- JSON: Schlagworte (stored, NOT matched: see the doc)
        eurovoc      TEXT,               -- JSON: EuroVoc descriptors (stored, not matched)
        vote_text    TEXT,               -- third reading, Klub level: 'Dafür: F, V, S, N, Dagegen: G'
        vote_comment TEXT,               -- namentliche Abstimmung totals, when there was one
        areas        TEXT,               -- JSON list; taxonomy-de + watchlist-at by key
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        detail_date  TEXT,               -- last_date when the history page was last read
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS at_divisions (
        division_key TEXT PRIMARY KEY,   -- 'XXVIII/I/525@XXVIII/NRSITZ/88#121.2'
        item_key     TEXT NOT NULL,
        date         TEXT,               -- ISO date
        body         TEXT,               -- 'NR', 'BR', or the committee: 'Justizausschuss'
        sitting      TEXT,               -- 'XXVIII/NRSITZ/88', 'BR/BRSITZ/981', or NULL
        question     TEXT,               -- what was put: 'Gesetzesvorschlag in dritter Lesung'
        outcome      TEXT,               -- 'angenommen' / 'abgelehnt', the record's own word
        unanimous    INTEGER,            -- 1 when the record says Einstimmig
        roll_call    INTEGER,            -- 1 for a namentliche Abstimmung
        yes_count    INTEGER,            -- namentliche Abstimmung only
        no_count     INTEGER,
        text         TEXT,               -- the stage text, tags stripped
        protocol_url TEXT,               -- the vote's anchor in the Stenographisches Protokoll
        areas        TEXT,               -- JSON: the item's areas
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS at_votes (
        division_key TEXT NOT NULL,
        klub         TEXT NOT NULL,      -- 'ÖVP', 'SPÖ', 'FPÖ', 'NEOS', 'GRÜNE'
        position     TEXT NOT NULL,      -- 'Dafür' / 'Dagegen'
        PRIMARY KEY (division_key, klub)
    )""",
    "CREATE INDEX IF NOT EXISTS at_divisions_item ON at_divisions (item_key)",
)

TABLES = ("at_members", "at_items", "at_divisions", "at_votes")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- the Austrian watchlist, applied by item KEY -----------------------------
#
# As in the US: a key is exact. The watchlist is where an item the shared
# German taxonomy cannot see is put on our ground until Christopher decides
# on the proposed Austrian terms (docs/austria-scope.md): the Sterbeverfügung
# items are the case in point, since taxonomy-de has no word for them.

_WATCH = {}


def watchlist(path=None):
    """{item_key: (areas, why)} from config/watchlist-at.yaml."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-at.yaml")
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {str(k): (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("items") or {}).items()}
    return _WATCH[path]


def add_watch_areas(res, item_key, path=None):
    """Union a watched item's areas into a FilterResult, in place, and say so
    in watchlist_hits so the stored row shows where the area came from."""
    hit = watchlist(path).get(item_key)
    if not hit:
        return res
    areas, _why = hit
    res.issue_areas = sorted(set(res.issue_areas or []) | set(areas))
    res.watchlist_hits = list(res.watchlist_hits or []) + ["watch:" + item_key]
    if res.tier is None:
        res.tier = 2
    return res


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)


def derived_member_positions(conn, division_key):
    """Each member's position on one division, DERIVED from their Klub's
    (X5, Chris, 10 October 2026: party-group countries derive member records
    from the group, labelled as derived).

    The Nationalrat and Bundesrat record only the Klub's vote, so every row
    here is an inference and says so: `derived` is always True and `basis`
    names the rule. The member's Klub is the latest seen (at_members keeps no
    history), so a member who changed Klub is attributed by today's Klub;
    `basis` says that too. Nothing is written: a derivation is computed when
    asked, never stored beside the record as if it were one.
    """
    div = conn.execute("SELECT body FROM at_divisions WHERE division_key=?",
                       (division_key,)).fetchone()
    if not div or div[0] not in ("NR", "BR"):
        return []          # committees: no membership list to derive from
    out = []
    for klub, position in conn.execute(
            "SELECT klub, position FROM at_votes WHERE division_key=? ORDER BY klub",
            (division_key,)):
        for pad, name in conn.execute(
                "SELECT pad, name FROM at_members WHERE chamber=? AND klub=? ORDER BY name",
                (div[0], klub)):
            out.append({"member_id": pad, "name": name, "party": klub,
                        "position": position, "derived": True,
                        "basis": "Klub vote; member's latest Klub"})
    return out
