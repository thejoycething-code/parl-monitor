"""The provinces edition's noise filter: free, deterministic, no model.

Christopher, 9 October 2026: free alternatives to a paid judge, "option 2".
config/prov-noise.yaml lists MEASURED false positives, each pattern keyed to
the area it wrongly tags and carrying a one-line reason: "Down syndrome" on a
commemorative day act is not abortion, "coercion" in a labour bill is not
assisted dying, "surrogate" (a substitute decision-maker) in an estates bill
is not surrogacy, laicity in an Appropriation Act is a ministry's name.

WHAT A MUTE DOES. It takes that area off the item for the EDITION only
(tools/prov_monitor.py); the store keeps every area. An item whose every
shown area is muted leaves the edition, and the edition's Coverage section
counts what was muted. Nothing here writes anything.

WHAT IS NEVER MUTED:
  * a watched item (its matched terms carry a bill key from
    config/watchlist-prov.yaml), as in src/noise.py;
  * anything a signed reading in config/prov_stance.yaml covers (a confirmed
    or evidence-only reading of the division, of the bill, or of a division
    on the bill): a human has read it, so it is not noise.

THE FILE. The same shape as config/edition-noise-<cc>.yaml (src/noise.py's
single-file form, so src/noise.Noise.rules_for reads it and its general keys
work as there: `exclude_titles` drops a whole item). The provinces add one
key, `exclude_in_area`, which src/noise.py ignores:

    exclude_in_area:
      <area number>:
        - title: <regex>          the item's heading matches (see below)
          only_terms: [terms]     every term the item matched IN THIS AREA is
                                  one of these (a term the taxonomies do not
                                  place, e.g. a watchlist phrase, keeps the area)
          except_title: <regex>   ...unless the heading matches this
          kinds: [bill, division, speech]   default: all three
          reason: <one line>      required

At least one of title and only_terms. Patterns match text folded as the
taxonomy folds it (lower case, accents stripped). The HEADING is a bill's
English and French titles; a division's linked bills' titles, its stage
and its question; a speech's debate subject and rubric.

Built so it can merge into src/noise.py later: the reader below uses
noise.load_yaml / noise.fold / Noise.rules_for and nothing of its own format.
"""

from __future__ import annotations

import os
import re

from src import noise

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOISE_FILE = "prov-noise.yaml"
HIDDEN_AREAS = (11,)
KINDS = ("bill", "division", "speech")
TAXONOMIES = [(os.path.join(ROOT, "config", "taxonomy.yaml"), None),
              (os.path.join(ROOT, "config", "taxonomy-qc.yaml"), None)]
_BILL_KEY = re.compile(r"^[a-z]{2}-\d+-\d+/")


class RuleError(ValueError):
    pass


def watched(terms):
    """A watched item's matched terms carry its bill key (src/prov_classify)."""
    return any(_BILL_KEY.match(str(t)) for t in terms or [])


