"""Read what a country vote is ON, not just its title (16 October 2026).

The UK reads the clause a division title only numbers (src/clausetext.py,
#194, #200). The same blindness hits every parliament whose recorded votes
carry generic titles: a French scrutin "l'amendement n° 516 de Mme Rousseau
a l'article 44 ...", an Italian Camera vote "Emendamento 7-bis.1 ORRICO ...",
a Dutch "Amendement van het lid X ter vervanging van nr. 12", a German
"(Änderungsantrag)" poll. Their areas came from the bill they amend, if that
bill was on our ground at all; an amendment putting abortion or gender into an
unrelated bill was invisible.

This module is the country-neutral half: the store cache, the match, the
ledger gate, the apply step and the fail-loud gap. Each country has a reader
(src/amendtext_<cc>.py) that knows its own source and identifiers:

    reader.candidates(conn)   -> votes whose titles only name an amendment,
                                 motion or resolution (dicts, `key` and
                                 `title` at least)
    reader.refs(row)          -> the source's own identifiers the vote names
                                 ([] = not a vote this reader reads)
    reader.fetch(row, refs)   -> Lookup with texts [{label, kind, source_id,
                                 url, purpose, text}]
    reader.taxonomy()         -> (taxonomy, watchlist, mask function)
    reader.apply(conn, row, result)  (optional; default: the division row's
                                 areas / matched_terms / tier columns)

A vote is linked to its text ONLY by the source's own identifiers (an
amendment number within a named text, a document id, a Kamerstuk number);
never by guessing from a title, and a link that is not unique is a gap.

MATCH SOURCE "amendment text". The taxonomy (the country's language master,
with its [only: cc] filter and the collector's own false-friend masks) runs
over each text on its own, so the record names the text that carried the
term (src/clausetext.match, the same convention).

THE LEDGER GATE (src/clausetext.ledger_ok, the same rule). A match in the body
of an amendment is not what the amendment is FOR: a French amendment to a
social-security article citing "l'article L. 2212-1 du code de la sante
publique" (abortion) in a list of exemptions, a Dutch motion's considerans
("overwegende dat ...") naming euthanasia in passing. Only a TIER-1 term in
the text's PURPOSE -- the reader sets it: the expose sommaire's opening, the
operative "verzoekt de regering" clause, the Antrag's heading, the ODG's
"impegna il Governo" -- opens the ledger. When it does, the division takes
the areas (union), the terms and tier 1, so the 5CA drafting, member
profiles and editions see it like any tier-1 vote. When it does not, the
match is still stored here and listed for review (tools/amendment_text.py
--report), but no member is placed by it.

THE APPLY IS RE-RUN EVERY WEEK from this cache, with no network: a
collector's upsert or --reclassify recomputes a division's areas from its
own title and its bill, which would drop the amendment's areas, so the
weekly's amendment-text step runs AFTER the collector and re-applies every
gated match. It is a union: it never removes an area the collector set.

Cached in the store (`amendment_text`, one row per division read
successfully, the texts kept so a taxonomy change re-matches offline);
failures are not cached and are tried again next run. Fail loud: a vote that
names a text we cannot read is reported "could not read amendment text
(<reason>)" in the gaps table and the run log, never "no match".
"""

from __future__ import annotations

import datetime
import json
import time
from dataclasses import dataclass, field

SOURCE = "amendment text"
PURPOSE_CHARS = 600      # a purpose longer than this is clipped before the gate reads it
MAX_GAP_ROWS = 25        # individual gap rows per run; the rest are summed in one line
TEXT_CHARS = 20000       # one stored text, at most


@dataclass
class Lookup:
    status: str                                   # none | ok | unreadable
    refs: list = field(default_factory=list)      # the source's identifiers, as strings
    texts: list = field(default_factory=list)     # [{label, kind, source_id, url, purpose, text}]
    reason: str = None
    cached: bool = False

    @property
    def gap(self):
        """The fail-loud line: unreadable, or read only in part."""
        if self.status == "none" or not self.reason:
            return None
        return "could not read amendment text ({0})".format(self.reason)


def unreadable(refs, reason):
    return Lookup("unreadable", refs=list(refs or []), reason=reason)


def clip(text, n=TEXT_CHARS):
    text = " ".join((text or "").split()) if n < 2000 else (text or "").strip()
    return text[:n]


def entry(label, kind, source_id, url, purpose, text):
    """One text as stored: the purpose clipped for the gate, the body capped."""
    return {"label": label, "kind": kind, "source_id": source_id, "url": url,
            "purpose": clip(purpose, PURPOSE_CHARS), "text": clip(text)}


