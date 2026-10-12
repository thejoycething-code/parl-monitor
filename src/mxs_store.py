"""Tables for Mexico's 32 STATE CONGRESSES (regional layer, 12 October 2026),
from tools/mxs_collect.py and its per-state readers (src/ingest/mxs_*.py).
Every table is prefixed `mxs_`.

See docs/mexico-regions-scope.md for what was measured, state by state, and
why only some states are read. The schema follows src/us_states_store.py
and src/prov_store.py: its own module, idempotent statements, created by
db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/mxs_collect.py and
src/ingest/mxs_*.py writes these tables, and nothing here touches the
federal Chamber's mx_* tables or any other jurisdiction's.

KEYS, NEVER TITLES. An item is '<state>/<the source's own id>':
'cdmx/<folio>', 'chih/<number>'. The id is whatever the state's own system
uses to tell its items apart (a folio, a number, a post id), never a title:
state titles repeat ("Iniciativa con proyecto de decreto por el que se
reforma ...") and numbers restart each legislature, so a reader that only
has per-legislature numbers prefixes the legislature ('jal/64/1234').
config/watchlist-mx-states.yaml is keyed the same way.

WHAT IS STORED. Every item a reader lists, on our ground or not (titles
only, a few hundred bytes each: tens of thousands a year across the states
read, under 20 MB), so a taxonomy change can be applied offline with
`tools/mxs_collect.py --reclassify`. Areas come from config/taxonomy-es.yaml
(country 'mx') and the watchlist, by key.

NO MEMBER POSITIONS YET. No state read so far publishes a machine-readable
roll call per member (several print one inside a PDF of the session's
minutes); see the scope doc. `mxs_items.status` and `status_date` are the
source's own words for where an item stands, verbatim. Where a source
prints a status without a date, `status_date` is the day a run first saw the
status change (never on an item's first sighting, which is the backlog).
"""

from __future__ import annotations

import json
import os

# The 32 federal entities, by the short codes used in keys.
STATES = {
    "ags": "Aguascalientes", "bc": "Baja California", "bcs": "Baja California Sur",
    "cam": "Campeche", "chis": "Chiapas", "chih": "Chihuahua", "cdmx": "Ciudad de México",
    "coah": "Coahuila", "col": "Colima", "dgo": "Durango", "mex": "Estado de México",
    "gto": "Guanajuato", "gro": "Guerrero", "hgo": "Hidalgo", "jal": "Jalisco",
    "mich": "Michoacán", "mor": "Morelos", "nay": "Nayarit", "nl": "Nuevo León",
    "oax": "Oaxaca", "pue": "Puebla", "qro": "Querétaro", "qroo": "Quintana Roo",
    "slp": "San Luis Potosí", "sin": "Sinaloa", "son": "Sonora", "tab": "Tabasco",
    "tamps": "Tamaulipas", "tlax": "Tlaxcala", "ver": "Veracruz", "yuc": "Yucatán",
    "zac": "Zacatecas",
}

