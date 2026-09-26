#!/usr/bin/env python3
"""Scan the Bundestag for vocabulary the German taxonomy does not have.

    python3 tools/de_taxonomy_scan.py            # ~180 paced DIP requests
    python3 tools/de_taxonomy_scan.py --report   # rewrite the report from cache

Christopher, 26 September 2026: "Scan the Bundestag yourself and determine
any additions that need to be made."

THE PROBLEM THIS SOLVES. Verifying the taxonomy earlier the same day
measured its behaviour, and could not escape one limit: the probe list used
to test recall was written from the same understanding that produced the
taxonomy, so it could not find a term neither of them knew. This scan takes
its vocabulary from somewhere else -- the DESCRIPTORS the Bundestag's own
documentation service assigns to every Vorgang ("Sterbehilfe",
typ "Sachbegriffe"). That is a controlled vocabulary, maintained by people
who are not us, applied to every document regardless of what any taxonomy
thinks is interesting.

THE METHOD, a snowball through that thesaurus:

  1. SEED. Every tier-1 term queried as a title, ALL TIME -- no 120-day
     window, because the window is exactly why assisted dying looked
     thin. The Vorgänge that come back are known to be ours.
  2. HARVEST. The descriptors on those Vorgänge, counted per area. A
     descriptor recurring across an area's seeds is the Bundestag's own
     name for that ground.
  3. GAP. Whether the taxonomy matches the descriptor's own name. If it
     does, the concept is covered; if not, it is a candidate.
  4. EXPAND. Each candidate's Vorgänge fetched BY DESCRIPTOR, and the
     taxonomy run over their titles. A descriptor whose Vorgänge the
     taxonomy mostly misses is a real gap, not a synonym.

Step 4 is the one that breaks the circle: those Vorgänge were chosen by the
Bundestag's indexers, not by our terms.

WHAT IT DOES NOT DO. It does not edit the taxonomy. It writes a ranked list
of candidates with their evidence to reviews/, for a person to accept or
reject -- the same rule every other judgement here follows. A descriptor
that is common across our areas can still be the wrong word for a German
reader, and some will be administrative noise that happens to co-occur.

PACING. One request a second. bundestag.de hosts stopped answering this
machine on 24 September after ~2,000 requests in a day; this is ~180.
"""

from __future__ import annotations

import argparse
import collections
import datetime
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import dip, filter as filt, intel  # noqa: E402
from src.http import HttpClient  # noqa: E402

CACHE = os.path.join(ROOT, "data", "de-taxonomy-scan.json")
HIDDEN_AREAS = (11,)          # migration: collated, never campaigned
PAUSE = 1.0
MIN_SEEDS = 3                 # a descriptor must recur within an area
MIN_SHARE = 0.5               # and belong mostly to that area
# Step 4's budget is shared out PER AREA, not taken from the top of one list.
# The first run ranked every candidate by seed count and expanded the top 60:
# migration, which has three times the seeds of anything else and is never
# shown, took 18 of them, and assisted dying, conversion practices, parental
# rights, gender medicine and surrogacy -- the thin areas the scan most
# needed to test -- got NONE. A budget allocated by size spends itself on the
# area that needed it least.
EXPAND_PER_AREA = 10


def _sachbegriffe(vorgang):
    return [d.get("name") for d in (vorgang.get("deskriptor") or [])
            if d.get("typ") == "Sachbegriffe" and d.get("name")]


def fetch_one_page(client, key, **params):
    time.sleep(PAUSE)
    page = next(iter(dip.pages(client, "vorgang", key, limit_pages=1,
                               feed="de-taxscan", slug="scan", log=lambda *a: None,
                               **params)), None)
    return (page or {}).get("documents") or []


def tier1_by_area(tax):
    """{area: [terms]} for the tier-1 terms DIP can use as a title query.

    Same rule as tools/de_documents.py:tier1_terms -- stems lose their *,
    section numbers and very short stems are dropped -- but kept per area,
    because a descriptor is judged against the area that found it.
    """
    out = {}
    for area, tiers in sorted((tax.terms or {}).items()):
        for entry in (tiers.get(1) or []):
            raw = str(entry[0] or "").strip().strip('"').rstrip("*").strip()
            if len(raw) >= 8 and not raw.startswith("§"):
                out.setdefault(area, []).append(raw)
    return {a: sorted(set(t)) for a, t in out.items()}


def run_seed(client, key, tax, log=print):
    found = {}
    for area, terms in tier1_by_area(tax).items():
        for term in terms:
            for v in fetch_one_page(client, key, **{"f.titel": term}):
                row = found.setdefault(str(v["id"]), {
                    "titel": v.get("titel") or "", "datum": v.get("datum"),
                    "areas": set(), "descriptors": _sachbegriffe(v)})
                row["areas"].add(area)
        log("  seed: area %s done, %d Vorgänge so far" % (area, len(found)))
    return found


def harvest(found, tax, wl):
    """Candidate descriptors: recurring within one area, mostly that area's,
    and not matched by the taxonomy under their own name."""
    per_area = collections.defaultdict(collections.Counter)
    overall = collections.Counter()
    for v in found.values():
        for d in set(v["descriptors"]):
            overall[d] += 1
            for a in v["areas"]:
                per_area[a][d] += 1
    out = []
    for area, counts in per_area.items():
        for desc, n in counts.items():
            if n < MIN_SEEDS or n / overall[desc] < MIN_SHARE:
                continue
            res = filt.filter_item(tax, wl, desc, "", "")
            out.append({"descriptor": desc, "area": area, "seeds": n,
                        "share": round(n / overall[desc], 2),
                        "covered": bool(res.issue_areas),
                        "covered_by": res.matched_terms})
    return sorted(out, key=lambda c: (c["covered"], -c["seeds"]))


