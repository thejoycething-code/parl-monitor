"""Tables for Australia's states and territories (13 October 2026): the six
state parliaments' and two territory assemblies' bills (with their stage),
the Acts they made, the divisions where a source publishes them, and members.

See docs/australia-states-scope.md for what was measured and why. The schema
follows src/es_regions_store.py: its own module, idempotent statements,
created by db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/au_states.py writes these tables,
and nothing here touches the Federal Parliament's au_* tables.

KEYS. Every row is keyed '<state>:<the source's own identifier>', never a
title, with one exception the scope doc explains: Tasmania's reachable bill
list (the Parliament's own search engine) publishes titles only, so a
Tasmanian bill is keyed 'tas:<year>:<the title folded to a slug>'.

  * aus_bills: one row per bill (or, for South Australia, motion: `kind`
    says which) that a state's source lists. `stage` is the source's own
    words ('Council - second reading', 'Adj 2nd Reading', 'Third Reading');
    `status` is one of STATUSES, derived from it. The lists are snapshots,
    re-read each week: a bill is new when first seen, and a source's FIRST
    read lists everything already before Parliament, so those rows are
    marked `seed` and count as new only by their own `introduced` date.
  * aus_bill_events: one row per stage a bill reached, as dated as the source
    allows: New South Wales from the Hansard (the sitting day the stage was
    taken); elsewhere the day a weekly read first saw the stage change.
  * aus_acts: Acts as made, for the states whose bill lists are out of reach
    or carry no stage (Western Australia, Tasmania, the ACT; Queensland's
    Acts settle its bills' passage). An Act whose title matches a stored
    bill marks that bill assented (`act_key`).
  * aus_divisions and aus_votes: New South Wales (its Hansard API publishes
    every division with each member's ID) and, from 13 October 2026,
    Victoria, South Australia, Tasmania and the ACT (their Votes and
    Proceedings, Minutes or Hansard records: names, no IDs, so those
    members are keyed '<state>:name:<the name folded>'; `teller` is set). A
    division takes its bills' areas; `own_areas` keeps its own words' match
    apart, as the federal au_divisions does.
  * aus_members: New South Wales (every speaker the Hansard names, with the
    Parliament's member ID) and South Australia (the session's members from
    the Legislative Tracking system), and every member a Victorian, South
    Australian, Tasmanian or ACT division names ('<state>:name:...').
    Names and electorates only; never a spouse, never a private detail.
  * aus_hansard_days: each sitting day's record read, per state and House
    (NSW's contents documents; the other states' Votes and Proceedings,
    Minutes or Hansard files, `toc_id` their ID, `topics` their divisions).
  * aus_reads: one row per source read, ok or not.

AREAS. NULL means unclassified, '[]' classified and on nobody's ground. The
English taxonomy (config/taxonomy.yaml) is applied to every title: all eight
publish in English.
"""

from __future__ import annotations

import json

# The eight, by the code this layer uses, in the scope doc's ranking
# (population and activity on our ground, then source quality).
STATES = {
    "nsw": "New South Wales",
    "vic": "Victoria",
    "qld": "Queensland",
    "wa": "Western Australia",
    "sa": "South Australia",
    "tas": "Tasmania",
    "act": "Australian Capital Territory",
    "nt": "Northern Territory",
}

SHORT = {"nsw": "NSW", "vic": "Vic", "qld": "Qld", "wa": "WA", "sa": "SA",
         "tas": "Tas", "act": "ACT", "nt": "NT"}

PARLIAMENTS = {
    "nsw": "Parliament of New South Wales",
    "vic": "Parliament of Victoria",
    "qld": "Queensland Parliament",
    "wa": "Parliament of Western Australia",
    "sa": "Parliament of South Australia",
    "tas": "Parliament of Tasmania",
    "act": "ACT Legislative Assembly",
    "nt": "Legislative Assembly of the Northern Territory",
}

