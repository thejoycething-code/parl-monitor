"""The 5CA's Evaluate phase, measured (13 September 2026).

The Plan sheet says where each member sits before a vote; the division says
how they voted. This puts the two side by side for one signed-off division: the
sheet as it stood the day BEFORE the vote (suggest_rows as_at), against the
lobbies from the ledger. Out of it come the numbers that were worked by hand for
the Second Reading on 12 September: how many ++ voted our way, how the flagged
members (WAVERING, CONFLICTING, TARGETED) moved against the unflagged base, and
the two lists a campaigner wants -- members placed on our side who voted against
(misses) and members placed against us who voted our way (gains). Banked under
data/5ca-eval/<division>.json so the flags are judged every vote, not once.
"""

import json
import os

COLUMNS = ("++", "+", "0", "-", "--")
OURS = {"++", "+"}
THEIRS = {"-", "--"}


def votes_for(conn, division_id):
    """{member_id: 'aye'|'no'|'both'|'absent'} from the ledger's division refs."""
    out = {}
    for mid, ref in conn.execute("SELECT member_id, ref FROM mp_events WHERE ref LIKE ?", ("div:c%d:%%" % int(division_id),)):
        out[mid] = ref.rsplit(":", 1)[1]
    return out


def outcome(vote, our_side):
    """'ours' | 'against' | 'abstained' | None (did not vote, not recorded absent)."""
    if vote is None:
        return None
    if vote in ("both", "absent"):
        return "abstained"
    return "ours" if vote == our_side else "against"


def evaluate(rows, votes, our_side):
    """rows: suggest_rows output (member_id, name, column, wavering, conflict, targeted).
    votes: votes_for output. Returns the calibration record (JSON-able)."""
    by_col = {c: {"n": 0, "ours": 0, "against": 0, "abstained": 0, "silent": 0} for c in COLUMNS}
    flags = {f: {"n": 0, "ours": 0, "against": 0, "abstained": 0, "silent": 0} for f in ("wavering", "conflict", "targeted", "none")}
    moved_from_theirs = {"flagged": [0, 0], "unflagged": [0, 0]}      # [moved or abstained, total] among members placed - or -- who voted or were recorded absent
    missing_from_theirs = {"flagged": [0, 0], "unflagged": [0, 0]}    # [moved, abstained OR did not vote, total] among ALL members placed - or --
    misses, gains = [], []
    for r in rows:
        col = r.get("column", "0")
        o = outcome(votes.get(r["member_id"]), our_side)
        key = o or "silent"
        by_col.setdefault(col, {"n": 0, "ours": 0, "against": 0, "abstained": 0, "silent": 0})
        by_col[col]["n"] += 1
        by_col[col][key] += 1
        has_flag = False
        for f in ("wavering", "conflict", "targeted"):
            if r.get(f):
                has_flag = True
                flags[f]["n"] += 1
                flags[f][key] += 1
        if not has_flag:
            flags["none"]["n"] += 1
            flags["none"][key] += 1
        if col in THEIRS:
            bucket = "flagged" if (r.get("wavering") or r.get("conflict")) else "unflagged"
            missing_from_theirs[bucket][1] += 1
            if o != "against":
                missing_from_theirs[bucket][0] += 1
            if o is not None:
                moved_from_theirs[bucket][1] += 1
                if o in ("ours", "abstained"):
                    moved_from_theirs[bucket][0] += 1
        entry = {"member_id": r["member_id"], "name": r.get("name") or r.get("decision_maker"), "party": r.get("party"), "column": col,
                 "vote": votes.get(r["member_id"]), "flags": [f for f in ("wavering", "conflict", "targeted") if r.get(f)]}
        if col in OURS and o == "against":
            misses.append(entry)
        if col in THEIRS and o == "ours":
            gains.append(entry)
    voted = sum(v["ours"] + v["against"] for v in by_col.values())
    ours_total = sum(v["ours"] for v in by_col.values())
    return {"our_side": our_side, "columns": by_col, "flags": flags, "moved_from_theirs": moved_from_theirs, "missing_from_theirs": missing_from_theirs,
            "misses": misses, "gains": gains, "voted": voted, "ours": ours_total,
            "placed_rows": len(rows), "voters_placed": sum(1 for r in rows if r["member_id"] in votes)}


def _pct(a, b):
    return "%d%%" % round(100.0 * a / b) if b else "-"


def render(rec, title, date, division_id, as_at):
    L = ["# 5CA Evaluate: %s (division %s, %s)" % (title, division_id, date), "",
         "Sheet as at %s (the day before the vote) against the lobbies. Our side: %s. %d rows placed, %d of them voted or were recorded absent."
         % (as_at, rec["our_side"].upper(), rec["placed_rows"], rec["voters_placed"]), "",
         "## Where each column went", "", "| Column | Members | Our way | Against | Abstained/absent | Did not vote | Our way of those voting |", "|---|---|---|---|---|---|---|"]
    for c in COLUMNS:
        v = rec["columns"].get(c, {"n": 0, "ours": 0, "against": 0, "abstained": 0, "silent": 0})
        L.append("| %s | %d | %d | %d | %d | %d | %s |" % (c, v["n"], v["ours"], v["against"], v["abstained"], v["silent"], _pct(v["ours"], v["ours"] + v["against"])))
    L += ["", "## The flags", "", "| Flag | Members | Our way | Against | Abstained/absent | Did not vote |", "|---|---|---|---|---|---|"]
    for f in ("wavering", "conflict", "targeted", "none"):
        v = rec["flags"][f]
        L.append("| %s | %d | %d | %d | %d | %d |" % (f.upper() if f != "none" else "no flag", v["n"], v["ours"], v["against"], v["abstained"], v["silent"]))
    m, x = rec["moved_from_theirs"], rec["missing_from_theirs"]
    L += ["", "Of members placed against us (- or --) who voted or were recorded absent: flagged WAVERING or CONFLICTING moved to us or abstained %d of %d (%s); unflagged %d of %d (%s)."
          % (m["flagged"][0], m["flagged"][1], _pct(*m["flagged"]), m["unflagged"][0], m["unflagged"][1], _pct(*m["unflagged"])),
          "Counting members who did not vote at all as movement (staying away is the movement a losing side needs): flagged %d of %d (%s); unflagged %d of %d (%s)."
          % (x["flagged"][0], x["flagged"][1], _pct(*x["flagged"]), x["unflagged"][0], x["unflagged"][1], _pct(*x["unflagged"]))]
    L += ["", "## Misses: placed with us, voted against (%d)" % len(rec["misses"]), ""]
    L += ["* %s at %s%s" % (e["name"], e["column"], (" [" + ", ".join(e["flags"]) + "]") if e["flags"] else "") for e in rec["misses"]] or ["* none"]
    L += ["", "## Gains: placed against us, voted our way (%d)" % len(rec["gains"]), ""]
    L += ["* %s at %s%s" % (e["name"], e["column"], (" [" + ", ".join(e["flags"]) + "]") if e["flags"] else "") for e in rec["gains"]] or ["* none"]
    return "\n".join(L) + "\n"


def bank(root, division_id, rec, md):
    d = os.path.join(root, "data", "5ca-eval")
    os.makedirs(d, exist_ok=True)
    json.dump(rec, open(os.path.join(d, "%s.json" % division_id), "w"), indent=1)
    open(os.path.join(d, "%s.md" % division_id), "w", encoding="utf-8").write(md)
    return os.path.join(d, "%s.md" % division_id)
