"""Taxonomy + watchlist matching -> candidate items (handoff sections 6, 4).

Matching conventions (handoff/keyword-taxonomy.md):
  * case-insensitive;
  * trailing '*' is a stem wildcard (puberty blocker* -> puberty blockers);
  * everything else is a phrase/word match with punctuation-safe boundaries, so
    RSE does not match "nurse" and phrases with punctuation still match;
  * smart quotes are folded, so "Children's" matches "Children's";
  * global exclusions (termination, conversion, ... ) are never taxonomy terms,
    so bare noise words never match alone.

Tiering (handoff 7): a tier-1 match auto-includes (straight to review); tier-2
matches and all watchlist hits go to triage. Any item mentioning a watchlist
entity is included at minimum score 2 regardless of keyword match.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml


def _fold(text):
    """Fold smart quotes to straight quotes."""
    return (text or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')


def _norm(text):
    return _fold(text).lower()


_ACRONYM = re.compile(r"[A-Z][A-Za-z]{1,7}")  # see _is_acronym


def _is_acronym(raw):
    """Terms that must match case-sensitively.

    All-caps terms (CARE, RSE, EOTAS) and short single-word mixed-case
    acronyms with an internal capital (MAiD, FoRB) - so "maid" and "forb"
    never match. Hyphenated terms (self-ID) stay case-insensitive so
    sentence-case variants still match.
    """
    if " " in raw or "-" in raw:
        return False
    if raw.isupper():
        return True
    return len(raw) <= 6 and sum(1 for c in raw[1:] if c.isupper()) >= 1 and raw[0].isupper() and not raw[1:].islower()


def _compile_term(term):
    """Compile a term into (regex, case_sensitive).

    All-caps acronyms (CARE, SPUC, RSE, EOTAS, PATHWAYS) match case-sensitively
    against the original text, so the charity "CARE" does not match the word
    "care" and the "PATHWAYS" programme does not match "care pathways".
    """
    stem = term.endswith("*")
    raw = (term[:-1] if stem else term).strip()
    if _is_acronym(raw):
        core = _fold(raw)  # preserve case
        left, right = r"(?<![A-Za-z0-9])", ("" if stem else r"(?![A-Za-z0-9])")
        return re.compile(left + re.escape(core) + right), True
    core = _norm(raw)
    left, right = r"(?<![a-z0-9])", ("" if stem else r"(?![a-z0-9])")
    return re.compile(left + re.escape(core) + right), False


def _area_number(key):
    return int(str(key).split("_", 1)[0])


@dataclass
class Taxonomy:
    version: str
    # area -> tier -> list[(term, compiled)]
    terms: dict
    exclusions: set


def load_taxonomy(path):
    with open(path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    terms = {}
    for key, spec in (raw.get("areas") or {}).items():
        area = _area_number(key)
        terms[area] = {}
        for tier_name, tier_num in (("tier1", 1), ("tier2", 2)):
            compiled = []
            for t in (spec.get(tier_name) or []):
                pattern, cs = _compile_term(t)
                compiled.append((t, pattern, cs))
            terms[area][tier_num] = compiled
    exclusions = {str(e).lower() for e in (raw.get("exclusions_global") or [])}
    return Taxonomy(version=str(raw.get("version")), terms=terms, exclusions=exclusions)


@dataclass
class Watchlist:
    entities: list       # list[(term, compiled, cs, areas)] ; areas may be []
    bill_titles: list    # (title, compiled, cs, areas)
    act_shorts: list     # (short, compiled, cs, areas)
    holyrood: list = None    # raw holyrood entries (slug/title/areas/why), for scotland.py
    bills_raw: dict = None   # raw bills: {bill_id: {title, areas, why}} for the board
    fallen_raw: dict = None  # raw fallen_bills: same shape, closure candidates
    acts_raw: list = None    # raw acts_watch entries (short/chapter/bill_id/areas/why)
    people: list = None      # parliamentarian names: reference only, never matched


def load_watchlist(path):
    with open(path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    entities, bill_titles, act_shorts = [], [], []

    def entry(term, areas):
        pattern, cs = _compile_term(term)
        return (term, pattern, cs, areas)

    for _bill_id, spec in (raw.get("bills") or {}).items():
        e = entry(spec.get("title"), spec.get("areas") or [])
        entities.append(e)
        bill_titles.append(e)
    for act in (raw.get("acts_watch") or []):
        e = entry(act.get("short"), act.get("areas") or [])
        entities.append(e)
        act_shorts.append(e)
    for group in ("processes", "organisations"):
        for name in (raw.get(group) or []):
            entities.append(entry(name, []))
    # Parliamentarian names are deliberately NOT matching entities
    # (Christopher, 2026-08-05). Hansard prints members' names structurally,
    # so a name is a poor relevance signal: it was admitting speeches on drug
    # deaths and extreme heat to the ledger. The monitor treats every
    # parliamentarian equally, so the list confers no special status; it is
    # carried through for reference only.
    people = list(raw.get("parliamentarians") or [])
    # Holyrood bills are tracked by slug via the Scotland ingester (their status
    # comes from the bill page, not from keyword matching), so they are carried
    # through as raw entries rather than compiled into the matching entity list.
    return Watchlist(entities=entities, bill_titles=bill_titles, act_shorts=act_shorts,
                     holyrood=list(raw.get("holyrood") or []),
                     bills_raw=dict(raw.get("bills") or {}),
                     fallen_raw=dict(raw.get("fallen_bills") or {}),
                     acts_raw=list(raw.get("acts_watch") or []),
                     people=people)


@dataclass
class FilterResult:
    matched_terms: list = field(default_factory=list)
    issue_areas: list = field(default_factory=list)
    tier: int = None                 # 1 if any tier-1 match, else 2
    watchlist_hits: list = field(default_factory=list)
    min_score: int = None            # 2 when a watchlist entity is hit

    def matched(self):
        return bool(self.matched_terms) or bool(self.watchlist_hits)

    @property
    def auto_include(self):
        return self.tier == 1

    @property
    def to_triage(self):
        # tier-2-only matches and watchlist hits go to the Claude scoring pass.
        return self.matched() and not self.auto_include


def _scan_taxonomy(text_lower, text_orig, taxonomy):
    hits = []  # (area, tier, term)
    for area, tiers in taxonomy.terms.items():
        for tier_num, compiled_terms in tiers.items():
            for term, pattern, cs in compiled_terms:
                if pattern.search(text_orig if cs else text_lower):
                    hits.append((area, tier_num, term))
    return hits


def _scan_watchlist(text_lower, text_orig, watchlist):
    hits = []  # (term, areas)
    for term, pattern, cs, areas in watchlist.entities:
        if pattern.search(text_orig if cs else text_lower):
            hits.append((term, areas))
    return hits


_TAG_RE = re.compile(r"<[^>]+>")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def split_passages(text, max_chars=1200):
    """Split a long contribution into passages for per-passage matching.

    Hansard separates paragraphs with blank lines and embeds column-number
    markup; both are handled here. A paragraph longer than max_chars is
    broken on sentence boundaries, so one wall of text cannot defeat
    passage-level precision.
    """
    clean = _TAG_RE.sub(" ", text or "")
    out = []
    for para in re.split(r"[\r\n]+", clean):
        para = " ".join(para.split())
        if not para:
            continue
        if len(para) <= max_chars:
            out.append(para)
            continue
        chunk = ""
        for sentence in _SENTENCE_RE.split(para):
            if chunk and len(chunk) + len(sentence) + 1 > max_chars:
                out.append(chunk)
                chunk = sentence
            else:
                chunk = (chunk + " " + sentence).strip()
        if chunk:
            out.append(chunk)
    return out


@dataclass
class PassageMatch:
    passage: str
    result: object      # FilterResult for this passage alone


def match_passages(taxonomy, watchlist, text, title=None):
    """Filter each passage of a long text separately (qualifying ones only).

    A 3,000-word speech is then tagged with the areas its passages actually
    support, instead of every area it brushes against once. The title is
    treated as a passage in its own right: a debate title match is real.
    """
    passages = ([title] if title else []) + split_passages(text)
    matches = []
    for passage in passages:
        result = filter_item(taxonomy, watchlist, passage)
        if result.tier == 1 or result.watchlist_hits:
            matches.append(PassageMatch(passage=passage, result=result))
    return matches


def aggregate_passages(matches, max_excerpt=260):
    """(areas, terms, excerpt) from qualifying passages.

    The excerpt is the strongest-matching passage: what a 5CA Comments cell
    should quote as the reason this member is listed, rather than a debate
    title that may be about something else entirely.
    """
    if not matches:
        return [], [], None
    areas, terms = set(), []
    for m in matches:
        areas.update(m.result.issue_areas)
        for term in m.result.matched_terms + m.result.watchlist_hits:
            if term not in terms:
                terms.append(term)
    best = max(matches, key=lambda m: (
        1 if m.result.tier == 1 else 0,
        len(m.result.matched_terms) + len(m.result.watchlist_hits),
        -len(m.passage)))
    excerpt = " ".join(best.passage.split())
    if len(excerpt) > max_excerpt:
        excerpt = excerpt[:max_excerpt].rsplit(" ", 1)[0] + "..."
    return sorted(areas), terms, excerpt


def filter_item(taxonomy, watchlist, *text_fields):
    """Match an item's text fields. Returns a FilterResult (matched() may be False)."""
    text_orig = _fold(" \n ".join(f for f in text_fields if f))
    text_lower = text_orig.lower()

    tax_hits = _scan_taxonomy(text_lower, text_orig, taxonomy)
    wl_hits = _scan_watchlist(text_lower, text_orig, watchlist)

    areas = set()
    matched_terms = []
    tiers = set()
    for area, tier, term in tax_hits:
        areas.add(area)
        tiers.add(tier)
        if term not in matched_terms:
            matched_terms.append(term)

    watchlist_hits = []
    for term, wl_areas in wl_hits:
        if term not in watchlist_hits:
            watchlist_hits.append(term)
        areas.update(wl_areas)

    result = FilterResult(
        matched_terms=matched_terms,
        issue_areas=sorted(areas),
        tier=(1 if 1 in tiers else (2 if tiers else None)),
        watchlist_hits=watchlist_hits,
        min_score=(2 if watchlist_hits else None),
    )
    # A watchlist-only hit has no taxonomy tier but still belongs (min score 2).
    if result.tier is None and watchlist_hits:
        result.tier = 2
    return result
