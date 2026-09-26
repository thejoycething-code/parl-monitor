"""Tables for the Canadian monitor (phase 1: House of Commons divisions and bills).

WHY A MODULE OF ITS OWN. Every other jurisdiction's schema lives in
`src/db.py:init_db`. These four tables are kept here while the Canadian
monitor is groundwork only, so a scoping build cannot collide with work in
progress on the shared schema. `ensure_schema` is idempotent and every
Canadian tool calls it; when the monitor is adopted, fold these statements
into `init_db` and make this a re-export.

SEPARATION GUARANTEE. Nothing outside tools/ca_*.py reads or writes these
tables, and nothing here touches a Westminster, devolved, EU or German table.

PARTY IS STORED PER VOTE. The House publishes each participant's caucus on
the division itself, so `ca_votes.party` is the party the member voted in,
not the one they sit in today. `ca_members.party` is only the latest seen.
The Northern Ireland roster taught that joining a past vote to today's party
misattributes every floor-crosser (src/ni_store.py).
"""

from __future__ import annotations

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS ca_members (
        person_id    TEXT PRIMARY KEY,   -- the House's PersonId
        name         TEXT,
        party        TEXT,               -- latest caucus seen; see ca_votes.party
        constituency TEXT,
        province     TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ca_divisions (
        division_key TEXT PRIMARY KEY,   -- '<chamber>-<parl>-<session>-<number>'
        chamber      TEXT NOT NULL,      -- 'commons' (the Senate is phase 2)
        parliament   INTEGER NOT NULL,
        session      INTEGER NOT NULL,
        number       INTEGER NOT NULL,
        date         TEXT,               -- ISO date-time as the House gives it
        subject      TEXT,
        result       TEXT,               -- the House's own words, never derived
        yeas         INTEGER,
        nays         INTEGER,
        paired       INTEGER,
        doc_type     TEXT,               -- 'Legislative Process', 'Supply', ...
        bill_number  TEXT,               -- 'C-9', or NULL for a motion
        areas        TEXT,               -- JSON list; English taxonomy + watchlist-ca
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        positions_fetched INTEGER NOT NULL DEFAULT 0,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ca_votes (
        division_key TEXT NOT NULL,
        person_id    TEXT NOT NULL,
        position     TEXT,               -- 'Yea' / 'Nay' / 'Paired'
        party        TEXT,               -- caucus AT THE VOTE
        PRIMARY KEY (division_key, person_id)
    )""",
    """CREATE TABLE IF NOT EXISTS ca_bills (
        bill_key     TEXT PRIMARY KEY,   -- '<parl>-<session>/<number>'
        parliament   INTEGER NOT NULL,
        session      INTEGER NOT NULL,
        number       TEXT NOT NULL,      -- 'C-34', 'S-209'
        legisinfo_id TEXT,
        long_title   TEXT,
        short_title  TEXT,
        status       TEXT,
        is_government INTEGER,
        sponsor      TEXT,
        latest_event TEXT,
        latest_event_at TEXT,
        royal_assent_at TEXT,
        areas        TEXT,
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ca_divisions_date ON ca_divisions (date)",
    "CREATE INDEX IF NOT EXISTS ca_votes_person ON ca_votes (person_id)",
)


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn
