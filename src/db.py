"""SQLite schema and connection helper (handoff section 5).

The store is the single source of truth: the digest, alerts and MP
intelligence are all queries over these tables. Nothing is written "for the
digest". The schema below is the handoff section 5 model verbatim, with
`IF NOT EXISTS` so init is idempotent.
"""

from __future__ import annotations

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY,            -- '{feed}:{source_id}'
  captured_at TEXT NOT NULL,
  source_feed TEXT NOT NULL,      -- bills|pq|wms|edm|si|division|whatson|consultation|scotland|committee
  item_type TEXT NOT NULL,
  title TEXT, url TEXT,
  legislature TEXT,               -- Commons|Lords|Holyrood|Senedd|NIA
  jurisdiction TEXT,
  event_date TEXT, deadline TEXT,
  date_tabled TEXT,               -- PQs: required for deep links
  issue_areas TEXT,               -- json list of area numbers
  matched_terms TEXT,             -- json list, for taxonomy maintenance
  tier INTEGER, triage_score INTEGER,
  priority_tag TEXT,              -- ACT|WATCH|NOTE (human-set at review)
  why_it_matters TEXT,            -- <=35 words, drafted by triage, edited by human
  owner TEXT, action_status TEXT DEFAULT 'none',
  mp_refs TEXT, bill_ref INTEGER,
  raw_path TEXT,                  -- provenance pointer into data/raw/
  extra TEXT                      -- feed-specific structured payload (json)
);
CREATE TABLE IF NOT EXISTS bills_board (
  bill_id INTEGER PRIMARY KEY, title TEXT, sponsor TEXT,
  house TEXT, stage TEXT, next_key_date TEXT, what_next TEXT,
  areas TEXT, status TEXT,        -- live|closed
  closed_note TEXT, closed_edition TEXT,
  session_ids TEXT, last_update TEXT, board_snapshot TEXT -- json of prior edition row for movement marker
);
CREATE TABLE IF NOT EXISTS members (id INTEGER PRIMARY KEY, name TEXT, party TEXT, seat TEXT, house TEXT);
CREATE TABLE IF NOT EXISTS mp_events (member_id INTEGER, date TEXT, kind TEXT, ref TEXT, line TEXT,
  areas TEXT                      -- json list of area numbers (5CA per-area scoring)
);
CREATE TABLE IF NOT EXISTS edm_signatures (edm_id INTEGER, edition TEXT, count INTEGER, PRIMARY KEY (edm_id, edition));
CREATE TABLE IF NOT EXISTS editions (week_commencing TEXT PRIMARY KEY, generated_at TEXT, mode TEXT, path TEXT);
CREATE TABLE IF NOT EXISTS gaps (edition TEXT, feed TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS discards (edition TEXT, item_id TEXT, title TEXT, matched_terms TEXT);
"""

# Tables the schema is expected to create; used by init verification and tests.
TABLES = (
    "items",
    "bills_board",
    "members",
    "mp_events",
    "edm_signatures",
    "editions",
    "gaps",
    "discards",
)


def connect(path):
    """Open a connection with dict-like rows and foreign keys enabled."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    """Create all tables if absent, and apply column migrations. Idempotent."""
    conn.executescript(SCHEMA)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(items)")}
    if "extra" not in cols:
        conn.execute("ALTER TABLE items ADD COLUMN extra TEXT")
    ev_cols = {r[1] for r in conn.execute("PRAGMA table_info(mp_events)")}
    if "areas" not in ev_cols:
        conn.execute("ALTER TABLE mp_events ADD COLUMN areas TEXT")
    conn.commit()
    return conn
