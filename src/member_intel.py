"""Member intelligence for the new country editions: committees, cross-party
groups and registers of interests, from each parliament's own open data.

    from src import member_intel as mi
    mi.ensure(conn)
    got = mi.collect(conn, client, "br", today)      # fetch, parse, replace
    mi.groups_by_member(conn, "br")                  # what the profiles read

    python3 tools/member_intel.py br nl ch           # the weekly step

The parity layer "member intelligence" (docs/country-parity-handover.md),
generalising the UK's tools/pull_interests.py (register of interests),
tools/load_appgs.py (APPGs, the cross-party groups) and the committee side
of tools/pull_pbc_attendance.py to the countries built on 9-10 October 2026.
The UK tables (member_interest, appg_officers, committee_attendance) are
keyed on Westminster member ids and are left as they are; the new countries
share three tables of their own, one row per membership or declared
interest, keyed by country and source:

  mi_groups     committee, cross-party group (Brazil's frentes parlamentares,
                France's groupes d'études), delegation or inquiry membership;
  mi_interests  a declared interest (the Tweede Kamer's nevenfuncties, the
                Swiss Interessenbindungen);
  mi_runs       when each source was last read in full, and what it gave.

WHAT EACH COUNTRY READS (probed 11 October 2026; every source is the
parliament's own open data, no key, no login, nothing behind a bot check):

  br  Câmara dos Deputados, dadosabertos.camara.leg.br (open data): the
      frentes parlamentares of the 57th legislature and their members, and
      every deputy's open organ memberships (committees, CPIs; the bulk
      file orgaosDeputados-L57, one request). The fronts on our ground
      (config/member-intel-groups.yaml) are read every week, the other
      fronts an eighth a week in rotation (a front's members take about 3 s
      to answer); --full reads every front.
  nl  Tweede Kamer, gegevensmagazijn OData v4 (CC0): current committee
      seats (CommissieZetelVastPersoon) and current nevenfuncties
      (PersoonNevenfunctie), sitting members only.
  ch  Swiss Parliament, ws.parlament.ch OData (open data): committee
      memberships (MemberCommittee) and the register of interests
      (PersonInterest, the Interessenbindungen).
  pl  Sejm API (api.sejm.gov.pl): every committee of the 10th term with its
      members, one request.
  fr  Assemblée nationale open data (Licence Ouverte), AMO10: committees,
      délégations, commissions d'enquête, missions and the groupes d'études
      (cross-party) of every sitting deputy. Friendship groups (GA) are left
      out: 4,900 memberships of bilateral groups, none on our ground.
  it  Camera dei deputati, dati.camera.it SPARQL (CC BY): the current organ
      memberships of the 19th legislature's deputies (committees, giunte,
      inquiries), matched to the store's members by name. The Senate's
      SPARQL refuses the laptop (403, 10 October); not read.
  at  Austrian Parliament, the Filter API behind parlament.gv.at (list 250,
      the "Ausschüsse" tab of each biography): every committee function of
      the current Nationalrat period and of the Bundesrat, two requests.

NOT BUILT, and why (docs/country-parity-handover.md has the table):
  * Austria's interests: the Unvereinbarkeits register is HTML per member;
    meineabgeordneten.at needs a licence (AT5).
  * Spain: the Cortes were dissolved on 5 October (RD 806/2026); declarations
    are scanned PDFs.
  * Argentina: the Senate's open data lists committees without members;
    Diputados is unreachable.
  * Chile: the Cámara's committee service still lists the 2022-26 members.
  * Whip lines: only Brazil publishes one (the Câmara's orientação de
    bancada per vote, already in br_orientations); the profiles show it
    beside each Brazilian position. No other country publishes a whip.

FRANCE'S HATVP DECLARATIONS (additive, 11 October 2026, src/fr_hatvp.py,
tools/fr_hatvp.py): the declarations of interests and activities of sitting
députés and sénateurs, the declarant's OWN items only, into mi_interests
(source 'fr-hatvp') with the declaration's date (`declared`) and the HATVP's
page for the member (`url`), two columns ensure() adds to an older store.
mi_downloads keeps the file's validators so the 80 MB XML is downloaded only
when it changed. Spouses' and collaborators' sections never reach this
module (src/fr_hatvp.py skips them at parse time).

WHAT A ROW SAYS. Names and titles verbatim; the member's store key where the
source gives the store's own id (member_key), otherwise only the printed name
and the source's id (member_ref), resolved by src/member_profiles.py's
Roster at render time: exactly one listed member or nothing. Membership is a
fact the parliament records; flagging a group "on our ground" is the
config's reading of the group's NAME (config/member-intel-groups.yaml), never
a claim about how the member votes.

REFRESH. A source read in full replaces every row it gave before (one
transaction); a source that fails leaves last run's rows standing and is a
[gap] line. Nothing here posts or DMs.
"""

