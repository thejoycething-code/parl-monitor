"""Tables for the Brazil National Congress monitor (phase 1, 9 October 2026):
members of both chambers, the proposições their recorded votes are about,
every nominal vote of the Câmara dos Deputados and the Senado Federal, each
member's position, and the Câmara party leaders' orientations.

See docs/brazil-scope.md for what was measured and why. The schema follows
the US precedent (src/us_store.py): its own module, idempotent statements,
created by db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/br_*.py writes these tables,
and nothing here touches another jurisdiction's table.

KEYS.
  * A proposição is its type, number and year as Congress prints them:
    'PL 1904/2024', 'PEC 164/2012'. Since 2019 both chambers share one
    numbering, so a bill keeps its key when it crosses from one house to the
    other. Before 2019 they numbered separately, so a Senate proposição from
    before 2019 is prefixed 'SF ' ('SF PEC 5/2017') rather than risk taking
    a Câmara bill's key. A Câmara record with no number or year (a rapporteur's
    opinion, 'PRL 1/0') is keyed on its Câmara ID: 'camara:2645880'.
    Never a title: titles repeat, and an ementa is rewritten as a bill moves.
  * A member is their chamber and that chamber's own ID: 'camara-160561',
    'senado-5672'. The two houses do not share an ID space, so a deputy who
    becomes a senator is two members here, joined later if ever needed.
  * A vote is 'camara-<idVotacao>' ('camara-2611313-31') or
    'senado-<codigoSessaoVotacao>' ('senado-7101').

PARTY IS STORED PER VOTE: `br_votes.party` is the party printed on that
vote. Brazilian deputies change party often (the party-switch window of
every election year), so `br_members.party` is only the latest seen.

ONLY NOMINAL VOTES ARE STORED. Most decisions in both houses are symbolic
votes, with no individual positions (the Câmara recorded 13,827 votações in
2025 and 550 of them were nominal). A symbolic vote says nothing about any
member, so it is not a division here.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS br_members (
        member_key   TEXT PRIMARY KEY,   -- 'camara-160561' / 'senado-5672'
        chamber      TEXT NOT NULL,      -- 'camara' / 'senado'
        source_id    TEXT NOT NULL,      -- the chamber's own ID
        name         TEXT,               -- parliamentary name, as printed
        party        TEXT,               -- latest seen; see br_votes.party
        uf           TEXT,               -- two-letter state
        in_office    INTEGER,            -- 1 when the chamber's current list carries them
        as_of        TEXT,               -- date of the fact stored
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS br_bills (
        bill_key     TEXT PRIMARY KEY,   -- 'PL 1904/2024'
        sigla        TEXT,               -- PL, PEC, PLP, PDL, MPV, REQ ...
        numero       INTEGER,
        ano          INTEGER,
        camara_id    INTEGER,            -- dadosabertos.camara.leg.br proposição ID
        senado_codigo INTEGER,           -- the Senate's codigoMateria
        ementa       TEXT,
        ementa_detalhada TEXT,           -- Câmara only
        keywords     TEXT,               -- Câmara indexing terms; carries words the ementa omits
        presented    TEXT,               -- ISO date
        status       TEXT,               -- latest situação, as printed
        url          TEXT,               -- full text (inteiro teor)
        detail_fetched INTEGER,          -- 1 once the Câmara detail record was read
        areas        TEXT,               -- JSON list; watchlist-br by key (+ taxonomy-pt once approved)
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        former_keys  TEXT,               -- JSON list: numbers this bill was stored under before a renumbering
        renamed_on   TEXT,               -- ISO date of the latest renumbering seen
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS br_divisions (
        division_key TEXT PRIMARY KEY,   -- 'camara-2611313-31' / 'senado-7101'
        chamber      TEXT NOT NULL,
        source_id    TEXT NOT NULL,
        date         TEXT,               -- ISO date
        organ        TEXT,               -- 'PLEN' or a committee ('CCJC')
        description  TEXT,               -- the chamber's own words
        result       TEXT,               -- Câmara: 'approved' / 'rejected'; Senado: its code
        yes          INTEGER,
        no           INTEGER,
        other        INTEGER,
        secret       INTEGER,            -- Senado secret ballot: positions say only who voted
        bill_key     TEXT,               -- the substantive proposição voted on, or NULL
        linked_bills TEXT,               -- JSON: every proposição the chamber links to the vote
        own_areas    TEXT,               -- JSON: matched on the vote's OWN text
        areas        TEXT,               -- JSON: own + every linked bill's
        matched_terms TEXT,
        tier         INTEGER,
        positions_fetched INTEGER,       -- 1 once every position is stored
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS br_votes (
        division_key TEXT NOT NULL,
        member_key   TEXT NOT NULL,
        position     TEXT,               -- as printed: 'Sim', 'Não', 'Abstenção', 'Obstrução', 'Artigo 17', 'Votou' ...
        party        TEXT,               -- AT THE VOTE
        uf           TEXT,
        PRIMARY KEY (division_key, member_key)
    )""",
    """CREATE TABLE IF NOT EXISTS br_orientations (
        division_key TEXT NOT NULL,
        bloc         TEXT NOT NULL,      -- party, bloc, 'Governo', 'Oposição', 'Maioria' ...
        orientation  TEXT,               -- 'Sim', 'Não', 'Liberado', 'Obstrução' ...
        PRIMARY KEY (division_key, bloc)
    )""",
    "CREATE INDEX IF NOT EXISTS br_divisions_bill ON br_divisions (bill_key)",
    "CREATE INDEX IF NOT EXISTS br_votes_member ON br_votes (member_key)",
)

