"""Regenerate config/taxonomy.yaml from docs/keyword-taxonomy.md.

The markdown is the human-editable master (handoff section 6 / CLAUDE.md:
never hand-edit the yaml). This tool makes that rule enforceable:

    python3 tools/generate_taxonomy.py            # rewrite config/taxonomy.yaml
    python3 tools/generate_taxonomy.py --check    # exit 1 if yaml is out of sync

tests/test_taxonomy_sync.py runs the --check equivalent in the suite, so a
hand-edited yaml (or an md edit without regeneration) fails CI.

Markdown conventions parsed here:
  * area headings carry their yaml key:  ### 1. Abortion {#1_abortion}
  * term lines are semicolon-separated:  - **Tier 1:** abortion; "buffer zone*"
  * quoted terms keep their quotes (phrase match); trailing * is a stem;
    all-caps terms match case-sensitively (filter-side heuristic, no flag here)
  * a term may require company:          "buffer zone*" [with: clinic*, abortion]
    which matches only when the text also contains one of the listed guards.
    For terms whose words belong to more than one policy area -- a buffer zone
    is an abortion clinic zone, a pesticide margin and a military perimeter --
    the guard is what keeps someone else's subject out of ours.
  * a term may be vetoed by company:     "organ donor*" [without: "organ donor leave"]
    which does NOT match where the text also contains one of the vetoes. For
    terms whose own words are ours but sit inside someone else's subject: a
    labour code's organ-donor leave is employment law, not transplant ethics
    (v1.16, 2 October 2026). Both brackets may follow one term, with first.
  * a term may belong to some countries only:  "Ley 4/2023" [only: es]
    (10 October 2026, X1/X2). A shared language list (Spanish for eighteen
    countries, Portuguese for Brazil and Portugal) carries statute numbers,
    national bodies and spelling variants that are one country's own; the
    tag keeps them out of every other country's matching. The loader drops
    a tagged term unless the collector names one of its countries.
  * an addendum may extend another master:  **Extends:** qc
    on its own line near the top. The generated file is the base master's
    areas and exclusions with the addendum's terms appended, so France,
    Belgium and Switzerland get Quebec's French plus their own words without
    one character of taxonomy-qc.yaml changing.
  * - **Notes:** lines become YAML comments (the loader ignores prose)
  * global exclusions:                   - **Terms:** termination; conversion
  * version from the header line:        **Version 0.2 | ...**
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, "docs", "keyword-taxonomy.md")
CONFIG = os.path.join(ROOT, "config", "taxonomy.yaml")

HEADING = re.compile(r"^### \d+\. (?P<title>.+?) \{#(?P<key>[a-z0-9_]+)\}\s*$")
TIER = re.compile(r"^- \*\*Tier (?P<tier>[12]):\*\* (?P<terms>.+)$")
NOTES = re.compile(r"^- \*\*Notes:\*\* (?P<note>.+)$")
# An OPTIONAL display-label override. Deliberately opt-in rather than taken
# from every heading: intel.area_names() otherwise derives the label from the
# yaml key, and make_5ca.py builds its CSV FILENAMES from that label, so
# relabelling an area renames its sheets. Ten areas are happy with the derived
# label and must not move; area 7 needs a comma its key cannot hold.
NAME = re.compile(r"^- \*\*Name:\*\* (?P<name>.+)$")
EXCLUSIONS = re.compile(r"^- \*\*Terms:\*\* (?P<terms>.+)$")
VERSION = re.compile(r"\*\*Version (?P<version>[0-9.]+)")
EXTENDS = re.compile(r"^\*\*Extends:\*\* (?P<base>[a-z]+)\s*$")


def split_terms(line):
    """Split a semicolon-separated term line, preserving quotes."""
    return [t.strip() for t in line.split(";") if t.strip()]


def parse_master(text):
    version, exclusions = None, []
    areas = {}  # key -> {"tier1": [...], "tier2": [...], "note": str|None}
    current = None
    in_exclusions = False

    for line in text.splitlines():
        if version is None:
            m = VERSION.search(line)
            if m:
                version = m.group("version")
        if line.startswith("## Global exclusions"):
            in_exclusions = True
            current = None
            continue
        if line.startswith("## ") and not line.startswith("## Global"):
            in_exclusions = False
        m = HEADING.match(line)
        if m:
            current = m.group("key")
            areas[current] = {"name": None, "tier1": [], "tier2": [],
                              "note": None}
            in_exclusions = False
            continue
        if in_exclusions:
            m = EXCLUSIONS.match(line)
            if m:
                exclusions = split_terms(m.group("terms"))
            continue
        if current:
            m = TIER.match(line)
            if m:
                areas[current]["tier" + m.group("tier")] = split_terms(m.group("terms"))
                continue
            m = NAME.match(line)
            if m:
                areas[current]["name"] = m.group("name").strip()
                continue
            m = NOTES.match(line)
            if m:
                areas[current]["note"] = m.group("note").strip()
    if not version or not areas or not exclusions:
        raise SystemExit("keyword-taxonomy.md did not parse: version=%r areas=%d exclusions=%d"
                         % (version, len(areas), len(exclusions)))
    return version, areas, exclusions


GUARD = re.compile(r'\s*\[(?P<kind>with|without|only):\s*(?P<terms>[^\]]+)\]\s*$')


def _split_guarded(term):
    """('term', [with...], [without...]) for `"buffer zone*" [with: clinic*, abortion]`.

    Brackets are peeled from the right, so `x [with: a] [without: b]` gives
    both lists; a bracket kind given twice is a master error, not a merge.
    """
    term, guards, vetoes, _only = _split_tagged(term)
    return term, guards, vetoes


def _split_tagged(term):
    """_split_guarded plus the [only: ...] country tag (10 October 2026)."""
    lists = {"with": None, "without": None, "only": None}
    while True:
        m = GUARD.search(term)
        if not m:
            break
        kind = m.group("kind")
        if lists[kind] is not None:
            raise SystemExit("term %r has two [%s:] brackets" % (term, kind))
        lists[kind] = [g.strip() for g in m.group("terms").split(",") if g.strip()]
        term = term[:m.start()]
    return (term.strip(), lists["with"] or [], lists["without"] or [],
            [c.lower() for c in (lists["only"] or [])])


def _yaml_term(term):
    """Serialise one term for a YAML flow list.

    Terms already carrying double quotes keep them (phrase markers); bare
    terms are emitted bare unless YAML would misread them. A guarded term
    becomes a mapping, which is what the filter reads to require company.
    """
    bare, guards, vetoes, only = _split_tagged(term)
    if guards or vetoes or only:
        parts = ["term: " + _yaml_term(bare)]
        if guards:
            parts.append("with: [%s]" % ", ".join(_yaml_term(g) for g in guards))
        if vetoes:
            parts.append("without: [%s]" % ", ".join(_yaml_term(g) for g in vetoes))
        if only:
            parts.append("only: [%s]" % ", ".join(only))
        return "{%s}" % ", ".join(parts)
    term = bare
    if term.startswith('"') and term.endswith('"'):
        return term
    # A bare term YAML would read as something other than a string: a law
    # number ("27.610", "2010") is a float or an int, "no" and "si" can be
    # booleans to some loaders. Quoted, it stays the text it is.
    if re.fullmatch(r"[-+0-9.,_/ :eE]+|(?i:y|n|yes|no|on|off|true|false|null|~)", term):
        return '"' + term + '"'
    if re.search(r"[:#\[\]{},&*!|>'\"%@`]", term) or term != term.strip():
        return '"' + term.replace('"', '\\"') + '"'
    return term


def emit_yaml(version, areas, exclusions, master=None, lang="en"):
    # The header NAMES ITS OWN MASTER (22 September 2026). It used to hardcode
    # the English pair, so the first generated German file told the next reader
    # to edit docs/keyword-taxonomy.md and run a command that would overwrite
    # the English yaml instead. A generated file's header is the only
    # instruction most people will read.
    source = os.path.relpath(master or MASTER, ROOT)
    regen = "python3 tools/generate_taxonomy.py"
    if lang != "en":
        regen += " --lang " + lang
    lines = [
        "# GENERATED FILE - do not hand-edit (handoff section 6 / CLAUDE.md).",
        "# Source of truth: {0}".format(source),
        "# Regenerate: {0}".format(regen),
        "version: {0}".format(version),
        "areas:",
    ]
    for key, spec in areas.items():
        lines.append("  {0}:".format(key))
        if spec.get("name"):
            lines.append("    name: {0}".format(_yaml_term(spec["name"])))
        for tier in ("tier1", "tier2"):
            terms = ", ".join(_yaml_term(t) for t in spec[tier])
            lines.append("    {0}: [{1}]".format(tier, terms))
        if spec["note"]:
            lines.append("    # note: {0}".format(spec["note"]))
    lines.append("exclusions_global: [{0}]".format(
        ", ".join(_yaml_term(t) for t in exclusions)))
    lines.append("")
    return "\n".join(lines)


# A SECOND LANGUAGE GETS ITS OWN PAIR (22 September 2026). German terms
# cannot share the English yaml: matching is substring-based and the two
# languages collide inside each other's words -- "Rat" (council) hides in
# "corporate", "Tat" in "state", "Amt" in "Parliament". The areas and their
# keys are identical, because they are CitizenGO's positions rather than any
# one country's vocabulary; only the terms differ.
MASTERS = {
    "en": (MASTER, CONFIG),
    "de": (os.path.join(ROOT, "docs", "keyword-taxonomy-de.md"),
           os.path.join(ROOT, "config", "taxonomy-de.yaml")),
    # Quebec French (2 October 2026), for the Assemblee nationale collector
    # (src/ingest/prov_qc.py). "qc", not "fr": the terms are measured against
    # Quebec's own legislative French ("aide medicale a mourir", "grossesse
    # pour autrui", "laicite de l'Etat"), which is not the vocabulary of the
    # French Republic or of Brussels, and a France or EU French layer would
    # be a different file.
    "qc": (os.path.join(ROOT, "docs", "keyword-taxonomy-qc.md"),
           os.path.join(ROOT, "config", "taxonomy-qc.yaml")),
}

# The country editions of 10 October 2026 (docs/country-decisions-2026-10-10.md,
# X1, X2, X4). One file per LANGUAGE, not per country: "es" serves the
# eighteen Spanish-speaking parliaments and "pt" Brazil and Portugal, with
# country-only terms tagged [only: ...]; "nl" serves the Netherlands and
# Flanders. "fr" and "atch" are ADDENDA (**Extends:**): Quebec's French plus
# the words of France, Belgium and Switzerland, and Germany's German plus
# Austria's and Switzerland's, so taxonomy-qc.yaml and taxonomy-de.yaml, and
# with them Quebec and the Bundestag, are untouched.
for _lang in ("es", "pt", "it", "nl", "pl", "hr", "sk", "hu", "fr", "atch"):
    MASTERS[_lang] = (os.path.join(ROOT, "docs", "keyword-taxonomy-%s.md" % _lang),
                      os.path.join(ROOT, "config", "taxonomy-%s.yaml" % _lang))


def _base_of(text):
    for line in text.splitlines()[:40]:
        m = EXTENDS.match(line.strip())
        if m:
            return m.group("base")
    return None


def _merge_addendum(base, addendum):
    """The base master's (version, areas, exclusions) with the addendum's
    terms appended area by area, duplicates dropped. The addendum's version
    and notes win; an area the addendum leaves out keeps the base's terms."""
    _bv, base_areas, base_excl = base
    version, add_areas, add_excl = addendum
    areas = {}
    for key, spec in base_areas.items():
        merged = {"name": spec.get("name"), "note": spec.get("note"),
                  "tier1": list(spec["tier1"]), "tier2": list(spec["tier2"])}
        extra = add_areas.get(key)
        if extra:
            for tier in ("tier1", "tier2"):
                for t in extra[tier]:
                    if t not in merged[tier]:
                        merged[tier].append(t)
            if extra.get("note"):
                merged["note"] = extra["note"]
            if extra.get("name"):
                merged["name"] = extra["name"]
        areas[key] = merged
    for key in add_areas:
        if key not in areas:
            raise SystemExit("addendum area %r is not in its base master" % key)
    exclusions = list(base_excl) + [e for e in add_excl if e not in base_excl]
    return version, areas, exclusions


