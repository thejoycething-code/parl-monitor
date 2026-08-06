"""Work through the division candidate queue, then apply your decisions.

    python3 tools/review_divisions.py                 # write the worksheet
    python3 tools/review_divisions.py --area 6        # one area at a time
    python3 tools/review_divisions.py --apply         # fold decisions into config

Same round-trip as the weekly review file: a markdown worksheet you fill in,
then a command that applies it. Candidates are grouped by BILL, because
related divisions share an issue and most of their context -- deciding six
Children's Wellbeing and Schools Bill votes together is one judgement, not six.

For each candidate the worksheet carries what the ledger knows: the areas, how
many speeches in the same debate, a link to the official division record, and
excerpts from those speeches, which is usually where the amendment's substance
is explained. Meaning lines are NOT pre-drafted: a division titled "New Clause
34" gives no clue what the clause did, and inventing one would put a guess in
front of the public.

Leave INCLUDE blank (or write no) to skip a division. Divisions you include
enter config/vote_tracker.yaml with signed_off: false, so they still carry the
pending notice until you have checked the wording against Hansard.
"""

from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel

QUEUE = os.path.join(ROOT, "data", "division-candidates.json")
WORKSHEET = os.path.join(ROOT, "reviews", "division-review.md")
CONFIG = os.path.join(ROOT, "config", "vote_tracker.yaml")

HEADER = """# Division review worksheet

{total} candidates touching a displayable area, grouped by bill and ordered by
weight of same-debate evidence. Migration is excluded: we track it, we do not
show it.

For each division you want on the tracker:

  INCLUDE:      yes
  ISSUE:        an existing issue id, or a new one you also add to the
                `issues:` block of config/vote_tracker.yaml
  SHORT:        the headline for the row, e.g. "Parental duty to register"
  CONTEXT:      smaller sub-title, e.g. the host bill, or leave blank
  LANDMARK:     yes for the defining vote of an issue, else blank
  OUR_SIDE:     aye or no -- which way was CitizenGO's side
  MEANING_AYE:  what voting Aye meant, in plain English
  MEANING_NO:   what voting No meant

Leave INCLUDE blank to skip. Then run:

    python3 tools/review_divisions.py --apply

Nothing published here goes out unchecked: everything applied gets
signed_off: false and the page keeps the pending-sign-off notice.

Existing issue ids: {issues}

---
"""

FIELDS = ("INCLUDE", "ISSUE", "SHORT", "CONTEXT", "LANDMARK", "OUR_SIDE",
          "MEANING_AYE", "MEANING_NO")


def bill_of(title):
    """The bill or subject a division belongs to, for grouping."""
    cut = re.split(r":|\bReport Stage\b|\bCommittee\b|\bThird Reading\b|"
                   r"\bSecond Reading\b", title)[0]
    return " ".join(cut.split()).strip(" -") or title


def load_queue():
    if not os.path.exists(QUEUE):
        print("no candidate queue: run tools/find_division_candidates.py first")
        sys.exit(1)
    with open(QUEUE, encoding="utf-8") as handle:
        return json.load(handle)


def load_config_text():
    with open(CONFIG, encoding="utf-8") as handle:
        return handle.read()


