#!/usr/bin/env python3
"""Apply config/holyrood_votes.yaml to the Scottish record.

    python3 tools/sp_score.py            # report
    python3 tools/sp_score.py --apply    # write sp_scored

Holyrood divided 218 times on the Assisted Dying for Terminally Ill Adults
(Scotland) Bill and 129 MSPs -- every one still sitting -- have a recorded
vote. The store held all of it and nothing said which way any of them went
on our terms.

Three divisions are scored, not 218: the other 215 are Stage 3 amendment
votes with no motion reference and no recorded result, so what each decided
cannot be established from what we hold. Scoring them would be invention.

signed_off gates the verdict here exactly as it does at Westminster: an
unapproved division counts as a receipt and produces no good/bad reading.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db

CONFIG = os.path.join(ROOT, "config", "holyrood_votes.yaml")
# Holyrood records four states; only two are a position.
FOR, AGAINST = "Yes", "No"


def load():
    import yaml
    with open(CONFIG, encoding="utf-8") as handle:
        return (yaml.safe_load(handle) or {}).get("divisions") or []


def main():
    apply_it = "--apply" in sys.argv
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    conn.execute("""CREATE TABLE IF NOT EXISTS sp_scored (
        division_key TEXT NOT NULL, person_id TEXT NOT NULL,
        vote TEXT NOT NULL,          -- Yes | No | Abstain | Not Voted
        verdict TEXT,                -- good | bad | NULL when unsigned
        PRIMARY KEY (division_key, person_id))""")

    scored = load()
    print("{0} division(s) scored in {1}".format(scored and len(scored) or 0,
                                                 os.path.relpath(CONFIG, ROOT)))
    total = 0
    for d in scored:
        row = conn.execute(
            "SELECT title, dated, vote_for, vote_against, result FROM sp_divisions "
            "WHERE key = ?", (d["key"],)).fetchone()
        if row is None:
            print("  [gap] {0}: no such division in the store".format(d["key"]))
            continue
        votes = conn.execute(
            "SELECT person_id, vote FROM sp_votes WHERE division_key = ?",
            (d["key"],)).fetchall()
        ours = d["our_side"]
        good = bad = other = 0
        for v in votes:
            side = ("for" if v["vote"] == FOR else
                    "against" if v["vote"] == AGAINST else None)
            if side is None:
                other += 1
                verdict = None
            else:
                # No verdict at all until the division is signed off -- the
                # same rule the Westminster builder applies.
                verdict = None
                if d.get("signed_off"):
                    verdict = "good" if side == ours else "bad"
                    if verdict == "good":
                        good += 1
                    else:
                        bad += 1
            if apply_it:
                conn.execute(
                    "INSERT INTO sp_scored (division_key, person_id, vote, verdict) "
                    "VALUES (?,?,?,?) ON CONFLICT(division_key, person_id) DO UPDATE "
                    "SET vote=excluded.vote, verdict=excluded.verdict",
                    (d["key"], v["person_id"], v["vote"], verdict))
        total += len(votes)
        mark = "" if d.get("signed_off") else "   [UNSIGNED -- no verdict published]"
        print("\n  {0}  {1}".format(d["dated"], d["short"]))
        print("     {0}".format(str(row["title"])[:88]))
        print("     for {0}, against {1} -- {2}{3}".format(
            row["vote_for"], row["vote_against"], row["result"] or "result not recorded", mark))
        print("     {0} MSP votes; {1} neither for nor against".format(len(votes), other))
        if d.get("signed_off"):
            print("     with us {0}, against us {1}".format(good, bad))
    if apply_it:
        conn.commit()
        print("\n{0} vote(s) written to sp_scored.".format(total))
    else:
        print("\n{0} vote(s) would be written. Re-run with --apply.".format(total))
    print("Stored in sp_scored, not items: this cannot reach the Slack digest.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
