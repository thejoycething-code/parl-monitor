"""Member profiles for the new country editions, from the stores alone.

    from src import member_profiles as mp
    got = mp.build(conn, "pl", today)          # {'members': {...}, ...}
    mp.write(got, "profiles")                  # profiles/pl/*.md and index.md

    python3 tools/member_profiles.py pl        # the weekly step

Handover item 3 (docs/country-parity-handover.md): one profile per member
from the stores already collected, generalising the UK/DE/US profiles
(tools/de_profiles.py, src/us_profiles.py) to the countries built on 9-10
October 2026. Nothing here fetches, posts or DMs; it reads a store and writes
Markdown. The two fetches X6 needed are their own tools, run by their
country's weekly job before this step: tools/hr_party_history.py (Croatia's
transcripts) and tools/cl_senate_parties.py (Chile's senators, BCN).

WHAT A PROFILE HOLDS, all from the store, nothing personal:
  * identity: name as the source prints it, party, chamber, constituency or
    region, sitting or not where the source says, the source's own id;
  * party history WHERE THE SOURCE GIVES IT (Chile's militancias and the
    BCN's, Italy's Senate group spells, Croatia's transcript headings), and,
    where every vote record names the party at the vote, the parties the
    member was recorded under, first and last date;
  * every recorded position on a vote on our ground, verbatim (the record's
    own word: "Za", "AFIRMATIVO", "Dafür"), with the party at that vote and
    what that party claim rests on;
  * bills on our ground they authored or introduced, where the store links
    authors to members (by id, or by an exact name match);
  * questions on our ground they asked, where collected (Slovakia's
    interpellations, Uruguay's pedidos, Austria's Anfragen).

ON OUR GROUND IS THE EDITION'S CLASSIFICATION, not a second one. Votes are
taken from the country's own edition adapter (src/editions/<cc>.py, or
src/latam.py for the Latam countries) over the whole store, through the
same noise rules, mutes and session-judge scores the edition applies
(country_edition.gather, latam.country_items). A vote the edition would
leave out is not in a profile. Bills and questions use the same test the
adapters use: stored areas (migration matched but hidden, as everywhere) or
a watchlist key.

NO VERDICTS. Which way a vote cut for our side is a signed human judgement
(config/<cc>_stance.yaml, 5CA) that no new country has yet. A profile shows
what the record says each member did and never colours it.

PARTY AT THE VOTE, three bases, always stated (X5, X6):
  * at_vote   the vote record names the party or group (PL, IT, CH, FR, ES,
              BR, AR, MX, SK, DO, SV, PE, HU, and NL roll calls);
  * as_listed the record names no party; the party shown is the member
              list's, labelled "as listed, not party at the vote" (Croatia
              without a transcript sighting, Guatemala, Ecuador, Colombia,
              Belgium's group-when-stored, Chile's Senate before the BCN);
  * derived   the record names only the group (AT, PT, NL show of hands):
              each member's position is DERIVED from the group's vote by the
              store's own derived_member_positions (X5), labelled on every
              line, and never counted as a recorded position.
For Croatia and Chile the sourced history overrides the listed party where
it covers the vote's date, and says so on the line.

SPECS. One `Spec` per country below, each a few SQL statements over that
country's own tables; adding a country is adding a Spec. Read-only on the
store.
"""

from __future__ import annotations

import dataclasses
import datetime
import glob
import json
import os
import re
import sqlite3
from typing import Callable, Optional

from src import country_edition as ce
from src import latam

ALL_TIME = "0000-00-00"
# Size, measured on the scoping stores (10 October 2026): every vote in full
# came to 143 MB of Markdown (France alone, 629 deputies by 1,221 votes, over
# 100 MB). A profile is a member's summary, not the vote record: the counts
# cover every vote, the table the latest MAX_VOTES_SHOWN, one row each; the
# full record stays in the store and the weekly editions. At 20 rows the 23
# scoping stores gave about 30 MB in 5,000 files (1.5 MB gzipped).
MAX_VOTES_SHOWN = 20
MAX_LINKED_SHOWN = 20
TITLE_CLIP = 140
SAMPLE_MARK = "SAMPLE PROFILE"
GENERATOR = "tools/member_profiles.py"

AT_VOTE = "at the vote, as the record names it"
DERIVED = "the group's vote, X5"
AS_LISTED = "as listed, not party at the vote, X6"


# --- small helpers ------------------------------------------------------------------

def fold(text):
    from src.noise import fold as _fold
    return _fold(text or "")


def name_tokens(name):
    """A name as a set of folded words, titles ('Dr.', 'Mag.') and initials
    dropped: 'Auer Katrin, Mag.' and 'Katrin Auer' give the same set."""
    words = re.findall(r"[\w'-]+\.?", fold(name))
    return frozenset(w.strip("'-") for w in words
                     if not w.endswith(".") and len(w.strip("'-")) > 1)


def slug(text, n=60):
    s = re.sub(r"[^a-z0-9]+", "-", fold(text)).strip("-")
    return s[:n].strip("-") or "member"


def md(text):
    """Source text safe inside Markdown emphasis and tables, one line."""
    return ce.clean(text).replace("|", "/").replace("*", "∗").replace("_", "\\_")


def date_long(iso):
    try:
        return ce.long_date(ce.day(iso))
    except (TypeError, ValueError):
        return iso or "date not recorded"


def _rows(conn, sql, params=()):
    return ce.rows(conn, sql, params) if sql else []


def _json(raw):
    try:
        got = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return None
    return got


# --- the member roster -------------------------------------------------------------

@dataclasses.dataclass
class Member:
    key: str
    name: str
    party: Optional[str] = None
    chamber: Optional[str] = None
    region: Optional[str] = None
    current: Optional[bool] = None
    extra: tuple = ()
    stub: bool = False                  # seen in a record only, not in the member list
    votes: list = dataclasses.field(default_factory=list)
    authored: list = dataclasses.field(default_factory=list)
    questions: list = dataclasses.field(default_factory=list)
    history: list = dataclasses.field(default_factory=list)      # (party, start, end, source)
    at_votes: list = dataclasses.field(default_factory=list)     # (party, first, last)


