"""Tables for the Australian Federal Parliament monitor (phase 1, 9 October
2026): members, bills, House and Senate divisions and every member's vote.

See docs/australia-scope.md for what was measured and why. The schema follows
the US precedent (src/us_store.py): its own module, idempotent statements,
created by db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/au_*.py writes these tables, and
nothing here touches another jurisdiction's table.

KEYS.
  * A bill is the Parliament's own bill ID, 'r7532' (introduced in the House)
    or 's1518' (introduced in the Senate). It is the ID ParlInfo, the Hansard
    and the Federal Register of Legislation all use. Titles are never keys:
    "Treasury Laws Amendment (2025 Measures No. 1) Bill" exists in every
    Parliament.
  * A member is the OpenAustralia PERSON ID ('10007'), the identity the
    division lists carry (through an office ID that resolves to a person).
    The APH's own PHID ('R36') is kept beside it where the Parliamentary
    Handbook gives exactly one match, never a guessed one.
  * A division is '<chamber>-<date>-<number>', 'senate-2026-09-17-8': each
    chamber numbers its divisions from 1 on every sitting day.

PARTY IS STORED PER VOTE, as in Canada and the US: `au_votes.party` is the
party of the office spell the division list names (OpenAustralia opens a new
office ID when a member changes party). `au_members.party` is only the latest.

A BILL LAPSES WITH ITS PARLIAMENT. When the House is dissolved for an
election every bill before either House lapses; it comes back, if at all,
under a new ID. Nothing in a bill's own record says so, so `au_bills.parliament`
is what a board reads, never `last_stage`.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS au_members (
        person_id    TEXT PRIMARY KEY,   -- OpenAustralia person ID: '10007'
        name         TEXT,
        party        TEXT,               -- latest seen; see au_votes.party
        house        TEXT,               -- 'house' / 'senate', latest office
        electorate   TEXT,               -- House division, or the senator's state
        phid         TEXT,               -- APH Parliamentary Handbook ID, only when unambiguous
        current      INTEGER,            -- 1 while an office is open
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS au_offices (
        office_id    TEXT PRIMARY KEY,   -- 'member/857', 'lord/100969' (OpenAustralia)
        person_id    TEXT NOT NULL,
        house        TEXT,
        party        TEXT,               -- the party for THIS spell (see role)
        role         TEXT,               -- 'PRES', 'DPRES', 'SPK', 'CWM': OpenAustralia
                                         -- opens a spell for the chair and writes the
                                         -- role where the party goes; party is then the
                                         -- person's last real party before it
        electorate   TEXT,
        from_date    TEXT,
        to_date      TEXT                -- '9999-12-31' while open
    )""",
    """CREATE TABLE IF NOT EXISTS au_bills (
        bill_id      TEXT PRIMARY KEY,   -- 'r7532' / 's1518'
        parliament   INTEGER,            -- 48: the Parliament it was first seen in
        origin       TEXT,               -- 'house' / 'senate', from the ID's prefix
        title        TEXT,               -- as the Hansard heading names it
        first_date   TEXT,               -- first sitting day the Hansard names it
        last_stage   TEXT,               -- 'Second Reading', 'Third Reading', ...
        last_stage_chamber TEXT,
        last_stage_date TEXT,
        act_id       TEXT,               -- Federal Register of Legislation: 'C2026A00005'
        act_name     TEXT,
        assent_date  TEXT,
        areas        TEXT,               -- JSON list; taxonomy + watchlist-au by key
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS au_divisions (
        division_key TEXT PRIMARY KEY,   -- 'senate-2026-09-17-8'
        chamber      TEXT NOT NULL,      -- 'house' / 'senate'
        parliament   INTEGER,
        date         TEXT NOT NULL,
        number       INTEGER NOT NULL,   -- the day's division number
        time         TEXT,
        major_heading TEXT,
        minor_heading TEXT,              -- 'Universities Accord (...) Bill 2026; Second Reading'
        bill_ids     TEXT,               -- JSON list: every bill tagged on the debate (cognates)
        question     TEXT,               -- the Chair's words: 'The question is that ...'
        motion       TEXT,               -- the nearest 'I move ...' before it, if any
        ayes         INTEGER,
        noes         INTEGER,
        pairs        INTEGER,
        own_areas    TEXT,               -- JSON: matched on the division's OWN text
        areas        TEXT,               -- JSON: own + every tagged bill's
        matched_terms TEXT,
        tier         INTEGER,
        source_url   TEXT,               -- the ParlInfo Hansard page
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS au_votes (
        division_key TEXT NOT NULL,
        person_id    TEXT NOT NULL,
        office_id    TEXT,
        position     TEXT,               -- 'Aye' / 'No' / 'Paired' (side not published)
        party        TEXT,               -- AT THE VOTE: the office spell's party
        electorate   TEXT,
        PRIMARY KEY (division_key, person_id)
    )""",
    # One row per Hansard day file read, with the listing's own modified stamp:
    # OpenAustralia re-parses old days (all of June 2026 was rewritten on 25
    # August), so a file is re-read only when its stamp moves.
    """CREATE TABLE IF NOT EXISTS au_hansard_files (
        path         TEXT PRIMARY KEY,   -- 'senate_debates/2026-09-17.xml'
        chamber      TEXT,
        date         TEXT,
        listed_modified TEXT,            -- as the directory listing gives it
        read_at      TEXT,
        divisions    INTEGER
    )""",
    # --- the week ahead (tools/au_schedule.py, 9 October 2026) ---------------
    # The APH sitting calendar, Notice Papers and Daily Programs are on
    # aph.gov.au, which refuses our collectors. What answers is the Federal
    # Register of Legislation: every legislative instrument open for
    # disallowance, with the LAST DAY each House can disallow it. That day is
    # the fifteenth sitting day after tabling, counted on the Register's own
    # copy of the sitting calendar, so every such date still ahead is a day
    # that House is due to sit (au_sitting_days).
    """CREATE TABLE IF NOT EXISTS au_instruments (
        title_id     TEXT PRIMARY KEY,   -- Register title ID: 'F2026L00968'
        name         TEXT,
        collection   TEXT,               -- 'LegislativeInstrument'
        making_date  TEXT,
        registered_at TEXT,
        last_day_house  TEXT,            -- last day the House can disallow; NULL when the
        last_day_senate TEXT,            -- Register gives none (9999-12-31: not yet tabled
                                         -- there, or a disallowance motion is pending)
        enabling_acts TEXT,              -- JSON: Register IDs of the Acts it is made under
        bill_id      TEXT,               -- the bill of this Parliament whose Act enables it
                                         -- (au_bills.act_id), when one does
        own_areas    TEXT,               -- JSON: matched on the instrument's own name
        areas        TEXT,               -- JSON: own + the enabling Act's (watchlist-au acts:)
                                         -- + the enabling bill's
        areas_from   TEXT,               -- 'own' / 'act' / 'bill'
        matched_terms TEXT,
        tier         INTEGER,
        scrutiny     TEXT,               -- JSON: tabling and disallowance motion events;
                                         -- read only for instruments on our ground
        open         INTEGER,            -- 1 while the Register lists it open for disallowance
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS au_sitting_days (
        chamber      TEXT NOT NULL,      -- 'house' / 'senate'
        date         TEXT NOT NULL,
        source       TEXT,               -- 'frl-disallowance': a last day for disallowance
        instruments  INTEGER,            -- how many open instruments' clocks end that day
        first_seen   TEXT,
        last_seen    TEXT,
        PRIMARY KEY (chamber, date)
    )""",
    # The Parliamentary Handbook's own record of each Parliament: a
    # dissolution date appearing here is the one signal that every bill
    # before Parliament has lapsed.
    """CREATE TABLE IF NOT EXISTS au_parliaments (
        parliament   INTEGER PRIMARY KEY,
        name         TEXT,
        election     TEXT,
        opening      TEXT,
        dissolution  TEXT,               -- NULL while the Parliament stands
        ended        TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    # --- debates (tools/au_debates.py, 9 October 2026) ------------------------
    # Speeches on our ground from the same OpenAustralia day files the
    # divisions come from. Only speeches on our ground are stored, with an
    # excerpt of at most 400 characters, never the text.
    """CREATE TABLE IF NOT EXISTS au_speeches (
        speech_key   TEXT PRIMARY KEY,   -- 'senate/2026-09-16.10.1': chamber + OpenAustralia
                                         -- speech ID of the speech's first segment
        chamber      TEXT NOT NULL,      -- 'house' / 'senate'
        parliament   INTEGER,
        date         TEXT NOT NULL,
        time         TEXT,
        person_id    TEXT,               -- OpenAustralia person ID (au_members)
        office_id    TEXT,
        phid         TEXT,               -- APH Handbook ID, when au_members has one
        name         TEXT,               -- as the Hansard names the speaker
        party        TEXT,               -- AT THE TIME: the office spell's party
        kind         TEXT,               -- 'speech' / 'motion' (moved: 'I move') /
                                         -- 'notice' (under the NOTICES heading)
        major_heading TEXT,
        minor_heading TEXT,
        bill_ids     TEXT,               -- JSON: bills tagged on the debate (it is ON them)
        words        INTEGER,
        own_areas    TEXT,               -- JSON: the speaker's own words (and the heading,
                                         -- for a speech of MIN_WORDS or more)
        areas        TEXT,               -- JSON: own + a bill's, in the narrow cases only
        areas_from   TEXT,               -- 'own' / 'watch' / 'bill'
        matched_terms TEXT,
        tier         INTEGER,
        excerpt      TEXT,               -- at most 400 characters
        url          TEXT,               -- the OpenAustralia page for the speech
        source_url   TEXT,               -- the ParlInfo Hansard page the parse names
        triage_score INTEGER,
        why_it_matters TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    # One row per day file read for debates, with the listing's stamp (a
    # re-parsed day is read again) and what came of it.
    """CREATE TABLE IF NOT EXISTS au_debate_days (
        path         TEXT PRIMARY KEY,   -- 'senate_debates/2026-09-16.xml'
        chamber      TEXT,
        date         TEXT,
        listed_modified TEXT,
        read_at      TEXT,
        speeches     INTEGER,            -- speeches read (interjections and unknown speakers aside)
        ours         INTEGER,            -- of those, stored as on our ground
        unresolved   INTEGER,            -- segments whose speaker resolved to no person
        last_seen    TEXT                -- re-stamped every run while the listing names it
    )""",
    "CREATE INDEX IF NOT EXISTS au_speeches_date ON au_speeches (date)",
    "CREATE INDEX IF NOT EXISTS au_votes_member ON au_votes (person_id)",
    "CREATE INDEX IF NOT EXISTS au_offices_person ON au_offices (person_id)",
)

