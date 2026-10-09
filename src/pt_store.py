"""Tables for the Portugal monitor (phase 1, 9 October 2026): deputies, the
initiatives (iniciativas) of the Assembleia da República, the votes taken on
them, how each parliamentary group voted, and the deputies named as voting
against their group.

See docs/portugal-scope.md for what was measured and why. The schema follows
the US precedent (src/us_store.py): its own module, idempotent statements,
created by db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/pt_*.py writes these tables, and
nothing here touches another jurisdiction's table.

KEYS. An initiative is '<legislature>/<type>/<number>', 'XVII/J/479' for
Projeto de Lei 479/XVII: the type letter is the Assembleia's own IniTipo
(J projeto de lei, P proposta de lei, R projeto de resolucao, ...). Numbers
restart every legislature. The Assembleia's internal IniId is stored too,
but a human can read the key and the watchlist is written in it. Never a
title: the Assembleia files dozens of near-identical titles a session
("Recomenda ao Governo...").

A vote is 'XVII/<id>', the Assembleia's own vote id, unique across the
legislature (2,162 ids, no repeats, measured 9 October 2026).

PORTUGAL VOTES BY GROUP. The plenary votes by sitting and standing, so the
record is each parliamentary group's position, not each deputy's. A deputy
appears by name only when they broke from their group, and the group then
appears twice: 'Abstencao: PS' and 'A Favor: 13-PS' plus thirteen names.
So:
  * pt_group_votes holds what the record says about each group. `members`
    is NULL for the whole group, or the count printed ('13-PS' -> 13) for
    a breakaway block.
  * pt_votes holds ONLY deputies named in the record. A deputy who is not
    named voted with their group, or was absent; the record does not say
    which, so nothing here pretends to know. A 5CA derives a member's
    position from the group row, and must say it is derived.
  * On a free vote there is no whole-group row, only counted blocks on
    each side ('8-PSD' for, '60-PSD' against), and only the smaller block
    is named. Which sixty is an inference, never stored as a fact.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS pt_members (
        cad_id       INTEGER PRIMARY KEY, -- DepCadId: the Assembleia's person id
        name         TEXT,                -- DepNomeParlamentar, as votes print it
        full_name    TEXT,
        party        TEXT,                -- latest group sigla; see pt_votes.party
        circle       TEXT,                -- circulo eleitoral
        situation    TEXT,                -- latest: Efetivo, Suplente, Renunciou...
        legislature  TEXT,                -- the latest legislature seen
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS pt_initiatives (
        ini_key      TEXT PRIMARY KEY,    -- 'XVII/J/479'
        ini_id       INTEGER,             -- IniId, the Assembleia's own
        legislature  TEXT NOT NULL,       -- 'XVII'
        ini_type     TEXT NOT NULL,       -- IniTipo letter
        type_desc    TEXT,                -- 'Projeto de Lei'
        number       INTEGER NOT NULL,
        title        TEXT,
        epigraph     TEXT,
        authors_gp   TEXT,                -- JSON list of group siglas
        author_other TEXT,                -- 'Governo', a committee, citizens
        entered      TEXT,                -- date of the first event
        latest_phase TEXT,
        latest_phase_at TEXT,
        law_published TEXT,               -- date of 'Lei (Publicacao DR)', once it appears
        vetoes       INTEGER,             -- presidential vetoes received (Veto (Rececao))
        text_url     TEXT,
        areas        TEXT,                -- JSON list; taxonomy + watchlist-pt by key
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS pt_authors (
        ini_key      TEXT NOT NULL,
        cad_id       INTEGER NOT NULL,
        party        TEXT,                -- the group printed with the author
        PRIMARY KEY (ini_key, cad_id)
    )""",
    """CREATE TABLE IF NOT EXISTS pt_divisions (
        division_key TEXT PRIMARY KEY,    -- 'XVII/139999'
        vote_id      INTEGER NOT NULL,
        legislature  TEXT NOT NULL,
        ini_key      TEXT,                -- the initiative it was recorded under
        date         TEXT,
        phase        TEXT,                -- 'Votacao na generalidade', 'Votacao final global'
        description  TEXT,                -- set for amendments and requerimentos
        result       TEXT,                -- the record's own word: Aprovado, Rejeitado...
        unanimous    INTEGER,
        meeting      TEXT,                -- reuniao number
        meeting_type TEXT,                -- RP plenary, CP committee
        detail       TEXT,                -- the raw detalhe, tags kept: it is the record
        absent_groups TEXT,               -- JSON list from 'ausencias'
        own_areas    TEXT,                -- JSON: matched on the vote's own description
        areas        TEXT,                -- JSON: own + the initiative's
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS pt_group_votes (
        division_key TEXT NOT NULL,
        party        TEXT NOT NULL,
        position     TEXT NOT NULL,       -- 'A Favor' / 'Contra' / 'Abstencao' / 'Ausente'
        members      INTEGER,             -- NULL: the group; N: a breakaway block of N
        PRIMARY KEY (division_key, party, position)
    )""",
    """CREATE TABLE IF NOT EXISTS pt_votes (
        division_key TEXT NOT NULL,
        name         TEXT NOT NULL,       -- as printed: 'Pedro Vaz'
        party        TEXT NOT NULL,       -- AT THE VOTE, as printed: '(PS)'
        position     TEXT,
        cad_id       INTEGER,             -- resolved by name + party, or NULL
        PRIMARY KEY (division_key, name, party)
    )""",
    "CREATE INDEX IF NOT EXISTS pt_divisions_ini ON pt_divisions (ini_key)",
    "CREATE INDEX IF NOT EXISTS pt_votes_member ON pt_votes (cad_id)",
)

