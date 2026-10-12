"""Shared parsing helpers for the Mexican state congress readers
(src/ingest/mxs_*.py, tools/mxs_collect.py). Stdlib only."""

from __future__ import annotations

import datetime
import html as _html
import re

MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
          "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
          "noviembre": 11, "diciembre": 12}
ABBR = {m[:3]: n for m, n in MONTHS.items()}
ABBR["set"] = 9

TAG = re.compile(r"<[^>]+>")
ROW = re.compile(r"<tr\b([^>]*)>(.*?)</tr>", re.S | re.I)
CELL = re.compile(r"<t([dh])\b[^>]*>(.*?)</t\1>", re.S | re.I)
HREF = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.I)


def clean(markup):
    """Text of an HTML fragment, entities decoded, whitespace collapsed; None if empty."""
    if markup is None:
        return None
    text = _html.unescape(TAG.sub(" ", str(markup)))
    text = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
    return text or None


def rows(markup):
    """[(tr attributes, [cell html, ...])] for every table row."""
    return [(attrs, [c[1] for c in CELL.findall(body)]) for attrs, body in ROW.findall(markup or "")]


def hrefs(markup):
    return [_html.unescape(h) for h in HREF.findall(markup or "")]


def date(text):
    """ISO date from '08/10/2026', '29/sep/2026', '2026-09-30', '8 de octubre de
    2026' or '2026-10-08T00:00:00'; None when there is none."""
    t = (text or "").strip().lower()
    if not t:
        return None
    try:
        m = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", t)
        if m:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        m = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b", t)
        if m:
            return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        m = re.search(r"\b(\d{1,2})[/ .-]([a-z]{3})[a-z]*\.?[/ .-](\d{4})\b", t)
        if m and m.group(2) in ABBR:
            return datetime.date(int(m.group(3)), ABBR[m.group(2)], int(m.group(1))).isoformat()
        m = re.search(r"\b(\d{1,2})\s+(?:de\s+)?(" + "|".join(MONTHS)
                      + r"),?\s+(?:de(?:l)?\s+)?(\d{4})", t)
        if m:
            return datetime.date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1))).isoformat()
    except ValueError:
        return None
    return None


PARTY = re.compile(
    r"\b(MOVIMIENTO DE REGENERACI[OÓ]N NACIONAL|MORENA|PAN|PRI|PRD|PT|PVEM|MC|PES|NUEVA ALIANZA|MOVIMIENTO CIUDADANO|"
    r"PARTIDO VERDE(?: ECOLOGISTA DE M[EÉ]XICO)?|PARTIDO DEL TRABAJO|"
    r"(?:PARTIDO )?ACCI[OÓ]N NACIONAL|(?:PARTIDO )?REVOLUCIONARIO INSTITUCIONAL)\b", re.I)
PARTY_SHORT = {"MOVIMIENTO CIUDADANO": "MC", "PARTIDO DEL TRABAJO": "PT"}


def party_in(text):
    """The first party a presenter line names, short form; None if none.
    Only what is printed: never inferred from a name."""
    m = PARTY.search(text or "")
    if not m:
        return None
    p = re.sub(r"\s+", " ", m.group(1)).upper()
    if p.startswith("MOVIMIENTO DE REGENERACI"):
        return "MORENA"
    if "ACCI" in p and "NACIONAL" in p:
        return "PAN"
    if "REVOLUCIONARIO" in p:
        return "PRI"
    if p.startswith("PARTIDO VERDE"):
        return "PVEM"
    return PARTY_SHORT.get(p, p)


def since_ok(iso, since):
    """True when an item dated `iso` is on or after `since` (undated: True)."""
    return not iso or not since or iso >= since


def kind_of(title):
    t = (title or "").lower()
    if "punto de acuerdo" in t or t.startswith("proposici"):
        return "punto"
    if t.startswith("dictamen"):
        return "dictamen"
    if t.startswith("minuta"):
        return "other"
    return "iniciativa"
