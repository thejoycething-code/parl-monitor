"""What the US, Irish and Australian 5CA sheets share: readings, placement, the
sheet, and the sign-off guide.

tools/us_5ca.py, tools/ie_5ca.py and tools/au_5ca.py each gather their own
evidence (the stores differ) and hand rows to this module. The rule is the one
tools/ca_5ca.py and tools/prov_5ca.py follow, unchanged:

  * The direction of a division -- which lobby is CitizenGO's -- is a SIGNED
    HUMAN JUDGEMENT, written in config/<cc>_stance.yaml. No tool infers it (the
    Lords inversion; a motion to table an amendment; a government counter-text
    that puts Aontu and the Social Democrats in one lobby).
  * Every entry Claude drafts carries `draft: true`, and a draft places NOBODY.
    Signing is deleting that line (by hand, or with `--sign-from-doc` after
    ticking the box in docs/5ca-<cc>-readings.md). Until something is signed,
    every column is 0 and the sheet says, in its own last row, that no reading
    is signed: an evidence list, not a judgement.
  * Here `draft` outranks `placeable: false`: a drafted "evidence only" call is
    still Claude's, so it counts as unsigned in every tally until signed.

Entries use `yea:` / `nay:` for the two lobbies whatever the chamber calls them
(Yea/Nay in Congress; Ta/Nil, stored Yes/No, in the Oireachtas; Aye/No in
Canberra), on the stance scale -2..2, with `why_yea:` / `why_nay:`. A bill entry
uses `sponsored:` and, in the US, `cosponsored:`.
"""

from __future__ import annotations

import csv
import datetime
import os
import re

from src import stance

COLUMNS = stance.COLUMNS
HEADER = ["Decision-Maker", "++", "+", "0", "-", "--", "Target (Y/N)",
          "Based on", "Confidence", "Evidence items", "Profile", "Comments", "Party", "Where"]
VALUE_KEYS = ("yea", "nay", "sponsored", "cosponsored")


def load_stance(path, section="divisions"):
    """{key: entry} for one section of a stance file, drafts included."""
    import yaml
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    out = {}
    for e in cfg.get(section) or []:
        if e.get("key"):
            if True in e:                  # YAML 1.1 reads a bare `on:` key as True
                e = dict(e)
                e.setdefault("on", e.pop(True))
            out[str(e["key"])] = e
    return out


def status(entry):
    """'none', 'draft', 'unplaceable', 'unread' or 'confirmed'.

    Draft first: an unsigned call, even "evidence only", is still unsigned.
    Unread before confirmed: an entry with no values has nothing to apply
    even once its draft line is gone.

    ADDED 10 October 2026 (src/country5ca.py, the new country editions): an
    entry with a `status:` field is read by it. `needs_reading` is unread,
    `draft` is a draft, and `confirmed` counts only with both `confirmed_by`
    (a named person) and `confirmed_on` (a date); without them it stays a
    draft. Entries without `status:` (every older stance file) read exactly
    as before."""
    if not entry:
        return "none"
    st = entry.get("status")
    if st is not None:
        if st == "needs_reading":
            return "unread"
        if st != "confirmed" or not (entry.get("confirmed_by") and entry.get("confirmed_on")):
            return "draft"
    if entry.get("draft"):
        return "draft"
    if entry.get("placeable") is False:
        return "unplaceable"
    if all(entry.get(k) is None for k in VALUE_KEYS):
        return "unread"
    return "confirmed"


NOT_PLACED = {"draft": "reading DRAFT, unsigned -- not placed",
              "confirmed": "this side carries no value -- its lobby tells no member apart",
              "unplaceable": "never places: {reason}",
              "unread": "not read yet -- not placed",
              "none": "no reading -- not placed"}


def not_placed(entry):
    return NOT_PLACED[status(entry)].format(reason=(entry or {}).get("reason") or "")


def value(entry, side):
    """(stance, why) for one side of a SIGNED entry, else (None, None)."""
    if status(entry) != "confirmed":
        return None, None
    return entry.get(side), entry.get("why_" + side)


def place(scored, weights):
    """(column, conflict, decided): most directional act, then the stronger kind
    of evidence, then the most recent. Never averaged; mixed signs flagged."""
    real = [s for s in scored if s[0] is not None]
    if not real:
        return "0", False, None
    best = max(real, key=lambda s: (abs(s[0] or 0), weights.get(s[3], 0), s[1] or ""))
    signs = {(1 if s[0] > 0 else -1) for s in real if s[0]}
    return stance.stance_to_column(best[0]), len(signs) > 1, best


def decisive(divisions, entries):
    """The divisions whose SIGNED reading scores our side +2 -- the only ones
    the absence rule may cap against."""
    out = []
    for d in divisions:
        e = entries.get(d["division_key"])
        if status(e) == "confirmed" and max(e.get("yea") or 0, e.get("nay") or 0) >= 2:
            out.append(d)
    return out


_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def line_date(line):
    hit = _DATE.search(line)
    return hit.group(0) if hit else ""


