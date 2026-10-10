"""Tables for the Bolivia monitor (phase 1, 9 October 2026): members of both
chambers of the Asamblea Legislativa Plurinacional and its proyectos de ley,
with every status change we see.

See docs/bolivia-scope.md for what was measured and why. The schema follows
the US and Peru precedent (src/us_store.py): its own module, idempotent
statements, created by db.init_db so every store carries it and db.TABLES
stays true.

SEPARATION GUARANTEE. Nothing outside tools/bo_*.py writes these tables,
and nothing here touches another jurisdiction's table.

NO VOTE TABLES, ON PURPOSE. Neither chamber publishes how members voted:
the Diputados' electronic system's results are never released, the Senado
API's `sesiones` list is empty, and news items report "por mayoria" or
"por unanimidad" without names (docs/bolivia-scope.md). bo_divisions and
bo_votes are added the day a per-member source exists, not before.

KEYS. A proyecto de ley is numbered per legislative year and per chamber of
origin, so the key carries all three, in one canonical spelling whatever
the source printed:

    'PL 820/2025-2026 CD'   'PL No 820/2025-2026' on diputados.gob.bo,
                            'P.L. N° 820/2025-2026 C.D.' on the Senado API
    'PL 291/2025-2026 CS'   'PLS-291/2025-2026' or 'PLS N° 291/2025-2026'
                            on diputados.gob.bo (a Senado bill in revision
                            there), 'P.L. N° 291/2025-2026 C.S.' on the Senado
    'LEY 1754'              a promulgated law ('LEY N° 1754', 'Ley No 1754')

'PLA 429-2023-2024' on diputados.gob.bo is the approved text of
'PL 429/2023-2024 CD' and folds into it. The title is never a key: dozens
of bills share "DECLARA PATRIMONIO CULTURAL ..." openings. A member is
'diputados/<slug>' (the WordPress slug) or 'senado/<id>' (the Senado API's
own id).

ONE ROW, TWO CHAMBERS. A bill that crosses from one chamber to the other is
one row: `dip_*` columns are what diputados.gob.bo says of it, `sen_*`
what the Senado API says. bo_bill_changes records every move of either
status, so "what moved this week" is a query, not a diff of snapshots.

PERSONAL DATA. The Senado API also serves members' e-mail, date and place of
birth; the Diputados site serves biographies. None of it is stored: name,
party, department and role only.
"""

from __future__ import annotations

