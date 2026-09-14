#!/usr/bin/env python3
"""Re-score items the pull had to stub-score, live.

    python3 tools/rescore_stub.py --week 2026-09-14 [--since 2026-09-12] [--dry-run]

When the live judge fails mid-pull the run falls back to deterministic stub
scores (tier-1 = 2, tier-2 = 1, no "why it matters"), records a gap, and the
edition goes out flagged for human review. 14 Sept 2026: the reply's thinking
ate the token budget and 80 items were stubbed the morning of the publish.
This puts those items back in the queue (triage_score NULL) and runs the live
pass on them, then drops the triage gap for the week if every item scored.
Only stub rows are touched: a score with a why_it_matters, or a human
priority_tag, is left alone. Sequencing: pull the store before, push after.
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt  # noqa: E402


def stub_rows(conn, since):
    return conn.execute(
        "SELECT id FROM items WHERE triage_score IS NOT NULL AND (why_it_matters IS NULL OR why_it_matters = '') "
        "AND priority_tag IS NULL AND captured_at >= ?", (since,)).fetchall()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--week", required=True, help="edition week commencing (the pull's week)")
    ap.add_argument("--since", help="items captured on or after this date (default: the Friday before --week)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    import datetime
    since = args.since or (datetime.date.fromisoformat(args.week) - datetime.timedelta(days=3)).isoformat()
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    rows = stub_rows(conn, since)
    print("%d stub-scored item(s) captured since %s" % (len(rows), since))
    if not rows or args.dry_run:
        return 0
    conn.execute("UPDATE items SET triage_score = NULL WHERE id IN (%s)" % ",".join("?" * len(rows)), [r[0] for r in rows])
    conn.commit()
    import run_weekly
    from src import publish
    key = publish.load_secrets().get("anthropic_api_key")
    if key:
        os.environ.setdefault("ANTHROPIC_API_KEY", key)
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    status = run_weekly.run_triage_pass(conn, wl, args.week, mode="live")
    print("triage:", status)
    left = conn.execute("SELECT COUNT(*) FROM items WHERE triage_score IS NULL").fetchone()[0]
    if "(live)" in status and left == 0:
        n = conn.execute("DELETE FROM gaps WHERE edition = ? AND feed = 'triage'", (args.week,)).rowcount
        conn.commit()
        print("cleared %d triage gap row(s) for w/c %s" % (n, args.week))
    else:
        print("%d item(s) still unscored; the triage gap stays" % left)
    return 0 if left == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
