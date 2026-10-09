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
  * - **Notes:** lines become YAML comments (the loader ignores prose)
  * an ADDENDUM adds terms to an existing area: a level-four heading with
    the same key,                        #### 1. Abortion {#1_abortion}
    whose Tier lines are APPENDED to that area's lists, never replacing
    them. The American vocabulary (v1.17, 9 October 2026) lives there so
    a reader can see which terms came from which country.
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
ADDENDUM = re.compile(r"^#### \d+\. (?P<title>.+?) \{#(?P<key>[a-z0-9_]+)\}\s*$")
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


def split_terms(line):
    """Split a semicolon-separated term line, preserving quotes."""
    return [t.strip() for t in line.split(";") if t.strip()]


def parse_master(text):
    version, exclusions = None, []
    areas = {}  # key -> {"tier1": [...], "tier2": [...], "note": str|None}
    current = None
    addendum = False
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
            # A new top-level section closes the last area, so prose or a
            # Notes line under an addendum's preamble cannot land on area 13.
            current = None
        m = HEADING.match(line)
        if m:
            current = m.group("key")
            areas[current] = {"name": None, "tier1": [], "tier2": [],
                              "note": None}
            addendum = False
            in_exclusions = False
            continue
        m = ADDENDUM.match(line)
        if m:
            current = m.group("key")
            if current not in areas:
                raise SystemExit("addendum heading %r names no area defined above"
                                 % line.strip())
            addendum = True
            continue
        if in_exclusions:
            m = EXCLUSIONS.match(line)
            if m:
                exclusions = split_terms(m.group("terms"))
            continue
        if current:
            m = TIER.match(line)
            if m:
                tier = "tier" + m.group("tier")
                terms = split_terms(m.group("terms"))
                if addendum:
                    dupes = [t for t in terms if t in areas[current][tier]]
                    if dupes:
                        raise SystemExit("addendum repeats %s terms already in %s: %s"
                                         % (tier, current, dupes))
                    areas[current][tier] = areas[current][tier] + terms
                else:
                    areas[current][tier] = terms
                continue
            m = NAME.match(line)
            if m:
                areas[current]["name"] = m.group("name").strip()
                continue
            m = NOTES.match(line)
            if m:
                note = m.group("note").strip()
                if addendum and areas[current]["note"]:
                    note = areas[current]["note"] + " ADDENDUM: " + note
                areas[current]["note"] = note
    if not version or not areas or not exclusions:
        raise SystemExit("keyword-taxonomy.md did not parse: version=%r areas=%d exclusions=%d"
                         % (version, len(areas), len(exclusions)))
    return version, areas, exclusions


GUARD = re.compile(r'\s*\[(?P<kind>with|without):\s*(?P<terms>[^\]]+)\]\s*$')


def _split_guarded(term):
    """('term', [with...], [without...]) for `"buffer zone*" [with: clinic*, abortion]`.

    Brackets are peeled from the right, so `x [with: a] [without: b]` gives
    both lists; a bracket kind given twice is a master error, not a merge.
    """
    lists = {"with": None, "without": None}
    while True:
        m = GUARD.search(term)
        if not m:
            break
        kind = m.group("kind")
        if lists[kind] is not None:
            raise SystemExit("term %r has two [%s:] brackets" % (term, kind))
        lists[kind] = [g.strip() for g in m.group("terms").split(",") if g.strip()]
        term = term[:m.start()]
    return term.strip(), lists["with"] or [], lists["without"] or []


def _yaml_term(term):
    """Serialise one term for a YAML flow list.

    Terms already carrying double quotes keep them (phrase markers); bare
    terms are emitted bare unless YAML would misread them. A guarded term
    becomes a mapping, which is what the filter reads to require company.
    """
    bare, guards, vetoes = _split_guarded(term)
    if guards or vetoes:
        parts = ["term: " + _yaml_term(bare)]
        if guards:
            parts.append("with: [%s]" % ", ".join(_yaml_term(g) for g in guards))
        if vetoes:
            parts.append("without: [%s]" % ", ".join(_yaml_term(g) for g in vetoes))
        return "{%s}" % ", ".join(parts)
    term = bare
    if term.startswith('"') and term.endswith('"'):
        return term
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


def generate(master=None, lang="en"):
    with open(master or MASTER, "r", encoding="utf-8") as handle:
        text = handle.read()
    return emit_yaml(*parse_master(text), master=master or MASTER, lang=lang)


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
