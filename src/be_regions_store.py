"""Tables for Belgium's community and regional parliaments (13 October 2026),
from tools/be_regions.py. Every table is prefixed `ber_`.

See docs/belgium-regions-scope.md for what was probed and why. The schema
follows src/atl_store.py: its own module, idempotent statements, created by
db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/be_regions.py writes these
tables, and nothing here touches another jurisdiction's table (the federal
Chamber's are be_*).

WHY THESE PARLIAMENTS. Education, youth, family allowances, health
prevention and culture are community matters in Belgium, so school sex
education (the French Community's EVRAS), gender in schools, family policy
and religious-symbol rules in schools are decided here, not in the Chamber.

ONE TABLE FOR SEVERAL PARLIAMENTS. Each parliament has its own system, and
each yields the same thing: a numbered parliamentary document (a bill for a
decree or an ordinance, a resolution, a motion, a petition) with a title,
a deposit date and a status. One row per document, keyed by the parliament
and its own number, never a title:

    vl/2025-2026/947        Vlaams Parlement, stuk 947 (2025-2026)
    pw/2025-2026/657        Parlement de Wallonie, doc. 657 (2025-2026)
    fwb/2026-2027/327       Parlement de la Fédération Wallonie-Bruxelles, doc. 327
    fwb/q/001863672         ... an oral or topical question (no number): its page id
    bru/24-29/A-123         Parlement bruxellois / Brussels Parlement, dossier A-123
    cocom/24-29/B-9         the United Assembly of the Common Community Commission
                            (ARCCC / VVGGC), dossier B-9

The parliament codes and names are PARLIAMENTS below; BLOCKED says which are
not read and why.

VOTES. Only the Flemish Parliament publishes its recorded votes, with every
member's position, as open data (ws.vlpar.be): ber_votes holds the tally and
ber_positions each member's vote, with the member's group AS THE VOTE RECORD
PRINTS IT (the Flemish record names the fractie with each vote, so it is the
group at the vote). The other parliaments print votes only in their
verbatim reports (PDF); not read.

MEMBERS. ber_members holds name, group and constituency only: never an
address, a telephone number, an e-mail address, a social-media account or a
spouse, even where the open data carries them (the Walloon list does).

DATES. `date` is the document's own deposit (or publication) date;
`status_date` the source's date for the current status where it prints one
(Flanders dates every status, Wallonia dates every document), else the day a
run first saw the status change (status_seen = 1). The first sighting of a
document is never a status change.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS ber_docs (
        doc_key      TEXT PRIMARY KEY,   -- 'vl/2025-2026/947' (see the docstring)
        parliament   TEXT NOT NULL,      -- 'vl','pw','fwb','bru','cocom'
        kind         TEXT,               -- ours: 'bill','resolution','motion','concept','petition','question','other'
        doc_type     TEXT,               -- the source's own words: 'Voorstel van decreet', 'Projet de décret'
        session      TEXT,               -- '2025-2026', or the legislature '24-29' (Brussels)
        number       TEXT,               -- as printed: '947', 'A-123'
        title        TEXT,               -- verbatim, in the parliament's language (Brussels: French)
        title_alt    TEXT,               -- the other language's title (Brussels: Dutch)
        lang         TEXT,               -- 'nl', 'fr', 'de'
        subject      TEXT,               -- the source's themes (Flanders), '; '-joined
        authors      TEXT,               -- introducers as printed (never contact data)
        date         TEXT,               -- ISO: deposited / published
        status       TEXT,               -- the source's own status words
        status_date  TEXT,               -- ISO; see DATES
        status_seen  INTEGER,            -- 1: status_date is the day a run saw the change
        url          TEXT,
        areas        TEXT,               -- JSON list; taxonomy-nl / taxonomy-fr for 'be', watchlist-be 'regions' by key
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ber_docs_parl ON ber_docs (parliament, date)",
    """CREATE TABLE IF NOT EXISTS ber_votes (
        vote_key     TEXT PRIMARY KEY,   -- 'vl/<journaallijn id>/<n>'
        parliament   TEXT NOT NULL,
        doc_key      TEXT,               -- the document voted on
        date         TEXT,               -- ISO
        title        TEXT,               -- what was voted on, verbatim
        yes          INTEGER,
        no           INTEGER,
        abstain      INTEGER,
        adopted      INTEGER,            -- 1 adopted, 0 rejected, NULL unknown
        matter       TEXT,               -- 'Gemeenschap' / 'Gewest' (Flemish: who may vote)
        url          TEXT,
        areas        TEXT,               -- JSON; the document's areas
        matched_terms TEXT,
        first_seen   TEXT
    ) WITHOUT ROWID""",
    """CREATE TABLE IF NOT EXISTS ber_positions (
        vote_key     TEXT NOT NULL,
        member_key   TEXT NOT NULL,      -- 'vl/4070'
        member_name  TEXT,               -- 'Koen Daniëls'
        group_name   TEXT,               -- the fractie the vote record prints
        position     TEXT,               -- 'yes','no','abstain'
        PRIMARY KEY (vote_key, member_key)
    ) WITHOUT ROWID""",  # vote tables carry no rowid (#140, src/store_compact.py)
    """CREATE TABLE IF NOT EXISTS ber_members (
        member_key   TEXT PRIMARY KEY,   -- 'vl/4070', 'pw/3676'
        parliament   TEXT NOT NULL,
        name         TEXT,               -- 'Koen Daniëls'
        group_name   TEXT,
        constituency TEXT,
        current      INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    # One row per parliament: when it was last read and what came back.
    """CREATE TABLE IF NOT EXISTS ber_reads (
        parliament   TEXT PRIMARY KEY,
        last_read    TEXT,               -- ISO date of the last attempt
        last_ok      TEXT,               -- ISO date of the last read with no gap
        rows_seen    INTEGER,
        rows_ours    INTEGER,
        note         TEXT                -- the last gap
    )""",
)

