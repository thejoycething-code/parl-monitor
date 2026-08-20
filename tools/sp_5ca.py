"""A 5CA sheet for Holyrood: 129 MSPs, one issue area, paste-in CSV.

    python3 tools/sp_5ca.py --area 2              # sheet for one area
    python3 tools/sp_5ca.py --area 2 out.csv      # explicit path

Mirrors tools/ni_5ca.py, one legislature over, with the same contract: the
Westminster 5CA places members from the Claude-scored `stance` table; the
watching briefs forbid that. Placement comes ONLY from acts whose meaning a
human confirmed in config/sp_stance.yaml -- a recorded vote on a division, or
proposing a motion -- and an entry carrying `draft: true` places NOBODY.
Questions appear as evidence in Comments and never place anyone: activity is
not direction. Sign conflicts are flagged, never averaged. Target is blank.

Holyrood gives this sheet two things NI could not:

  * The API stamps each vote row with the voter's party AT THE VOTE and its
    own whip-agreement flag (MSPSharesParty). A member who broke whip on one
    of our divisions gets a REBELLED marker on the evidence line -- a chosen
    act against the party line is the strongest signal short of the vote
    value itself.
  * 'Not Voted' and 'Abstain' are first-class values, so absence is data:
    both render as evidence lines, neither places.

NEVER POSTED. No Slack, no publish import, no `items`, no `mp_events`. The
CSV lands in data/5ca/ next to the Westminster and NI sheets and stays there.
"""

from __future__ import annotations

import csv
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel, stance

STANCE_PATH = os.path.join(ROOT, "config", "sp_stance.yaml")

HEADER = ["Decision-Maker", "++", "+", "0", "-", "--", "Target (Y/N)",
          "Based on", "Confidence", "Evidence items", "Profile", "Comments"]

SP_KIND_WEIGHT = {"vote": 5, "motion": 3, "question": 1}


def load_stance(path=STANCE_PATH, section="divisions"):
    """{reference: entry}, drafts included. Normalises the YAML 1.1 trap: an
    unquoted `no:` key parses as boolean False (the ni_5ca lesson)."""
    import yaml
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    out = {}
    for entry in (cfg.get(section) or []):
        ref = str(entry.get("reference") or "")
        if not ref:
            continue
        if "no" not in entry and False in entry:
            entry["no"] = entry.pop(False)
        out[ref] = entry
    return out


def vote_stance(entry, vote):
    """(stance, why) for one vote against one CONFIRMED entry. Drafts,
    abstentions and 'Not Voted' return (None, None): a draft is not a
    judgement yet, and absence is not a direction."""
    if not entry or entry.get("draft"):
        return None, None
    if vote == "Yes":
        return entry.get("aye"), entry.get("why_aye")
    if vote == "No":
        return entry.get("no"), entry.get("why_no")
    return None, None


def sponsor_stance(entry):
    if not entry or entry.get("draft"):
        return None, None
    if entry.get("sponsored") is None:
        return None, None
    return entry.get("sponsored"), entry.get("why_sponsored")


def place(scored):
    """Most-directional wins, then evidence weight, then recency; a sign
    conflict is flagged and never averaged (the stance.py discipline)."""
    real = [s for s in scored if s[0] is not None]
    if not real:
        return "0", False, None
    best = max(real, key=lambda s: (abs(s[0] or 0),
                                    SP_KIND_WEIGHT.get(s[3], 0), s[1] or ""))
    signs = {(1 if s[0] > 0 else -1) for s in real if s[0]}
    return stance.stance_to_column(best[0]), len(signs) > 1, best