class Roster:
    """Members by key, and by name for records that print a name only.

    A name resolves only when exactly one member has it (folded), or exactly
    one has the same set of name words, or (for records that print a short
    form, El Salvador's "ADOLFO RIVAS" for "Adolfo Antonio Rivas Ramírez")
    exactly one member's name contains every word of a printed name of two
    words or more. Anything else is a stub member, shown under the name the
    record prints, never guessed onto a namesake."""

    def __init__(self, members):
        self.by_key = {m.key: m for m in members}
        self._full, self._tokens = {}, {}
        for m in members:
            for table, k in ((self._full, " ".join(fold(m.name).split())),
                             (self._tokens, name_tokens(m.name))):
                if k:
                    table[k] = None if k in table and table[k] != m.key else m.key
        self._listed = [(name_tokens(m.name), m.key) for m in members]
        self._short = {}

    def by_name(self, name):
        k = " ".join(fold(name).split())
        if k and self._full.get(k):
            return self._full[k]
        t = name_tokens(name)
        if len(t) < 2:
            return None
        if t in self._tokens:
            return self._tokens[t]
        if t not in self._short:
            hits = {key for toks, key in self._listed if t <= toks}
            self._short[t] = hits.pop() if len(hits) == 1 else None
        return self._short[t]

    def resolve(self, member_id=None, name=None, make_stub=True):
        if member_id is not None and str(member_id) in self.by_key:
            return self.by_key[str(member_id)]
        key = self.by_name(name) if name else None
        if key:
            return self.by_key[key]
        if not make_stub or not (name or member_id):
            return None
        stub_key = "name:" + slug(name or str(member_id), 80)
        if stub_key not in self.by_key:
            self.by_key[stub_key] = Member(stub_key, ce.clean(name) or str(member_id), stub=True)
        return self.by_key[stub_key]


# --- party spells ------------------------------------------------------------------

def spell_on(spells, date):
    """(party, source) of the spell covering an ISO date, or None."""
    d = ce.day(date)
    for party, start, end, source in spells or ():
        if (start or "") <= d and (not end or d <= end):
            return party, source
    return None


def sightings_to_spells(rows):
    """[(party, first, last, n)] from dated (date, party) sightings, merging
    consecutive sightings of one party."""
    out = []
    for date, party in sorted(rows):
        if out and out[-1][0] == party:
            out[-1][2] = date
            out[-1][3] += 1
        else:
            out.append([party, date, date, 1])
    return [tuple(s) for s in out]


def sighted_party(spells, date):
    """The party seen in debate around a date: inside a spell, or between two
    spells of the same party. None when the sightings disagree or are absent."""
    d = ce.day(date)
    before = after = None
    for party, first, last, _n in spells or ():
        if first <= d <= last:
            return party
        if last < d:
            before = party
        elif first > d and after is None:
            after = party
    return before if before is not None and before == after else None


# --- the country specs -------------------------------------------------------------

@dataclasses.dataclass
class Spec:
    cc: str
    members: str                         # SQL: key, name, party, chamber, region, current
    positions: object                    # SQL (one '?': the division) or fn(conn, key)
    basis: str = "at_vote"               # 'at_vote' | 'as_listed' | 'derived'
    listed_label: str = AS_LISTED        # how an as-listed party is labelled
    party_note: str = ""                 # the profile's line on what party means here
    vote_parties: Optional[str] = None   # SQL: member_id, name, party, first, last
    history: Optional[Callable] = None   # fn(conn) -> {member_key: [(party, start, end, source)]}
    party_at: Optional[Callable] = None  # fn(ctx, member, date, recorded) -> (party, label) or None
    authored: Optional[Callable] = None  # fn(conn, wl) -> [dict]
    questions: Optional[Callable] = None
    group_labels: Optional[str] = None   # SQL: code, label (France's organe refs)
    extra: Optional[str] = None          # SQL: key, label, value (shown under identity)
    notes: tuple = ()                    # extra lines for the profile's notes
    vote_note: Optional[Callable] = None # fn(vote) -> a short note for its table row


def sql_positions(sql):
    """fn(conn, division_key) -> [{member_id, name, party, position, derived}]
    from a statement returning member_id, name, party, position."""
    def run(conn, key):
        return [{"member_id": r[0], "name": r[1], "party": r[2], "position": r[3],
                 "derived": False} for r in _rows(conn, sql, (key,))]
    return run


def store_derived(module):
    """The store's own X5 derivation (src/<cc>_store.derived_member_positions)."""
    def run(conn, key):
        import importlib
        mod = importlib.import_module("src.{0}_store".format(module))
        conn.row_factory = None
        try:
            got = mod.derived_member_positions(conn, key)
        except sqlite3.OperationalError:
            got = []
        finally:
            conn.row_factory = sqlite3.Row
        return [dict(g, member_id=g.get("member_id")) for g in got]
    return run


def _authored_rows(conn, wl, sql, ids=None, names=None, role="author", url=None):
    """Bills on our ground with their authors, one dict per (bill, author).
    `ids(row)` gives member ids, `names(row)` printed names."""
    out = []
    for r in _rows(conn, sql):
        watched = str(r["key"]) in wl
        if not ce.on_ground(r["areas"], watched):
            continue
        base = {"key": str(r["key"]), "date": ce.day(r["date"]), "title": r["title"],
                "areas": ce.areas_of(r["areas"]), "tier": r["tier"], "watched": watched,
                "url": url(r) if url else None,
                "role": role(r) if callable(role) else role}
        for i in (ids(r) if ids else []) or []:
            out.append(dict(base, member_id=str(i), name=None))
        for n in (names(r) if names else []) or []:
            out.append(dict(base, member_id=None, name=n))
    return out


def json_list(col):
    def get(r):
        got = _json(r[col])
        return [str(x) for x in got if x] if isinstance(got, list) else []
    return get


def split_names(col, seps=r";|\n"):
    def get(r):
        raw = r[col] or ""
        got = _json(raw) if raw.strip().startswith("[") else None
        if isinstance(got, list):
            return [str(x) for x in got if x]
        return [p.strip() for p in re.split(seps, raw) if p.strip()]
    return get


# Country-specific pieces, kept beside their spec.

def _cl_history(conn):
    out = {}
    for mk, party, name, start, end in _rows(
            conn, "SELECT member_key, party, party_name, start, end FROM cl_party_spells "
                  "ORDER BY member_key, start"):
        src = "the BCN's militancies" if mk.startswith("S-") else "the Cámara's militancias"
        label = party if (party == name or not name) else "{0} ({1})".format(party, name)
        out.setdefault(mk, []).append((label, start, end, src))
    return out


def _cl_party_at(ctx, m, date, recorded):
    if m.key.startswith("D-"):
        if recorded:
            return recorded, "on the day, from the Cámara's militancias"
        return None, "no militancia covers the day"
    got = spell_on(ctx["history"].get(m.key), date)
    if got:
        return got[0].split(" (")[0], "on the day, from the BCN's party history, X6"
    return recorded or m.party, "as listed when the vote was collected, not party at the vote, X6"


