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
  answer_areas TEXT,              -- areas from the MINISTER'S answer. SEPARATE
  answer_terms TEXT,              -- from `areas` on purpose: `areas` is the
  answer_shape TEXT,              -- MLA's evidence and feeds the 5CA, and a
                                  -- Minister's words are not the asker's
                                  -- position. answer_shape names the kind of
                                  -- refusal where there is one (see ni_answers).
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
-- Who tabled a motion. The 5CA's missing middle: NI had votes (which need a
-- human meaning line) and questions (activity, never direction) but nothing
-- between them. Sponsoring a motion is a chosen act of advancing a specific
-- text, which is why Westminster weights an EDM sponsored above one signed --
-- and `sequence` carries exactly that split, 1 being the proposer.
--
-- The motion list's MotionTablers string cannot replace this: no PersonId, so
-- no join to the roster, and its order after the first name is not the tabling
-- sequence.
CREATE TABLE IF NOT EXISTS ni_sponsors (
  doc_id TEXT NOT NULL,           -- the motion's DocumentID
  person_id TEXT NOT NULL,        -- joins to ni_members / ni_affiliations
  sequence INTEGER,               -- 1 = proposer, 2+ = co-signatory
  name TEXT, seat TEXT,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
  PRIMARY KEY (doc_id, person_id)
);
-- Committee agenda items, one row per SLOT in a meeting. The business diary
-- names the committee and the room; this names the subject being taken, which
-- is the difference between "the Health Committee meets on Thursday" and "the
-- Health Committee takes X on Thursday".
--
-- Keyed on (event_id, item_order), NOT item_id: one subject occupies several
-- slots, because a committee commonly runs an item in public and then again in
-- closed session. Keying on item_id collapsed the 20 August meeting's nine
-- slots to four and took the public/closed distinction with them.
CREATE TABLE IF NOT EXISTS ni_agenda (
  event_id TEXT NOT NULL,         -- joins to ni_items 'ni-diary:<event_id>'
  item_order INTEGER NOT NULL,
  item_id TEXT,                   -- the SUBJECT id; repeats across slots
  committee TEXT, business TEXT, item_type TEXT,
  session TEXT,                   -- 'Public, 10:00 AM - 10:05 AM'
  dated TEXT,
  areas TEXT, matched_terms TEXT,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
  PRIMARY KEY (event_id, item_order)
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
-- ============================= HOLYROOD ====================================
-- Scottish Parliament watching brief (2026-08-20). Same rules as ni_*: its own
-- tables, never `items`/`mp_events`, so it structurally cannot reach the Slack
-- digest. Unlike NI there is NO search API -- data.parliament.scot serves
-- whole-year dumps -- so every row of the fetched years is classified by the
-- taxonomy directly and NO sweep terms exist to go stale.
CREATE TABLE IF NOT EXISTS sp_items (
  id TEXT PRIMARY KEY,            -- 'sp-question:S6W-12345' | 'sp-motion:447623'
  kind TEXT NOT NULL,             -- question|motion
  reference TEXT,                 -- 'S6W-12345' event reference where present
  title TEXT,
  dated TEXT,                     -- SubmissionDateTime date part
  msp_id TEXT,                    -- PersonID; joins sp_members
  party TEXT,                     -- as carried ON THE ROW by the API itself
  areas TEXT,                     -- json list of OUR area numbers
  matched_terms TEXT,             -- json list, for taxonomy maintenance
  body TEXT,                      -- ItemText stored whole: the DB is the
                                  -- archive here, because the year dumps are
                                  -- not mirrored into data/raw (110MB of
                                  -- motions a week has no place in git; the
                                  -- API serves them canonically by year).
  answered TEXT,                  -- AnswerDate
  answer TEXT,                    -- AnswerText, stored ONLY for matched rows:
                                  -- classification runs on the QUESTION text,
                                  -- so unmatched rows keep enough to re-test
                                  -- a taxonomy change without carrying ~7MB a
                                  -- year of answers nobody will read.
  answered_by TEXT,               -- AnsweredByMSP id
  cross_party INTEGER,            -- CrossPartySupport flag on motions
  tier INTEGER,                   -- 1 = tier-1 match; 2 = tier-2 only. The
                                  -- monitor shows tier 1 and counts tier 2:
                                  -- Holyrood motion culture is congratulatory
                                  -- ("welcomes...", thousands a year), and the
                                  -- first pull filed a dental-charity
                                  -- fundraiser under assisted dying via the
                                  -- tier-2 term "hospice". Westminster gates
                                  -- tier 2 behind paid triage; the watching
                                  -- brief gates it behind this column.
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
);
-- All 416 people who have ever sat; IsCurrent marks the 129 sitting MSPs.
CREATE TABLE IF NOT EXISTS sp_members (
  person_id TEXT PRIMARY KEY,
  name TEXT, preferred_name TEXT, is_current INTEGER,
  party TEXT,                     -- current party, from the null-until range
  constituency TEXT,              -- Person.ConstituencyRegion off vote rows
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
);
-- Party membership AS DATE RANGES, straight from /api/memberparties -- unlike
-- NI, where party-as-at had to be reconstructed per date, Holyrood publishes
-- the ranges natively (ValidFromDate/ValidUntilDate, null until = current).
-- 976 rows total; a floor-crosser is two rows.
CREATE TABLE IF NOT EXISTS sp_affiliations (
  id TEXT PRIMARY KEY,            -- the API's own row ID
  person_id TEXT NOT NULL,
  party_id TEXT, party TEXT,
  valid_from TEXT, valid_until TEXT,   -- null valid_until = current
  captured_at TEXT NOT NULL
);
-- Holyrood divisions. Classification is an EXACT-KEY join: the reference
-- 'S7M-00469.5' is amendment 5 to motion S7M-00469, and BOTH are rows in the
-- motions dump with their own full text, already stored in sp_items. So a
-- division inherits areas from its own amendment's wording -- the thing NI
-- needed a Hansard parser for arrives here as a foreign key.
CREATE TABLE IF NOT EXISTS sp_divisions (
  key TEXT PRIMARY KEY,           -- 'm<MotionAgendaItemID>' or
                                  -- 'b<BackupAgendaItemID>': two Detail
                                  -- schemas coexist in the dump and 11 of 151
                                  -- divisions in 2026 carry only the second.
  reference TEXT,                 -- 'S7M-00469.5'
  title TEXT, dated TEXT, session TEXT,
  vote_for INTEGER, vote_against INTEGER, result TEXT,
  abstentions INTEGER,
  amendment_no TEXT,              -- bill amendments only, from the OR
  source TEXT,                    -- 'votesmotion' (per-MSP votes held) or
                                  -- 'official-report' (AGGREGATE ONLY: the OR
                                  -- prints no roll-call, so these rows can
                                  -- never place anyone -- record and context)
  item_id TEXT,                   -- sp_items id of the amendment/motion voted
  areas TEXT, matched_terms TEXT, tier INTEGER,   -- from that item's wording
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sp_votes (
  division_key TEXT NOT NULL,
  person_id TEXT NOT NULL,
  vote TEXT,                      -- Yes | No | Abstain | Not Voted: every MSP
                                  -- appears, so absence is data, not a gap
  party TEXT,                     -- stamped on the vote row by the API itself
  shares_party TEXT,              -- the API's own whip-agreement flag
  PRIMARY KEY (division_key, person_id)
);
-- Holyrood speech ledger: Official Report contributions that match the
-- taxonomy, passage-filtered like the Westminster ledger. Speeches are
-- ACTIVITY evidence in the SP 5CA -- there is no Claude stance scoring in a
-- watching brief, so a speech never places anyone; it shows engagement and
-- gives the campaigner a dated, quotable excerpt.
CREATE TABLE IF NOT EXISTS sp_events (
  key TEXT PRIMARY KEY,           -- 'orc<ContributionID>'
  person_id TEXT NOT NULL,
  dated TEXT, heading TEXT,
  areas TEXT, matched_terms TEXT,
  excerpt TEXT,                   -- the strongest-matching passage
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
);
-- Holyrood bills: identity from /api/bills, latest stage joined from
-- /api/BillStages. first_seen is the NEW-BILL flag: a bill absent last run
-- and present now is surfaced by the pull and the monitor.
CREATE TABLE IF NOT EXISTS sp_bills (
  bill_id TEXT PRIMARY KEY,
  reference TEXT, name TEXT, person_id TEXT,
  latest_stage TEXT, latest_stage_date TEXT,
  areas TEXT, matched_terms TEXT, tier INTEGER,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
);
-- Co-signatories of Holyrood motions, fetched per-id for tier-1 matched
-- motions only (the full-dump endpoint cannot be served; see holyrood.py).
CREATE TABLE IF NOT EXISTS sp_supports (
  motion_uid TEXT NOT NULL,       -- sp_items UniqueID (the sp-motion: suffix)
  person_id TEXT NOT NULL,
  lodged TEXT,
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (motion_uid, person_id)
);
-- ============================== SENEDD =====================================
-- Welsh Parliament watching brief, phase 1 (2026-08-21): written questions by
-- ID-walking record.senedd.wales (no data API exists; docs/api-notes.md).
-- Same rules as ni_*/sp_*: own tables, never items/mp_events, off Slack.
CREATE TABLE IF NOT EXISTS sd_items (
  id TEXT PRIMARY KEY,            -- 'sd-question:100032'
  kind TEXT NOT NULL,             -- question (phase 1)
  reference TEXT,                 -- 'WQ100032'
  member_name TEXT,               -- from the page; NO PARTY in phase 1 --
  constituency TEXT,              -- the party source (ModernGov) rejects our
                                  -- honest User-Agent, and spoofing a browser
                                  -- is a decision, not a default
  dated TEXT, welsh INTEGER,      -- tabled date; tabled-in-Welsh marker
  body TEXT,                      -- question text, stored whole (the archive)
  answered TEXT, answered_by TEXT,
  answer TEXT,                    -- kept only for matched rows (the sp rule)
  areas TEXT, matched_terms TEXT, tier INTEGER,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
);
-- Senedd roster from mySociety parlparse (the honest party source: the
-- Senedd's own party pages sit behind a WAF that rejects our User-Agent, and
-- parlparse is maintained, public and needs no games -- 96 members stamped
-- from the May 2026 expansion election).
CREATE TABLE IF NOT EXISTS sd_members (
  person_id TEXT PRIMARY KEY,     -- parlparse person id
  name TEXT, party TEXT, post TEXT,
  start_date TEXT, end_date TEXT, -- null end = sitting
  captured_at TEXT NOT NULL
);
-- Senedd plenary divisions from the undocumented XMLExport (found via
-- mySociety's scraper; docs/api-notes.md). Per-member votes, full chamber.
CREATE TABLE IF NOT EXISTS sd_divisions (
  key TEXT PRIMARY KEY,           -- the export's Contribution_ID
  meeting_id INTEGER, dated TEXT,
  title TEXT,                     -- Vote_Name_English: what was voted on
  total_for INTEGER, total_against INTEGER, total_abstain INTEGER,
  result TEXT,
  areas TEXT, matched_terms TEXT, tier INTEGER,  -- taxonomy over the title
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sd_votes (
  division_key TEXT NOT NULL,
  member_id TEXT NOT NULL,        -- the Record's own member id
  member_name TEXT,
  result TEXT,                    -- For | Against | Abstain
  PRIMARY KEY (division_key, member_id)
);
-- Senedd speech ledger: attributed plenary contributions matching the
-- taxonomy, passage-filtered. Activity evidence only -- the watching-brief
-- rule: no stance scoring, a speech never places, it gives a dated quotable
-- excerpt.
CREATE TABLE IF NOT EXISTS sd_events (
  key TEXT PRIMARY KEY,           -- 'sdc<Contribution_ID>'
  member_id TEXT NOT NULL, member_name TEXT,
  dated TEXT, heading TEXT,
  areas TEXT, matched_terms TEXT,
  excerpt TEXT,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
);
-- Senedd bill register: iids from the legislation pages plus any tracking
-- page surfacing in mgWhatsNew (new-bill discovery); stage parsed from the
-- tracking page's PROSE (the scotland.py pattern -- no status field exists).
CREATE TABLE IF NOT EXISTS sd_bills (
  iid INTEGER PRIMARY KEY,        -- ModernGov issue id
  title TEXT,
  latest_stage TEXT,              -- 'Stage 3' | 'Royal Assent' | 'Withdrawn or rejected' | 'Introduced'
  stage_date TEXT,                -- only Royal Assent carries a parseable date
  areas TEXT, matched_terms TEXT, -- taxonomy over the title
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dg_consultations (
  key TEXT PRIMARY KEY,           -- '<nation>:<url path>'
  nation TEXT NOT NULL,           -- 'scotland' | 'wales' | 'ni'
  title TEXT, url TEXT,
  summary TEXT,                   -- listing summary (Citizen Space) or topics (gov.wales)
  opened TEXT, closes TEXT,       -- ISO dates from the detail page; NULL = not parsed
  areas TEXT, matched_terms TEXT, tier INTEGER,
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
    "un_votes",
    "sp_items",
    "sp_members",
    "sp_affiliations",
    "sp_divisions",
    "sp_votes",
    "sp_events",
    "sp_bills",
    "sp_supports",
    "sd_items",
    "sd_members",
    "sd_divisions",
    "sd_votes",
    "sd_events",
    "sd_bills",
    "dg_consultations",
    "ni_items",
    "ni_members",
    "ni_affiliations",
    "ni_divisions",
    "ni_sponsors",
    "ni_agenda",
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
    # 30s was NOT enough on 2026-08-21: sp_pull held one transaction across
    # 10,588 motion inserts and starved the stance scorer past its patience,
    # twice. The real fix is batched commits in the bulk writers (done), but
    # the timeout is also raised so a future long writer degrades a
    # concurrent job to slow instead of dead.
    conn.execute("PRAGMA busy_timeout = 120000")
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
                       "department", "answered", "answer", "body",
                       "answer_areas", "answer_terms", "answer_shape"):
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
