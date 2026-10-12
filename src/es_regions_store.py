"""Tables for Spain's regional layer (12 October 2026): the seventeen
autonomous communities' laws, as the BOE publishes them, and the bills in
passage in the regional parliaments whose own sites give a usable list.

See docs/spain-regions-scope.md for what was measured and why. The schema
follows src/es_store.py: its own module, idempotent statements, created by
db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/es_regions.py writes these
tables, and nothing here touches another jurisdiction's table.

TWO LAYERS, TWO KEYS.

  * esr_laws: one row per regional act in section I of the BOE
    ("Disposiciones generales"), under the department of its community.
    Keyed on the BOE's own identifier ('BOE-A-2026-20746'), never a title.
    The BOE publishes every community's laws in Spanish, whatever the
    community's own languages, so this layer is classified with the Spanish
    list for all seventeen. It is the one platform that serves every region,
    and it is late by design: a law reaches the BOE weeks after the regional
    bulletin (Asturias' Ley 6/2026 of 10 September appeared on 6 October).
  * esr_bills: one row per bill a regional parliament lists as in passage,
    keyed '<region>:<the parliament's own expediente>' ('an:13-26/PPL-000002',
    'cn:11L/PL-0012'). The lists are snapshots: a bill is new when first seen,
    and `last_seen` stops moving once it leaves the list (passed, rejected,
    withdrawn or lapsed; the law then arrives through the BOE layer). A
    source's first read lists every bill already in passage: those rows are
    marked `seed` and count as new only by their own `presented` date, so
    the first edition is not a flood of old bills.

CO-OFFICIAL LANGUAGES. `lang` is the language the title is published in:
'es' is classified with the Spanish list (config/taxonomy-es.yaml); any
other ('ca' for Valencian and Catalan, 'eu', 'gl') is stored with areas
NULL, unclassified rather than "nothing found", and counted under the
edition's Coverage as a gap, never shown as an item on our ground.

AREAS. NULL means unclassified, '[]' classified and on nobody's ground.
"""

from __future__ import annotations

import json

# The seventeen communities, by the code this layer uses, in the order of
# docs/spain-regions-scope.md's ranking (population, then source quality).
REGIONS = {
    "an": "Andalucía",
    "ct": "Cataluña",
    "md": "Madrid",
    "vc": "Comunitat Valenciana",
    "ga": "Galicia",
    "cl": "Castilla y León",
    "pv": "País Vasco",
    "cn": "Canarias",
    "cm": "Castilla-La Mancha",
    "mc": "Región de Murcia",
    "ar": "Aragón",
    "ib": "Illes Balears",
    "ex": "Extremadura",
    "as": "Asturias",
    "nc": "Navarra",
    "cb": "Cantabria",
    "ri": "La Rioja",
}

# The parliament of each, as the edition names it.
PARLIAMENTS = {
    "an": "Parlamento de Andalucía",
    "ct": "Parlament de Catalunya",
    "md": "Asamblea de Madrid",
    "vc": "Corts Valencianes",
    "ga": "Parlamento de Galicia",
    "cl": "Cortes de Castilla y León",
    "pv": "Parlamento Vasco",
    "cn": "Parlamento de Canarias",
    "cm": "Cortes de Castilla-La Mancha",
    "mc": "Asamblea Regional de Murcia",
    "ar": "Cortes de Aragón",
    "ib": "Parlament de les Illes Balears",
    "ex": "Asamblea de Extremadura",
    "as": "Junta General del Principado de Asturias",
    "nc": "Parlamento de Navarra",
    "cb": "Parlamento de Cantabria",
    "ri": "Parlamento de La Rioja",
}

# A BOE department name (accents folded, upper case) to a region code, by
# the distinctive word in it. The BOE's department codes are stored too, but
# the name is the published, readable key: 'COMUNIDAD AUTÓNOMA DE ANDALUCÍA'
# (8010), 'COMUNIDAD DE CASTILLA Y LEÓN' (9531), 'COMUNIDAD FORAL DE
# NAVARRA' (8170). Ceuta and Melilla ('CIUDAD DE ...') have assemblies
# without legislative power and are left out.
BOE_DEPARTMENTS = (
    ("ANDALUCIA", "an"),
    ("CATALUNA", "ct"),
    ("MADRID", "md"),
    ("VALENCIANA", "vc"),
    ("GALICIA", "ga"),
    ("CASTILLA Y LEON", "cl"),
    ("PAIS VASCO", "pv"),
    ("CANARIAS", "cn"),
    ("CASTILLA-LA MANCHA", "cm"),
    ("CASTILLA LA MANCHA", "cm"),
    ("MURCIA", "mc"),
    ("ARAGON", "ar"),
    ("BALEARS", "ib"),
    ("BALEARES", "ib"),
    ("EXTREMADURA", "ex"),
    ("ASTURIAS", "as"),
    ("NAVARRA", "nc"),
    ("CANTABRIA", "cb"),
    ("RIOJA", "ri"),
)

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS esr_laws (
        boe_id       TEXT PRIMARY KEY,    -- 'BOE-A-2026-20746'
        region       TEXT NOT NULL,       -- 'as', see REGIONS
        department   TEXT,                -- the BOE's department code, '8150'
        published    TEXT,                -- ISO date of the BOE issue
        rank         TEXT,                -- 'ley', 'decreto-ley', 'decreto legislativo', 'decreto', 'other'
        title        TEXT,                -- the BOE's title, verbatim
        heading      TEXT,                -- the BOE's subject heading ('Medio ambiente')
        url_html     TEXT,
        url_pdf      TEXT,
        areas        TEXT,                -- JSON list, NULL = unclassified
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS esr_bills (
        bill_key     TEXT PRIMARY KEY,    -- 'an:13-26/PPL-000002'
        region       TEXT NOT NULL,
        expediente   TEXT NOT NULL,       -- the parliament's own number, as printed
        kind         TEXT,                -- 'proyecto de ley', 'proposición de ley', 'decreto-ley', 'ilp', ...
        title        TEXT,                -- as printed, whitespace folded
        status       TEXT,                -- the parliament's own words, when it gives any
        presented    TEXT,                -- ISO date, when the list gives one
        proponent    TEXT,
        url          TEXT,
        lang         TEXT NOT NULL DEFAULT 'es',   -- the title's language; see the docstring
        areas        TEXT,                -- JSON list, NULL = unclassified
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,                -- ISO date first listed: "new" in the edition
        last_seen    TEXT,                -- ISO date last listed
        seed         INTEGER              -- 1: first listed on the source's FIRST read, so
                                          -- not "new" unless `presented` says so
    )""",
    """CREATE TABLE IF NOT EXISTS esr_reads (
        source       TEXT PRIMARY KEY,    -- 'boe', 'an', 'cn', ...
        last_seen    TEXT,                -- ISO date of the last read, ok or not (status says)
        last_day     TEXT,                -- BOE: the newest issue date read
        items        INTEGER,             -- rows the last read listed
        status       TEXT                 -- 'ok', or the last failure, short
    )""",
    "CREATE INDEX IF NOT EXISTS esr_laws_region ON esr_laws (region, published)",
    "CREATE INDEX IF NOT EXISTS esr_bills_region ON esr_bills (region, first_seen)",
)

TABLES = ("esr_laws", "esr_bills", "esr_reads")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
