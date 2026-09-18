#!/usr/bin/env python3
"""Sweep Hansard for the sitting days not yet swept, and report the day's debates.

    python3 tools/day_sweep.py                       # yesterday and today, if not done
    python3 tools/day_sweep.py --since 2026-09-01    # catch up a range
    python3 tools/day_sweep.py --dry-run             # which days are pending, no calls
    python3 tools/day_sweep.py --radar-only          # find the debates, write no ledger rows
    python3 tools/day_sweep.py --dm                  # DM the radar reading

Sweeps a day ONCE and remembers it in `sweep_log`, so this can run every evening without
re-searching ground it has covered. A day within two days of today is looked at again,
because Hansard publishes hours after the House rises and revises text afterwards. A
recess day is recorded as such and never checked again.

Speeches only. Written questions and Early Day Motion signatures change after the fact,
so they stay on the weekly rolling window where they belong.

Sequencing: pull the store BEFORE this writes, push after. `git pull` comes first --
db_state verifies the asset against the sidecar COMMITTED in the repo.
"""

import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import daysweep, db, debateradar as radar, filter as filt, publish  # noqa: E402
from src.http import HttpClient  # noqa: E402
from src.ingest import hansard  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", help="first day to consider (default: 3 days ago)")
    ap.add_argument("--until", help="last day to consider (default: today)")
    ap.add_argument("--dry-run", action="store_true", help="list the pending days and stop")
    ap.add_argument("--radar-only", action="store_true", help="do not write ledger rows")
    ap.add_argument("--dm", action="store_true", help="DM the radar reading")
    ap.add_argument("--floor", type=int, default=radar.FLOOR_MEMBERS, help="members a debate needs")
    args = ap.parse_args()

    today = datetime.date.today()
    start = datetime.date.fromisoformat(args.since) if args.since else today - datetime.timedelta(days=3)
    end = datetime.date.fromisoformat(args.until) if args.until else today

    import yaml
    settings = yaml.safe_load(open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8")) or {}
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    pending = daysweep.pending_days(conn, start, end)
    if not pending:
        print("nothing pending between %s and %s (all swept, or no sitting weekdays)" % (start, end))
        return
    print("pending: %s" % ", ".join(d.isoformat() for d in pending))
    if args.dry_run:
        return

    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    terms = hansard.sweep_terms(settings)
    client = HttpClient(os.path.join(ROOT, "data", "raw"))
    all_cands, total, all_gaps = [], 0, []
    for day in pending:
        cands, written, gaps = daysweep.sweep_day(
            client, conn, day, terms, tax, wl, log=print, write_ledger=not args.radar_only)
        all_cands.extend(cands)
        total += written
        all_gaps.extend(gaps)
    conn.close()

    worth = [c for c in all_cands if c.worth_a_pack(args.floor)]
    print("\n%d ledger row(s); %d debate(s) worth a pack" % (total, len(worth)))
    reading = radar.report(sorted(all_cands, key=lambda c: len(c.members), reverse=True),
                           all_gaps, pending[-1], floor=args.floor)
    print()
    print(reading)
    if args.dm:
        if not worth:
            print("not DMing: nothing cleared the floor")
            return
        lines = ["*Debate radar — %s*" % ", ".join(d.isoformat() for d in pending), ""]
        for c in worth:
            lines += ["*%s* (%s) — %d members, %d contributions, %s"
                      % (c.title, c.house, len(c.members), len(c.contributions), c.strength),
                      c.url()]
        lines += ["", "%d ledger row(s) written." % total]
        if all_gaps:
            lines.append("%d gap(s) in the sweep — see the log." % len(all_gaps))
        lines += ["", "To build a pack:",
                  "```python3 tools/debate_pack.py --date %s --find \"<term>\"```" % pending[-1].isoformat()]
        result = publish.slack_dm(publish.load_secrets(), "\n".join(lines))
        print("DM:", result.get("message_ts") or result)


if __name__ == "__main__":
    main()