# -- store cache ----------------------------------------------------------------

def cached(conn, cc, key):
    try:
        row = conn.execute("SELECT refs, texts FROM amendment_text WHERE cc=? AND division_key=?",
                           (cc, str(key))).fetchone()
    except Exception:                                   # noqa: BLE001 - pre-migration store
        return None
    if not row:
        return None
    return Lookup("ok", refs=json.loads(row[0] or "[]"), texts=json.loads(row[1] or "[]"), cached=True)


def store(conn, cc, key, lk, today=None):
    if lk.status != "ok":
        return
    conn.execute(
        "INSERT INTO amendment_text (cc, division_key, refs, texts, fetched_at) VALUES (?,?,?,?,?) "
        "ON CONFLICT(cc, division_key) DO UPDATE SET refs=excluded.refs, texts=excluded.texts, "
        "fetched_at=excluded.fetched_at",
        (cc, str(key), json.dumps(lk.refs, ensure_ascii=False), json.dumps(lk.texts, ensure_ascii=False),
         today or datetime.date.today().isoformat()))


def save_match(conn, cc, key, result, labels, ledger, today=None):
    conn.execute(
        "UPDATE amendment_text SET areas=?, matched_terms=?, tier=?, labels=?, ledger=?, "
        "match_source=?, matched_at=? WHERE cc=? AND division_key=?",
        (json.dumps(result.issue_areas if result else []),
         json.dumps((result.matched_terms + result.watchlist_hits) if result else [], ensure_ascii=False),
         result.tier if result else None, json.dumps(labels or [], ensure_ascii=False),
         1 if ledger else 0, SOURCE if labels else None,
         today or datetime.date.today().isoformat(), cc, str(key)))


# -- match and gate -------------------------------------------------------------

def match(lookup, tax, wl, mask=None):
    """(FilterResult, [labels that matched]) over the texts; (None, []) if none read.

    Each text is matched on its own so the record names the text that carried
    the term; title="" because an amendment body has no heading of its own (a
    broad watchlist name cited inside it is a citation, not the subject)."""
    from src import filter as filt
    if lookup.status != "ok":
        return None, []
    mask = mask or (lambda s: s)
    bodies = [(t, mask(" \n ".join(x for x in (t.get("purpose"), t.get("text")) if x)))
              for t in lookup.texts]
    hits = [(t, b) for t, b in bodies if filt.filter_item(tax, wl, b, title="").matched()]
    if not hits:
        return filt.FilterResult(), []
    result = filt.filter_item(tax, wl, *[b for _, b in hits], title="")
    return result, [t["label"] for t, _ in hits]


def ledger_ok(lookup, labels, tax, wl, mask=None):
    """May an amendment-text match place the vote's members?

    Only when a TIER-1 term is in what the text is FOR (its `purpose`, set by
    the reader), not merely somewhere in its body. A text with no purpose of
    its own never opens the ledger: its body is listed for review only."""
    from src import filter as filt
    mask = mask or (lambda s: s)
    for t in lookup.texts:
        if t.get("label") not in labels or not t.get("purpose"):
            continue
        if filt.filter_item(tax, wl, mask(t["purpose"]), title="").tier == 1:
            return True
    return False


def describe(lookup, labels):
    """The 'why' line a reviewer sees: which text, from where."""
    hit = [t for t in lookup.texts if t.get("label") in labels]
    urls = [t["url"] for t in hit if t.get("url")]
    return "{0}: {1}".format(SOURCE, ", ".join(labels)) + (" " + urls[0] if urls else "")


# -- apply ----------------------------------------------------------------------

def _json_list(raw):
    try:
        val = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return val if isinstance(val, list) else []


def apply_columns(conn, table, key_col, key, result, areas_col="areas", terms_col="matched_terms",
                  tier_col="tier"):
    """Union a gated match into a division row. Returns True when it changed.

    Never removes: an area or term the collector set stays. tier becomes 1."""
    cols = [areas_col] + [c for c in (terms_col, tier_col) if c]
    row = conn.execute("SELECT {0} FROM {1} WHERE {2}=?".format(", ".join(cols), table, key_col),
                       (key,)).fetchone()
    if row is None:
        return False
    areas = sorted(set(_json_list(row[0])) | set(result.issue_areas or []), key=lambda a: (str(type(a)), a))
    sets, vals = ["{0}=?".format(areas_col)], [json.dumps(areas)]
    changed = areas != _json_list(row[0])
    if terms_col:
        old = _json_list(row[1])
        terms = old + [t for t in (result.matched_terms or []) if t not in old]
        sets.append("{0}=?".format(terms_col))
        vals.append(json.dumps(terms, ensure_ascii=False))
        changed = changed or terms != old
    if tier_col:
        old_tier = row[len(cols) - 1]
        sets.append("{0}=?".format(tier_col))
        vals.append(1)
        changed = changed or old_tier != 1
    if changed:
        conn.execute("UPDATE {0} SET {1} WHERE {2}=?".format(table, ", ".join(sets), key_col), vals + [key])
    return changed


