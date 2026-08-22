"""A 5CA sheet for the Senedd: 96 Members, one issue area, paste-in CSV.

    python3 tools/sd_5ca.py --area 2

The ni_5ca/sp_5ca contract, third legislature: placement comes ONLY from a
vote whose meaning a human confirmed in config/sd_stance.yaml; `draft: true`
or a values-less (NOT PLACEABLE) entry places nobody; questions and speeches
are ACTIVITY evidence in Comments and never place; sign conflicts are flagged,
never averaged; Target is always blank; NEVER POSTED anywhere.

Senedd particulars:
  * Vote values are For / Against / Abstain / DidNotVote; the latter two are
    data, not direction.
  * The roster is sd_members (parlparse, with party); vote rows carry the
    Record's own member ids, so the JOIN IS BY NAME, unicode-normalised
    (Sian == Sian-with-a-to-bach); unmatched voters are counted and printed,
    never guessed.
  * There is no sponsorship class: statements of opinion appear discontinued
    and motions are not a Senedd instrument the store holds.
"""

from __future__ import annotations

import csv
import datetime
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel, stance

STANCE_PATH = os.path.join(ROOT, "config", "sd_stance.yaml")
HEADER = ["Decision-Maker", "++", "+", "0", "-", "--", "Target (Y/N)",
          "Based on", "Confidence", "Evidence items", "Profile", "Comments"]


def norm_name(name):
    n = unicodedata.normalize("NFKD", name or "").encode(
        "ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", n.lower())


def name_tokens(name):
    """(first, last) token key -- the Record inserts middle names parlparse
    lacks ('Benjamin Hodge Mckenna' vs 'Benjamin McKenna')."""
    toks = [norm_name(t) for t in re.split(r"\s+", (name or "").strip()) if t]
    return (toks[0], toks[-1]) if len(toks) >= 2 else None


class Roster:
    """Name join with a first+last-token fallback that only fires when the
    pairing is unique among sitting Members -- an ambiguous pairing is a
    miss, never a guess."""

    def __init__(self, members):
        self.exact = dict(members)
        self.pairs = {}
        ambiguous = set()
        for key, m in members.items():
            pair = name_tokens(m["name"])
            if pair is None:
                continue
            if pair in self.pairs and self.pairs[pair] != key:
                ambiguous.add(pair)
            self.pairs[pair] = key
        for pair in ambiguous:
            del self.pairs[pair]

    def lookup(self, record_name):
        key = norm_name(record_name)
        if key in self.exact:
            return key
        pair = name_tokens(record_name)
        return self.pairs.get(pair) if pair else None


def load_stance(path=STANCE_PATH):
    import yaml
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    out = {}
    for entry in (cfg.get("divisions") or []):
        key = str(entry.get("key") or "")
        if key:
            # YAML 1.1: unquoted `for` is safe (not a bool) but keep the
            # no/False normalisation habit for any future `no:` keys.
            if "no" not in entry and False in entry:
                entry["no"] = entry.pop(False)
            out[key] = entry
    return out


def vote_stance(entry, result):
    if not entry or entry.get("draft"):
        return None, None
    if result == "For":
        return entry.get("for"), entry.get("why_for")
    if result == "Against":
        return entry.get("against"), entry.get("why_against")
    return None, None


def place(scored):
    real = [s for s in scored if s[0] is not None]
    if not real:
        return "0", False, None
    best = max(real, key=lambda s: (abs(s[0] or 0), s[1] or ""))
    signs = {(1 if s[0] > 0 else -1) for s in real if s[0]}
    return stance.stance_to_column(best[0]), len(signs) > 1, best