TABLES = ("pt_members", "pt_initiatives", "pt_authors", "pt_divisions",
          "pt_group_votes", "pt_votes")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- the Portugal watchlist, applied by initiative KEY -----------------------
#
# Keyed, never titled, for the reason in the module docstring. It also
# carries what the term list cannot see before Chris approves a Portuguese
# taxonomy: until then the shared English list is all there is, and it is
# blind to Portuguese (docs/portugal-scope.md).

_WATCH = {}


def watchlist(path=None):
    """{ini_key: (areas, why)} from config/watchlist-pt.yaml."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-pt.yaml")
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {k: (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("initiatives") or {}).items()}
    return _WATCH[path]


def add_watch_areas(res, ini_key, path=None):
    """Union a watched initiative's areas into a FilterResult, in place, and
    say so in watchlist_hits so the stored row shows where the area came from."""
    hit = watchlist(path).get(ini_key)
    if not hit:
        return res
    areas, _why = hit
    res.issue_areas = sorted(set(res.issue_areas or []) | set(areas))
    res.watchlist_hits = list(res.watchlist_hits or []) + ["watch:" + ini_key]
    if res.tier is None:
        res.tier = 2
    return res


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)


def derived_member_positions(conn, division_key):
    """Each deputy's position on one division (X5, Chris, 10 October 2026:
    derive member records from the group, labelled as derived).

    A deputy NAMED in the record (pt_votes) is a fact: `derived` False. Every
    other deputy of a group with a whole-group row (members NULL) is given
    that group's position with `derived` True. Counted blocks on a free vote
    ('60-PSD') are never spread over unnamed deputies: which sixty is not in
    the record. The group is the deputy's latest (pt_members.party). Nothing
    is written.
    """
    out, named = [], set()
    for name, party, position, cad_id in conn.execute(
            "SELECT name, party, position, cad_id FROM pt_votes WHERE division_key=? "
            "ORDER BY name", (division_key,)):
        out.append({"member_id": cad_id, "name": name, "party": party,
                    "position": position, "derived": False, "basis": "named in the record"})
        if cad_id is not None:
            named.add(cad_id)
    for party, position in conn.execute(
            "SELECT party, position FROM pt_group_votes WHERE division_key=? AND members IS NULL "
            "ORDER BY party", (division_key,)):
        for cad_id, name in conn.execute(
                "SELECT cad_id, name FROM pt_members WHERE party=? AND situation LIKE 'Efetiv%' "
                "ORDER BY name", (party,)):
            if cad_id in named:
                continue
            out.append({"member_id": cad_id, "name": name, "party": party,
                        "position": position, "derived": True,
                        "basis": "group vote; deputy's latest group"})
    return out
