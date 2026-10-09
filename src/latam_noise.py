"""Free, deterministic noise filters for the Latam monitor.

The AI judge stays off (X16), and Chris on 10 October 2026: "no judge yet,
we need free alternatives". So between the collectors' taxonomy pass and
what Chris reads, three cheap checks run, every one of them configured by
hand in config/latam-noise.yaml and config/latam-mute.yaml:

  * EDITION FILTERS (drop_reason): a recorded vote whose own words are
    procedural (order of the day, minutes, quorum, a recess, the Dominican
    Cámara's "liberado del trámite de lectura"); a title on a country's
    exclusion list (Dominican honours resolutions), or a vote naming only
    such bills; an item missing a country's required context (Nicaragua's
    gazette notices without a cancellation or a church); and Chris's mutes.
    These leave the edition and therefore the alerts too.
  * ALERT EVIDENCE (alert_reason): a tier-1 item that is not watched alerts
    only with a tier-1 term in its own title, or enough distinct terms in
    shown areas, or (Honduras's press releases) a decree or expediente
    number. Anything else still appears in the monthly edition.
  * A WATCHED ITEM IS NEVER FILTERED, except by its own key on the mute list.

Without config/latam-noise.yaml nothing is filtered and every tier-1 item
alerts, as before these filters existed. Patterns match text folded the way
src/filter.py folds it (lower case, accents stripped).

Measured on the October 2026 sample: docs/country-decisions-2026-10-10.md,
"Latam noise filters".
"""

from __future__ import annotations

import os
import re

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config")
TAXONOMY_ES = os.path.join(CONFIG, "taxonomy-es.yaml")
NOISE_FILE = "latam-noise.yaml"
MUTE_FILE = "latam-mute.yaml"
HIDDEN_AREAS = (11,)            # migration: matched, never shown (src/latam.py)

_FILES = {}
_TAX = {}


def fold(text):
    from src.filter import _fold
    return _fold(text or "").lower()


def _load(config_dir, name):
    path = os.path.join(config_dir or CONFIG, name)
    if path not in _FILES:
        got = None
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                got = yaml.safe_load(fh) or {}
        _FILES[path] = got
    return _FILES[path]


def clear():
    """Forget loaded files (tests, or a long-running caller after an edit)."""
    _FILES.clear()
    _TAX.clear()


# --- rules ----------------------------------------------------------------------

def rules_for(cc, config_dir=None):
    """The default rules with the country's added: lists concatenated, alert
    keys overriding one by one. None when there is no noise file."""
    raw = _load(config_dir, NOISE_FILE)
    if raw is None:
        return None
    base = raw.get("default") or {}
    own = (raw.get("countries") or {}).get(cc) or {}
    out = {
        "procedural_votes": list(base.get("procedural_votes") or [])
        + list(own.get("procedural_votes") or []),
        "exclude_titles": list(base.get("exclude_titles") or [])
        + list(own.get("exclude_titles") or []),
        "require_any": dict(base.get("require_any") or {}),
        "alert": dict(base.get("alert") or {}),
        "alert_by_kind": dict(base.get("alert_by_kind") or {}),
    }
    out["require_any"].update(own.get("require_any") or {})
    out["alert"].update(own.get("alert") or {})
    out["alert_by_kind"].update(own.get("alert_by_kind") or {})
    return out


def _any(patterns, text):
    return next((p for p in patterns or [] if re.search(p, text)), None)


# --- the mute list ----------------------------------------------------------------

def muted(it, config_dir=None, edition=False):
    """True when Chris's mute list names this item (by key, or by a title
    pattern for an unwatched item). edition=True asks for the edition, which
    honours the list only while mute_in_edition is true."""
    raw = _load(config_dir, MUTE_FILE)
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


# --- edition filters --------------------------------------------------------------

def drop_reason(it, config_dir=None):
    """Why an item leaves the edition (and so the alerts), or None to keep it."""
    if muted(it, config_dir, edition=True):
        return "muted"
    if it.get("watched"):
        return None
    rules = rules_for(it["cc"], config_dir)
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
    return None


def split(items, config_dir=None):
    """(kept, dropped); each dropped item carries its `dropped` reason."""
    kept, dropped = [], []
    for it in items:
        why = drop_reason(it, config_dir)
        if why:
            it = dict(it, dropped=why)
            dropped.append(it)
        else:
            kept.append(it)
    return kept, dropped


# --- alert evidence ---------------------------------------------------------------

def taxonomy(cc):
    if cc not in _TAX:
        from src import filter as tfilter
        _TAX[cc] = tfilter.load_taxonomy(TAXONOMY_ES, country=cc) \
            if os.path.exists(TAXONOMY_ES) else None
    return _TAX[cc]


def title_tier1(it):
    """True when the title alone carries a tier-1 term in a shown area."""
    from src import filter as tfilter
    tax = taxonomy(it["cc"])
    if tax is None or not it.get("title"):
        return False
    text = tfilter._fold(it["title"])
    return any(tier == 1 and area not in HIDDEN_AREAS
               for area, tier, _ in tfilter._scan_taxonomy(text.lower(), text, tax))


def _term_areas(cc):
    """{folded term: {areas}} for the country's taxonomy."""
    key = ("areas", cc)
    if key not in _TAX:
        out = {}
        tax = taxonomy(cc)
        for area, tiers in (tax.terms.items() if tax else ()):
            for compiled in tiers.values():
                for term, *_ in compiled:
                    out.setdefault(fold(term), set()).add(area)
        _TAX[key] = out
    return _TAX[key]


def _bare(term):
    return fold(term).replace("*", "").replace('"', "").strip()


def distinct_terms(it):
    """How many distinct matched terms the item has in shown areas. Variants
    of one term (trasplante*, trasplante de órganos) count once: a term whose
    bare form contains, or is contained in, another's is the same term."""
    areas = _term_areas(it["cc"])
    groups = []
    for t in it.get("terms") or []:
        known = areas.get(fold(t))
        if known is not None and not (known - set(HIDDEN_AREAS)):
            continue                     # migration only: not shown, not counted
        bare = _bare(t)
        if not bare:
            continue
        if not any(bare in g or g in bare for g in groups):
            groups.append(bare)
    return len(groups)


def alert_reason(it, config_dir=None):
    """Why an item alerts ("watched", "tier-1 title", ...), or None. An item
    the edition filters dropped never reaches here (src/latam.country_items);
    the mute list is checked again because the edition may ignore it."""
    if muted(it, config_dir):
        return None
    if it.get("watched"):
        return "watched"
    if it.get("tier") != 1 or it["kind"] == "updated":
        return None
    rules = rules_for(it["cc"], config_dir)
    if rules is None:
        return "tier 1"                  # no noise file: the old rule
    ev = dict(rules["alert"])
    ev.update(rules["alert_by_kind"].get(it["kind"]) or {})
    if not any(ev.get(k) for k in ("title_tier1", "distinct_terms", "numbers")):
        return "tier 1"
    if ev.get("numbers") and re.search(ev["numbers"], fold(it.get("title")) + " "
                                       + fold(it.get("body"))):
        return "decree or bill number"
    if ev.get("title_tier1") and title_tier1(it):
        return "tier-1 term in the title"
    n = int(ev.get("distinct_terms") or 0)
    if n and distinct_terms(it) >= n:
        return "{0} distinct terms".format(n)
    return None
