"""Length of service for the new country editions: every period each member
has sat, from each parliament's own open data.

    from src import member_service as ms
    ms.ensure(conn)
    got = ms.collect(conn, client, "ch", today)       # fetch, parse, replace
    svc = ms.load(conn, "ch")                          # what profiles and pages read
    ms.summary(svc_rows, today)                        # "serving since", earlier periods

    python3 tools/member_service.py ch nl fr          # the weekly step

The parity layer "length of service" (docs/country-parity-handover.md),
generalising the UK's tools/pull_service.py. That tool was built on 26 August
2026 after a member's page said "MP since 13 Aug 2026" beside votes from years
before: the roster's start date is the start of the CURRENT period, not of a
member's service. The same trap is open in every new country, and a worse one
in the party-group countries (AT, PT, NL): each member's position was DERIVED
from their group's vote by the group they sit in TODAY, so a member who
joined last month was given positions on votes taken before they sat, and a
member who changed group was given the new group's votes for the old days.

THREE SHARED TABLES, keyed by country and source (the UK's members /
member_party_history tables are keyed on Westminster ids and are left alone):

  ms_periods  one row per period a member sat: chamber, term, start, end,
              precision ('day': the source dates the member's own seat;
              'term': the source says only that the member sat in that
              term), the party or list and the group or club for the period
              where the source gives them, and the seat;
  ms_party    one row per DATED party or group spell (kind 'party' or
              'group'), where the source dates them: what corrects X6 party
              at the vote, and the group a DERIVED position follows;
  ms_runs     when each source was last read, what it covers ("every
              Nationalrat and Standerat period since 1848", "legislatures 12
              to 17, from June 2002") and from when (covers_from).

WHAT EACH COUNTRY READS (probed 11 October 2026; every source is the
parliament's own open data, no key, no login, robots.txt respected):

  ch  ws.parlament.ch OData MemberCouncilHistory: every Nationalrat and
      Standerat period since 1848, with party and parliamentary group.
  nl  Tweede Kamer gegevensmagazijn, FractieZetelPersoon: every fractie
      seat with its dates (periods are the seats joined end to end; the
      fractie is a dated group spell, matched to the vote by Fractie_Id).
  fr  Assemblee nationale AMO30 (every acteur, every mandate): the
      ASSEMBLEE mandates of legislatures 12 to 17 (from June 2002) and the
      dated political-group (GP) mandates.
  at  parlament.gv.at, each member's biography (/person/<PAD>?json=TRUE):
      every Nationalrat and Bundesrat mandate with its dates, Klub and
      Wahlpartei. One request a member, monthly.
  pt  Assembleia da Republica, InformacaoBase<LEG> for legislatures I to
      XVII: each deputy's situations (Efetivo ... dated) and groups (DepGP,
      dated). Monthly.
  it  Camera dei deputati, dati.camera.it SPARQL: every Camera mandate of
      the Republic (legislatures 1 to 19) of each sitting deputy, and the
      dated group adhesions. The Senate's SPARQL refuses us (not read).
  es  Congreso open data, odsDiputados00..14 and DiputadosActivos /
      DiputadosDeBaja: every seat since 1977 with its alta and baja, and the
      dated parliamentary group.
  pl  Sejm API, /term<N>/MP for every term: each MP's oath date and mandate
      expiry, and the club at the end of the term. Terms are linked to the
      sitting member by name and date of birth (the date is a link key only,
      never stored).
  br  Camara dos Deputados, /deputados/<id>/historico (entries and exits,
      dated) for each sitting deputy; Senado Federal /senador/<id>/mandatos
      (exercises and party filiations, dated) for each sitting senator.
      Monthly, with a time budget (members not reached keep last month's).
  cl  The Camara's militancias already in the store (cl_party_spells, from
      tools/cl_rollcalls.py): the dated party spells the Camara records for
      each deputy, joined end to end. No fetch. Senators: none (not read).
  sk  NRSR open data MP/MembersOfParliament?termNr=N for every term: who sat
      in which term (TERM precision: no seat dates), the club at the end.
  hr  sabor.hr member lists for the 10th and 11th sazivi (TERM precision).
  be  lachambre.be member list of each legislature from the 48th (TERM
      precision). Crawl-delay 5.
  hu  karzat's mandate dates already in the store (hu_members): the current
      term only. Wikidata was the other route named; its SPARQL endpoint is
      disallowed by robots.txt and is not used.
  ar, pe, do, mx  the store's own current term (the Senate roster's mandate
      term, the period, the legislature): TERM precision, no fetch.
  ec, sv, gt, co, uy  no source gives a member's service: nothing is said.

WHAT A PROFILE OR PAGE MAY SAY, AND NOTHING MORE:
  * "Serving since D": the start of the current unbroken run of day-precision
    periods in the member's current chamber (periods that abut within a day
    are one run; a dissolution, a ministerial post or a resignation breaks
    it). "At least since D" when D is the first day the source covers.
  * "Earlier periods": each with its dates as the source gives them.
  * TERM precision: "terms in the source: ..." and never a "since".
  * What the source covers, always: a period before it is not in it, and
    nothing here says this is anyone's first term.
  * No service rows: nothing about service at all, beyond "not in the source".

DERIVED POSITIONS (X5) AND PARTY AT THE VOTE (X6). adjust_derived() takes the
store's derived rows for a division and, where the source dates the member's
seats: drops a member who did not sit on the vote's day (in that chamber),
and gives each member the vote of the group they belonged to ON THE DAY
(a dated group spell matched to the vote's group label), not today's. A
member with no service rows keeps the store's derivation and its label.
party_on() is the X6 correction: a dated spell covering a vote's day.

REFRESH. A source read in full replaces every row it gave before (one
transaction); a source that fails leaves last run's rows standing and is a
[gap] line. Nothing here posts or DMs.
"""

from __future__ import annotations

import datetime
import hashlib
import io
import json
import re
import sqlite3
import time
import zipfile
from urllib.parse import quote