from __future__ import annotations

import datetime
import io
import json
import os
import re
import sqlite3
import zipfile
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_NAME = "member-intel-groups.yaml"
CONFIG = os.path.join(ROOT, "config", CONFIG_NAME)
FEED = "member-intel"

KINDS = ("committee", "cross_party", "delegation", "inquiry", "other")
KIND_WORDS = {"committee": "Committees", "cross_party": "Cross-party groups",
              "delegation": "Delegations", "inquiry": "Inquiries",
              "other": "Other bodies"}

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS mi_groups (
        cc          TEXT NOT NULL,
        source      TEXT NOT NULL,      -- 'br-frentes', 'nl-commissies', ...
        member_key  TEXT,               -- the store's member key, when the source gives its id
        member_ref  TEXT,               -- the source's own person id
        name        TEXT,               -- the member as the source prints them
        kind        TEXT NOT NULL,      -- committee | cross_party | delegation | inquiry | other
        group_type  TEXT,               -- the source's own word ('Comissão Permanente', 'GE')
        group_key   TEXT NOT NULL,
        group_name  TEXT NOT NULL,      -- verbatim
        role        TEXT,               -- 'Membro', 'Voorzitter', 'Titolare', verbatim
        start       TEXT,
        end         TEXT,
        last_seen   TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS mi_groups_cc ON mi_groups (cc, member_key)",
    """CREATE TABLE IF NOT EXISTS mi_interests (
        cc          TEXT NOT NULL,
        source      TEXT NOT NULL,
        member_key  TEXT,
        member_ref  TEXT,
        name        TEXT,
        category    TEXT,               -- the register's own category, verbatim
        text        TEXT NOT NULL,      -- the declared interest, verbatim
        role        TEXT,               -- function in the body, where given
        paid        TEXT,               -- the register's own word on payment
        start       TEXT,
        end         TEXT,
        last_seen   TEXT NOT NULL,
        declared    TEXT,               -- the declaration's own date, where the register dates it
        url         TEXT                -- the register's page for the member, where it has one
    )""",
    "CREATE INDEX IF NOT EXISTS mi_interests_cc ON mi_interests (cc, member_key)",
    """CREATE TABLE IF NOT EXISTS mi_runs (
        cc          TEXT NOT NULL,
        source      TEXT NOT NULL,
        last_seen   TEXT NOT NULL,      -- last successful read
        full_ran    TEXT,               -- last read of everything (Brazil's fronts)
        groups      INTEGER,
        interests   INTEGER,
        note        TEXT,
        PRIMARY KEY (cc, source)
    )""",
    # A big file read only when it changed (France's HATVP declarations,
    # src/fr_hatvp.py): its validators and when it was last checked and read.
    """CREATE TABLE IF NOT EXISTS mi_downloads (
        url           TEXT PRIMARY KEY,
        last_modified TEXT,
        etag          TEXT,
        size          INTEGER,
        last_seen     TEXT,             -- last conditional request (checked), answered or 304
        fetched       TEXT              -- last full download and parse
    )""",
)

# Columns added after the first release of mi_interests (additive, 11 October
# 2026, France's HATVP round): ensure() adds them to an older store.
ADDED_COLUMNS = (("mi_interests", "declared", "TEXT"), ("mi_interests", "url", "TEXT"))

# The register's name for a source, where a profile names it beside the
# declaration date and link.
SOURCE_NAMES = {"fr-hatvp": "HATVP"}

TABLES = ("mi_groups", "mi_interests", "mi_runs", "mi_downloads")


def ensure(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    for table, col, typ in ADDED_COLUMNS:
        have = {r[1] for r in conn.execute("PRAGMA table_info({0})".format(table))}
        if col not in have:
            conn.execute("ALTER TABLE {0} ADD COLUMN {1} {2}".format(table, col, typ))
    conn.commit()
    return conn


def has_tables(conn):
    try:
        got = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND "
                           "name='mi_groups'").fetchone()
    except sqlite3.Error:
        return False
    return bool(got)


# --- small helpers -------------------------------------------------------------------

def clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def iso(text):
    """'2025-02-26T00:00:00', '20250226', '/Date(1791555761747)/', '26/02/2025' ->
    '2025-02-26'; a month alone, '02/2025' or '2025-02', -> '2025-02'."""
    s = clean(text)
    if not s:
        return None
    m = re.match(r"/Date\((-?\d+)", s)
    if m:
        return datetime.datetime.utcfromtimestamp(int(m.group(1)) / 1000).date().isoformat()
    m = re.match(r"(\d{4})-?(\d{2})-?(\d{2})", s)
    if m:
        return "{0}-{1}-{2}".format(*m.groups())
    m = re.match(r"(\d{2})[./](\d{2})[./](\d{4})", s)
    if m:
        return "{2}-{1}-{0}".format(*m.groups())
    # A month alone (HATVP: '05/2022'), additive 11 October 2026.
    m = re.match(r"(\d{2})/(\d{4})$", s)
    if m:
        return "{1}-{0}".format(*m.groups())
    m = re.match(r"(\d{4})-(\d{2})$", s)
    if m:
        return s
    m = re.match(r"(\d{4})$", s)
    return m.group(1) if m else None


def group(member_key=None, member_ref=None, name=None, kind="committee", group_type=None,
          group_key=None, group_name=None, role=None, start=None, end=None):
    return {"member_key": member_key, "member_ref": None if member_ref is None else
            str(member_ref), "name": clean(name) or None, "kind": kind,
            "group_type": clean(group_type) or None, "group_key": str(group_key or group_name),
            "group_name": clean(group_name), "role": clean(role) or None,
            "start": iso(start), "end": iso(end)}


def interest(member_key=None, member_ref=None, name=None, category=None, text=None,
             role=None, paid=None, start=None, end=None, declared=None, url=None):
    return {"member_key": member_key, "member_ref": None if member_ref is None else
            str(member_ref), "name": clean(name) or None, "category": clean(category) or None,
            "text": clean(text), "role": clean(role) or None, "paid": clean(paid) or None,
            "start": iso(start), "end": iso(end), "declared": iso(declared),
            "url": clean(url) or None}


# --- the store -------------------------------------------------------------------------

def replace(conn, cc, source, today, groups=(), interests=(), full=None, note=None):
    """Swap one source's rows for this run's, in one transaction."""
    groups = [g for g in groups if g["group_name"]]
    interests = [i for i in interests if i["text"]]
    with conn:
        conn.execute("DELETE FROM mi_groups WHERE cc=? AND source=?", (cc, source))
        conn.execute("DELETE FROM mi_interests WHERE cc=? AND source=?", (cc, source))
        conn.executemany(
            "INSERT INTO mi_groups (cc, source, member_key, member_ref, name, kind, group_type, "
            "group_key, group_name, role, start, end, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(cc, source, g["member_key"], g["member_ref"], g["name"], g["kind"],
              g["group_type"], g["group_key"], g["group_name"], g["role"], g["start"], g["end"],
              today) for g in groups])
        conn.executemany(
            "INSERT INTO mi_interests (cc, source, member_key, member_ref, name, category, text, "
            "role, paid, start, end, last_seen, declared, url) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(cc, source, i["member_key"], i["member_ref"], i["name"], i["category"], i["text"],
              i["role"], i["paid"], i["start"], i["end"], today, i.get("declared"), i.get("url"))
             for i in interests])
        old = conn.execute("SELECT full_ran FROM mi_runs WHERE cc=? AND source=?",
                           (cc, source)).fetchone()
        conn.execute(
            "INSERT OR REPLACE INTO mi_runs (cc, source, last_seen, full_ran, groups, interests, note) "
            "VALUES (?,?,?,?,?,?,?)",
            (cc, source, today, today if full else (old[0] if old else None), len(groups),
             len(interests), note))
    return len(groups), len(interests)


def download_row(conn, url):
    """(last_modified, etag, size, last_seen, fetched) for a big file, or None."""
    return conn.execute("SELECT last_modified, etag, size, last_seen, fetched FROM mi_downloads "
                        "WHERE url=?", (url,)).fetchone()


def record_download(conn, url, today, headers=None, fetched=False):
    """Stamp a conditional check (last_seen) and, when the file was read, its new
    validators and `fetched` (France's HATVP declarations, src/fr_hatvp.py)."""
    h = {k.lower(): v for k, v in (headers or {}).items()}
    old = download_row(conn, url)
    size = h.get("content-length")
    with conn:
        conn.execute(
            "INSERT INTO mi_downloads (url, last_modified, etag, size, last_seen, fetched) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET "
            "last_modified=excluded.last_modified, etag=excluded.etag, size=excluded.size, "
            "last_seen=excluded.last_seen, fetched=excluded.fetched",
            (url,
             h.get("last-modified") or (old[0] if old else None),
             h.get("etag") or (old[1] if old else None),
             int(size) if size and str(size).isdigit() else (old[2] if old else None),
             today, today if fetched else (old[4] if old else None)))