TABLES = ("au_members", "au_offices", "au_bills", "au_divisions", "au_votes",
          "au_hansard_files", "au_instruments", "au_sitting_days", "au_parliaments",
          "au_speeches", "au_debate_days")


# The judge's score and why-line (tools/au_triage.py), added after the first
# live run (9 October 2026). Scored once, ever, as every judge here is.
ADDED_COLUMNS = (
    ("au_bills", "triage_score", "INTEGER"),
    ("au_bills", "why_it_matters", "TEXT"),
    ("au_divisions", "triage_score", "INTEGER"),
    ("au_divisions", "why_it_matters", "TEXT"),
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


# --- the Australian watchlist, applied by bill KEY ---------------------------
#
# As in the US: a key is exact, a title term is not. "Sex Discrimination
# Amendment" names a dozen bills a Parliament, most of them about something
# else; the one that matters is a bill ID.

_WATCH = {}


def watchlist(path=None):
    """{bill_id: (areas, why)} from config/watchlist-au.yaml."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-au.yaml")
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {k: (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("bills") or {}).items()}
    return _WATCH[path]


_ACTS = {}


def act_watchlist(path=None):
    """{Register title ID: (areas, why)} from the acts: section of
    config/watchlist-au.yaml: principal Acts whose instruments are ours."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-au.yaml")
    if path not in _ACTS:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _ACTS[path] = {k: (list(v.get("areas") or []), v.get("why"))
                       for k, v in (raw.get("acts") or {}).items()}
    return _ACTS[path]


def add_watch_areas(res, bill_id, path=None):
    """Union a watched bill's areas into a FilterResult, in place, and say so
    in watchlist_hits so the stored row shows where the area came from."""
    hit = watchlist(path).get(bill_id)
    if not hit:
        return res
    areas, _why = hit
    res.issue_areas = sorted(set(res.issue_areas or []) | set(areas))
    res.watchlist_hits = list(res.watchlist_hits or []) + ["watch:" + bill_id]
    if res.tier is None:
        res.tier = 2
    return res


def dumps(values):
    return json.dumps(values or [])
