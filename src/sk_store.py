"""Tables for the Slovak monitor (phase 1, 9 October 2026): the members of
the Národná rada, its parliamentary prints (tlače), its recorded votes with
every member's position, and interpellations.

See docs/slovakia-scope.md for what was measured and why. Same shape as
src/us_store.py: its own module, idempotent statements, created by
db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/sk_*.py writes these tables,
and nothing here touches another jurisdiction's table.

KEYS.
  * A member is the Národná rada's own PoslanecID (`mpId` in the open data,
    `PoslanecID=` in every vote page). It is stable across terms.
  * A bill is '<term>/<tlač>', '9/733': print numbers restart every
    electoral term (volebné obdobie), so the number alone is ambiguous
    across terms. Never the title: Slovak titles name the law being
    amended ("...ktorým sa mení a dopĺňa zákon č. 36/2005 Z. z. o rodine"),
    and dozens of prints share one.
  * A vote is the parliament's own voting ID (`id` in Voting/Votings, `ID=`
    in the vote pages), unique across terms.

CLUB IS STORED PER VOTE. `sk_votes.club` is the club (poslanecký klub) the
vote page grouped the member under on that day. Slovak MPs change clubs
mid-term (HLAS listed 40 members ever and 24 current on 9 October 2026), so
`sk_members.club` is only the latest the open data reports.

POSITIONS ARE FETCHED ONLY WHERE THEY MATTER. The vote list is one JSON
call; each vote's positions are one slow HTML page (1.7 to 96 seconds each,
measured). `sk_divisions.positions_at` says when they were read; NULL means
not yet, which the collector fills for votes on our ground.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS sk_members (
        mp_id        INTEGER PRIMARY KEY, -- PoslanecID
        name         TEXT,                -- 'Bajo Holečková, Martina' as the source prints it
        first_name   TEXT,
        last_name    TEXT,
        party        TEXT,                -- the party on whose list they stood
        club         TEXT,                -- latest club abbreviation; see sk_votes.club
        club_id      INTEGER,
        region       TEXT,
        term         INTEGER,             -- latest electoral term seen
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS sk_bills (
        bill_key     TEXT PRIMARY KEY,    -- '9/733'
        term         INTEGER NOT NULL,
        tlac         TEXT NOT NULL,       -- the print number, '733'
        od_id        INTEGER,             -- the open data's own id (NOT the web MasterID)
        type_id      INTEGER,             -- 1 bill, 2 information, 3 report, 4 other, 5 treaty, 6 petition
        type_name    TEXT,
        title        TEXT,
        delivered    TEXT,                -- ISO date
        areas        TEXT,                -- JSON list; taxonomy-sk + watchlist-sk by key
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS sk_divisions (
        voting_id    INTEGER PRIMARY KEY, -- the parliament's own voting ID
        term         INTEGER NOT NULL,
        meeting      INTEGER,             -- schôdza number
        number       INTEGER,             -- vote number within the meeting
        date         TEXT,                -- ISO datetime as published
        name         TEXT,                -- the vote's own label, often the print's title + the question
        bill_key     TEXT,                -- '9/733', or NULL (procedure, elections)
        vote_type    TEXT,                -- 'štandardné hlasovanie' / 'tajné hlasovanie' / 'hromadné hlasovanie'
        is_secret    INTEGER,
        is_constitutional INTEGER,       -- as published; FALSE on every vote of term 9, amendments included
        result       TEXT,                -- the source's own words, never derived
        present      INTEGER,
        agreed       INTEGER,             -- [Z] za
        disagreed    INTEGER,             -- [P] proti
        abstained    INTEGER,             -- [?] zdržal sa
        not_voting   INTEGER,             -- [N] nehlasoval
        absent       INTEGER,             -- [0] neprítomný; WRONG on 12% of votes, see check_totals
        own_areas    TEXT,                -- JSON: matched on the vote's OWN label
        areas        TEXT,                -- JSON: own + the print's
        matched_terms TEXT,
        tier         INTEGER,
        positions_at TEXT,                -- when the per-member page was read; NULL = not yet
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS sk_votes (
        voting_id    INTEGER NOT NULL,
        mp_id        INTEGER NOT NULL,
        position     TEXT,                -- 'Z' / 'P' / '?' / 'N' / '0', the source's own codes
        club         TEXT,                -- AT THE VOTE, as the page grouped it; NULL = no club
        PRIMARY KEY (voting_id, mp_id)
    )""",
    """CREATE TABLE IF NOT EXISTS sk_interpellations (
        int_id       INTEGER PRIMARY KEY,
        term         INTEGER,
        subject      TEXT,                -- 'Vo veci ...'
        questioner   TEXT,
        addressee    TEXT,                -- the office addressed, 'minister vnútra SR'
        state        TEXT,
        submitted    TEXT,
        answered     TEXT,
        satisfactory INTEGER,             -- the House's verdict on the answer, when voted
        areas        TEXT,
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS sk_divisions_bill ON sk_divisions (bill_key)",
    "CREATE INDEX IF NOT EXISTS sk_votes_member ON sk_votes (mp_id)",
)

TABLES = ("sk_members", "sk_bills", "sk_divisions", "sk_votes", "sk_interpellations")

# The source's position codes, for display. Stored as the code itself.
POSITIONS = {"Z": "za", "P": "proti", "?": "zdržal sa", "N": "nehlasoval", "0": "neprítomný"}


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- the Slovak watchlist, applied by print KEY -----------------------------
#
# As in the US: a key is exact, a title never is. The 2025 constitutional
# amendment (tlač 733) is titled only "Vládny návrh ústavného zákona, ktorým
# sa mení a dopĺňa Ústava Slovenskej republiky", like twenty other prints
# this term.

_WATCH = {}


def watchlist(path=None):
    """{bill_key: (areas, why)} from config/watchlist-sk.yaml."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-sk.yaml")
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {str(k): (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("bills") or {}).items()}
    return _WATCH[path]


def add_watch_areas(res, bill_key, path=None):
    """Union a watched print's areas into a FilterResult, in place, and say so
    in watchlist_hits so the stored row shows where the area came from."""
    hit = watchlist(path).get(bill_key) if bill_key else None
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
