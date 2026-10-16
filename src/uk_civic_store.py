"""Tables for the UK weekly edition's civic layer (16 October 2026): UK
Parliament e-petitions on our ground (tools/uk_petitions.py) and GOV.UK
consultations and key publications on our ground (tools/govuk_docs.py),
both filled by the Sunday pull before the Monday edition.

The two main tables are the ones agreed with the edition's renderer:

  uk_petitions(petition_id, title, state, signatures, threshold_reached,
               response_date, debate_date, url, areas, matched_terms,
               first_seen, last_seen)
  govuk_docs(base_path, title, doc_type, organisation, public_updated_at,
             closing_date, url, areas, matched_terms, first_seen, last_seen)

Extra columns after those are additions, never replacements: a renderer
written against the agreed columns keeps working.

PETITIONS ARE PUBLIC; NO SIGNER DATA. petition.parliament.uk publishes each
petition's counts by constituency and country, and the creator's name; none
of it is stored. A petition row is the petition itself and its milestones.

THRESHOLDS. threshold_reached is '100k', '10k' or NULL, from the API's own
response_threshold_reached_at / debate_threshold_reached_at (kept, as the
dates the line was crossed). threshold_first_seen is the Sunday our sweep
first saw the CURRENT threshold: what lets the edition say "crossed 10,000
this week" without re-deriving it.

govuk_docs IS KEYED ON THE GOV.UK base_path ('/government/consultations/x').
Two regulator routes land in the same table so the renderer reads one place
(source says which): Ofcom's consultations listing (full URL as the key, as
ofcom.org.uk has no base_path) and NHS England's publication feed.

SEPARATION. Nothing outside tools/uk_petitions.py and tools/govuk_docs.py
writes these tables.
"""

from __future__ import annotations

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS uk_petitions (
        petition_id        INTEGER PRIMARY KEY,
        title              TEXT NOT NULL,   -- the petition's 'action'
        state              TEXT,            -- open / closed (API state)
        signatures         INTEGER NOT NULL,
        threshold_reached  TEXT,            -- '100k' / '10k' / NULL
        response_date      TEXT,            -- Government response (YYYY-MM-DD)
        debate_date        TEXT,            -- Westminster Hall debate, scheduled or held
        url                TEXT,
        areas              TEXT,            -- json list of area numbers
        matched_terms      TEXT,            -- json list of matched terms
        first_seen         TEXT NOT NULL,
        last_seen          TEXT NOT NULL,
        tier               INTEGER,
        opened_at          TEXT,
        closing_date       TEXT,            -- when it closes (open) or closed
        closed_at          TEXT,
        response_threshold_at TEXT,         -- 10,000 crossed (API)
        debate_threshold_at   TEXT,         -- 100,000 crossed (API)
        threshold_first_seen  TEXT,         -- Sunday we first saw the current threshold
        debate_held        INTEGER,         -- 1 once the debate has happened
        debate_url         TEXT,            -- Hansard transcript, once debated
        response_summary   TEXT,            -- the Government's own one-paragraph summary
        departments        TEXT             -- json list
    )""",
    """CREATE TABLE IF NOT EXISTS uk_petition_counts (
        petition_id  INTEGER NOT NULL,
        captured_at  TEXT NOT NULL,          -- YYYY-MM-DD, the sweep's day
        signatures   INTEGER NOT NULL,
        PRIMARY KEY (petition_id, captured_at)
    )""",
    """CREATE TABLE IF NOT EXISTS govuk_docs (
        base_path          TEXT PRIMARY KEY,
        title              TEXT NOT NULL,
        doc_type           TEXT,            -- content_store_document_type
        organisation       TEXT,            -- '; '-joined organisation titles
        public_updated_at  TEXT,            -- YYYY-MM-DD
        closing_date       TEXT,            -- consultations (YYYY-MM-DD)
        url                TEXT,
        areas              TEXT,
        matched_terms      TEXT,
        first_seen         TEXT NOT NULL,
        last_seen          TEXT NOT NULL,
        description        TEXT,
        source             TEXT,            -- 'govuk' / 'ofcom' / 'nhs-england'
        tier               INTEGER,
        opening_date       TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS uk_civic_runs (
        source     TEXT NOT NULL,           -- 'uk_petitions:open', 'govuk:search', ...
        run_date   TEXT NOT NULL,
        ok         INTEGER NOT NULL,        -- 1 complete, 0 partial or failed
        fetched    INTEGER,
        matched    INTEGER,
        detail     TEXT,
        PRIMARY KEY (source, run_date)
    )""",
    "CREATE INDEX IF NOT EXISTS uk_petitions_state ON uk_petitions (state, last_seen)",
    "CREATE INDEX IF NOT EXISTS govuk_docs_type ON govuk_docs (doc_type, public_updated_at)",
)

ADDED_COLUMNS = ()


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    for table, column, kind in ADDED_COLUMNS:
        have = {r[1] for r in conn.execute("PRAGMA table_info({0})".format(table))}
        if column not in have:
            conn.execute("ALTER TABLE {0} ADD COLUMN {1} {2}".format(table, column, kind))
    conn.commit()
    return conn


def record_run(conn, source, run_date, ok, fetched=None, matched=None, detail=None):
    conn.execute("INSERT OR REPLACE INTO uk_civic_runs (source, run_date, ok, fetched, matched, detail) "
                 "VALUES (?,?,?,?,?,?)", (source, run_date, 1 if ok else 0, fetched, matched, detail))
    conn.commit()


def last_ok_run(conn, source):
    row = conn.execute("SELECT MAX(run_date) FROM uk_civic_runs WHERE source = ? AND ok = 1",
                       (source,)).fetchone()
    return row[0] if row else None
