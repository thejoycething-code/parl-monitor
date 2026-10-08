#!/usr/bin/env python3
"""The blind sample for the Canada agreement test (Q4 2026 Rock 2).

    python3 tools/review_sample.py --round R1               # print the sample's shape
    python3 tools/review_sample.py --round R1 --write       # data/review/R1/{items,ours}.json

Christopher, 8 October 2026: "Option 1, private claude.ai page, members
only". Greg scores a sample of members BLIND -- before he can see ours --
and the round passes at >=80% same-or-one-step and <=5% opposite sign.

THE UNIT is one member on one issue area, as the 5CA sheets place them: a
member's column (++ + 0 - --) on that area's sheet, computed by the sheets'
own build_rows from CONFIRMED readings only (a draft places nobody, so a
draft can never enter a sample). Only SITTING members whose column is not
"0" are drawn: a "0" member has no confirmed reading to compare. One area
per member, chosen at random among the areas that place them, so the
sample spreads over people rather than piling one member's six sheets in.

THE SAMPLE: 30 federal (Commons and Senate together) and 50 provincial,
at least 5 per scored province and the rest in proportion to each
province's placed population. NL and Nova Scotia are EXEMPT (Christopher,
8 October 2026: "Option 1" -- no recorded division on our ground places a
sitting member there), as PEI is (not collected). A province with fewer
than 5 placed members gives all it has, and the shortfall is printed.

TWO FILES, so the blind holds on the server and not only on screen:
items.json carries what the reviewer sees (name, party, seat, area) and
NO column; ours.json carries our column and evidence lines, loaded into a
collection the review page's rules hide from the reviewer until the round
is revealed. The draw is seeded by the round name: the same store and
stance files give the same sample.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SCORED_PROVS = ("ab", "sk", "bc", "mb", "on", "qc", "nb")
EXEMPT_PROVS = ("nl", "ns", "pe")
PROV_NAMES = {"ab": "Alberta", "sk": "Saskatchewan", "bc": "British Columbia", "mb": "Manitoba",
              "on": "Ontario", "qc": "Quebec", "nb": "New Brunswick"}
FEDERAL, PROVINCIAL, MIN_PER_PROV = 30, 50, 5
OUT_DIR = os.path.join(ROOT, "data", "review")


def _excluded():
    import yaml
    with open(os.path.join(ROOT, "config", "stance_overrides.yaml"), encoding="utf-8") as h:
        return {int(a) for a in (yaml.safe_load(h) or {}).get("excluded_from_5ca") or []}


def population(conn, names, excluded):
    """{stratum: {member_id: [candidate dict, ...]}} -- one candidate per
    placing area. Strata: 'federal' and each scored province."""
    ca, prov = _load("ca_5ca"), _load("prov_5ca")
    areas = sorted(a for a in names if a not in excluded)
    pop = {"federal": {}}
    ca_entries, ca_bills = ca.load_stance(section="divisions"), ca.load_stance(section="bills")
    for chamber in ("commons", "senate"):
        for area in areas:
            for r in ca.build_rows(conn, area, chamber, ca_entries, ca_bills)[0]:
                if r["sitting"] and r["column"] != "0":
                    pid = "{0}:{1}".format(chamber, r["person_id"])
                    pop["federal"].setdefault(pid, []).append({
                        "member_id": pid, "jurisdiction": "Federal",
                        "chamber": "House of Commons" if chamber == "commons" else "Senate",
                        "member": r["decision_maker"], "party": r["party"], "area": area,
                        "area_name": names[area], "column": r["column"], "evidence": r["comments"],
                        "based_on": r["based_on"]})
    p_entries, p_bills = prov.load_stance(prov.STANCE_PATH, "divisions"), prov.load_stance(prov.STANCE_PATH, "bills")
    for code in SCORED_PROVS:
        pop[code] = {}
        for area in areas:
            for r in prov.build_rows(conn, code, area, p_entries, p_bills)[0]:
                if r["sitting"] and r["column"] != "0":
                    pid = "{0}:{1}".format(code, r["key"])
                    pop[code].setdefault(pid, []).append({
                        "member_id": pid, "jurisdiction": PROV_NAMES[code], "chamber": "Legislature",
                        "member": r["decision_maker"], "party": r["party"], "area": area,
                        "area_name": names[area], "column": r["column"], "evidence": r["comments"],
                        "based_on": r["based_on"]})
    return pop


def allocate(sizes, total=PROVINCIAL, floor=MIN_PER_PROV):
    """{prov: n}: `floor` each (or all a province has), the rest in
    proportion to what remains in each, largest remainders first."""
    take = {p: min(floor, n) for p, n in sizes.items()}
    left = total - sum(take.values())
    spare = {p: sizes[p] - take[p] for p in sizes}
    pool = sum(spare.values())
    if left <= 0 or pool <= 0:
        return take
    shares = {p: left * spare[p] / pool for p in sizes}
    for p in sizes:
        take[p] += min(spare[p], int(shares[p]))
    order = sorted(sizes, key=lambda p: (shares[p] - int(shares[p])), reverse=True)
    i = 0
    while sum(take.values()) < total and any(take[p] < sizes[p] for p in sizes):
        p = order[i % len(order)]
        if take[p] < sizes[p]:
            take[p] += 1
        i += 1
    return take


def draw(pop, round_name, federal=FEDERAL, provincial=PROVINCIAL):
    """(items, ours, report). Seeded by the round name."""
    seed = int(hashlib.sha256(round_name.encode()).hexdigest()[:12], 16)
    rng = random.Random(seed)
    picked = []
    fed_ids = sorted(pop["federal"])
    for pid in rng.sample(fed_ids, min(federal, len(fed_ids))):
        picked.append(rng.choice(pop["federal"][pid]))
    sizes = {p: len(pop[p]) for p in SCORED_PROVS}
    alloc = allocate(sizes, provincial)
    for p in SCORED_PROVS:
        ids = sorted(pop[p])
        for pid in rng.sample(ids, alloc[p]):
            picked.append(rng.choice(pop[p][pid]))
    rng.shuffle(picked)
    items, ours = [], []
    for n, c in enumerate(picked, 1):
        item_id = "{0}-{1:03d}".format(round_name, n)
        items.append({"id": item_id, "round": round_name, "seq": n, "jurisdiction": c["jurisdiction"],
                      "chamber": c["chamber"], "member": c["member"], "party": c["party"],
                      "area": c["area"], "area_name": c["area_name"]})
        ours.append({"id": item_id, "round": round_name, "column": c["column"],
                     "based_on": c["based_on"], "evidence": c["evidence"][:12]})
    report = {"federal_population": len(fed_ids), "federal_drawn": min(federal, len(fed_ids)),
              "provinces": {p: {"population": sizes[p], "drawn": alloc[p],
                                "short": max(0, MIN_PER_PROV - alloc[p])} for p in SCORED_PROVS},
              "exempt": list(EXEMPT_PROVS), "items": len(items)}
    return items, ours, report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--round", required=True, help="round name, e.g. R1 (also the seed)")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--write", action="store_true", help="write data/review/<round>/items.json and ours.json")
    args = ap.parse_args(argv)
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    conn = db.init_db(db.connect(args.db))
    items, ours, report = draw(population(conn, names, _excluded()), args.round)
    print(json.dumps(report, indent=2))
    short = [p for p, r in report["provinces"].items() if r["short"]]
    if short:
        print("SHORT of {0} placed members: {1} -- confirm more readings there".format(
            MIN_PER_PROV, ", ".join(short)))
    if args.write:
        out = os.path.join(OUT_DIR, args.round)
        os.makedirs(out, exist_ok=True)
        for name, rows in (("items.json", items), ("ours.json", ours)):
            with open(os.path.join(out, name), "w", encoding="utf-8") as h:
                json.dump(rows, h, ensure_ascii=False, indent=1)
        print("wrote {0} item(s) to {1}".format(len(items), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
