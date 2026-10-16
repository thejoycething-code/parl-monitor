"""The UK petitions noise filter: free, deterministic, no model.

Chris, 16 October 2026 (round 4 decisions): "build a mute/noise list for UK
petitions in the same style as the other editions' noise files". The PR #208
scratch run kept 162 petitions on our ground; read by hand, some were there
on a word that means something else in them: "family breakdown" in a
petition about dopamine agonists, "euthanasia" of pets and dangerous dogs,
"Down syndrome" in adult cancer screening, "Equality Act 2010" in a petition
for BSL interpreters. config/uk-petitions-noise.yaml lists those MEASURED
false positives, each with a one-line reason.

WHAT A MUTE DOES. It takes an area off a petition for the EDITION only
(src/countdown.petitions_from_store); the store keeps every area. A petition
left with no shown area leaves the edition. Nothing here writes anything.

WHAT IS NEVER MUTED: a watched petition, one whose matched terms name a
watchlist Bill (config/watchlist.yaml bills:, e.g. the Terminally Ill
Adults (End of Life) Bill), as in src/prov_noise.py.

THE FILE (the shape of config/prov-noise.yaml, plus petition ids):

    exclude_ids:                  the whole petition leaves the edition
      <petition id>: <reason>
    exclude_in_area:
      <area number>:
        - title: <regex>          the petition's title (folded) matches
          only_terms: [terms]     every term it matched IN THIS AREA is one
                                  of these (a term the taxonomy does not
                                  place, e.g. a watchlist Act, keeps the area)
          except_title: <regex>   ...unless the title matches this
          ids: [petition ids]     only these petitions
          reason: <one line>      required

A rule needs at least one of title, only_terms and ids. Prefer narrow rules:
an id, or a term with a title context, over a bare term.
"""

from __future__ import annotations

import os
import re

from src import filter as filt
from src import noise

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOISE_FILE = "uk-petitions-noise.yaml"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
WATCHLIST = os.path.join(ROOT, "config", "watchlist.yaml")


class RuleError(ValueError):
    pass


class PetitionNoise:
    def __init__(self, config_dir=None, noise_file=NOISE_FILE, taxonomy_path=TAXONOMY, watchlist_path=WATCHLIST):
        raw = noise.load_yaml(config_dir, noise_file) or {}
        self.exclude_ids = {str(k): str(v).strip() for k, v in (raw.get("exclude_ids") or {}).items()}
        for pid, why in self.exclude_ids.items():
            if not why:
                raise RuleError("exclude_ids {0}: no reason".format(pid))
        self.area_rules = self._compile(raw.get("exclude_in_area") or {})
        self._term_areas = {}
        if os.path.exists(taxonomy_path):
            tax = filt.load_taxonomy(taxonomy_path)
            for area, tiers in tax.terms.items():
                for compiled in tiers.values():
                    for term, *_ in compiled:
                        self._term_areas.setdefault(noise.fold(term), set()).add(area)
        self._watched = set()
        if os.path.exists(watchlist_path):
            wl = filt.load_watchlist(watchlist_path)
            self._watched = {noise.fold(t[0]) for t in wl.bill_titles if t[0]}

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
                if not (r.get("title") or r.get("only_terms") or r.get("ids")):
                    raise RuleError(where + ": needs title, only_terms or ids")
                for k in ("title", "except_title"):
                    if r.get(k):
                        re.compile(r[k])
                out.setdefault(area, []).append({
                    "title": r.get("title"), "except_title": r.get("except_title"),
                    "only_terms": {noise.fold(t) for t in r.get("only_terms") or []},
                    "ids": {str(x) for x in r.get("ids") or []}, "reason": r["reason"].strip()})
        return out

    def watched(self, terms):
        return any(noise.fold(t) in self._watched for t in terms or [])

    def _terms_in(self, area, terms):
        out = set()
        for t in terms or []:
            f = noise.fold(t)
            got = self._term_areas.get(f)
            if got is None or area in got:
                out.add(f)
        return out

    def _hits(self, rule, pid, title, area, terms):
        if rule["ids"] and pid not in rule["ids"]:
            return False
        if rule["title"] and not re.search(rule["title"], title):
            return False
        if rule["except_title"] and re.search(rule["except_title"], title):
            return False
        if rule["only_terms"]:
            mine = self._terms_in(area, terms)
            if not mine or not mine <= rule["only_terms"]:
                return False
        return True

    def judge(self, petition_id, title, areas, terms):
        """(shown areas, {muted area: reason}) for one petition's areas."""
        areas = list(areas or [])
        pid = str(petition_id or "")
        if not areas or self.watched(terms):
            return areas, {}
        if pid in self.exclude_ids:
            return [], {a: self.exclude_ids[pid] for a in areas}
        text = noise.fold(title or "")
        muted = {}
        for a in areas:
            for rule in self.area_rules.get(a, []):
                if self._hits(rule, pid, text, a, terms):
                    muted[a] = rule["reason"]
                    break
        return [a for a in areas if a not in muted], muted
