"""Tables for the two light Latam checks that have no parliament to collect
(the Latam monitor, 10 October 2026; docs/country-decisions-2026-10-10.md,
"Edition structure"):

  * Venezuela (VE1-VE3): the Asamblea Nacional's *Legislativa* news feed,
    read monthly and classified with the shared taxonomy-es for code `ve`
    (tools/ve_news.py). The Assembly publishes no votes and its bill register
    stopped in 2022, so the feed is the only live source (docs/venezuela-scope.md).
  * Nicaragua (NI2): La Gaceta, the official gazette, read for religious-
    freedom items (cancellations of the legal status of churches, religious
    associations and NGOs), classified with taxonomy-es for code `nic`
    (tools/nic_gaceta.py). The prefix is `nic`, never `ni`: `ni_` is
    Northern Ireland.

Own module, as for every country: idempotent statements, created by
db.init_db so every store carries them and db.TABLES stays true. Nothing
outside tools/ve_news.py and tools/nic_gaceta.py writes these tables.
"""

from __future__ import annotations

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS ve_news (
        url           TEXT PRIMARY KEY,   -- the article's own address: the only stable key
        date          TEXT,               -- ISO date the site prints ('Fecha: dd/mm/yyyy')
        title         TEXT,               -- verbatim
        body          TEXT,               -- plain text, first 6,000 characters
        areas         TEXT,               -- JSON list, taxonomy-es for 've'
        matched_terms TEXT,
        tier          INTEGER,
        first_seen    TEXT,
        last_seen     TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS nic_gazette_issues (
        issue         INTEGER PRIMARY KEY, -- La Gaceta's printed number: 184 (restarts each year)
        year          INTEGER NOT NULL,
        date          TEXT,               -- ISO date of the issue
        url           TEXT,               -- the issue page (the PDF is embedded in it)
        pages         INTEGER,            -- text blocks read; 0 = no text layer
        items         INTEGER,            -- notices split out
        read_at       TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS nic_gazette_items (
        item_key      TEXT PRIMARY KEY,   -- '2026/184/12': year, issue, notice number in the issue
        issue         INTEGER NOT NULL,
        date          TEXT,
        url           TEXT,               -- the issue page
        heading       TEXT,               -- the notice's first words, verbatim
        text          TEXT,               -- the notice, first 2,000 characters
        areas         TEXT,               -- JSON list, taxonomy-es for 'nic'
        matched_terms TEXT,
        tier          INTEGER,
        first_seen    TEXT,
        last_seen     TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ve_news_date ON ve_news (date)",
    "CREATE INDEX IF NOT EXISTS nic_gazette_items_date ON nic_gazette_items (date)",
)

TABLES = ("ve_news", "nic_gazette_issues", "nic_gazette_items")


def ensure_schema(conn):
    for statement in SCHEMA:
        conn.execute(statement)
    conn.commit()
    return conn