def _it_history(conn):
    out = {}
    for key, groups in _rows(conn, "SELECT member_key, groups FROM it_members "
                                   "WHERE groups IS NOT NULL"):
        for g in _json(groups) or []:
            if isinstance(g, dict) and g.get("grp"):
                out.setdefault(key, []).append((g["grp"], g.get("from"), g.get("to"),
                                                "the Senate's group spells"))
    return out


def _hr_history(conn):
    rows = {}
    for slug_, date, party in _rows(conn, "SELECT slug, date, party FROM hr_party_seen"):
        rows.setdefault(slug_, []).append((date, party))
    out = {}
    for k, sightings in rows.items():
        out[k] = [(p, a, b, "the Sabor's transcripts, seen in debate {0} time(s)".format(n))
                  for p, a, b, n in sightings_to_spells(sightings)]
    return out


def _hr_party_at(ctx, m, date, recorded):
    spells = [(p, a, b, 0) for p, a, b, _s in ctx["history"].get(m.key) or ()]
    seen = sighted_party(spells, date)
    if seen:
        return seen, "seen in debate around the vote, from the Sabor's transcripts, X6"
    return recorded or m.party, ("as listed when the vote was collected, not party at the "
                                 "vote, X6")


def _hr_note(v):
    """Croatia: on a conclusion not to accept a bill, "for" was to reject it."""
    t = v.get("takeaway") or ""
    if "conclusion NOT to accept" in t:
        return "question put: a conclusion not to accept the bill, so 'for' was to reject it"
    if "has not been read" in t:
        return "question put not read yet"
    return None


def _pt_authored(conn, wl):
    from src.editions import pt
    return _authored_rows(
        conn, wl, "SELECT i.ini_key AS key, i.entered AS date, i.title, i.areas, i.tier, "
                  "i.ini_id, a.cad_id FROM pt_authors a JOIN pt_initiatives i USING (ini_key)",
        ids=lambda r: [r["cad_id"]], role="author", url=lambda r: pt.ini_url(r["ini_id"]))


def _at_items(conn, wl, questions):
    from src.editions import at
    test = "LIKE '%Anfrage%'" if questions else "NOT LIKE '%Anfrage%'"
    return _authored_rows(
        conn, wl, "SELECT item_key AS key, introduced AS date, title, areas, tier, persons, "
                  "art_long FROM at_items WHERE persons IS NOT NULL AND persons != '[]' "
                  "AND COALESCE(art_long, '') " + test,
        ids=json_list("persons"),
        role=lambda r: "named on the item ({0})".format(ce.clean(r["art_long"]) or "item"),
        url=lambda r: at.item_url(r["key"]))


def _fr_authored(conn, wl):
    from src.editions import fr
    return _authored_rows(
        conn, wl, "SELECT dossier_ref AS key, last_act_at AS date, title, areas, tier, "
                  "initiator, an_path FROM fr_dossiers WHERE initiator IS NOT NULL",
        ids=lambda r: [r["initiator"]], role="first author (initiator of the dossier)",
        url=lambda r: fr.dossier_url(r["key"], r["an_path"]))


def _be_authored(conn, wl):
    from src.editions import be

    def ids(r):
        got = _json(r["authors"]) or []
        return [a[0] for a in got if isinstance(a, list) and a and a[0]]

    def names(r):
        got = _json(r["authors"]) or []
        return [a[1] for a in got if isinstance(a, list) and len(a) > 1 and not a[0] and a[1]]
    return _authored_rows(
        conn, wl, "SELECT dossier_key AS key, deposited AS date, "
                  "COALESCE(title_fr, title_nl) AS title, areas, NULL AS tier, authors "
                  "FROM be_dossiers WHERE authors IS NOT NULL AND authors != '[]'",
        ids=ids, names=names, role="author", url=lambda r: be.dossier_url(r["key"]))


def _ch_authored(conn, wl):
    from src.editions import ch
    return _authored_rows(
        conn, wl, "SELECT short_number AS key, submission_date AS date, "
                  "COALESCE(title_de, title_fr) AS title, areas, tier, submitted_by, "
                  "business_id FROM ch_businesses WHERE COALESCE(submitted_by, '') != ''",
        names=lambda r: [r["submitted_by"]], role="submitted by",
        url=lambda r: ch.business_url(r["business_id"]))


def _names_authored(sql, col, role="author"):
    def run(conn, wl):
        return _authored_rows(conn, wl, sql, names=split_names(col), role=role)
    return run


def _sk_questions(conn, wl):
    return _authored_rows(
        conn, wl, "SELECT 'int:' || int_id AS key, submitted AS date, subject AS title, "
                  "areas, tier, questioner, addressee FROM sk_interpellations",
        names=lambda r: [r["questioner"]],
        role=lambda r: "interpellation to {0}".format(ce.clean(r["addressee"]) or "?"))


def _uy_questions(conn, wl):
    return _authored_rows(
        conn, wl, "SELECT question_key AS key, date, tema AS title, areas, tier, autores, "
                  "organismo, url_oficio FROM uy_questions",
        names=split_names("autores", r";|\n| y |, (?=[A-ZÁÉÍÓÚÑ][a-záéíóúñ])"),
        role=lambda r: "pedido de informes to {0}".format(ce.clean(r["organismo"]) or "?"),
        url=lambda r: r["url_oficio"])


AS_LISTED_ROSTER = "as listed on the member roster, not party at the vote, X6"

