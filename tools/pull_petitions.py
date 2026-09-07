"""Sweep e-petitions into the store outside the Sunday pull.

    python3 tools/pull_petitions.py

Same code path as the weekly (run_weekly.sweep_petitions); this exists so
the first snapshot can be taken today rather than next Sunday, giving the
edition a "this week" movement column from its first appearance. Items
land with triage_score NULL and are scored by the next pull's judge pass.
ONE WRITER AT A TIME: pull the store first, push it after.
"""

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import run_weekly
from src import db, filter as filt
from src.http import HttpClient


def main():
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    n = run_weekly.sweep_petitions(client, conn, tax, wl, datetime.date.today(),
                                   edition=datetime.date.today().isoformat())
    conn.close()
    return 0 if n is not None else 1


if __name__ == "__main__":
    sys.exit(main())
