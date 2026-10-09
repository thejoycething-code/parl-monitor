"""The EU 5CA's readings: status, the sign-off guide, and signing from it.

config/eu_divisions.yaml is a MAPPING keyed by decision-event id with
`our_side` / `meaning_favor` / `meaning_against` / `signed_off`, the shape
the tracker, the edition and the queue have read since 1 September 2026. The
US, Irish and Australian stance files are lists with `yea:` / `nay:` values,
so src/readings5ca.py's guide and signer do not fit it as they stand; this
module is their EU counterpart and reuses the parts that do fit (the
checkbox format and its parser, the clipping).

The rule is the same everywhere: a division's direction is a SIGNED human
judgement. A draft (`draft: true`, `signed_off: false`) places no MEP. A
draft with no direction (`read_first:`) cannot be signed from the guide:
there is nothing to sign until someone writes `our_side` or
`placeable: false`.
"""

from __future__ import annotations

import datetime
import os
import re

from src import readings5ca as r5

NOTE = "  # Christopher, {0}, ticked in {1}"


def load(path):
    import yaml
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        return (yaml.safe_load(handle) or {}).get("divisions") or {}


def status(entry):
    """'confirmed' (signed, places), 'unplaceable' (signed, evidence only),
    'draft' (a proposal, unsigned), 'unread' (no direction, unsigned)."""
    if entry.get("signed_off"):
        return "confirmed" if entry.get("our_side") else "unplaceable"
    if entry.get("our_side") or entry.get("placeable") is False:
        return "draft"
    return "unread"


def counts(entries):
    out = {k: 0 for k in ("confirmed", "unplaceable", "draft", "unread")}
    for e in entries.values():
        out[status(e)] += 1
    return out


def proposal(entry):
    if entry.get("our_side"):
        return "dir"
    if entry.get("placeable") is False:
        return "evid"
    return "none"


def _family(key, entry):
    short = entry.get("short") or key
    return str(entry.get("date") or "")[:10], short.split(":")[0]


INTRO = """Every unsigned reading below was DRAFTED by Claude on 9 October 2026 from
the store (eu_divisions, eu_votes, eu_meps) and the adopted texts, read in
full. None is signed, so `tools/make_eu_5ca.py` places nobody on them: the
EU 5CA still rests on the signed divisions only. The direction of a vote is
your judgement, never the tool's.

Three kinds of draft. **Proposed side**: our side favour or against, with the
two meaning lines and a confidence. **Evidence only**: never places anyone
(no name lists, near-unanimous, a split part without the contested words,
words not on our ground, migration); ticking it accepts that. **No
direction**: the amendment's words are not in the store, or the call is
yours; these cannot be ticked into force. Write `our_side` (favor/against)
and both meaning lines in `config/eu_divisions.yaml` first, or
`placeable: false` with a `reason:`.

Lobbies are favour-against-abstention by each MEP's current group."""


