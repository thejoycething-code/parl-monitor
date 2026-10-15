"""Tables for Brazil's STATE ASSEMBLIES (regional layer, 13 October 2026):
the 26 Assembleias Legislativas and the Câmara Legislativa do Distrito
Federal, from tools/br_states.py. Every table is prefixed `brs_`.

See docs/brazil-regions-scope.md for what was measured, assembly by
assembly, and why only some are read. The schema follows src/mxs_store.py
and src/es_regions_store.py: its own module, idempotent statements, created
by db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/br_states.py writes these
tables, and nothing here touches the National Congress's br_* tables or any
other jurisdiction's.

KEYS, NEVER TITLES. A bill is '<uf>/<the assembly's own type> <number>/<year>':
'sp/PL 652/2026', 'mg/PEC 41/2026', 'rj/PL 8397/2026', 'ro/PLO 1541/2026'.
The type is the assembly's own abbreviation (ALESP's sgNatureza, ALMG's and
ALERJ's printed one, a SAPL house's tipo sigla), so a key reads as the
assembly prints the bill. config/watchlist-br-states.yaml is keyed the same
way. `source_id` keeps the assembly's internal id (ALESP IdDocumento, SAPL
materia id, ALERJ Notes code) for links and joins.

WHAT IS STORED. Every bill a source lists (PL, PLC, PEC, PDL and their
local equivalents; never indicações, requerimentos or moções), on our ground
or not, so `--reclassify` can apply a taxonomy change offline. Titles are
the assembly's own words, verbatim. Areas come from config/taxonomy-pt.yaml
(country 'br') and the watchlist, by key. NULL areas mean unclassified,
'[]' classified and on nobody's ground.

ADOPTED LAWS. Where an assembly's bills cannot be read, the laws it passed
are read from the state's own legislation portal (Goiás, Paraná):
one row per law, keyed '<uf>/<Lei|LC|EC> <number>/<year>' ('pr/Lei
23448/2026'), its publication date as `presented`, `source` naming the
route (VIA below), so the edition shows it the week it is published.

VOTES. brs_votes holds one row per recorded vote ON A BILL STORED HERE:
ALESP's committee votes (each member's vote is published, brs_positions)
and the SAPL houses' plenary tallies (registrovotacao: yes, no, abstentions
and the result; no names); ALMG's plenary results from its open-data API
(15 October 2026: the result only, keyed 'mg/p<meeting id>/<bill> <n>/<year>/<order>'). Only votes on bills on our ground or watched
keep positions, so the store stays small.

MEMBERS. brs_members: a deputy's name and party as the source prints them
(ALESP deputados.xml, ALMG's API deputies and authors keyed 'mg/<ALMG id>'
(its website route keys authors by name), a SAPL house's autor), nothing
else: no biography, contact or family details are read into the store.
"""

from __future__ import annotations

import json
import os

# The 27 federative units, by the lower-case UF code used in keys.
STATES = {
    "ac": "Acre", "al": "Alagoas", "ap": "Amapá", "am": "Amazonas", "ba": "Bahia",
    "ce": "Ceará", "df": "Distrito Federal", "es": "Espírito Santo", "go": "Goiás",
    "ma": "Maranhão", "mt": "Mato Grosso", "ms": "Mato Grosso do Sul",
    "mg": "Minas Gerais", "pa": "Pará", "pb": "Paraíba", "pr": "Paraná",
    "pe": "Pernambuco", "pi": "Piauí", "rj": "Rio de Janeiro",
    "rn": "Rio Grande do Norte", "rs": "Rio Grande do Sul", "ro": "Rondônia",
    "rr": "Roraima", "sc": "Santa Catarina", "sp": "São Paulo", "se": "Sergipe",
    "to": "Tocantins",
}