def member_keys(conn, sql):
    """The store's member keys (a set), or None when the table is absent or
    empty: a collector then keeps every row rather than none."""
    try:
        got = {str(r[0]) for r in conn.execute(sql)}
    except sqlite3.Error:
        return None
    return got or None


# --- which groups are on our ground ----------------------------------------------------

def load_flags(path=CONFIG):
    """{cc: [(compiled pattern, areas, why)]} from config/member-intel-groups.yaml."""
    if not os.path.exists(path):
        return {}
    import yaml
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    out = {}
    for cc, rules in raw.items():
        for r in rules or []:
            out.setdefault(cc, []).append(
                (re.compile(r["match"], re.I), tuple(r.get("areas") or ()), r.get("why") or ""))
    return out


def fold(text):
    from src.noise import fold as _fold
    return _fold(text or "")


def flag(flags, cc, group_name):
    """(areas, why) when a group's name is on our ground for this country, else None."""
    name = fold(group_name)
    for pat, areas, why in flags.get(cc, ()):
        if pat.search(name):
            return areas, why
    return None


# --- what the profiles read ---------------------------------------------------------------

def rows_for(conn, cc):
    """(groups, interests) for a country, current rows only, as dicts."""
    if not has_tables(conn):
        return [], []
    conn.row_factory = sqlite3.Row
    groups = [dict(r) for r in conn.execute(
        "SELECT * FROM mi_groups WHERE cc=? ORDER BY kind, group_name, role", (cc,))]
    interests = [dict(r) for r in conn.execute(
        "SELECT * FROM mi_interests WHERE cc=? ORDER BY category, text", (cc,))]
    return groups, interests


def sources_line(conn, cc):
    """'br-frentes 11 October 2026 (3,412 rows); ...' for the profile notes."""
    if not has_tables(conn):
        return None
    got = conn.execute("SELECT source, last_seen, groups, interests FROM mi_runs WHERE cc=? "
                       "ORDER BY source", (cc,)).fetchall()
    return "; ".join("{0} read {1} ({2} row(s))".format(s, r, (g or 0) + (i or 0))
                     for s, r, g, i in got) or None


# --- the parsers (pure; fixtures in tests/fixtures/member_intel/) ---------------------------

# Brazil -----------------------------------------------------------------------------------

def parse_br_fronts(pages):
    """[{id, titulo}] from the pages of /frentes?idLegislatura=57."""
    out = []
    for page in pages:
        for f in (page or {}).get("dados") or []:
            if f.get("id") and f.get("titulo"):
                out.append({"id": str(f["id"]), "titulo": clean(f["titulo"])})
    return out


def parse_br_front_members(front, reply):
    return [group(member_key="camara-{0}".format(d["id"]), member_ref=d["id"], name=d.get("nome"),
                  kind="cross_party", group_type="Frente parlamentar", group_key=front["id"],
                  group_name=front["titulo"], role=d.get("titulo"), start=d.get("dataInicio"),
                  end=d.get("dataFim"))
            for d in (reply or {}).get("dados") or [] if d.get("id")]


def br_organ_kind(name):
    n = fold(name)
    if "inquerito" in n or n.startswith("cpi"):
        return "inquiry"
    if "comissao" in n or "conselho de etica" in n:
        return "committee"
    if "frente" in n:
        return "cross_party"
    if "delegacao" in n or "grupo parlamentar" in n:
        return "delegation"
    return "other"


def parse_br_organs(reply, today):
    """Open memberships from the bulk file orgaosDeputados-L57.json (one row
    per deputy per organ and cargo; dataFim '' while open)."""
    out = []
    for d in (reply or {}).get("dados") or []:
        end = iso(d.get("dataFim"))
        if end and end < today:
            continue
        m = re.search(r"/deputados/(\d+)", d.get("uriDeputado") or "")
        o = re.search(r"/orgaos/(\d+)", d.get("uriOrgao") or "")
        if not m:
            continue
        organ = d.get("nomePublicacaoOrgao") or d.get("nomeOrgao")
        out.append(group(member_key="camara-{0}".format(m.group(1)), member_ref=m.group(1),
                         name=d.get("nomeDeputado"),
                         kind=br_organ_kind(d.get("nomeOrgao") or organ),
                         group_type=d.get("siglaOrgao"), group_key=o.group(1) if o else organ,
                         group_name=organ, role=d.get("cargo"), start=d.get("dataInicio"),
                         end=end))
    return out


def br_rotation(fronts, today, weeks=8):
    """This week's share of every front, so that all are read within `weeks`
    runs (ISO week number modulo `weeks`, fronts in id order)."""
    week = datetime.date.fromisoformat(today).isocalendar()[1] % weeks
    ordered = sorted(fronts, key=lambda f: int(f["id"]) if f["id"].isdigit() else 0)
    return [f for i, f in enumerate(ordered) if i % weeks == week]


