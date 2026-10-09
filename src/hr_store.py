"""Tables for the Croatian Sabor monitor (phase 1, 9 October 2026): members,
agenda items, the recorded vote on each item and every member's position.

See docs/croatia-scope.md for what was measured and why. The schema follows
the US precedent (src/us_store.py): its own module, idempotent statements,
created by db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/hr_*.py writes these tables,
and nothing here touches another jurisdiction's table.

KEYS.
  * An agenda item is the Sabor's own `tid` (the fsm_id in its vote
    service). The same bill appears on several sessions' agendas (first
    reading in one, second in a later one, or carried over unheard), and
    each appearance is a new tid, so a tid is one appearance, not one bill.
  * A bill is '<saziv>/<number>': '11/328' for "P.Z.E. br. 328" of the 11th
    Sabor. PZ and PZE share ONE number sequence (350 numbers in the 11th
    Sabor, one of them printed with both markers), so the marker is stored
    beside the key, never in it. Numbers restart with each saziv.
  * A division is 'hr-<saziv>-<tid>': the vote service returns one vote
    per agenda item.
  * A member is the slug of their sabor.hr page, 'ackar-kresimir-11-saziv',
    the only identifier the vote service prints. It carries the saziv, so a
    member re-elected to the next Sabor is a new slug; that is the source's
    choice, kept rather than guessed across.

PARTY IS WHAT THE MEMBER LIST SAID WHEN THE VOTE WAS COLLECTED. The vote
service prints names and positions only, no party. `hr_votes.party_seen`
is the member's party from the list read in the same run, which is the
party at the vote for a weekly run and only approximately so for the
backfill. Named for what it is so nobody reads it as party-at-the-vote.

ABSENT MEMBERS ARE NOT LISTED. The service lists Za / Protiv / Suzdržan
only; a member with no row did not vote. Nothing is inferred for them.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS hr_members (
        slug         TEXT PRIMARY KEY,   -- 'ackar-kresimir-11-saziv'
        name         TEXT,               -- 'Ačkar, Krešimir', as printed
        party        TEXT,               -- latest seen: 'HDZ', 'SDP', 'Možemo!'
        constituency TEXT,               -- 'I. izborna jedinica'
        mandate      TEXT,               -- 'Aktivan' / 'U mirovanju' / 'Završen'
        saziv        INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS hr_items (
        tid          INTEGER PRIMARY KEY, -- the Sabor's agenda-appearance id
        tocka        INTEGER,            -- the item node ('t=' in its URL)
        parent       INTEGER,            -- grouping item (data-nadtocka), or NULL
        saziv        INTEGER NOT NULL,
        session_id   INTEGER,            -- the plenary session node
        session_no   TEXT,               -- '12' or '11-izvanredna'
        status_id    INTEGER,            -- 6 not debated, 7 in debate, 8 voted,
                                         -- 9 debate closed, 10 withdrawn
        title        TEXT,
        url          TEXT,
        bill_key     TEXT,               -- '11/328', or NULL for a non-bill
        bill_marker  TEXT,               -- 'PZ' / 'PZE' as printed
        vote_state   TEXT,               -- NULL unchecked, 'stored', 'none'
        areas        TEXT,               -- JSON list; taxonomy-hr + watchlist-hr
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS hr_divisions (
        division_key TEXT PRIMARY KEY,   -- 'hr-11-214596'
        tid          INTEGER NOT NULL,
        saziv        INTEGER NOT NULL,
        session_no   TEXT,
        voted_at     TEXT,               -- '2026-09-25T12:22', Zagreb local time
        title        TEXT,               -- the service's own title
        bill_key     TEXT,
        yes          INTEGER,            -- Za
        no           INTEGER,            -- Protiv
        abstain      INTEGER,            -- Suzdržan
        total        INTEGER,            -- members who voted
        areas        TEXT,
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS hr_votes (
        division_key TEXT NOT NULL,
        slug         TEXT NOT NULL,
        position     TEXT,               -- 'for' / 'against' / 'abstained'
        party_seen   TEXT,               -- see the module docstring
        PRIMARY KEY (division_key, slug)
    )""",
    "CREATE INDEX IF NOT EXISTS hr_items_bill ON hr_items (bill_key)",
    "CREATE INDEX IF NOT EXISTS hr_divisions_bill ON hr_divisions (bill_key)",
    "CREATE INDEX IF NOT EXISTS hr_votes_member ON hr_votes (slug)",
)

TABLES = ("hr_members", "hr_items", "hr_divisions", "hr_votes")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- the Croatian watchlist, applied by KEY ---------------------------------
#
# Keys, never titles: a bill key ('11/328') or an agenda appearance
# ('item:214596') for the many things the Sabor votes on that are not bills
# (declarations, decisions, reports). Croatian titles are long, upper-case
# and repeated across readings, so a title match would claim every reading
# of every amending act with a shared phrase.

_WATCH = {}

WATCHLIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "config", "watchlist-hr.yaml")


def watchlist(path=None):
    """{key: (areas, why)} from config/watchlist-hr.yaml."""
    import yaml
    path = path or WATCHLIST
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        entries = {}
        for section in ("bills", "items"):
            for k, v in (raw.get(section) or {}).items():
                key = str(k) if section == "bills" else "item:{0}".format(k)
                entries[key] = (list((v or {}).get("areas") or []), (v or {}).get("why"))
        _WATCH[path] = entries
    return _WATCH[path]


def watch_keys(tid, bill_key):
    keys = ["item:{0}".format(tid)]
    if bill_key:
        keys.insert(0, bill_key)
    return keys


def add_watch_areas(res, keys, path=None):
    """Union watched keys' areas into a FilterResult, in place, and say so in
    watchlist_hits so the stored row shows where the area came from."""
    wl = watchlist(path)
    for key in keys:
        hit = wl.get(key)
        if not hit:
            continue
        areas, _why = hit
        res.issue_areas = sorted(set(res.issue_areas or []) | set(areas))
        res.watchlist_hits = list(res.watchlist_hits or []) + ["watch:" + key]
        if res.tier is None:
            res.tier = 2
    return res


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
