#!/usr/bin/env python3
"""Words since the last vote, for NL, CH, AT, FR and BE (src/country_since_vote.py).

    python3 tools/country_since_vote.py --cc be                  # every area, to the terminal
    python3 tools/country_since_vote.py --cc fr --area 2 --write # data/briefs/fr-since-vote-area2.md
    python3 tools/country_since_vote.py --cc ch --queue-out /tmp/ch-reads.yaml [--queue-all]
    python3 tools/country_since_vote.py --cc ch --reads /tmp/ch-reads.yaml

Per area, each member's last recorded vote on it and what they have said on
it since, with excerpts. The country version of tools/since_last_vote.py.
Drift is named only where the vote's reading is CONFIRMED and a person or
the free session judge has read the words (--queue-out writes the reads
template, --reads loads it, `read_by` must name the reader); before that the
rows are "awaiting sign-off", ranked by recency and volume. A group's vote
(X5: NL shows of hands, Austria) never names drift.

Manual. Read-only on the store (opened read-only, so it runs while a Mini
job holds it). Nothing is posted; no AI API calls.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country5ca as c5  # noqa: E402
from src import country_since_vote as sv  # noqa: E402


def main(argv=None, log=print):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cc", required=True, choices=sv.COUNTRIES)
    ap.add_argument("--area", type=int, action="append",
                    help="only this area (repeatable); default every area")
    ap.add_argument("--since", help="use each member's last vote on or before this date")
    ap.add_argument("--until", help="words up to this date (default: everything stored)")
    ap.add_argument("--top", type=int, default=sv.TOP, help="members shown per area")
    ap.add_argument("--reads", help="a filled reads file (from --queue-out)")
    ap.add_argument("--queue-out", help="write the reads template here")
    ap.add_argument("--queue-all", action="store_true",
                    help="queue the rows awaiting sign-off too, not only confirmed ones")
    ap.add_argument("--write", action="store_true",
                    help="write data/briefs/<cc>-since-vote[-areaN].md")
    ap.add_argument("--out", help="write the digest to this path instead")
    ap.add_argument("--db", default=sv.STORE)
    ap.add_argument("--config-dir", help=argparse.SUPPRESS)
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--sample", action="store_true", help="mark the digest SAMPLE")
    args = ap.parse_args(argv)
    if not os.path.exists(args.db):
        log("since-vote: no store at {0}".format(args.db))
        return 1
    read_by, reads = sv.load_reads(args.reads)
    if args.reads and not read_by:
        log("since-vote: {0} names no read_by (or does not exist): its reads are not "
            "counted".format(args.reads))
    conn = c5.connect_ro(args.db)
    try:
        got = sv.gather(conn, args.cc, args.area, args.since, args.until, args.config_dir,
                        reads=reads, read_by=read_by)
    finally:
        conn.close()
    text = sv.render(got, args.date, args.top, sample=args.sample)
    path = args.out
    if args.write and not path:
        suffix = "-area" + "-".join(str(a) for a in sorted(args.area)) if args.area else ""
        path = os.path.join(sv.BRIEFS, "{0}-since-vote{1}.md".format(args.cc, suffix))
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as h:
            h.write(text)
        log("-> {0}".format(os.path.relpath(path, ROOT) if path.startswith(ROOT) else path))
    else:
        log(text)
    if args.queue_out:
        q, n = sv.queue_text(got, args.queue_all)
        with open(args.queue_out, "w", encoding="utf-8") as h:
            h.write(q)
        log("reads template: {0} row(s) -> {1}".format(n, args.queue_out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
