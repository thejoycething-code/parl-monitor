"""Classification for the provincial legislatures: TEXT, PER PASSAGE.

Measured before the build (docs/canada-provinces-scope.md, finding 2): the
English taxonomy matched 2 of 18 provincial test-case TITLES. Provincial
titles name a statute, not a subject ("Education Amendment Act, 2024" is the
pronoun and parental-notification bill). So a bill is classified on its
TEXT, passage by passage, and a division on its question, its debate heading
and the passages of the debate under that heading -- never on the title
alone. The same lesson as the Canada Gazette: match per passage, never on
the whole document, or one passing citation tags the lot.

Three layers, all needed:
  * config/taxonomy.yaml, unchanged (Christopher's to version);
  * config/watchlist-prov.yaml `terms:` -- provincial policy vocabulary the
    taxonomy measurably lacks (Policy 713, SOGI 123, "Parents' Bill of
    Rights", preferred names and pronouns), matched like taxonomy terms;
  * config/watchlist-prov.yaml `provinces.<prov>.bills:` -- watched bill
    KEYS. Matched by key only: titles recur ("Education Amendment Act,
    2025"), so a title would tag the wrong year's bill.

STATUTE NAMES ARE MASKED IN BILL TEXT. An omnibus bill names every Act it
amends: Alberta Bill 26 (puberty blockers) amends the "Human Tissue and
Organ Donation Act" for a corporate rename, and matched area 13 on that name
alone. Area 13 feeds the 5CA, so a vote on Bill 26 would have been scored as
a position on organ donation. Capitalised "... Act" names are replaced
before body passages are matched; the bill's own title is still matched
unmasked, as a passage of its own.
"""

from __future__ import annotations

import os
import re

import yaml

from src import filter as filt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
WATCHLIST = os.path.join(ROOT, "config", "watchlist-prov.yaml")
# Migration is collated, never campaigned (src/partner.py HIDDEN_AREAS).
HIDDEN_AREAS = (11,)

_ACT_NAME = re.compile(
    r"\b(?:[A-Z][\w'’\-]*\.?,?\s+(?:(?:and|of|the|for|on|in|to|des|de|la|du|et|sur)\s+)*)+"
    r"(?:Act|Code|Loi)\b(?:,?\s+\d{4})?")

_RAW = {}


def _raw(path=None):
    path = path or WATCHLIST
    if path not in _RAW:
        with open(path, encoding="utf-8") as fh:
            _RAW[path] = yaml.safe_load(fh) or {}
    return _RAW[path]


def load_taxonomy(path=None):
    return filt.load_taxonomy(path or TAXONOMY)


def load_watchlist(prov, path=None):
    """A filter.Watchlist whose entities are the shared and the province's
    `terms:`. Bills are NOT compiled into entities (key-only, see above)."""
    raw = _raw(path)
    entities = []
    specs = list(raw.get("terms") or []) + list(
        ((raw.get("provinces") or {}).get(prov) or {}).get("terms") or [])
    for spec in specs:
        term = spec["term"] if isinstance(spec, dict) else spec
        areas = list((spec.get("areas") if isinstance(spec, dict) else None) or [])
        pattern, cs = filt._compile_term(term)
        guards = [filt._compile_term(g) for g in ((spec.get("with") if isinstance(spec, dict) else None) or [])]
        entities.append((term, _Guarded(pattern, cs, guards), cs, areas, False))
    return filt.Watchlist(entities=entities, bill_titles=[], act_shorts=[])


class _Guarded:
    """A compiled term that matches only with one of its guards in the same
    passage -- the taxonomy's {term, with: [...]} form, for watchlist terms."""

    def __init__(self, pattern, cs, guards):
        self.pattern, self.cs, self.guards = pattern, cs, guards

    def search(self, text):
        hit = self.pattern.search(text)
        if not hit or not self.guards:
            return hit
        low = text.lower()
        return hit if any(g.search(text if gcs else low) for g, gcs in self.guards) else None


def watched_bill(prov, key, path=None):
    """The watchlist entry for a bill KEY, or None."""
    if not key:
        return None
    return (((_raw(path).get("provinces") or {}).get(prov) or {}).get("bills") or {}).get(key)


def mask_statute_names(text):
    return _ACT_NAME.sub(" [statute] ", text or "")


class Result:
    __slots__ = ("areas", "terms", "tier", "excerpt")

    def __init__(self, areas=None, terms=None, tier=None, excerpt=None):
        self.areas, self.terms, self.tier, self.excerpt = (
            sorted(set(areas or [])), list(terms or []), tier, excerpt)

    def merge(self, other):
        if other is None:
            return self
        terms = self.terms + [t for t in other.terms if t not in self.terms]
        tiers = [t for t in (self.tier, other.tier) if t]
        return Result(set(self.areas) | set(other.areas), terms,
                      min(tiers) if tiers else None, self.excerpt or other.excerpt)

    def on_our_ground(self):
        return on_our_ground(self.areas)

    def __repr__(self):
        return "Result(areas={0}, tier={1}, terms={2})".format(self.areas, self.tier, self.terms)


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def classify_text(tax, wl, title=None, body=None, mask=True):
    """Per-passage classification of one text. The title, when given, is a
    passage of its own and is never masked."""
    text = mask_statute_names(body) if (mask and body) else (body or "")
    matches = filt.match_passages(tax, wl, text, title=title or None)
    areas, terms, excerpt = filt.aggregate_passages(matches)
    tiers = [m.result.tier for m in matches if m.result.tier]
    return Result(areas, terms, min(tiers) if tiers else None, excerpt)


def classify(tax, wl, prov, title=None, texts=(), bill_key=None, mask=True,
             inherit=None):
    """Title + any number of body texts + a watched bill key + the areas a
    division INHERITS from its bill's stored text classification."""
    res = classify_text(tax, wl, title=title, body=None)
    for body in texts:
        if body:
            res = res.merge(classify_text(tax, wl, body=body, mask=mask))
    if inherit is not None:
        res = res.merge(inherit)
    entry = watched_bill(prov, bill_key)
    if entry:
        res = res.merge(Result(entry.get("areas") or [], [bill_key], 1))
    return res
