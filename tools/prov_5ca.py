#!/usr/bin/env python3
"""A 5CA sheet for one Canadian provincial legislature and one issue area, CSV.

    python3 tools/prov_5ca.py --prov ab --area 3
    python3 tools/prov_5ca.py --prov sk --all
    python3 tools/prov_5ca.py --prov bc --area 6 --db /tmp/prov.db --out-dir /tmp/5ca

Reads the store only; fetches nothing and posts nothing. The provincial
mirror of tools/ca_5ca.py, with the same rule: config/prov_stance.yaml is
where a HUMAN writes what a Yea on a division meant, and this tool applies
it. An entry carrying `draft: true` places nobody; so does one marked
`placeable: false`, and so does one with only `read_first:`. The file is
EMPTY today, so every sheet is an evidence list: that is the design.

What can place a member, once a reading is confirmed:
  * a recorded VOTE on a division whose TALLY CHECK passed
    (prov_divisions.positions_ok = 1) -- weight 5;
  * SPONSORING a private member's bill -- weight 3 (a government bill's
    sponsor is a minister acting in office, never placed).
What never places anyone:
  * a division with positions_ok = 0: its names did not account for the
    printed totals, so its positions are not trusted. Counted in the log,
    never shown against a member;
  * a VOICE decision: there is no member record. The sheet's last row says
    how many decisions on the area passed on voice, so an empty column is
    never read as one.

THE ABSENCE RULE (Westminster, 21 September 2026): a member at ++ with no
Yea/Nay on the area's latest decisive confirmed division, while holding a
term valid that day, is capped at + with the reason in Comments.

Party: the column is the member's latest; each vote line carries the party
AT THE VOTE where the source dates it (Alberta, Saskatchewan) and "?"
where it does not (BC). Everyone who cast a vote on the area is listed;
those not on the latest roster are labelled FORMER and not counted.

Consensus legislatures (nt, nu) are refused: no parties, cabinet abstains
as a bloc, evidence lists only (docs/canada-provinces-scope.md).

Output: <out-dir>/prov-5ca-<prov>-<area-slug>.csv, a stable name per sheet.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel, prov_names as pn, stance  # noqa: E402

STANCE_PATH = os.path.join(ROOT, "config", "prov_stance.yaml")
OUT_DIR = os.path.join(ROOT, "data", "5ca")
HEADER = ["Decision-Maker", "++", "+", "0", "-", "--", "Target (Y/N)",
          "Based on", "Confidence", "Evidence items", "Profile", "Comments", "Party", "Riding"]
KIND_WEIGHT = {"vote": 5, "bill": 3}
DIRECTIONAL = ("Yea", "Nay")
CONSENSUS = ("nt", "nu")


def load_stance(path=STANCE_PATH, section="divisions"):
    import yaml
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    return {str(e["key"]): e for e in (cfg.get(section) or []) if e.get("key")}


def status(entry):
    """'confirmed', 'draft', 'unplaceable', 'unread' or 'none' (as tools/ca_5ca.py)."""
    if not entry:
        return "none"
    if entry.get("placeable") is False:
        return "unplaceable"
    if entry.get("yea") is None and entry.get("nay") is None and entry.get("sponsored") is None:
        return "unread"
    if entry.get("draft"):
        return "draft"
    return "confirmed"


NOT_PLACED = {"draft": "reading DRAFT -- not placed",
              "confirmed": "this side carries no value -- its lobby tells no member apart",
              "unplaceable": "never places: {reason}",
              "unread": "not read yet -- not placed",
              "none": "no reading -- not placed"}


def not_placed(entry):
    return NOT_PLACED[status(entry)].format(reason=(entry or {}).get("reason") or "")


def place(scored):
    real = [s for s in scored if s[0] is not None]
    if not real:
        return "0", False, None
    best = max(real, key=lambda s: (abs(s[0] or 0), KIND_WEIGHT.get(s[3], 0), s[1] or ""))
    signs = {(1 if s[0] > 0 else -1) for s in real if s[0]}
    return stance.stance_to_column(best[0]), len(signs) > 1, best


def _in_area(areas, area):
    return area in json.loads(areas or "[]")


def build_rows(conn, prov, area, entries, bill_entries):
    members = {r["member_key"]: dict(r) for r in conn.execute(
        "SELECT * FROM prov_members WHERE prov=?", (prov,))}
    resolver = pn.Resolver.from_conn(conn, prov)
    all_divs = [dict(r) for r in conn.execute(
        "SELECT * FROM prov_divisions WHERE prov=? ORDER BY date, division_key", (prov,))
        if _in_area(r["areas"], area)]
    trusted = [d for d in all_divs if d["kind"] == "recorded" and d["positions_ok"] == 1]
    untrusted = [d for d in all_divs if d["kind"] == "recorded" and d["positions_ok"] != 1]
    voice = [d for d in all_divs if d["kind"] == "voice"]
    votes = {d["division_key"]: {r["member_key"]: (r["position"], r["party_at_vote"]) for r in conn.execute(
        "SELECT member_key, position, party_at_vote FROM prov_votes WHERE division_key=? "
        "AND member_key IS NOT NULL", (d["division_key"],))} for d in trusted}
    per = {}

    def rec(key):
        return per.setdefault(key, {"scored": [], "lines": [], "voted": False})

    for d in trusted:
        entry = entries.get(d["division_key"])
        base = "{0} {1}{2} ({3} {4}-{5})".format(
            d["date"], (d["bill_key"] + " " if d["bill_key"] else ""), d["stage"] or d["vote_on"] or "",
            d["result"] or "?", d["yeas"], d["nays"])
        for key, (position, party) in votes[d["division_key"]].items():
            r = rec(key)
            r["voted"] = True
            label = "VOTE {0} as {1}: {2}".format(position.upper(), party or "?", base)
            if position not in DIRECTIONAL:
                r["lines"].append(label + " [no direction recorded]")
                continue
            s = why = None
            if status(entry) == "confirmed":
                s = entry.get("yea") if position == "Yea" else entry.get("nay")
                why = entry.get("why_yea") if position == "Yea" else entry.get("why_nay")
            if s is not None:
                r["scored"].append((s, d["date"], label, "vote"))
                r["lines"].append("{0} [{1:+d}: {2}]".format(label, s, " ".join((why or "").split())[:120]))
            else:
                r["lines"].append("{0} [{1}]".format(label, not_placed(entry)))
        for key in members:
            if key not in votes[d["division_key"]] and resolver.term_for(key, d["date"], d["legislature"]):
                rec(key)["lines"].append("{0} NO RECORDED VOTE: {1}".format(d["date"], base))

    for b in conn.execute("SELECT * FROM prov_bills WHERE prov=? AND sponsor_key IS NOT NULL "
                          "AND COALESCE(is_government, 0) = 0", (prov,)):
        if not _in_area(b["areas"], area):
            continue
        entry = bill_entries.get(b["bill_key"])
        label = "SPONSORED {0} {1}".format(b["bill_key"], (b["title_en"] or "")[:70])
        st = entry.get("sponsored") if status(entry) == "confirmed" else None
        r = rec(b["sponsor_key"])
        if st is not None:
            r["scored"].append((st, b["latest_stage"] or "", label, "bill"))
            r["lines"].append("{0} [{1:+d}: {2}]".format(
                label, st, " ".join((entry.get("why_sponsored") or "").split())[:120]))
        else:
            r["lines"].append("{0} [{1}]".format(label, not_placed(entry)))

    decisive = [d for d in trusted if status(entries.get(d["division_key"])) == "confirmed"
                and max(entries[d["division_key"]].get("yea") or 0,
                        entries[d["division_key"]].get("nay") or 0) >= 2]
    latest = decisive[-1] if decisive else None
    rows = []
    for key, m in members.items():
        r = per.get(key, {"scored": [], "lines": [], "voted": False})
        sitting = bool(m["sitting"]) if m["sitting"] is not None else False
        if not sitting and not r["voted"] and not r["scored"]:
            continue
        column, conflict, decided = place(r["scored"])
        comments = sorted(r["lines"], reverse=True)
        capped = False
        if column == "++" and latest is not None:
            got = votes[latest["division_key"]].get(key, (None,))[0]
            if got not in DIRECTIONAL and resolver.term_for(key, latest["date"], latest["legislature"]):
                column, capped = "+", True
                comments.insert(0, "CAPPED at +: no Yea/Nay on the latest signed division ({0}). ++ "
                                   "means 'will vote with us'; a member who missed it is the contact "
                                   "list.".format(latest["division_key"]))
        if conflict:
            comments.insert(0, "MIXED RECORD: directional evidence on both sides -- read the acts")
        if decided:
            based = stance.based_on({"vote": "vote", "bill": "edm"}[decided[3]], decided[1][:10])
            confidence = "strong (recorded vote, human-confirmed reading)" if decided[3] == "vote" \
                else "moderate (bill sponsorship, human-confirmed reading)"
        elif r["lines"]:
            based, confidence = "no confirmed reading", "n/a (evidence only)"
        else:
            based, confidence, comments = "no evidence", "", ["No recorded activity on this area"]
        rows.append({"key": key, "column": column, "capped": capped, "sitting": sitting,
                     "decision_maker": "{0} ({1}){2}{3}".format(
                         m["name"] or key, m["party"] or "?", " - " + m["riding"] if m["riding"] else "",
                         "" if sitting else " [FORMER]"),
                     "n_events": len(r["lines"]), "based_on": based, "confidence": confidence,
                     "comments": comments, "party": m["party"] or "", "riding": m["riding"] or ""})
    order = {c: i for i, c in enumerate(stance.COLUMNS)}
    rows.sort(key=lambda x: (order[x["column"]], not x["sitting"], -x["n_events"], x["decision_maker"]))
    return rows, trusted, untrusted, voice


def write_sheet(path, rows, voice, untrusted):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tally = {c: 0 for c in stance.COLUMNS}
    sitting = sum(1 for r in rows if r["sitting"])
    with open(path, "w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        w.writerow(HEADER)
        for r in rows:
            if r["sitting"]:
                tally[r["column"]] += 1
            w.writerow([r["decision_maker"], *("1" if r["column"] == c else "" for c in stance.COLUMNS),
                        "", r["based_on"], r["confidence"], r["n_events"], "",
                        " | ".join(r["comments"]), r["party"], r["riding"]])
        w.writerow(["Totals - {0} sitting decision-makers ({1} former listed, not counted)".format(
            sitting, len(rows) - sitting), *(tally[c] for c in stance.COLUMNS),
            "", "", "", "", "", "", "", ""])
        if voice:
            w.writerow(["Passed on voice, no member record: " + "; ".join(
                "{0} {1} {2}".format(d["date"], d["bill_key"] or "", d["stage"] or "") for d in voice)]
                + [""] * (len(HEADER) - 1))
        if untrusted:
            w.writerow(["Not trusted (tally check failed), not shown: " + "; ".join(
                d["division_key"] for d in untrusted)] + [""] * (len(HEADER) - 1))
    return tally


def run(conn, prov, area, entries, bill_entries, names, out_dir, log=print):
    rows, trusted, untrusted, voice = build_rows(conn, prov, area, entries, bill_entries)
    if not any(r["n_events"] for r in rows) and not voice:
        return None
    slug = names.get(area, "area-{0}".format(area)).lower().replace(" ", "-").replace(",", "")
    path = os.path.join(out_dir, "prov-5ca-{0}-{1}.csv".format(prov, slug))
    tally = write_sheet(path, rows, voice, untrusted)
    log("{0} {1}: {2} trusted division(s), {3} voice, {4} untrusted; {5} sitting placed -> {6}".format(
        prov, names.get(area, area), len(trusted), len(voice), len(untrusted),
        sum(1 for r in rows if r["column"] != "0" and r["sitting"]), path))
    log("    " + "  ".join("{0} x{1}".format(c, tally[c]) for c in stance.COLUMNS))
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prov", required=True)
    ap.add_argument("--area", type=int)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--stance", default=STANCE_PATH)
    args = ap.parse_args(argv)
    if args.prov in CONSENSUS:
        print("{0} is a consensus legislature: evidence lists only, no 5CA".format(args.prov))
        return 1
    if not args.all and args.area is None:
        ap.error("--area N or --all")
    import yaml
    with open(os.path.join(ROOT, "config", "stance_overrides.yaml"), encoding="utf-8") as h:
        excluded = {int(a) for a in (yaml.safe_load(h) or {}).get("excluded_from_5ca") or []}
    if args.area in excluded:
        print("area {0} is collated only, not a 5CA area".format(args.area))
        return 1
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    conn = db.init_db(db.connect(args.db))
    entries = load_stance(args.stance, "divisions")
    bill_entries = load_stance(args.stance, "bills")
    areas = sorted(a for a in names if a not in excluded) if args.all else [args.area]
    written = sum(run(conn, args.prov, a, entries, bill_entries, names, args.out_dir) is not None
                  for a in areas)
    every = list(entries.values()) + list(bill_entries.values())
    counts = {k: sum(1 for e in every if status(e) == k) for k in ("confirmed", "draft", "unread", "unplaceable")}
    print("\n{0} sheet(s). config/prov_stance.yaml: {confirmed} confirmed, {draft} draft, {unread} "
          "unread, {unplaceable} never-placeable. A draft or unread entry places NOBODY.".format(
              written, **counts))
    print("  Target is blank: the campaigner's call. Never posted anywhere. Generated {0}.".format(
        datetime.date.today().isoformat()))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