def expansion_plan(candidates):
    """Up to EXPAND_PER_AREA uncovered descriptors per CAMPAIGNED area, the
    most-recurring first. Migration is skipped outright; its sparseness is
    deliberate. Already-expanded candidates are not fetched again."""
    by_area = collections.defaultdict(list)
    for c in candidates:
        if c["covered"] or c["area"] in HIDDEN_AREAS:
            continue
        by_area[c["area"]].append(c)
    todo = []
    for area in sorted(by_area):
        ranked = sorted(by_area[area], key=lambda c: -c["seeds"])
        todo += [c for c in ranked[:EXPAND_PER_AREA] if "expanded" not in c]
    return todo


def expand(client, key, tax, wl, candidates, log=print):
    """Fetch each uncovered descriptor's Vorgänge and measure the miss rate."""
    todo = expansion_plan(candidates)
    log("  expand: %d descriptor(s) to fetch" % len(todo))
    for i, c in enumerate(todo, 1):
        docs = fetch_one_page(client, key, **{"f.deskriptor": c["descriptor"]})
        missed = []
        for v in docs:
            res = filt.filter_item(tax, wl, v.get("titel") or "", "", "")
            if not res.issue_areas:
                missed.append((v.get("datum") or "", v.get("titel") or ""))
        c["expanded"] = len(docs)
        c["missed"] = len(missed)
        c["samples"] = sorted(missed, reverse=True)[:4]
        if i % 10 == 0:
            log("  expand: %d of %d descriptors" % (i, len(todo)))
    return candidates


def render(candidates, names, found, when):
    real = [c for c in candidates if not c["covered"] and c.get("expanded")]
    real.sort(key=lambda c: (c["area"] in HIDDEN_AREAS, -c["missed"]))
    covered = [c for c in candidates if c["covered"]]
    out = [
        "# German taxonomy scan - {0}".format(when), "",
        "*Vocabulary taken from the Bundestag's own descriptors, not from "
        "ours. Seeded from {0} Vorgänge found by the tier-1 terms across ALL "
        "time; {1} recurring descriptors harvested; {2} already covered by "
        "the taxonomy under their own name; {3} uncovered and expanded.*"
        .format(len(found), len(candidates), len(covered), len(real)), "",
        "**Nothing here has been applied.** Each candidate is the "
        "Bundestag's term, the area whose seeds it recurred in, and how many "
        "of ITS Vorgänge the taxonomy misses by title. Mark each ACCEPT, "
        "REJECT or TIER2 on its DECISION line.", "",
        "Migration (area 11) is listed last: it is collated and never "
        "campaigned, and its sparseness is deliberate.", "", "---", ""]
    for c in real:
        out += ["### {0}".format(c["descriptor"]),
                "- area: {0} | recurs in {1} seed Vorgänge ({2:.0%} of its "
                "appearances) | its own Vorgänge: {3}, of which the taxonomy "
                "MISSES {4}".format(names.get(c["area"], c["area"]), c["seeds"],
                                    c["share"], c["expanded"], c["missed"])]
        for datum, titel in c["samples"]:
            out.append("  - {0} {1}".format(datum, " ".join(titel.split())[:110]))
        out += ["DECISION: ", ""]
    out += ["---", "", "## Already covered (the taxonomy matches the "
            "descriptor's own name)", ""]
    for c in covered:
        out.append("- {0} -> {1} via {2}".format(
            c["descriptor"], names.get(c["area"], c["area"]),
            ", ".join(c["covered_by"][:2])))
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", action="store_true",
                    help="rewrite the report from the cached scan, no requests")
    ap.add_argument("--resume", action="store_true",
                    help="keep the cached seeds and harvest; expand only the "
                         "candidates not yet fetched")
    args = ap.parse_args()
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy-de.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist-de.yaml"))
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy-de.yaml"))
    today = datetime.date.today().isoformat()

    if (args.report or args.resume) and os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as fh:
            saved = json.load(fh)
        found, candidates = saved["found"], saved["candidates"]
        if args.resume:
            client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
            key = dip.api_key(client=client)
            candidates = expand(client, key, tax, wl, candidates)
            with open(CACHE, "w", encoding="utf-8") as fh:
                json.dump({"when": today, "found": found,
                           "candidates": candidates},
                          fh, ensure_ascii=False, indent=1)
    else:
        client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
        key = dip.api_key(client=client)
        found = run_seed(client, key, tax)
        candidates = harvest(found, tax, wl)
        print("harvested %d recurring descriptors, %d uncovered" % (
            len(candidates), sum(1 for c in candidates if not c["covered"])))
        candidates = expand(client, key, tax, wl, candidates)
        for v in found.values():
            v["areas"] = sorted(v["areas"])
        with open(CACHE, "w", encoding="utf-8") as fh:
            json.dump({"when": today, "found": found, "candidates": candidates},
                      fh, ensure_ascii=False, indent=1)

    path = os.path.join(ROOT, "reviews", "de-taxonomy-scan-{0}.md".format(today))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render(candidates, names, found, today))
    print("report -> {0}".format(os.path.relpath(path, ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
