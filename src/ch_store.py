"""Tables for the Swiss Federal Assembly monitor (phase 1, 9 October 2026):
members, sessions, businesses (Geschaefte / objets), recorded votes of both
councils and the members' positions.

See docs/switzerland-scope.md for what was measured and why. The schema
follows the US precedent (src/us_store.py): its own module, idempotent
statements, created by db.init_db so every store carries it and db.TABLES
stays true.

SEPARATION GUARANTEE. Nothing outside tools/ch_*.py writes these tables,
and nothing here touches another jurisdiction's table.

KEYS.
  * A member is their PersonNumber, the Parliament Services' own ID. The
    Nationalrat's positions carry it; the Staenderat's session spreadsheets
    do NOT (name and canton only), so a Staenderat position is resolved to
    a PersonNumber by name and canton, and an unresolved one is dropped and
    recorded as a gap, never stored under a guess.
  * A business is its Geschaeftsnummer as the OData service writes it, an
    integer: 20250059 for 25.059. `short_number` keeps the printed form.
    Titles are never keys: the same title recurs as motions in both
    councils and as a Fragestunde question on the same day.
  * A division is 'nr-<Vote ID>' (the OData Vote entity) or
    'sr-<Referenznummer>' (the spreadsheet's running vote number).

PARTY IS STORED PER VOTE: `ch_votes.parl_group` is the Fraktion printed on
that vote. `ch_members.parl_group` is only the latest seen.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS ch_members (
        person_number INTEGER PRIMARY KEY,
        first_name   TEXT,
        last_name    TEXT,
        council      TEXT,               -- 'NR' / 'SR' (latest), 'BR' Federal Council
        canton       TEXT,               -- two-letter abbreviation: 'ZH'
        canton_name  TEXT,               -- German name, as the SR spreadsheets print it
        parl_group   TEXT,               -- Fraktion abbreviation, latest seen: 'V', 'S', 'M-E'
        party        TEXT,               -- party abbreviation: 'SVP', 'SP'
        active       INTEGER,
        date_joining TEXT,
        date_leaving TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ch_sessions (
        session_id   INTEGER PRIMARY KEY, -- 5215
        name         TEXT,               -- 'Herbstsession 2026'
        start_date   TEXT,
        end_date     TEXT,
        session_type INTEGER,            -- 1 ordinary?/2 ordinary/3 special, as published
        legislative_period INTEGER,
        nr_votes     INTEGER,            -- divisions stored for this session
        sr_votes     INTEGER,
        complete_at  TEXT,               -- set once pulled after end_date + grace
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ch_businesses (
        business_id  INTEGER PRIMARY KEY, -- Geschaeftsnummer: 20250059
        short_number TEXT,               -- '25.059'
        business_type TEXT,              -- 'Mo.', 'Pa. Iv.', 'BRG', 'Fra.', ...
        title_de     TEXT,
        title_fr     TEXT,
        submitted_by TEXT,
        submission_date TEXT,
        submission_council TEXT,         -- 'NR' / 'SR'
        legislative_period INTEGER,
        status       TEXT,               -- German status text, never derived
        status_date  TEXT,
        department   TEXT,               -- responsible department: 'EDI'
        tags         TEXT,               -- the service's own topic tags, '|'-separated
        modified     TEXT,               -- the record's own Modified stamp
        areas_de     TEXT,               -- JSON: taxonomy-de on the German text
        areas_fr     TEXT,               -- JSON: taxonomy-qc on the French text
        areas        TEXT,               -- JSON: de | fr | watchlist-ch by number
        matched_terms TEXT,              -- JSON
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ch_divisions (
        division_key TEXT PRIMARY KEY,   -- 'nr-38971' / 'sr-8426'
        council      TEXT NOT NULL,      -- 'NR' / 'SR'
        vote_id      INTEGER NOT NULL,   -- OData Vote ID (NR) or Referenznummer (SR)
        session_id   INTEGER,
        date         TEXT,               -- ISO date
        business_id  INTEGER,            -- Geschaeftsnummer, or NULL
        short_number TEXT,
        draft_title  TEXT,               -- the bill (Entwurf) voted on, if any
        subject      TEXT,               -- 'Schlussabstimmung', 'Art. 101 Abs. 1'
        meaning_yes  TEXT,               -- what a yes meant: 'Antrag der Mehrheit'
        meaning_no   TEXT,
        yes          INTEGER,
        no           INTEGER,
        abstain      INTEGER,
        absent       INTEGER,            -- did not take part + excused
        result       TEXT,               -- SR: the council's own 'ja'/'nein'; NR: NULL (unpublished)
        counts_from  TEXT,               -- 'published' (SR) / 'tallied' (NR, from positions)
        positions    INTEGER,            -- positions stored in ch_votes
        own_areas    TEXT,               -- JSON: matched on the vote's OWN text
        areas        TEXT,               -- JSON: own + the business's
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ch_votes (
        division_key TEXT NOT NULL,
        person_number INTEGER NOT NULL,
        position     TEXT,               -- 'Ja' / 'Nein' / 'Enthaltung' / 'Nicht teilgenommen'
                                         -- / 'Entschuldigt' / 'Präsident' / 'Anwesend'
        parl_group   TEXT,               -- AT THE VOTE
        canton       TEXT,
        PRIMARY KEY (division_key, person_number)
    )""",
    "CREATE INDEX IF NOT EXISTS ch_divisions_business ON ch_divisions (business_id)",
    "CREATE INDEX IF NOT EXISTS ch_votes_member ON ch_votes (person_number)",
)

TABLES = ("ch_members", "ch_sessions", "ch_businesses", "ch_divisions", "ch_votes")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- the Swiss watchlist, applied by Geschaeftsnummer ------------------------

_WATCH = {}


def watchlist(path=None):
    """{business_id: (areas, why)} from config/watchlist-ch.yaml."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-ch.yaml")
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {int(k): (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("businesses") or {}).items()}
    return _WATCH[path]


def watch_areas(business_id, path=None):
    """(areas, hit label) for a watched business, else ([], None)."""
    if business_id is None:
        return [], None
    hit = watchlist(path).get(int(business_id))
    if not hit:
        return [], None
    return list(hit[0]), "watch:{0}".format(int(business_id))


def short_number(business_id):
    """20250059 -> '25.059'; 20262001 -> '26.2001'; 20193743 -> '19.3743'."""
    s = str(int(business_id))
    year, rest = s[2:4], s[4:]
    rest = rest.lstrip("0").rjust(3, "0") if len(rest) == 4 and rest.startswith("0") else rest
    return "{0}.{1}".format(year, rest)


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
