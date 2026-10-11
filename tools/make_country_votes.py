#!/usr/bin/env python3
"""Build the new countries' vote pages, the vote tracker and the bill
timelines (src/country_votes.py).

    python3 tools/make_country_votes.py                 # every country, the weekly step
    python3 tools/make_country_votes.py --country pl --country hr
    python3 tools/make_country_votes.py --db /tmp/hr.db --country hr --out /tmp/site --sample

Writes into partner_site/ (behind the partner passphrase; Monday's deploy
ships it):
  <cc>-votes.html        one page per country with votes on our ground;
  votes-countries.html   the multi-country tracker;
  bill-timelines.html    the watched bills' timelines.
A country with no vote on our ground gets no page (a stale one is removed),
so the partner index never links an empty page. With --country, only those
countries are rebuilt and the tracker and timelines cover only them, so the
weekly step runs without it.

Read-only on the store and the config: no fetch, no post, no DM, no AI call.
Run by jobs/editions-session-judge.sh (Sundays 16:45 London, after the last
country weekly). Exit 0 when every country rendered, 1 when one failed (its
error printed; the others still rendered).
"""

from __future__ import annotations

import argparse
import datetime
import os
import sqlite3
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country_votes as cv  # noqa: E402


def _write(path, text):
    old = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            old = fh.read()
    if old != text:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    return len(text.encode("utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--country", action="append", help="country code (repeatable); default "
                    "every country: " + " ".join(cv.COUNTRIES))
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--out", default=os.path.join(ROOT, "partner_site"))
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--sample", action="store_true",
                    help="mark every page SAMPLE (a scoping store, never published)")
    args = ap.parse_args(argv)
    countries = args.country or list(cv.COUNTRIES)
    bad = [c for c in countries if c not in cv.COUNTRIES]
    if bad:
        ap.error("no vote page for: " + ", ".join(bad))
    if not os.path.exists(args.db):
        print("country-votes: no store at {0}".format(args.db))
        return 1
    os.makedirs(args.out, exist_ok=True)
    conn = sqlite3.connect("file:{0}?mode=ro".format(args.db), uri=True)
    rc, datas, tls = 0, [], []
    for cc in countries:
        path = os.path.join(args.out, cv.page_name(cc))
        try:
            data = cv.build(conn, cc, args.date)
        except Exception:  # one country's failure never costs the others
            traceback.print_exc()
            print("  [gap] country-votes {0}: failed; last week's page stands".format(cc))
            rc = 1
            continue
        if not data["divisions"]:
            if os.path.exists(path):
                os.remove(path)
            print("country-votes {0}: no vote on our ground; no page".format(cc))
        else:
            size = _write(path, cv.render_page(data, sample=args.sample))
            datas.append(data)
            c = data["counts"]
            print("country-votes {0}: {1} vote(s) on our ground, {2} listed, {3} member(s); "
                  "positions {4} recorded at the vote, {5} as listed (X6), {6} derived (X5); "
                  "readings {7} confirmed, {8} awaiting -> {9} ({10:,} bytes)".format(
                      cc, data["total"], data["shown"], len(data["members"]), c["recorded"],
                      c["as_listed"], c["derived"], c["confirmed"], c["awaiting"],
                      os.path.relpath(path, ROOT) if path.startswith(ROOT) else path, size))
        try:
            tl = cv.timelines(conn, cc, args.date)
        except Exception:
            traceback.print_exc()
            print("  [gap] bill timelines {0}: failed".format(cc))
            rc = 1
            tl = []
        tls.append((cc, cv.mp.country_name(cc), tl))
    tracker = os.path.join(args.out, "votes-countries.html")
    size = _write(tracker, cv.render_tracker(datas, args.date, sample=args.sample))
    print("country-votes: tracker, {0} countries -> {1} ({2:,} bytes)".format(
        len(datas), tracker, size))
    timeline = os.path.join(args.out, "bill-timelines.html")
    tls.sort(key=lambda t: t[1])
    size = _write(timeline, cv.render_timelines(tls, args.date, sample=args.sample))
    print("country-votes: bill timelines, {0} watched bill(s) -> {1} ({2:,} bytes)".format(
        sum(len(t) for _c, _n, t in tls), timeline, size))
    if not any(d["readings"]["confirmed"] for d in datas):
        print("NO CONFIRMED READINGS: every page shows the record and labels nobody.")
    conn.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
