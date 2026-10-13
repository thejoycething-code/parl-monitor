"""Tables for Poland's regional layer (13 October 2026): the sixteen
voivodeship assemblies (sejmiki województw).

See docs/poland-regions-scope.md for what was measured and why. The schema
follows src/es_regions_store.py: its own module, idempotent statements,
created by db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/pl_regions.py writes these
tables, and nothing here touches another jurisdiction's table (the Sejm's
pl_* tables are src/pl_store.py's).

TWO SOURCES, ONE TABLE, TWO KEYS.

  * The voivodeship official journals (dzienniki urzędowe województw), one
    per voivode, fifteen of them on the same e-Dziennik platform with the
    same JSON month list. They publish every act of a sejmik that must be
    published (local law, budgets, statutes, programmes adopted as local
    law) and the voivode's supervisory rulings (rozstrzygnięcia nadzorcze)
    that annul one. Keyed '<region>/dz/<year>/<position>' ('mz/dz/2026/9183'),
    the journal's own position number. Non-binding resolutions (stanowiska,
    apele, declarations such as the 2019-20 "Samorządowa Karta Praw Rodzin")
    are never published there.
  * The sejmiki's own registers of resolutions in their BIP (Biuletyn
    Informacji Publicznej), read where the register is a plain list:
    every resolution adopted, binding or not, with its number, date and
    subject. Keyed '<region>/<the resolution number as printed>'
    ('ld/XXXI/396/2026', 'mz/154/26'). A register's first read lists the
    whole term so far: those rows are marked `seed` and count as new only by
    their own adoption date, so the first edition is not a flood.

AREAS. NULL means unclassified, '[]' classified and on nobody's ground.
Every title is Polish and classified with config/taxonomy-pl.yaml, plus
config/watchlist-pl.yaml's `regional` section by KEY.
"""

from __future__ import annotations

import json
import os

# The sixteen voivodeships by their standard two-letter codes, in the order
# of docs/poland-regions-scope.md's ranking (population, then relevance).
REGIONS = {
    "mz": "Mazowieckie",
    "sl": "Śląskie",
    "wp": "Wielkopolskie",
    "ma": "Małopolskie",
    "ds": "Dolnośląskie",
    "ld": "Łódzkie",
    "pm": "Pomorskie",
    "pk": "Podkarpackie",
    "lu": "Lubelskie",
    "kp": "Kujawsko-Pomorskie",
    "zp": "Zachodniopomorskie",
    "wn": "Warmińsko-Mazurskie",
    "sk": "Świętokrzyskie",
    "pd": "Podlaskie",
    "lb": "Lubuskie",
    "op": "Opolskie",
}

# The assembly of each, in the genitive the publications use ("Sejmik
# Województwa Mazowieckiego"), for matching a journal publisher.
SEJMIK = {
    "mz": "Sejmik Województwa Mazowieckiego",
    "sl": "Sejmik Województwa Śląskiego",
    "wp": "Sejmik Województwa Wielkopolskiego",
    "ma": "Sejmik Województwa Małopolskiego",
    "ds": "Sejmik Województwa Dolnośląskiego",
    "ld": "Sejmik Województwa Łódzkiego",
    "pm": "Sejmik Województwa Pomorskiego",
    "pk": "Sejmik Województwa Podkarpackiego",
    "lu": "Sejmik Województwa Lubelskiego",
    "kp": "Sejmik Województwa Kujawsko-Pomorskiego",
    "zp": "Sejmik Województwa Zachodniopomorskiego",
    "wn": "Sejmik Województwa Warmińsko-Mazurskiego",
    "sk": "Sejmik Województwa Świętokrzyskiego",
    "pd": "Sejmik Województwa Podlaskiego",
    "lb": "Sejmik Województwa Lubuskiego",
    "op": "Sejmik Województwa Opolskiego",
}

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS plr_acts (
        act_key      TEXT PRIMARY KEY,    -- 'mz/dz/2026/9183' (journal) or 'ld/XXXI/396/2026' (register)
        region       TEXT NOT NULL,       -- 'mz', see REGIONS
        source       TEXT NOT NULL,       -- 'journal' or 'bip'
        number       TEXT,                -- the resolution's number as printed ('154/26', 'XXXI/396/2026')
        kind         TEXT,                -- 'uchwała', 'stanowisko', 'rozstrzygnięcie nadzorcze', ...
        title        TEXT,                -- as printed, whitespace folded
        adopted      TEXT,                -- ISO date the sejmik adopted it (or the ruling's date)
        published    TEXT,                -- ISO date of the journal position (journal rows)
        session      TEXT,                -- the sitting, when the register groups by it ('XXXI sesja')
        journal_ref  TEXT,                -- 'Dz. Urz. Woj. Mazowieckiego 2026 poz. 9183'
        url          TEXT,
        areas        TEXT,                -- JSON list, NULL = unclassified
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,                -- ISO date first read
        last_seen    TEXT,                -- ISO date last read
        seed         INTEGER              -- 1: first listed on the source's FIRST read
    )""",
    """CREATE TABLE IF NOT EXISTS plr_reads (
        source       TEXT PRIMARY KEY,    -- 'journal:mz', 'bip:ld', ...
        last_seen    TEXT,                -- ISO date of the last read, ok or not (status says)
        items        INTEGER,             -- sejmik rows the last read listed
        status       TEXT                 -- 'ok', or the last failure, short
    )""",
    "CREATE INDEX IF NOT EXISTS plr_acts_region ON plr_acts (region, adopted)",
    "CREATE INDEX IF NOT EXISTS plr_acts_published ON plr_acts (published)",
)

TABLES = ("plr_acts", "plr_reads")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)


# --- the regional watchlist, applied by act KEY --------------------------------
#
# config/watchlist-pl.yaml's `regional` section, keyed by plr_acts.act_key.
# A sejmik's titles are mostly plain ("w sprawie przyjęcia Samorządowej Karty
# Praw Rodzin"), but a repeal reads "w sprawie uchylenia uchwały nr
# XXIII/353/19": the key is how it reaches the edition.

_WATCH = {}


def watchlist(path=None):
    """{act_key: (areas, why)} from config/watchlist-pl.yaml's `regional`."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-pl.yaml")
    if path not in _WATCH:
        try:
            with open(path, encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
        except FileNotFoundError:
            raw = {}
        _WATCH[path] = {str(k): (list((v or {}).get("areas") or []), (v or {}).get("why"))
                        for k, v in (raw.get("regional") or {}).items()}
    return _WATCH[path]


def add_watch_areas(res, key, path=None):
    """Union a watched act's areas into a FilterResult, in place, and say so
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