# What an item is, as the edition names it.
KINDS = {
    "iniciativa": "Iniciativa",
    "punto": "Punto de acuerdo",
    "dictamen": "Dictamen",
    "decreto": "Decree (approved)",
    "gaceta": "Gaceta entry",
    "other": "Item",
}

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS mxs_items (
        item_key     TEXT PRIMARY KEY,   -- '<state>/<source id>'
        state        TEXT NOT NULL,      -- 'cdmx', see STATES
        source_id    TEXT NOT NULL,      -- the source's own id, as printed
        legislature  TEXT,               -- 'III', 'LXVIII', as the state numbers it
        kind         TEXT,               -- see KINDS
        title        TEXT,               -- the source's own words, verbatim
        presenter    TEXT,               -- author / promovente, verbatim
        party        TEXT,               -- as printed, if any
        presented    TEXT,               -- ISO date presented / published
        turno        TEXT,               -- committee(s) it was sent to
        status       TEXT,               -- the source's own status words
        status_date  TEXT,               -- ISO date of that status, if given
        url          TEXT,               -- the state's own page or document
        areas        TEXT,               -- JSON list; taxonomy-es (mx) + watchlist
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    # One row per state per run: what the reader did. A state not read
    # (blocked, unreachable) has a row too, so the edition can say so.
    """CREATE TABLE IF NOT EXISTS mxs_reads (
        state        TEXT PRIMARY KEY,
        reader       TEXT,               -- the src/ingest module, or NULL
        status       TEXT,               -- 'ok' / 'gap' / 'unreachable' / 'blocked'
        detail       TEXT,               -- why, in a line
        items_listed INTEGER,            -- items the listing returned this run
        items_new    INTEGER,            -- of those, new to the store
        data_through TEXT,               -- the newest item date seen
        read_at      TEXT,
        last_ok      TEXT,               -- the last run that read it cleanly
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS mxs_items_state ON mxs_items (state, presented)",
)

TABLES = ("mxs_items", "mxs_reads")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


def item_key(state, source_id):
    return "{0}/{1}".format(state, str(source_id).strip())


# --- the watchlist, applied by item KEY ---------------------------------------

_WATCH = {}
WATCH_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "config", "watchlist-mx-states.yaml")


def watchlist(path=None):
    """{item_key: {"areas": [...], "why": str}} from config/watchlist-mx-states.yaml."""
    import yaml
    path = path or WATCH_PATH
    if path not in _WATCH:
        raw = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {str(k): {"areas": list((v or {}).get("areas") or []),
                                 "why": (v or {}).get("why")}
                        for k, v in (raw.get("items") or {}).items()}
    return _WATCH[path]


def add_watch_areas(res, key, path=None):
    hit = watchlist(path).get(key)
    if not hit:
        return res
    res.issue_areas = sorted(set(res.issue_areas or []) | set(hit["areas"]))
    res.watchlist_hits = list(res.watchlist_hits or []) + ["watch:" + key]
    if res.tier is None:
        res.tier = 2
    return res


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)


def upsert_item(conn, it, res, today):
    """Store one item (a dict from a reader) with its classification; True
    when it was new to the store."""
    key = item_key(it["state"], it["source_id"])
    old = conn.execute("SELECT status FROM mxs_items WHERE item_key=?", (key,)).fetchone()
    new = old is None
    # A status the source prints without a date is dated the day we first see
    # it change (never on the first sighting: that is the backlog).
    if (not new and it.get("status") and not it.get("status_date")
            and (old[0] or "") != it["status"]):
        it = dict(it, status_date=today)
    conn.execute(
        "INSERT INTO mxs_items (item_key, state, source_id, legislature, kind, title, presenter, "
        "party, presented, turno, status, status_date, url, areas, matched_terms, tier, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(item_key) DO UPDATE SET "
        "legislature=COALESCE(excluded.legislature, mxs_items.legislature), "
        "kind=COALESCE(excluded.kind, mxs_items.kind), "
        "title=COALESCE(excluded.title, mxs_items.title), "
        "presenter=COALESCE(excluded.presenter, mxs_items.presenter), "
        "party=COALESCE(excluded.party, mxs_items.party), "
        "presented=COALESCE(excluded.presented, mxs_items.presented), "
        "turno=COALESCE(excluded.turno, mxs_items.turno), "
        "status=COALESCE(excluded.status, mxs_items.status), "
        "status_date=COALESCE(excluded.status_date, mxs_items.status_date), "
        "url=COALESCE(excluded.url, mxs_items.url), areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (key, it["state"], str(it["source_id"]), it.get("legislature"), it.get("kind"),
         it.get("title"), it.get("presenter"), it.get("party"), it.get("presented"),
         it.get("turno"), it.get("status"), it.get("status_date"), it.get("url"),
         dumps(res.issue_areas), dumps(res.matched_terms), res.tier, today, today))
    return new


def record_read(conn, state, reader, status, detail, listed, new, through, now):
    conn.execute(
        "INSERT INTO mxs_reads (state, reader, status, detail, items_listed, items_new, "
        "data_through, read_at, last_ok, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(state) DO UPDATE SET reader=excluded.reader, status=excluded.status, "
        "detail=excluded.detail, items_listed=excluded.items_listed, "
        "items_new=excluded.items_new, "
        "data_through=COALESCE(excluded.data_through, mxs_reads.data_through), "
        "read_at=excluded.read_at, last_ok=COALESCE(excluded.last_ok, mxs_reads.last_ok), "
        "last_seen=excluded.last_seen",
        (state, reader, status, detail, listed, new, through, now,
         now if status == "ok" else None, now[:10], now[:10]))
