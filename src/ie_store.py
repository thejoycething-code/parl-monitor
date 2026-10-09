"""Tables for the Ireland (Oireachtas) monitor (phase 1, 9 October 2026):
members with their party spells, bills with their sponsors and the debate
sections that carry them, divisions in the Dail, the Seanad and committee,
and every member's vote.

See docs/ireland-scope.md for what was measured and why. The schema follows
the US precedent (src/us_store.py): its own module, idempotent statements,
created by db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/ie_*.py writes these tables,
and nothing here touches another jurisdiction's table.

KEYS. A member is the Oireachtas memberCode ('Shay-Brennan.D.2024-11-29'),
the identifier every Oireachtas dataset shares (votes, sponsors, questions,
debates). A bill is '<year>/<number>', '2026/10': the Oireachtas numbers
bills per calendar year across both Houses, and the pair is unique across
all 6,048 bills the API holds (measured 9 October 2026). A division is its
path in the Oireachtas URI, 'dail/34/2026-10-06/vote_214' (committee:
'committee/<committee>/<date>/vote_N'): vote IDs restart, so the bare
'vote_214' names 2 or more divisions (220 distinct IDs across 429 Dail votes).

PARTY IS STORED PER VOTE, as in Canada and the US. The Oireachtas vote
record carries no party at all, so `ie_votes.party` is derived from the
member's party spell (ie_member_parties) covering the vote's date in that
House. A vote with no covering spell stores NULL and records a gap; it is
never filled with the member's latest party.

A BILL LAPSES WITH ITS HOUSE, AND THE API STILL CALLS IT 'CURRENT'. Every
bill lapses when the Dail is dissolved (Seanad bills when that Seanad ends),
and a lapsed bill can be restored to the order paper by motion in the new
House at the stage it reached. On 9 October 2026, 102 of the 266 bills the
API marks 'Current' had lapsed and never been restored. So the board reads
`ie_bills.alive`, derived in tools/ie_rollcalls.py, never `status`.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS ie_members (
        member_code  TEXT PRIMARY KEY,   -- 'Shay-Brennan.D.2024-11-29'
        name         TEXT,
        first_name   TEXT,
        last_name    TEXT,
        house        TEXT,               -- 'dail' / 'seanad', latest membership
        house_no     INTEGER,            -- 34 / 27
        party        TEXT,               -- latest spell; see ie_votes.party
        represents   TEXT,               -- constituency (Dail) or panel (Seanad)
        start_date   TEXT,               -- latest membership's start
        end_date     TEXT,               -- NULL while sitting
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ie_member_parties (
        member_code  TEXT NOT NULL,
        house_key    TEXT NOT NULL,      -- 'dail/34', 'seanad/27'
        party        TEXT NOT NULL,      -- 'Fianna Fáil', as the Oireachtas prints it
        start_date   TEXT NOT NULL,
        end_date     TEXT,               -- NULL: the spell is open
        PRIMARY KEY (member_code, house_key, party, start_date)
    )""",
    """CREATE TABLE IF NOT EXISTS ie_bills (
        bill_key     TEXT PRIMARY KEY,   -- '2026/10'
        year         INTEGER NOT NULL,
        number       INTEGER NOT NULL,
        title        TEXT,               -- shortTitleEn, the title it carries NOW
        title_ga     TEXT,               -- shortTitleGa
        long_title   TEXT,               -- longTitleEn, tags stripped
        source       TEXT,               -- 'Government' / 'Private Member'
        bill_type    TEXT,               -- 'Public' / 'Private'
        origin_house TEXT,               -- 'dail' / 'seanad'
        status       TEXT,               -- the API's word; NOT a liveness test
        last_stage   TEXT,               -- 'Second Stage'
        last_stage_house TEXT,           -- 'dail/34'
        last_stage_at TEXT,
        lapsed_at    TEXT,               -- latest 'Bill Lapsed' event
        restored_at  TEXT,               -- latest 'Bill Restored' event
        alive        INTEGER,            -- derived: see the module docstring
        act          TEXT,               -- 'Act 32 of 2026' once enacted
        act_title    TEXT,
        last_updated TEXT,               -- the record's own lastUpdated
        url          TEXT,
        areas        TEXT,               -- JSON list; taxonomy + watchlist-ie by key
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ie_sponsors (
        bill_key     TEXT NOT NULL,
        sponsor      TEXT NOT NULL,      -- memberCode, or the office for a Government bill
        member_code  TEXT,               -- NULL for a Government bill sponsored by office
        name         TEXT,
        office       TEXT,               -- 'Minister for Health' (Government bills)
        is_primary   INTEGER,
        PRIMARY KEY (bill_key, sponsor)
    )""",
    """CREATE TABLE IF NOT EXISTS ie_bill_debates (
        debate_uri   TEXT NOT NULL,      -- '.../debateRecord/dail/2026-09-22/debate/main'
        debate_section TEXT NOT NULL,    -- 'dbsect_10'
        bill_key     TEXT NOT NULL,
        date         TEXT,
        title        TEXT,               -- 'X Bill 2026: Second Stage'
        PRIMARY KEY (debate_uri, debate_section, bill_key)
    )""",
    """CREATE TABLE IF NOT EXISTS ie_divisions (
        division_key TEXT PRIMARY KEY,   -- 'dail/34/2026-10-06/vote_214'
        chamber      TEXT NOT NULL,      -- 'dail' / 'seanad' / 'committee'
        house_key    TEXT,               -- 'dail/34'; the parent House for a committee
        committee    TEXT,               -- committee name, NULL in plenary
        date         TEXT,
        vote_id      TEXT,               -- 'vote_214' (restarts; not a key)
        debate_title TEXT,               -- 'X Bill 2025: Report Stage (Resumed)'
        debate_uri   TEXT,
        debate_section TEXT,
        subject      TEXT,               -- 'Amendment put:' -- usually without the amendment
        outcome      TEXT,               -- the Oireachtas's own word, never derived
        ta           INTEGER,            -- Tá (yes)
        nil          INTEGER,            -- Níl (no)
        staon        INTEGER,            -- Staon (abstain)
        tellers      TEXT,
        vote_note    TEXT,
        bill_key     TEXT,               -- joined by debate section ID, or NULL
        debate_bill  TEXT,               -- the bill the debate title names, as printed: text, not a key
        own_areas    TEXT,               -- JSON: matched on the division's OWN text
        areas        TEXT,               -- JSON: own + the bill's
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ie_votes (
        division_key TEXT NOT NULL,
        member_code  TEXT NOT NULL,
        position     TEXT,               -- 'Yes' (Tá) / 'No' (Níl) / 'Abstain' (Staon)
        party        TEXT,               -- AT THE VOTE, from ie_member_parties; NULL if none covers it
        PRIMARY KEY (division_key, member_code)
    )""",
    "CREATE INDEX IF NOT EXISTS ie_divisions_bill ON ie_divisions (bill_key)",
    "CREATE INDEX IF NOT EXISTS ie_votes_member ON ie_votes (member_code)",
    "CREATE INDEX IF NOT EXISTS ie_bill_debates_bill ON ie_bill_debates (bill_key)",
)

