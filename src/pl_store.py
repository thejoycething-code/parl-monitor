"""Tables for the Polish Sejm monitor (phase 1, 9 October 2026): deputies,
prints (druki), legislative processes, recorded votes and every deputy's
position.

See docs/poland-scope.md for what was measured and why. The schema follows
the US and Croatia precedent: its own module, idempotent statements, created
by db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/pl_*.py writes these tables, and
nothing here touches another jurisdiction's table.

KEYS (every one carries the Sejm term, because numbers restart each term).
  * A PROCESS is '<term>/<number>', '10/2110'. The Sejm numbers a legislative
    process by the print that opened it (druk nr 2110), and its own pages,
    the API and the ISAP/ELI records all use that number. Titles are never
    keys: "o zmianie ustawy - Kodeks karny" opens dozens of processes a term.
  * A PRINT is '<term>/<number>', '10/3080-A' (letters mark additional
    reports). pl_prints.process_key says which process it belongs to, as the
    API's own `processPrint` gives it.
  * A DEPUTY is '<term>/<id>', '10/1': the API's MP id within the term.
  * A DIVISION is 'pl-<term>-<sitting>-<number>', 'pl-10-66-133': the Sejm
    numbers votes from 1 within each sitting (posiedzenie), across its days.

THE CLUB IS STORED PER VOTE, as in Canada and the US: `pl_votes.club` is the
club (klub or koło) the vote record itself names, which is the club at the
time of the vote. Deputies move between clubs mid-term (Centrum and
RozwojPlus formed in 2026); `pl_members.club` is only the latest.

A BILL DOES NOT ALWAYS LAPSE WITH THE TERM. Under the Sejm's rules bills fall
at the end of a term (dyskontynuacja), EXCEPT citizens' bills (projekty
obywatelskie), which carry over into the next term under a new number. The
term is therefore part of every key.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS pl_members (
        mp_key       TEXT PRIMARY KEY,   -- '10/1': term / API MP id
        term         INTEGER NOT NULL,
        mp_id        INTEGER NOT NULL,
        name         TEXT,               -- 'Andrzej Adamczyk'
        club         TEXT,               -- latest seen; see pl_votes.club
        district     TEXT,               -- 'Kraków (13)'
        voivodeship  TEXT,
        active       INTEGER,            -- 1 while the mandate is held
        inactive_cause TEXT,             -- 'Zrzeczenie', 'Wygaśnięcie', ...
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS pl_prints (
        print_key    TEXT PRIMARY KEY,   -- '10/3080-A'
        term         INTEGER NOT NULL,
        number       TEXT NOT NULL,      -- '3080-A'
        process_key  TEXT,               -- '10/3030', from the API's processPrint
        title        TEXT,
        document_date TEXT,
        delivery_date TEXT,
        change_date  TEXT,               -- the API's own changeDate
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS pl_processes (
        process_key  TEXT PRIMARY KEY,   -- '10/2110'
        term         INTEGER NOT NULL,
        number       TEXT NOT NULL,
        title        TEXT,               -- 'Rządowy projekt ustawy o ...'
        title_final  TEXT,               -- the enacted title, once passed
        description  TEXT,               -- the Sejm's own one-paragraph summary
        document_type TEXT,              -- 'projekt ustawy', 'projekt uchwały', 'wniosek', ...
        document_type_enum TEXT,         -- 'BILL', 'DRAFT_RESOLUTION' or NULL
        start_date   TEXT,
        closure_date TEXT,
        passed       INTEGER,            -- the API's `passed`
        eli          TEXT,               -- 'DU/2026/123' once published
        change_date  TEXT,               -- the API's changeDate, from the list
        last_stage   TEXT,               -- the latest stage's name (detail read)
        last_stage_date TEXT,
        stages_read  TEXT,               -- change_date of the detail last read
        areas        TEXT,               -- JSON list, NULL = not classified
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS pl_divisions (
        division_key TEXT PRIMARY KEY,   -- 'pl-10-66-133'
        term         INTEGER NOT NULL,
        sitting      INTEGER NOT NULL,
        sitting_day  INTEGER,
        number       INTEGER NOT NULL,   -- the vote's number within the sitting
        voted_at     TEXT,               -- '2026-10-08T14:02:11'
        kind         TEXT,               -- 'ELECTRONIC' / 'ON_LIST' (elections of persons)
        title        TEXT,               -- 'Pkt. 34 Sprawozdanie Komisji o ... (druki nr ...)'
        topic        TEXT,               -- 'wniosek o odrzucenie w całości projektu.'
        description  TEXT,
        print_numbers TEXT,              -- JSON list of prints the title or topic cites
        process_keys TEXT,               -- JSON list, through pl_prints.process_key
        majority_type TEXT,
        majority_votes INTEGER,
        yes          INTEGER,
        no           INTEGER,
        abstain      INTEGER,
        present      INTEGER,            -- quorum calls only
        not_participating INTEGER,
        total_voted  INTEGER,
        against_all  INTEGER,            -- ON_LIST only
        options      TEXT,               -- ON_LIST only: JSON [{option, optionIndex, votes}]
        own_areas    TEXT,               -- matched on the vote's OWN text
        areas        TEXT,               -- own + every linked process's; NULL = not classified
        matched_terms TEXT,
        tier         INTEGER,
        positions    INTEGER,            -- positions stored; NULL until the detail is read
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS pl_votes (
        division_key TEXT NOT NULL,
        mp_key       TEXT NOT NULL,
        position     TEXT,               -- 'YES' / 'NO' / 'ABSTAIN' / 'ABSENT' / 'VOTE_VALID'
        club         TEXT,               -- AT THE VOTE, as the vote record names it
        list_votes   TEXT,               -- ON_LIST only: JSON {optionIndex: 'YES'/'NO'}
        PRIMARY KEY (division_key, mp_key)
    )""",
    "CREATE INDEX IF NOT EXISTS pl_votes_member ON pl_votes (mp_key)",
    "CREATE INDEX IF NOT EXISTS pl_prints_process ON pl_prints (process_key)",
)

TABLES = ("pl_members", "pl_prints", "pl_processes", "pl_divisions", "pl_votes")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


def process_key(term, number):
    return "{0}/{1}".format(int(term), str(number).strip())


def mp_key(term, mp_id):
    return "{0}/{1}".format(int(term), int(mp_id))


def division_key(term, sitting, number):
    return "pl-{0}-{1}-{2}".format(int(term), int(sitting), int(number))


# --- the Polish watchlist, applied by process KEY ----------------------------
#
# As in the US: a key is exact, a title term is not. "Poselski projekt ustawy
# o zmianie ustawy - Kodeks karny" is the title of the abortion
# decriminalisation bill (10/176) and of a dozen bills about something else.

_WATCH = {}


def watchlist(path=None):
    """{process_key: (areas, why)} from config/watchlist-pl.yaml."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-pl.yaml")
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {str(k): (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("processes") or {}).items()}
    return _WATCH[path]


def add_watch_areas(res, key, path=None):
    """Union a watched process's areas into a FilterResult, in place, and say
    so in watchlist_hits so the stored row shows where the area came from."""
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
    return json.dumps(values or [], ensure_ascii=False)
