"""Tables for the Netherlands monitor (phase 1, 9 October 2026): the Tweede
Kamer's parliamentary groups (fracties), its members, the zaken it voted on
and every recorded position on every vote.

See docs/netherlands-scope.md for what was measured and why. The schema
follows the US precedent (src/us_store.py): its own module, idempotent
statements, created by db.init_db so every store carries it and db.TABLES
stays true.

THE EERSTE KAMER (NL4, added 10 October 2026, additively): nl_ek_bills,
nl_ek_divisions and nl_ek_votes, written by tools/nl_eerstekamer.py from
eerstekamer.nl's vote pages. Separate tables, because the Senate has no
zaaknummers and its show-of-hands votes name fracties only.

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
    # --- the Eerste Kamer (NL4, 10 October 2026; tools/nl_eerstekamer.py) ------
    # Read from eerstekamer.nl's "Stemmingen per vergaderdag" pages: no API
    # exists. Keyed by sitting date and Kamerstuk reference, never by title.
    """CREATE TABLE IF NOT EXISTS nl_ek_bills (
        dossier      TEXT PRIMARY KEY,   -- Kamerstuk number as printed: '36791', '36945-I'
        title        TEXT,               -- the bill's title on the vote list
        url          TEXT,               -- its eerstekamer.nl page
        last_vote    TEXT,               -- ISO date of the latest vote seen on it
        last_result  TEXT,               -- 'aangenomen' / 'verworpen', the Kamer's word
        areas        TEXT,               -- JSON: taxonomy-nl + watchlist-nl by dossier
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS nl_ek_divisions (
        division_key TEXT PRIMARY KEY,   -- 'ek-20261006-37020-M' (date + Kamerstuk reference)
        date         TEXT NOT NULL,
        kind         TEXT,               -- 'bill' / 'motion' / 'amendment' / 'other'
        dossier      TEXT,               -- '37020'; what the watchlist is keyed on
        ref          TEXT,               -- '37020-M', '36791', 'CLXXVII-F'
        title        TEXT,               -- as printed: 'Motie-Beukering (...) over ...'
        url          TEXT,
        method       TEXT,               -- 'Stemming bij zitten en opstaan' / 'Hoofdelijke stemming' / 'Hamerstuk'
        result       TEXT,               -- 'aangenomen' / 'verworpen', the Kamer's word
        roll_call    INTEGER,            -- 1: every senator recorded by name
        voor         INTEGER,            -- roll call only: senators for
        tegen        INTEGER,            -- roll call only: senators against
        aantekening  TEXT,               -- JSON: fracties recording dissent on a hamerstuk
        own_areas    TEXT,
        areas        TEXT,               -- JSON: own + the bill's (motions on a bill dossier)
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS nl_ek_votes (
        division_key TEXT NOT NULL,
        kind         TEXT NOT NULL,      -- 'fractie' (show of hands) / 'lid' (roll call)
        actor        TEXT NOT NULL,      -- the fractie, or the senator's name as printed
        fractie      TEXT,               -- the senator's fractie AT THE VOTE, as printed
        position     TEXT,               -- 'voor' / 'tegen' / 'aantekening'
        PRIMARY KEY (division_key, kind, actor)
    )""",
    "CREATE INDEX IF NOT EXISTS nl_ek_divisions_dossier ON nl_ek_divisions (dossier)",
)

TABLES = ("nl_fracties", "nl_members", "nl_zaken", "nl_divisions", "nl_votes",
          "nl_ek_bills", "nl_ek_divisions", "nl_ek_votes")


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


def derived_member_positions(conn, besluit_id):
    """Each member's position on one vote (X5, Chris, 10 October 2026:
    derive member records from the group, labelled as derived).

    A roll call (kind 'lid') records each member: `derived` False. A show of
    hands records one position per fractie, and each member of that fractie
    is given it with `derived` True. The fractie is the member's latest
    (nl_members.fractie); the vote's own fractie label is kept in `party`.
    Nothing is written.
    """
    out = []
    rows = conn.execute("SELECT kind, fractie, persoon_id, actor, position FROM nl_votes "
                        "WHERE besluit_id=? ORDER BY fractie, actor", (besluit_id,)).fetchall()
    for kind, fractie, persoon_id, actor, position in rows:
        if kind == "lid":
            out.append({"member_id": persoon_id, "name": actor, "party": fractie,
                        "position": position, "derived": False, "basis": "roll call"})
            continue
        for pid, name in conn.execute(
                "SELECT persoon_id, name FROM nl_members WHERE fractie=? ORDER BY name", (fractie,)):
            out.append({"member_id": pid, "name": name, "party": fractie,
                        "position": position, "derived": True,
                        "basis": "fractie vote; member's latest fractie"})
    return out