SPECS = {
    "pl": Spec(
        "pl", "SELECT mp_key, name, club, 'Sejm', district, active FROM pl_members",
        sql_positions("SELECT v.mp_key, m.name, v.club, v.position FROM pl_votes v LEFT JOIN "
                      "pl_members m USING (mp_key) WHERE v.division_key = ?"),
        vote_parties="SELECT v.mp_key, NULL, v.club, MIN(d.voted_at), MAX(d.voted_at) FROM "
                     "pl_votes v JOIN pl_divisions d USING (division_key) GROUP BY 1, 3",
        party_note="The club the Sejm's vote record names at each vote."),
    "it": Spec(
        "it", "SELECT member_key, name, grp, chamber, NULL, NULL FROM it_members",
        sql_positions("SELECT v.member_key, m.name, v.grp, v.position FROM it_votes v LEFT JOIN "
                      "it_members m USING (member_key) WHERE v.division_key = ?"),
        vote_parties="SELECT v.member_key, NULL, v.grp, MIN(d.date), MAX(d.date) FROM it_votes v "
                     "JOIN it_divisions d USING (division_key) WHERE v.grp IS NOT NULL "
                     "GROUP BY 1, 3",
        history=_it_history,
        party_note="The group the vote record names at each vote; the Senate's group spells "
                   "where dati.senato.it gives them."),
    "ch": Spec(
        "ch", "SELECT person_number, first_name || ' ' || last_name, party, council, "
              "COALESCE(canton_name, canton), active FROM ch_members",
        sql_positions("SELECT v.person_number, m.first_name || ' ' || m.last_name, v.parl_group, "
                      "v.position FROM ch_votes v LEFT JOIN ch_members m USING (person_number) "
                      "WHERE v.division_key = ?"),
        vote_parties="SELECT v.person_number, NULL, v.parl_group, MIN(d.date), MAX(d.date) FROM "
                     "ch_votes v JOIN ch_divisions d USING (division_key) GROUP BY 1, 3",
        extra="SELECT person_number, 'Parliamentary group (latest)', parl_group FROM ch_members",
        authored=_ch_authored,
        party_note="Party is the member's party; the vote record names the parliamentary "
                   "group (Fraktion) at each vote, which is what each vote line shows."),
    "fr": Spec(
        "fr", "SELECT acteur_ref, name, group_ref, chamber, TRIM(COALESCE(department, '') || "
              "CASE WHEN constituency IS NOT NULL THEN ', circonscription ' || constituency "
              "ELSE '' END), current FROM fr_members",
        sql_positions("SELECT v.acteur_ref, m.name, v.group_ref, v.position FROM fr_votes v "
                      "LEFT JOIN fr_members m USING (acteur_ref) WHERE v.division_key = ?"),
        vote_parties="SELECT v.acteur_ref, NULL, v.group_ref, MIN(d.date), MAX(d.date) FROM "
                     "fr_votes v JOIN fr_divisions d USING (division_key) GROUP BY 1, 3",
        group_labels="SELECT organe_ref, COALESCE(abbr, label) FROM fr_groups",
        authored=_fr_authored,
        party_note="The political group the scrutin names at each vote."),
    "es": Spec(
        "es", "SELECT name, name, grupo, 'Congreso de los Diputados', circunscripcion, "
              "baja IS NULL, MAX(legislature) FROM es_members GROUP BY name",
        sql_positions("SELECT NULL, name, grupo, position FROM es_votes WHERE division_key = ?"),
        vote_parties="SELECT NULL, v.name, v.grupo, MIN(d.date), MAX(d.date) FROM es_votes v "
                     "JOIN es_divisions d USING (division_key) GROUP BY 2, 3",
        extra="SELECT name, 'Electoral list', formacion, MAX(legislature) FROM es_members "
              "GROUP BY name",
        party_note="The parliamentary group the vote file names at each vote."),
    "nl": Spec(
        "nl", "SELECT persoon_id, name, fractie, 'Tweede Kamer', NULL, NULL FROM nl_members",
        store_derived("nl"), basis="derived",
        party_note="Most Tweede Kamer votes are by show of hands, one position per fractie; "
                   "those member positions are DERIVED (X5), given to every member the store "
                   "lists under that fractie by their latest fractie. Roll calls record each "
                   "member and are shown as recorded."),
    "be": Spec(
        "be", "SELECT member_key, name, party_group, 'Chambre / Kamer', NULL, current "
              "FROM be_members",
        sql_positions("SELECT member_key, member_name, group_seen, position FROM be_votes "
                      "WHERE division_key = ?"),
        basis="as_listed",
        listed_label="the member's group when the vote was stored, not party at the vote, X6",
        authored=_be_authored,
        party_note="The Chamber's vote lists print names only; the group shown is the "
                   "member's group when the vote was stored."),
    "at": Spec(
        "at", "SELECT pad, name, klub, chamber, TRIM(COALESCE(wahlkreis, '') || CASE WHEN "
              "bundesland IS NOT NULL THEN ' (' || bundesland || ')' ELSE '' END), NULL "
              "FROM at_members",
        store_derived("at"), basis="derived",
        authored=lambda conn, wl: _at_items(conn, wl, False),
        questions=lambda conn, wl: _at_items(conn, wl, True),
        party_note="The Nationalrat and Bundesrat record only each Klub's vote: every member "
                   "position here is DERIVED from it (X5), by the member's latest Klub."),
    "pt": Spec(
        "pt", "SELECT cad_id, name, party, 'Assembleia da República', circle, "
              "situation LIKE 'Efetiv%' FROM pt_members",
        store_derived("pt"), basis="derived",
        authored=_pt_authored,
        party_note="Portugal votes by group: a deputy is named only when they broke from it. "
                   "Named positions are recorded facts; every other position is DERIVED from "
                   "the group's vote (X5), by the deputy's latest group, sitting deputies only."),
    "sk": Spec(
        "sk", "SELECT mp_id, name, club, 'Národná rada', region, NULL FROM sk_members",
        sql_positions("SELECT v.mp_id, m.name, v.club, v.position FROM sk_votes v LEFT JOIN "
                      "sk_members m USING (mp_id) WHERE v.voting_id = ?"),
        vote_parties="SELECT v.mp_id, NULL, v.club, MIN(d.date), MAX(d.date) FROM sk_votes v "
                     "JOIN sk_divisions d USING (voting_id) WHERE v.club IS NOT NULL "
                     "GROUP BY 1, 3",
        extra="SELECT mp_id, 'Elected on the list of', party FROM sk_members",
        questions=_sk_questions,
        party_note="The club the vote page groups each member under (no club: independent)."),
    "hr": Spec(
        "hr", "SELECT slug, name, party, 'Hrvatski sabor', constituency, "
              "mandate = 'Aktivan' FROM hr_members",
        sql_positions("SELECT v.slug, m.name, v.party_seen, v.position FROM hr_votes v "
                      "LEFT JOIN hr_members m USING (slug) WHERE v.division_key = ?"),
        basis="as_listed", history=_hr_history, party_at=_hr_party_at, vote_note=_hr_note,
        party_note="The Sabor's vote service prints no party. Where the plenary transcripts "
                   "show the member speaking for a party on both sides of a vote's date, that "
                   "party is shown and said to come from the transcripts; otherwise the party "
                   "is the member list's when the vote was collected, as listed, not party at "
                   "the vote (X6). On a conclusion not to accept a bill, 'for' was a vote to "
                   "reject it (each vote line says what was put)."),
    "hu": Spec(
        "hu", "SELECT member_id, name, faction, 'Országgyűlés', TRIM(COALESCE(county, '') || "
              "CASE WHEN constituency_no IS NOT NULL THEN ' ' || constituency_no ELSE '' END), "
              "current FROM hu_members",
        sql_positions("SELECT member_id, name, faction, position FROM hu_votes "
                      "WHERE vote_ts = ?"),
        vote_parties="SELECT v.member_id, NULL, v.faction, MIN(d.date), MAX(d.date) FROM "
                     "hu_votes v JOIN hu_divisions d USING (vote_ts) GROUP BY 1, 3",
        party_note="The faction the vote record names at each vote. Votes come from karzat "
                   "(9 May to 28 August 2026) until the Parliament's own API opens."),
    "br": Spec(
        "br", "SELECT member_key, name, party, chamber, uf, in_office FROM br_members",
        sql_positions("SELECT v.member_key, m.name, v.party, v.position FROM br_votes v "
                      "LEFT JOIN br_members m USING (member_key) WHERE v.division_key = ?"),
        vote_parties="SELECT v.member_key, NULL, v.party, MIN(d.date), MAX(d.date) FROM br_votes "
                     "v JOIN br_divisions d USING (division_key) GROUP BY 1, 3",
        party_note="The party the vote record names at each vote."),
    "ar": Spec(
        "ar", "SELECT member_key, name, bloc, chamber, province, current FROM ar_members",
        sql_positions("SELECT v.member_key, m.name, v.bloc, v.position FROM ar_votes v "
                      "LEFT JOIN ar_members m USING (member_key) WHERE v.division_key = ?"),
        vote_parties="SELECT v.member_key, NULL, v.bloc, MIN(d.date), MAX(d.date) FROM ar_votes "
                     "v JOIN ar_divisions d USING (division_key) GROUP BY 1, 3",
        authored=_names_authored("SELECT exp_key AS key, published AS date, title, areas, tier, "
                                 "author FROM ar_bills WHERE author IS NOT NULL", "author"),
        party_note="The bloc the Senate's acta names at each vote. Diputados votes are not "
                   "collected (the chamber's site answers from nowhere we can reach)."),
    "mx": Spec(
        "mx", "SELECT member_key, name, party, 'Cámara de Diputados', TRIM(COALESCE(entidad, '') "
              "|| CASE WHEN distrito IS NOT NULL THEN ', ' || distrito ELSE '' END), NULL "
              "FROM mx_members",
        sql_positions("SELECT v.member_key, m.name, v.party, v.position FROM mx_votes v "
                      "LEFT JOIN mx_members m USING (member_key) WHERE v.division_key = ?"),
        vote_parties="SELECT v.member_key, NULL, v.party, MIN(d.date), MAX(d.date) FROM mx_votes "
                     "v JOIN mx_divisions d USING (division_key) GROUP BY 1, 3",
        party_note="The party the SITL vote table names at each vote. Initiatives name their "
                   "presenter in a sentence, not linked to a member: authorship is not shown."),
    "cl": Spec(
        "cl", "SELECT member_key, name, party, chamber, TRIM(COALESCE(district, '') || CASE "
              "WHEN region IS NOT NULL THEN ' (' || region || ')' ELSE '' END), NULL "
              "FROM cl_members",
        sql_positions("SELECT v.member_key, m.name, v.party, v.position FROM cl_votes v "
                      "LEFT JOIN cl_members m USING (member_key) WHERE v.division_key = ?"),
        basis="at_vote", history=_cl_history, party_at=_cl_party_at,
        authored=_names_authored("SELECT boletin AS key, introduced AS date, title, areas, tier, "
                                 "authors FROM cl_bills WHERE authors IS NOT NULL AND "
                                 "authors != '[]'", "authors"),
        party_note="Deputies: the party on the day, from the Cámara's militancias. Senators: "
                   "the party on the day from the BCN's party history where it covers the "
                   "vote (X6), otherwise the party when the vote was collected, as listed."),
    "pe": Spec(
        "pe", "SELECT member_key, name, bancada, chamber, district, status = 'en-ejercicio' "
              "FROM pe_members",
        sql_positions("SELECT member_key, name_raw, bancada, position FROM pe_votes "
                      "WHERE division_key = ?"),
        vote_parties="SELECT v.member_key, v.name_raw, v.bancada, MIN(d.date), MAX(d.date) FROM "
                     "pe_votes v JOIN pe_divisions d USING (division_key) GROUP BY 1, 2, 3",
        extra="SELECT member_key, 'Party', party FROM pe_members",
        authored=_names_authored("SELECT bill_key AS key, presented AS date, title, areas, tier, "
                                 "authors FROM pe_bills WHERE authors IS NOT NULL AND "
                                 "authors != '[]'", "authors"),
        party_note="The bancada the vote PDF names at each vote."),
    "ec": Spec(
        "ec", "SELECT r.name_key, r.name, r.party, 'Asamblea Nacional', r.constituency, NULL "
              "FROM ec_roster r UNION ALL SELECT m.name_key, m.name, NULL, 'Asamblea Nacional', "
              "NULL, NULL FROM ec_members m WHERE m.name_key NOT IN "
              "(SELECT name_key FROM ec_roster)",
        sql_positions("SELECT name_key, name, NULL, position FROM ec_votes "
                      "WHERE division_key = ?"),
        basis="as_listed", listed_label=AS_LISTED_ROSTER,
        party_note="The vote service prints no party; the party shown is the Asamblea's "
                   "current roster's, as listed, not party at the vote."),
    "do": Spec(
        "do", "SELECT member_key, name, party, role, TRIM(COALESCE(province, '') || CASE WHEN "
              "constituency IS NOT NULL THEN ', ' || constituency ELSE '' END), NULL "
              "FROM do_members",
        sql_positions("SELECT member_key, name, party, COALESCE(label, position) FROM do_votes "
                      "WHERE division_key = ?"),
        vote_parties="SELECT v.member_key, NULL, v.party, MIN(d.date), MAX(d.date) FROM do_votes "
                     "v JOIN do_divisions d USING (division_key) GROUP BY 1, 3",
        party_note="The party (siglas) the SIL's vote record names at each vote."),
    "sv": Spec(
        "sv", "SELECT member_id, name, party, 'Asamblea Legislativa', department, NULL "
              "FROM sv_members",
        sql_positions("SELECT NULL, name, party, position FROM sv_votes WHERE division_key = ?"),
        vote_parties="SELECT NULL, v.name, v.party, MIN(d.date), MAX(d.date) FROM sv_votes v "
                     "JOIN sv_divisions d USING (division_key) GROUP BY 2, 3",
        extra="SELECT member_id, 'Seat', cargo FROM sv_members",
        party_note="The party the vote PDF names at each vote. The PDFs print names only, "
                   "matched to the member list by name (a short form such as 'ADOLFO RIVAS' only "
                   "when exactly one listed member's name contains it); a name that matches no "
                   "one, or more than one, is shown as printed, as are former deputies."),
    "gt": Spec(
        "gt", "SELECT name_key, name, bloque, 'Congreso de la República', distrito, NULL "
              "FROM gt_members",
        sql_positions("SELECT name_key, name, NULL, position FROM gt_votes "
                      "WHERE division_key = ?"),
        basis="as_listed", listed_label=AS_LISTED,
        party_note="The vote pages print no bloc, and the per-vote PDFs that might are closed "
                   "to robots: the bloc shown is the member's current one, as listed, not "
                   "party at the vote (X6, GT4)."),
    "co": Spec(
        "co", "SELECT member_key, name, party, chamber, department, NULL FROM co_members",
        sql_positions("SELECT member_key, NULL, NULL, position FROM co_votes "
                      "WHERE division_key = ?"),
        basis="as_listed", listed_label=AS_LISTED_ROSTER,
        authored=_names_authored("SELECT bill_key AS key, filed_at AS date, "
                                 "COALESCE(nickname, title) AS title, areas, tier, authors "
                                 "FROM co_bills WHERE COALESCE(authors, '') != ''", "authors"),
        party_note="Colombia's vote files print no party; the party shown is the member "
                   "list's latest, as listed, not party at the vote."),
    "uy": Spec(
        "uy", "SELECT name, name, party, chamber, departamento, NULL FROM uy_members",
        None, basis="as_listed", listed_label=AS_LISTED_ROSTER,
        questions=_uy_questions,
        party_note="Uruguay publishes no member-level votes we can reach (the Parliament's "
                   "main site refuses us): profiles hold questions only."),
}

