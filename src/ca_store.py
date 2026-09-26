"""Tables for the Canadian monitor: House divisions and bills (phase 1),
Hansard, petitions, Senate votes and the Canada Gazette (phase 2).

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
        chamber      TEXT NOT NULL,      -- 'commons' or 'senate'
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
    # Phase 2 (26 September 2026): Hansard and petitions.
    #
    # Every sitting READ gets a row whatever it held, so "nothing on our
    # ground that week" can be told apart from "that week was never read".
    """CREATE TABLE IF NOT EXISTS ca_sittings (
        sitting_key  TEXT PRIMARY KEY,   -- '<parl>-<session>-<number>'
        parliament   INTEGER NOT NULL,
        session      INTEGER NOT NULL,
        number       INTEGER NOT NULL,
        date         TEXT,
        interventions INTEGER,           -- every Intervention in the XML
        chair        INTEGER,            -- the presiding officer's, counted not stored
        stored       INTEGER,            -- speeches on our ground
        unresolved   INTEGER,            -- stored speeches with no person_id
        chars        INTEGER,
        read_at      TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ca_speeches (
        speech_id    TEXT PRIMARY KEY,   -- the Hansard Intervention id
        sitting_key  TEXT NOT NULL,
        date         TEXT,
        time         TEXT,               -- 'HH:MM', the last Hansard timestamp before it
        rubric       TEXT,               -- 'Government Orders', 'Oral Questions', ...
        subject      TEXT,               -- SubjectOfBusinessTitle
        bill_number  TEXT,
        kind         TEXT,               -- the House's Type: Debate/Question/Answer/Interjection
        db_id        TEXT,               -- Hansard Affiliation DbId: a ROLE, not a person
        person_id    TEXT,               -- resolved to ca_members, or NULL, never guessed
        speaker      TEXT,               -- the label exactly as printed
        party        TEXT,               -- as printed in the label, when it is
        text         TEXT,
        areas        TEXT,
        matched_terms TEXT,
        excerpt      TEXT,
        first_seen   TEXT
    )""",
    # Hansard's DbId identifies a member IN A ROLE: Kevin Lamoureux speaking
    # as a parliamentary secretary has a different DbId from his members'
    # PersonId, and a minister's later interventions are labelled only
    # "Minister of Finance". The map is learned from labels that carry a
    # riding, and kept, so a bare role label resolves on a later sitting.
    """CREATE TABLE IF NOT EXISTS ca_speaker_roles (
        db_id        TEXT PRIMARY KEY,
        person_id    TEXT NOT NULL,
        label        TEXT,
        how          TEXT,               -- 'riding' or 'name': which key resolved it
        first_seen   TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ca_petitions (
        petition_id  TEXT PRIMARY KEY,   -- 'e-7000' or '451-00001', the page's own number
        presented_number TEXT,           -- '451-01121' once presented; NULL while open
        kind         TEXT,               -- 'E-petition' / 'Paper petition'
        category     TEXT,               -- the House's subject, e.g. 'Health'
        keywords     TEXT,               -- JSON list of the House's index terms
        addressee    TEXT,
        prayer       TEXT,
        opened       TEXT,
        closed       TEXT,
        presented    TEXT,
        mp_person_id TEXT,               -- the sponsoring/presenting member's PersonId
        mp_name      TEXT,
        response_tabled TEXT,
        response_by  TEXT,
        response_text TEXT,              -- on our ground only
        signatures   INTEGER,
        areas        TEXT,
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    # Senate (phase 2b). Senators have their own id space on sencanada.ca,
    # so their rows in ca_votes carry person_id 'senator-<id>' and can never
    # collide with a House PersonId. Divisions share ca_divisions with
    # chamber='senate'; the Senate publishes no division number, so `number`
    # is the vote's details id.
    """CREATE TABLE IF NOT EXISTS ca_senators (
        person_id    TEXT PRIMARY KEY,   -- 'senator-<sencanada id>'
        name         TEXT,               -- 'Martin, Yonah', as the Senate prints it
        affiliation  TEXT,               -- latest seen; ca_votes.party is at the vote
        province     TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    # Canada Gazette (phase 2b). Part I carries notices and PROPOSED
    # regulations with their comment period; Part II carries made
    # regulations (SOR) and statutory instruments (SI). Every issue READ gets
    # a row, as every Hansard sitting does.
    """CREATE TABLE IF NOT EXISTS ca_gazette_issues (
        issue_key    TEXT PRIMARY KEY,   -- 'p1-2026-09-26'
        part         INTEGER NOT NULL,
        date         TEXT NOT NULL,
        title        TEXT,
        url          TEXT,
        items        INTEGER,
        ours         INTEGER,
        read_at      TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ca_gazette_items (
        item_key     TEXT PRIMARY KEY,   -- the item's URL, with its #anchor for a notice
        issue_key    TEXT NOT NULL,
        part         INTEGER,
        date         TEXT,
        section      TEXT,               -- 'Government notices', 'Proposed Regulations', ...
        department   TEXT,               -- the index's sub-heading
        title        TEXT,
        url          TEXT,
        kind         TEXT,               -- 'regulation'/'extra'/'document' (own page) or 'notice' (anchor on a shared page)
        registration TEXT,               -- 'SOR/2026-184' for Part II
        comment_days INTEGER,            -- Part I: 'within N days after the date of publication'
        comment_until TEXT,              -- date + comment_days
        areas        TEXT,
        matched_terms TEXT,
        tier         INTEGER,
        excerpt      TEXT,
        matched_on   TEXT,               -- 'body' or 'title' (a notice whose anchor was not found)
        text         TEXT,               -- a NOTICE's own text; a regulation's lives at url
        first_seen   TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ca_gazette_items_issue ON ca_gazette_items (issue_key)",
    "CREATE INDEX IF NOT EXISTS ca_speeches_sitting ON ca_speeches (sitting_key)",
    "CREATE INDEX IF NOT EXISTS ca_speeches_person ON ca_speeches (person_id)",
    "CREATE INDEX IF NOT EXISTS ca_petitions_presented ON ca_petitions (presented_number)",
    "CREATE INDEX IF NOT EXISTS ca_divisions_date ON ca_divisions (date)",
    "CREATE INDEX IF NOT EXISTS ca_votes_person ON ca_votes (person_id)",
)


# Columns added after a table first shipped. CREATE TABLE IF NOT EXISTS
# never alters an existing table, so a store made before the column existed
# would silently lack it; each is added here if missing.
ADDED_COLUMNS = (
    ("ca_divisions", "abstentions", "INTEGER"),   # the Senate records them; the House does not
)


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    for table, column, kind in ADDED_COLUMNS:
        have = {r[1] for r in conn.execute("PRAGMA table_info({0})".format(table))}
        if column not in have:
            conn.execute("ALTER TABLE {0} ADD COLUMN {1} {2}".format(table, column, kind))
    conn.commit()
    return conn
