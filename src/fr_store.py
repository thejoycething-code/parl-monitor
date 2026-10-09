"""Tables for the France monitor (phase 1, 9 October 2026): the Assemblee
nationale's deputies and political groups, its dossiers legislatifs, its
scrutins publics and every deputy's position.

See docs/france-scope.md for what was measured and why. The schema follows
the US precedent (src/us_store.py): its own module, idempotent statements,
created by db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/fr_*.py writes these tables,
and nothing here touches another jurisdiction's table.

KEYS. A deputy is the Assemblee's own acteur ID ('PA1008'), the one
identifier every AN dataset shares (scrutins, dossiers, amendements,
questions, agenda). A dossier is its AN uid ('DLR5L17N51670'): the
legislature is inside the key, so a dossier carried over from the 16th
legislature ('DLR5L16N49654', a Senate-adopted bill still pending at the
Assemblee) keeps its own key. A division is 'an-<legislature>-<numero>'.
Titles are never keys: the AN gives the same text several titles (the
dossier's short "Fin de vie", the bill's "relative au droit a l'aide a
mourir"), and the scrutin's own title truncates the text's name.

THE GROUP IS STORED PER VOTE, as party is in Canada and the US: each
scrutin publishes its positions group by group, so `fr_votes.group_ref` is
the group the deputy sat in on that day. `fr_members.group_ref` is only the
latest seen.

A MISE AU POINT IS NOT A VOTE. A deputy may say afterwards that they meant
to vote otherwise (1,593 of the 8,621 scrutins of the 17th legislature
carry at least one). The official result never changes, so `position` is
what was recorded and `intended` is what the deputy said afterwards.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS fr_members (
        acteur_ref   TEXT PRIMARY KEY,   -- 'PA1008'
        chamber      TEXT NOT NULL,      -- 'an' (the Senat is phase 2)
        name         TEXT,
        civility     TEXT,               -- 'M.' / 'Mme'
        group_ref    TEXT,               -- latest seen; see fr_votes.group_ref
        department   TEXT,
        constituency TEXT,               -- circonscription number
        current      INTEGER,            -- 1 when in the sitting-deputies file
        as_of        TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS fr_groups (
        organe_ref   TEXT PRIMARY KEY,   -- 'PO845401'
        chamber      TEXT NOT NULL,
        abbr         TEXT,               -- 'RN'
        label        TEXT,               -- 'Rassemblement National'
        date_start   TEXT,
        date_end     TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS fr_dossiers (
        dossier_ref  TEXT PRIMARY KEY,   -- 'DLR5L17N51670'
        legislature  INTEGER,
        title        TEXT,               -- the dossier's own (often short) title
        procedure    TEXT,               -- 'Proposition de loi ordinaire', ...
        an_path      TEXT,               -- titreChemin: the assemblee-nationale.fr slug
        senat_url    TEXT,               -- the Senat's dossier page, when it has one
        initiator    TEXT,               -- acteur_ref of the first author, if a deputy
        doc_titles   TEXT,               -- JSON list: every document title filed under it
        last_act     TEXT,               -- code of the latest dated act: 'PROM-PUB', 'AN2-DEBATS-DEC'
        last_act_label TEXT,
        last_act_at  TEXT,
        promulgated_at TEXT,
        areas        TEXT,               -- JSON list; taxonomy + watchlist-fr by key
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS fr_divisions (
        division_key TEXT PRIMARY KEY,   -- 'an-17-6722'
        chamber      TEXT NOT NULL,      -- 'an'
        legislature  INTEGER NOT NULL,
        number       INTEGER NOT NULL,   -- the scrutin's numero
        date         TEXT,
        vote_type    TEXT,               -- 'SPO' ordinaire, 'SPS' solennel, 'MOC' motion de censure
        result       TEXT,               -- the AN's own code: 'adopté' / 'rejeté'
        title        TEXT,               -- what was voted on, in the AN's words
        dossier_ref  TEXT,               -- NULL when no dossier could be named
        dossier_via  TEXT,               -- 'ref' (the scrutin names it) / 'title' (unique title match)
        pour         INTEGER,
        contre       INTEGER,
        abstentions  INTEGER,
        non_votants  INTEGER,
        own_areas    TEXT,               -- JSON: matched on the scrutin's OWN title
        areas        TEXT,               -- JSON: own + the dossier's
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS fr_votes (
        division_key TEXT NOT NULL,
        acteur_ref   TEXT NOT NULL,
        position     TEXT,               -- 'pour' / 'contre' / 'abstention' / 'nonVotant'
        group_ref    TEXT,               -- AT THE VOTE
        by_delegation INTEGER,           -- 1: cast by proxy (parDelegation)
        cause        TEXT,               -- why a non-vote: 'PAN', 'PSE', 'MG'
        intended     TEXT,               -- mise au point: what the deputy said they meant
        PRIMARY KEY (division_key, acteur_ref)
    )""",
    "CREATE INDEX IF NOT EXISTS fr_divisions_dossier ON fr_divisions (dossier_ref)",
    "CREATE INDEX IF NOT EXISTS fr_votes_member ON fr_votes (acteur_ref)",
)

TABLES = ("fr_members", "fr_groups", "fr_dossiers", "fr_divisions", "fr_votes")

MEMBER_UPSERT = (
    "INSERT INTO fr_members (acteur_ref, chamber, name, civility, group_ref, department, "
    "constituency, current, as_of, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
    "ON CONFLICT(acteur_ref) DO UPDATE SET "
    "name=COALESCE(excluded.name, fr_members.name), "
    "civility=COALESCE(excluded.civility, fr_members.civility), "
    "group_ref=CASE WHEN {newer} THEN COALESCE(excluded.group_ref, fr_members.group_ref) "
    "ELSE fr_members.group_ref END, "
    "department=COALESCE(excluded.department, fr_members.department), "
    "constituency=COALESCE(excluded.constituency, fr_members.constituency), "
    "current=COALESCE(excluded.current, fr_members.current), "
    "as_of=CASE WHEN {newer} THEN excluded.as_of ELSE fr_members.as_of END, "
    "last_seen=excluded.last_seen").format(
        newer="COALESCE(excluded.as_of, '') >= COALESCE(fr_members.as_of, '')")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- the France watchlist, applied by dossier KEY ---------------------------

_WATCH = {}


def watchlist(path=None):
    """{dossier_ref: (areas, why)} from config/watchlist-fr.yaml."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-fr.yaml")
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {k: (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("dossiers") or {}).items()}
    return _WATCH[path]


def add_watch_areas(res, dossier_ref, path=None):
    """Union a watched dossier's areas into a FilterResult, in place, and say
    so in watchlist_hits so the stored row shows where the area came from."""
    hit = watchlist(path).get(dossier_ref)
    if not hit:
        return res
    areas, _why = hit
    res.issue_areas = sorted(set(res.issue_areas or []) | set(areas))
    res.watchlist_hits = list(res.watchlist_hits or []) + ["watch:" + dossier_ref]
    if res.tier is None:
        res.tier = 2
    return res


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