# Each assembly's own short name, as the edition prints it.
ASSEMBLIES = {
    "ac": "ALEAC", "al": "ALE-AL", "ap": "ALAP", "am": "ALEAM", "ba": "ALBA",
    "ce": "ALECE", "df": "CLDF", "es": "ALES", "go": "ALEGO", "ma": "ALEMA",
    "mt": "ALMT", "ms": "ALEMS", "mg": "ALMG", "pa": "ALEPA", "pb": "ALPB",
    "pr": "ALEP", "pe": "ALEPE", "pi": "ALEPI", "rj": "ALERJ", "rn": "ALRN",
    "rs": "ALRS", "ro": "ALERO", "rr": "ALE-RR", "sc": "ALESC", "sp": "ALESP",
    "se": "ALESE", "to": "ALETO",
}

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS brs_bills (
        bill_key     TEXT PRIMARY KEY,   -- 'sp/PL 652/2026'
        uf           TEXT NOT NULL,      -- 'sp', see STATES
        source       TEXT NOT NULL,      -- 'sp', 'mg', 'rj', 'sapl', or an alternative route (VIA)
        source_id    TEXT,               -- the assembly's own internal id
        kind         TEXT,               -- the assembly's type abbreviation: 'PL', 'PLC', 'PEC', 'PLO' ...
        kind_name    TEXT,               -- its name: 'Projeto de lei Complementar'
        number       INTEGER,
        year         INTEGER,
        title        TEXT,               -- the ementa, verbatim
        authors      TEXT,               -- 'Name (PARTY); Name', as printed
        presented    TEXT,               -- ISO date presented / published, when the source gives one
        status       TEXT,               -- the source's own words for where it stands
        status_date  TEXT,               -- ISO date of that status; see below
        committees   TEXT,               -- committees it was sent to, as printed
        url          TEXT,
        areas        TEXT,               -- JSON list, NULL = unclassified
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT,
        seed         INTEGER             -- 1: listed on the source's FIRST read (the backlog)
    )""",
    # status_date: the source's own date for the status where it prints one
    # (ALESP's andamento, a SAPL tramitação); otherwise the day a run first
    # saw the status CHANGE (never on a bill's first sighting).
    """CREATE TABLE IF NOT EXISTS brs_votes (
        vote_key     TEXT PRIMARY KEY,   -- 'sp/c<IdReuniao>/<IdDocumento>', 'ro/v<registro id>'
        uf           TEXT NOT NULL,
        bill_key     TEXT NOT NULL,
        date         TEXT,               -- ISO date
        body         TEXT,               -- 'plenary' or the committee's name
        description  TEXT,               -- the source's own words
        result       TEXT,               -- as printed: 'APROVADO', 'Aprovado', 'Rejeitado o Veto'
        yes          INTEGER,
        no           INTEGER,
        abstain      INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    ) WITHOUT ROWID""",
    """CREATE TABLE IF NOT EXISTS brs_positions (
        vote_key     TEXT NOT NULL,
        member       TEXT NOT NULL,      -- the name as the source prints it
        party        TEXT,               -- from the source's member list, when known
        position     TEXT,               -- as printed: 'Favorável ao parecer', 'Contrário' ...
        PRIMARY KEY (vote_key, member)
    ) WITHOUT ROWID""",
    """CREATE TABLE IF NOT EXISTS brs_members (
        member_key   TEXT PRIMARY KEY,   -- '<uf>/<source id>' or '<uf>/name:<name>'
        uf           TEXT NOT NULL,
        name         TEXT,
        party        TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    # One row per source per run: what it did. A source not read (blocked,
    # unreachable) has a row too, so the edition can say so.
    """CREATE TABLE IF NOT EXISTS brs_reads (
        source       TEXT PRIMARY KEY,   -- 'sp', 'mg', 'rj', 'sapl:ro' ...
        uf           TEXT,
        status       TEXT,               -- 'ok' / 'gap' / 'unreachable' / 'blocked'
        detail       TEXT,               -- why, in a line
        items        INTEGER,            -- bills the source listed this run
        new_items    INTEGER,            -- of those, new to the store
        data_through TEXT,               -- the newest date the source showed
        meta         TEXT,               -- JSON: a source's own bookkeeping (SAPL types, last meeting)
        read_at      TEXT,
        last_ok      TEXT,
        last_seen    TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS brs_bills_uf ON brs_bills (uf, presented)",
    "CREATE INDEX IF NOT EXISTS brs_votes_bill ON brs_votes (bill_key)",
)

TABLES = ("brs_bills", "brs_votes", "brs_positions", "brs_members", "brs_reads")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)


def bill_key(uf, kind, number, year):
    return "{0}/{1} {2}/{3}".format(uf, kind, int(number), int(year))


def assembly(uf):
    """'ALESP (São Paulo)'."""
    return "{0} ({1})".format(ASSEMBLIES.get(uf, uf.upper()), STATES.get(uf, uf))


# Where an item came from when it is not the assembly's own bill system: the
# edition adds "(via ...)" to its line (13 October 2026, the alternative
# routes of tools/br_states.py). Keyed by brs_bills.source.
VIA = {
    "rn": "ALRN's Transparência Legislativa data",
    "ce": "ALECE's proposições lists",
    "pe": "ALEPE's open-data API",
    "pa": "ALEPA's proposições search",
    "go": "the Goiás Casa Civil's legislation portal: adopted law",
    "pr": "the Paraná Casa Civil's Sistema Estadual de Legislação: adopted law",
    # The one plain-HTTP source (src/http.PLAIN_HTTP_EXCEPTIONS, Chris, 13
    # October 2026): every item says so.
    "alep": "ALEP open data, unencrypted",
    # GitHub-only (tools/br_states.py fetch_sc, 13 October 2026).
    "sc": "ALESC's e-Legis portal, read from GitHub",
}

# What the coverage line adds after an assembly's name, per source.
READ_NOTES = {"go": "adopted laws only", "pr": "adopted laws only",
              "alep": "bills via open data, unencrypted"}


# Routes that read the laws an assembly passed, not its bills.
LAWS_ONLY = ("go", "pr")


def via(source):
    """'(via ALEPE's open-data API)', or '' for an assembly's own system."""
    return "(via {0})".format(VIA[source]) if source in VIA else ""


# --- the watchlist, applied by bill KEY ----------------------------------------

_WATCH = {}
WATCH_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "config", "watchlist-br-states.yaml")


def watchlist(path=None):
    """{bill_key: {"areas": [...], "why": str}} from config/watchlist-br-states.yaml."""
    import yaml
    path = path or WATCH_PATH
    if path not in _WATCH:
        raw = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {str(k): {"areas": list((v or {}).get("areas") or []),
                                 "why": (v or {}).get("why")}
                        for k, v in (raw.get("bills") or {}).items()}
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


# --- writes ------------------------------------------------------------------------

def upsert_bill(conn, b, areas, terms, tier, today, seed):
    """Store one bill (a dict from a reader). Returns (new, status_changed)."""
    old = conn.execute("SELECT status, status_date FROM brs_bills WHERE bill_key=?",
                       (b["bill_key"],)).fetchone()
    new = old is None
    status_date = b.get("status_date")
    changed = False
    if not new and b.get("status") and (old[0] or "") != b["status"]:
        changed = True
        if not status_date:
            status_date = today
    conn.execute(
        "INSERT INTO brs_bills (bill_key, uf, source, source_id, kind, kind_name, number, year, "
        "title, authors, presented, status, status_date, committees, url, areas, matched_terms, "
        "tier, first_seen, last_seen, seed) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(bill_key) DO UPDATE SET source_id=COALESCE(excluded.source_id, brs_bills.source_id), "
        "kind_name=COALESCE(excluded.kind_name, brs_bills.kind_name), "
        "title=COALESCE(excluded.title, brs_bills.title), "
        "authors=COALESCE(excluded.authors, brs_bills.authors), "
        "presented=COALESCE(excluded.presented, brs_bills.presented), "
        "status=COALESCE(excluded.status, brs_bills.status), "
        "status_date=COALESCE(excluded.status_date, brs_bills.status_date), "
        "committees=COALESCE(excluded.committees, brs_bills.committees), "
        "url=COALESCE(excluded.url, brs_bills.url), areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (b["bill_key"], b["uf"], b["source"], b.get("source_id"), b.get("kind"), b.get("kind_name"),
         b.get("number"), b.get("year"), b.get("title"), b.get("authors"), b.get("presented"),
         b.get("status"), status_date if (new or changed or b.get("status_date")) else None,
         b.get("committees"), b.get("url"), None if areas is None else dumps(areas),
         dumps(terms), tier, today, today, 1 if (new and seed) else 0))
    return new, changed


def upsert_vote(conn, v, today):
    conn.execute(
        "INSERT INTO brs_votes (vote_key, uf, bill_key, date, body, description, result, yes, no, "
        "abstain, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(vote_key) DO UPDATE SET date=excluded.date, body=excluded.body, "
        "description=excluded.description, result=COALESCE(excluded.result, brs_votes.result), "
        "yes=excluded.yes, no=excluded.no, abstain=excluded.abstain, last_seen=excluded.last_seen",
        (v["vote_key"], v["uf"], v["bill_key"], v.get("date"), v.get("body"), v.get("description"),
         v.get("result"), v.get("yes"), v.get("no"), v.get("abstain"), today, today))


def replace_positions(conn, vote_key, rows):
    conn.execute("DELETE FROM brs_positions WHERE vote_key=?", (vote_key,))
    conn.executemany("INSERT OR REPLACE INTO brs_positions (vote_key, member, party, position) "
                     "VALUES (?,?,?,?)", [(vote_key, m, p, pos) for m, p, pos in rows])


def upsert_member(conn, member_key, uf, name, party, today):
    conn.execute(
        "INSERT INTO brs_members (member_key, uf, name, party, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?) ON CONFLICT(member_key) DO UPDATE SET "
        "name=COALESCE(excluded.name, brs_members.name), "
        "party=COALESCE(excluded.party, brs_members.party), last_seen=excluded.last_seen",
        (member_key, uf, name, party, today, today))


def record_read(conn, source, uf, status, detail, items, new_items, through, now, meta=None):
    conn.execute(
        "INSERT INTO brs_reads (source, uf, status, detail, items, new_items, data_through, meta, "
        "read_at, last_ok, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(source) DO UPDATE SET uf=excluded.uf, status=excluded.status, "
        "detail=excluded.detail, items=excluded.items, new_items=excluded.new_items, "
        "data_through=COALESCE(excluded.data_through, brs_reads.data_through), "
        "meta=COALESCE(excluded.meta, brs_reads.meta), read_at=excluded.read_at, "
        "last_ok=COALESCE(excluded.last_ok, brs_reads.last_ok), last_seen=excluded.last_seen",
        (source, uf, status, detail, items, new_items, through,
         None if meta is None else json.dumps(meta, ensure_ascii=False), now,
         now if status == "ok" else None, now[:10]))


def read_meta(conn, source):
    row = conn.execute("SELECT meta FROM brs_reads WHERE source=?", (source,)).fetchone()
    try:
        return json.loads(row[0]) if row and row[0] else {}
    except ValueError:
        return {}
