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

ITALIAN (CH6, Chris, 10 October 2026: run the Italian list on the Italian
texts too). Added 10 October 2026, additively: `ch_businesses.title_it`,
`areas_it` (config/taxonomy-it.yaml for `ch` on the Italian title and
submitted text), `terms_it` and `tier_it`, created on old stores by ensure_schema
(ADDED_COLUMNS). `areas` is now de | fr | it | watchlist.

THE CANTONS (CH7, 13 October 2026). `ch_canton_acts` holds the business
items of the cantonal parliaments read by tools/ch_cantons.py
(docs/switzerland-cantons-scope.md): Zuerich, Bern, Geneva, Vaud and
Ticino. Keys carry the canton and its own number ('zh/376/2026',
'be/2026.GRPARL.151', 'ge/M3137', 'vd/26_MOT_10', 'ti/134780'), so a
cantonal item never collides with a federal business. Where the source
dates a step, `status_date` is that date; where it prints only the current
status, a run that sees it change stamps the day it saw it and sets
`status_seen`. `baseline` marks rows of an undated canton's first read
(never shown as new). Since 13 October 2026 Basel-Stadt and Thurgau are read
from their open-data APIs (written permission; `source_url` names the
dataset, as the licence asks) and their members' individual votes go to
`ch_canton_votes`. `ch_canton_divisions` holds Bern's Tagblatt votes with
their published tallies, linked to the act they name (St. Gallen's, Basel-Stadt's
and Thurgau's too). Additive: new tables only, created
by ensure_schema; nothing here touches the federal tables.
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
        areas        TEXT,               -- JSON: de | fr | it | watchlist-ch by number
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
    ) WITHOUT ROWID""",
    """CREATE TABLE IF NOT EXISTS ch_canton_acts (
        act_key      TEXT PRIMARY KEY,   -- 'zh/376/2026', 'be/2026.GRPARL.151', 'ge/M3137'
        canton       TEXT NOT NULL,      -- 'zh' / 'be' / 'ge' / 'vd' / 'ti'
        kind         TEXT NOT NULL,      -- the canton's own type: 'Motion', 'Anfrage', 'PL', ...
        number       TEXT,               -- the canton's own number, as printed
        label        TEXT,
        title        TEXT,               -- in the canton's language (Bern: German)
        title_fr     TEXT,               -- Bern's French title
        presented    TEXT,               -- submission / start date where the source gives one
        status       TEXT,               -- the canton's own words, never derived
        status_date  TEXT,               -- the source's date; else the run that saw it change
        status_seen  INTEGER DEFAULT 0,  -- 1: status_date is when a run SAW the change
        initiative   TEXT,               -- first signatory (party) or author, as printed
        committee    TEXT,
        url          TEXT,
        seq          INTEGER,            -- Zuerich's index sequence (incremental reads)
        question     INTEGER DEFAULT 0,  -- 1: an Anfrage / Interpellation / question
        baseline     INTEGER DEFAULT 0,  -- 1: seen on an undated canton's first read
        areas        TEXT,               -- JSON; the language list + watchlist-ch `cantons`
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ch_canton_divisions (
        vote_key     TEXT PRIMARY KEY,   -- 'be/v/<abstimmung_uid>'
        canton       TEXT NOT NULL,
        act_key      TEXT,               -- the act the vote names, or NULL
        date         TEXT,
        subject      TEXT,               -- what was voted on: 'Ziff. 1', 'Antrag 2, BaK'
        result       TEXT,               -- as published: 'Annahme / Adoption'
        yes          INTEGER,
        no           INTEGER,
        abstain      INTEGER,
        url          TEXT,
        areas        TEXT,               -- the act's
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    # Members' individual votes in a cantonal division, where the canton
    # publishes them (13 October 2026: Basel-Stadt's data.bs.ch 100186,
    # Thurgau's data.tg.ch sk-stat-136 and Basel-Landschaft's data.bl.ch
    # 13080, read with written permission).
    """CREATE TABLE IF NOT EXISTS ch_canton_votes (
        vote_key     TEXT NOT NULL,      -- ch_canton_divisions.vote_key
        member       TEXT NOT NULL,      -- 'Vorname Name', as the dataset prints it
        member_id    TEXT,               -- the canton's own member number, where given
        parl_group   TEXT,               -- the Fraktion AT THE VOTE
        position     TEXT,               -- 'Ja' / 'Nein' / 'Enthaltung' / 'Abwesend' /
                                         -- 'Präsident' / a named option ('Antrag GFK')
        PRIMARY KEY (vote_key, member)
    ) WITHOUT ROWID""",
    "CREATE INDEX IF NOT EXISTS ch_canton_acts_canton ON ch_canton_acts (canton, presented)",
    "CREATE INDEX IF NOT EXISTS ch_canton_divisions_act ON ch_canton_divisions (act_key)",
    "CREATE INDEX IF NOT EXISTS ch_divisions_business ON ch_divisions (business_id)",
    "CREATE INDEX IF NOT EXISTS ch_votes_member ON ch_votes (person_number)",
)

TABLES = ("ch_members", "ch_sessions", "ch_businesses", "ch_divisions", "ch_votes",
          "ch_canton_acts", "ch_canton_divisions", "ch_canton_votes")

# Columns added after a table was first shipped: (table, column, type).
# CH6 (10 October 2026): the Italian pass.
ADDED_COLUMNS = (
    ("ch_businesses", "title_it", "TEXT"),
    ("ch_businesses", "areas_it", "TEXT"),   # JSON: taxonomy-it (for ch) on the Italian text
    ("ch_businesses", "terms_it", "TEXT"),   # JSON: the Italian matched terms
    ("ch_businesses", "tier_it", "INTEGER"), # the Italian match's own tier
    # 13 October 2026 (written permissions): the open-data dataset an act or
    # a vote was read from (data.bs.ch / data.tg.ch / data.bl.ch), which the licence asks
    # us to link; NULL for the cantons read from their own sites.
    ("ch_canton_acts", "source_url", "TEXT"),
    ("ch_canton_divisions", "source_url", "TEXT"),
    ("ch_canton_divisions", "counts_from", "TEXT"),   # 'published' / 'tallied'
    # 15 October 2026: the member's party (Basel-Stadt: the Grand Council's
    # adr export), beside the Fraktion at the vote (parl_group).
    ("ch_canton_votes", "party", "TEXT"),
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


_CANTON_WATCH = {}


def canton_watchlist(path=None):
    """{act_key: (areas, why)} from config/watchlist-ch.yaml's `cantons`
    section (CH7), keyed by ch_canton_acts.act_key."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-ch.yaml")
    if path not in _CANTON_WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _CANTON_WATCH[path] = {str(k): (list(v.get("areas") or []), v.get("why"))
                               for k, v in (raw.get("cantons") or {}).items()}
    return _CANTON_WATCH[path]


def canton_watch_areas(act_key, path=None):
    """(areas, hit label) for a watched cantonal act, else ([], None)."""
    hit = canton_watchlist(path).get(act_key) if act_key else None
    if not hit:
        return [], None
    return list(hit[0]), "watch:{0}".format(act_key)


def short_number(business_id):
    """20250059 -> '25.059'; 20262001 -> '26.2001'; 20193743 -> '19.3743'."""
    s = str(int(business_id))
    year, rest = s[2:4], s[4:]
    rest = rest.lstrip("0").rjust(3, "0") if len(rest) == 4 and rest.startswith("0") else rest
    return "{0}.{1}".format(year, rest)


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
