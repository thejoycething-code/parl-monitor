"""Stage 2: re-score speeches the classifier judged without seeing the match.

    python3 tools/rescore_blind_speeches.py [--dry-run]

Evidence text was truncated to 1,500 characters before being sent, but the
median speech is 3,100 (p90 8,800). For a slice of speeches the qualifying
match sat beyond the cut, so the classifier scored a passage that never
contained the reason the speech was captured.

Those refs are identified exactly -- the match qualifies on the full text but
not on the first 1,500 characters -- their stance rows are dropped, and
score_pending re-scores them. It now sends the stored excerpt (the matching
passage) rather than a prefix, so the re-score sees the relevant words.

Dry run by default: prints the count and the estimated spend.
"""

from __future__ import annotations

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, publish, stance

PREFIX = 1500          # what the old payload sent
COST_PER_BATCH = 0.03  # observed, in pounds


def main():
    apply = "--apply" in sys.argv
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    texts = stance.build_text_map(os.path.join(ROOT, "data", "raw"))

    rows = conn.execute(
        "SELECT DISTINCT e.ref FROM mp_events e JOIN stance s ON s.ref = e.ref "
        "WHERE e.kind = 'debate' AND e.areas IS NOT NULL AND e.areas != '[]'").fetchall()

    blind = []
    for r in rows:
        text = texts.get(r["ref"], "")
        if len(text) <= PREFIX:
            continue
        full = filt.filter_item(tax, wl, text)
        seen = filt.filter_item(tax, wl, text[:PREFIX])
        if (full.tier == 1 or full.watchlist_hits) and not (
                seen.tier == 1 or seen.watchlist_hits):
            blind.append(r["ref"])

    batches = (len(blind) + stance.BATCH_SIZE - 1) // stance.BATCH_SIZE
    print("{0} speeches of {1} were scored without their match in view".format(
        len(blind), len(rows)))
    print("re-scoring needs ~{0} batches, about GBP {1:.2f}".format(
        batches, batches * COST_PER_BATCH))
    if not apply:
        print("\ndry run; re-run with --apply to spend that and re-score")
        return

    conn.executemany("DELETE FROM stance WHERE ref = ?", [(r,) for r in blind])
    conn.commit()
    cfg = stance.load_overrides(os.path.join(ROOT, "config", "stance_overrides.yaml"))
    stats = stance.score_pending(
        conn, os.path.join(ROOT, "data", "raw"),
        publish.load_secrets().get("anthropic_api_key"),
        datetime.date.today().isoformat(), overrides_cfg=cfg,
        log=lambda msg: print("  [gap] " + msg))
    print("re-scored {scored}; {failed_batches} batch(es) failed; "
          "overrides on {overridden}".format(**stats))
    conn.close()


if __name__ == "__main__":
    main()
