"""Tables for the fifty state legislatures (phase 4, 9 October 2026), from
Open States (tools/us_states.py). Every table is prefixed `uss_`.

See docs/us-states-scope.md for what was measured and why. The schema
follows src/us_store.py: its own module, idempotent statements, created by
db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/us_states.py writes these
tables (the judge writes only triage_score and why_it_matters), and
nothing here touches another jurisdiction's table.

KEYS. A bill is Open States' own ID, 'ocd-bill/<uuid>', which never
changes. Beside it sits a readable key, '<ST>/<session>/<identifier>' with
the identifier's spaces removed ('TX/89R/HB229'), which is what a person
types into config/watchlist-us-states.yaml. Never a title: state titles
repeat ('relating to education') and a bill number restarts every session.
A vote is 'ocd-vote/<uuid>', a person 'ocd-person/<uuid>'.

WHAT IS STORED. Only bills the classifier puts on any area (migration
included, as us_bills does; the edition hides it), with their actions,
sponsors, votes and EVERY legislator's position on each vote. The rest is
counted per session in uss_sessions, never stored: the most recent session
of the fifty is 209,743 bills with 7.6 million recorded positions, which
would take the store past its 2 GB release-asset ceiling (it was 963 MB on
9 October 2026). A taxonomy change that widens the net is applied by
re-reading the bulk files (tools/us_states.py --full), not from the store.
"""

from __future__ import annotations

import json
import os
import re

