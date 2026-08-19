"""A 5CA sheet for the NI Assembly: 90 MLAs, one issue area, paste-in CSV.

    python3 tools/ni_5ca.py --area 5              # sheet for one area
    python3 tools/ni_5ca.py --area 5 out.csv      # explicit path

HOW A COLUMN GETS FILLED, and why this does not break the no-scoring rule.
The Westminster 5CA places members from the `stance` table, which is
Claude-scored; NI forbids that (tools/ni_monitor.py: nothing estimates a
stance). What transfers is the OTHER Westminster mechanism -- the `overrides`
block of config/stance_overrides.yaml, where a human writes what an aye means
and the tool merely applies it. config/ni_stance.yaml is that file for NI.
An entry still carrying `draft: true` places NOBODY: its divisions render as
evidence lines only, so a Claude-drafted reading can never move an MLA into a
column without Christopher having confirmed it.

Placement therefore comes only from acts whose meaning a human has confirmed:
a recorded VOTE on a division, or SPONSORSHIP of a motion. Sponsoring is a
chosen act of advancing a specific text, which is why Westminster weights an
EDM sponsored above one signed, and NI_KIND_WEIGHT keeps that ordering with a
vote on top -- a vote is the only act with a recorded direction.

Questions appear as evidence in Comments and never place anyone: a question
shows activity, not direction, which is the same reason the Westminster ledger
alone cannot fill a column (docs/5ca-notes.md).

Sign conflicts are flagged, never averaged (the stance.py discipline: the
tool will not quietly cancel a vote against a vote). Target is always blank
-- that is the campaigner's call, never the tool's.

THE DESIGNATION COLUMN is NI-specific and load-bearing: a cross-community
vote needs majorities in BOTH designations, so "48 of 90 with us" can still
lose. The sheet carries Unionist/Nationalist/Other so that arithmetic is
possible at a glance.

NEVER POSTED. No Slack, no publish import, no `items`, no `mp_events`. The
CSV lands in data/5ca/ next to the Westminster sheets and stays there.
"""

from __future__ import annotations

import csv
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel, ni_store, stance

STANCE_PATH = os.path.join(ROOT, "config", "ni_stance.yaml")

HEADER = ["Decision-Maker", "++", "+", "0", "-", "--", "Target (Y/N)",
          "Based on", "Confidence", "Evidence items", "Profile", "Comments",
          "Designation"]


def load_stance(path=STANCE_PATH, section="divisions"):
    """{doc_id: entry} from one section of config/ni_stance.yaml, drafts included.

    Normalises the YAML 1.1 trap: an unquoted `no:` key parses as the boolean
    False, so both spellings are read -- an edit that drops the quotes must
    not silently lose the no-lobby meaning.
    """
    import yaml
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    out = {}
    for entry in (cfg.get(section) or []):
        doc_id = str(entry.get("doc_id") or "")
        if not doc_id:
            continue
        if "no" not in entry and False in entry:
            entry["no"] = entry.pop(False)
        out[doc_id] = entry
    return out


# Sponsoring a motion outranks signing one, which outranks a question -- the
# same ordering as the Westminster KIND_WEIGHT (edm 3 > edm-signed 2 > pq 1).
# A vote stays top because it is the only act with a recorded direction.
NI_KIND_WEIGHT = {"vote": 5, "motion": 3, "motion-signed": 2, "question": 1}


def sponsor_stance(entry, sequence):
    """(stance, why) for one sponsorship against a CONFIRMED motion entry.

    The SEQUENCE changes the evidence weight, never the direction: a
    co-signatory is advancing the same text as the proposer, just less
    prominently. Returns (None, None) for drafts.
    """
    if not entry or entry.get("draft"):
        return None, None
    stance_value = entry.get("sponsored")
    if stance_value is None:
        return None, None
    role = "proposed" if sequence == 1 else "co-signed"
    return stance_value, "{0}: {1}".format(
        role, " ".join((entry.get("why_sponsored") or "").split()))


def vote_stance(entry, vote):
    """(stance, why) for one recorded vote against one CONFIRMED entry.

    Returns (None, None) for drafts, abstentions and unrecognised votes: an
    abstention is not a direction, and a draft is not a judgement yet.
    """
    if not entry or entry.get("draft"):
        return None, None
    if vote == "aye":
        return entry.get("aye"), entry.get("why_aye")
    if vote == "no":
        return entry.get("no"), entry.get("why_no")
    return None, None