def build_rows(conn, area, entries, motion_entries=None):
    motion_entries = motion_entries or {}
    members = {r["person_id"]: r for r in conn.execute(
        "SELECT person_id, name, preferred_name, party, constituency "
        "FROM sp_members WHERE is_current = 1")}
    per = {pid: {"scored": [], "lines": []} for pid in members}

    votes = conn.execute(
        "SELECT v.person_id, v.vote, v.party, v.shares_party, d.reference, "
        "d.title, d.dated, d.areas FROM sp_votes v "
        "JOIN sp_divisions d ON d.key = v.division_key "
        "WHERE d.areas IS NOT NULL AND d.areas != '[]'").fetchall()
    for v in votes:
        if area not in json.loads(v["areas"] or "[]"):
            continue
        rec = per.get(v["person_id"])
        if rec is None:
            continue                     # not a current member
        entry = entries.get(v["reference"])
        s, why = vote_stance(entry, v["vote"])
        rebel = " REBELLED (voted against own party)" \
            if v["shares_party"] == "No" else ""
        label = "{0} VOTE {1}: {2} ({3}){4}".format(
            v["dated"] or "?", (v["vote"] or "?").upper(),
            v["reference"], (v["title"] or "")[:48], rebel)
        if s is not None:
            rec["scored"].append((s, v["dated"] or "", label, "vote"))
            rec["lines"].append("{0} [{1:+d}: {2}]".format(
                label, s, " ".join((why or "").split())[:110]))
        elif v["vote"] in ("Abstain", "Not Voted"):
            rec["lines"].append(label + " [absence/abstention -- not placed]")
        elif entry and entry.get("draft"):
            rec["lines"].append(label + " [meaning line DRAFT -- not placed]")
        else:
            rec["lines"].append(label + " [no meaning line -- not placed]")

    # Proposer sponsorship: the motion's own msp_id. Co-signatories arrive
    # when the supports endpoint recovers (503 on 2026-08-20).
    motions = conn.execute(
        "SELECT reference, title, dated, msp_id, areas FROM sp_items "
        "WHERE kind='motion' AND msp_id IS NOT NULL "
        "AND areas IS NOT NULL AND areas != '[]'").fetchall()
    for m in motions:
        if area not in json.loads(m["areas"] or "[]"):
            continue
        rec = per.get(m["msp_id"])
        if rec is None:
            continue
        label = "{0} MOTION PROPOSED {1}: {2}".format(
            m["dated"] or "?", m["reference"] or "?", (m["title"] or "")[:52])
        entry = motion_entries.get(m["reference"])
        s, why = sponsor_stance(entry)
        if s is not None:
            rec["scored"].append((s, m["dated"] or "", label, "motion"))
            rec["lines"].append("{0} [{1:+d}: {2}]".format(
                label, s, " ".join((why or "").split())[:110]))
        elif entry and entry.get("draft"):
            rec["lines"].append(label + " [meaning line DRAFT -- not placed]")
        else:
            rec["lines"].append(label + " [no meaning line -- not placed]")

    questions = conn.execute(
        "SELECT msp_id, reference, dated, body, areas FROM sp_items "
        "WHERE kind='question' AND msp_id IS NOT NULL "
        "AND areas IS NOT NULL AND areas != '[]'").fetchall()
    for q in questions:
        if area not in json.loads(q["areas"] or "[]"):
            continue
        rec = per.get(q["msp_id"])
        if rec is None:
            continue
        rec["lines"].append(
            "{0} QUESTION {1}: \"{2}\" [activity, not direction]".format(
                q["dated"] or "?", q["reference"] or "?",
                " ".join((q["body"] or "").split())[:90]))

    today = datetime.date.today().isoformat()
    rows = []
    for pid, m in members.items():
        rec = per[pid]
        column, conflict, decided = place(rec["scored"])
        comments = list(reversed(sorted(rec["lines"])))
        if conflict:
            comments.insert(0, "CONFLICTING SIGNALS - review all evidence")
        if decided:
            based = stance.based_on(
                {"vote": "vote", "motion": "edm"}.get(decided[3], decided[3]),
                decided[1] or today)
            confidence = ("strong (recorded vote, human-confirmed meaning line)"
                          if decided[3] == "vote" else
                          "moderate (motion proposed, human-confirmed "
                          "meaning line)")
        elif rec["lines"]:
            based = "no confirmed meaning line"
            confidence = "n/a (activity only)"
        else:
            based = "no evidence"
            confidence = ""
            comments = ["No recorded activity on this area"]
        rows.append({
            "decision_maker": "{0} ({1}) - {2}".format(
                m["preferred_name"] and "{0} {1}".format(
                    m["preferred_name"], m["name"].split(",")[0])
                or m["name"], m["party"] or "?", m["constituency"] or "?"),
            "column": column, "conflict": conflict,
            "n_events": len(rec["lines"]),
            "based_on": based, "confidence": confidence,
            "comments": comments})
    order = {c: i for i, c in enumerate(stance.COLUMNS)}
    rows.sort(key=lambda r: (order[r["column"]], -r["n_events"],
                             r["decision_maker"]))
    return rows


def main():
    if "--area" not in sys.argv:
        print("usage: python3 tools/sp_5ca.py --area N [out.csv]")
        return 1
    area = int(sys.argv[sys.argv.index("--area") + 1])
    import yaml
    with open(os.path.join(ROOT, "config", "stance_overrides.yaml"),
              encoding="utf-8") as handle:
        excluded = {int(a) for a in
                    (yaml.safe_load(handle) or {}).get("excluded_from_5ca") or []}
    if area in excluded:
        print("area {0} is collated only, not a 5CA area".format(area))
        return 1

    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    entries = load_stance(section="divisions")
    motion_entries = load_stance(section="motions")
    drafts = sum(1 for e in list(entries.values()) + list(motion_entries.values())
                 if e.get("draft"))
    rows = build_rows(conn, area, entries, motion_entries)

    label = names.get(area, "area-{0}".format(area))
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    positional = [a for a in sys.argv[sys.argv.index("--area") + 2:]
                  if not a.startswith("--")]
    path = positional[0] if positional else os.path.join(
        ROOT, "data", "5ca", "sp-5ca-{0}-{1}.csv".format(
            slug, datetime.date.today().isoformat()))
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        w.writerow(HEADER)
        tally = {c: 0 for c in stance.COLUMNS}
        placed = with_evidence = 0
        for r in rows:
            tally[r["column"]] += 1
            if r["column"] != "0":
                placed += 1
            if r["based_on"] != "no evidence":
                with_evidence += 1
            marks = {c: ("x" if c == r["column"] else "") for c in stance.COLUMNS}
            w.writerow([r["decision_maker"], marks["++"], marks["+"],
                        marks["0"], marks["-"], marks["--"], "",
                        r["based_on"], r["confidence"], r["n_events"], "",
                        " | ".join(r["comments"])[:1800]])
    print("SP 5CA ({0}): {1} MSPs ({2} with evidence, {3} placed) -> {4}".format(
        label, len(rows), with_evidence, placed, path))
    print("  " + "  ".join("{0} x{1}".format(c, tally[c]) for c in stance.COLUMNS))
    total = len(entries) + len(motion_entries)
    if drafts:
        print("\n  {0} of {1} meaning line(s) are still DRAFT; a draft places "
              "nobody\n  until Christopher removes the flag.".format(drafts, total))
    elif total:
        print("\n  All {0} meaning line(s) are human-confirmed: the sheet "
              "places MSPs.".format(total))
    print("  Placement comes only from acts whose meaning a human confirmed.")
    print("  Never posted anywhere.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
