"""Forward business at Holyrood and the Senedd: shared store and item types.

sp_agenda and sd_agenda (src/db.py) hold one row per agenda item of a
sitting or committee meeting from today to the horizon each source publishes.
They mirror ni_agenda: the business text is classified with the English
taxonomy, areas and matched_terms are JSON lists, and first_seen survives a
re-read while last_seen is stamped by every run that sees the item.

Unlike a history table, a forward agenda CHANGES: a placeholder ("Scottish
Government Business") becomes a named debate, a revision moves an item to
another day, a meeting is cancelled. So a day (Holyrood) or a meeting (Senedd)
that was read successfully is the whole truth for that day or meeting: rows
for it that this run did not see are removed (prune_unseen). A day or meeting
that could NOT be read keeps its rows and records a gap, so a failed read
never empties the table.
"""

from __future__ import annotations

import html as _html
import json
import re

# One classifier for both parliaments. Order matters: the first match wins,
# so the specific (bill stage, legislative consent, members' business) come
# before the general (debate, statement).
_TYPES = (
    ("procedural", re.compile(
        r"^(time for reflection|parliamentary bureau motions?|business motions?|"
        r"decision time|committee announcements|voting time|"
        r"business statement and announcement|"
        r"decisions? on taking (?:business|items?|agenda items?)[^:]*in private|"
        r"motions? under standing orders? ?17\.42|"
        r"papers? to note|apologies|declarations? of interest|"
        r"introductions?(?:,| and) apologies|"
        r"work programme|forward work programme|review of evidence|"
        r"consideration of evidence)", re.I)),
    ("members' business", re.compile(r"^members[’']? business|^short debate", re.I)),
    ("legislative consent", re.compile(r"legislative consent", re.I)),
    ("bill stage", re.compile(
        r"\bstage [1-4]\b|\bbill\b.*\b(?:debate|proceedings|amendments?|"
        r"consideration|evidence|scrutiny)\b|\bfinancial resolution\b|"
        r"members[’']? legislative|\bLCM\b", re.I)),
    ("subordinate legislation", re.compile(
        r"\b(?:regulations|order|rules|scheme) 20\d\d\b|subordinate legislation|"
        r"statutory instruments?|negative instruments?|affirmative instruments?|"
        r"\bSSIs?\b", re.I)),
    ("questions", re.compile(
        r"question(?:s|time)?\b|^topical|^first minister[’']?s questions", re.I)),
    ("statement", re.compile(r"statement|^90 second", re.I)),
    ("petition", re.compile(r"\bpetitions?\b|\bPE\d{4}\b|\bP-\d\d-\d{3,4}\b", re.I)),
    ("committee evidence", re.compile(r"take evidence|evidence session|evidence from|"
                                      r"– evidence|- evidence|\bevidence\b", re.I)),
    ("debate", re.compile(r"debate|\bmotion\b|business$", re.I)),
)


# A slot the programme has booked without a subject yet: "Scottish Government
# Business", "Scottish Liberal Democrats Business", a bare "Members' Business"
# or "Committee Business". Typed apart so an edition can say "subject to be
# announced" instead of presenting a placeholder as business.
_PLACEHOLDER = re.compile(r"^(?:[A-Z][\w’' ]+ )?Business$|^Members[’']? Business$")


def official_only(hosts):
    """A redirect guard (HttpClient.add_redirect_guard) that refuses any hop
    off the parliament's own hosts. parliament.scot sends every path it does
    not know to webarchive.nrscotland.gov.uk: an archived page is not this
    week's business, so the hop is refused and the day is a gap."""
    from urllib.parse import urlsplit
    allowed = set(hosts)

    def guard(url, origin):
        host = urlsplit(url).hostname or ""
        if host in allowed:
            return None
        return ("redirected off {0} to {1}: not a source for forward business".format(
            "/".join(sorted(allowed)), host), False)
    return guard


def item_type(business, detail="", committee=False):
    """A coarse kind for one agenda item, read off its title (and detail)."""
    text = " ".join((business or "").split())
    if not committee and _PLACEHOLDER.match(text):
        return "to be announced"
    for kind, pattern in _TYPES:
        if pattern.search(text):
            if kind == "questions" and committee:
                continue        # "Questions" in a committee title is rarely question time
            return kind
    if committee and re.search(r"take evidence|evidence from", detail or "", re.I):
        return "committee evidence"
    return "committee business" if committee else "chamber business"


def clean(fragment):
    """Text of an HTML fragment: entities decoded, tags dropped, spaces folded."""
    text = _html.unescape(_html.unescape(fragment or ""))
    # Source line breaks are layout (Word's export wraps mid-sentence); only
    # block tags end a line.
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"<\?xml[^>]*\?>|<!DOCTYPE[^>]*>", " ", text)
    text = re.sub(r"<(?:br|/p|/li|/div|/h\d)[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def slug(text, limit=60):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:limit].rstrip("-") or "item"


def classify(tax, wl, business, detail):
    """(areas, matched_terms) for one item, business first (it is the title)."""
    from src import filter as filt
    res = filt.filter_item(tax, wl, business or "", detail or "")
    terms = list(res.matched_terms) + [t for t in (res.watchlist_hits or [])
                                       if t not in res.matched_terms]
    return res.issue_areas, terms


COLUMNS = ("key", "dated", "item_time", "body", "item_order", "business",
           "detail", "item_type", "reference", "meeting_id", "url", "source",
           "areas", "matched_terms")


def upsert(conn, table, row, today):
    """Write one item, keeping first_seen. Returns True for a new row."""
    existing = conn.execute(
        "SELECT first_seen FROM {0} WHERE key = ?".format(table),
        (row["key"],)).fetchone()
    values = [row.get(c) for c in COLUMNS]
    values[COLUMNS.index("areas")] = json.dumps(row.get("areas") or [])
    values[COLUMNS.index("matched_terms")] = json.dumps(row.get("matched_terms") or [])
    conn.execute(
        "INSERT OR REPLACE INTO {0} ({1}, first_seen, last_seen) VALUES ({2})".format(
            table, ", ".join(COLUMNS), ", ".join("?" * (len(COLUMNS) + 2))),
        values + [existing[0] if existing else today, today])
    return existing is None


def prune_unseen(conn, table, today, where, params):
    """Remove rows of a day/meeting read in full this run but not seen in it."""
    cur = conn.execute(
        "DELETE FROM {0} WHERE last_seen < ? AND {1}".format(table, where),
        [today] + list(params))
    return cur.rowcount or 0


def unique_keys(rows):
    """Suffix repeated keys (#2, #3) so two same-titled items on one day --
    Holyrood takes Parliamentary Bureau Motions twice -- are both kept."""
    seen = {}
    for row in rows:
        base = row["key"]
        seen[base] = seen.get(base, 0) + 1
        if seen[base] > 1:
            row["key"] = "{0}#{1}".format(base, seen[base])
    return rows