def generate(master=None, lang="en"):
    with open(master or MASTER, "r", encoding="utf-8") as handle:
        text = handle.read()
    parsed = parse_master(text)
    base = _base_of(text)
    if base:
        if base not in MASTERS or base == lang:
            raise SystemExit("unknown base master %r" % base)
        with open(MASTERS[base][0], "r", encoding="utf-8") as handle:
            parsed = _merge_addendum(parse_master(handle.read()), parsed)
    return emit_yaml(*parsed, master=master or MASTER, lang=lang)


def main():
    lang = "en"
    if "--lang" in sys.argv:
        lang = sys.argv[sys.argv.index("--lang") + 1]
    if lang not in MASTERS:
        print("unknown --lang {0}; one of {1}".format(lang, ", ".join(sorted(MASTERS))))
        return 1
    master, config = MASTERS[lang]
    if not os.path.exists(master):
        print("no master for --lang {0} at {1}".format(lang, master))
        return 1
    output = generate(master, lang)
    if "--check" in sys.argv:
        with open(config, "r", encoding="utf-8") as handle:
            current = handle.read()
        if current != output:
            print("{0} is OUT OF SYNC with {1}".format(
                os.path.basename(config), os.path.basename(master)))
            print("regenerate with: python3 tools/generate_taxonomy.py --lang " + lang)
            return 1
        print("{0} in sync".format(os.path.basename(config)))
        return 0
    with open(config, "w", encoding="utf-8") as handle:
        handle.write(output)
    print("wrote {0}".format(config))
    return 0


if __name__ == "__main__":
    sys.exit(main())
