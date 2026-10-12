"""The EU Five Columns Analysis: verdicts x roll calls x groups.

    python3 tools/make_eu_5ca.py
    python3 tools/make_eu_5ca.py --db /tmp/copy.db --out /tmp/eu-5ca.csv
    python3 tools/make_eu_5ca.py --signoff-doc       # write docs/5ca-eu-readings.md
    python3 tools/make_eu_5ca.py --sign-from-doc     # apply its ticked boxes

Westminster's 5CA grid built from EP data. Placement is tally-based over
SIGNED-OFF divisions only -- with none signed, the tool says so and
produces nothing, because a grid built on unsigned meanings is the Lords
inversion with a spreadsheet. Columns are the house vocabulary:

  ++  voted our side in every signed division they attended (2+ votes)
  +   voted our side in every signed division attended (1 vote)
  0   no signed division attended, or abstained throughout
  -   voted against us in some attended division (mixed record)
  --  voted against us in every signed division attended

Group cohesion rides in the Comments column: the EP has no whip, so "one
of 41 EPP voting against the group's 140" is the pressure-map fact a
campaigner needs. Output: briefs/eu-5ca.csv in the Brief template's
column shape (Decision-Maker | Country | Group | Column | Comments).

THE ABSENCE RULE (Westminster, 21 September 2026; the EU from 9 October
2026). A member at ++ who was in the chamber on the day of the latest signed
division -- they cast a vote on something that sitting day -- but cast no
favour or against on it (absent from that roll call, or abstaining) is capped
at +, with the reason in Comments. ++ means "will vote with us"; a member who
sat that day and did not is the contact list. Every signed EU reading counts
as decisive: the EU file has no weaker +1/-1 scale. A member absent the whole
day is not capped -- the EP records no reason, and a mission or sick day is
not a choice.

Drafts: config/eu_divisions.yaml also holds DRAFT readings (`draft: true`,
`signed_off: false`) written by Claude for Christopher to sign. They place
nobody: only signed_off counts. The sign-off guide is docs/5ca-eu-readings.md
(src/eureadings.py).

Reads only; never writes the store.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, eureadings

OUT = os.path.join(ROOT, "briefs", "eu-5ca.csv")
CONFIG = os.path.join(ROOT, "config", "eu_divisions.yaml")
DOC = os.path.join(ROOT, "docs", "5ca-eu-readings.md")


def signed_divisions(conn, path=None):
    cfg = eureadings.load(path or CONFIG)
    out = []
    for vote_id, c in cfg.items():
        if not (c.get("signed_off") and c.get("our_side")):
            continue
        row = conn.execute("SELECT * FROM eu_divisions WHERE vote_id = ?",
                           (vote_id,)).fetchone()
        if row:
            out.append({"vote_id": vote_id, "short": c.get("short"),
                        "our_side": c["our_side"], "date": row["date"]})
    out.sort(key=lambda d: (d["date"] or "", d["vote_id"]))
    return out


def present_on(conn, date):
    """Members who cast any vote (favour, against or abstention) on any roll
    call that sitting day: in the chamber, by the only record the EP keeps."""
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT v.person_id FROM eu_votes v JOIN eu_divisions d "
        "ON d.vote_id = v.vote_id WHERE d.date = ?", (date,))}


def placements(conn, divisions):
    meps = {r["person_id"]: dict(r) for r in
            conn.execute("SELECT * FROM eu_meps").fetchall()}
    votes = {}
    for r in conn.execute("SELECT * FROM eu_votes").fetchall():
        votes.setdefault(r["person_id"], {})[r["vote_id"]] = r["position"]
    group_split = {}   # (vote_id, group) -> {favor, against}
    for pid, vv in votes.items():
        g = (meps.get(pid) or {}).get("group_label") or "Unknown"
        for vote_id, pos in vv.items():
            k = (vote_id, g)
            group_split.setdefault(k, {"favor": 0, "against": 0,
                                       "abstention": 0})
            group_split[k][pos] += 1
    latest = divisions[-1] if divisions else None
    present = present_on(conn, latest["date"]) if latest else set()
    rows = []
    for pid, m in meps.items():
        withs = againsts = 0
        notes = []
        for d in divisions:
            pos = (votes.get(pid) or {}).get(d["vote_id"])
            if pos in (None, "abstention"):
                continue
            with_us = (pos == "favor") == (d["our_side"] == "favor")
            g = m.get("group_label") or "Unknown"
            split = group_split.get((d["vote_id"], g),
                                    {"favor": 0, "against": 0})
            mine = split[pos]
            other = split["against" if pos == "favor" else "favor"]
            if with_us:
                withs += 1
                if mine < other:
                    notes.append("with us AGAINST their group on {0} "
                                 "({1} of {2} {3})".format(
                                     d["short"], mine, mine + other, g))
            else:
                againsts += 1
                if mine < other:
                    notes.append("against us, defying their group, on {0}"
                                 .format(d["short"]))
        if withs and not againsts:
            col = "++" if withs >= 2 else "+"
            got = (votes.get(pid) or {}).get(latest["vote_id"]) if latest else None
            if col == "++" and pid in present and got in (None, "abstention"):
                col = "+"
                notes.insert(0, "CAPPED at +: in the chamber on {0} but {1} on the "
                                "latest signed division ({2}, {3})".format(
                                    latest["date"], "abstained" if got else "cast no vote",
                                    latest["short"], latest["vote_id"]))
        elif againsts and not withs:
            col = "--"
        elif withs and againsts:
            col = "-"
        else:
            col = "0"
        rows.append({"name": m.get("name"), "country": m.get("country"),
                     "group": m.get("group_label"), "column": col,
                     "comments": "; ".join(notes)})
    order = {"++": 0, "+": 1, "0": 2, "-": 3, "--": 4}
    rows.sort(key=lambda r: (order[r["column"]], r["group"] or "~",
                             r["name"] or "~"))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--config", default=CONFIG)
    ap.add_argument("--signoff-doc", nargs="?", const=DOC, metavar="PATH",
                    help="write the sign-off guide (default docs/5ca-eu-readings.md) and stop")
    ap.add_argument("--sign-from-doc", nargs="?", const=DOC, metavar="PATH",
                    help="sign the readings ticked in the sign-off guide, then stop")
    args = ap.parse_args(argv)
    if args.sign_from_doc:
        eureadings.sign_from_doc(args.config, args.sign_from_doc)
        return 0
    entries = eureadings.load(args.config)
    if args.signoff_doc:
        with open(args.signoff_doc, "w", encoding="utf-8") as h:
            h.write(eureadings.signoff_markdown(entries))
        print("wrote {0}: {1} EU readings ({draft} drafted, {unread} with no direction, "
              "{confirmed} signed, {unplaceable} signed evidence-only)".format(
                  args.signoff_doc, len(entries), **eureadings.counts(entries)))
        return 0
    conn = db.connect(args.db)
    divisions = signed_divisions(conn, args.config)
    if not divisions:
        print("eu-5ca: NO signed-off divisions - the grid is deliberately "
              "not built. Sign verdicts in config/eu_divisions.yaml first; "
              "a grid on unsigned meanings is the Lords inversion with a "
              "spreadsheet.")
        return 0
    rows = placements(conn, divisions)
    out = args.out
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Decision-Maker", "Country", "Group", "Column",
                    "Comments", "Evidence: " + "; ".join(
                        "{0} ({1})".format(d["short"], d["date"])
                        for d in divisions)])
        for r in rows:
            w.writerow([r["name"], r["country"], r["group"], r["column"],
                        r["comments"], ""])
    tally = {}
    for r in rows:
        tally[r["column"]] = tally.get(r["column"], 0) + 1
    print("eu-5ca: {0} MEPs placed over {1} signed division(s) -> {2}"
          .format(len(rows), len(divisions), out))
    print("  " + "  ".join("{0} x{1}".format(c, tally.get(c, 0))
                           for c in ("++", "+", "0", "-", "--")))
    capped = sum(1 for r in rows if r["comments"].startswith("CAPPED"))
    print("  {0} capped at + by the absence rule (latest signed: {1})".format(
        capped, divisions[-1]["vote_id"]))
    print("  config: {confirmed} signed, {unplaceable} signed evidence-only, {draft} DRAFT "
          "(unsigned), {unread} with no direction. Drafts place nobody; sign in "
          "docs/5ca-eu-readings.md, then --sign-from-doc.".format(**eureadings.counts(entries)))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
