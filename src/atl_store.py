"""Tables for Austria's nine Landtage (AT6, 12 October 2026), from
tools/at_landtage.py. Every table is prefixed `atl_`.

See docs/austria-regions-scope.md for what was probed and why. The schema
follows src/at_store.py: its own module, idempotent statements, created by
db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/at_landtage.py writes these
tables, and nothing here touches another jurisdiction's table (the national
Parliament's are at_*).

ONE TABLE FOR NINE PARLIAMENTS. Seven Landtage are read, each from its own
system (no two share a platform), and every one of them yields the same
thing: a numbered document with a type, a title, sometimes a date and a
decision. So one row per document, keyed by Land and the Landtag's own
number, never a title:

    noe/XX/1095            Niederösterreich, Ltg.-1095/XX-2026
    stmk/XIX/1713/1        Steiermark, EZ/OZ 1713/1 of the XIX. GP
    ooe/XXIX/1469/2026     Oberösterreich, Beilage 1469/2026
    wien/201607            Wien, INFODAT Id(201607)
    sbg/17/362-BEA         Salzburg, Nr. 362-BEA der Beilagen, 17. GP
    vbg/<unid>             Vorarlberg, the Landtag's Domino document ID
    bgld/XXIII/2100-0603   Burgenland, Zahl 2100-0603
    ris/<RIS ID>           an adopted Land law in RIS Landesrecht

Kärnten and Tirol have no rows: their Landtag systems are closed to robots
(docs/austria-regions-scope.md). RIS rows carry the law's own Land.

DATES. `date` is the source's own date and `date_basis` says which:
'introduced' (eingebracht, Eingang), 'sitting' (the sitting it was dealt
with at: Wien), 'reported' (Salzburg's "Meldung vom"), 'decided' (the sitting that took a
Landtagsbeschluss: Steiermark), 'published'
(Kundmachung, RIS). Three systems print no date in their lists
(Steiermark, Vorarlberg, Burgenland): the collector reads the document's
own page for the rows on our ground; a row with no date at all falls back
to the day we first saw it ('first_seen'), and a row seen on a Land's very
first read is a `baseline` row, never shown as new (it may be years old).

DECISIONS ARE KLUB-LEVEL OR NONE. Oberösterreich prints the decision with
the Klubs for and against ('Antrag angenommen - mehrstimmig - Dafür: ÖVP,
FPÖ, SPÖ / Dagegen: GRÜNE, MFG, NEOS'); it is stored verbatim in `outcome`
and never turned into member positions here (X5's derived records stay in
the national edition until a Landtag's members are read).
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS atl_items (
        item_key     TEXT PRIMARY KEY,   -- 'noe/XX/1095' (see the docstring)
        land         TEXT NOT NULL,      -- 'noe','stmk','ooe','wien','sbg','vbg','bgld', or a RIS law's Land
        source       TEXT NOT NULL,      -- 'landtag' / 'ris'
        period       TEXT,               -- the Gesetzgebungsperiode as the Land writes it: 'XX', '17', '32'
        number       TEXT,               -- as printed: 'Ltg.-1095/XX-2026', '1713/1', 'LGBl. Nr. 37/2026'
        doc_type     TEXT,               -- the source's own type: 'Antrag', 'IA', 'Selbstständiger Antrag'
        kind         TEXT,               -- ours: 'bill','motion','question','answer','report','law','other'
        title        TEXT,               -- verbatim
        by_whom      TEXT,               -- introducers or Klubs, as printed (never a spouse, never contact data)
        date         TEXT,               -- ISO; see date_basis
        date_basis   TEXT,               -- 'introduced','sitting','reported','decided','published','first_seen'
        status       TEXT,               -- the source's own status words, when it prints any
        outcome      TEXT,               -- the recorded decision, verbatim (Oberösterreich's Klub line)
        url          TEXT,
        detail_read  TEXT,               -- ISO date the document's own page was last read
        baseline     INTEGER,            -- 1: first seen on the Land's first read, date unknown
        areas        TEXT,               -- JSON list; taxonomy-atch + watchlist-at 'landtage' by key
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS atl_items_land ON atl_items (land, date)",
    # One row per Land (and 'ris'): when it was last read and what came back.
    """CREATE TABLE IF NOT EXISTS atl_reads (
        land         TEXT PRIMARY KEY,
        last_read    TEXT,               -- ISO date of the last attempt
        last_ok      TEXT,               -- ISO date of the last read with no gap
        rows_seen    INTEGER,            -- rows in the last read's lists
        rows_ours    INTEGER,            -- of those, on our ground
        note         TEXT                -- the last gap, or why the Land is not read
    )""",
)

TABLES = ("atl_items", "atl_reads")

# The Länder, in the order the edition lists them, with the Landtag's name.
LANDTAGE = (
    ("wien", "Wien", "Wiener Landtag"),
    ("noe", "Niederösterreich", "Landtag von Niederösterreich"),
    ("ooe", "Oberösterreich", "Oberösterreichischer Landtag"),
    ("stmk", "Steiermark", "Landtag Steiermark"),
    ("tir", "Tirol", "Tiroler Landtag"),
    ("ktn", "Kärnten", "Kärntner Landtag"),
    ("sbg", "Salzburg", "Salzburger Landtag"),
    ("vbg", "Vorarlberg", "Vorarlberger Landtag"),
    ("bgld", "Burgenland", "Burgenländischer Landtag"),
)
NAMES = {code: name for code, name, _ in LANDTAGE}
LANDTAG = {code: house for code, _, house in LANDTAGE}
# Read by tools/at_landtage.py; the other two are closed to robots.
READ = ("wien", "noe", "ooe", "stmk", "sbg", "vbg", "bgld")
BLOCKED = {
    "ktn": "www.ktn.gv.at, the Kärntner Landtag's only site, disallows every robot "
           "but Google's and Bing's in robots.txt",
    "tir": "lte.tirol.gv.at, the Tiroler Landtag's materials system, disallows every "
           "robot in robots.txt",
}
RIS_BLOCKED = ("RIS Landesrecht (adopted Land laws): data.bka.gv.at, the open-data API's "
               "host, disallows every robot in robots.txt, and www.ris.bka.gv.at answers "
               "a bot check; parser ready, not read")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)


_WATCH = {}


def watchlist(path=None):
    """{item_key: (areas, why)} from the `landtage` section of
    config/watchlist-at.yaml (the national items stay under `items`)."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-at.yaml")
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {str(k): (list((v or {}).get("areas") or []), (v or {}).get("why"))
                        for k, v in (raw.get("landtage") or {}).items()}
    return _WATCH[path]


def add_watch_areas(res, item_key, path=None):
    """Union a watched document's areas into a FilterResult, in place."""
    hit = watchlist(path).get(item_key)
    if not hit:
        return res
    areas, _why = hit
    res.issue_areas = sorted(set(res.issue_areas or []) | set(areas))
    res.watchlist_hits = list(res.watchlist_hits or []) + ["watch:" + item_key]
    if res.tier is None:
        res.tier = 2
    return res


def reads(conn):
    """{land: row} from atl_reads ({} when the table is missing)."""
    try:
        return {r[0]: r for r in conn.execute(
            "SELECT land, last_read, last_ok, rows_seen, rows_ours, note FROM atl_reads")}
    except Exception:            # an old store without the table
        return {}