# -- the run --------------------------------------------------------------------

@dataclass
class Outcome:
    key: str
    date: str
    title: str
    status: str                 # ok | unreadable | skipped (budget)
    cached: bool = False
    areas: list = field(default_factory=list)
    terms: list = field(default_factory=list)
    labels: list = field(default_factory=list)
    ledger: bool = False
    changed: bool = False
    gap: str = None
    why: str = None
    before: list = field(default_factory=list)   # the division's areas before


def run(conn, reader, budget_seconds=None, limit=None, apply=True, record_gaps=True, log=print,
        clock=time.monotonic, today=None):
    """Read, match, gate and apply for every candidate vote. Returns [Outcome].

    Cached votes are re-matched and re-applied with no network (the weekly
    re-apply); new ones are fetched while the budget lasts and `limit`
    allows. Never raises on a source failure: that is a gap."""
    from src import db
    start = clock()
    tax, wl, mask = reader.taxonomy()
    out, gaps, fetched = [], [], 0
    for row in reader.candidates(conn):
        refs = reader.refs(row)
        if not refs:
            continue
        key = str(row["key"])
        lk = cached(conn, reader.cc, key)
        if lk is None:
            over = budget_seconds is not None and clock() - start > budget_seconds
            if over or (limit is not None and fetched >= limit):
                out.append(Outcome(key, row.get("date"), row.get("title"), "skipped"))
                continue
            fetched += 1
            try:
                lk = reader.fetch(row, refs)
            except Exception as exc:                    # noqa: BLE001 - fail loud, never fatal
                lk = unreadable(refs, "{0}: {1}".format(type(exc).__name__, str(exc)[:160]))
            if lk.status == "ok":
                store(conn, reader.cc, key, lk, today)
        o = Outcome(key, row.get("date"), row.get("title"), lk.status, cached=lk.cached,
                    before=_json_list(row.get("areas")))
        if lk.gap:
            o.gap = lk.gap
            gaps.append("{0} {1} ({2}): {3}".format(reader.cc.upper(), key, row.get("date") or "?", lk.gap))
        if lk.status == "ok":
            result, labels = match(lk, tax, wl, mask)
            o.labels = labels
            if labels:
                o.areas, o.terms = list(result.issue_areas), result.matched_terms + result.watchlist_hits
                o.ledger = ledger_ok(lk, labels, tax, wl, mask)
                o.why = describe(lk, labels)
                if o.ledger and apply:
                    o.changed = bool(reader.apply(conn, row, result))
            save_match(conn, reader.cc, key, result, labels, o.ledger, today)
        out.append(o)
    conn.commit()
    if record_gaps and gaps:
        feed = "{0}-amendment-text".format(reader.cc)
        for g in gaps[:MAX_GAP_ROWS]:
            db.record_gap(conn, feed, g)
        if len(gaps) > MAX_GAP_ROWS:
            db.record_gap(conn, feed, "{0} more vote(s) whose amendment text could not be read "
                                      "(tools/amendment_text.py --cc {1} --report lists them)".format(
                                          len(gaps) - MAX_GAP_ROWS, reader.cc))
    skipped = sum(1 for o in out if o.status == "skipped")
    if skipped:
        log("  {0}: {1} vote(s) left for the next run (budget/limit); read next week".format(
            reader.cc.upper(), skipped))
    return out


class Reader:
    """Base for a country reader; see the module docstring."""

    cc = None
    table = None          # the division table
    key_col = None        # its key column

    def taxonomy(self):
        raise NotImplementedError

    def candidates(self, conn):
        raise NotImplementedError

    def refs(self, row):
        raise NotImplementedError

    def fetch(self, row, refs):
        raise NotImplementedError

    def apply(self, conn, row, result):
        return apply_columns(conn, self.table, self.key_col, row["key"], result)
