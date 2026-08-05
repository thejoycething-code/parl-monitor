"""Historic backfill of Hansard spoken contributions into the ledger.

    python3 tools/backfill_hansard.py [cutoff-date] [end-date]

Sweeps the PQ sweep terms (campaign + historic vocabulary) through the
Hansard contributions search in year windows, taxonomy-filters each speech
(tier-1/watchlist precision gate on the full contribution text + debate
title), and ledgers kind='debate' events. Safe to run CONCURRENTLY with the
PQ/EDM backfill: different API host, and both commit in tiny transactions.

Speeches sit just below votes in the 5CA evidence hierarchy: speaking is a
chosen, personal act. Stance scoring reads the full speech text recovered
offline from the raw archive.
"""

from __future__ import annotations

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, intel, members
from src.http import FetchError, HttpClient
from src.ingest import hansard


def load_settings():
    import yaml
    with open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def year_windows(cutoff, end):
    windows = []
    for year in range(cutoff.year, end.year + 1):
        start = max(cutoff, datetime.date(year, 1, 1))
        stop = min(end, datetime.date(year, 12, 31))
        windows.append((start.isoformat(), stop.isoformat()))
    return windows


def main():
    cutoff = datetime.date.fromisoformat(sys.argv[1] if len(sys.argv) > 1 else "2020-01-01")
    end = datetime.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else datetime.date.today()
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    terms = load_settings().get("pq_sweep_terms") or []
    cache = {}

    def resolve(member_id):
        if member_id in cache:
            return cache[member_id]
        try:
            m = members.resolve(conn, client, member_id)
        except Exception:
            m = None
        cache[member_id] = m
        return m

    print("backfilling Hansard speeches {0} -> {1}".format(cutoff, end))
    written, seen = 0, set()
    for term in terms:
        for w_from, w_to in year_windows(cutoff, end):
            try:
                speeches = hansard.search_contributions(client, term, w_from, w_to)
            except FetchError as exc:
                print("  [gap] '{0}' {1}: {2}".format(term, w_from[:4], exc.cause))
                continue
            for s in speeches:
                if not s.ext_id or s.ext_id in seen:
                    continue
                seen.add(s.ext_id)
                if not s.member_id or not s.date:
                    continue
                matches = filt.match_passages(tax, wl, s.text or "",
                                              title=s.debate_title or "")
                if not matches:
                    continue
                areas, terms, excerpt = filt.aggregate_passages(matches)
                if resolve(s.member_id) is None:
                    continue
                intel.record_event(
                    conn, s.member_id, s.date.isoformat(), "debate",
                    "hansard:{0}".format(s.ext_id),
                    intel.annotated_line("Spoke: {0}".format(s.debate_title), terms),
                    areas=areas, excerpt=excerpt)
                written += 1
        print("  hansard '{0}' done ({1} events so far)".format(term, written))
    print("done: {0} debate events".format(written))
    print("ledger:", intel.ledger_stats(conn))
    conn.close()


if __name__ == "__main__":
    main()
