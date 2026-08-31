"""Every Commons division of this Parliament, and what it says about loyalty.

    python3 tools/pull_division_rolls.py

Two jobs, one tool (Christopher, 2026-08-31: whole-record party alignment
and willingness to defy a whip, for the 5CA):

1. COLLECT: page the Commons Votes API for every division since the 2024
   general election, fetch the full lists for any division not yet held,
   and store one compact row per member per division (cv_divisions /
   cv_votes). The payloads are NOT archived to data/raw: 575 of them would
   put ~30MB into git for bytes the rows already carry. The party stored is
   the one the division list printed THAT DAY, so no join against
   member_party is needed and a floor-crosser is measured against the
   colleagues they actually had.

2. COMPUTE: rebuild mp_alignment (one row per member) and mp_defiance (one
   row per defiance) from the full corpus. "With/against party" compares
   the member's side to their own party's majority in that division;
   "whipped" is the bloc inference the vote tracker already uses -- the two
   largest parties >=98% on opposite sides -- and "defied" is voting
   against your own party's bloc in such a division. These are 5CA-facing
   tables; nothing here reaches the public page.
"""

from __future__ import annotations

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db
from src.http import HttpClient

API = "https://commonsvotes-api.parliament.uk/data"
SINCE = "2024-07-04"               # the general election: this Parliament
PAGE = 25
SIDES = (("Ayes", "A"), ("Noes", "N"), ("AyeTellers", "TA"),
         ("NoTellers", "TN"), ("NoVoteRecorded", "X"))
BLOC_FLOOR = 20                    # same thresholds as the tracker's
BLOC_SHARE = 0.98                  # party_line(): evidence, not vibes


def collect(conn, client):
    have = {r[0] for r in conn.execute("SELECT division_id FROM cv_divisions")}
    skip, index, gaps = 0, [], 0
    while True:
        url = ("{0}/divisions.json/search?queryParameters.startDate={1}"
               "&queryParameters.skip={2}&queryParameters.take={3}").format(
                   API, SINCE, skip, PAGE)
        try:
            batch = client.get_json(url, "cvotes", "search", archive=False)
        except Exception as exc:
            db.record_gap(conn, "division-rolls",
                          "search at skip={0}: {1}".format(skip, exc))
            break
        index.extend(batch)
        if len(batch) < PAGE:
            break
        skip += PAGE

    fetched = 0
    for row in index:
        div_id = row.get("DivisionId")
        if not div_id or div_id in have:
            continue
        try:
            detail = client.get_json(
                "{0}/division/{1}.json".format(API, div_id),
                "cvotes", "detail-{0}".format(div_id), archive=False)
        except Exception as exc:
            gaps += 1
            db.record_gap(conn, "division-rolls",
                          "division {0} ({1}): {2}".format(
                              div_id, (row.get("Date") or "")[:10], exc))
            continue
        conn.execute(
            "INSERT OR REPLACE INTO cv_divisions (division_id, date, title, "
            "ayes, noes) VALUES (?,?,?,?,?)",
            (div_id, (detail.get("Date") or "")[:10],
             detail.get("Title") or "", detail.get("AyeCount"),
             detail.get("NoCount")))
        for key, code in SIDES:
            for m in (detail.get(key) or []):
                if not m.get("MemberId"):
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO cv_votes (division_id, member_id, "
                    "side, party) VALUES (?,?,?,?)",
                    (div_id, m["MemberId"], code, m.get("Party")))
        fetched += 1
        if fetched % 50 == 0:
            conn.commit()
            print("  ...{0} divisions fetched".format(fetched))
    conn.commit()
    return len(index), fetched, gaps


# Labour (Co-op) takes the Labour whip; the tracker merges them and so
# does this, or 43 members would be measured against a phantom party.
MERGE = {"Labour (Co-op)": "Labour"}


