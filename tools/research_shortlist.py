"""Who to ask, when the 5CA has no answer.

    python3 tools/research_shortlist.py --area 8        # top 20
    python3 tools/research_shortlist.py --area 8 --n 40
    python3 tools/research_shortlist.py --area 9 --party Labour

The 5CA is dense where there have been divisions and near-empty where there
have not: 629 of 650 sitting MPs have assisted-dying evidence, but only 49 have
anything on freedom of religion. Those zeros are honest -- 0 means no evidence,
which tells a campaigner the seat is genuinely open -- but 601 zeros is not a
research plan.

This ranks the zeros by how likely the MP is to HAVE a view that simply is not
recorded, using adjacency DERIVED from the store rather than guessed: 63% of
members with conversion-practices evidence also have sex-based-rights evidence,
so a member with one and not the other is a better ask than a random backbench
zero.

It deliberately does NOT estimate a stance. It says who is worth asking and
what to open the conversation with. Filling a 5CA cell remains a campaigner's
judgement on evidence, which is the same reason RF4 is never auto-filled.
"""

from __future__ import annotations

import collections
import itertools
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel

# Evidence weights, matching the 5CA's own hierarchy: a vote is a commitment,
# a written question is a gesture.
KIND_WEIGHT = {"vote": 5, "debate": 4, "edm": 3, "edm-signed": 2, "pq": 1}


def evidence_by_member(conn, mps):
    """{member_id: {area: weighted evidence}} and {member_id: {area: kinds}}."""
    weight = collections.defaultdict(lambda: collections.Counter())
    kinds = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    for row in conn.execute("SELECT member_id, kind, areas, line FROM mp_events "
                            "WHERE areas IS NOT NULL"):
        if row["member_id"] not in mps:
            continue
        w = KIND_WEIGHT.get(row["kind"], 1)
        for area in json.loads(row["areas"] or "[]"):
            weight[row["member_id"]][area] += w
            kinds[row["member_id"]][area][row["kind"]] += 1
    return weight, kinds


def adjacency(weight, target):
    """{area: predictive value} for every other area, from the store.

    Two factors, because correlation alone ranked badly. P(target | other) is
    the obvious one. The second is DISCRIMINATIVENESS: 642 of 650 members have
    migration evidence, so "has migration evidence" tells you nothing about
    anybody, while 49 have freedom-of-religion evidence and that is a real
    signal. Without it the shortlist ranked members by who had the most
    migration debates -- 120 of them -- which is noise wearing a big number.
    """
    have = collections.Counter()
    both = collections.Counter()
    total = max(len(weight), 1)
    for areas in weight.values():
        present = set(areas)
        for a in present:
            have[a] += 1
        for other in present:
            if other != target and target in present:
                both[other] += 1
    out = {}
    for other in have:
        if other == target or not have[other]:
            continue
        correlation = both[other] / have[other]
        discriminating = 1.0 - (have[other] / total)
        out[other] = correlation * discriminating
    return out


def main():
    argv = sys.argv[1:]
    if "--area" not in argv:
        print("need --area N. Sparse areas worth a shortlist: 4, 5, 6, 8, 9, 10.")
        return 1
    target = int(argv[argv.index("--area") + 1])
    limit = int(argv[argv.index("--n") + 1]) if "--n" in argv else 20
    party = argv[argv.index("--party") + 1] if "--party" in argv else None

    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    members = {r["id"]: r for r in conn.execute(
        "SELECT id, name, party, seat FROM members WHERE current_mp = 1")}
    weight, kinds = evidence_by_member(conn, set(members))
    adj = adjacency(weight, target)

    zeros = [m for m in members if not weight[m].get(target)]
    scored = []
    for m in zeros:
        if party and party.lower() not in (members[m]["party"] or "").lower():
            continue
        # sqrt of the evidence weight, not the raw figure: nine debates on
        # conversion practices is a better lead than 120 on migration, and a
        # linear sum says the opposite.
        score = sum((w ** 0.5) * adj.get(a, 0) for a, w in weight[m].items())
        if score <= 0:
            continue
        top = sorted(weight[m].items(),
                     key=lambda kv: -(kv[1] ** 0.5) * adj.get(kv[0], 0))[:3]
        scored.append((score, m, top))
    scored.sort(reverse=True)

    print("\nRESEARCH SHORTLIST — area {0} ({1})".format(target, names.get(target, "?")))
    print("{0} sitting MPs have evidence here; {1} are at zero.".format(
        sum(1 for m in members if weight[m].get(target)), len(zeros)))
    print("Ranked by evidence in areas that PREDICT this one (correlation x")
    print("discriminativeness, so near-universal areas count for almost nothing):")
    for a, p in sorted(adj.items(), key=lambda kv: -kv[1])[:4]:
        print("   area {0:<2} {1:<26} predictive value {2:.2f}".format(
            a, names.get(a, "?")[:26], p))
    if party:
        print("filtered to party matching {0!r}".format(party))
    print()
    for score, m, top in scored[:limit]:
        row = members[m]
        print("  {0:<28} {1:<14} {2}".format(
            (row["name"] or "")[:28], (row["party"] or "")[:14], (row["seat"] or "")[:24]))
        angle = "; ".join("{0} ({1})".format(
            names.get(a, a), ", ".join("%s x%d" % (k, n)
                                       for k, n in kinds[m][a].most_common(2)))
            for a, _w in top)
        print("      open with: {0}".format(angle[:88]))
    print("\n{0} of {1} zeros have some adjacent evidence, so the value here is"
          .format(len(scored), len(zeros)))
    print("the ORDER, not the filter -- the list is a queue, not a set.")
    print()
    print("READ THIS AS: likely to HAVE a view, not likely to AGREE. The top of an")
    print("area-8 list is mostly members who spoke on conversion practices, which")
    print("makes them worth asking and quite possibly opponents. Knowing which is")
    print("the point of asking.")
    print("It says who to ask, never what they think: a 5CA placement stays a")
    print("judgement on evidence, which is why RF4 is never auto-filled either.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
