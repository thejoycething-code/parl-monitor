"""Backfill division member-breakdowns into the MP intelligence ledger.

    python3 tools/backfill_divisions.py [cutoff-date] [end-date]

Sweeps config/settings.yaml division_sweep_terms through both votes APIs
(Commons + Lords, keyless, fast) from the cutoff (default 2020-01-01),
taxonomy-filters each division title (tier-1/watchlist precision gate, same
rule as every other ledger path), then fetches the full member breakdown of
each matched division and ledgers every voter.

Ledger shape: kind='vote', ref='div:{c|l}{id}:{aye|no}' -- direction lives in
the ref because stance classification is per-ref, and Ayes and Noes on the
same division carry opposite stances. Voter payloads embed name/party/seat,
so the members cache seeds without Members API traffic.

Idempotent: record_event upserts; re-runs fill gaps. Volume: a Commons
division ledgers ~300-600 rows; commits are batched per division.
"""

from __future__ import annotations

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, intel
from src.http import FetchError, HttpClient
from src.ingest import divisions

HOUSES = (
    ("Commons", "c", divisions.search_commons_divisions, divisions.fetch_commons_breakdown),
    ("Lords", "l", divisions.search_lords_divisions, divisions.fetch_lords_breakdown),
)


def load_settings():
    import yaml
    with open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def main():
    cutoff = sys.argv[1] if len(sys.argv) > 1 else "2020-01-01"
    end = sys.argv[2] if len(sys.argv) > 2 else datetime.date.today().isoformat()
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    terms = load_settings().get("division_sweep_terms") or []

    print("backfilling divisions {0} -> {1}".format(cutoff, end))
    total, matched_n = 0, 0
    for house, prefix, search, breakdown in HOUSES:
        seen = set()
        for term in terms:
            try:
                found = search(client, term, cutoff, end)
            except FetchError as exc:
                print("  [gap] {0} '{1}': {2}".format(house, term, exc.cause))
                continue
            for d in found:
                if d.id in seen or not d.date:
                    continue
                seen.add(d.id)
                r = filt.filter_item(tax, wl, d.title or "")
                if not (r.tier == 1 or r.watchlist_hits):
                    continue
                try:
                    division, voters = breakdown(client, d.id)
                except FetchError as exc:
                    print("  [gap] {0} division {1}: {2}".format(house, d.id, exc.cause))
                    continue
                division.house = house
                n = intel.record_votes(conn, division, voters, prefix, r.issue_areas)
                total += n
                matched_n += 1
                print("  {0} {1} {2} ({3} voters): {4}".format(
                    house, d.date, (d.title or "")[:60], n,
                    ", ".join(r.matched_terms[:2] + r.watchlist_hits[:1])))
    print("done: {0} matched divisions, {1} vote events".format(matched_n, total))
    print("ledger:", intel.ledger_stats(conn))
    conn.close()


if __name__ == "__main__":
    main()