# 'before' Parliament; 'passed' both Houses, awaiting assent; 'assented'
# (an Act); 'defeated', 'withdrawn', 'lapsed'; 'unknown' when the source
# gives no stage at all (Tasmania's titles).
STATUSES = ("before", "passed", "assented", "defeated", "withdrawn", "lapsed", "unknown")

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS aus_bills (
        bill_key      TEXT PRIMARY KEY,   -- 'nsw:18897', 'vic:22713', 'sa:5622'
        state         TEXT NOT NULL,      -- see STATES
        ext_id        TEXT NOT NULL,      -- the source's own identifier
        kind          TEXT,               -- 'bill', 'motion' (SA), 'private bill' where the source says
        title         TEXT,
        chamber       TEXT,               -- house of origin, the source's words, when given
        introduced    TEXT,               -- ISO date, when the source gives one
        introduced_by TEXT,
        stage         TEXT,               -- the source's own words for where it stands
        stage_date    TEXT,               -- ISO date of that stage, as dated as the source allows
        status        TEXT,               -- see STATUSES
        act_key       TEXT,               -- aus_acts row it became, when matched
        url           TEXT,
        areas         TEXT,               -- JSON list, NULL = unclassified
        matched_terms TEXT,
        tier          INTEGER,
        first_seen    TEXT,
        last_seen     TEXT,
        seed          INTEGER             -- 1: listed on the source's FIRST read
    )""",
    """CREATE TABLE IF NOT EXISTS aus_bill_events (
        bill_key  TEXT NOT NULL,
        date      TEXT NOT NULL,          -- ISO date
        chamber   TEXT NOT NULL DEFAULT '',
        stage     TEXT NOT NULL,          -- the source's words
        source    TEXT,                   -- 'hansard' (dated by the sitting) or 'list' (dated by our read)
        PRIMARY KEY (bill_key, date, chamber, stage)
    )""",
    """CREATE TABLE IF NOT EXISTS aus_acts (
        act_key       TEXT PRIMARY KEY,   -- 'wa:A147533', 'tas:act-2026-018', 'qld:act-2026-001'
        state         TEXT NOT NULL,
        title         TEXT,
        made          TEXT,               -- ISO date published or assented, the source's
        number        TEXT,               -- 'No. 18 of 2026' where given
        url           TEXT,
        bill_key      TEXT,               -- the aus_bills row it settles, when matched
        areas         TEXT,
        matched_terms TEXT,
        tier          INTEGER,
        first_seen    TEXT,
        last_seen     TEXT,
        seed          INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS aus_divisions (
        division_key  TEXT PRIMARY KEY,   -- 'nsw:2026-09-24:la:3' (the day's third division in that House)
        state         TEXT NOT NULL,
        chamber       TEXT NOT NULL,      -- 'Legislative Assembly', 'Legislative Council'
        date          TEXT NOT NULL,
        topic_uid     TEXT,               -- the Hansard fragment it sits in
        heading       TEXT,               -- the topic's heading (bill titles or the debate's name)
        stage         TEXT,               -- the subproceeding ('Second Reading Debate')
        bill_keys     TEXT,               -- JSON list of aus_bills keys
        question      TEXT,               -- 'The question is that ...', from the fragment (on our ground only)
        result        TEXT,               -- 'Motion negatived.', from the fragment
        ayes          INTEGER,
        noes          INTEGER,
        pairs         INTEGER,
        url           TEXT,
        areas         TEXT,               -- own areas and the bills' areas
        own_areas     TEXT,               -- its own words' match only
        matched_terms TEXT,
        fragment_read TEXT,               -- ISO date the fragment was read (NULL: not yet)
        first_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS aus_votes (
        division_key TEXT NOT NULL,
        member_key   TEXT NOT NULL,       -- 'nsw:2270'
        vote         TEXT NOT NULL,       -- 'aye', 'no', 'pair'
        teller       INTEGER,
        PRIMARY KEY (division_key, member_key)
    ) WITHOUT ROWID""",
    """CREATE TABLE IF NOT EXISTS aus_members (
        member_key  TEXT PRIMARY KEY,     -- 'nsw:2270', 'sa:7340'
        state       TEXT NOT NULL,
        name        TEXT,
        electorate  TEXT,
        chamber     TEXT,
        first_seen  TEXT,
        last_seen   TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS aus_hansard_days (
        state    TEXT NOT NULL,
        date     TEXT NOT NULL,
        chamber  TEXT NOT NULL,
        toc_id   TEXT,
        draft    INTEGER,
        read_on  TEXT,
        topics   INTEGER,
        PRIMARY KEY (state, date, chamber)
    )""",
    """CREATE TABLE IF NOT EXISTS aus_reads (
        source      TEXT PRIMARY KEY,     -- 'nsw', 'vic', 'qld-bills', 'qld-acts', ...
        last_seen   TEXT,                 -- ISO date of the last read, ok or not (status says)
        items       INTEGER,
        status      TEXT                  -- 'ok', or the last failure, short
    )""",
    "CREATE INDEX IF NOT EXISTS aus_bills_state ON aus_bills (state, first_seen)",
    "CREATE INDEX IF NOT EXISTS aus_events_date ON aus_bill_events (date)",
    "CREATE INDEX IF NOT EXISTS aus_divisions_date ON aus_divisions (state, date)",
    "CREATE INDEX IF NOT EXISTS aus_votes_member ON aus_votes (member_key)",
)

TABLES = ("aus_bills", "aus_bill_events", "aus_acts", "aus_divisions", "aus_votes",
          "aus_members", "aus_hansard_days", "aus_reads")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