def clip(text, n):
    return " ".join((text or "").split())[:n]


def finish_row(pid, lines, scored, weights, name, party, where, sitting, cap_note=None,
               today=None):
    """One sheet row from a member's evidence. cap_note, when given, is the
    absence rule's reason: a ++ becomes + with it at the head of Comments."""
    column, conflict, decided = place(scored, weights)
    comments = sorted(lines, key=line_date, reverse=True)
    capped = False
    if column == "++" and cap_note:
        column, capped = "+", True
        comments.insert(0, cap_note)
    if conflict:
        comments.insert(0, "MIXED RECORD: directional evidence on both sides -- read the acts, "
                           "not the column")
    if decided:
        kind = {"vote": "vote", "sponsored": "a bill sponsored",
                "cosponsored": "a bill cosponsored"}.get(decided[3], decided[3])
        based = stance.based_on(kind, decided[1][:10] or today)
        confidence = {"vote": "strong (recorded vote, signed reading)",
                      "sponsored": "moderate (bill sponsored, signed reading)",
                      "cosponsored": "moderate (bill cosponsored, signed reading)"}.get(
                          decided[3], "signed reading")
    elif lines:
        based, confidence = "no signed reading", "n/a (evidence only)"
    else:
        based, confidence, comments = "no evidence", "", ["No recorded activity on this area"]
    return {"person_id": pid, "column": column, "conflict": conflict, "capped": capped,
            "decision_maker": "{0} ({1}){2}{3}".format(
                name or pid, party or "?", " - " + where if where else "",
                "" if sitting else " [FORMER]"),
            "n_events": len(lines), "based_on": based, "confidence": confidence,
            "comments": comments, "party": party or "", "where": where or "",
            "sitting": bool(sitting)}


def sort_rows(rows):
    order = {c: i for i, c in enumerate(COLUMNS)}
    rows.sort(key=lambda x: (order[x["column"]], not x["sitting"], -x["n_events"],
                             x["decision_maker"]))
    return rows


def readings_line(signed, unsigned, area_name):
    """The plain statement the sheet ends with. With nothing signed it says the
    columns are blank by design, so a 0 is never read as a judgement."""
    if not signed:
        return ("NO SIGNED READINGS for {0}: {1} drafted, 0 signed. No member is placed; every "
                "row sits at 0 and the sheet is an evidence list. Sign readings in "
                "the sign-off guide to fill the columns.".format(area_name, unsigned))
    return ("Readings for {0}: {1} signed, {2} unsigned. Only signed readings place anyone; "
            "unsigned divisions appear in Comments as evidence.".format(area_name, signed, unsigned))


