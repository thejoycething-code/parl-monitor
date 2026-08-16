"""Open OHCHR calls for input, flagged against our issue areas.

    python3 tools/pull_un_calls.py              # everything open, by deadline
    python3 tools/pull_un_calls.py --ours       # only calls touching our areas
    python3 tools/pull_un_calls.py --days 60    # closing within 60 days

The early-warning half of the UN monitor. A call for input is a dated,
named invitation to put written evidence in front of a UN body -- the
analogue of a Commons committee inquiry, and the same kind of thing the
parliamentary monitor raises as an ACT item.

Every open call is listed, not just the matching ones. There are only ever
about fifteen, the taxonomy was built for British parliamentary language
rather than UN thematic titles, and a call missed because a title used
unfamiliar words is a closed door nobody saw. Matching calls are MARKED, not
filtered to.
"""

from __future__ import annotations

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import filter as filt
from src.http import FetchError, HttpClient
from src.ingest import ohchr_calls

UN_TAXONOMY = os.path.join(ROOT, "config", "un-taxonomy.yaml")
WATCHLIST = os.path.join(ROOT, "config", "watchlist.yaml")


def load_un_filter():
    """The UN taxonomy, not the parliamentary one.

    taxonomy.yaml matched ZERO of the fifteen calls open on 2026-08-17: it
    encodes British legislative vocabulary and these are UN thematic titles.
    un-taxonomy.yaml carries the same eleven areas in the UN's words, so a
    match also says WHICH area, which a flat word list never could.
    """
    return filt.load_taxonomy(UN_TAXONOMY), filt.load_watchlist(WATCHLIST)


def areas_for(call, tax, wl):
    return filt.filter_item(tax, wl, ohchr_calls.match_text(call)).issue_areas


def main():
    days = None
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    ours_only = "--ours" in sys.argv

    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax, wl = load_un_filter()

    try:
        calls = ohchr_calls.fetch_calls(client)
    except FetchError as exc:
        print("OHCHR calls for input: fetch failed ({0})".format(exc))
        return 1
    if not calls:
        # The listing is scraped HTML with no JSON alternative, so an empty
        # parse is far more likely to be a layout change than a genuinely
        # empty page. Say so instead of reporting "no calls open".
        print("OHCHR calls for input: parsed ZERO calls. The listing layout "
              "has probably changed -- check src/ingest/ohchr_calls.py before "
              "believing there is nothing open.")
        return 1

    live = ohchr_calls.open_calls(calls, horizon_days=days)
    flagged = 0
    print("{0} call(s) open{1}, of {2} listed\n".format(
        len(live), " within {0} days".format(days) if days else "", len(calls)))
    for call in live:
        hits = areas_for(call, tax, wl)
        ours = bool(hits)
        if ours:
            flagged += 1
        elif ours_only:
            continue
        mark = "OURS" if ours else "    "
        areas = ("  areas " + ", ".join(str(a) for a in hits)) if ours else ""
        print("{0}  {1}  {2:>4}d  {3}{4}".format(
            mark, call.deadline, call.days_left, call.title[:64], areas))
        print("        {0} | {1}".format(call.body[:44], call.url))

    print("\n{0} call(s) match our areas.".format(flagged))
    soon = [c for c in live if c.days_left <= 30]
    if soon:
        print("CLOSING WITHIN 30 DAYS: {0}".format(len(soon)))
        for c in soon:
            print("  {0} ({1}d) {2}".format(c.deadline, c.days_left, c.title[:60]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