SCHEMA = (
    # One row per legislative session Open States lists for a state, with
    # what was last read of it. read_zip_updated is the bulk file's own
    # generation stamp at the time we read it: a later stamp means the file
    # has changed. data_through is how far the store is good for: the day
    # before the bulk file's stamp after a bulk read (the nightly file lags
    # the scrapers by about a day), the run date after an API read.
    """CREATE TABLE IF NOT EXISTS uss_sessions (
        state        TEXT NOT NULL,      -- 'tx'
        session      TEXT NOT NULL,      -- Open States identifier: '89R', '2025-2026'
        name         TEXT,               -- '89th Legislature (2025)'
        classification TEXT,             -- 'primary' / 'special' / '' as Open States gives it
        start_date   TEXT,               -- as listed; NOT reliable (see the scope doc)
        end_date     TEXT,
        zip_url      TEXT,               -- the per-session CSV bulk file
        zip_updated  TEXT,               -- its generation stamp, as listed
        read_zip_updated TEXT,           -- the stamp of the file we last read
        read_via     TEXT,               -- 'bulk' / 'api'
        data_through TEXT,               -- ISO date the stored rows are good to
        bills_read   INTEGER,            -- bills in the session at the last full read
        bills_ours   INTEGER,            -- of those, on any area
        read_at      TEXT,               -- when we last read anything of it
        first_seen   TEXT,
        last_seen    TEXT,
        PRIMARY KEY (state, session)
    )""",
    """CREATE TABLE IF NOT EXISTS uss_bills (
        bill_id      TEXT PRIMARY KEY,   -- 'ocd-bill/<uuid>'
        bill_key     TEXT NOT NULL,      -- 'TX/89R/HB229'
        state        TEXT NOT NULL,
        session      TEXT NOT NULL,
        identifier   TEXT NOT NULL,      -- as Open States prints it: 'HB 229'
        title        TEXT,
        classification TEXT,             -- JSON list: ['bill'], ['resolution'], ...
        subjects     TEXT,               -- JSON list (many states give none)
        abstract     TEXT,               -- joined abstracts (many states give none)
        chamber      TEXT,               -- of origin: 'lower' / 'upper' / 'legislature'
        url          TEXT,               -- the state's own page, where Open States lists one
        introduced_at TEXT,              -- first action's date
        latest_action TEXT,
        latest_action_at TEXT,
        passed_lower_at TEXT,            -- first passage action in each chamber
        passed_upper_at TEXT,
        law_at       TEXT,               -- 'became-law' or 'executive-signature'
        vetoed_at    TEXT,
        sponsor      TEXT,               -- the first primary sponsor's name
        sponsors     INTEGER,            -- sponsorships of every kind
        areas        TEXT,               -- JSON list; taxonomy + watchlist-us-states by key
        matched_terms TEXT,
        tier         INTEGER,
        triage_score INTEGER,
        why_it_matters TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS uss_actions (
        bill_id      TEXT NOT NULL,
        ord          INTEGER NOT NULL,   -- Open States' own order within the bill
        date         TEXT,               -- ISO date
        description  TEXT,
        classification TEXT,             -- JSON list: ['passage'], ['executive-signature'], ...
        chamber      TEXT,               -- 'lower' / 'upper' / 'executive' / 'legislature'
        PRIMARY KEY (bill_id, ord)
    )""",
    """CREATE TABLE IF NOT EXISTS uss_sponsors (
        bill_id      TEXT NOT NULL,
        seq          INTEGER NOT NULL,
        name         TEXT,
        person_id    TEXT,               -- 'ocd-person/<uuid>', or NULL: never guessed
        is_primary   INTEGER,
        classification TEXT,             -- 'primary' / 'cosponsor' / ...
        PRIMARY KEY (bill_id, seq)
    )""",
    """CREATE TABLE IF NOT EXISTS uss_votes (
        vote_id      TEXT PRIMARY KEY,   -- 'ocd-vote/<uuid>'
        bill_id      TEXT NOT NULL,
        state        TEXT NOT NULL,
        session      TEXT,
        date         TEXT,               -- ISO date
        motion       TEXT,
        motion_classification TEXT,      -- JSON list
        result       TEXT,               -- 'pass' / 'fail', as given
        chamber      TEXT,               -- 'lower' / 'upper' / 'legislature'
        yes          INTEGER,
        no           INTEGER,
        other        INTEGER,            -- every other option, summed
        url          TEXT,
        positions    INTEGER,            -- positions listed in uss_vote_people
        positions_ok INTEGER,            -- 1 when they account for yes + no + other
                                         -- exactly; 0 is stored, never "fixed"
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    # Every legislator's position. Rewritten whole each time its vote is
    # read. person_id is NULL where Open States could not link the name
    # (Colorado links 18%, New Hampshire 56%; see the scope doc): the name
    # is kept, never matched to a person by guesswork. Alaska and Missouri
    # give vote totals with no positions at all; Alabama, Arkansas, Kansas
    # and New Jersey give no votes.
    """CREATE TABLE IF NOT EXISTS uss_vote_people (
        vote_id      TEXT NOT NULL,
        seq          INTEGER NOT NULL,
        voter_name   TEXT,
        person_id    TEXT,
        option       TEXT,               -- 'yes' / 'no' / 'other' / 'absent' / 'excused' ...
        PRIMARY KEY (vote_id, seq)
    )""",
    # Sitting legislators, from the open per-state CSV
    # (data.openstates.org/people/current/<st>.csv, no key).
    """CREATE TABLE IF NOT EXISTS uss_people (
        person_id    TEXT PRIMARY KEY,
        state        TEXT NOT NULL,
        name         TEXT,
        party        TEXT,
        chamber      TEXT,               -- 'lower' / 'upper' / 'legislature'
        district     TEXT,
        given_name   TEXT,
        family_name  TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    # Keyed Open States requests per UTC day, across every run that shares
    # the store (the Mini, GitHub's backup, a hand run): the default tier
    # allows 250 a day and refuses the rest, so tools/us_states.py checks
    # this before each request and writes it before sending (see Ledger).
    """CREATE TABLE IF NOT EXISTS uss_api_ledger (
        day          TEXT PRIMARY KEY,   -- UTC date, as Open States counts
        requests     INTEGER NOT NULL,
        last_at      TEXT                -- UTC time of the latest request
    )""",
    "CREATE INDEX IF NOT EXISTS uss_bills_key ON uss_bills (bill_key)",
    "CREATE INDEX IF NOT EXISTS uss_bills_state ON uss_bills (state, session)",
    "CREATE INDEX IF NOT EXISTS uss_actions_date ON uss_actions (date)",
    "CREATE INDEX IF NOT EXISTS uss_votes_bill ON uss_votes (bill_id)",
    "CREATE INDEX IF NOT EXISTS uss_vote_people_person ON uss_vote_people (person_id)",
)

TABLES = ("uss_sessions", "uss_bills", "uss_actions", "uss_sponsors", "uss_votes",
          "uss_vote_people", "uss_people", "uss_api_ledger")

# The fifty, by postal code. DC and Puerto Rico are in Open States but not
# in the decision (Christopher, 9 October 2026: all 50 state legislatures).
STATES = {
    "al": "Alabama", "ak": "Alaska", "az": "Arizona", "ar": "Arkansas", "ca": "California",
    "co": "Colorado", "ct": "Connecticut", "de": "Delaware", "fl": "Florida", "ga": "Georgia",
    "hi": "Hawaii", "id": "Idaho", "il": "Illinois", "in": "Indiana", "ia": "Iowa",
    "ks": "Kansas", "ky": "Kentucky", "la": "Louisiana", "me": "Maine", "md": "Maryland",
    "ma": "Massachusetts", "mi": "Michigan", "mn": "Minnesota", "ms": "Mississippi",
    "mo": "Missouri", "mt": "Montana", "ne": "Nebraska", "nv": "Nevada", "nh": "New Hampshire",
    "nj": "New Jersey", "nm": "New Mexico", "ny": "New York", "nc": "North Carolina",
    "nd": "North Dakota", "oh": "Ohio", "ok": "Oklahoma", "or": "Oregon", "pa": "Pennsylvania",
    "ri": "Rhode Island", "sc": "South Carolina", "sd": "South Dakota", "tn": "Tennessee",
    "tx": "Texas", "ut": "Utah", "vt": "Vermont", "va": "Virginia", "wa": "Washington",
    "wv": "West Virginia", "wi": "Wisconsin", "wy": "Wyoming",
}


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


def state_of(jurisdiction_id):
    """'ocd-jurisdiction/country:us/state:tx/government' -> 'tx'."""
    hit = re.search(r"/state:([a-z]{2})/", jurisdiction_id or "")
    return hit.group(1) if hit else None


def bill_key(state, session, identifier):
    """('tx', '89R', 'HB 229') -> 'TX/89R/HB229'."""
    return "{0}/{1}/{2}".format(state.upper(), session, re.sub(r"\s+", "", identifier or ""))


# --- the watchlist, applied by bill KEY -------------------------------------

_WATCH = {}


def watchlist(path=None):
    """{bill_key: (areas, why)} from config/watchlist-us-states.yaml."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-us-states.yaml")
    if path not in _WATCH:
        raw = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {k: (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("bills") or {}).items()}
    return _WATCH[path]


def add_watch_areas(res, key, path=None):
    """Union a watched bill's areas into a FilterResult, in place, and say so
    in watchlist_hits so the stored row shows where the area came from."""
    hit = watchlist(path).get(key)
    if not hit:
        return res
    areas, _why = hit
    res.issue_areas = sorted(set(res.issue_areas or []) | set(areas))
    res.watchlist_hits = list(res.watchlist_hits or []) + ["watch:" + key]
    if res.tier is None:
        res.tier = 2
    return res


def dumps(values):
    return json.dumps(values or [])
