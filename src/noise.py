"""Free, deterministic noise filters, shared by every edition that runs
without the AI judge (X16: deferred, stays off).

Generalised on 10 October 2026 from src/latam_noise.py (PR #23), which is
now a thin wrapper over a `Noise` built here, so the Latam monitor and the
weekly country editions (src/country_edition.py) run one implementation.

Three cheap checks, every one configured by hand in YAML:

  * EDITION FILTERS (drop_reason): a recorded vote whose own words are
    procedural (order of the day, minutes, quorum, a recess); a title on the
    country's exclusion list, or a vote naming only such bills; an item
    missing the country's required context; an item without the country's
    minimum evidence for the edition (`edition_evidence`); and Chris's mutes.
  * MINIMUM EVIDENCE (alert_reason): a tier-1 item that is not watched
    qualifies (for an instant alert in the Latam monitor, for the lead of a
    weekly edition) only with a tier-1 term in its own title, or enough
    distinct terms in shown areas, or a pattern (a decree or bill number).
  * A WATCHED ITEM IS NEVER FILTERED, except by its own key on the mute list.

THE RULES FILE. Either the Latam shape (`default:` plus `countries: {cc:
...}`, the default's lists concatenated with the country's, its `alert`
keys overridden one by one) or, for a file that holds one country's rules
(config/edition-noise-<cc>.yaml), the country's keys at the top level.
Keys:

    procedural_votes   [regex]   a vote whose title matches leaves
    exclude_titles     [regex]   any item whose title matches leaves
    require_any        {kind: [regex]}  kept only if title or body matches
    alert              {title_tier1, distinct_terms, numbers}
    alert_by_kind      {kind: {...}}    the same keys for one kind
    edition_evidence   {kind: {title_tier1, distinct_terms, numbers,
                       own_words}}  an unwatched item of that kind stays in
                       the edition only with one of these (any tier);
                       own_words: true accepts an item whose own words (not
                       only its parent bill's or dossier's) matched

Without a rules file nothing is filtered and every tier-1 item qualifies.
Patterns match text folded the way src/filter.py folds it (lower case,
accents stripped, 'ł' to 'l', 'ß' to 'ss').
"""

from __future__ import annotations

import os
import re

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config")
HIDDEN_AREAS = (11,)            # migration: matched, never shown

_FILES = {}


def fold(text):
    from src.filter import _fold
    return _fold(text or "").lower()


def load_yaml(config_dir, name):
    """A config file's contents, cached by path; None when it is absent."""
    path = os.path.join(config_dir or CONFIG, name)
    if path not in _FILES:
        got = None
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                got = yaml.safe_load(fh) or {}
        _FILES[path] = got
    return _FILES[path]


def _any(patterns, text):
    return next((p for p in patterns or [] if re.search(p, text)), None)


EVIDENCE_KEYS = ("title_tier1", "distinct_terms", "numbers", "own_words")