# Netherlands ------------------------------------------------------------------------------

def parse_nl_seats(rows, substitute=False, keep=None):
    out = []
    for r in rows:
        zetel = r.get("CommissieZetel") or {}
        com = zetel.get("Commissie") or {}
        pid = r.get("Persoon_Id")
        if not pid or r.get("Verwijderd") or com.get("Verwijderd") or com.get("DatumInactief"):
            continue
        if keep is not None and pid not in keep:
            continue
        out.append(group(member_key=pid, member_ref=pid, kind="committee",
                         group_type=com.get("Inhoudsopgave") or com.get("Soort"),
                         group_key=com.get("Id"), group_name=com.get("NaamNL") or com.get("NaamWebNL"),
                         role=r.get("Functie") or ("Plv. lid" if substitute else "Lid"),
                         start=r.get("Van"), end=r.get("TotEnMet")))
    return out


def parse_nl_nevenfuncties(rows, keep=None):
    out = []
    for r in rows:
        pid = r.get("PersoonId")
        if not pid or r.get("Verwijderd"):
            continue
        if keep is not None and pid not in keep:
            continue
        out.append(interest(member_key=pid, member_ref=pid, category="Nevenfunctie",
                            text=r.get("Omschrijving"), paid=r.get("VergoedingSoort"),
                            start=r.get("PeriodeVan"), end=r.get("PeriodeTotEnMet")))
    return out


# Switzerland -----------------------------------------------------------------------------

def ch_committee_kind(type_name, name):
    n = fold("{0} {1}".format(type_name or "", name or ""))
    if "untersuchung" in n or "puk" in n.split():
        return "inquiry"
    if "delegation" in n:
        return "delegation"
    return "committee"


def parse_ch_committees(rows):
    out = []
    for r in rows:
        if not r.get("PersonNumber") or not r.get("CommitteeName"):
            continue
        out.append(group(member_key=str(r["PersonNumber"]), member_ref=r["PersonNumber"],
                         name="{0} {1}".format(r.get("FirstName") or "", r.get("LastName") or ""),
                         kind=ch_committee_kind(r.get("CommitteeTypeName"), r["CommitteeName"]),
                         group_type=r.get("CommitteeTypeName"),
                         group_key=r.get("CommitteeNumber"), group_name=r["CommitteeName"],
                         role=r.get("CommitteeFunctionName")))
    return out


def parse_ch_interests(rows):
    out = []
    for r in rows:
        if not r.get("PersonNumber") or not r.get("InterestName"):
            continue
        paid = r.get("Paid")
        out.append(interest(member_key=str(r["PersonNumber"]), member_ref=r["PersonNumber"],
                            name="{0} {1}".format(r.get("FirstName") or "", r.get("LastName") or ""),
                            category=r.get("InterestTypeText"), text=r["InterestName"],
                            role=r.get("FunctionInAgencyText"),
                            paid=None if paid is None else ("bezahlt" if paid else "ehrenamtlich")))
    return out


# Poland ----------------------------------------------------------------------------------

PL_KINDS = {"INVESTIGATIVE": "inquiry", "STANDING": "committee", "EXTRAORDINARY": "committee"}


def parse_pl_committees(reply, term):
    out = []
    for c in reply or []:
        for m in c.get("members") or []:
            if m.get("id") is None:
                continue
            out.append(group(member_key="{0}/{1}".format(term, m["id"]), member_ref=m["id"],
                             name="{0} {1}".format(m.get("firstName") or "", m.get("lastName") or ""),
                             kind=PL_KINDS.get(c.get("type"), "committee"),
                             group_type=c.get("type"), group_key=c.get("code"),
                             group_name=c.get("name"), role=m.get("function") or "członek",
                             start=m.get("joinDate")))
    return out


# France ----------------------------------------------------------------------------------

# AMO organ types kept, and what each is. GA (friendship groups), the
# political groups and parties, the constituencies, the government and
# ministries are not memberships this layer is about.
FR_TYPES = {
    "COMPER": "committee", "CNPS": "committee", "COMNL": "committee", "CMP": "committee",
    "CNPE": "inquiry",
    "DELEG": "delegation", "DELEGBUREAU": "delegation", "OFFPAR": "delegation",
    "API": "delegation",
    "GE": "cross_party", "GEVI": "cross_party",
    "MISINFO": "other", "MISINFOCOM": "other", "MISINFOPRE": "other", "ORGEXTPARL": "other",
}