def place(scored):
    """(column, conflict, decided) from [(stance, date, line, kind)] rows.

    Most-directional wins, then evidence WEIGHT, then recency -- the
    suggest_rows ordering. Weight matters now that a vote and a motion
    sponsorship can both carry a direction: a recorded vote is ground truth and
    must outrank a signature of equal magnitude. A sign conflict is flagged and
    NEVER averaged: +2 and -1 is a flagged +2, not a quiet +0.5.
    """
    real = [s for s in scored if s[0] is not None]
    if not real:
        return "0", False, None
    best = max(real, key=lambda s: (abs(s[0] or 0),
                                    NI_KIND_WEIGHT.get(s[3], 0), s[1] or ""))
    signs = {(1 if s[0] > 0 else -1) for s in real if s[0]}
    return stance.stance_to_column(best[0]), len(signs) > 1, best


def build_rows(conn, area, entries, motion_entries=None):
    """One row per sitting MLA, strongest placement first.

    Evidence gathered per member: votes on divisions classified into `area`,
    MOTIONS they proposed or co-signed in `area`, and questions they tabled in
    `area`. Each is scored only where a human has confirmed its meaning; all of
    it is listed either way, because absence of a meaning line is not absence
    of activity.
    """
    motion_entries = motion_entries or {}
    today = datetime.date.today().isoformat()
    members = {r["person_id"]: r for r in conn.execute(
        "SELECT person_id, display_name, party, constituency FROM ni_members")}

    votes = conn.execute(
        "SELECT v.person_id, v.vote, v.designation, d.doc_id, d.dated, "
        "d.bill, d.amendment_no, d.areas, d.excerpt FROM ni_votes v "
        "JOIN ni_divisions d ON d.doc_id = v.doc_id "
        "WHERE d.areas IS NOT NULL AND d.areas != '[]'").fetchall()

    questions = conn.execute(
        "SELECT tabler_person_id, reference, dated, title, areas "
        "FROM ni_items WHERE kind = 'question' AND tabler_person_id IS NOT NULL "
        "AND areas IS NOT NULL").fetchall()

    per = {pid: {"scored": [], "lines": [], "designation": ""}
           for pid in members}
    for v in votes:
        if area not in json.loads(v["areas"] or "[]"):
            continue
        rec = per.get(v["person_id"])
        if rec is None:
            continue                      # a former member; roster is current
        rec["designation"] = v["designation"] or rec["designation"]
        entry = entries.get(v["doc_id"])
        s, why = vote_stance(entry, v["vote"])
        label = "{0} VOTE {1}: {2} amendment {3}".format(
            v["dated"] or "?", (v["vote"] or "?").upper(),
            v["bill"] or "?", v["amendment_no"])
        if s is not None:
            rec["scored"].append((s, v["dated"] or "", label, "vote"))
            rec["lines"].append("{0} [{1:+d}: {2}]".format(
                label, s, " ".join((why or "").split())[:110]))
        elif entry and entry.get("draft"):
            rec["lines"].append(label + " [meaning line DRAFT -- not placed]")
        else:
            rec["lines"].append(label + " [no meaning line -- not placed]")
    # MOTION SPONSORSHIP. Joined through ni_items so only motions classified
    # into this area count, and through ni_sponsors for the person and sequence.
    sponsorships = conn.execute(
        "SELECT s.person_id, s.sequence, s.doc_id, i.title, i.dated, i.areas "
        "FROM ni_sponsors s JOIN ni_items i "
        "  ON i.id = 'ni-motion:' || s.doc_id "
        "WHERE i.areas IS NOT NULL AND i.areas != '[]'").fetchall()
    for sp in sponsorships:
        if area not in json.loads(sp["areas"] or "[]"):
            continue
        rec = per.get(sp["person_id"])
        if rec is None:
            continue
        role = "PROPOSED" if sp["sequence"] == 1 else "CO-SIGNED"
        label = "{0} MOTION {1}: {2}".format(
            sp["dated"] or "?", role, (sp["title"] or "?")[:52])
        entry = motion_entries.get(sp["doc_id"])
        st, why = sponsor_stance(entry, sp["sequence"])
        if st is not None:
            kind = "motion" if sp["sequence"] == 1 else "motion-signed"
            rec["scored"].append((st, sp["dated"] or "", label, kind))
            rec["lines"].append("{0} [{1:+d}: {2}]".format(
                label, st, (why or "")[:110]))
        elif entry and entry.get("draft"):
            rec["lines"].append(label + " [meaning line DRAFT -- not placed]")
        else:
            rec["lines"].append(label + " [no meaning line -- not placed]")

    for q in questions:
        if area not in json.loads(q["areas"] or "[]"):
            continue
        rec = per.get(q["tabler_person_id"])
        if rec is None:
            continue
        rec["lines"].append(
            "{0} QUESTION {1}: \"{2}\" [activity, not direction]".format(
                q["dated"] or "?", q["reference"] or "?",
                " ".join((q["title"] or "").split())[:90]))

    rows = []
    for pid, m in members.items():
        rec = per[pid]
        column, conflict, decided = place(rec["scored"])
        comments = list(reversed(sorted(rec["lines"])))
        if conflict:
            comments.insert(0, "CONFLICTING SIGNALS - review all evidence")
        if decided:
            kind = decided[3]
            based = stance.based_on(
                {"vote": "vote", "motion": "edm",
                 "motion-signed": "edm-signed"}.get(kind, kind),
                decided[1] or today)
            confidence = ("strong (recorded vote, human-confirmed meaning line)"
                          if kind == "vote" else
                          "moderate (motion sponsorship, human-confirmed "
                          "meaning line)")
        elif rec["lines"]:
            based = "no confirmed meaning line"
            confidence = "n/a (activity only)"
        else:
            based = "no evidence"
            confidence = ""
            comments = ["No recorded activity on this area"]
        rows.append({
            "person_id": pid,
            "decision_maker": "{0} ({1}) - {2}".format(
                m["display_name"], m["party"], m["constituency"]),
            "column": column, "conflict": conflict,
            "n_events": len(rec["lines"]),
            "based_on": based, "confidence": confidence,
            "comments": comments, "designation": rec["designation"]})
    order = {c: i for i, c in enumerate(stance.COLUMNS)}
    rows.sort(key=lambda r: (order[r["column"]], -r["n_events"],
                             r["decision_maker"]))
    return rows


