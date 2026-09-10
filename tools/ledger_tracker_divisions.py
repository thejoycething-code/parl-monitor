#!/usr/bin/env python3
"""Put the voters of every vote-tracker division into the ledger.

    python3 tools/ledger_tracker_divisions.py            # ledger any tracker division with no voters
    python3 tools/ledger_tracker_divisions.py --dry-run  # say which, fetch nothing

The tracker card draws its voters FROM the ledger, and the only sweeps that fill the
ledger search division TITLES -- so a division whose title names no issue ("Health Bill:
Report Stage: New Clause 142") can be signed off on the tracker and publish a verdict on
nobody. Found 2026-09-10. This runs in the Monday publish before make_vote_tracker, so
that can no longer happen. Idempotent; leaves sweep-found divisions alone.

Sequencing: pull the store before, push after.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from src import db, trackerledger  # noqa: E402
from src.http import HttpClient  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    import make_vote_tracker
    cfg = make_vote_tracker.load_config()
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(os.path.join(ROOT, "data", "raw"))
    report = trackerledger.ensure(conn, client, cfg, log=print, dry_run=args.dry_run)
    conn.close()
    done = [r for r in report if isinstance(r[3], int)]
    gaps = [r for r in report if isinstance(r[3], str)]
    print("tracker ledger: %d division(s) ledgered, %d gap(s), %d already present"
          % (len(done), len(gaps), len(cfg.get("divisions") or []) - len(report)))


if __name__ == "__main__":
    main()