def existing_issue_ids():
    import yaml
    with open(CONFIG, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    return [i["id"] for i in (cfg.get("issues") or [])]


def _flat(text):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", (text or "").lower()).split())


def excerpts_for(conn, date, title, limit=2):
    """Speech excerpts from the same debate: usually where the substance is.

    Longest first: an excerpt that is merely the debate title tells you
    nothing, while the passage that earned the capture explains the clause.
    """
    norm = _flat(bill_of(title))
    if len(norm) < 12:
        return []
    rows = conn.execute(
        "SELECT excerpt, line FROM mp_events WHERE kind='debate' AND date = ? "
        "AND excerpt IS NOT NULL AND excerpt != ''", (date,)).fetchall()
    out = []
    for r in rows:
        # The "(re: term)" annotation must come off, or nothing ever matches.
        debate = _flat(re.sub(r"\s*\(re: [^)]*\)$", "",
                              re.sub(r"^Spoke:\s*", "", r["line"] or "")))
        if debate and (norm in debate or debate in norm):
            out.append(" ".join((r["excerpt"] or "").split()))
    out.sort(key=len, reverse=True)
    return out[:limit]


def write_worksheet(area_filter=None):
    queue = load_queue()
    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    rows = [c for c in queue["candidates"]
            if not c["in_ledger"] and not c["hidden_only"]]
    if area_filter:
        rows = [c for c in rows if area_filter in c["areas"]]

    groups = {}
    for c in rows:
        groups.setdefault(bill_of(c["title"]), []).append(c)
    # General debates -- King's/Queen's Speech, opposition days, programme and
    # money motions -- surface because our issues came up in a wide-ranging
    # debate, not because the House voted on them. Sorted to the bottom and
    # labelled, rather than removed: the judgement stays yours.
    def is_general(bill):
        low = bill.lower()
        return any(p in low for p in ("speech", "opposition day", "address",
                                      "programme motion", ": money", "business of the house"))

    ordered = sorted(groups.items(),
                     key=lambda kv: (is_general(kv[0]),
                                     -max(sum(c["day_areas"].values()) for c in kv[1])))

    blocks = [HEADER.format(total=len(rows), issues=", ".join(existing_issue_ids()))]
    for bill, items in ordered:
        items.sort(key=lambda c: c["date"])
        area_tally = {}
        for c in items:
            # JSON object keys are strings; area names are keyed by int.
            for a, n in c["day_areas"].items():
                key = int(a)
                area_tally[key] = max(area_tally.get(key, 0), n)
        blocks.append("## {0}  ({1} division{2}){3}".format(
            bill, len(items), "" if len(items) == 1 else "s",
            "  -- GENERAL DEBATE: our issues were discussed, but the House was "
            "not voting on them. Likely skip." if is_general(bill) else ""))
        blocks.append("*Areas in this debate: {0}*".format(", ".join(
            "{0} ({1} speeches)".format(names.get(a, a), n)
            for a, n in sorted(area_tally.items(), key=lambda kv: -kv[1])) or "title match only"))
        ex = excerpts_for(conn, items[0]["date"], items[0]["title"])
        for e in ex:
            blocks.append("> {0}".format(e[:300]))
        blocks.append("")
        for c in items:
            blocks.append("### division: {0}".format(c["id"]))
            blocks.append("- {0} | {1}".format(c["date"], c["title"]))
            blocks.append("- record: https://votes.parliament.uk/Votes/Commons/Division/{0}"
                          .format(c["id"]))
            for field in FIELDS:
                blocks.append("{0}: ".format(field))
            blocks.append("")

    os.makedirs(os.path.dirname(WORKSHEET), exist_ok=True)
    with open(WORKSHEET, "w", encoding="utf-8") as handle:
        handle.write("\n".join(blocks))
    conn.close()
    print("{0} candidates across {1} bills -> {2}".format(
        len(rows), len(groups), WORKSHEET))
    for bill, items in ordered[:8]:
        print("   {0:58} {1}".format(bill[:58], len(items)))


def parse_worksheet():
    with open(WORKSHEET, encoding="utf-8") as handle:
        text = handle.read()
    out, current = [], None
    for line in text.splitlines():
        m = re.match(r"### division: (\d+)", line)
        if m:
            current = {"id": int(m.group(1))}
            out.append(current)
            continue
        if current is None:
            continue
        m = re.match(r"({0}): ?(.*)$".format("|".join(FIELDS)), line)
        if m:
            current[m.group(1)] = m.group(2).strip()
    return [c for c in out if (c.get("INCLUDE") or "").lower() in ("y", "yes", "true")]


def apply_worksheet():
    if not os.path.exists(WORKSHEET):
        print("no worksheet at {0}: generate it first".format(WORKSHEET))
        return 1
    chosen = parse_worksheet()
    if not chosen:
        print("nothing marked INCLUDE: yes -- nothing to apply")
        return 0
    missing = [c["id"] for c in chosen
               if not (c.get("ISSUE") and c.get("SHORT")
                       and c.get("MEANING_AYE") and c.get("MEANING_NO"))]
    if missing:
        print("these need ISSUE, SHORT, MEANING_AYE and MEANING_NO before they "
              "can be applied: {0}".format(missing))
        return 1
    known = set(existing_issue_ids())
    unknown = sorted({c["ISSUE"] for c in chosen} - known)
    if unknown:
        print("unknown issue id(s) {0}: add them to the issues: block of "
              "config/vote_tracker.yaml first".format(unknown))
        return 1

    queue = {c["id"]: c for c in load_queue()["candidates"]}
    lines = []
    for c in chosen:
        cand = queue.get(c["id"], {})
        stage = "Report Stage" if "Report Stage" in (cand.get("title") or "") else (
            "Third Reading" if "Third Reading" in (cand.get("title") or "") else (
                "Second Reading" if "Second Reading" in (cand.get("title") or "")
                else "Division"))
        lines.append("""
  # added from the division review worksheet
  - id: {id}
    issue: {issue}
    stage: {stage}
    stage_group: {stage}
    landmark: {landmark}
    signed_off: false
    our_side: "{side}"
    short: {short}
    context: {context}
    meaning_aye: >-
      {aye}
    meaning_no: >-
      {no}""".format(
            id=c["id"], issue=c["ISSUE"], stage=stage,
            landmark=str((c.get("LANDMARK") or "").lower() in ("y", "yes", "true")).lower(),
            side=(c.get("OUR_SIDE") or "no"),
            short=json.dumps(c["SHORT"]), context=json.dumps(c.get("CONTEXT") or ""),
            aye=c["MEANING_AYE"], no=c["MEANING_NO"]))

    with open(CONFIG, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print("appended {0} division(s) to {1}, all signed_off: false".format(
        len(chosen), CONFIG))
    print("now rebuild: python3 tools/make_vote_tracker.py")
    return 0


def main():
    if "--apply" in sys.argv:
        return apply_worksheet()
    area = None
    if "--area" in sys.argv:
        area = int(sys.argv[sys.argv.index("--area") + 1])
    write_worksheet(area)
    return 0


if __name__ == "__main__":
    sys.exit(main())
