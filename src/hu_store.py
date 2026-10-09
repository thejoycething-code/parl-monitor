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
)

TABLES = ("hu_gazette_issues", "hu_gazette_entries")

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