COUNTRIES = tuple(SPECS)

# The source's chamber codes, in words (anything else is shown as stored).
CHAMBERS = {
    "cl": {"camara": "Cámara de Diputadas y Diputados", "senado": "Senado"},
    "it": {"camera": "Camera dei deputati", "senato": "Senato della Repubblica"},
    "br": {"camara": "Câmara dos Deputados", "senado": "Senado Federal"},
    "ar": {"senado": "Senado", "diputados": "Cámara de Diputados"},
    "pe": {"senado": "Senado", "diputados": "Cámara de Diputados"},
    "co": {"camara": "Cámara de Representantes", "senado": "Senado"},
    "at": {"NR": "Nationalrat", "BR": "Bundesrat"},
    "ch": {"NR": "Nationalrat", "SR": "Ständerat", "BR": "Federal Council"},
    "fr": {"an": "Assemblée nationale"},
    "uy": {"representantes": "Cámara de Representantes", "senadores": "Cámara de Senadores"},
}


# --- building ------------------------------------------------------------------------

def country_name(cc):
    if cc in latam.NAMES and not os.path.exists(edition_module(cc)):
        return latam.NAMES[cc]
    return ce.adapter(cc).name


def edition_module(cc):
    return os.path.join(ce.ROOT, "src", "editions", "{0}.py".format(cc))