def _as_list(x):
    return x if isinstance(x, list) else ([] if x is None else [x])


def _ref(x):
    return x.get("#text") if isinstance(x, dict) else x


def parse_fr_amo(raw):
    """Memberships from the AMO10 zip's bytes: the organs it ships, and each
    acteur's active mandates in a kept organ type."""
    z = zipfile.ZipFile(io.BytesIO(raw))
    organs = {}
    for n in z.namelist():
        if "/organe/" in n:
            o = json.loads(z.read(n)).get("organe") or {}
            organs[_ref(o.get("uid"))] = (o.get("libelle"), o.get("codeType"))
    out = []
    for n in z.namelist():
        if "/acteur/" not in n:
            continue
        a = json.loads(z.read(n)).get("acteur") or {}
        uid = _ref(a.get("uid"))
        ident = (a.get("etatCivil") or {}).get("ident") or {}
        name = "{0} {1}".format(ident.get("prenom") or "", ident.get("nom") or "")
        for m in _as_list((a.get("mandats") or {}).get("mandat")):
            kind = FR_TYPES.get(m.get("typeOrgane"))
            if not kind or m.get("dateFin"):
                continue
            for ref in _as_list((m.get("organes") or {}).get("organeRef")):
                label, code = organs.get(_ref(ref), (None, None))
                out.append(group(member_key=uid, member_ref=uid, name=name, kind=kind,
                                 group_type=code or m.get("typeOrgane"), group_key=_ref(ref),
                                 group_name=label or _ref(ref),
                                 role=(m.get("infosQualite") or {}).get("libQualite"),
                                 start=m.get("dateDebut")))
    return out


# Italy -----------------------------------------------------------------------------------

def it_organ_kind(name):
    n = fold(name)
    if "inchiesta" in n:
        return "inquiry"
    if "delegazione" in n:
        return "delegation"
    if "commissione" in n or "giunta" in n or "comitato" in n:
        return "committee"
    return "other"


def parse_it_camera(bindings):
    out, seen = [], set()
    for b in bindings:
        d = b.get("d") or ""
        m = re.search(r"/d(\d+)_\d+$", d)
        ref = m.group(1) if m else d
        org = b.get("org") or ""
        title = b.get("title") or re.sub(r"\s*\([\d.]+-?[\d.]*\)?$", "", b.get("label") or "")
        key = (ref, org, b.get("type"), b.get("start"))
        if b.get("end") or key in seen:
            continue
        seen.add(key)
        out.append(group(member_ref=ref, name="{0} {1}".format(b.get("first") or "",
                                                               b.get("surname") or ""),
                         kind=it_organ_kind(title), group_type=None,
                         group_key=org.rsplit("/", 1)[-1], group_name=title,
                         role=b.get("type"), start=b.get("start")))
    return out


def q_it_camera(leg):
    return ("PREFIX ocd: <http://dati.camera.it/ocd/>\n"
            "PREFIX dc: <http://purl.org/dc/elements/1.1/>\n"
            "PREFIX foaf: <http://xmlns.com/foaf/0.1/>\n"
            "SELECT ?d ?first ?surname ?org ?title ?label ?type ?start ?end WHERE {{ "
            "?d a ocd:deputato ; ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/"
            "repubblica_{0}> ; ocd:membro ?m . ?m ocd:rif_organo ?org . "
            "OPTIONAL {{ ?d foaf:firstName ?first }} OPTIONAL {{ ?d foaf:surname ?surname }} "
            "OPTIONAL {{ ?org dc:title ?title }} "
            "OPTIONAL {{ ?m <http://www.w3.org/2000/01/rdf-schema#label> ?label }} "
            "OPTIONAL {{ ?m dc:type ?type }} OPTIONAL {{ ?m ocd:startDate ?start }} "
            "OPTIONAL {{ ?m ocd:endDate ?end }} }}").format(int(leg))


# Austria ---------------------------------------------------------------------------------

def parse_at_committees(reply, keep=None):
    """Rows of list 250: [GP, sort, Funktion, label, nrbr, url, PAD, fromDate,
    Ausschuss, Gremium, gp_text, BEGINNDATUM_ISO, ...]. The Bundesrat has no
    periods: its list holds every function since 1945, the current ones marked
    'BR-aktuell' in the nrbr column; only those are kept."""
    out = []
    for r in (reply or {}).get("rows") or []:
        if len(r) < 12 or not r[6] or not r[8] or r[4] == "BR":
            continue
        pad = str(r[6])
        if keep is not None and pad not in keep:
            continue
        name = clean(r[8])
        n = fold(name)
        kind = "inquiry" if "untersuchungsausschuss" in n else (
            "delegation" if "delegation" in n else "committee")
        out.append(group(member_key=pad, member_ref=pad, kind=kind, group_type=r[9],
                         group_key="{0}:{1}".format(r[0], name), group_name=name,
                         role=r[2], start=r[11]))
    return out