def write_sheet(path, rows, footer):
    """Write the sheet. Totals count SITTING members only (a former member who
    voted is listed and labelled, not counted). The last row is `footer`."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tally = {c: 0 for c in COLUMNS}
    sitting = sum(1 for r in rows if r["sitting"])
    with open(path, "w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        w.writerow(HEADER)
        for r in rows:
            if r["sitting"]:
                tally[r["column"]] += 1
            w.writerow([r["decision_maker"], *("1" if r["column"] == c else "" for c in COLUMNS),
                        "", r["based_on"], r["confidence"], r["n_events"], "",
                        " | ".join(r["comments"]), r["party"], r["where"]])
        w.writerow(["Totals - {0} sitting decision-makers ({1} former listed, not counted)".format(
                        sitting, len(rows) - sitting),
                    *(tally[c] for c in COLUMNS), "", "", "", "", "", "", "", ""])
        w.writerow([footer] + [""] * (len(HEADER) - 1))
    return tally


def area_counts(divisions, entries):
    """(signed, unsigned) readings among one sheet's divisions. Signed means a
    human's call stands (confirmed or never-placeable); unsigned is a draft or
    an unread entry. A division with no entry at all counts as neither."""
    signed = unsigned = 0
    for d in divisions:
        st = status(entries.get(d["division_key"]))
        if st in ("confirmed", "unplaceable"):
            signed += 1
        elif st in ("draft", "unread"):
            unsigned += 1
    return signed, unsigned


def file_counts(*sections):
    every = [e for s in sections for e in s.values()]
    return {k: sum(1 for e in every if status(e) == k)
            for k in ("confirmed", "draft", "unread", "unplaceable")}


def slug(name):
    return name.lower().replace(" ", "-").replace(",", "")


def excluded_areas(root):
    import yaml
    with open(os.path.join(root, "config", "stance_overrides.yaml"), encoding="utf-8") as h:
        return {int(a) for a in (yaml.safe_load(h) or {}).get("excluded_from_5ca") or []}


# --- the sign-off guide --------------------------------------------------------

def _fmt(v):
    return "no value" if v is None else "{0:+d}".format(v)


def signoff_markdown(title, intro, labels, entries, bill_entries, stance_rel):
    """docs/5ca-<cc>-readings.md: every entry, one checkbox each.

    labels: {'yea': 'Yea', 'nay': 'Nay'} as the chamber says it. Ticking a box
    and running `--sign-from-doc` deletes that entry's `draft: true`; an entry
    already signed prints ticked."""
    out = ["# {0}".format(title), "", intro.strip(), "",
           "**How to sign.** Tick `[x]` on each reading you accept as drafted, then run "
           "the tool with `--sign-from-doc` (it deletes those entries' `draft: true` lines in "
           "`{0}` and stamps `signed:`). To change a value, edit `{0}` first and leave the box "
           "empty; to strike a reading, write `placeable: false` and a `reason:`. Nothing "
           "unticked places anyone.".format(stance_rel), ""]
    groups = [("Divisions", entries), ("Bills (sponsorship)", bill_entries)]
    n = 0
    for heading, section in groups:
        if not section:
            continue
        out += ["## {0}".format(heading), ""]
        for key, e in section.items():
            n += 1
            st = status(e)
            box = "[ ]" if st in ("draft", "unread") else "[x]"
            out.append("### {0} `{1}` {2}".format(box, key, e.get("title") or ""))
            out.append("")
            meta = [x for x in (e.get("dated"), e.get("result"), e.get("chamber_label")) if x]
            if meta:
                out.append("- **When / result:** " + "; ".join(str(m) for m in meta))
            if e.get("motion"):
                out.append("- **Motion:** " + clip(e["motion"], 900))
            if e.get("aye_means"):
                out.append("- **A {0} means:** {1}".format(labels["yea"], clip(e["aye_means"], 600)))
            if e.get("lobbies"):
                out.append("- **Lobbies:** " + clip(e["lobbies"], 400))
            if e.get("tellers"):
                out.append("- **Tellers:** " + clip(re.sub(r"^Tellers:\s*", "", e["tellers"]), 200))
            if all(e.get(k) is None for k in VALUE_KEYS) and e.get("placeable") is not False:
                out.append("- **Proposed direction:** none -- " + clip(e.get("read_first") or
                                                                      "not read yet", 400))
            elif e.get("placeable") is False:
                out.append("- **Proposed direction:** evidence only, never places -- "
                           + clip(e.get("reason"), 500))
            elif heading.startswith("Bills"):
                parts = []
                if "sponsored" in e:
                    parts.append("sponsor {0} ({1})".format(_fmt(e.get("sponsored")),
                                                           clip(e.get("why_sponsored"), 200)))
                if "cosponsored" in e:
                    parts.append("cosponsor {0} ({1})".format(_fmt(e.get("cosponsored")),
                                                             clip(e.get("why_cosponsored"), 200)))
                out.append("- **Proposed direction:** " + "; ".join(parts))
            else:
                out.append("- **Proposed direction:** {0} {1} ({2}); {3} {4} ({5})".format(
                    labels["yea"], _fmt(e.get("yea")), clip(e.get("why_yea"), 250) or "-",
                    labels["nay"], _fmt(e.get("nay")), clip(e.get("why_nay"), 250) or "-"))
            if e.get("flag"):
                out.append("- **Flag for you:** " + clip(e["flag"], 500))
            if e.get("signed"):
                out.append("- **Signed:** {0}".format(e["signed"]))
            out.append("")
    out.append("{0} entries.".format(n))
    return "\n".join(out) + "\n"


_TICK = re.compile(r"^###\s*\[([ xX])\]\s*`([^`]+)`", re.M)


def ticked_keys(doc_text):
    return [k for mark, k in _TICK.findall(doc_text) if mark.lower() == "x"]


def sign_keys(yaml_text, keys, stamp):
    """Delete `draft: true` from the entries with these keys and add `signed:`.

    A text edit, not a YAML round trip: the stance files are commented by hand
    and a dump would throw every comment away. Returns (new_text, signed)."""
    lines = yaml_text.splitlines(keepends=True)
    out, signed, current, indent = [], [], None, None
    key_re = re.compile(r"^(\s*)-\s+key:\s*['\"]?([^'\"\n#]+?)['\"]?\s*(#.*)?$")
    for line in lines:
        m = key_re.match(line.rstrip("\n"))
        if m:
            current = m.group(2).strip() if m.group(2).strip() in keys else None
            indent = len(m.group(1)) + 2
        if current and re.match(r"^\s*draft:\s*true\s*(#.*)?$", line):
            out.append(" " * indent + "signed: \"{0}\"\n".format(stamp))
            signed.append(current)
            current = None
            continue
        out.append(line)
    return "".join(out), signed


def sign_from_doc(stance_path, doc_path, today=None, log=print):
    today = today or datetime.date.today().isoformat()
    with open(doc_path, encoding="utf-8") as h:
        keys = set(ticked_keys(h.read()))
    with open(stance_path, encoding="utf-8") as h:
        text = h.read()
    new, signed = sign_keys(text, keys, "{0}, ticked in {1}".format(
        today, os.path.basename(doc_path)))
    if signed:
        with open(stance_path, "w", encoding="utf-8") as h:
            h.write(new)
    log("signed {0} reading(s) from {1}: {2}".format(len(signed), doc_path,
                                                      ", ".join(signed) or "none"))
    return signed
