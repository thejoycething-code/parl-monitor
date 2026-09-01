"""The EU Five Columns Analysis: verdicts x roll calls x groups.

    python3 tools/make_eu_5ca.py

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

Reads only; never writes the store.
"""

from __future__ import annotations

import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db

OUT = os.path.join(ROOT, "briefs", "eu-5ca.csv")


def signed_divisions(conn):
    import yaml
    path = os.path.join(ROOT, "config", "eu_divisions.yaml")
    cfg = (yaml.safe_load(open(path, encoding="utf-8")) or {}).get(
        "divisions") or {} if os.path.exists(path) else {}
    out = []
    for vote_id, c in cfg.items():
        if not (c.get("signed_off") and c.get("our_side")):
            continue
        row = conn.execute("SELECT * FROM eu_divisions WHERE vote_id = ?",
                           (vote_id,)).fetchone()
        if row:
            out.append({"vote_id": vote_id, "short": c.get("short"),
                        "our_side": c["our_side"], "date": row["date"]})
    return out


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


def main():
    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    divisions = signed_divisions(conn)
    if not divisions:
        print("eu-5ca: NO signed-off divisions - the grid is deliberately "
              "not built. Sign verdicts in config/eu_divisions.yaml first; "
              "a grid on unsigned meanings is the Lords inversion with a "
              "spreadsheet.")
        return 0
    rows = placements(conn, divisions)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
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
          .format(len(rows), len(divisions), OUT))
    print("  " + "  ".join("{0} x{1}".format(c, tally.get(c, 0))
                           for c in ("++", "+", "0", "-", "--")))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