def watchlist(cc, config_dir=None):
    if os.path.exists(edition_module(cc)):
        return ce.watchlist_of(ce.adapter(cc), config_dir)
    return latam.watchlist(cc, config_dir)


def vote_items(conn, cc, today, config_dir=None):
    """The edition's vote items over the whole store: the country's adapter,
    noise rules, mutes and session-judge scores, exactly as an edition."""
    conn.row_factory = sqlite3.Row
    if os.path.exists(edition_module(cc)):
        got = ce.gather(conn, ce.adapter(cc), ALL_TIME, today, config_dir)
    else:
        got = latam.country_items(conn, cc, ALL_TIME, today, ledger={"moves": []},
                                  config_dir=config_dir)
    return [it for it in got if it["kind"] == "vote"]


def roster(conn, spec):
    out = []
    for r in _rows(conn, spec.members):
        if r[0] is None:
            continue
        cur = r[5]
        chamber = ce.clean(r[3]) or None
        chamber = CHAMBERS.get(spec.cc, {}).get(chamber, chamber)
        out.append(Member(str(r[0]), ce.clean(r[1]) or str(r[0]), ce.clean(r[2]) or None,
                          chamber, ce.clean(r[4]) or None,
                          None if cur is None else bool(cur)))
    ros = Roster(out)
    if spec.extra:
        for key, label, value, *_ in _rows(conn, spec.extra):
            m = ros.by_key.get(str(key))
            if m and ce.clean(value):
                m.extra = m.extra + ((label, ce.clean(value)),)
    return ros


def build(conn, cc, today, config_dir=None):
    """Every member's profile data for one country. Read-only."""
    spec = SPECS[cc]
    conn.row_factory = sqlite3.Row
    ros = roster(conn, spec)
    labels = {str(a): b for a, b in _rows(conn, spec.group_labels)} if spec.group_labels else {}
    history = spec.history(conn) if spec.history else {}
    ctx = {"history": history, "labels": labels}
    for m in ros.by_key.values():
        m.party = labels.get(str(m.party), m.party) if m.party else m.party
    for key, spells in history.items():
        m = ros.by_key.get(key)
        if m:
            m.history = spells
    wl = watchlist(cc, config_dir)
    unresolved = 0
    items = vote_items(conn, cc, today, config_dir) if spec.positions else []
    for it in items:
        div = it.get("division") or it["key"]
        for p in spec.positions(conn, div):
            m = ros.resolve(p.get("member_id"), p.get("name"))
            if m is None:
                continue
            if m.stub:
                unresolved += 1
            recorded = labels.get(str(p.get("party")), p.get("party"))
            party, basis = party_of(spec, ctx, m, it["date"], ce.clean(recorded) or None,
                                    p.get("derived"))
            m.votes.append({
                "date": it["date"], "title": it["title"], "key": it["key"], "division": div,
                "position": ce.clean(p.get("position")) or "(no position recorded)",
                "party": party, "basis": basis, "derived": bool(p.get("derived")),
                "areas": it["areas"], "tier": it["tier"], "watched": it["watched"],
                "url": it["url"], "takeaway": it.get("takeaway"), "own": it.get("own"),
                "group_title": it.get("group_title"), "judge": it.get("judge"),
                "judge_why": it.get("judge_why")})
    if spec.vote_parties:
        for mid, name, party, first, last in _rows(conn, spec.vote_parties):
            m = ros.resolve(mid, name, make_stub=False)
            if m and party:
                m.at_votes.append((labels.get(str(party), party), ce.day(first), ce.day(last)))
    for field_, fn in (("authored", spec.authored), ("questions", spec.questions)):
        for row in (fn(conn, wl) if fn else []):
            m = ros.resolve(row.get("member_id"), row.get("name"), make_stub=False)
            if m is None:
                unresolved += 1
                continue
            getattr(m, field_).append(row)
    for m in ros.by_key.values():
        m.votes.sort(key=lambda v: (v["date"], v["key"]), reverse=True)
        for lst in (m.authored, m.questions):
            lst.sort(key=lambda v: (v["date"] or "", v["key"]), reverse=True)
        m.at_votes.sort(key=lambda p: (p[1] or "", p[0]))
    return {"cc": cc, "name": country_name(cc), "today": today, "spec": spec,
            "members": ros.by_key, "votes": len(items), "unresolved": unresolved,
            "attribution": attribution(conn, cc)}


