"""Tables for the Hungarian monitor, phase 0 (10 October 2026): the Magyar
Közlöny, Hungary's official gazette (tools/hu_gazette.py).

Chris, 10 October 2026 (docs/country-decisions-2026-10-10.md, HU6 "build
now"): the parliament's own site (parlament.hu) answers every client of ours
with a CAPTCHA, and its W-API needs a personal token (HU1), so the first
Hungarian leg is the gazette: what became law, without who voted. See
docs/hungary-scope.md, "Proposed phasing".

SEPARATION GUARANTEE. Nothing outside tools/hu_*.py writes these tables, and
nothing here touches another jurisdiction's table. Created by db.init_db so
every store carries them and db.TABLES stays true.

KEYS.
  * AN ISSUE is '<year>/<serial>', '2026/148': the Magyar Közlöny numbers its
    issues from 1 each year ("Magyar Közlöny 2026. évi 148. szám").
  * AN ENTRY (one line of an issue's contents page, the Tartalomjegyzék) is
    keyed on its OFFICIAL DESIGNATION, verbatim with the spaces normalised:
    '2026. évi LVI. törvény', '22/2026. (V. 27.) OGY határozat',
    '225/2026. (X. 6.) Korm. rendelet', '10/2026. (X. 8.) HM rendelet'. The
    designation is unique: numbers restart each year and the year is in it,
    and a ministry's decrees carry the ministry. Titles are never keys
    ("... módosításáról" opens hundreds of entries a year). An amendment to
    the Fundamental Law has no number; its designation is its own heading,
    'Magyarország Alaptörvényének tizenhetedik módosítása (2026. ...)'.

TYPES (hu_gazette_entries.type), read off the designation:
    act              törvény (an Act of Parliament)
    fundamental_law  Magyarország Alaptörvényének ... módosítása
    ogy_resolution   OGY határozat (a resolution of the Országgyűlés)
    gov_decree       Korm. rendelet (a government decree)
    gov_resolution   Korm. határozat (a government resolution)
    ministerial_decree  any other rendelet (a minister's, the MNB's, an
                     autonomous regulator's: 'BM rendelet', 'SZTFH rendelet')
    ab_decision      AB határozat / AB végzés (the Constitutional Court)
    ke_decision      KE határozat (the President of the Republic)
    pm_decision      ME határozat (the Prime Minister)
    other            anything else (the Kúria's local-government decisions,
                     notices)

HU4 (Chris, 10 October 2026): every amendment to the Fundamental Law goes to
triage whatever its words. Its title names no subject ("Magyarország
Alaptörvényének tizenhetedik módosítása"), so no term can catch it; the
collector stores `rule = 'HU4'` and the edition treats it as watched.

THE PARLIAMENT'S RECORD (HU7, 10 October 2026): members, papers (irományok),
recorded votes and member positions, keyed exactly as the W-API keys them,
so the token's collector (HU1, phase 1) writes the same rows:

  * A MEMBER is the parliament's own identifier, `p_azon` ('a011').
  * A PAPER is its number in the term, 'T/324' (a bill), 'H/179' (a
    resolution), 'I/49' (an interpellation), 'K/463', 'A/77', 'S/3', 'B/1'.
    Numbers restart each term; the 43rd began on 9 May 2026. Never a title.
  * A DIVISION is the vote's timestamp, '2026.07.13.18:19:08', as the
    W-API's `szavazas` service takes it. A vote often has no title of its
    own: what was put is its motion ('324/14', the bill's consolidated
    text; 'T/324', the bill; 'I/49', the minister's answer), joined to its
    paper by the paper's number in the term (the `izon`, '324'), never by
    title.
  * A POSITION is (division, member), with the member's group AT THE VOTE
    and the record's own word for the position (POSITIONS).

PROVENANCE. Every row carries `source`: 'karzat@<commit>' for a row loaded
from karzat's open data (tools/hu_karzat_backfill.py, CC BY 4.0, see
KARZAT_ATTRIBUTION), and `as_of`, the date the data stood at. hu_sources
holds one row per load (commit, licence, attribution, window, counts). The
House's own record wins: a loader of karzat's files never overwrites a row
whose source is not karzat's.

HU5 (Chris, 10 October 2026): a vote on accepting a minister's answer to an
interpellation counts as a division, on our ground when the interpellation
is; such a division carries `rule = 'HU5'`.
"""