import json
import os
import re

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS bo_members (
        member_key   TEXT PRIMARY KEY,   -- 'diputados/aida-luz-tuchani-lurici', 'senado/78'
        chamber      TEXT NOT NULL,      -- 'diputados' / 'senado'
        name         TEXT,
        party        TEXT,               -- bancada name (Senado only; the Diputados site has none)
        party_code   TEXT,               -- 'PDC', 'LIBRE', 'UNIDAD', 'APB-SUMATE'
        department   TEXT,               -- 'Tarija' (Senado brigada)
        role         TEXT,               -- 'Presidente', 'Diputado Nacional', ...
        titular      INTEGER,            -- 1 titular, 0 suplente, NULL unknown
        source_id    INTEGER,            -- WordPress post id / Senado API id
        link         TEXT,
        as_of        TEXT,               -- the record's own modified date, when given
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS bo_bills (
        bill_key     TEXT PRIMARY KEY,   -- 'PL 820/2025-2026 CD', 'LEY 1754'; never the title
        kind         TEXT NOT NULL,      -- 'PL' / 'LEY'
        origin       TEXT,               -- 'CD' / 'CS' for a PL; NULL for a law
        number       INTEGER,
        legislatura  TEXT,               -- '2025-2026'
        title        TEXT,               -- the longest description either chamber gave
        law_number   TEXT,               -- 'LEY 1754' once promulgated, when a source links it
        dip_status   TEXT,               -- diputados.gob.bo estado_de_ley, its own words
        dip_committee TEXT,              -- comision_de_ley name
        dip_id       INTEGER,            -- WordPress post id
        dip_link     TEXT,
        dip_modified TEXT,
        dip_file     INTEGER,            -- media id of the bill's PDF (scans: no text layer)
        sen_stage    TEXT,               -- Senado list: tratamiento / aprobados / sancionada / promulgada / rechazada / devuelto
        sen_id       INTEGER,
        sen_document TEXT,               -- Senado PDF path (OCR'd text layer)
        areas        TEXT,               -- JSON list; taxonomy + watchlist-bo by key
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS bo_bill_changes (
        bill_key     TEXT NOT NULL,
        seen         TEXT NOT NULL,      -- ISO date of the run that saw the change
        field        TEXT NOT NULL,      -- 'dip_status' / 'sen_stage'
        old          TEXT,               -- NULL: first sighting
        new          TEXT,
        PRIMARY KEY (bill_key, seen, field)
    )""",
    "CREATE INDEX IF NOT EXISTS bo_bills_leg ON bo_bills (legislatura, origin, number)",
    # BO4 (10 October 2026; tools/bo_questions.py): written questions to the
    # executive, peticiones de informe escrito, the only member-attributed
    # record Bolivia publishes (votes are never released).
    """CREATE TABLE IF NOT EXISTS bo_questions (
        question_key TEXT PRIMARY KEY,   -- 'senado/PIE 1039/2025-2026', 'diputados/PIE 957/2024-2025'
        chamber      TEXT NOT NULL,      -- 'senado' / 'diputados'
        kind         TEXT,               -- 'PIE' (escrito) / 'PIO' (oral)
        number       INTEGER,
        legislatura  TEXT,               -- '2025-2026'
        date         TEXT,               -- received (Senado) / filed (Diputados), ISO
        addressee    TEXT,               -- the ministry or office asked, verbatim
        summary      TEXT,               -- what was asked, verbatim
        askers       TEXT,               -- JSON list of names as printed (or resolved)
        asker_keys   TEXT,               -- JSON list of bo_members keys; NULL entries unresolved
        answered     TEXT,               -- ISO date of the answer, when the chamber records one
        answer_url   TEXT,
        doc_url      TEXT,
        url          TEXT,
        source_id    INTEGER,            -- Senado API id / WordPress post id
        updated      TEXT,               -- the source's own modified date
        areas        TEXT,               -- JSON list; taxonomy-es for bo
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS bo_questions_date ON bo_questions (date)",
)

TABLES = ("bo_members", "bo_bills", "bo_bill_changes", "bo_questions")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- keys ---------------------------------------------------------------------

_NUM = r"N\s*[o°º]?\.?\s*[°º]?\s*"
# Every spelling diputados.gob.bo has used since 2020, measured over its 5,352
# records: 'PL No 820/2025-2026', 'PL N° 005/2020-2021', 'PLS N°092/2024-2025',
# 'PLS-291/2025-2026', 'PLA 429-2023-2024', 'PLA  N° 113/2021-2022',
# 'PL CS N°098/2022-2023', 'PL-CS N° 125/2021-2022', 'PLS CD N° 114/2019-2020',
# 'N°219/2022-2023', and laws as 'PLP LEY D N° 1512'.
_DIP_PL = re.compile(
    r"^\s*(?P<prefix>PLS|PLA|PLP|PL)?\s*-?\s*(?P<ch>C\.?\s*[SD]\.?)?\s*(?P<law>LEY\s*[DS]?\s*)?"
    r"(?:" + _NUM + r")?(?P<num>\d+)\s*(?:[/-]\s*(?P<a>\d{4})\s*-\s*(?P<b>\d{4}))?", re.I)
# 'P.L. N° 743/2025-2026 C.D.', 'P.L. N° 307/2024-2025 C.S.', and the odd
# '295/2024-2025 C.S.' and 'P.L. N° 001-2023-2024 C.D.'
_SEN_PL = re.compile(r"^\s*(?:P\.?\s*L\.?)?\s*(?:" + _NUM + r")?(\d+)\s*[/-]\s*(\d{4})\s*-\s*(\d{4})\s*"
                     r"C\.?\s*([DS])\.?", re.I)
# 'LEY N° 1754', 'Ley No 1491', 'Ley N° 807', and a bare '348' (ley_nro)
_LAW = re.compile(r"^\s*(?:LEY\s*)?(?:" + _NUM + r")?(\d+)\s*$", re.I)


def pl_key(number, start, end, origin):
    return "PL {0}/{1}-{2} {3}".format(int(number), start, end, origin)


def dip_key(titulo, ley_nro=None):
    """diputados.gob.bo titulo (and ley_nro) -> (bill_key, kind, origin,
    number, legislatura), or None when neither carries a number."""
    m = _DIP_PL.match(titulo or "")
    if m and (m.group("prefix") or m.group("ch") or m.group("a")):
        if m.group("law") or (m.group("prefix") or "").upper() == "PLP":
            return law_key(m.group("num"))
        if m.group("a"):
            ch = re.sub(r"[^SD]", "", (m.group("ch") or "").upper())
            if ch:
                origin = "C" + ch
            else:
                origin = "CS" if (m.group("prefix") or "").upper() == "PLS" else "CD"
            num = m.group("num")
            return (pl_key(num, m.group("a"), m.group("b"), origin), "PL", origin, int(num),
                    "{0}-{1}".format(m.group("a"), m.group("b")))
    if ley_nro and ley_nro != titulo:
        k = dip_key(ley_nro) if _DIP_PL.match(ley_nro) and not _LAW.match(ley_nro) else None
        return k or law_key(ley_nro)
    return law_key(titulo)


def sen_key(titulo):
    """Senado API titulo -> the same tuple, or None."""
    m = _SEN_PL.match(titulo or "")
    if m:
        num, a, b, ch = m.groups()
        origin = "C" + ch.upper()
        return pl_key(num, a, b, origin), "PL", origin, int(num), "{0}-{1}".format(a, b)
    return law_key(titulo)


def law_key(text):
    m = _LAW.match(text or "")
    if m:
        return "LEY {0}".format(int(m.group(1))), "LEY", None, int(m.group(1)), None
    return None


# --- watchlist ---------------------------------------------------------------

WATCHLIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "config", "watchlist-bo.yaml")


def watchlist(path=None):
    """{bill_key: (areas, why)} from config/watchlist-bo.yaml. Keyed by the
    canonical bill key, never the title."""
    import yaml
    path = path or WATCHLIST
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    out = {}
    for key, spec in (raw.get("bills") or {}).items():
        spec = spec or {}
        out[str(key)] = (sorted(int(a) for a in (spec.get("areas") or [])), spec.get("why"))
    return out


def add_watch_areas(res, bill_key, path=None, wl=None):
    """Union a watched bill's areas into a FilterResult, in place, and say so
    in watchlist_hits so the stored row shows where the area came from."""
    hit = (wl if wl is not None else watchlist(path)).get(bill_key)
    if not hit:
        return res
    areas, _why = hit
    res.issue_areas = sorted(set(res.issue_areas or []) | set(areas))
    res.watchlist_hits = list(res.watchlist_hits or []) + ["watch:" + bill_key]
    if res.tier is None:
        res.tier = 2
    return res


def dumps(values):
    return json.dumps(values or [], ensure_ascii=False)