def main():
    if "--area" not in sys.argv:
        print("usage: python3 tools/ni_5ca.py --area N [out.csv]")
        return 1
    area = int(sys.argv[sys.argv.index("--area") + 1])

    # Same exclusion the Westminster sheet enforces, same source of truth.
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
    total_entries = len(entries) + len(motion_entries)
    rows = build_rows(conn, area, entries, motion_entries)

    label = names.get(area, "area-{0}".format(area))
    slug = label.lower().replace(" ", "-")
    positional = [a for a in sys.argv[sys.argv.index("--area") + 2:]
                  if not a.startswith("--")]
    path = positional[0] if positional else os.path.join(
        ROOT, "data", "5ca", "ni-5ca-{0}-{1}.csv".format(
            slug, datetime.date.today().isoformat()))
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        w.writerow(HEADER)
        tally = {c: 0 for c in stance.COLUMNS}
        for r in rows:
            tally[r["column"]] += 1
            w.writerow([
                r["decision_maker"],
                *("1" if r["column"] == c else "" for c in stance.COLUMNS),
                "",                                   # Target: never the tool's
                r["based_on"], r["confidence"], r["n_events"],
                "",                                   # Profile: none for NI yet
                " | ".join(r["comments"]), r["designation"]])
        w.writerow(["Totals - {0} decision-makers".format(len(rows)),
                    *(tally[c] for c in stance.COLUMNS), "", "", "", "", "",
                    "", ""])

    placed = sum(1 for r in rows if r["column"] != "0")
    active = sum(1 for r in rows if r["n_events"])
    print("NI 5CA ({0}): {1} MLAs ({2} with evidence, {3} placed) -> {4}"
          .format(label, len(rows), active, placed, os.path.relpath(path, ROOT)))
    print("  " + "  ".join("{0} x{1}".format(c, tally[c])
                           for c in stance.COLUMNS))
    if drafts:
        print("\n  {0} of {1} meaning line(s) in config/ni_stance.yaml are "
              "still DRAFT.".format(drafts, total_entries))
        print("  A draft places NOBODY: its votes appear as evidence only. "
              "Review the\n  drafted readings and delete each `draft: true` "
              "line to confirm it.")
    conflicts = sum(1 for r in rows if r["conflict"])
    if conflicts:
        print("  {0} MLA(s) carry CONFLICTING SIGNALS - flagged in Comments, "
              "never averaged.".format(conflicts))
    print("\n  Placement comes only from acts whose meaning a human confirmed: "
          "a recorded\n  vote, or sponsorship of a motion. Questions are "
          "evidence, not direction.\n  Target is blank: that is the "
          "campaigner's call. Never posted anywhere.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