from __future__ import annotations

import json
import os
import re

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCHLIST = os.path.join(ROOT, "config", "watchlist-hu.yaml")

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS hu_gazette_issues (
        issue_key    TEXT PRIMARY KEY,   -- '2026/148'
        year         INTEGER NOT NULL,
        serial       INTEGER NOT NULL,
        date         TEXT,               -- '2026-10-08', the feed's or listing's own date
        url          TEXT,               -- the issue's page on magyarkozlony.hu
        pdf_url      TEXT,               -- the PDF ("letoltes")
        pages        INTEGER,            -- PDF pages read (the contents and a few after)
        entries      INTEGER,            -- contents entries stored
        contents_ok  INTEGER,            -- 1 when the contents page was read
        read_at      TEXT,
        last_seen    TEXT                -- last time the feed or listing showed it
    )""",
    """CREATE TABLE IF NOT EXISTS hu_gazette_entries (
        entry_key    TEXT PRIMARY KEY,   -- the official designation, see KEYS
        issue_key    TEXT NOT NULL,      -- '2026/148'
        date         TEXT,               -- the issue's date
        page         INTEGER,            -- the gazette page the entry starts on
        type         TEXT,               -- see TYPES
        number       TEXT,               -- 'LVI/2026', '225/2026'; NULL for an amendment
        issuer       TEXT,               -- 'OGY', 'Korm.', 'AB', 'BM', ...; NULL for an Act
        title        TEXT,               -- the contents line's title, verbatim
        areas        TEXT,               -- JSON list; [] = read and off our ground
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        rule         TEXT,               -- 'HU4' for an amendment to the Fundamental Law
        watched      INTEGER,            -- 1 when config/watchlist-hu.yaml names the key
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS hu_gazette_entries_date ON hu_gazette_entries (date)",
    "CREATE INDEX IF NOT EXISTS hu_gazette_entries_issue ON hu_gazette_entries (issue_key)",
    """CREATE TABLE IF NOT EXISTS hu_members (
        member_id    TEXT PRIMARY KEY,   -- p_azon, 'a011'
        name         TEXT,
        faction      TEXT,               -- the group now (or when the mandate ended)
        current      INTEGER,
        mandate_kind TEXT,               -- 'egyeni' (constituency), 'lista' (list)
        county       TEXT,
        constituency_no INTEGER,
        mandate_from TEXT,
        mandate_to   TEXT,
        source       TEXT NOT NULL,      -- 'karzat@<commit>', or the W-API's collector
        as_of        TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS hu_papers (
        paper_key    TEXT PRIMARY KEY,   -- 'T/324', see KEYS
        izon         TEXT,               -- '324', the paper's number in the term
        kind         TEXT,               -- the letter: T, H, I, K, A, S, B, Y
        type         TEXT,               -- the record's type, verbatim
        main_type    TEXT,               -- 'törvényjavaslat', 'interpelláció', ...
        title        TEXT,
        status       TEXT,               -- the record's status, verbatim
        submitted_on TEXT,
        submitters   TEXT,               -- JSON list, verbatim
        addressee    TEXT,               -- the minister a question is put to
        procedure    TEXT,               -- 'normal', 'surgos', 'kiveteles', ...
        promulgated_issue TEXT,          -- '2026/92', a hu_gazette_issues key
        promulgated_on TEXT,
        law_ref      TEXT,               -- '2026. évi XX. törvény', a hu_gazette_entries key
        final_vote_ts TEXT,              -- a hu_divisions key
        url          TEXT,               -- the paper's text
        areas        TEXT,               -- JSON list; [] = read and off our ground
        matched_terms TEXT,
        tier         INTEGER,
        rule         TEXT,               -- 'HU4' for an amendment to the Fundamental Law
        watched      INTEGER,
        source       TEXT NOT NULL,
        as_of        TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS hu_divisions (
        vote_ts      TEXT PRIMARY KEY,   -- '2026.07.13.18:19:08', see KEYS
        date         TEXT,
        time         TEXT,
        mode         TEXT,               -- the record's own words: 'Listás az összes képviselő 2/3-ával'
        secret       INTEGER,            -- 1 for a secret ballot: no positions
        kind         TEXT,               -- 'dontes' (a decision), 'jelenlet' (a quorum call)
        majority     TEXT,               -- 'egyszeru', 'ketharmad_jelenlevo', 'ketharmad_osszes',
                                         -- 'abszolut', 'negyotod_jelenlevo'
        yes          INTEGER,            -- igen
        no           INTEGER,            -- nem
        abstain      INTEGER,            -- tartózkodott
        total        INTEGER,            -- votes cast
        passed       INTEGER,
        result       TEXT,               -- 'Elfogadva', verbatim
        motion       TEXT,               -- what was put: 'T/324', '324/14', 'I/49'
        motion_kind  TEXT,               -- 'T', 'I', ..., 'amendment'
        outcome      TEXT,               -- the record's words: 'önálló indítvány elfogadva'
        paper_key    TEXT,               -- the motion's paper, a hu_papers key
        title        TEXT,               -- the motion's title (its paper's)
        group_tallies TEXT,              -- JSON [{faction, igen, nem, tartozkodott, ...}]
        areas        TEXT,
        matched_terms TEXT,
        tier         INTEGER,
        rule         TEXT,               -- 'HU4' (an amendment) or 'HU5' (an interpellation answer)
        watched      INTEGER,
        source       TEXT NOT NULL,
        as_of        TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS hu_votes (
        vote_ts      TEXT NOT NULL,      -- a hu_divisions key
        member_id    TEXT NOT NULL,      -- a hu_members key
        name         TEXT,
        faction      TEXT,               -- the member's group AT THE VOTE
        position     TEXT,               -- POSITIONS, the record's own word
        source       TEXT NOT NULL,
        as_of        TEXT,
        PRIMARY KEY (vote_ts, member_id)
    )""",
    """CREATE TABLE IF NOT EXISTS hu_sources (
        source       TEXT PRIMARY KEY,   -- 'karzat@<commit>'
        name         TEXT,
        url          TEXT,
        licence      TEXT,
        attribution  TEXT,               -- shown wherever the source's rows are
        commit_sha   TEXT,
        derived_at   TEXT,               -- when the source derived its files
        data_from    TEXT,
        data_to      TEXT,               -- the as-of date of its votes
        loaded_at    TEXT,
        counts       TEXT                -- JSON {members, papers, divisions, positions}
    )""",
    "CREATE INDEX IF NOT EXISTS hu_divisions_date ON hu_divisions (date)",
    "CREATE INDEX IF NOT EXISTS hu_divisions_paper ON hu_divisions (paper_key)",
    "CREATE INDEX IF NOT EXISTS hu_papers_submitted ON hu_papers (submitted_on)",
)