TABLES = ("ie_members", "ie_member_parties", "ie_bills", "ie_sponsors",
          "ie_bill_debates", "ie_divisions", "ie_votes")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- the Ireland watchlist, applied by bill KEY ---------------------------
#
# Applied by key for the same reason as the US list: a title term would
# claim every bill whose title shares the words, and Irish bills change
# their title on the way through (the Incitement to Violence or Hatred and
# Hate Offences Bill 2022 is stored today as the Criminal Justice (Hate
# Offences) Bill 2022). A key is exact and survives a renaming.

_WATCH = {}


def watchlist(path=None):
    """{bill_key: (areas, why)} from config/watchlist-ie.yaml."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-ie.yaml")
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {str(k): (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("bills") or {}).items()}
    return _WATCH[path]


def add_watch_areas(res, bill_key, path=None):
    """Union a watched bill's areas into a FilterResult, in place, and say so
    in watchlist_hits so the stored row shows where the area came from."""
    hit = watchlist(path).get(bill_key)
    if not hit:
        return res
    areas, _why = hit
    res.issue_areas = sorted(set(res.issue_areas or []) | set(areas))
    res.watchlist_hits = list(res.watchlist_hits or []) + ["watch:" + bill_key]
    if res.tier is None:
        res.tier = 2
    return res


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