TABLES = ("ber_docs", "ber_votes", "ber_positions", "ber_members", "ber_reads")

# (code, short name, the parliament's name, language). Order = the edition's.
PARLIAMENTS = (
    ("vl", "Flanders", "Vlaams Parlement", "nl"),
    ("fwb", "French Community", "Parlement de la Fédération Wallonie-Bruxelles", "fr"),
    ("pw", "Wallonia", "Parlement de Wallonie", "fr"),
    ("bru", "Brussels", "Parlement bruxellois / Brussels Parlement", "fr"),
    ("cocom", "Brussels (COCOM)",
     "Assemblée réunie de la COCOM / Verenigde Vergadering van de GGC", "fr"),
    ("dg", "German-speaking Community", "Parlament der Deutschsprachigen Gemeinschaft", "de"),
    ("cocof", "Brussels (COCOF)", "Parlement francophone bruxellois", "fr"),
    ("vgc", "Brussels (VGC)", "Raad van de Vlaamse Gemeenschapscommissie", "nl"),
)
NAMES = {code: short for code, short, _, _ in PARLIAMENTS}
HOUSE = {code: house for code, _, house, _ in PARLIAMENTS}
LANG = {code: lang for code, _, _, lang in PARLIAMENTS}
# Read by tools/be_regions.py ('bru' and 'cocom' come from one read).
READ = ("vl", "fwb", "pw", "bru", "cocom")
BLOCKED = {
    "dg": "pdg.be (and ostbelgienlive.be, ostbelgienrecht.be) answer every request, "
          "robots.txt included, with a Cloudflare bot challenge; never bypassed",
    "cocof": "its documents are a Plone faceted search loaded by script, with no list "
             "or feed to read; not built yet (a small assembly, few decrees)",
    "vgc": "the VGC council publishes regulations and minutes as PDFs on vgc.be only; "
           "not built yet",
}
PARTIAL = {
    "fwb": "the full document index is an Algolia search whose key sits in the site's "
           "code (not used); read instead: the newest-documents page (18 cards) and the "
           "plenary agendas, so a busy week's older documents can be missed",
}


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)


_WATCH = {}


def watchlist(path=None):
    """{doc_key: (areas, why)} from the `regions` section of
    config/watchlist-be.yaml (the federal dossiers stay under `dossiers`)."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-be.yaml")
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {str(k): (list((v or {}).get("areas") or []), (v or {}).get("why"))
                        for k, v in (raw.get("regions") or {}).items()}
    return _WATCH[path]


def add_watch_areas(res, doc_key, path=None):
    """Union a watched document's areas into a FilterResult, in place."""
    hit = watchlist(path).get(doc_key)
    if not hit:
        return res
    areas, _why = hit
    res.issue_areas = sorted(set(res.issue_areas or []) | set(areas))
    res.watchlist_hits = list(res.watchlist_hits or []) + ["watch:" + doc_key]
    if res.tier is None:
        res.tier = 2
    return res


def reads(conn):
    """{parliament: row} from ber_reads ({} when the table is missing)."""
    try:
        return {r[0]: r for r in conn.execute(
            "SELECT parliament, last_read, last_ok, rows_seen, rows_ours, note FROM ber_reads")}
    except Exception:            # an old store without the table
        return {}
