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
  agenda_item INTEGER,
  subject TEXT,                   -- the AGENDA ITEM title
  title TEXT,                     -- the draft's OWN title, where it has one
  amends TEXT,                    -- the draft an amendment attacks
  instruction TEXT,               -- an amendment's operative text
  event TEXT,                     -- 'mandate' etc: a campaign trigger type
  kind TEXT,                      -- resolution | decision | note
  dated TEXT,
  areas TEXT,                     -- json list of OUR area numbers
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
);
-- Recorded votes from HRC session reports. One row per state per vote, which
-- is what makes "how did Nigeria vote on every SRHR text" a single query --
-- the same shape as mp_events for Westminster divisions.
CREATE TABLE IF NOT EXISTS un_votes (
  report TEXT NOT NULL,           -- 'A/HRC/58/2'
  draft TEXT,                     -- 'A/HRC/58/L.30/Rev.1'; joins to un_documents
  state TEXT NOT NULL,
  position TEXT NOT NULL,         -- for | against | abstain
  captured_at TEXT NOT NULL,
  PRIMARY KEY (report, draft, state)
);
-- Northern Ireland Assembly. A SEPARATE table from `items` on purpose: the
-- published edition is built by "SELECT ... FROM items", so anything stored
-- there can reach the Slack digest. NI is a watching brief (Christopher,
-- 2026-08-18) and must stay off that report, so the separation is structural
-- rather than a flag on a row that a later query could forget to filter.
CREATE TABLE IF NOT EXISTS ni_items (
  id TEXT PRIMARY KEY,            -- 'ni-question:21109' | 'ni-motion:448545' | 'ni-diary:19841'
  kind TEXT NOT NULL,             -- question|motion|diary
  reference TEXT,                 -- 'AQW 4832/08'; motions and diary have none
  title TEXT,                     -- motion title, diary organisation, question text
  dated TEXT,                     -- tabled date, or the event date for diary rows
  tablers TEXT,                   -- motions: raw "Name (PARTY) / Name (PARTY)"
  parties TEXT,                   -- json list, motions only
  category TEXT,                  -- motion category, or diary event type
  areas TEXT,                     -- json list of OUR area numbers
  matched_terms TEXT,             -- json list, for taxonomy maintenance
  url TEXT,
  tabler_person_id TEXT,          -- joins to ni_members; null until enriched
  tabler TEXT, tabler_seat TEXT,
  minister TEXT, department TEXT,
  answered TEXT, answer TEXT,     -- answer stored whole, displayed truncated
  body TEXT,                      -- a motion's operative TEXT, stored whole so
                                  -- re-classification never re-fetches. `title`
                                  -- is the 3-6 word label that classified 0 of
                                  -- 33; this is what actually carries meaning.
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
);
-- The 90 sitting MLAs. Needed because no question or division payload carries
-- a party: they give a PersonId and expect you to join.
CREATE TABLE IF NOT EXISTS ni_members (
  person_id TEXT PRIMARY KEY,
  name TEXT, display_name TEXT, party TEXT, constituency TEXT,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
);
-- Party AS AT a date, one row per member per date we have had reason to ask
-- about. ni_members holds the CURRENT roster and answers "who is an MLA now";
-- this answers "whose party was what when they said it", which is the only
-- honest basis for attributing a question or a vote. A floor-crosser reads
-- differently in the two tables by design: Doug Beattie asked as UUP leader
-- and sits as an Independent now, and the row must show the party he held on
-- the day. Sparse on purpose -- dates are fetched only when needed.
CREATE TABLE IF NOT EXISTS ni_affiliations (
  person_id TEXT NOT NULL,
  as_at TEXT NOT NULL,            -- the date asked about, not a term boundary
  party TEXT, constituency TEXT, display_name TEXT,
  captured_at TEXT NOT NULL,
  PRIMARY KEY (person_id, as_at)
);
-- Assembly divisions. `bill` is DERIVED from the subject (see bill_of) because
-- the subject names an amendment number, not what the amendment says, and is
-- truncated at 100 characters. Grouping by bill is the only usable unit.
-- COLUMN OWNERSHIP, and why it is written down. tools/ni_divisions.py owns
-- identity and `watched`; tools/ni_classify.py owns everything derived from
-- Hansard (areas, matched_terms, evidence*, excerpt, item*, amendment_no,
-- on_amendment, classified_at). The harvester upserts by NAME rather than
-- INSERT OR REPLACE precisely so a later harvest cannot blank a classification
-- -- which it did, and which would have looked exactly like the bug being fixed.
CREATE TABLE IF NOT EXISTS ni_divisions (
  doc_id TEXT PRIMARY KEY,
  event_id TEXT,
  subject TEXT,                   -- verbatim, truncated by the API at 100 chars
  bill TEXT,                      -- derived group key
  dated TEXT,
  kind TEXT,                      -- 'Simple Majority' | 'Cross-Community'
  areas TEXT,                     -- json list, from the AMENDMENT TEXT via Hansard
  matched_terms TEXT,
  watched INTEGER,                -- 1 when a human listed the bill in ni_watch.yaml
  item_id TEXT,                   -- Hansard plenary item id: an ID, not a title
  item_name TEXT,                 -- Header text, UNTRUNCATED, with stage
  amendment_no INTEGER,           -- from the Hansard 'Question put' line
  on_amendment INTEGER,           -- 1 = amendment vote, 0 = whole question
  evidence TEXT,                  -- the amendment's own wording, stored whole
  evidence_source TEXT,           -- amendment-text | item-text | no-text
  excerpt TEXT,                   -- strongest passage, for display
  classified_at TEXT,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
);
-- One row per Hansard sitting already fetched, so a re-run costs nothing --
-- the same job ni_store.dates_present does for rosters.
CREATE TABLE IF NOT EXISTS ni_sittings (
  dated TEXT PRIMARY KEY,
  components INTEGER,             -- a sudden drop is a signal, not noise
  divisions INTEGER,
  captured_at TEXT NOT NULL
);
-- One row per MLA per division: the same shape as mp_events for Westminster
-- divisions, so "how did this MLA vote on every X" is a single query.
-- `designation` is NI-specific and load-bearing: a cross-community vote needs
-- majorities in both, so a bare for/against tally misreads it.
CREATE TABLE IF NOT EXISTS ni_votes (
  doc_id TEXT NOT NULL,
  person_id TEXT NOT NULL,
  member TEXT,
  vote TEXT NOT NULL,             -- aye | no | abstain | (verbatim if unknown)
  designation TEXT,               -- Unionist | Nationalist | Other
  captured_at TEXT NOT NULL,
  PRIMARY KEY (doc_id, person_id)
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
    "un_votes",
    "ni_items",
    "ni_members",
    "ni_affiliations",
    "ni_divisions",
    "ni_sittings",
    "ni_votes",
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
    d_cols = {r[1] for r in conn.execute("PRAGMA table_info(un_documents)")}
    if d_cols:
        # Added 2026-08-17 once pypdf made subjects readable: the table was
        # created a few hours earlier holding symbols only.
        for column, decl in (("agenda_item", "INTEGER"), ("subject", "TEXT"),
                             ("title", "TEXT"), ("amends", "TEXT"),
                             ("instruction", "TEXT"), ("event", "TEXT"),
                             ("kind", "TEXT"),
                             ("dated", "TEXT"), ("areas", "TEXT")):
            if column not in d_cols:
                conn.execute("ALTER TABLE un_documents ADD COLUMN {0} {1}"
                             .format(column, decl))
    n_cols = {r[1] for r in conn.execute("PRAGMA table_info(ni_items)")}
    if n_cols:
        # Added 2026-08-18 with MLA attribution: the table was created earlier
        # the same day holding no tabler, because the question SEARCH endpoint
        # returns no member name. GetQuestionDetails supplies these.
        for column in ("tabler_person_id", "tabler", "tabler_seat", "minister",
                       "department", "answered", "answer", "body"):
            if column not in n_cols:
                conn.execute("ALTER TABLE ni_items ADD COLUMN {0} TEXT"
                             .format(column))
    nd_cols = {r[1] for r in conn.execute("PRAGMA table_info(ni_divisions)")}
    if nd_cols:
        # Added 2026-08-18 with Hansard classification: the table was created
        # earlier the same day, when a division's areas could only come from its
        # subject line -- which yielded 0 of 139.
        for column, decl in (("item_id", "TEXT"), ("item_name", "TEXT"),
                             ("amendment_no", "INTEGER"),
                             ("on_amendment", "INTEGER"), ("evidence", "TEXT"),
                             ("evidence_source", "TEXT"), ("excerpt", "TEXT"),
                             ("classified_at", "TEXT")):
            if column not in nd_cols:
                conn.execute("ALTER TABLE ni_divisions ADD COLUMN {0} {1}"
                             .format(column, decl))
    if "current_mp" not in m_cols:
        # 1 = sitting MP per the Commons roster pull; peers and former
        # members stay NULL. Full-roster 5CA sheets select on this flag.
        conn.execute("ALTER TABLE members ADD COLUMN current_mp INTEGER")
    conn.commit()
    return conn
