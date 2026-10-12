"""Tables for Argentina's provincial layer (13 October 2026): the 24
jurisdictions' adopted laws, and the bills in passage in the provincial
legislatures whose own sites give a usable list.

See docs/argentina-regions-scope.md for what was measured and why. The
schema follows src/es_regions_store.py: its own module, idempotent
statements, created by db.init_db so every store carries it and db.TABLES
stays true.

SEPARATION GUARANTEE. Nothing outside tools/ar_regions.py writes these
tables, and nothing here touches another jurisdiction's table (the national
Congress lives in ar_* tables, src/ar_store.py).

TWO LAYERS, TWO KEYS.

  * arp_laws: one row per provincial law. SAIJ (the Ministry of Justice's
    Sistema Argentino de Información Jurídica) indexes every province's
    laws, with the official title, a sumario and the date of the Boletín
    Oficial that published it: the one platform that serves all 24, late by
    one to three weeks. Buenos Aires province's own normative system
    (normas.gba.gob.ar, the Boletín Oficial's) and Córdoba's list of
    approved texts are read too, and meet SAIJ on the same key:
    '<province>/ley/<number>' ('ba/ley/15625', 'cba/ley/11108'). A law
    number is unique within a province.
  * arp_bills: one row per expediente a legislature lists, keyed
    '<legislature>:<the legislature's own number>' ('caba:3199-D-2026',
    'ba-dip:D-3281/26-27', 'cba:47972/L/26', 'er-sen:34495'). The lists are
    snapshots: a bill is new when first seen (or by its own `presented`
    date when the list gives one), and `status` is overwritten with the
    legislature's latest words on every read; when those words change,
    `moved` takes the day and `prev_status` the old words (a stage move). A source's first read is a
    seed: those rows count as new only by their own `presented` date.

AREAS. NULL means unclassified, '[]' classified and on nobody's ground.
"""

from __future__ import annotations

import json

# The 24 jurisdictions, by the code this layer uses, in the order of
# docs/argentina-regions-scope.md's ranking (population, then sources).
PROVINCES = {
    "ba": "Buenos Aires",
    "caba": "Ciudad Autónoma de Buenos Aires",
    "cba": "Córdoba",
    "sf": "Santa Fe",
    "mza": "Mendoza",
    "tuc": "Tucumán",
    "er": "Entre Ríos",
    "sal": "Salta",
    "mis": "Misiones",
    "cha": "Chaco",
    "ctes": "Corrientes",
    "sde": "Santiago del Estero",
    "sj": "San Juan",
    "juj": "Jujuy",
    "rn": "Río Negro",
    "nqn": "Neuquén",
    "fsa": "Formosa",
    "chu": "Chubut",
    "sl": "San Luis",
    "cat": "Catamarca",
    "lr": "La Rioja",
    "lp": "La Pampa",
    "sc": "Santa Cruz",
    "tdf": "Tierra del Fuego",
}

# SAIJ's `provincia` field, accents folded, upper case, to a code.
SAIJ_PROVINCES = {
    "BUENOS AIRES": "ba",
    "CIUDAD AUTONOMA DE BUENOS AIRES": "caba",
    "CORDOBA": "cba",
    "SANTA FE": "sf",
    "MENDOZA": "mza",
    "TUCUMAN": "tuc",
    "ENTRE RIOS": "er",
    "SALTA": "sal",
    "MISIONES": "mis",
    "CHACO": "cha",
    "CORRIENTES": "ctes",
    "SANTIAGO DEL ESTERO": "sde",
    "SAN JUAN": "sj",
    "JUJUY": "juj",
    "RIO NEGRO": "rn",
    "NEUQUEN": "nqn",
    "FORMOSA": "fsa",
    "CHUBUT": "chu",
    "SAN LUIS": "sl",
    "CATAMARCA": "cat",
    "LA RIOJA": "lr",
    "LA PAMPA": "lp",
    "SANTA CRUZ": "sc",
    "TIERRA DEL FUEGO": "tdf",
    "TIERRA DEL FUEGO, ANTARTIDA E ISLAS DEL ATLANTICO SUR": "tdf",
}

# The legislatures (chambers) whose bills are read, as the edition names them.
LEGISLATURES = {
    "ba-dip": "Cámara de Diputados de la Provincia de Buenos Aires",
    "caba": "Legislatura de la Ciudad Autónoma de Buenos Aires",
    "cba": "Legislatura de la Provincia de Córdoba",
    "er-sen": "Cámara de Senadores de Entre Ríos",
}

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS arp_laws (
        law_key      TEXT PRIMARY KEY,    -- 'ba/ley/15625'
        province     TEXT NOT NULL,       -- 'ba', see PROVINCES
        number       INTEGER,
        sanctioned   TEXT,                -- ISO date SAIJ gives the law (sanction or promulgation)
        published    TEXT,                -- ISO date of the Boletín Oficial, when known
        title        TEXT,                -- the official title (SAIJ titulo-norma) or the summary
        summary      TEXT,                -- SAIJ's sumario, or the source's own summary
        descriptors  TEXT,                -- JSON list of SAIJ thesaurus terms (shown, not classified)
        url          TEXT,
        source       TEXT,                -- 'saij', 'normas-gba', 'cba-gld', joined with '+'
        areas        TEXT,                -- JSON list, NULL = unclassified
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS arp_bills (
        bill_key     TEXT PRIMARY KEY,    -- 'caba:3199-D-2026'
        legislature  TEXT NOT NULL,       -- 'caba', see LEGISLATURES
        province     TEXT NOT NULL,
        expediente   TEXT NOT NULL,       -- the legislature's own number, as printed
        kind         TEXT,                -- 'ley', 'resolucion', 'declaracion', 'comunicacion', ...
        title        TEXT,                -- the extracto / sumario, whitespace folded
        author       TEXT,
        status       TEXT,                -- the legislature's own words, latest read
        committee    TEXT,
        presented    TEXT,                -- ISO date, when the list gives one
        sanctioned   INTEGER,             -- 1 when the list says it was sanctioned/approved
        url          TEXT,
        areas        TEXT,
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT,
        seed         INTEGER,             -- 1: first listed on the source's FIRST read
        moved        TEXT,                -- ISO date `status` last changed (not on first sight)
        prev_status  TEXT                 -- the status before that change
    )""",
    """CREATE TABLE IF NOT EXISTS arp_reads (
        source       TEXT PRIMARY KEY,    -- 'saij', 'normas-gba', 'ba-dip', 'caba', 'cba', 'er-sen'
        last_seen    TEXT,                -- ISO date of the last read, ok or not
        items        INTEGER,             -- rows the last read listed
        status       TEXT,                -- 'ok', or the last failure, short
        cursor       TEXT                 -- source-specific: Córdoba's sessions already read (JSON)
    )""",
    "CREATE INDEX IF NOT EXISTS arp_laws_province ON arp_laws (province, published)",
    "CREATE INDEX IF NOT EXISTS arp_bills_leg ON arp_bills (legislature, first_seen)",
)

TABLES = ("arp_laws", "arp_bills", "arp_reads")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