# --- the fetchers ---------------------------------------------------------------------------

BR_API = "https://dadosabertos.camara.leg.br/api/v2"
BR_LEGISLATURE = 57
BR_ORGANS = "https://dadosabertos.camara.leg.br/arquivos/orgaosDeputados/json/orgaosDeputados-L{0}.json"
NL_API = "https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/"
CH_API = "https://ws.parlament.ch/odata.svc/"
PL_API = "https://api.sejm.gov.pl/sejm"
PL_TERM = 10
FR_AMO10 = ("https://data.assemblee-nationale.fr/static/openData/repository/{0}/amo/"
            "deputes_actifs_mandats_actifs_organes/"
            "AMO10_deputes_actifs_mandats_actifs_organes.json.zip")
FR_LEGISLATURE = 17
IT_CAMERA_SPARQL = "https://dati.camera.it/sparql"
IT_LEGISLATURE = 19
AT_LIST_250 = "https://www.parlament.gv.at/Filter/api/filter/data/250?js=eval&showAll=true"
AT_GP = "XXVIII"


def _odata_q(**params):
    return "&".join("{0}={1}".format(k.replace("_", "$", 1) if k.startswith("_") else k,
                                     quote(v, safe="(),'=$*")) for k, v in params.items())


def fetch_br(conn, client, today, log=print, full=False, flags=None):
    """Brazil: every sitting deputy's organs (one bulk file); the fronts on our
    ground every run, and an eighth of the rest in rotation, so every front is
    re-read within eight weeks (each front's members are one request of 3 s or
    so: all 320 at once would take a quarter of an hour). `full` reads every
    front now."""
    flags = load_flags() if flags is None else flags
    out = {}
    organs = parse_br_organs(client.get_json(BR_ORGANS.format(BR_LEGISLATURE), FEED,
                                             "br-orgaos-L{0}".format(BR_LEGISLATURE)), today)
    out["br-orgaos"] = (organs, [], True, None)
    log("  br: {0} open organ membership(s)".format(len(organs)))
    pages, page = [], 1
    while True:
        got = client.get_json("{0}/frentes?idLegislatura={1}&itens=100&pagina={2}".format(
            BR_API, BR_LEGISLATURE, page), FEED, "br-frentes-{0}".format(page))
        pages.append(got)
        if not got.get("dados") or len(got["dados"]) < 100:
            break
        page += 1
    fronts = parse_br_fronts(pages)
    ours = [f for f in fronts if flag(flags, "br", f["titulo"])]
    chosen = fronts if full else ours + [f for f in br_rotation(fronts, today) if f not in ours]
    rows = []
    for f in chosen:
        rows += parse_br_front_members(f, client.get_json(
            "{0}/frentes/{1}/membros".format(BR_API, f["id"]), FEED,
            "br-frente-{0}".format(f["id"])))
    # Last run's rows stand for the fronts not read this week (a front no
    # longer listed for the legislature is dropped).
    chosen_ids = {f["id"] for f in chosen}
    listed = {f["id"] for f in fronts}
    cols = ("member_key", "member_ref", "name", "kind", "group_type", "group_key",
            "group_name", "role", "start", "end")
    for r in conn.execute("SELECT {0} FROM mi_groups WHERE cc='br' AND "
                          "source='br-frentes'".format(", ".join(cols))):
        if r[5] not in chosen_ids and r[5] in listed:
            rows.append(dict(zip(cols, tuple(r))))
    out["br-frentes"] = (rows, [], full, "{0} of {1} front(s) read this run".format(
        len(chosen), len(fronts)))
    log("  br: {0} of {1} front(s) read ({2} on our ground{3})".format(
        len(chosen), len(fronts), len(ours), ", every front" if full else ", rest in rotation"))
    return out


def _nl_all(client, entity, query, slug):
    rows, url, n = [], "{0}{1}?{2}".format(NL_API, entity, query), 0
    while url:
        got = client.get_json(url, FEED, "{0}-{1}".format(slug, n))
        rows += got.get("value") or []
        url = got.get("@odata.nextLink")
        n += 1
    return rows


