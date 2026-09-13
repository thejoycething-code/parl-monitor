#!/usr/bin/env python3
"""Name today's key debate, if there was one.

    python3 tools/debate_today.py               # today, both Houses
    python3 tools/debate_today.py --date 2026-09-11

Prints the day's debates whose titles are on our ground with their speaker
counts, and a final line "KEY DEBATE: <house> | <title> | <ext id> | N speakers"
or "KEY DEBATE: none". The standing evening task reads that line and builds the
pack (tools/debate_pack.py --date D --debate <ext id> --house H) only when there
is one. Exit 0 either way; exit 2 when Hansard has nothing for the day yet.
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import debatetoday as dt  # noqa: E402
from src import filter as filt  # noqa: E402
from src.http import HttpClient  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default=dt.today_london())
    ap.add_argument("--key", type=int, default=dt.KEY_SPEAKERS, help="speakers that make a key debate")
    args = ap.parse_args()
    import make_vote_tracker
    cfg = make_vote_tracker.load_config()
    terms = {}
    for i in cfg.get("issues") or []:
        for t in i.get("debate_match") or []:
            terms.setdefault(t, i.get("area"))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    client = HttpClient(os.path.join(ROOT, "data", "raw"))
    cands = dt.candidates(client, args.date, tax, wl, terms)
    rows = dt.sized(client, args.date, cands)
    print(dt.report(rows, args.date, key=args.key))
    if not rows and not any(dt.dp._find_debate_once(client, args.date, "", h) for h in dt.HOUSES):
        print("Hansard has no sections for %s yet." % args.date)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
