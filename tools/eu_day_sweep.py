#!/usr/bin/env python3
"""Sweep the European Parliament for the sitting days not yet swept.

    python3 tools/eu_day_sweep.py                    # the last week, if not done
    python3 tools/eu_day_sweep.py --since 2026-07-01 # catch up a range
    python3 tools/eu_day_sweep.py --dry-run          # which days are pending, no calls
    python3 tools/eu_day_sweep.py --dm               # DM what the sitting decided

Westminster has been swept per sitting day since 9 September. This is the EU
half of that: a plenary Tuesday reaches the store on Tuesday night instead of
waiting for Saturday. A day is swept ONCE and remembered in `sweep_log` under
source 'ep-plenary', so this can run every evening without re-walking ground it
has covered, and a non-sitting day is recorded as such and never asked about
again. The Parliament sits in blocks, so most days cost one cached calendar
lookup and nothing else.

Roll calls and adopted texts only. Written questions, ECI signatures, dossier
stages and consultation windows all change after the fact, so they stay on the
weekly rolling window where they belong -- the same division Hansard's day
sweep makes.

Sequencing: pull the store BEFORE this writes, push after. `git pull` comes
first, because db_state verifies the asset against the sidecar committed in the
repo.
"""

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, eudaysweep  # noqa: E402
from src.http import HttpClient  # noqa: E402

LOOKBACK_DAYS = 7


def main():
    argv = sys.argv[1:]
    today = datetime.date.today()
    start = today - datetime.timedelta(days=LOOKBACK_DAYS)
    if "--since" in argv:
        start = datetime.date.fromisoformat(argv[argv.index("--since") + 1])
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    pending = eudaysweep.pending_days(conn, start, today)
    if not pending:
        print("ep-day-sweep: nothing pending between {0} and {1}.".format(start, today))
        return 0
    if "--dry-run" in argv:
        print("ep-day-sweep: {0} day(s) pending: {1}".format(
            len(pending), ", ".join(d.isoformat() for d in pending)))
        return 0
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    cache, sittings, divisions, texts, gaps = {}, [], 0, 0, 0
    for day in pending:
        sat, m, o, g = eudaysweep.sweep_day(conn, client, day, log=print, cache=cache)
        gaps += g
        if sat:
            sittings.append(day.isoformat())
            divisions += m
            texts += o
            print("  {0}: SAT - {1} division(s) on our ground, {2} adopted text(s)"
                  .format(day, m, o))
    print("ep-day-sweep: {0} day(s) checked, {1} sitting(s), {2} division(s) and "
          "{3} text(s) on our ground, {4} gap(s)."
          .format(len(pending), len(sittings), divisions, texts, gaps))
    if "--dm" in argv and sittings:
        from src import publish
        text = ("*European Parliament sat {0}*: {1} division(s) on our ground and "
                "{2} adopted text(s), collected the same day. Verdicts are signed "
                "by hand in config/eu_divisions.yaml; unsigned divisions place "
                "nobody.".format(", ".join(sittings), divisions, texts))
        print("dm:", publish.slack_dm(publish.load_secrets(), text))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
