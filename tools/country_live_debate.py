#!/usr/bin/env python3
"""Read a debate mid-flight in a new country: what members said, next to their votes.

    python3 tools/country_live_debate.py nl --find "zorgverzekering"         # today
    python3 tools/country_live_debate.py be --date 2026-10-08 --debate 56/143-13
    python3 tools/country_live_debate.py fr --find "violences" --queue-out /tmp/reads.yaml
    python3 tools/country_live_debate.py fr --find "violences" --reads /tmp/reads.yaml --dm

The new countries' tools/live_debate.py (src/country_live.py). It reads what
the chamber has published so far today (the country's own collector, into a
throwaway in-memory store; the real store is only read), picks the debate
(--debate, the id tools/country_debate_today.py prints, or --find, words of
its title; with neither, the day's largest debate on our ground), and for
each member who spoke on our ground sets their words beside their latest
recorded votes on the debate's areas.

BEFORE SIGN-OFF (today, every country): no reading of those votes is
confirmed in config/<cc>_stance.yaml, so the read is labelled AWAITING
SIGN-OFF and names no contradiction: words and votes, side by side.

AFTER SIGN-OFF: a contradiction is named (WOBBLE: words read with us or
unclear, last confirmed vote against us; SLIP: words read against us, last
confirmed vote with us) only when the vote's reading is CONFIRMED and the
member's words have been read. Words are read by a person or the free
session judge, never an API: --queue-out writes a reads file with every
speaker's words, to be filled with with / against / unclear and passed back
with --reads. A vote derived from a group's show of hands (X5) never names
a contradiction.

Only countries whose source publishes the same day qualify
(tools/country_debate_today.py --list). --dm sends the read to Chris only.
Run at lunchtime (NL, CH) or after the sitting (FR, BE), and again before
the vote. Writes nothing to the store; --out saves the read.
"""

import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country5ca as c5  # noqa: E402
from src import country_debatepack as dp  # noqa: E402
from src import country_live as cl  # noqa: E402
from src.http import HttpClient  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cc", choices=cl.COUNTRIES)
    ap.add_argument("--date", default=cl.today_local())
    ap.add_argument("--find", help="words of the debate's title")
    ap.add_argument("--debate", help="the debate id country_debate_today printed")
    ap.add_argument("--area", type=int, action="append", help="the area(s) to set votes against "
                    "(default: the debate's own)")
    ap.add_argument("--reads", help="a filled reads file (with / against / unclear per speaker)")
    ap.add_argument("--queue-out", help="write the reads template here")
    ap.add_argument("--db", default=cl.STORE, help="the store, read-only")
    ap.add_argument("--config-dir", help="stance files (default config/)")
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--budget-seconds", type=float, default=300.0)
    ap.add_argument("--out", help="also write the read to this file")
    ap.add_argument("--dm", action="store_true", help="DM the read to Chris")
    args = ap.parse_args(argv)

    client = HttpClient(raw_dir=args.raw_dir, throttle=1.0)
    speeches, docs, gaps = cl.read_day(args.cc, args.date, client, args.db, args.budget_seconds,
                                       log=lambda *a, **k: None)
    rows = cl.debates(speeches)
    for g in gaps:
        print("[gap] " + g)
    if not docs:
        print("{0}: the source has published nothing for {1} yet.".format(args.cc, args.date))
        return 2
    got = cl.pick(rows, args.find, args.debate)
    if not got:
        print("No debate on our ground matches. On our ground today:")
        for d in rows:
            print("  {0:<14} {1:>2} speakers  {2}".format(d["debate_id"], len(d["speakers"]), d["title"][:90]))
        return 1
    if len(got) > 1 and (args.find or args.debate):
        print("Several debates match; rerun with --debate:")
        for d in got:
            print("  {0:<14} {1:>2} speakers  {2}".format(d["debate_id"], len(d["speakers"]), d["title"][:90]))
        return 1
    debate = got[0]
    if not os.path.exists(args.db):
        print("No store at {0}: words only.".format(args.db))
    conn = c5.connect_ro(args.db) if os.path.exists(args.db) else None
    if conn is None:
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
    wl = dp.watchlist(args.cc, args.config_dir)
    assessed, divs = cl.assess(conn, args.cc, debate, args.date, cl.load_reads(args.reads),
                               args.config_dir, wl, args.area)
    conn.close()
    if args.queue_out:
        with open(args.queue_out, "w", encoding="utf-8") as h:
            h.write(cl.queue_text(args.cc, args.date, debate, assessed))
        print("reads template: {0}".format(args.queue_out))
    text = cl.render(args.cc, args.date, debate, assessed, divs,
                     as_of=datetime.datetime.now().strftime("%H:%M"))
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as h:
            h.write(text + "\n")
    if args.dm:
        from src import publish
        r = publish.slack_dm(publish.load_secrets(), text)
        print("DM:", r.get("message_ts") or r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