def party_of(spec, ctx, m, date, recorded, derived):
    if derived:
        return recorded, DERIVED
    if spec.party_at:
        got = spec.party_at(ctx, m, date, recorded)
        if got:
            return got
    if spec.basis == "at_vote" and recorded:
        return recorded, AT_VOTE
    if spec.basis == "derived":
        return (recorded, AT_VOTE) if recorded else (m.party, spec.listed_label)
    return recorded or m.party, spec.listed_label


def attribution(conn, cc):
    """A third-party source's attribution line, where the store records one
    (Hungary's karzat, hu_sources)."""
    if cc != "hu":
        return None
    got = _rows(conn, "SELECT name, licence, attribution FROM hu_sources")
    return "; ".join(ce.clean(" ".join(x for x in (r[2] or r[0], r[1] and "licence " + r[1])
                                       if x)) for r in got) or None


# --- rendering ------------------------------------------------------------------------

def has_record(m):
    return bool(m.votes or m.authored or m.questions)


def filename(m):
    """Stable across runs: the name and the source's id ('ackar-kresimir-11-saziv'
    alone when the id already spells the name)."""
    name, key = slug(m.name, 50), slug(m.key, 40)
    return "{0}.md".format(key if key.startswith(name) else "{0}-{1}".format(name, key))


def _flags(v):
    bits = [ce.area_text(v["areas"]) or "watched"]
    if v.get("tier"):
        bits.append("tier {0}".format(v["tier"]))
    if v.get("watched"):
        bits.append("**watched**")
    return " · ".join(bits)


def short_basis(basis):
    """The party-at-the-vote basis in a table cell's words."""
    b = basis or ""
    if b == DERIVED:
        return "group's vote, X5"
    if b == AT_VOTE:
        return "at the vote"
    if "transcripts" in b:
        return "seen in debate, transcripts"
    if "BCN" in b:
        return "on the day, BCN"
    if "militancias" in b:
        return "on the day, militancias" if "no militancia" not in b else b
    if "not party at the vote" in b:
        return "as listed, not at the vote"
    return b


def vote_row(spec, v):
    text = v["title"] or ""
    if v.get("group_title") and v["group_title"] != text:
        text = "{0}; on: {1}".format(text, v["group_title"]) if text else v["group_title"]
    title = md(ce.clip(text, TITLE_CLIP)) or "(no title)"
    if v.get("url"):
        title = "[{0}]({1})".format(title, v["url"])
    marks = []
    if v.get("watched"):
        marks.append("**watched**")
    if v.get("own") is False:
        marks.append("bill's areas")
    note = spec.vote_note(v) if spec.vote_note else None
    if note:
        marks.append(note)
    position = md(v["position"]) + (" (DERIVED)" if v["derived"] else "")
    party = "{0} ({1})".format(md(v["party"]), short_basis(v["basis"])) if v["party"] else \
        "not known ({0})".format(short_basis(v["basis"]))
    areas = ce.area_text(v["areas"]) or "watched"
    if v.get("tier"):
        areas += ", tier {0}".format(v["tier"])
    return "| {0} | {1} | {2} | {3}{4} | {5} |".format(
        ce.short_date(v["date"]) + " " + (v["date"] or "")[:4], position, party, title,
        " · " + " · ".join(marks) if marks else "", areas)


def linked_row(r):
    title = md(ce.clip(r["title"] or "", TITLE_CLIP)) or "(no title)"
    if r.get("url"):
        title = "[{0}]({1})".format(title, r["url"])
    areas = ce.area_text(r["areas"]) or "watched"
    if r.get("watched"):
        areas += ", **watched**"
    return "| {0} | {1} | {2} | {3} | {4} |".format(
        (ce.short_date(r["date"]) + " " + r["date"][:4]) if r.get("date") else "",
        title, md(r["key"]), md(r["role"]).rstrip("."), areas)


def by_area(votes):
    """'abortion: “pour” 3, “contre” 1; ...' over every vote."""
    areas = {}
    for v in votes:
        for a in v["areas"] or [None]:
            areas.setdefault(a, []).append(v)
    return "; ".join("{0}: {1}".format(ce.area_text([a]) if a else "watched only",
                                      position_counts(vs))
                     for a, vs in sorted(areas.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)))


