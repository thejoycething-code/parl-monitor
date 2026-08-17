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
  areas TEXT,                     -- json list of area numbers (5CA per-area scoring)
  excerpt TEXT                    -- the matching passage: why this row exists
);
CREATE TABLE IF NOT EXISTS edm_signatures (edm_id INTEGER, edition TEXT, count INTEGER, PRIMARY KEY (edm_id, edition));
CREATE TABLE IF NOT EXISTS editions (week_commencing TEXT PRIMARY KEY, generated_at TEXT, mode TEXT, path TEXT);
-- UN monitor. A UPR recommendation is a position taken by one state towards
-- another, so both states are first-class here rather than one being an
-- attribute of the other: the interesting cut is often who is DOING the
-- pressing, not who is receiving it.
CREATE TABLE IF NOT EXISTS upr_recommendations (
  id TEXT PRIMARY KEY,            -- uwazi sharedId, stable across edits
  first_seen TEXT,                -- set once; what makes "new this month" answerable
  captured_at TEXT NOT NULL,
  text TEXT,
  state_under_review TEXT, sur_group TEXT,
  recommending_state TEXT, rs_group TEXT,
  response TEXT,                  -- Supported | Noted | Not Supported
  refused INTEGER,                -- 1 for Noted or Not Supported; see upr.py
  issues TEXT,                    -- json list of UPR issue tags
  issue_areas TEXT,               -- json list of OUR area numbers
  matched_terms TEXT,             -- json list, for taxonomy maintenance
  cycle TEXT, session TEXT, action_category TEXT,
  url TEXT
);
-- UN forward calendar. One row per dated thing the UN has announced, so a
-- weekly message can report what is NEW and what has DISAPPEARED rather than
-- re-listing the same fifteen calls every week.
-- Ids are constructed to be stable across runs but NOT to include the date,
-- so a deadline that moves shows up as a change to one row instead of as one
-- row vanishing and another appearing.
CREATE TABLE IF NOT EXISTS un_calendar (
  id TEXT PRIMARY KEY,            -- 'call:<slug>' | 'session:<body>:<n>' | 'treaty:<treaty>:<country>:<doc>' | 'meeting:<uuid>'
  kind TEXT NOT NULL,             -- session|call|treaty|meeting
  title TEXT, body TEXT,
  starts TEXT, ends TEXT,         -- ISO; starts may carry a time for meetings
  approximate INTEGER,            -- 1 when only the month is published
  areas TEXT,                     -- json list of OUR area numbers, or null
  url TEXT,
  first_seen TEXT NOT NULL,       -- set once; never moved by a re-read
  last_seen TEXT NOT NULL,
  gone_at TEXT                    -- set when a still-future item stops being listed
);
-- UN documents discovered by symbol (draft resolutions). Separate from
-- un_calendar because a draft has no date: what matters is that it exists and
-- when we first saw it, which is what makes "new drafts this week" answerable.
CREATE TABLE IF NOT EXISTS un_documents (
  symbol TEXT PRIMARY KEY,        -- 'A/C.3/81/L.7'
  body TEXT,                      -- 'Third Committee' | 'Human Rights Council'
  session INTEGER,
  url TEXT, size INTEGER,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
);
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
    "upr_recommendations",
    "un_calendar",
    "un_documents",
)


def connect(path):
    """Open a connection with dict-like rows and foreign keys enabled."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Backfills may run concurrently (e.g. Hansard alongside PQ/EDM); both
    # commit in tiny transactions, so a generous busy wait absorbs overlap.
    conn.execute("PRAGMA busy_timeout = 30000")
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
    if "excerpt" not in ev_cols:
        conn.execute("ALTER TABLE mp_events ADD COLUMN excerpt TEXT")
    m_cols = {r[1] for r in conn.execute("PRAGMA table_info(members)")}
    for column in ("since", "list_as"):
        if column not in m_cols:
            # since = start of the current membership period, which is what
            # "Not yet an MP for this division" depends on; list_as = how
            # Parliament sorts names.
            conn.execute("ALTER TABLE members ADD COLUMN {0} TEXT".format(column))
    if "current_peer" not in m_cols:
        conn.execute("ALTER TABLE members ADD COLUMN current_peer INTEGER")
    u_cols = {r[1] for r in conn.execute("PRAGMA table_info(upr_recommendations)")}
    if u_cols and "first_seen" not in u_cols:
        # Added 2026-08-17. captured_at is refreshed on every upsert, so it
        # cannot answer "what arrived since last month" -- which is the whole
        # point of a monthly run. Backfilled from captured_at: those rows
        # were genuinely first seen at the initial harvest.
        conn.execute("ALTER TABLE upr_recommendations ADD COLUMN first_seen TEXT")
        conn.execute("UPDATE upr_recommendations SET first_seen = captured_at "
                     "WHERE first_seen IS NULL")
    if "current_mp" not in m_cols:
        # 1 = sitting MP per the Commons roster pull; peers and former
        # members stay NULL. Full-roster 5CA sheets select on this flag.
        conn.execute("ALTER TABLE members ADD COLUMN current_mp INTEGER")
    conn.commit()
    return conn
