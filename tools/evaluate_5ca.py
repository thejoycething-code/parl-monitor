"""The 5CA's Evaluate phase: score a prediction against the actual vote.

    python3 tools/evaluate_5ca.py div:c2071 --area 2
    python3 tools/evaluate_5ca.py div:c2071 --area 2 --apply

The framework has two halves and we only ever built one. Plan records where
each member is thought to stand; Evaluate records how they actually voted.
Without it the sheets are a standing prediction nobody ever marks, and there
is no way to know whether the evidence hierarchy is any good.

HOW THE PREDICTION IS RECOVERED, and why it is fair. The sheet is rebuilt
`as_at` the division's date, so only evidence from BEFORE the vote counts.
After the vote the vote itself is evidence, and a sheet that included it
would be marking its own homework. No snapshot is needed -- the ledger
carries dates, so any past placement is reconstructable.

WHAT COUNTS AS A MISS, which is most of the design:

  * A member placed at 0 is NOT a miss. Zero means "no evidence", which is
    an honest absence of prediction, not a wrong one. Counting it would
    punish the sheet for admitting what it does not know.
  * An ABSENCE is not a miss either. Someone paired, ill or abroad has not
    contradicted anything.
  * Only members with BOTH a directional placement and a recorded vote can
    be right or wrong, and the hit rate is computed over exactly those.

WHICH LOBBY IS OURS comes from the stance already scored on the division's
own refs (div:cN:aye / :no) -- the same human-reviewable judgement the 5CA
places on. If the division has no scored direction, the tool refuses rather
than guessing.

Dry run by default.
"""

from __future__ import annotations

import collections
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel, stance

OURS = {"++": 1, "+": 1, "-": -1, "--": -1, "0": 0}


def direction(conn, division_ref):
    """(+1 if an AYE is our side, -1 if a NO is) or None if unscored."""
    rows = {r["ref"]: r["stance"] for r in conn.execute(
        "SELECT ref, stance FROM stance WHERE ref IN (?, ?)",
        (division_ref + ":aye", division_ref + ":no"))}
    aye, no = rows.get(division_ref + ":aye"), rows.get(division_ref + ":no")
    if aye is None and no is None:
        return None
    if aye and aye != 0:
        return 1 if aye > 0 else -1
    if no and no != 0:
        return -1 if no > 0 else 1
    return None                     # both scored 0: procedural, no direction


