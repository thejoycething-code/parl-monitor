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
EXCLUSIONS = re.compile(r"^- \*\*Terms:\*\* (?P<terms>.+)$")
VERSION = re.compile(r"\*\*Version (?P<version>[0-9.]+)")


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
            areas[current] = {"tier1": [], "tier2": [], "note": None}
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
            m = NOTES.match(line)
            if m:
                areas[current]["note"] = m.group("note").strip()
    if not version or not areas or not exclusions:
        raise SystemExit("keyword-taxonomy.md did not parse: version=%r areas=%d exclusions=%d"
                         % (version, len(areas), len(exclusions)))
    return version, areas, exclusions


WITH = re.compile(r'^(?P<term>.+?)\s*\[with:\s*(?P<guards>[^\]]+)\]\s*$')


def _split_guarded(term):
    """('term', ['guard', ...]) for `"buffer zone*" [with: clinic*, abortion]`."""
    m = WITH.match(term)
    if not m:
        return term, []
    guards = [g.strip() for g in m.group("guards").split(",") if g.strip()]
    return m.group("term").strip(), guards


def _yaml_term(term):
    """Serialise one term for a YAML flow list.

    Terms already carrying double quotes keep them (phrase markers); bare
    terms are emitted bare unless YAML would misread them. A guarded term
    becomes a mapping, which is what the filter reads to require company.
    """
    bare, guards = _split_guarded(term)
    if guards:
        return "{{term: {0}, with: [{1}]}}".format(
            _yaml_term(bare), ", ".join(_yaml_term(g) for g in guards))
    term = bare
    if term.startswith('"') and term.endswith('"'):
        return term
    if re.search(r"[:#\[\]{},&*!|>'\"%@`]", term) or term != term.strip():
        return '"' + term.replace('"', '\\"') + '"'
    return term


def emit_yaml(version, areas, exclusions):
    lines = [
        "# GENERATED FILE - do not hand-edit (handoff section 6 / CLAUDE.md).",
        "# Source of truth: docs/keyword-taxonomy.md",
        "# Regenerate: python3 tools/generate_taxonomy.py",
        "version: {0}".format(version),
        "areas:",
    ]
    for key, spec in areas.items():
        lines.append("  {0}:".format(key))
        for tier in ("tier1", "tier2"):
            terms = ", ".join(_yaml_term(t) for t in spec[tier])
            lines.append("    {0}: [{1}]".format(tier, terms))
        if spec["note"]:
            lines.append("    # note: {0}".format(spec["note"]))
    lines.append("exclusions_global: [{0}]".format(
        ", ".join(_yaml_term(t) for t in exclusions)))
    lines.append("")
    return "\n".join(lines)


def generate():
    with open(MASTER, "r", encoding="utf-8") as handle:
        text = handle.read()
    return emit_yaml(*parse_master(text))


def main():
    output = generate()
    if "--check" in sys.argv:
        with open(CONFIG, "r", encoding="utf-8") as handle:
            current = handle.read()
        if current != output:
            print("config/taxonomy.yaml is OUT OF SYNC with docs/keyword-taxonomy.md")
            print("regenerate with: python3 tools/generate_taxonomy.py")
            return 1
        print("taxonomy.yaml in sync")
        return 0
    with open(CONFIG, "w", encoding="utf-8") as handle:
        handle.write(output)
    print("wrote {0}".format(CONFIG))
    return 0


if __name__ == "__main__":
    sys.exit(main())