TABLES = ("hu_gazette_issues", "hu_gazette_entries", "hu_members", "hu_papers",
          "hu_divisions", "hu_votes", "hu_sources")

# The six positions the record carries, plus an excused absence (igazoltan
# távol), which karzat also records; abstention is a political act here.
POSITIONS = {"i": "igen", "n": "nem", "t": "tartozkodott", "j": "jelen_nem_szavazott",
             "s": "nem_szavazott", "h": "bejelentett_hianyzo", "v": "igazoltan_tavol"}
YES, NO, ABSTAIN = ("igen",), ("nem",), ("tartozkodott",)

MAJORITIES = {"egyszeru": "a simple majority",
              "abszolut": "an absolute majority (half of all MPs)",
              "ketharmad_jelenlevo": "two-thirds of those present",
              "ketharmad_osszes": "two-thirds of all MPs",
              "negyotod_jelenlevo": "four-fifths of those present",
              "negyotod_osszes": "four-fifths of all MPs"}

KARZAT = "karzat"
KARZAT_URL = "https://github.com/abognar-git/karzat"
KARZAT_LICENCE = "CC BY 4.0"
KARZAT_ATTRIBUTION = ("Votes, papers and members before the parliament's own feed from karzat "
                      "(github.com/abognar-git/karzat, open data under CC BY 4.0), derived "
                      "from the Országgyűlés's record")


