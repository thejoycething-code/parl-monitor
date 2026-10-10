"""Tables for the Peru Congress monitor (phase 1, 9 October 2026): members of
both chambers, proyectos de ley, plenary votes and every member's position.

See docs/peru-scope.md for what was measured and why. The schema follows the
US precedent (src/us_store.py): its own module, idempotent statements,
created by db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/pe_*.py writes these tables,
and nothing here touches another jurisdiction's table.

BICAMERAL SINCE 27 JULY 2026. The 2026-2031 Congress has a Senado (60) and a
Camara de Diputados (130). `chamber` is 'senado' or 'diputados' everywhere;
a proyecto of the old single chamber (and the few still filed to the
Congress as a whole) carries 'congreso'.

KEYS. A proyecto is the Congress's own number string, exactly as the
Sistema de Proyectos de Ley prints it: '00553-2026-2031-CD',
'00013-2026-2031-S', '00006-2026-2031-CR', and for the 2021-2026 Congress
'14864/2025-CR'. Numbers restart per chamber and per period, so the bare
number is never a key and the title never is. A member is
'<chamber>/<slug>', the chamber site's own WordPress slug
('senado/velasquez-garcia-miguel-angel'). A division is
'<chamber>/<record id>': the vote system prints a record id at the foot of
every page ('41010 - 58450 - 10009 - S'), unique per vote.

POSITIONS COME FROM PROVISIONAL RECORDS. The signed vote records are
printer scans with no text layer; the provisional "copia informativa"
uploaded first is a digital export with one (docs/peru-scope.md). So a
division row says `provisional = 1`, and `counts_match` says whether the
positions parsed add up to the totals the record itself prints. Names on
the record are cut to a column width ('JAUREGUI MARTINEZ DE'), so
`pe_votes.name_raw` is always kept and `member_key` is filled only when the
name resolves to exactly one member of that chamber.

PARTY IS STORED PER VOTE: `pe_votes.bancada` is the group code the record
printed ('FP', 'JP'); `pe_members.bancada` is only the latest seen.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS pe_members (
        member_key   TEXT PRIMARY KEY,   -- 'senado/velasquez-garcia-miguel-angel'
        chamber      TEXT NOT NULL,      -- 'senado' / 'diputados'
        name         TEXT,               -- as the site prints it: 'Velasquez Garcia, Miguel Angel'
        bancada      TEXT,               -- grupo parlamentario slug, latest seen
        party        TEXT,               -- partido politico slug
        district     TEXT,               -- distrito electoral slug
        period       TEXT,               -- '2026-2031'
        status       TEXT,               -- condicion: 'en-ejercicio', ...
        wp_id        INTEGER,
        link         TEXT,
        as_of        TEXT,               -- the record's own modified date
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS pe_bills (
        bill_key     TEXT PRIMARY KEY,   -- '00553-2026-2031-CD', never the title
        period       INTEGER NOT NULL,   -- perParId: 2026, 2021
        chamber      TEXT NOT NULL,      -- 'senado' / 'diputados' / 'congreso'
        number       INTEGER NOT NULL,   -- pleyNum, restarts per chamber and period
        title        TEXT,
        status       TEXT,               -- desEstado, the Congress's own words
        presented    TEXT,               -- ISO date
        proponent    TEXT,               -- desProponente
        authors      TEXT,               -- JSON list of 'Surname, Name'
        areas        TEXT,               -- JSON list; taxonomy + watchlist-pe by key
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS pe_divisions (
        division_key TEXT PRIMARY KEY,   -- 'senado/41010-58450-10009'
        chamber      TEXT NOT NULL,
        date         TEXT,               -- ISO date
        time         TEXT,               -- '01:06 PM', as printed
        subject      TEXT,               -- the record's Asunto
        bill_refs    TEXT,               -- JSON list of bill_keys the subject names (resolved)
        source_url   TEXT,
        provisional  INTEGER,            -- 1: positions from the provisional copy
        yes          INTEGER,            -- A FAVOR (SI), as printed
        no           INTEGER,
        abstain      INTEGER,
        no_answer    INTEGER,            -- SIN RESPUESTA
        absent       INTEGER,
        on_leave     INTEGER,            -- every LIC. line added up
        counts_match INTEGER,            -- 1 when parsed positions equal the printed totals
        own_areas    TEXT,               -- JSON: matched on the subject itself
        areas        TEXT,               -- JSON: own + the named bills'
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS pe_votes (
        division_key TEXT NOT NULL,
        name_raw     TEXT NOT NULL,      -- as printed, cut to the column
        member_key   TEXT,               -- NULL unless exactly one member matches
        bancada      TEXT,               -- AT THE VOTE: 'FP', 'JP', ...
        position     TEXT,               -- 'SI' / 'NO' / 'ABST' / 'AUS' / 'LO' / 'LE' / 'LP' / 'LV' / 'SUS' / 'PRES' / 'SR'
        PRIMARY KEY (division_key, name_raw)
    )""",
    """CREATE TABLE IF NOT EXISTS pe_vote_files (
        url          TEXT PRIMARY KEY,   -- a vote record PDF in a chamber's media library
        chamber      TEXT NOT NULL,
        uploaded     TEXT,               -- the media item's own date
        text_layer   INTEGER,            -- 0: a scan, nothing to read
        divisions    INTEGER,            -- votes parsed from it
        read_at      TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS pe_votes_member ON pe_votes (member_key)",
    "CREATE INDEX IF NOT EXISTS pe_bills_chamber ON pe_bills (chamber, number)",
)

# X8 (10 October 2026): the constitutional court's rulings on our ground, one
# shape for every country (src/courts.py); written only by tools/pe_courts.py.
from src import courts as _courts  # noqa: E402

SCHEMA = SCHEMA + _courts.schema("pe")

# X7 (10 October 2026; tools/pe_ocr.py, src/ocr.py): Tesseract's reading of
# the scan-only vote records (pe_vote_files.text_layer = 0). Stored as
# evidence beside the scan, never parsed into positions (src/ocr.py).
SCHEMA = SCHEMA + (
    """CREATE TABLE IF NOT EXISTS pe_vote_ocr (
        url          TEXT PRIMARY KEY,   -- the scan, as in pe_vote_files
        engine       TEXT,               -- 'tesseract 5.5.1' as it reports itself
        lang         TEXT,               -- 'spa'
        pages        INTEGER,
        chars        INTEGER,
        text         TEXT,               -- page texts joined, '\f' between pages
        read_at      TEXT
    )""",
)

TABLES = ("pe_members", "pe_bills", "pe_divisions", "pe_votes", "pe_vote_files", "pe_rulings",
          "pe_vote_ocr")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- watchlist ---------------------------------------------------------------

WATCHLIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "config", "watchlist-pe.yaml")


def watchlist(path=None):
    """{bill_key: (areas, why)} from config/watchlist-pe.yaml. Keyed by the
    proyecto number string, never the title."""
    import yaml
    path = path or WATCHLIST
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    out = {}
    for key, spec in (raw.get("bills") or {}).items():
        spec = spec or {}
        out[str(key)] = (sorted(int(a) for a in (spec.get("areas") or [])), spec.get("why"))
    return out


def add_watch_areas(res, bill_key, path=None, wl=None):
    """Union a watched proyecto's areas into a FilterResult, in place, and say
    so in watchlist_hits so the stored row shows where the area came from."""
    hit = (wl if wl is not None else watchlist(path)).get(bill_key)
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