def fetch_nl(conn, client, today, log=print, **_):
    keep = member_keys(conn, "SELECT persoon_id FROM nl_members")
    expand = "CommissieZetel($expand=Commissie)"
    seats = parse_nl_seats(_nl_all(client, "CommissieZetelVastPersoon", _odata_q(
        _filter="Verwijderd eq false and TotEnMet eq null", _expand=expand), "nl-vast"), keep=keep)
    seats += parse_nl_seats(_nl_all(client, "CommissieZetelVervangerPersoon", _odata_q(
        _filter="Verwijderd eq false and TotEnMet eq null", _expand=expand), "nl-vervanger"),
        substitute=True, keep=keep)
    neven = parse_nl_nevenfuncties(_nl_all(client, "PersoonNevenfunctie", _odata_q(
        _filter="Verwijderd eq false and (PeriodeTotEnMet eq null or IsActief eq true)"),
        "nl-neven"), keep=keep)
    log("  nl: {0} committee seat(s), {1} nevenfunctie(s)".format(len(seats), len(neven)))
    return {"nl-commissies": (seats, [], True, None), "nl-nevenfuncties": ([], neven, True, None)}


def _ch_all(client, entity, slug, page=1000):
    rows, skip = [], 0
    while True:
        got = client.get_json("{0}{1}?$filter=Language%20eq%20'DE'&$top={2}&$skip={3}"
                              "&$format=json".format(CH_API, entity, page, skip), FEED,
                              "{0}-{1}".format(slug, skip))
        batch = got.get("d") or []
        if isinstance(batch, dict):
            batch = batch.get("results") or []
        rows += batch
        if len(batch) < page:
            return rows
        skip += page


def fetch_ch(conn, client, today, log=print, **_):
    keep = member_keys(conn, "SELECT person_number FROM ch_members WHERE active=1")
    coms = [g for g in parse_ch_committees(_ch_all(client, "MemberCommittee", "ch-committees"))
            if keep is None or g["member_key"] in keep]
    ints = [i for i in parse_ch_interests(_ch_all(client, "PersonInterest", "ch-interests"))
            if keep is None or i["member_key"] in keep]
    log("  ch: {0} committee membership(s), {1} declared interest(s)".format(len(coms),
                                                                             len(ints)))
    return {"ch-committees": (coms, [], True, None), "ch-interests": ([], ints, True, None)}


def fetch_pl(conn, client, today, log=print, **_):
    rows = parse_pl_committees(client.get_json("{0}/term{1}/committees".format(PL_API, PL_TERM),
                                               FEED, "pl-committees"), PL_TERM)
    log("  pl: {0} committee membership(s)".format(len(rows)))
    return {"pl-committees": (rows, [], True, None)}


def fetch_fr(conn, client, today, log=print, **_):
    raw = client.get_bytes(FR_AMO10.format(FR_LEGISLATURE), FEED, "fr-amo10")
    rows = parse_fr_amo(raw)
    log("  fr: {0} membership(s) from AMO10".format(len(rows)))
    return {"fr-organes": (rows, [], True, None)}


def fetch_it(conn, client, today, log=print, **_):
    url = "{0}?query={1}&format={2}".format(IT_CAMERA_SPARQL, quote(q_it_camera(IT_LEGISLATURE)),
                                           quote("application/sparql-results+json"))
    got = client.get_json(url, FEED, "it-camera-organi")
    bindings = [{k: v.get("value") for k, v in b.items()}
                for b in (got.get("results") or {}).get("bindings") or []]
    rows = parse_it_camera(bindings)
    log("  it: {0} Camera organ membership(s)".format(len(rows)))
    return {"it-camera-organi": (rows, [], True, "Camera only; the Senate's SPARQL refuses us")}


def fetch_at(conn, client, today, log=print, **_):
    keep = member_keys(conn, "SELECT pad FROM at_members")
    rows = []
    for gp in (AT_GP, "BR"):
        rows += parse_at_committees(client.post_json(AT_LIST_250, json.dumps({"GP": [gp]}), FEED,
                                                     "at-ausschuesse-{0}".format(gp)), keep=keep)
    log("  at: {0} committee function(s)".format(len(rows)))
    return {"at-ausschuesse": (rows, [], True, None)}


FETCHERS = {"br": fetch_br, "nl": fetch_nl, "ch": fetch_ch, "pl": fetch_pl, "fr": fetch_fr,
            "it": fetch_it, "at": fetch_at}
COUNTRIES = tuple(FETCHERS)


def collect(conn, client, cc, today, log=print, full=False):
    """Fetch one country's sources and replace their rows. Returns
    {source: (groups, interests)}. A fetch error propagates: nothing of this
    country is replaced, last run's rows stand."""
    ensure(conn)
    got = FETCHERS[cc](conn, client, today, log=log, full=full)
    done = {}
    for source, (groups, interests, full_, note) in got.items():
        done[source] = replace(conn, cc, source, today, groups, interests, full=full_, note=note)
    return done