FEED = "member-service"

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS ms_periods (
        cc          TEXT NOT NULL,
        source      TEXT NOT NULL,      -- 'ch-council-history', 'fr-amo30', ...
        member_key  TEXT,               -- the store's member key, when the source gives its id
        member_ref  TEXT,               -- the source's own person id
        name        TEXT,               -- as the source prints it
        chamber     TEXT,               -- 'NR', 'SR', 'an', 'camara', ...
        term        TEXT,               -- the source's term label: '17', 'XVII', 'XXVI.-XXVIII. GP'
        start       TEXT,               -- ISO date; NULL when the source gives none
        end         TEXT,               -- ISO date; NULL while sitting (day) or not given (term)
        precision   TEXT NOT NULL,      -- 'day' (the member's own seat dates) | 'term'
        party       TEXT,               -- party or electoral list for the period, verbatim
        grp         TEXT,               -- parliamentary group or club for the period, verbatim
        seat        TEXT,               -- constituency, canton, circle
        last_seen   TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS ms_periods_cc ON ms_periods (cc, member_key)",
    """CREATE TABLE IF NOT EXISTS ms_party (
        cc          TEXT NOT NULL,
        source      TEXT NOT NULL,
        member_key  TEXT,
        member_ref  TEXT,
        name        TEXT,
        kind        TEXT NOT NULL,      -- 'group' (fraktion, klub, club) | 'party'
        party       TEXT NOT NULL,      -- verbatim
        party_ref   TEXT,               -- the label or id the vote record uses, where known
        start       TEXT NOT NULL,
        end         TEXT,
        last_seen   TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS ms_party_cc ON ms_party (cc, member_key)",
    """CREATE TABLE IF NOT EXISTS ms_runs (
        cc          TEXT NOT NULL,
        source      TEXT NOT NULL,
        last_seen   TEXT NOT NULL,
        periods     INTEGER,
        spells      INTEGER,
        covers      TEXT,               -- what the source covers, in words
        covers_from TEXT,               -- the first day it covers, when it starts part-way
        note        TEXT,
        PRIMARY KEY (cc, source)
    )""",
)

TABLES = ("ms_periods", "ms_party", "ms_runs")


def ensure(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


def has_tables(conn):
    try:
        got = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND "
                           "name='ms_periods'").fetchone()
    except sqlite3.Error:
        return False
    return bool(got)


# --- small helpers -------------------------------------------------------------------

def clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def iso(text):
    """'2025-02-26T00:00:00', '20250226', '26/02/2025', '26.02.2025',
    '/Date(1791555761747)/' -> '2025-02-26'; anything else None."""
    s = clean(text)
    if not s:
        return None
    m = re.match(r"/Date\((-?\d+)", s)
    if m:
        epoch = datetime.datetime(1970, 1, 1)
        return (epoch + datetime.timedelta(milliseconds=int(m.group(1)))).date().isoformat()
    m = re.match(r"(\d{4})-?(\d{2})-?(\d{2})", s)
    if m:
        return "{0}-{1}-{2}".format(*m.groups())
    m = re.match(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", s)
    if m:
        return "{2}-{1:0>2}-{0:0>2}".format(*m.groups())
    return None


def _value(text):
    """A source's text, None for empty or a bare dash ('-', the NRSR's 'no club')."""
    t = clean(text)
    return None if t in ("", "-", "\u2013") else t


def period(member_key=None, member_ref=None, name=None, chamber=None, term=None, start=None,
           end=None, precision="day", party=None, grp=None, seat=None):
    party, grp = _value(party), _value(grp)
    return {"member_key": None if member_key is None else str(member_key),
            "member_ref": None if member_ref is None else str(member_ref),
            "name": clean(name) or None, "chamber": clean(chamber) or None,
            "term": clean(term) or None, "start": iso(start), "end": iso(end),
            "precision": precision, "party": clean(party) or None, "grp": clean(grp) or None,
            "seat": clean(seat) or None}


def spell(member_key=None, member_ref=None, name=None, kind="group", party=None,
          party_ref=None, start=None, end=None):
    return {"member_key": None if member_key is None else str(member_key),
            "member_ref": None if member_ref is None else str(member_ref),
            "name": clean(name) or None, "kind": kind, "party": clean(party),
            "party_ref": clean(party_ref) or None, "start": iso(start), "end": iso(end)}


def next_day(d):
    return (datetime.date.fromisoformat(d) + datetime.timedelta(days=1)).isoformat()


def runs(periods):
    """Day-precision periods joined where they abut or overlap (a gap of at
    most one day), per chamber, oldest first: [(chamber, start, end or None,
    [periods])]. An open period (end None) closes nothing after it."""
    out = []
    by_chamber = {}
    for p in sorted((p for p in periods if p["precision"] == "day" and p["start"]),
                    key=lambda p: (p["start"], p["end"] or "9999")):
        by_chamber.setdefault(p["chamber"], []).append(p)
    for chamber, ps in by_chamber.items():
        cur = None
        for p in ps:
            if cur and (cur[2] is None or p["start"] <= next_day(cur[2])):
                if cur[2] is not None and (p["end"] is None or p["end"] > cur[2]):
                    cur[2] = p["end"]
                cur[3].append(p)
                continue
            cur = [chamber, p["start"], p["end"], [p]]
            out.append(cur)
    return sorted((tuple(r) for r in out), key=lambda r: (r[1], r[0] or ""))


def sat_on(periods, date, chamber=None):
    """True when a day-precision period covers the date (in the chamber, when
    given); False when the member has day-precision periods and none does;
    None when the source dates no seat (term precision, or no rows)."""
    day_ps = [p for p in periods if p["precision"] == "day" and p["start"]]
    if not day_ps:
        return None
    d = (date or "")[:10]
    for p in day_ps:
        if chamber and p["chamber"] and p["chamber"] != chamber:
            continue
        if p["start"] <= d and (not p["end"] or d <= p["end"]):
            return True
    return False


def party_on(spells, date, kind="group"):
    """The spell of `kind` covering an ISO date, or None (the latest-starting
    one when two overlap, as a change of group is dated on its first day)."""
    d = (date or "")[:10]
    hit = [s for s in spells if s["kind"] == kind and s["start"] and s["start"] <= d
           and (not s["end"] or d <= s["end"])]
    return sorted(hit, key=lambda s: s["start"])[-1] if hit else None


# --- the store -------------------------------------------------------------------------

def replace(conn, cc, source, today, periods=(), spells=(), covers=None, covers_from=None,
            note=None):
    """Swap one source's rows for this run's, in one transaction."""
    periods = [p for p in periods if p["start"] or p["term"]]
    spells = [s for s in spells if s["party"] and s["start"]]
    with conn:
        conn.execute("DELETE FROM ms_periods WHERE cc=? AND source=?", (cc, source))
        conn.execute("DELETE FROM ms_party WHERE cc=? AND source=?", (cc, source))
        conn.executemany(
            "INSERT INTO ms_periods (cc, source, member_key, member_ref, name, chamber, term, "
            "start, end, precision, party, grp, seat, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(cc, source, p["member_key"], p["member_ref"], p["name"], p["chamber"], p["term"],
              p["start"], p["end"], p["precision"], p["party"], p["grp"], p["seat"],
              p.get("last_seen") or today) for p in periods])
        conn.executemany(
            "INSERT INTO ms_party (cc, source, member_key, member_ref, name, kind, party, "
            "party_ref, start, end, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(cc, source, s["member_key"], s["member_ref"], s["name"], s["kind"], s["party"],
              s["party_ref"], s["start"], s["end"], s.get("last_seen") or today) for s in spells])
        conn.execute(
            "INSERT OR REPLACE INTO ms_runs (cc, source, last_seen, periods, spells, covers, "
            "covers_from, note) VALUES (?,?,?,?,?,?,?,?)",
            (cc, source, today, len(periods), len(spells), covers, covers_from, note))
    return len(periods), len(spells)


def keys(conn, sql):
    """The store's member keys (a set), or None when the table is absent or
    empty: a collector then keeps every row rather than none."""
    try:
        got = {str(r[0]) for r in conn.execute(sql)}
    except sqlite3.Error:
        return None
    return got or None


def last_read(conn, cc):
    """The newest last_seen of a country's sources, or None."""
    if not has_tables(conn):
        return None
    got = conn.execute("SELECT MAX(last_seen) FROM ms_runs WHERE cc=?", (cc,)).fetchone()
    return got[0] if got else None


# --- what the profiles and pages read -------------------------------------------------------

class Service:
    """One member's periods and dated spells, from every source of a country."""

    def __init__(self):
        self.periods, self.spells, self.sources = [], [], set()

    def sat_on(self, date, chamber=None):
        return sat_on(self.periods, date, chamber)

    def group_on(self, date):
        return party_on(self.spells, date, "group")


def load(conn, cc):
    """{'by_key': {member_key: Service}, 'by_name': [(name, ref, Service)],
    'runs': [ms_runs row dicts]} for one country, or None when it has none."""
    if not has_tables(conn):
        return None
    runs_ = [dict(zip(("source", "last_seen", "periods", "spells", "covers", "covers_from",
                       "note"), r)) for r in conn.execute(
        "SELECT source, last_seen, periods, spells, covers, covers_from, note FROM ms_runs "
        "WHERE cc=? ORDER BY source", (cc,))]
    if not runs_:
        return None
    by_key, by_ref = {}, {}

    def slot(source, member_key, member_ref, name):
        if member_key:
            s = by_key.setdefault(member_key, Service())
        else:
            s = by_ref.setdefault((source, member_ref or name), (name, member_ref, Service()))[2]
        s.sources.add(source)
        return s
    cols = ("source", "member_key", "member_ref", "name", "chamber", "term", "start", "end",
            "precision", "party", "grp", "seat")
    for r in conn.execute("SELECT {0} FROM ms_periods WHERE cc=?".format(", ".join(cols)), (cc,)):
        p = dict(zip(cols, r))
        slot(p["source"], p["member_key"], p["member_ref"], p["name"]).periods.append(p)
    cols = ("source", "member_key", "member_ref", "name", "kind", "party", "party_ref", "start",
            "end")
    for r in conn.execute("SELECT {0} FROM ms_party WHERE cc=?".format(", ".join(cols)), (cc,)):
        s = dict(zip(cols, r))
        slot(s["source"], s["member_key"], s["member_ref"], s["name"]).spells.append(s)
    return {"by_key": by_key, "by_name": list(by_ref.values()), "runs": runs_,
            "covers": {r["source"]: r for r in runs_}}


def attach(svc, roster):
    """{roster member key: Service}: rows with the store's own key by key, the
    rest by the printed name through the Roster (exactly one listed member,
    or nothing). Two sources for one member are merged."""
    out = {}
    if not svc:
        return out
    for key, s in svc["by_key"].items():
        m = roster.resolve(key, None, make_stub=False)
        if m is not None:
            _merge(out, m.key, s)
    for name, ref, s in svc["by_name"]:
        m = roster.resolve(None, name, make_stub=False) if name else None
        key = m.key if m is not None else (longer_name(roster, name) if name else None)
        if key is not None:
            _merge(out, key, s)
    return out


def longer_name(roster, name):
    """The one listed member whose every name word (two or more) is in a
    longer printed name ('Piero Fassino' in 'PIERO FRANCO RODOLFO FASSINO'),
    or None when none or several are."""
    from src import member_profiles as mp
    words = mp.name_tokens(name)
    hits = {key for toks, key in getattr(roster, "_listed", ()) if len(toks) >= 2 and toks <= words}
    return hits.pop() if len(hits) == 1 else None


def _merge(out, key, s):
    if key not in out:
        out[key] = s
        return
    t = out[key]
    if t is s:
        return
    t.periods = t.periods + s.periods
    t.spells = t.spells + s.spells
    t.sources = t.sources | s.sources


# The service sources' own chamber codes, in words, beside the profiles'
# (src/member_profiles.CHAMBERS).
CHAMBER_WORDS = {"nl": {"TK": "Tweede Kamer"}, "pt": {"AR": "Assembleia da República"},
                 "es": {"congreso": "Congreso de los Diputados"}}


def chamber_words(cc, code):
    from src import member_profiles as mp
    if not code:
        return None
    return CHAMBER_WORDS.get(cc, {}).get(code) or mp.CHAMBERS.get(cc, {}).get(code, code)


def summary(cc, s, covers, today, current=None):
    """What may be said about one member's service, as data:
    {'since', 'since_chamber', 'at_least', 'earlier': [...], 'terms': [...],
     'ended', 'sources', 'covers': [text]}. Never more than the rows support."""
    from src import member_profiles as mp  # noqa: F401  (chamber words)
    out = {"since": None, "since_chamber": None, "at_least": False, "earlier": [],
           "since_terms": [], "since_grp": [],
           "terms": [], "ended": None, "covers": [], "sources": sorted(s.sources),
           "first": None}
    for src in sorted(s.sources):
        c = covers.get(src) or {}
        if c.get("covers"):
            out["covers"].append(c["covers"])
    starts = [(covers.get(src) or {}).get("covers_from") for src in s.sources]
    covers_from = min((d for d in starts if d), default=None)

    def at_least(day):
        return bool(covers_from) and day <= covers_from
    rs = runs(s.periods)
    if rs:
        out["first"] = rs[0][1]
        open_runs = [r for r in rs if r[2] is None or r[2] >= today]
        current_run = open_runs[-1] if open_runs and current is not False else None
        if current_run:
            out["since"], out["since_chamber"] = current_run[1], current_run[0]
            out["at_least"] = at_least(current_run[1])
            out["since_terms"] = _uniq(p["term"] for p in current_run[3])
            out["since_grp"] = _uniq(p["grp"] or p["party"] for p in current_run[3])
        else:
            out["ended"] = rs[-1][2]
        for r in rs:
            if r is current_run:
                continue
            ps = r[3]
            out["earlier"].append({
                "chamber": r[0], "start": r[1], "end": r[2],
                "at_least": at_least(r[1]),
                "terms": _uniq(p["term"] for p in ps),
                "grp": _uniq(p["grp"] or p["party"] for p in ps)})
        out["earlier"].reverse()
    term_ps = [p for p in s.periods if p["precision"] == "term"]
    for p in sorted(term_ps, key=lambda p: (_term_order(p["term"]), p["start"] or "")):
        out["terms"].append({"term": p["term"], "chamber": p["chamber"], "start": p["start"],
                             "end": p["end"], "grp": p["grp"] or p["party"]})
    return out


def _uniq(values):
    out = []
    for v in values:
        if v and v not in out:
            out.append(v)
    return out


ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def _term_order(term):
    t = clean(term)
    m = re.search(r"\d+", t)
    if m:
        return int(m.group(0))
    r = re.match(r"(?:leg\.\s*)?([IVXLC]+)\b", t, re.I)
    if r:
        total, prev = 0, 0
        for ch in reversed(r.group(1).upper()):
            v = ROMAN[ch]
            total = total - v if v < prev else total + v
            prev = max(prev, v)
        return total
    return 0


# --- derived positions (X5) and party on the day (X6) --------------------------------------

# Per party-group country: the division's date and chamber, the group votes
# (label, ref, position), and the member's name (to add a member the store's
# derivation, by today's group, missed).
GROUP_VOTES = {
    "at": ("SELECT date, body FROM at_divisions WHERE division_key=?",
           "SELECT klub, klub, position FROM at_votes WHERE division_key=?",
           "SELECT pad, name FROM at_members"),
    "pt": ("SELECT date, 'AR' FROM pt_divisions WHERE division_key=?",
           "SELECT party, party, position FROM pt_group_votes WHERE division_key=? AND "
           "members IS NULL",
           "SELECT cad_id, name FROM pt_members"),
    "nl": ("SELECT date, 'TK' FROM nl_divisions WHERE besluit_id=?",
           "SELECT fractie, fractie_id, position FROM nl_votes WHERE besluit_id=? AND "
           "COALESCE(kind, 'fractie') != 'lid'",
           "SELECT persoon_id, name FROM nl_members"),
}

DERIVED_ON_DAY = "the group's vote, X5; the member's group on the day"


def fold(text):
    from src.noise import fold as _fold
    return _fold(text or "")


def by_store_key(svc):
    """{member_key: Service} for the rows that carry the store's key."""
    return dict(svc["by_key"]) if svc else {}


def adjust_derived(conn, cc, division_key, rows, services):
    """The store's derived rows for one division, corrected by the dated
    service rows (`services`, {member_key: Service}): a member who did not
    sit on the day is dropped; a member whose dated group on the day voted
    as a group gets that group's position and label (basis DERIVED_ON_DAY);
    a listed member the store missed (today's group did not vote, or they
    have left) but who sat on the day with a group that voted is added.
    Recorded rows (derived False) are never touched. Returns (rows, dropped)."""
    if cc not in GROUP_VOTES or not services:
        return rows, 0
    q_div, q_votes, q_names = GROUP_VOTES[cc]
    try:
        div = conn.execute(q_div, (division_key,)).fetchone()
        votes = conn.execute(q_votes, (division_key,)).fetchall()
    except sqlite3.Error:
        return rows, 0
    if not div or not div[0]:
        return rows, 0
    date, chamber = str(div[0])[:10], div[1]
    if cc == "at" and chamber not in ("NR", "BR"):
        return rows, 0
    by_label = {}
    for label, ref, position in votes:
        by_label[fold(label)] = (label, position)
        if ref:
            by_label["ref:" + str(ref)] = (label, position)

    def group_vote(g):
        for k in (("ref:" + g["party_ref"]) if g.get("party_ref") else None,
                  fold(g.get("party_ref")), fold(g["party"])):
            if k and k in by_label:
                return by_label[k]
        return None
    out, dropped, seen = [], 0, set()
    for p in rows:
        mk = None if p.get("member_id") is None else str(p["member_id"])
        if mk:
            seen.add(mk)
        if not p.get("derived") or mk not in services:
            out.append(p)
            continue
        s = services[mk]
        sat = s.sat_on(date, chamber if cc == "at" else None)
        if sat is False:
            dropped += 1
            continue
        g = s.group_on(date)
        if g is None:
            out.append(p)
            continue
        got = group_vote(g)
        if got is None:
            dropped += 1        # their group on the day cast no group vote here
            continue
        out.append(dict(p, party=got[0], position=got[1], basis=DERIVED_ON_DAY))
    names = None
    for mk, s in services.items():
        if mk in seen or s.sat_on(date, chamber if cc == "at" else None) is not True:
            continue
        g = s.group_on(date)
        got = group_vote(g) if g else None
        if not got:
            continue
        if names is None:
            try:
                names = {str(a): b for a, b in conn.execute(q_names)}
            except sqlite3.Error:
                names = {}
        if mk not in names:
            continue
        out.append({"member_id": mk, "name": names[mk], "party": got[0], "position": got[1],
                    "derived": True, "basis": DERIVED_ON_DAY})
    return out, dropped


class Cache:
    """Services per (connection, country), for callers that see one division
    at a time (src/country5ca.py). Keyed on the connection's id and its
    change count, so a new or written store reloads."""

    def __init__(self):
        self._got = {}

    def get(self, conn, cc):
        k = (id(conn), cc, conn.total_changes)
        if k not in self._got:
            self._got = {k: by_store_key(load(conn, cc))}
        return self._got[k]


# --- the parsers (pure; fixtures in tests/fixtures/member_service/) -------------------------

# Switzerland -------------------------------------------------------------------------------

def parse_ch_history(rows, keep=None):
    periods, spells = [], []
    for r in rows:
        council = r.get("CouncilAbbreviation")
        pn = r.get("PersonNumber")
        if pn is None or council not in ("NR", "SR"):
            continue
        key = str(pn)
        if keep is not None and key not in keep:
            continue
        name = "{0} {1}".format(r.get("FirstName") or "", r.get("LastName") or "")
        start, end = iso(r.get("DateJoining")), iso(r.get("DateLeaving"))
        periods.append(period(key, key, name, council, None, start, end, "day",
                              r.get("PartyAbbreviation"), r.get("ParlGroupAbbreviation"),
                              r.get("CantonAbbreviation")))
        if r.get("ParlGroupAbbreviation") and start:
            spells.append(spell(key, key, name, "group", r.get("ParlGroupAbbreviation"),
                                r.get("ParlGroupAbbreviation"), start, end))
        if r.get("PartyAbbreviation") and start:
            spells.append(spell(key, key, name, "party", r.get("PartyAbbreviation"), None,
                                start, end))
    return periods, spells


# Netherlands -------------------------------------------------------------------------------

def parse_nl_seats(rows, keep=None):
    """Fractie seats -> (periods: the seats joined end to end, spells: one
    group spell per seat, party_ref the Fractie_Id the vote record uses)."""
    by_person, spells = {}, []
    for r in rows:
        pid = r.get("Persoon_Id")
        fr = ((r.get("FractieZetel") or {}).get("Fractie") or {})
        if not pid or r.get("Verwijderd") or not r.get("Van"):
            continue
        if keep is not None and pid not in keep:
            continue
        s = spell(pid, pid, None, "group", fr.get("Afkorting") or fr.get("NaamNL"),
                  fr.get("Id"), r.get("Van"), r.get("TotEnMet"))
        spells.append(s)
        by_person.setdefault(pid, []).append(s)
    periods = []
    for pid, ss in by_person.items():
        seats = [period(pid, pid, None, "TK", None, s["start"], s["end"], "day", None,
                        s["party"]) for s in ss]
        for chamber, start, end, ps in runs(seats):
            grps = _uniq(p["grp"] for p in ps)
            periods.append(period(pid, pid, None, "TK", None, start, end, "day", None,
                                  " / ".join(grps)))
    return periods, spells


# France ------------------------------------------------------------------------------------

def _as_list(x):
    return x if isinstance(x, list) else ([] if x is None else [x])


def _ref(x):
    return x.get("#text") if isinstance(x, dict) else x


def parse_fr_amo30(raw, keep=None):
    """AMO30's zip bytes -> ASSEMBLEE periods and GP (political group) spells."""
    z = zipfile.ZipFile(io.BytesIO(raw))
    organs = {}
    for n in z.namelist():
        if "/organe/" in n:
            o = json.loads(z.read(n)).get("organe") or {}
            organs[_ref(o.get("uid"))] = o.get("libelleAbrege") or o.get("libelle")
    periods, spells, first = [], [], None
    for n in z.namelist():
        if "/acteur/" not in n:
            continue
        uid = n.rsplit("/", 1)[-1].split(".")[0]
        if keep is not None and uid not in keep:
            continue
        a = json.loads(z.read(n)).get("acteur") or {}
        uid = _ref(a.get("uid")) or uid
        ident = (a.get("etatCivil") or {}).get("ident") or {}
        name = "{0} {1}".format(ident.get("prenom") or "", ident.get("nom") or "")
        for m in _as_list((a.get("mandats") or {}).get("mandat")):
            t = m.get("typeOrgane")
            if t == "ASSEMBLEE":
                lieu = ((m.get("election") or {}).get("lieu") or {})
                seat = None
                if lieu.get("departement"):
                    seat = "{0}{1}".format(lieu["departement"], ", circonscription {0}".format(
                        lieu["numCirco"]) if lieu.get("numCirco") else "")
                # The seat is taken on datePriseFonction (a minister's
                # substitute gives it back months after the mandate's
                # dateDebut, the election); dateDebut only where it is absent.
                took = (m.get("mandature") or {}).get("datePriseFonction")
                periods.append(period(uid, uid, name, "an", m.get("legislature"),
                                      took or m.get("dateDebut"), m.get("dateFin"), "day",
                                      seat=seat))
            elif t == "GP":
                ref = _ref((m.get("organes") or {}).get("organeRef"))
                spells.append(spell(uid, uid, name, "group", organs.get(ref) or ref, ref,
                                    m.get("dateDebut"), m.get("dateFin")))
    return periods, spells


def fr_first_day(raw):
    """The first ASSEMBLEE mandate start anywhere in the file: what it covers from."""
    z = zipfile.ZipFile(io.BytesIO(raw))
    first = None
    for n in z.namelist():
        if "/acteur/" not in n:
            continue
        a = json.loads(z.read(n)).get("acteur") or {}
        for m in _as_list((a.get("mandats") or {}).get("mandat")):
            took = (m.get("mandature") or {}).get("datePriseFonction") or m.get("dateDebut")
            if m.get("typeOrgane") == "ASSEMBLEE" and took:
                d = iso(took)
                first = d if first is None or d < first else first
    return first


# Austria ------------------------------------------------------------------------------------

def parse_at_person(pad, reply):
    """One biography -> (periods, spells): every Nationalrat and Bundesrat
    mandate with its dates, Wahlpartei and Klub (full name)."""
    bio = (((reply or {}).get("content") or {}).get("biografie") or {})
    name = ((reply or {}).get("meta") or {}).get("description")
    periods, spells = [], []
    for m in (bio.get("mandatefunktionen") or {}).get("mandate") or []:
        g = m.get("gremium")
        if g not in ("NR", "BR"):
            continue
        term = re.search(r"\(([^()]*GP)\)", m.get("bez") or "")
        start, end = iso(m.get("mandatVon")), iso(m.get("mandatBis"))
        periods.append(period(pad, pad, name, g, term.group(1) if term else None, start, end,
                              "day", m.get("wahlpartei"), m.get("klub"), m.get("wahlkreis")))
        if m.get("klub") and start:
            spells.append(spell(pad, pad, name, "group", m["klub"], None, start, end))
    return periods, spells


def at_klub_map(spells, latest):
    """{full Klub name: the vote record's abbreviation} from the sitting
    members: their open spell's full name against the Klub the member list
    gives them now (at_members.klub). Majority per full name; a name the
    sitting members do not settle is left unmapped."""
    votes = {}
    for s in spells:
        if s["end"] or s["member_key"] not in latest or not latest[s["member_key"]]:
            continue
        votes.setdefault(s["party"], {}).setdefault(latest[s["member_key"]], 0)
        votes[s["party"]][latest[s["member_key"]]] += 1
    out = {}
    for full, counts in votes.items():
        best = sorted(counts.items(), key=lambda kv: -kv[1])
        if len(best) == 1 or best[0][1] > best[1][1]:
            out[full] = best[0][0]
    return out


# Portugal -----------------------------------------------------------------------------------

def parse_pt_base(data, keep=None):
    """One legislature's InformacaoBase -> (periods: each Efetivo situation,
    dated; spells: each DepGP, dated)."""
    periods, spells = [], []
    for dep in (data or {}).get("Deputados") or []:
        if dep.get("DepCadId") is None:
            continue
        key = str(int(dep["DepCadId"]))
        if keep is not None and key not in keep:
            continue
        name, leg = dep.get("DepNomeParlamentar"), dep.get("LegDes")
        gps = [g for g in dep.get("DepGP") or [] if g and g.get("gpSigla")]
        for s in dep.get("DepSituacao") or []:
            if not s or not (s.get("sioDes") or "").lower().startswith("efetiv"):
                continue
            start = iso(s.get("sioDtInicio"))
            grp = None
            if start:
                on = [g for g in gps if (iso(g.get("gpDtInicio")) or "") <= start and
                      (not g.get("gpDtFim") or start <= iso(g.get("gpDtFim")))]
                grp = on[-1]["gpSigla"] if on else None
            periods.append(period(key, key, name, "AR", leg, start, s.get("sioDtFim"), "day",
                                  None, grp, dep.get("DepCPDes")))
        for g in gps:
            spells.append(spell(key, key, name, "group", g["gpSigla"], g["gpSigla"],
                                g.get("gpDtInicio"), g.get("gpDtFim")))
    return periods, spells


# Italy --------------------------------------------------------------------------------------

def q_it_mandates(leg):
    return ("PREFIX ocd: <http://dati.camera.it/ocd/>\n"
            "PREFIX foaf: <http://xmlns.com/foaf/0.1/>\n"
            "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
            "SELECT DISTINCT ?d ?first ?surname ?ms ?me ?gs ?ge ?glabel WHERE {{ "
            "?d a ocd:deputato ; ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/"
            "repubblica_{0}> ; ocd:rif_mandatoCamera ?m . ?m ocd:startDate ?ms . "
            "OPTIONAL {{ ?m ocd:endDate ?me }} OPTIONAL {{ ?d foaf:firstName ?first }} "
            "OPTIONAL {{ ?d foaf:surname ?surname }} "
            "OPTIONAL {{ ?d ocd:aderisce ?a . ?a ocd:startDate ?gs . "
            "OPTIONAL {{ ?a ocd:endDate ?ge }} OPTIONAL {{ ?a rdfs:label ?glabel }} }} }}"
            ).format(int(leg))


def parse_it_camera(bindings, leg, keep_refs=None):
    """SPARQL rows for one legislature -> (periods, spells, {ref: name}). A
    person is the number in the deputato URI (d302103_19 -> 302103), the same
    in every legislature."""
    periods, spells, names, seen = [], [], {}, set()
    for b in bindings:
        m = re.search(r"/d(\d+)_\d+$", b.get("d") or "")
        if not m:
            continue
        ref = m.group(1)
        if keep_refs is not None and ref not in keep_refs:
            continue
        name = "{0} {1}".format(b.get("first") or "", b.get("surname") or "").strip()
        names.setdefault(ref, name)
        pk = (ref, b.get("ms"), b.get("me"))
        if pk not in seen:
            seen.add(pk)
            periods.append(period(None, ref, name, "camera", str(leg), b.get("ms"), b.get("me"),
                                  "day"))
        if b.get("gs"):
            sk = (ref, b.get("gs"), b.get("ge"), b.get("glabel"))
            if sk not in seen:
                seen.add(sk)
                label = re.sub(r"\s*\([\d.]+-?[\d.]*\)\s*$", "", b.get("glabel") or "")
                spells.append(spell(None, ref, name, "group", label, None, b.get("gs"),
                                    b.get("ge")))
    return periods, spells, names


# Spain --------------------------------------------------------------------------------------

def parse_es_file(records, leg, keep=None):
    """One odsDiputadosNN / DiputadosActivos / DiputadosDeBaja file: each seat
    (alta to baja) and each dated group membership. The BIOGRAFIA is never read."""
    periods, spells = [], []
    for r in records or []:
        name = clean(r.get("NOMBRE"))
        if not name or (keep is not None and name not in keep):
            continue
        periods.append(period(name, None, name, "Congreso de los Diputados", str(leg),
                              r.get("FECHAALTA"),
                              r.get("FECHABAJA"), "day", r.get("FORMACIONELECTORAL"),
                              r.get("GRUPOPARLAMENTARIO"), r.get("CIRCUNSCRIPCION")))
        if r.get("GRUPOPARLAMENTARIO") and r.get("FECHAALTAENGRUPOPARLAMENTARIO"):
            spells.append(spell(name, None, name, "group", r["GRUPOPARLAMENTARIO"], None,
                                r["FECHAALTAENGRUPOPARLAMENTARIO"],
                                r.get("FECHABAJAENGRUPOPARLAMENTARIO")))
    return periods, spells


ES_FILE = re.compile(r'href="(/webpublica/opendata/diputados/'
                     r'(odsDiputados(\d\d)|DiputadosActivos|DiputadosDeBaja)__\d+\.json)"')


def es_files(page, current_leg):
    """[(url path, legislature)] from the open-data page, one per stem."""
    out, seen = [], set()
    for path, stem, nn in ES_FILE.findall(page or ""):
        stem_key = stem
        if stem_key in seen:
            continue
        seen.add(stem_key)
        out.append((path, int(nn) if nn else current_leg))
    return out


# Poland --------------------------------------------------------------------------------------

def pl_person(mp):
    """A link key across terms: the name and date of birth, hashed. The date
    itself is never stored."""
    raw = "{0}|{1}".format(fold(mp.get("firstLastName")), mp.get("birthDate") or "")
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def parse_pl_terms(terms, mps_by_term, current, keep=None):
    """{term: [MP]} -> (periods) for every person who sits in the current term
    (keep: the store's '10/<id>' keys). Each period's member_key is the
    current term's key; the club is the club at the end of that term or
    mandate, as the API gives it."""
    ends = {t["num"]: t.get("to") for t in terms}
    starts = {t["num"]: t.get("from") for t in terms}
    now = {}
    for mp in mps_by_term.get(current) or []:
        key = "{0}/{1}".format(current, mp["id"])
        if keep is None or key in keep:
            now[pl_person(mp)] = key
    periods = []
    for term, mps in sorted(mps_by_term.items()):
        for mp in mps:
            person = pl_person(mp)
            if person not in now:
                continue
            start = mp.get("oathDate")
            end = mp.get("mandateExpiryDate") or (None if mp.get("active") and term == current
                                                   else ends.get(term))
            precision = "day" if start else "term"
            periods.append(period(now[person], "{0}/{1}".format(term, mp["id"]),
                                  mp.get("firstLastName"), "Sejm", str(term),
                                  start or starts.get(term), end, precision, None,
                                  mp.get("club"), mp.get("districtName")))
    return periods


# Brazil --------------------------------------------------------------------------------------

def parse_br_historico(member_key, reply, today):
    """A deputy's status history -> periods: an 'Entrada' opens one, a
    'Saida' closes it. Events dated after today are ignored."""
    events = []
    for e in (reply or {}).get("dados") or []:
        d = (e.get("dataHora") or "")[:10]
        desc = fold(e.get("descricaoStatus"))
        if not d or d > today:
            continue
        if desc.startswith("entrada"):
            events.append((e["dataHora"], "in", e))
        elif desc.startswith("saida"):
            events.append((e["dataHora"], "out", e))
    periods, cur = [], None
    for when, kind, e in sorted(events, key=lambda x: x[0]):
        if kind == "in" and cur is None:
            cur = period(member_key, e.get("id"), e.get("nome"), "camara",
                         str(e.get("idLegislatura") or ""), when[:10], None, "day",
                         e.get("siglaPartido"), None, e.get("siglaUf"))
        elif kind == "out" and cur is not None:
            cur["end"] = iso(when)
            periods.append(cur)
            cur = None
    if cur is not None:
        periods.append(cur)
    return periods


def parse_br_mandatos(member_key, reply):
    """A senator's Senate mandates -> (periods: each exercise, dated; spells:
    each party filiation, dated)."""
    parl = (((reply or {}).get("MandatoParlamentar") or {}).get("Parlamentar") or {})
    name = parl.get("Nome")
    periods, spells = [], []
    for m in _as_list((parl.get("Mandatos") or {}).get("Mandato")):
        legs = [x.get("NumeroLegislatura") for x in (m.get("PrimeiraLegislaturaDoMandato") or {},
                                                      m.get("SegundaLegislaturaDoMandato") or {})
                if x.get("NumeroLegislatura")]
        for ex in _as_list((m.get("Exercicios") or {}).get("Exercicio")):
            periods.append(period(member_key, parl.get("Codigo"), name, "senado", "-".join(legs),
                                  ex.get("DataInicio"), ex.get("DataFim"), "day", None, None,
                                  m.get("UfParlamentar")))
        for p in _as_list((m.get("Partidos") or {}).get("Partido")):
            if p.get("Sigla") and p.get("DataFiliacao"):
                spells.append(spell(member_key, parl.get("Codigo"), name, "party", p["Sigla"],
                                    None, p["DataFiliacao"], p.get("DataDesfiliacao")))
    seen, uniq = set(), []
    for s in spells:
        k = (s["party"], s["start"], s["end"])
        if k not in seen:
            seen.add(k)
            uniq.append(s)
    return periods, uniq


# Slovakia ------------------------------------------------------------------------------------

def parse_sk_term(rows, term, keep=None):
    out = []
    for r in rows or []:
        mid = r.get("mpId")
        if mid is None or (keep is not None and str(mid) not in keep):
            continue
        out.append(period(mid, mid, r.get("name"), "NRSR", str(term), None, None, "term",
                          r.get("partyDepartmentName"), r.get("lastClubAbbr")))
    return out


# --- the fetchers ----------------------------------------------------------------------------

CH_API = "https://ws.parlament.ch/odata.svc/"
NL_API = "https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/"
FR_AMO30 = ("https://data.assemblee-nationale.fr/static/openData/repository/17/amo/"
            "tous_acteurs_mandats_organes_xi_legislature/"
            "AMO30_tous_acteurs_tous_mandats_tous_organes_historique.json.zip")
AT_PERSON = "https://www.parlament.gv.at/person/{0}?json=TRUE"
IT_SPARQL = "https://dati.camera.it/sparql"
IT_LEGISLATURES = range(1, 20)
ES_PAGE = "https://www.congreso.es/es/opendata/diputados"
ES_BASE = "https://www.congreso.es"
ES_CURRENT = 15
PL_API = "https://api.sejm.gov.pl/sejm"
BR_CAMARA = "https://dadosabertos.camara.leg.br/api/v2/deputados/{0}/historico"
BR_SENADO = "https://legis.senado.leg.br/dadosabertos/senador/{0}/mandatos.json"
SK_API = "https://www.nrsr.sk/opendata/1/sk/MP/MembersOfParliament?termNr={0}"
SK_CURRENT = 9


def fetch_ch(conn, client, today, log=print, **_):
    keep = keys(conn, "SELECT person_number FROM ch_members")
    rows, skip = [], 0
    while True:
        got = client.get_json("{0}MemberCouncilHistory?$filter=Language%20eq%20'DE'&$top=1000"
                              "&$skip={1}&$format=json".format(CH_API, skip), FEED,
                              "ch-council-history-{0}".format(skip))
        batch = got.get("d") or []
        if isinstance(batch, dict):
            batch = batch.get("results") or []
        rows += batch
        if len(batch) < 1000:
            break
        skip += 1000
    periods, spells = parse_ch_history(rows, keep)
    log("  ch: {0} period(s), {1} spell(s) from {2} history row(s)".format(
        len(periods), len(spells), len(rows)))
    return {"ch-council-history": (periods, spells, {
        "covers": "every Nationalrat and Ständerat period since 1848 (MemberCouncilHistory)",
        "covers_from": None})}


def fetch_nl(conn, client, today, log=print, **_):
    keep = keys(conn, "SELECT persoon_id FROM nl_members")
    q = ("$filter=" + quote("Verwijderd eq false", safe="") + "&$expand=" +
         quote("FractieZetel($expand=Fractie($select=Id,Afkorting,NaamNL))", safe="(),=$"))
    url, rows, n = "{0}FractieZetelPersoon?{1}".format(NL_API, q), [], 0
    while url:
        got = client.get_json(url, FEED, "nl-fractiezetels-{0}".format(n))
        rows += got.get("value") or []
        url = got.get("@odata.nextLink")
        n += 1
    periods, spells = parse_nl_seats(rows, keep)
    first = min((iso(r.get("Van")) for r in rows if r.get("Van")), default=None)
    log("  nl: {0} period(s), {1} fractie spell(s)".format(len(periods), len(spells)))
    return {"nl-fractiezetels": (periods, spells, {
        "covers": "every Tweede Kamer fractie seat the gegevensmagazijn records (the earliest "
                  "from {0})".format(long_date(first) if first else "?"), "covers_from": first})}


def fetch_fr(conn, client, today, log=print, **_):
    keep = keys(conn, "SELECT acteur_ref FROM fr_members")
    raw = client.get_bytes(FR_AMO30, FEED, "fr-amo30", timeout=300)
    periods, spells = parse_fr_amo30(raw, keep)
    first = fr_first_day(raw)
    log("  fr: {0} ASSEMBLEE period(s), {1} group spell(s)".format(len(periods), len(spells)))
    return {"fr-amo30": (periods, spells, {
        "covers": "every Assemblée nationale mandate from the 12th legislature (from {0}; "
                  "AMO30)".format(long_date(first) if first else "June 2002"),
        "covers_from": first})}


def fetch_at(conn, client, today, log=print, budget=None, **_):
    import urllib.robotparser
    members = {str(a): b for a, b in conn.execute("SELECT pad, klub FROM at_members")}
    robots = None
    try:
        text = client.get_text("https://www.parlament.gv.at/robots.txt", FEED, "at-robots",
                               archive=False)
        robots = urllib.robotparser.RobotFileParser()
        robots.parse(text.splitlines())
    except Exception as exc:  # unreadable robots: nothing skipped, and said
        log("  at: robots.txt unreadable ({0}); no path skipped".format(str(exc)[:60]))
    client.set_host_throttle("www.parlament.gv.at", 1.0)
    periods, spells, read, skipped = [], [], set(), 0
    started = time.monotonic()
    for pad in read_order(conn, "at", "at-biografien", members):
        url = AT_PERSON.format(pad)
        if robots is not None and not robots.can_fetch(client.user_agent, url):
            skipped += 1
            continue
        if budget and time.monotonic() - started > budget:
            break
        p, s = parse_at_person(pad, client.get_json(url, FEED, "at-person-{0}".format(pad)))
        periods += p
        spells += s
        read.add(pad)
    kept = carry_over(conn, "at", "at-biografien", read)
    periods += kept[0]
    spells += kept[1]
    mapping = at_klub_map([x for x in spells if x.get("party_ref") is None], members)
    for x in spells:
        if x.get("party_ref") is None and mapping.get(x["party"]):
            # Shown and matched as the vote record names the Klub ('SPÖ').
            x["party_ref"] = x["party"] = mapping[x["party"]]
    for x in periods:
        x["grp"] = mapping.get(x["grp"], x["grp"])
    log("  at: {0} of {1} biography(ies) read ({2} disallowed by robots.txt); {3} period(s)"
        .format(len(read), len(members), skipped, len(periods)))
    return {"at-biografien": (periods, spells, {
        "covers": "every Nationalrat and Bundesrat mandate the Parliament's biographies list",
        "covers_from": None,
        "note": "{0} of {1} read this run".format(len(read), len(members))})}


def carry_over(conn, cc, source, read):
    """Last run's rows for the members not read this run (a budget or a
    failure), so a partial run never empties a member's service."""
    if not has_tables(conn):
        return [], []
    pcols = ("member_key", "member_ref", "name", "chamber", "term", "start", "end",
             "precision", "party", "grp", "seat", "last_seen")
    scols = ("member_key", "member_ref", "name", "kind", "party", "party_ref", "start", "end",
             "last_seen")
    ps = [dict(zip(pcols, r)) for r in conn.execute(
        "SELECT {0} FROM ms_periods WHERE cc=? AND source=?".format(", ".join(pcols)),
        (cc, source)) if r[0] not in read]
    ss = [dict(zip(scols, r)) for r in conn.execute(
        "SELECT {0} FROM ms_party WHERE cc=? AND source=?".format(", ".join(scols)),
        (cc, source)) if r[0] not in read]
    return ps, ss


def read_order(conn, cc, source, member_keys):
    """Members for a per-member source, longest unread first: never read,
    then by the date their rows were last read (carried rows keep theirs),
    so a run cut short by its budget is finished by the next ones."""
    last = {}
    if has_tables(conn):
        for k, seen in conn.execute("SELECT member_key, MIN(last_seen) FROM ms_periods WHERE "
                                    "cc=? AND source=? GROUP BY member_key", (cc, source)):
            last[k] = seen
    return sorted(member_keys, key=lambda k: (last.get(k) or "", k))


def fetch_pt(conn, client, today, log=print, **_):
    from tools import pt_rollcalls as pt
    keep = keys(conn, "SELECT cad_id FROM pt_members")
    page_path, stem = pt.DATASETS["members"]
    page = client.get_text(pt.SITE + page_path, FEED, "pt-informacaobase", archive=False)
    legs = [t.split()[0] for _h, t in pt.anchors(page)
            if re.match(r"^[IVXLC]+ Legislatura$", t)]
    legs = list(dict.fromkeys(legs))
    if not legs:
        raise ValueError("the InformacaoBase page lists no legislature")
    periods, spells, read = [], [], []
    for leg in legs:
        folder = pt.folder_link(page, leg)
        listing = client.get_text(folder, FEED, "pt-folder-{0}".format(leg), archive=False)
        urls = pt_json_links(pt.anchors(listing), stem, leg)
        if not urls:
            if leg == legs[0]:
                raise ValueError("no {0}{1}_json.txt".format(stem, leg))
            log("  pt: legislature {0} lists no {1} JSON; not read".format(leg, stem))
            continue
        for part, url in urls:
            data = json.loads(client.get_bytes(url, FEED, "pt-base-{0}{1}".format(leg, part),
                                               timeout=300).decode("utf-8-sig"))
            p, s = parse_pt_base(data, keep)
            periods += p
            spells += s
        read.append(leg)
    log("  pt: {0} legislature(s), {1} period(s), {2} group spell(s)".format(
        len(read), len(periods), len(spells)))
    return {"pt-informacaobase": (periods, spells, {
        "covers": "every legislature from the {0} to the {1}, each deputy's situations and "
                  "groups (InformacaoBase)".format(read[-1], read[0]),
        "covers_from": None if read[-1] == "I" else min(
            (p["start"] for p in periods if p["start"]), default=None)})}


def pt_json_links(anchors, stem, leg):
    """[(part, href)] for <stem><leg>_json.txt, or the parts the first
    legislature is split in (InformacaoBaseIA_json.txt, ...IB_json.txt)."""
    # The parts are lettered A and B: never a Roman numeral's letter, so the
    # I legislature's pattern cannot take the II's file.
    pat = re.compile(r"^{0}{1}([AB]?)_json\.txt$".format(re.escape(stem), re.escape(leg)))
    out = []
    for href, text in anchors:
        m = pat.match(text or "")
        if m and "webutils/docs/" in href:
            out.append((m.group(1), href))
    return out


def _sparql(client, endpoint, query, slug):
    url = "{0}?query={1}&format={2}".format(endpoint, quote(query),
                                           quote("application/sparql-results+json"))
    got = client.get_json(url, FEED, slug, timeout=180)
    return [{k: v.get("value") for k, v in b.items()}
            for b in (got.get("results") or {}).get("bindings") or []]


def fetch_it(conn, client, today, log=print, **_):
    legs = list(IT_LEGISLATURES)
    current = legs[-1]
    p_now, s_now, names = parse_it_camera(
        _sparql(client, IT_SPARQL, q_it_mandates(current), "it-camera-{0}".format(current)),
        current)
    refs = set(names)
    periods, spells = p_now, s_now
    for leg in legs[:-1]:
        p, s, _n = parse_it_camera(_sparql(client, IT_SPARQL, q_it_mandates(leg),
                                           "it-camera-{0}".format(leg)), leg, refs)
        periods += p
        spells += s
    for row in periods + spells:
        row["name"] = names.get(row["member_ref"]) or row["name"]
    log("  it: {0} Camera period(s), {1} group spell(s) for {2} sitting deputy(ies)".format(
        len(periods), len(spells), len(refs)))
    return {"it-camera": (periods, spells, {
        "covers": "every Camera dei deputati mandate of the Republic (legislatures 1 to {0}); "
                  "the Senate is not read (its SPARQL refuses us)".format(current),
        "covers_from": None})}


def fetch_es(conn, client, today, log=print, **_):
    keep = keys(conn, "SELECT name FROM es_members")
    page = client.get_text(ES_PAGE, FEED, "es-diputados-page", archive=False)
    files = es_files(page, ES_CURRENT)
    if not any(leg == ES_CURRENT for _p, leg in files):
        raise ValueError("the open-data page links no current-legislature file")
    periods, spells = [], []
    for path, leg in files:
        p, s = parse_es_file(client.get_json(ES_BASE + path, FEED, "es-{0}".format(
            path.rsplit("/", 1)[-1].split("__")[0])), leg, keep)
        periods += p
        spells += s
    log("  es: {0} file(s), {1} seat(s), {2} group spell(s)".format(len(files), len(periods),
                                                                   len(spells)))
    return {"es-diputados": (periods, spells, {
        "covers": "every seat in the Congreso since the Constituent legislature (1977)",
        "covers_from": None})}


def fetch_pl(conn, client, today, log=print, **_):
    keep = keys(conn, "SELECT mp_key FROM pl_members")
    terms = client.get_json(PL_API + "/term", FEED, "pl-terms")
    current = max(t["num"] for t in terms if t.get("current")) if any(
        t.get("current") for t in terms) else max(t["num"] for t in terms)
    by_term = {}
    for t in sorted(t["num"] for t in terms):
        got = client.get_json("{0}/term{1}/MP".format(PL_API, t), FEED, "pl-mp-term{0}".format(t))
        if got:
            by_term[t] = got
    periods = parse_pl_terms(terms, by_term, current, keep)
    first = min(by_term) if by_term else None
    start = next((t.get("from") for t in terms if t["num"] == first), None)
    log("  pl: terms {0}, {1} period(s)".format(",".join(str(t) for t in sorted(by_term)),
                                                 len(periods)))
    return {"pl-sejm-terms": (periods, [], {
        "covers": "every Sejm term with a member list in the API (from term {0}, {1})".format(
            first, long_date(start)), "covers_from": start})}


def fetch_br(conn, client, today, log=print, budget=None, **_):
    members = {k: (c, sid) for k, c, sid in conn.execute(
        "SELECT member_key, chamber, source_id FROM br_members WHERE in_office=1")}
    periods, spells, read = [], [], set()
    started = time.monotonic()
    for key in read_order(conn, "br", "br-historico", members):
        chamber, sid = members[key]
        if budget and time.monotonic() - started > budget:
            break
        if chamber == "camara":
            periods += parse_br_historico(key, client.get_json(BR_CAMARA.format(sid), FEED,
                                                               "br-historico-{0}".format(sid)),
                                          today)
        else:
            p, s = parse_br_mandatos(key, client.get_json(BR_SENADO.format(sid), FEED,
                                                          "br-mandatos-{0}".format(sid)))
            periods += p
            spells += s
        read.add(key)
    kept = carry_over(conn, "br", "br-historico", read)
    periods += kept[0]
    spells += kept[1]
    log("  br: {0} of {1} member(s) read; {2} period(s)".format(len(read), len(members),
                                                                len(periods)))
    return {"br-historico": (periods, spells, {
        "covers": "the Câmara's status history of each sitting deputy and the Senado's "
                  "mandates of each sitting senator (each chamber separately: a deputy's "
                  "Senate years, or a senator's Câmara years, are not linked)",
        "covers_from": None, "note": "{0} of {1} read this run".format(len(read), len(members))})}


def fetch_sk(conn, client, today, log=print, **_):
    keep = keys(conn, "SELECT mp_id FROM sk_members")
    periods, terms = [], []
    for term in range(1, SK_CURRENT + 1):
        try:
            rows = client.get_json(SK_API.format(term), FEED, "sk-mps-term{0}".format(term))
        except Exception as exc:  # an old term the API does not hold
            log("  sk: term {0} not read ({1})".format(term, str(exc)[:60]))
            continue
        if rows:
            terms.append(term)
            periods += parse_sk_term(rows, term, keep)
    log("  sk: terms {0}, {1} term record(s)".format(",".join(map(str, terms)), len(periods)))
    return {"sk-terms": (periods, [], {
        "covers": "which electoral terms each member sat in (terms {0} to {1}; the source "
                  "gives no seat dates)".format(terms[0] if terms else "?", SK_CURRENT),
        "covers_from": None})}


def fetch_hr(conn, client, today, log=print, **_):
    from tools import hr_rollcalls as hr
    listed = {}
    for saziv in sorted(hr.SAZIV_NODE):
        seen, page = {}, 0
        while page < 20:
            text = client.get_text(hr.MEMBERS.format(hr.SAZIV_NODE[saziv], page), FEED,
                                   "hr-members-{0}-p{1}".format(saziv, page))
            rows, _total = hr.parse_members(text)
            fresh = [r for r in rows if r["slug"] not in seen]
            for r in fresh:
                seen[r["slug"]] = r
            if not fresh:
                break
            page += 1
        listed[saziv] = list(seen.values())
    current = max(listed)
    by_name = {}
    for r in listed[current]:
        k = fold(r["name"])
        by_name[k] = None if k in by_name else r["slug"]
    periods = []
    for saziv, rows in sorted(listed.items()):
        for r in rows:
            key = r["slug"] if saziv == current else by_name.get(fold(r["name"]))
            if not key:
                continue
            periods.append(period(key, r["slug"], r["name"], "Sabor", str(saziv), None, None,
                                  "term", None, r.get("party"), r.get("constituency")))
    log("  hr: sazivi {0}, {1} term record(s)".format(",".join(map(str, sorted(listed))),
                                                    len(periods)))
    return {"hr-sazivi": (periods, [], {
        "covers": "the {0}th and {1}th sazivi only (the member lists the Sabor's site "
                  "filters by); no seat dates".format(min(listed), current),
        "covers_from": None})}


def fetch_be(conn, client, today, log=print, **_):
    from tools import be_rollcalls as be
    client.set_host_throttle("www.lachambre.be", 5.0)       # robots.txt: Crawl-delay 5
    periods, read = [], []
    for leg in range(48, be.CURRENT_LEGISLATURE + 1):
        rows = be.parse_members(be.decode(client.get_bytes(
            be.MEMBERS_LEGISLATURE.format(leg), FEED, "be-members-{0}".format(leg))))
        if rows:
            read.append(leg)
        for key, name, group in rows:
            periods.append(period(key, key, name, "Chambre / Kamer", str(leg), None, None,
                                  "term", None, group))
    keep = keys(conn, "SELECT member_key FROM be_members")
    if keep is not None:
        periods = [p for p in periods if p["member_key"] in keep]
    log("  be: legislatures {0}, {1} term record(s)".format(",".join(map(str, read)),
                                                          len(periods)))
    return {"be-legislatures": (periods, [], {
        "covers": "the Chamber's member list of each legislature from the 48th; no seat "
                  "dates", "covers_from": None})}


# The store's own current term, no fetch. --------------------------------------------------

def _store_rows(conn, sql):
    try:
        return conn.execute(sql).fetchall()
    except sqlite3.Error:
        return []


def from_cl_store(conn, client, today, log=print, **_):
    by_member = {}
    for mk, party, start, end in _store_rows(
            conn, "SELECT member_key, party, start, end FROM cl_party_spells "
                  "WHERE member_key LIKE 'D-%' AND start IS NOT NULL"):
        by_member.setdefault(mk, []).append(period(mk, mk, None, "camara", None, start, end,
                                                   "day", None, party))
    periods = []
    for mk, ps in by_member.items():
        for chamber, start, end, group in runs(ps):
            periods.append(period(mk, mk, None, "camara", None, start, end, "day", None,
                                  " / ".join(_uniq(p["grp"] for p in group))))
    log("  cl: {0} period(s) from the Cámara's militancias".format(len(periods)))
    return {"cl-militancias": (periods, [], {
        "covers": "the Cámara's militancias (dated party spells it records for each sitting "
                  "deputy's time in the chamber), joined end to end; senators not read",
        "covers_from": None})}


def from_hu_store(conn, client, today, log=print, **_):
    periods = [period(mid, mid, name, "Országgyűlés", None, a, b, "day", None, fac)
               for mid, name, fac, a, b in _store_rows(
                   conn, "SELECT member_id, name, faction, mandate_from, mandate_to "
                         "FROM hu_members WHERE mandate_from IS NOT NULL")]
    log("  hu: {0} mandate(s) from karzat".format(len(periods)))
    first = min((p["start"] for p in periods), default=None)
    return {"hu-karzat": (periods, [], {
        "covers": "the current term's mandates only, from karzat (CC BY 4.0); earlier terms "
                  "are not read (Wikidata's query service is closed to robots)",
        "covers_from": first})}


def from_ar_store(conn, client, today, log=print, **_):
    periods = [period(k, k, n, ch, None, a, b, "term", None, bloc, prov)
               for k, n, ch, bloc, prov, a, b in _store_rows(
                   conn, "SELECT member_key, name, chamber, bloc, province, term_start, term_end "
                         "FROM ar_members WHERE term_start IS NOT NULL")]
    log("  ar: {0} current term(s) from the roster".format(len(periods)))
    return {"ar-roster": (periods, [], {
        "covers": "the current mandate term on the Senate roster only (the term's dates, not "
                  "the member's own seat dates); earlier terms are not read",
        "covers_from": None})}


def _term_store(cc, sql, chamber_sql_label, covers):
    def run(conn, client, today, log=print, **_):
        periods = [period(k, k, n, ch, t, None, None, "term", None, g)
                   for k, n, ch, t, g in _store_rows(conn, sql) if t]
        log("  {0}: {1} term record(s) from the store".format(cc, len(periods)))
        return {"{0}-{1}".format(cc, chamber_sql_label): (periods, [], {
            "covers": covers, "covers_from": None})}
    return run


from_pe_store = _term_store(
    "pe", "SELECT member_key, name, chamber, period, bancada FROM pe_members", "roster",
    "the current period on the member roster only; earlier periods are not read")
from_do_store = _term_store(
    "do", "SELECT member_key, name, role, period, party FROM do_members", "roster",
    "the current period on the SIL's member list only; earlier periods are not read")


def from_mx_store(conn, client, today, log=print, **_):
    rows = _store_rows(conn, "SELECT member_key, name, legislature, party FROM mx_members")
    latest = max((r[2] for r in rows), default=None)
    by_name = {}
    for k, n, leg, _p in rows:
        if leg == latest:
            f = fold(n)
            by_name[f] = None if f in by_name else k
    periods = []
    for k, n, leg, party in rows:
        key = k if leg == latest else by_name.get(fold(n))
        if key:
            periods.append(period(key, k, n, "Cámara de Diputados", "{0}".format(leg), None,
                                  None, "term", None, party))
    log("  mx: {0} term record(s) from the store".format(len(periods)))
    return {"mx-sitl": (periods, [], {
        "covers": "the legislatures the store has read from SITL only; no seat dates",
        "covers_from": None})}


FETCHERS = {"ch": fetch_ch, "nl": fetch_nl, "fr": fetch_fr, "at": fetch_at, "pt": fetch_pt,
            "it": fetch_it, "es": fetch_es, "pl": fetch_pl, "br": fetch_br, "sk": fetch_sk,
            "hr": fetch_hr, "be": fetch_be, "cl": from_cl_store, "hu": from_hu_store,
            "ar": from_ar_store, "pe": from_pe_store, "do": from_do_store, "mx": from_mx_store}
COUNTRIES = tuple(FETCHERS)
# How often each country's source is re-read: weekly where it is one or two
# requests, monthly where it is a request a member or a dozen large files.
STALE_DAYS = {"ch": 7, "nl": 7, "cl": 7, "hu": 7, "ar": 7, "pe": 7, "do": 7, "mx": 7,
              "fr": 28, "at": 28, "pt": 28, "it": 28, "es": 28, "pl": 28, "br": 28,
              "sk": 28, "hr": 28, "be": 28}
# Per-member sources take a time budget (seconds); members not reached keep
# last run's rows.
BUDGET = {"at": 900, "br": 1500}
NO_SOURCE = ("ec", "sv", "gt", "co", "uy")


def partial(conn, cc):
    """True when a per-member source's last run stopped short ('240 of 594
    read this run'): it is then due again a week later, not a month."""
    for (note,) in conn.execute("SELECT note FROM ms_runs WHERE cc=?", (cc,)):
        m = re.match(r"(\d+) of (\d+) read", note or "")
        if m and int(m.group(1)) < int(m.group(2)):
            return True
    return False


def due(conn, cc, today, stale_days=None):
    last = last_read(conn, cc)
    if not last:
        return True
    days = STALE_DAYS.get(cc, 7) if stale_days is None else stale_days
    if stale_days is None and partial(conn, cc):
        days = 7
    return (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(last[:10])).days \
        >= days


def collect(conn, client, cc, today, log=print, budget=None):
    """Fetch one country's sources and replace their rows. Returns
    {source: (periods, spells)}. A fetch error propagates: nothing of this
    country is replaced, last run's rows stand."""
    ensure(conn)
    got = FETCHERS[cc](conn, client, today, log=log,
                       budget=BUDGET.get(cc) if budget is None else budget)
    done = {}
    for source, (periods, spells, meta) in got.items():
        done[source] = replace(conn, cc, source, today, periods, spells, meta.get("covers"),
                               meta.get("covers_from"), meta.get("note"))
    return done


# --- words -------------------------------------------------------------------------------

def long_date(iso_):
    from src import country_edition as ce
    try:
        return ce.long_date(ce.day(iso_))
    except (TypeError, ValueError):
        return iso_ or "date not given"


# What each source calls a term, for the words "legislature 13, 14".
TERM_WORD = {"be": "legislature", "hr": "saziv", "es": "legislature", "it": "legislature",
             "fr": "legislature", "pt": "legislature", "br": "legislature", "pl": "term",
             "sk": "term", "mx": "legislature"}


def term_label(cc, terms):
    """'legislature 13, 14, 15' (or the source's own label, Austria's 'XXVI.-XXVIII. GP')."""
    terms = [t for t in terms if t]
    if not terms:
        return None
    if all(re.match(r"^[0-9IVXLC]+$", t) for t in terms):
        return "{0} {1}".format(TERM_WORD.get(cc, "term"), ", ".join(terms))
    return ", ".join(terms)


def term_words(cc, t):
    bits = [term_label(cc, [t["term"]]) or "term"]
    if t.get("start") or t.get("end"):
        bits.append("{0} to {1}".format(long_date(t["start"]) if t.get("start") else "?",
                                        long_date(t["end"]) if t.get("end") else "?"))
    if t.get("grp"):
        bits.append(t["grp"])
    return ", ".join(bits)


def merged_spells(spells, kind="group"):
    """Spells of one kind, consecutive spells of the same party that abut
    joined: [(party, start, end)], oldest first."""
    out = []
    for sp in sorted((x for x in spells if x["kind"] == kind and x["start"]),
                     key=lambda x: x["start"]):
        if out and out[-1][0] == sp["party"] and out[-1][2] is not None and \
                sp["start"] <= next_day(out[-1][2]):
            out[-1][2] = sp["end"] if sp["end"] is None or sp["end"] > out[-1][2] else out[-1][2]
            continue
        if out and out[-1][0] == sp["party"] and out[-1][2] is None:
            continue
        out.append([sp["party"], sp["start"], sp["end"]])
    return [tuple(x) for x in out]


MAX_EARLIER = 6     # Brazil's history lists every leave of absence as a period


def lines(cc, s, covers, today, current=None):
    """The profile's 'Length of service' lines (Markdown bullets, no colour)."""
    got = summary(cc, s, covers, today, current)
    out = []
    if got["since"]:
        bits = [chamber_words(cc, got["since_chamber"]) or "this chamber"]
        if term_label(cc, got["since_terms"]):
            bits.append(term_label(cc, got["since_terms"]))
        if got["since_grp"]:
            bits.append(" / ".join(got["since_grp"]))
        out.append("**Serving since:** {0}{1} ({2}; the current unbroken run of periods, as "
                   "the source dates them)".format(
                       "at least " if got["at_least"] else "", long_date(got["since"]),
                       "; ".join(bits)))
    elif got["ended"]:
        out.append("**Last period ended:** {0}".format(long_date(got["ended"])))
    if got["earlier"]:
        items = []
        shown = got["earlier"][:MAX_EARLIER]
        for e in shown:
            bits = ["{0}{1} to {2}".format("at least from " if e["at_least"] else "",
                                           long_date(e["start"]),
                                           long_date(e["end"]) if e["end"] else "?")]
            ch = chamber_words(cc, e["chamber"])
            if ch and ch != chamber_words(cc, got["since_chamber"]):
                bits.append(ch)
            if term_label(cc, e["terms"]):
                bits.append(term_label(cc, e["terms"]))
            if e["grp"]:
                bits.append(" / ".join(e["grp"]))
            items.append(" (".join([bits[0], "; ".join(bits[1:]) + ")"]) if len(bits) > 1
                         else bits[0])
        more = got["earlier"][MAX_EARLIER:]
        if more:
            items.append("and {0} earlier period(s), the first from {1}".format(
                len(more), long_date(more[-1]["start"])))
        out.append("**{0}:** {1}".format("Earlier periods" if got["since"] else "Periods",
                                         "; ".join(items)))
    if got["terms"]:
        out.append("**Terms in the source:** {0} (the source says which terms the member sat "
                   "in, not when they took or left the seat)".format(
                       "; ".join(term_words(cc, t) for t in got["terms"])))
    if not out:
        return []
    out.append("**What the source covers:** {0}. Service outside it is not in it, and "
               "nothing here says whether this is a first term.".format(
                   "; ".join(got["covers"]) or "not recorded"))
    return out


def short(cc, s, covers, today, current=None):
    """One line for a vote page's member card, or None."""
    got = summary(cc, s, covers, today, current)
    if got["since"]:
        text = "serving since {0}{1}".format("at least " if got["at_least"] else "",
                                             long_date(got["since"]))
        if got["earlier"]:
            text += "; {0} earlier period(s) from {1}".format(len(got["earlier"]),
                                                              long_date(got["earlier"][-1]["start"]))
        return text
    if got["ended"]:
        return "last period ended {0}".format(long_date(got["ended"]))
    if got["terms"]:
        return "in the source: " + (term_label(cc, [t["term"] for t in got["terms"]]) or "terms")
    return None