def evaluate(conn, division_ref, area, as_at=None, overrides_cfg=None):
    """(results, meta). Pure enough to test: writes nothing."""
    dates = [r[0] for r in conn.execute(
        "SELECT DISTINCT date FROM mp_events WHERE ref LIKE ? ORDER BY date",
        (division_ref + ":%",))]
    if not dates:
        return [], {"error": "no votes recorded for " + division_ref}
    voted_on = as_at or dates[0]
    ours = direction(conn, division_ref)
    if ours is None:
        return [], {"error": "no scored direction for {0}: score its stance "
                             "first, or it is procedural and means nothing "
                             "for us".format(division_ref)}

    actual = {}
    for r in conn.execute(
            "SELECT member_id, ref FROM mp_events WHERE ref LIKE ?",
            (division_ref + ":%",)):
        actual[r["member_id"]] = r["ref"].rsplit(":", 1)[1]

    rows = stance.suggest_rows(conn, area, full_roster=True,
                               overrides_cfg=overrides_cfg, as_at=voted_on)
    results = []
    for row in rows:
        predicted = row["column"]
        side = OURS.get(predicted, 0)
        vote = actual.get(row["member_id"])
        if side == 0:
            outcome = "no-prediction"
        elif vote is None:
            outcome = "no-vote"
        else:
            voted_our_way = (1 if vote == "aye" else -1) == ours
            outcome = "hit" if (side > 0) == voted_our_way else "miss"
        results.append({"member_id": row["member_id"],
                        "name": row.get("decision_maker") or "",
                        "predicted": predicted, "actual": vote or "absent",
                        "outcome": outcome,
                        # decided_kind is what the placement RESTED ON --
                        # vote, debate, pq, edm. Scoring hit rate by kind is
                        # the whole point: it measures the evidence
                        # hierarchy instead of assuming it.
                        "based_on": row.get("decided_kind") or "none",
                        "conflict": bool(row.get("conflict"))})
    return results, {"voted_on": voted_on, "ours": "aye" if ours > 0 else "no",
                     "division": division_ref, "area": area}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 1
    ref = args[0]
    area = int(sys.argv[sys.argv.index("--area") + 1]) if "--area" in sys.argv else None
    if area is None:
        print("--area is required")
        return 1
    apply_it = "--apply" in sys.argv

    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    cfg = stance.load_overrides(os.path.join(ROOT, "config",
                                             "stance_overrides.yaml"))
    results, meta = evaluate(conn, ref, area, overrides_cfg=cfg)
    if meta.get("error"):
        print(meta["error"])
        return 1

    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    tally = collections.Counter(r["outcome"] for r in results)
    scored = tally["hit"] + tally["miss"]
    print("EVALUATE  {0}  area {1} ({2})".format(
        meta["division"], area, names.get(area, "?")))
    print("  voted {0}; an {1} is our side (from the division's own scored "
          "stance)\n".format(meta["voted_on"], meta["ours"].upper()))
    print("  hit          {0:>4}".format(tally["hit"]))
    print("  miss         {0:>4}".format(tally["miss"]))
    print("  no-prediction{0:>4}   (placed at 0: no evidence, not a wrong "
          "answer)".format(tally["no-prediction"]))
    print("  no-vote      {0:>4}   (absent or paired: contradicts nothing)"
          .format(tally["no-vote"]))
    if scored:
        print("\n  HIT RATE {0:.0f}% over the {1} member(s) who had both a "
              "placement and a vote.".format(100 * tally["hit"] / scored,
                                             scored))
    else:
        print("\n  No member had both a directional placement and a vote: "
              "nothing to score.")

    misses = [r for r in results if r["outcome"] == "miss"]
    if misses:
        print("\n  MISSES -- either the evidence was misread or they moved. "
              "Both are worth a look:")
        for m in misses[:12]:
            print("   {0:<34} predicted {1:<3} voted {2:<4} | on a {3}".format(
                str(m["name"] or m["member_id"])[:34], m["predicted"],
                m["actual"], m["based_on"]))
        if len(misses) > 12:
            print("   ...and {0} more.".format(len(misses) - 12))

    by_basis = collections.Counter()
    for r in results:
        if r["outcome"] in ("hit", "miss"):
            by_basis[(r["based_on"], r["outcome"])] += 1
    if by_basis:
        print("\n  WHICH EVIDENCE PREDICTED, by what the placement rested on:")
        bases = sorted({b for b, _o in by_basis})
        for b in bases:
            h, m = by_basis[(b, "hit")], by_basis[(b, "miss")]
            if h + m:
                print("   {0:<28} {1:>3}/{2:<3} {3:.0f}%".format(
                    b or "?", h, h + m, 100 * h / (h + m)))

    if apply_it:
        now = datetime.date.today().isoformat()
        for r in results:
            conn.execute(
                "INSERT INTO evaluations (division_ref, area, member_id, "
                "predicted, actual, outcome, based_on, evaluated_at) "
                "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(division_ref, area, "
                "member_id) DO UPDATE SET predicted=excluded.predicted, "
                "actual=excluded.actual, outcome=excluded.outcome, "
                "based_on=excluded.based_on, evaluated_at=excluded.evaluated_at",
                (ref, area, r["member_id"], r["predicted"], r["actual"],
                 r["outcome"], r["based_on"], now))
        conn.commit()
        print("\n  {0} row(s) written to evaluations.".format(len(results)))
    else:
        print("\n  dry run; --apply to record this evaluation.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
