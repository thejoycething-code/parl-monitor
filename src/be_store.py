"""Tables for the Belgian federal monitor (phase 1, 9 October 2026): the
Chamber's members, its parliamentary documents (dossiers), the plenary
sittings read, every recorded vote and every member's position.

See docs/belgium-scope.md for what was measured and why. Own module, as for
the US and Canada (src/us_store.py, src/ca_store.py): idempotent statements,
created by db.init_db so every store carries them and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/be_*.py writes these tables, and
nothing here touches another jurisdiction's table.

KEYS.
  * A dossier is '<legislature>/<number>', '56/1338'. The Chamber numbers its
    documents from 1 in every legislature, and every vote, report and
    amendment cites the number ("(1338/6)" is document 6 of dossier 1338).
    NEVER the title: the Chamber reuses titles across legislatures and the
    plenary record prints a different title for the same dossier on
    different days (the euthanasia leave bill gained "en van de periode van
    palliatief verlof (nieuw opschrift)" between first and second reading).
  * A member is the Chamber's own five-digit key ('07757'), the one its
    member pages, its document authors and its written questions share.
  * A division is '<legislature>/<sitting>/<vote>', '56/143/4': the plenary
    record numbers its recorded votes from 1 in every sitting.

NAMES, NOT IDS, IN THE VOTE LISTS. The plenary record lists each position by
"Surname Forename" only ("Van der Donckt Wim"). be_votes keeps that name as
printed and the member key it resolved to, NULL when nothing matched, so an
unresolved name is visible rather than guessed.

GROUP IS NOT PRINTED WITH THE VOTE. Unlike Canada and the US, the Chamber's
vote lists carry no party. `be_votes.group_seen` is the member's group as
the member list stood when the vote was stored, never the group at the vote
itself; a member who changes group later keeps the old label on old votes.

NO CLASSIFICATION YET. Until a Belgian Dutch and French term list is approved
(docs/belgium-scope.md, "Proposed taxonomy terms"), `areas` comes only from
config/watchlist-be.yaml, applied by dossier KEY. Nothing is matched on text.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS be_members (
        member_key   TEXT PRIMARY KEY,   -- the Chamber's key: '07757'
        name         TEXT,               -- as the vote lists print it: 'Aerts Staf'
        party_group  TEXT,               -- latest seen on the member list
        legislature  INTEGER,            -- latest legislature seen in
        current      INTEGER,            -- 1 when on the list of sitting members
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS be_dossiers (
        dossier_key  TEXT PRIMARY KEY,   -- '56/1338'
        legislature  INTEGER NOT NULL,
        number       INTEGER NOT NULL,
        title_fr     TEXT,
        title_nl     TEXT,
        descriptor_fr TEXT,              -- the main Eurovoc descriptor, as the listing prints it
        descriptor_nl TEXT,
        doc_type     TEXT,               -- '05 PROPOSITION DE LOI' (dossier page)
        status       TEXT,               -- 'PENDANT CHAMBRE', 'ADOPTE', ... (dossier page)
        procedure    TEXT,               -- '74 procédure monocamérale'
        deposited    TEXT,               -- ISO date
        authors      TEXT,               -- JSON [[member_key, 'Forename, Surname', group], ...]
        eurovoc      TEXT,               -- JSON list of every Eurovoc descriptor (FR)
        detail_read  TEXT,               -- date the dossier page was last read; NULL never
        areas        TEXT,               -- JSON; taxonomy-nl + taxonomy-fr on the titles, and watchlist-be by key
        matched_terms TEXT,              -- JSON; 'watch:56/1338'
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS be_sittings (
        sitting_key  TEXT PRIMARY KEY,   -- '56/143'
        legislature  INTEGER NOT NULL,
        number       INTEGER NOT NULL,
        date         TEXT,               -- ISO
        url          TEXT,
        divisions    INTEGER,
        sha1         TEXT,               -- of the HTML read; a re-read upserts
        read_at      TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS be_divisions (
        division_key TEXT PRIMARY KEY,   -- '56/143/4'
        legislature  INTEGER NOT NULL,
        sitting      INTEGER NOT NULL,
        vote_no      INTEGER NOT NULL,
        date         TEXT,
        dossier_key  TEXT,               -- '56/1338', from the agenda heading; NULL for motions
        doc_refs     TEXT,               -- JSON: every '1338/6' the heading and subject cite
        heading_nl   TEXT,
        heading_fr   TEXT,
        subjects     TEXT,               -- JSON [[nl, fr], ...]: every question this result decided
        kind         TEXT,               -- 'nominal' (names listed) / 'count' (counted only)
        yes          INTEGER,
        no           INTEGER,
        abstain      INTEGER,
        outcome      TEXT,               -- 'adopted' / 'rejected' / 'annulled' / NULL, from the Chamber's own words
        result_fr    TEXT,               -- that sentence, verbatim
        areas        TEXT,               -- JSON; the dossier's watchlist areas
        matched_terms TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS be_votes (
        division_key TEXT NOT NULL,
        member_name  TEXT NOT NULL,      -- as printed: 'Van der Donckt Wim'
        member_key   TEXT,               -- resolved; NULL when no member matched
        position     TEXT NOT NULL,      -- 'yes' / 'no' / 'abstain'
        group_seen   TEXT,               -- the member's group WHEN STORED, not at the vote
        PRIMARY KEY (division_key, member_name)
    )""",
    "CREATE INDEX IF NOT EXISTS be_divisions_dossier ON be_divisions (dossier_key)",
    "CREATE INDEX IF NOT EXISTS be_votes_member ON be_votes (member_key)",
)

TABLES = ("be_members", "be_dossiers", "be_sittings", "be_divisions", "be_votes")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- the Belgian watchlist, applied by dossier KEY -------------------------
#
# Keyed by document number for the same reason as the US list: a title is
# not an identity. See config/watchlist-be.yaml.

_WATCH = {}


def watchlist(path=None):
    """{dossier_key: (areas, why)} from config/watchlist-be.yaml."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-be.yaml")
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {str(k): (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("dossiers") or {}).items()}
    return _WATCH[path]


def watch_areas(dossier_key, path=None):
    """(areas, matched_terms) for a dossier key: ([], []) when not watched."""
    hit = watchlist(path).get(dossier_key or "")
    if not hit:
        return [], []
    return sorted(set(hit[0])), ["watch:" + dossier_key]


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