def compute(conn):
    """Rebuild mp_alignment and mp_defiance from the corpus, in one pass."""
    divisions = {r["division_id"]: (r["date"], r["title"]) for r in
                 conn.execute("SELECT division_id, date, title FROM cv_divisions")}
    # party tallies per division, from the rolls themselves
    tallies = {}      # div -> party -> [ayes, noes]
    votes = {}        # div -> [(member, side, party)]
    for r in conn.execute("SELECT division_id, member_id, side, party FROM cv_votes"):
        party = MERGE.get(r["party"] or "?", r["party"] or "?")
        votes.setdefault(r["division_id"], []).append(
            (r["member_id"], r["side"], party))
        if r["side"] in ("A", "TA", "N", "TN"):
            t = tallies.setdefault(r["division_id"], {}).setdefault(party, [0, 0])
            t[0 if r["side"] in ("A", "TA") else 1] += 1

    # which parties were bloc-whipped, per division -- the tracker's rule
    whipped = {}      # div -> {party: 'aye'|'no'}
    for div, parties in tallies.items():
        ranked = sorted(parties.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))
        two = [(p, a, n) for p, (a, n) in ranked[:2] if a + n >= BLOC_FLOOR]
        if len(two) != 2:
            continue
        sides = []
        for _p, a, n in two:
            if a >= (a + n) * BLOC_SHARE:
                sides.append("aye")
            elif n >= (a + n) * BLOC_SHARE:
                sides.append("no")
            else:
                sides = None
                break
        if sides and sides[0] != sides[1]:
            whipped[div] = {two[0][0]: sides[0], two[1][0]: sides[1]}

    agg = {}          # member -> [eligible, voted, with, against, whipped, defied]
    conn.execute("DELETE FROM mp_defiance")
    for div, rows in votes.items():
        date, title = divisions.get(div, ("", ""))
        for member, side, party in rows:
            a = agg.setdefault(member, [0, 0, 0, 0, 0, 0])
            a[0] += 1
            if side == "X":
                continue
            a[1] += 1
            t = tallies.get(div, {}).get(party)
            if not t or t[0] == t[1]:
                continue          # no party position to compare against
            mine = t[0] if side in ("A", "TA") else t[1]
            other = t[1] if side in ("A", "TA") else t[0]
            if mine > other:
                a[2] += 1
            else:
                a[3] += 1
            bloc = whipped.get(div, {}).get(party)
            if bloc:
                a[4] += 1
                my_side = "aye" if side in ("A", "TA") else "no"
                if my_side != bloc:
                    a[5] += 1
                    conn.execute(
                        "INSERT OR REPLACE INTO mp_defiance (member_id, "
                        "division_id, date, title, side, party, party_with, "
                        "party_against) VALUES (?,?,?,?,?,?,?,?)",
                        (member, div, date, title, side, party,
                         max(t), min(t)))

    conn.execute("DELETE FROM mp_alignment")
    stamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M")
    until = max((d for d, _ in divisions.values()), default=None)
    for member, a in agg.items():
        conn.execute(
            "INSERT INTO mp_alignment (member_id, since, until, eligible, "
            "voted, with_party, against_party, whipped, defied, computed_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (member, SINCE, until, a[0], a[1], a[2], a[3], a[4], a[5], stamp))
    conn.commit()
    return len(agg), len(whipped), sum(a[5] for a in agg.values())


def main():
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    indexed, fetched, gaps = collect(conn, client)
    members_n, whipped_n, defiances = compute(conn)
    held = conn.execute("SELECT COUNT(*) FROM cv_divisions").fetchone()[0]
    rolls = conn.execute("SELECT COUNT(*) FROM cv_votes").fetchone()[0]
    print("division rolls: {0} divisions indexed, {1} fetched this run, "
          "{2} gap(s); {3} divisions / {4} vote rows held".format(
              indexed, fetched, gaps, held, rolls))
    print("alignment: {0} members computed; {1} bloc-whipped divisions; "
          "{2} defiances on record".format(members_n, whipped_n, defiances))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