def is_karzat(source):
    return bool(source) and str(source).startswith(KARZAT + "@")

TYPE_NAMES = {
    "act": "Act",
    "fundamental_law": "Amendment to the Fundamental Law",
    "ogy_resolution": "Resolution of the Országgyűlés",
    "gov_decree": "Government decree",
    "gov_resolution": "Government resolution",
    "ministerial_decree": "Decree",
    "ab_decision": "Constitutional Court decision",
    "ke_decision": "Decision of the President of the Republic",
    "pm_decision": "Decision of the Prime Minister",
    "other": "Gazette entry",
}

# Roman numerals, for an Act's number ('2026. évi LVI. törvény' is Act 56).
_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

ACT = re.compile(r"^(\d{4})\. évi ([IVXLCDM]+)\. törvény$")
NUMBERED = re.compile(r"^(\d+)/(\d{4})\. \(([IVX]+)\. ?(\d{1,2})\.\) (.+?) "
                      r"(rendelet|rendelete|határozat|határozata|végzés|végzése|utasítás|"
                      r"ítélet|közlemény)$")
AMENDMENT = re.compile(r"^Magyarország Alaptörvényének\b.*\bmódosítás", re.I)
# A motion that names its paper's number in the term: '324/14' (a text or an
# amendment of paper 324) or 'T/324' (the paper itself).
MOTION = re.compile(r"^(?:([A-Z])/)?(\d+)(?:/(\d+))?$")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


def issue_key(year, serial):
    return "{0}/{1}".format(int(year), int(serial))


def norm(text):
    """Spaces normalised (the PDF's no-break spaces included), ends stripped."""
    return re.sub(r"[\s  ]+", " ", text or "").strip()


def roman(numeral):
    total = prev = 0
    for ch in reversed(numeral or ""):
        v = _ROMAN.get(ch, 0)
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def classify_designation(designation):
    """(type, number, issuer) from an entry's official designation."""
    d = norm(designation)
    if AMENDMENT.search(d):
        return "fundamental_law", None, "OGY"
    m = ACT.match(d)
    if m:
        return "act", "{0}/{1}".format(m.group(2), m.group(1)), None
    m = NUMBERED.match(d)
    if m:
        number = "{0}/{1}".format(m.group(1), m.group(2))
        issuer, form = m.group(5).strip(), m.group(6)
        decree = form.startswith("rendelet")
        if issuer == "OGY":
            kind = "ogy_resolution"
        elif issuer == "Korm.":
            kind = "gov_decree" if decree else "gov_resolution"
        elif issuer == "AB":
            kind = "ab_decision"
        elif issuer == "KE":
            kind = "ke_decision"
        elif issuer == "ME":
            kind = "pm_decision"
        elif decree:
            kind = "ministerial_decree"
        else:
            kind = "other"
        return kind, number, issuer
    return "other", None, None


def watchlist(path=None):
    """{key: entry} from config/watchlist-hu.yaml: every mapping section
    merged (`gazette:` keyed on a gazette designation, `papers:` keyed on a
    parliamentary paper number for phase 1). {} when there is no file."""
    path = path or WATCHLIST
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    out = {}
    for section in raw.values():
        if isinstance(section, dict):
            for key, entry in section.items():
                out[norm(str(key))] = entry if isinstance(entry, dict) else {}
    return out


def dumps(values):
    return json.dumps(list(values or []), ensure_ascii=False)