def position_counts(votes):
    counts = {}
    for v in votes:
        counts[v["position"]] = counts.get(v["position"], 0) + 1
    return ", ".join("“{0}” {1}".format(md(k), n)
                     for k, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def render_member(data, m, sample=False):
    spec, name = data["spec"], data["name"]
    out = ["# {0}".format(md(m.name)), ""]
    if sample:
        out += ["**{0}**: built from a scoping store, never published.".format(SAMPLE_MARK), ""]
    out.append("{0}{1}. From the parliamentary monitor's store; positions are as the record "
               "gives them, never a verdict. Index: [{2} members](index.md).".format(
                   name, ", " + md(m.chamber) if m.chamber else "", name))
    out.append("")
    listed = spec.listed_label if spec.basis == "as_listed" else "latest seen in the member list"
    if spec.basis == "derived":
        listed = "latest seen in the member list (the group used for derived positions)"
    ident = [("Party", "{0}; {1}".format(md(m.party), listed) if m.party else
              "not given by the source")]
    if m.region:
        ident.append(("Constituency or region", md(m.region)))
    for label, value in m.extra:
        ident.append((label, md(value)))
    if m.current is not None:
        ident.append(("Status", "sitting, on the source's current list" if m.current
                      else "not on the source's current list"))
    if m.stub:
        ident.append(("Note", "named in a record but not matched to one member of the list; "
                              "shown as the record prints the name"))
    else:
        ident.append(("Source id", "`{0}`".format(m.key)))
    out += ["- **{0}:** {1}".format(k, v) for k, v in ident]
    out.append("")
    if m.history or m.at_votes:
        out += ["## Party history", ""]
        for party, start, end, source in m.history:
            out.append("- {0}: {1} to {2} ({3})".format(
                md(party), date_long(start) if start else "start not recorded",
                date_long(end) if end else "now", source))
        if m.at_votes:
            out.append("- Recorded at votes in the store: " + "; ".join(
                "{0} (first {1}, last {2})".format(md(p), date_long(a), date_long(b))
                for p, a, b in m.at_votes) + ".")
        out.append("")
    if m.votes:
        recorded = [v for v in m.votes if not v["derived"]]
        derived = [v for v in m.votes if v["derived"]]
        out += ["## Votes on our ground ({0})".format(len(m.votes)), ""]
        if recorded:
            out.append("Recorded positions ({0}): {1}.".format(len(recorded),
                                                               position_counts(recorded)))
        if derived:
            out.append("DERIVED positions ({0}, from the group's vote, X5; not recorded per "
                       "member): {1}.".format(len(derived), position_counts(derived)))
        out.append("By area (every vote): {0}.".format(by_area(m.votes)))
        out += ["", "{0}:".format("Every vote" if len(m.votes) <= MAX_VOTES_SHOWN else
                                  "The latest {0}".format(MAX_VOTES_SHOWN)), "",
                "| Date | Position | Party at the vote | Vote | Areas |",
                "|---|---|---|---|---|"]
        out += [vote_row(spec, v) for v in m.votes[:MAX_VOTES_SHOWN]]
        if len(m.votes) > MAX_VOTES_SHOWN:
            out += ["", "{0} earlier vote(s) on our ground are counted above; each is in the "
                        "store and in the week's edition.".format(len(m.votes) - MAX_VOTES_SHOWN)]
        out.append("")
    for title, lst in (("Bills and items on our ground they authored or introduced", m.authored),
                       ("Questions on our ground", m.questions)):
        if not lst:
            continue
        out += ["## {0} ({1})".format(title, len(lst)), "",
                "| Date | Title | Key | Role | Areas |", "|---|---|---|---|---|"]
        out += [linked_row(r) for r in lst[:MAX_LINKED_SHOWN]]
        if len(lst) > MAX_LINKED_SHOWN:
            out += ["", "{0} earlier item(s) are in the store.".format(
                len(lst) - MAX_LINKED_SHOWN)]
        out.append("")
    out += ["## Notes", "", "- Party: " + spec.party_note,
            "- How these profiles are built, and what they never say: [the index's notes]"
            "(index.md#notes)."]
    if data.get("attribution"):
        out.append("- Source attribution: {0}.".format(data["attribution"].rstrip(".")))
    return "\n".join(out).rstrip() + "\n"


def notes(data):
    spec = data["spec"]
    out = ["On our ground means what the {0} edition shows: the collector's classification "
           "(taxonomy and watchlist), the edition's noise rules and mutes, and the session "
           "judge's score where it has read the vote. Titles are the source's own, "
           "verbatim.".format(data["name"]),
           "Party: " + spec.party_note,
           "In the vote table, the party's basis: 'at the vote' (the record names it), "
           "'as listed, not at the vote' (X6: the record names none), 'group's vote, X5' (the "
           "position is DERIVED from the group's vote, never recorded per member), or the "
           "party-history source that covers the day.",
           "No verdicts: which way a vote cut for our side is a signed judgement (5CA) that "
           "this country does not have yet."]
    out += list(spec.notes)
    if data.get("attribution"):
        out.append("Source attribution: {0}.".format(data["attribution"].rstrip(".")))
    out.append("Generated by {0} from the store each week; do not edit by hand.".format(GENERATOR))
    return out


def render_index(data, written, sample=False):
    # Every member with a record, and every member not known to have left:
    # Portugal's list holds every deputy of past legislatures.
    members = sorted((m for m in data["members"].values()
                      if has_record(m) or m.current is not False),
                     key=lambda m: (m.stub, fold(m.name), m.key))
    with_record = [m for m in members if has_record(m)]
    out = ["# {0}: member profiles".format(data["name"]), ""]
    if sample:
        out += ["**{0}**: built from a scoping store, never published.".format(SAMPLE_MARK), ""]
    out.append("Store read {0}. {1} member(s) listed (sitting, or with a record), {2} with a "
               "record on our ground (a profile each); {3} vote(s) on our ground in the "
               "store.".format(
                   date_long(data["today"]), len(members), len(with_record), data["votes"]))
    if data["unresolved"]:
        out.append("{0} record line(s) name someone not matched to exactly one listed member; "
                   "they are shown under the printed name.".format(data["unresolved"]))
    out += ["", "| Member | Party | Chamber | Constituency or region | Votes | Authored | "
                "Questions |", "|---|---|---|---|---|---|---|"]
    for m in members:
        name = "[{0}]({1})".format(md(m.name), written[m.key]) if m.key in written else md(m.name)
        out.append("| {0} | {1} | {2} | {3} | {4} | {5} | {6} |".format(
            name, md(m.party) or "", md(m.chamber) or "", md(m.region) or "",
            len(m.votes) or "", len(m.authored) or "", len(m.questions) or ""))
    out += ["", "## Notes", ""] + ["- " + n for n in notes(data)]
    return "\n".join(out).rstrip() + "\n"


def write(data, out_dir, sample=False):
    """Write <out_dir>/<cc>/: one file per member with a record, and index.md;
    files from earlier runs for members no longer profiled are removed.
    Returns (profiles written, files removed)."""
    target = os.path.join(out_dir, data["cc"])
    os.makedirs(target, exist_ok=True)
    written = {}
    for m in data["members"].values():
        if not has_record(m):
            continue
        fname = filename(m)
        while fname in written.values():
            fname = fname[:-3] + "-x.md"
        written[m.key] = fname
        _write(os.path.join(target, fname), render_member(data, m, sample))
    _write(os.path.join(target, "index.md"), render_index(data, written, sample))
    keep = set(written.values()) | {"index.md"}
    removed = 0
    for path in glob.glob(os.path.join(target, "*.md")):
        if os.path.basename(path) not in keep:
            os.remove(path)
            removed += 1
    return len(written), removed


def _write(path, text):
    old = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            old = fh.read()
    if old != text:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
