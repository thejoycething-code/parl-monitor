"""Tables for the Netherlands monitor (phase 1, 9 October 2026): the Tweede
Kamer's parliamentary groups (fracties), its members, the zaken it voted on
and every recorded position on every vote.

See docs/netherlands-scope.md for what was measured and why. The schema
follows the US precedent (src/us_store.py): its own module, idempotent
statements, created by db.init_db so every store carries it and db.TABLES
stays true.

SEPARATION GUARANTEE. Nothing outside tools/nl_*.py writes these tables,
and nothing here touches another jurisdiction's table.

KEYS. Everything the Tweede Kamer's Open Data Portaal serves carries a GUID
`Id`, and those are the keys here, with one exception: a zaak is keyed on
its zaaknummer ('2026Z21728'). It is the number printed on every motion and
amendment, it is unique across years (the year is in it), and it is what a
human copies into config/watchlist-nl.yaml. The GUID is kept beside it.

A Kamerstuk DOSSIER ('36390', or '36800-XVI' for one chapter of the budget)
is what a Dutch bill is: every amendment and motion on the bill is a zaak
filed in the bill's dossier. The watchlist keys on dossier numbers or
zaaknummers, NEVER on titles: "Wijziging van de Embryowet" is the title of
four different dossiers.

MOST DUTCH VOTES ARE BY PARTY. A vote "met handopsteken" (show of hands)
records one position per fractie, with its seat count (`zetels`); a
"hoofdelijke stemming" (roll call) records one per member. `nl_votes.kind`
says which, and the party is stored PER VOTE, as everywhere in this repo.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS nl_fracties (
        fractie_id   TEXT PRIMARY KEY,   -- the portal's GUID
        afkorting    TEXT,               -- 'VVD', 'CDA', 'Groep Markuszower'
        naam         TEXT,
        zetels       INTEGER,            -- seats today
        actief_van   TEXT,
        actief_tot   TEXT,               -- NULL while the group exists
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS nl_members (
        persoon_id   TEXT PRIMARY KEY,   -- the portal's GUID
        name         TEXT,               -- 'Kati Piri': roepnaam, tussenvoegsel, achternaam
        fractie      TEXT,               -- latest seen; see nl_votes.fractie
        functie      TEXT,               -- 'Lid', 'Fractievoorzitter'
        seat_from    TEXT,               -- start of the current seat
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS nl_zaken (
        zaak_nummer  TEXT PRIMARY KEY,   -- '2026Z21728'
        zaak_id      TEXT,               -- the portal's GUID
        soort        TEXT,               -- 'Motie', 'Amendement', 'Wetgeving', ...
        onderwerp    TEXT,               -- 'Motie van het lid Piri c.s. over ...'
        titel        TEXT,               -- usually the dossier's title
        dossiers     TEXT,               -- JSON list: ['21501-02']
        dossier_titels TEXT,             -- JSON list, same order
        gestart      TEXT,               -- ISO date
        kabinetsappreciatie TEXT,        -- the government's advice on a motion
        afgedaan     INTEGER,
        own_areas    TEXT,               -- JSON: matched on onderwerp alone
        areas        TEXT,               -- JSON: + titel, dossier titles, watchlist-nl
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS nl_divisions (
        besluit_id   TEXT PRIMARY KEY,   -- the portal's GUID for the decision
        zaak_nummer  TEXT,               -- what was voted on
        date         TEXT,               -- ISO date of the voting sitting
        stemmingssoort TEXT,             -- 'Met handopsteken' / 'Hoofdelijk'
        besluit_soort TEXT,              -- 'Stemmen - aangenomen' / 'Stemmen - verworpen'
        besluit_tekst TEXT,              -- the Kamer's own words: 'Aangenomen (90-36).'
        agendapunt   TEXT,               -- agenda item heading
        voor         INTEGER,            -- seats (party vote) or members (roll call)
        tegen        INTEGER,
        niet_deelgenomen INTEGER,
        positions_pending INTEGER,       -- 1 while the portal has no positions yet
        areas        TEXT,               -- JSON: the zaak's areas
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS nl_votes (
        stemming_id  TEXT PRIMARY KEY,   -- the portal's GUID for one position
        besluit_id   TEXT NOT NULL,
        kind         TEXT,               -- 'fractie' (show of hands) / 'lid' (roll call)
        fractie      TEXT,               -- AT THE VOTE
        fractie_id   TEXT,
        persoon_id   TEXT,               -- roll calls only
        actor        TEXT,               -- as printed: 'VVD', or the member's surname
        position     TEXT,               -- 'Voor' / 'Tegen' / 'Niet deelgenomen'
        zetels       INTEGER,            -- the group's seats, show of hands only
        vergissing   INTEGER             -- 1 when the group declared the vote a mistake
    )""",
    "CREATE INDEX IF NOT EXISTS nl_votes_besluit ON nl_votes (besluit_id)",
    "CREATE INDEX IF NOT EXISTS nl_votes_persoon ON nl_votes (persoon_id)",
    "CREATE INDEX IF NOT EXISTS nl_divisions_zaak ON nl_divisions (zaak_nummer)",
)

TABLES = ("nl_fracties", "nl_members", "nl_zaken", "nl_divisions", "nl_votes")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- the Dutch watchlist, applied by dossier number or zaaknummer ----------

_WATCH = {}


def watchlist_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "config", "watchlist-nl.yaml")


def watchlist(path=None):
    """{'dossiers': {key: (areas, why)}, 'zaken': {key: (areas, why)}}."""
    import yaml
    path = path or watchlist_path()
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {
            group: {str(k): (list((v or {}).get("areas") or []), (v or {}).get("why"))
                    for k, v in (raw.get(group) or {}).items()}
            for group in ("dossiers", "zaken")}
    return _WATCH[path]


def add_watch_areas(res, zaak_nummer, dossier_keys, path=None):
    """Union a watched zaak's or dossier's areas into a FilterResult, in place,
    and say so in watchlist_hits so the stored row shows where they came from."""
    wl = watchlist(path)
    hits = []
    if zaak_nummer in wl["zaken"]:
        hits.append(("zaak:" + zaak_nummer, wl["zaken"][zaak_nummer][0]))
    for key in dossier_keys or []:
        if key in wl["dossiers"]:
            hits.append(("dossier:" + key, wl["dossiers"][key][0]))
    for label, areas in hits:
        res.issue_areas = sorted(set(res.issue_areas or []) | set(areas))
        res.watchlist_hits = list(res.watchlist_hits or []) + ["watch:" + label]
    if hits and res.tier is None:
        res.tier = 2
    return res


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
