#!/usr/bin/env python3
"""What each member has said on an area since they last voted on it, ranked by drift.

    python3 tools/since_last_vote.py --area 2 [--since 2025-06-20] [--top 40] [--write]

For every sitting member with a scored vote on the area, take the events after that
vote (debates, questions, motions) and compare their mean stance with the vote's:
a supporter of the other side whose words since have not been hostile is drifting
our way; one of ours whose words have softened is drifting off. Christopher, 12
Sept 2026: "every PQ, EDM, intervention and local statement since June 2025, ranked
by the change in tone -- the store has all of it; nothing reads it as a trend".
--write puts the digest in data/briefs/since-vote-area<N>.md.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import db  # noqa: E402
import json


def _in_area(areas_json, area):
    try:
        return area in json.loads(areas_json or "[]")
    except ValueError:
        return False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def drift(conn, area, since=None, house="Commons"):
    """[{name, party, seat, vote_date, vote_stance, n_since, mean_since, drift, lines}]
    for members with a scored vote on the area and at least one scored event since."""
    flag = "current_peer" if house == "Lords" else "current_mp"
    out = []
    members = conn.execute("SELECT id, name, party, seat FROM members WHERE %s = 1" % flag).fetchall()
    for mid, name, party, seat in members:
        votes = [v for v in conn.execute(
            "SELECT e.date, s.stance, e.line, e.areas FROM mp_events e JOIN stance s ON s.ref = e.ref "
            "WHERE e.member_id = ? AND e.kind = 'vote' AND s.stance != 0 " + ("AND e.date <= ? " if since else "") + "ORDER BY e.date DESC",
            [mid] + ([since] if since else [])) if _in_area(v[3], area)]
        vote = votes[0] if votes else None
        if not vote:
            continue
        after = [r for r in conn.execute(
            "SELECT e.date, e.kind, s.stance, e.line, e.areas FROM mp_events e JOIN stance s ON s.ref = e.ref "
            "WHERE e.member_id = ? AND e.kind != 'vote' AND e.date > ? ORDER BY e.date", (mid, vote[0])) if _in_area(r[4], area)]
        if not after:
            continue
        mean = sum((r[2] or 0) for r in after) / len(after)
        out.append({"member_id": mid, "name": name, "party": party or "", "seat": seat or "",
                    "vote_date": vote[0], "vote_stance": vote[1], "vote_line": vote[2],
                    "n_since": len(after), "mean_since": mean, "drift": mean - (2 if vote[1] > 0 else -2),
                    "lines": [(r[0], r[1], r[2], (r[3] or "")[:90]) for r in after[-4:]]})
    return out


def digest(rows, area, top=40):
    ours_off = sorted([r for r in rows if r["vote_stance"] > 0 and r["drift"] < 0], key=lambda r: r["drift"])[:top]
    theirs_on = sorted([r for r in rows if r["vote_stance"] < 0 and r["drift"] > 0], key=lambda r: -r["drift"])[:top]
    lines = ["# Since the last vote — area %s" % area, "",
             "*%d members have a scored vote on this area and have said something on it since. Drift is the mean stance of"
             " what they have said since, against the stance of that vote (+2 with us, -2 against): a supporter of the other"
             " side drifting up is a prospect; one of ours drifting down needs a call.*" % len(rows), ""]
    def block(title, rs):
        out = ["## %s (%d)" % (title, len(rs)), ""]
        for r in rs:
            out.append("### %s (%s, %s) — voted %s on %s; %d contribution%s since, mean %+.1f" % (
                r["name"], r["party"], r["seat"], "with us" if r["vote_stance"] > 0 else "against us", r["vote_date"],
                r["n_since"], "" if r["n_since"] == 1 else "s", r["mean_since"]))
            for d, k, st, l in r["lines"]:
                out.append("* %s %s %+d — %s" % (d, k, st or 0, l))
            out.append("")
        return out
    lines += block("Supporters of the other side drifting towards us", theirs_on)
    lines += block("Our side drifting away", ours_off)
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--area", type=int, required=True)
    ap.add_argument("--since", help="use each member's last vote on or before this date")
    ap.add_argument("--house", default="Commons")
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    rows = drift(conn, args.area, args.since, args.house)
    text = digest(rows, args.area, args.top)
    print(text[:4000])
    if args.write:
        os.makedirs(os.path.join(ROOT, "data", "briefs"), exist_ok=True)
        path = os.path.join(ROOT, "data", "briefs", "since-vote-area%d.md" % args.area)
        open(path, "w", encoding="utf-8").write(text)
        print("\n-> %s" % os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main()