class ProvNoise:
    def __init__(self, config_dir=None, noise_file=NOISE_FILE, signed=None):
        """signed: (division keys, bill keys) a signed reading covers, from
        signed_keys(); None treats nothing as signed."""
        self.config_dir = config_dir
        self.noise_file = noise_file
        self._noise = noise.Noise(noise_file, None, lambda cc: TAXONOMIES, HIDDEN_AREAS)
        self.signed_divisions, self.signed_bills = signed or (set(), set())
        raw = noise.load_yaml(config_dir, noise_file) or {}
        self.rules = self._noise.rules_for("prov", config_dir) or {"exclude_titles": []}
        self.area_rules = self._compile(raw.get("exclude_in_area") or {})

    @staticmethod
    def _compile(raw):
        out = {}
        for area, rules in raw.items():
            try:
                area = int(area)
            except (TypeError, ValueError):
                raise RuleError("exclude_in_area: {0!r} is not an area number".format(area))
            for i, r in enumerate(rules or []):
                where = "exclude_in_area {0} #{1}".format(area, i + 1)
                if not isinstance(r, dict):
                    raise RuleError(where + ": not a mapping")
                if not (r.get("reason") or "").strip():
                    raise RuleError(where + ": no reason")
                if not r.get("title") and not r.get("only_terms"):
                    raise RuleError(where + ": needs title or only_terms")
                bad = set(r.get("kinds") or KINDS) - set(KINDS)
                if bad:
                    raise RuleError(where + ": unknown kinds {0}".format(sorted(bad)))
                for k in ("title", "except_title"):
                    if r.get(k):
                        re.compile(r[k])
                out.setdefault(area, []).append({
                    "title": r.get("title"), "except_title": r.get("except_title"),
                    "only_terms": {noise.fold(t) for t in r.get("only_terms") or []},
                    "kinds": tuple(r.get("kinds") or KINDS), "reason": r["reason"].strip()})
        return out

    def _terms_in(self, area, terms):
        """The item's matched terms that may belong to `area`: those the
        taxonomies place there, and those they do not place at all."""
        known = self._noise._term_areas("prov")
        out = set()
        for t in terms or []:
            f = noise.fold(t)
            got = known.get(f)
            if got is None or area in got:
                out.add(f)
        return out

    def _rule_hits(self, rule, kind, heading, area, terms):
        if kind not in rule["kinds"]:
            return False
        if rule["title"] and not re.search(rule["title"], heading):
            return False
        if rule["except_title"] and re.search(rule["except_title"], heading):
            return False
        if rule["only_terms"]:
            mine = self._terms_in(area, terms)
            if not mine or not mine <= rule["only_terms"]:
                return False
        return True

    def protected(self, kind, key, bill_keys=()):
        """True when a signed reading covers the item (see the module doc)."""
        if kind == "division" and key in self.signed_divisions:
            return True
        if kind == "bill" and key in self.signed_bills:
            return True
        return any(b in self.signed_bills for b in bill_keys or [] if b)

    def judge(self, kind, key, heading, areas, terms, bill_keys=()):
        """(shown areas, {muted area: reason}). `areas` are the stored areas;
        hidden areas are never shown. An item left with no shown area, while
        it had some, is muted from the edition."""
        shown = [a for a in areas or [] if a not in HIDDEN_AREAS]
        if not shown or watched(terms) or self.protected(kind, key, bill_keys):
            return shown, {}
        text = noise.fold(heading)
        whole = noise._any(self.rules.get("exclude_titles"), text)
        if whole:
            return [], {a: "excluded title" for a in shown}
        muted = {}
        for a in shown:
            for rule in self.area_rules.get(a, []):
                if self._rule_hits(rule, kind, text, a, terms):
                    muted[a] = rule["reason"]
                    break
        return [a for a in shown if a not in muted], muted


def signed_keys(conn, stance_path=None):
    """(division keys, bill keys) a SIGNED reading covers: confirmed or
    evidence-only entries in config/prov_stance.yaml. A bill with a signed
    division counts as signed, so its votes and the bill never part."""
    import sys
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import prov_5ca as p5
    path = stance_path or p5.STANCE_PATH
    signed = ("confirmed", "unplaceable")
    divs = {k for k, e in p5.load_stance(path, "divisions").items() if p5.status(e) in signed}
    bills = {k for k, e in p5.load_stance(path, "bills").items() if p5.status(e) in signed}
    if conn is not None and divs:
        marks = ",".join("?" * len(divs))
        keys = list(divs)
        for (b,) in conn.execute("SELECT bill_key FROM prov_divisions WHERE bill_key IS NOT NULL "
                                 "AND division_key IN ({0})".format(marks), keys):
            bills.add(b)
        try:
            for (b,) in conn.execute("SELECT bill_key FROM prov_division_bills WHERE division_key "
                                     "IN ({0})".format(marks), keys):
                bills.add(b)
        except Exception:                     # noqa: BLE001  (an old store without the table)
            pass
    return divs, bills