TABLES = ("br_members", "br_bills", "br_divisions", "br_votes", "br_orientations")

MEMBER_UPSERT = (
    "INSERT INTO br_members (member_key, chamber, source_id, name, party, uf, in_office, "
    "as_of, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?) "
    "ON CONFLICT(member_key) DO UPDATE SET "
    "name=COALESCE(br_members.name, excluded.name), "
    "party=CASE WHEN {newer} THEN COALESCE(excluded.party, br_members.party) ELSE br_members.party END, "
    "uf=CASE WHEN {newer} THEN COALESCE(excluded.uf, br_members.uf) ELSE br_members.uf END, "
    "in_office=COALESCE(excluded.in_office, br_members.in_office), "
    "as_of=CASE WHEN {newer} THEN excluded.as_of ELSE br_members.as_of END, "
    "last_seen=excluded.last_seen").format(
        newer="COALESCE(excluded.as_of, '') >= COALESCE(br_members.as_of, '')")


# Columns added after a store was first built (10 October 2026, the edition
# shows both numbers of a renumbered bill): added in place, idempotently.
ADDED_COLUMNS = (
    ("br_bills", "former_keys", "TEXT"),
    ("br_bills", "renamed_on", "TEXT"),
)


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    for table, col, kind in ADDED_COLUMNS:
        have = {r[1] for r in conn.execute("PRAGMA table_info({0})".format(table))}
        if col not in have:
            conn.execute("ALTER TABLE {0} ADD COLUMN {1} {2}".format(table, col, kind))
    conn.commit()
    return conn


def former_keys(raw):
    """The JSON former_keys column as a list ([] for NULL or junk)."""
    try:
        got = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except (TypeError, ValueError):
        return []
    return [str(k) for k in got if k]


# --- the Brazil watchlist, applied by proposição KEY ------------------------
#
# Like the US one and for the same reason: a key is exact, a title is not.
# Many of the bills that matter most have ementas that never name the issue
# (PL 1904/2024 amends "arts. 124 to 128 of the Penal Code", which are the
# abortion articles; PL 2630/2020 is "Liberdade, Responsabilidade e
# Transparência na Internet").

_WATCH = {}


def watchlist(path=None):
    """{bill_key: (areas, why)} from config/watchlist-br.yaml."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-br.yaml")
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