class Noise:
    """One edition family's filters.

    noise_file, mute_file: a file name in the config directory, or a
    callable cc -> file name (one file per country). taxonomies: callable
    cc -> [(path, country code)], the taxonomy files the country's collector
    classifies with (two for Belgium, Dutch and French).
    """

    def __init__(self, noise_file, mute_file, taxonomies, hidden_areas=HIDDEN_AREAS):
        self.noise_file = noise_file
        self.mute_file = mute_file
        self.taxonomies = taxonomies
        self.hidden_areas = tuple(hidden_areas)
        self._tax = {}

    def _name(self, which, cc):
        return which(cc) if callable(which) else which

    def clear(self):
        """Forget loaded files (tests, or a long-running caller after an edit)."""
        _FILES.clear()
        self._tax.clear()

    # --- rules ------------------------------------------------------------------

    def rules_for(self, cc, config_dir=None):
        """The rules for one country, None when there is no rules file."""
        raw = load_yaml(config_dir, self._name(self.noise_file, cc))
        if raw is None:
            return None
        if "countries" in raw or "default" in raw:
            base = raw.get("default") or {}
            own = (raw.get("countries") or {}).get(cc) or {}
        else:
            base, own = {}, raw
        out = {
            "procedural_votes": list(base.get("procedural_votes") or [])
            + list(own.get("procedural_votes") or []),
            "exclude_titles": list(base.get("exclude_titles") or [])
            + list(own.get("exclude_titles") or []),
            "require_any": dict(base.get("require_any") or {}),
            "alert": dict(base.get("alert") or {}),
            "alert_by_kind": dict(base.get("alert_by_kind") or {}),
            "edition_evidence": dict(base.get("edition_evidence") or {}),
        }
        out["require_any"].update(own.get("require_any") or {})
        out["alert"].update(own.get("alert") or {})
        out["alert_by_kind"].update(own.get("alert_by_kind") or {})
        out["edition_evidence"].update(own.get("edition_evidence") or {})
        return out

    # --- the mute list ------------------------------------------------------------

    def muted(self, it, config_dir=None, edition=False):
        """True when Chris's mute list names this item (by key, or by a title
        pattern for an unwatched item). edition=True asks for the edition,
        which honours the list only while mute_in_edition is true."""
        raw = load_yaml(config_dir, self._name(self.mute_file, it["cc"]))
        if not raw:
            return False
        if edition and not raw.get("mute_in_edition", True):
            return False
        keys = {str(k) for k in raw.get("items") or []}
        if "{0}|{1}|{2}".format(it["cc"], it["kind"], it["key"]) in keys or \
                "{0}|{1}".format(it["cc"], it["key"]) in keys:
            return True
        if it.get("watched"):
            return False
        title = fold(it.get("title"))
        for p in raw.get("patterns") or []:
            if not isinstance(p, dict) or not p.get("title"):
                continue
            if p.get("cc") and p["cc"] != it["cc"]:
                continue
            if p.get("kind") and p["kind"] != it["kind"]:
                continue
            if re.search(p["title"], title):
                return True
        return False

    # --- edition filters ----------------------------------------------------------

    def drop_reason(self, it, config_dir=None):
        """Why an item leaves the edition (and so any alert), or None to keep it."""
        if self.muted(it, config_dir, edition=True):
            return "muted"
        if it.get("watched"):
            return None
        rules = self.rules_for(it["cc"], config_dir)
        if not rules:
            return None
        title = fold(it.get("title"))
        if it["kind"] == "vote" and _any(rules["procedural_votes"], title):
            return "procedural vote"
        if _any(rules["exclude_titles"], title):
            return "excluded title"
        refs = it.get("refs") or []
        if it["kind"] == "vote" and refs and rules["exclude_titles"] and all(
                _any(rules["exclude_titles"], fold(r)) for r in refs):
            return "names only excluded bills"
        need = rules["require_any"].get(it["kind"])
        if need and not _any(need, title + " " + fold(it.get("body"))):
            return "missing required context"
        ev = rules["edition_evidence"].get(it["kind"])
        if ev and not self.evidence(it, ev):
            return "too little evidence"
        return None

    def split(self, items, config_dir=None):
        """(kept, dropped); each dropped item carries its `dropped` reason."""
        kept, dropped = [], []
        for it in items:
            why = self.drop_reason(it, config_dir)
            if why:
                dropped.append(dict(it, dropped=why))
            else:
                kept.append(it)
        return kept, dropped

    # --- evidence -----------------------------------------------------------------

    def taxonomy(self, cc):
        """The country's compiled taxonomies, in a list ([] when none exist)."""
        if cc not in self._tax:
            from src import filter as tfilter
            self._tax[cc] = [tfilter.load_taxonomy(path, country=code)
                             for path, code in (self.taxonomies(cc) or [])
                             if os.path.exists(path)]
        return self._tax[cc]

    def title_tier1(self, it):
        """True when the title alone carries a tier-1 term in a shown area."""
        from src import filter as tfilter
        if not it.get("title"):
            return False
        text = tfilter._fold(it["title"])
        return any(tier == 1 and area not in self.hidden_areas
                   for tax in self.taxonomy(it["cc"])
                   for area, tier, _ in tfilter._scan_taxonomy(text.lower(), text, tax))

    def _term_areas(self, cc):
        """{folded term: {areas}} over the country's taxonomies."""
        key = ("areas", cc)
        if key not in self._tax:
            out = {}
            for tax in self.taxonomy(cc):
                for area, tiers in tax.terms.items():
                    for compiled in tiers.values():
                        for term, *_ in compiled:
                            out.setdefault(fold(term), set()).add(area)
            self._tax[key] = out
        return self._tax[key]

    def distinct_terms(self, it):
        """How many distinct matched terms the item has in shown areas.
        Variants of one term (trasplante*, trasplante de órganos) count once:
        a term whose bare form contains, or is contained in, another's is
        the same term."""
        areas = self._term_areas(it["cc"])
        groups = []
        for t in it.get("terms") or []:
            known = areas.get(fold(t))
            if known is not None and not (known - set(self.hidden_areas)):
                continue                 # hidden areas only: not shown, not counted
            bare = fold(t).replace("*", "").replace('"', "").strip()
            if not bare:
                continue
            if not any(bare in g or g in bare for g in groups):
                groups.append(bare)
        return len(groups)

    def evidence(self, it, ev):
        """The first piece of evidence `ev` asks for that the item has, or None."""
        if ev.get("own_words") and it.get("own") is not False:
            return "own words"
        if ev.get("numbers") and re.search(ev["numbers"], fold(it.get("title")) + " "
                                           + fold(it.get("body"))):
            return "decree or bill number"
        if ev.get("title_tier1") and self.title_tier1(it):
            return "tier-1 term in the title"
        n = int(ev.get("distinct_terms") or 0)
        if n and self.distinct_terms(it) >= n:
            return "{0} distinct terms".format(n)
        return None

    def alert_reason(self, it, config_dir=None):
        """Why an item qualifies ("watched", "tier-1 title", ...), or None. An
        item the edition filters dropped never reaches here; the mute list
        is checked again because the edition may ignore it."""
        if self.muted(it, config_dir):
            return None
        if it.get("watched"):
            return "watched"
        if it.get("tier") != 1 or it["kind"] == "updated":
            return None
        rules = self.rules_for(it["cc"], config_dir)
        if rules is None:
            return "tier 1"              # no rules file: the plain rule
        ev = dict(rules["alert"])
        ev.update(rules["alert_by_kind"].get(it["kind"]) or {})
        if not any(ev.get(k) for k in EVIDENCE_KEYS):
            return "tier 1"
        return self.evidence(it, ev)
