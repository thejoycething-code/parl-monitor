#!/usr/bin/env python3
"""Read the amendment, motion or resolution a country vote's title only names,
match the country's taxonomy over it, and (gated) apply it to the vote.

    python3 tools/amendment_text.py --cc fr                    # the weekly step
    python3 tools/amendment_text.py --cc fr --budget-seconds 600
    python3 tools/amendment_text.py --cc nl --report           # offline: what the cache says
    python3 tools/amendment_text.py --cc it --db /tmp/scratch.db --limit 50 --no-apply

The country analogue of the UK's clause text (src/clausetext.py); the design
is src/amendtext.py, each country's source and identifiers are in
src/amendtext_<cc>.py. Every fetch goes through src/robots_guard.guard
(robots.txt asked for every URL and every redirect hop; documented APIs exempt).

A run: every candidate vote whose title only names an amendment or motion is
looked up (store cache first: a vote is read once); a vote not yet read is
fetched while --budget-seconds and --limit allow (the rest wait for next
week, said in the log); the taxonomy runs over each text; a match whose
tier-1 term sits in the text's PURPOSE is applied to the division (areas
union, terms, tier 1) for THOSE areas only -- the areas whose own tier-1 term
is in the purpose; every other area of the text, and any other match, is
stored and listed for review only.
Cached matches are re-applied every run with no network, because the
collector's upsert or --reclassify recomputes a division's areas.

Writes amendment_text, the division rows' areas/matched_terms/tier (union
only) and gaps. ONE WRITER AT A TIME on the store: run it from the country's
weekly, after the collector, never beside a Mini job. Exit 0, or 3 when it
recorded gaps (the weekly still publishes).
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import amendtext, db  # noqa: E402

COUNTRIES = ("de", "fr", "nl", "it", "pt", "es")


def make_reader(cc, client=None, log=print):
    mod = importlib.import_module("src.amendtext_{0}".format(cc))
    if client is None:
        from src.http import HttpClient
        from src import robots_guard
        raw = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
        # guard(): robots.txt asked for every URL and every redirect hop, except
        # the documented machine APIs of robots_guard.DOCUMENTED_APIS (the
        # Tweede Kamer's OData), exactly as the collectors do (#144, #147).
        client = robots_guard.guard(raw, "{0}-amendment-text".format(cc), log=log)
    return mod.make_reader(client)


def report(outcomes, cc, names=None, out=sys.stdout):
    names = names or {}
    flagged = [o for o in outcomes if o.ledger]
    review = [o for o in outcomes if o.labels and not o.ledger]
    new = [o for o in flagged if not set(o.applied) <= set(o.before)]
    gaps = [o for o in outcomes if o.gap]
    read = [o for o in outcomes if o.status == "ok"]
    skipped = [o for o in outcomes if o.status == "skipped"]

    def area_names(areas):
        return ", ".join(names.get(a, str(a)) for a in areas)
    p = lambda *a: print(*a, file=out)  # noqa: E731
    p("{0}: {1} vote(s) name a text; {2} read ({3} from the cache), {4} unreadable, {5} left for "
      "later".format(cc.upper(), len(outcomes), len(read), sum(1 for o in read if o.cached),
                     sum(1 for o in outcomes if o.status == "unreadable"), len(skipped)))
    p("  {0} matched in the text; {1} passed the ledger gate ({2} gained an area they lacked); "
      "{3} gated to review only".format(len(flagged) + len(review), len(flagged), len(new), len(review)))
    if new:
        p("\n  NEWLY FLAGGED (gate passed, area new to the vote):")
        for o in sorted(new, key=lambda o: o.date or ""):
            p("    {0}  {1}  {2}".format(o.key, o.date, (o.title or "")[:110]))
            p("        applies: {0} (before: {1}) | terms: {2}".format(
                area_names(o.applied), area_names(o.before) or "none", ", ".join(o.applied_terms[:8])))
            rest = [a for a in o.areas if a not in o.applied]
            if rest:
                p("        review only (not in the purpose as tier 1): {0}".format(area_names(rest)))
            if o.why:
                p("        {0}".format(o.why[:200]))
    if review:
        p("\n  GATED (matched in the body, not the purpose: stored for review, no member placed):")
        for o in sorted(review, key=lambda o: o.date or "")[:60]:
            p("    {0}  {1}  {2}".format(o.key, o.date, (o.title or "")[:110]))
            p("        areas: {0} | terms: {1}".format(area_names(o.areas), ", ".join(o.terms[:8])))
        if len(review) > 60:
            p("    ...and {0} more".format(len(review) - 60))
    if gaps:
        p("\n  COULD NOT READ ({0}):".format(len(gaps)))
        for o in gaps[:40]:
            p("    {0}  {1}  {2}: {3}".format(o.key, o.date, (o.title or "")[:70], o.gap))
        if len(gaps) > 40:
            p("    ...and {0} more".format(len(gaps) - 40))


def area_names():
    try:
        from src.digest import AREA_NAMES
        return dict(AREA_NAMES)
    except Exception:                                   # noqa: BLE001 - names are cosmetic
        return {}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cc", required=True, choices=COUNTRIES)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--budget-seconds", type=float, default=None)
    ap.add_argument("--limit", type=int, default=None, help="new votes fetched at most this run")
    ap.add_argument("--no-apply", action="store_true", help="match and store, but leave divisions alone")
    ap.add_argument("--report", action="store_true", help="offline: re-match the cache, fetch nothing")
    ap.add_argument("--json", help="write the outcomes here as JSON")
    args = ap.parse_args(argv)

    conn = db.connect(args.db)
    db.init_db(conn)
    reader = make_reader(args.cc)
    outcomes = amendtext.run(conn, reader, budget_seconds=args.budget_seconds,
                             limit=0 if args.report else args.limit, apply=not args.no_apply,
                             record_gaps=not args.report)
    report(outcomes, args.cc, area_names())
    if args.json:
        with open(args.json, "w") as fh:
            json.dump([o.__dict__ for o in outcomes], fh, ensure_ascii=False, indent=1)
    return 3 if any(o.gap for o in outcomes) and not args.report else 0


if __name__ == "__main__":
    sys.exit(main())