def build_rows(conn, area, entries):
    members = {}
    for r in conn.execute(
            "SELECT name, party, post FROM sd_members WHERE end_date IS NULL "
            "OR end_date >= date('now')"):
        members[norm_name(r["name"])] = {"name": r["name"],
                                         "party": r["party"],
                                         "post": r["post"]}
    roster = Roster(members)
    per = {k: {"scored": [], "lines": []} for k in members}
    unmatched = set()

    def rec_for(record_name):
        key = roster.lookup(record_name)
        return per[key] if key else None

    votes = conn.execute(
        "SELECT v.member_name, v.result AS vote, d.key, d.title, d.dated, "
        "d.areas, d.result FROM sd_votes v "
        "JOIN sd_divisions d ON d.key = v.division_key "
        "WHERE d.areas IS NOT NULL AND d.areas != '[]'").fetchall()
    for v in votes:
        if area not in json.loads(v["areas"] or "[]"):
            continue
        rec = rec_for(v["member_name"])
        if rec is None:
            unmatched.add(v["member_name"])
            continue
        entry = entries.get(v["key"])
        s, why = vote_stance(entry, v["vote"])
        label = "{0} VOTE {1}: {2}".format(
            v["dated"] or "?", (v["vote"] or "?").upper(),
            (v["title"] or "")[:56])
        if s is not None:
            rec["scored"].append((s, v["dated"] or "", label))
            rec["lines"].append("{0} [{1:+d}: {2}]".format(
                label, s, " ".join((why or "").split())[:110]))
        elif v["vote"] in ("Abstain", "DidNotVote"):
            rec["lines"].append(label + " [absence/abstention -- not placed]")
        elif entry and entry.get("draft"):
            rec["lines"].append(label + " [meaning line DRAFT -- not placed]")
        elif entry:
            rec["lines"].append(label + " [NOT PLACEABLE (confirmed): see "
                                        "config/sd_stance.yaml]")
        else:
            rec["lines"].append(label + " [no meaning line -- not placed]")

    for q in conn.execute(
            "SELECT member_name, reference, dated, body, areas FROM sd_items "
            "WHERE kind='question' AND areas IS NOT NULL AND areas != '[]'"):
        if area not in json.loads(q["areas"] or "[]"):
            continue
        rec = rec_for(q["member_name"])
        if rec is None:
            continue
        rec["lines"].append(
            "{0} QUESTION {1}: \"{2}\" [activity, not direction]".format(
                q["dated"] or "?", q["reference"],
                " ".join((q["body"] or "").split())[:90]))

    for sp in conn.execute(
            "SELECT member_name, dated, heading, excerpt, areas FROM sd_events "
            "WHERE areas IS NOT NULL AND areas != '[]'"):
        if area not in json.loads(sp["areas"] or "[]"):
            continue
        rec = rec_for(sp["member_name"])
        if rec is None:
            continue
        rec["lines"].append(
            "{0} SPOKE: {1} \"{2}\" [activity, not direction]".format(
                sp["dated"] or "?", (sp["heading"] or "?")[:44],
                " ".join((sp["excerpt"] or "").split())[:90]))

    today = datetime.date.today().isoformat()
    rows = []
    for key, m in members.items():
        rec = per[key]
        column, conflict, decided = place(rec["scored"])
        comments = list(reversed(sorted(rec["lines"])))
        if conflict:
            comments.insert(0, "MIXED RECORD: directional evidence on both "
                               "sides -- read the acts, not the column")
        if decided:
            based = stance.based_on("vote", decided[1] or today)
            confidence = "strong (recorded vote, human-confirmed meaning line)"
        elif rec["lines"]:
            based = "no confirmed meaning line"
            confidence = "n/a (activity only)"
        else:
            based = "no evidence"
            confidence = ""
            comments = ["No recorded activity on this area"]
        rows.append({
            "decision_maker": "{0} ({1}) - {2}".format(
                m["name"], m["party"] or "?", m["post"] or "?"),
            "column": column, "conflict": conflict,
            "n_events": len(rec["lines"]),
            "based_on": based, "confidence": confidence,
            "comments": comments})
    order = {c: i for i, c in enumerate(stance.COLUMNS)}
    rows.sort(key=lambda r: (order[r["column"]], -r["n_events"],
                             r["decision_maker"]))
    former_norms = {norm_name(r["name"]) for r in conn.execute(
        "SELECT name FROM sd_members WHERE end_date < date('now')")}
    former = sorted(u for u in unmatched if norm_name(u) in former_norms)
    unknown = sorted(u for u in unmatched if norm_name(u) not in former_norms)
    return rows, former, unknown


def main():
    if "--area" not in sys.argv:
        print("usage: python3 tools/sd_5ca.py --area N [out.csv]")
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
    entries = load_stance()
    drafts = sum(1 for e in entries.values() if e.get("draft"))
    rows, former, unknown = build_rows(conn, area, entries)

    label = names.get(area, "area-{0}".format(area))
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    positional = [a for a in sys.argv[sys.argv.index("--area") + 2:]
                  if not a.startswith("--")]
    path = positional[0] if positional else os.path.join(
        ROOT, "data", "5ca", "sd-5ca-{0}-{1}.csv".format(
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
            marks = {c: ("x" if c == r["column"] else "")
                     for c in stance.COLUMNS}
            w.writerow([r["decision_maker"], marks["++"], marks["+"],
                        marks["0"], marks["-"], marks["--"], "",
                        r["based_on"], r["confidence"], r["n_events"], "",
                        " | ".join(r["comments"])[:1800]])
    print("SD 5CA ({0}): {1} Members ({2} with evidence, {3} placed) -> {4}"
          .format(label, len(rows), with_evidence, placed, path))
    print("  " + "  ".join("{0} x{1}".format(c, tally[c])
                           for c in stance.COLUMNS))
    if former:
        print("  {0} voter(s) are former Members, excluded by design (the "
              "sheet rates sitting Members only)".format(len(former)))
    if unknown:
        print("  {0} voter name(s) join NO roster row (reported, never "
              "guessed): {1}".format(len(unknown), "; ".join(unknown)))
    if drafts:
        print("\n  {0} of {1} meaning line(s) are still DRAFT; a draft "
              "places nobody.".format(drafts, len(entries)))
    elif entries:
        print("\n  All {0} meaning line(s) are human-settled (a NOT "
              "PLACEABLE entry is a settled reading too).".format(len(entries)))
    print("  Never posted anywhere.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