def signoff_markdown(entries, title="European Parliament 5CA: readings to sign",
                     intro=INTRO, config_rel="config/eu_divisions.yaml"):
    """docs/5ca-eu-readings.md: every division, one checkbox each, grouped by
    report, proposed sides first. A signed entry prints ticked."""
    c = counts(entries)
    fams = {}
    for key, e in entries.items():
        fams.setdefault(_family(key, e), []).append((key, e))
    # The hand-signed entries name their report in their own words ("Nigeria",
    # "SDG resolution (2026 ...)"); fold each into the report of the same
    # sitting whose name starts with the same word, under the commonest name.
    merged = {}
    for (date, name), items in sorted(fams.items(), key=lambda kv: -len(kv[1])):
        word = name.split()[0].lower() if name.split() else ""
        home = next((k for k in merged if k[0] == date and k[1].split()[0].lower() == word),
                    None)
        merged.setdefault(home or (date, name), []).extend(items)
    fams = merged
    out = ["# {0}".format(title), "", intro.strip(), "",
           "**How to sign.** Tick `[x]` on each reading you accept as drafted, then run "
           "`python3 tools/make_eu_5ca.py --sign-from-doc`. It deletes those entries' "
           "`draft: true` lines in `{0}` and sets `signed_off: true` with a dated note. To "
           "change a side or a meaning, edit `{0}` first and leave the box empty. Nothing "
           "unticked places anyone.".format(config_rel), "",
           "**Where it stands:** {confirmed} signed and placing, {unplaceable} signed evidence-only, "
           "{draft} drafted and unsigned, {unread} with no direction yet.".format(**c), "",
           "| Report | Sitting | Proposed side | No direction | Evidence only | Signed |",
           "|---|---|---|---|---|---|"]
    order = sorted(fams, key=lambda k: (k[0], k[1]))
    for fam in order:
        items = fams[fam]
        unsigned = [e for _k, e in items if not e.get("signed_off")]
        n = {p: sum(1 for e in unsigned if proposal(e) == p) for p in ("dir", "none", "evid")}
        out.append("| {0} | {1} | {2} | {3} | {4} | {5} |".format(
            fam[1], fam[0], n["dir"], n["none"], n["evid"], len(items) - len(unsigned)))
    out.append("")
    rank = {"dir": 0, "none": 1, "evid": 2}
    for fam in order:
        items = sorted(fams[fam], key=lambda ke: (not ke[1].get("signed_off"),
                                                  rank[proposal(ke[1])], ke[0]))
        out += ["## {0} ({1})".format(fam[1], fam[0]), ""]
        for key, e in items:
            st = status(e)
            box = "[x]" if st in ("confirmed", "unplaceable") else "[ ]"
            short = (e.get("short") or key).split(":", 1)[-1].strip()
            out.append("### {0} `{1}` {2}".format(box, key, short))
            out.append("")
            if e.get("result"):
                out.append("- **Result:** {0}".format(e["result"]))
            if e.get("favor_means"):
                out.append("- **A favour vote means:** " + r5.clip(e["favor_means"], 500))
            if e.get("text_voted"):
                out.append("- **Text:** " + r5.clip(e["text_voted"], 700))
            if e.get("lobbies"):
                out.append("- **Lobbies:** " + r5.clip(e["lobbies"].replace(
                    "favour-against-abstention by MEP's current group: ", ""), 300))
            if st in ("confirmed", "unplaceable") and not e.get("draft"):
                if e.get("our_side"):
                    out.append("- **Signed side:** {0}".format(e["our_side"]))
                else:
                    out.append("- **Signed:** no side, evidence only")
            elif e.get("our_side"):
                out.append("- **Proposed side:** {0} ({1} confidence)".format(
                    e["our_side"].upper(), e.get("confidence") or "?"))
                out.append("  - favour: " + r5.clip(e.get("meaning_favor"), 400))
                out.append("  - against: " + r5.clip(e.get("meaning_against"), 400))
            elif e.get("placeable") is False:
                out.append("- **Proposed:** evidence only, never places -- " + r5.clip(e.get("reason"), 500))
            else:
                out.append("- **Proposed:** no direction -- " + r5.clip(
                    e.get("read_first") or "not read yet", 700))
            if e.get("flag"):
                out.append("- **Flag for you:** " + r5.clip(e["flag"], 600))
            out.append("")
    out.append("{0} divisions.".format(len(entries)))
    return "\n".join(out) + "\n"


_KEY = re.compile(r"^  (MTG-[^:\s]+):\s*$")


def sign_keys(yaml_text, keys, note):
    """Sign these entries in the mapping file's TEXT (comments survive).

    Within each ticked entry's block: the `draft: true` line goes and
    `signed_off: false` becomes `signed_off: true` with `note`. An entry with
    no direction (our_side null and no `placeable: false`) is skipped: a tick
    cannot sign a reading nobody has written. Returns (text, signed, skipped).
    """
    lines = yaml_text.splitlines(keepends=True)
    blocks, start = [], None
    for i, line in enumerate(lines):
        if _KEY.match(line.rstrip("\n")) or (start is not None and re.match(r"^\S", line)):
            if start is not None:
                blocks.append((start, i))
            start = i if _KEY.match(line.rstrip("\n")) else None
    if start is not None:
        blocks.append((start, len(lines)))
    drop, edits, signed, skipped = set(), {}, [], []
    for a, b in blocks:
        key = _KEY.match(lines[a].rstrip("\n")).group(1)
        if key not in keys:
            continue
        body = "".join(lines[a:b])
        if not re.search(r"^    signed_off:\s*false\b", body, re.M):
            continue                                    # already signed
        directional = re.search(r"^    our_side:\s*(favor|against)\b", body, re.M)
        evidence = re.search(r"^    placeable:\s*false\b", body, re.M)
        if not (directional or evidence):
            skipped.append(key)
            continue
        for i in range(a, b):
            if re.match(r"^    draft:\s*true\s*(#.*)?$", lines[i]):
                drop.add(i)
            elif re.match(r"^    signed_off:\s*false\b", lines[i]):
                edits[i] = "    signed_off: true" + note + "\n"
        signed.append(key)
    out = [edits.get(i, line) for i, line in enumerate(lines) if i not in drop]
    return "".join(out), signed, skipped


def sign_from_doc(config_path, doc_path, today=None, log=print):
    today = today or datetime.date.today().isoformat()
    with open(doc_path, encoding="utf-8") as h:
        keys = set(r5.ticked_keys(h.read()))
    with open(config_path, encoding="utf-8") as h:
        text = h.read()
    new, signed, skipped = sign_keys(text, keys, NOTE.format(today, os.path.basename(doc_path)))
    if signed:
        with open(config_path, "w", encoding="utf-8") as h:
            h.write(new)
    log("signed {0} EU reading(s) from {1}: {2}".format(
        len(signed), doc_path, ", ".join(signed) or "none"))
    if skipped:
        log("NOT signed, no direction written yet ({0}): {1}".format(
            len(skipped), ", ".join(skipped)))
    return signed
