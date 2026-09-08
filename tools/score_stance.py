"""Score unscored ledger refs onto the 5CA stance gradient.

    python3 tools/score_stance.py [--dry-run] [--max N] [--skip-hidden]

The weekly pull scores each week's new evidence automatically (capped by
settings.stance_weekly_max_refs). This CLI is for backfills and gap-fills:
it runs uncapped by default, so a re-run after a failure or a fresh historic
import places everything outstanding.

Evidence text is recovered offline from data/raw -- no source API traffic.
Idempotent: only refs without a stance row are sent, and each batch stores
as it completes, so an interruption costs nothing already paid for.
"""

from __future__ import annotations

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, publish, stance


def main():
    dry = "--dry-run" in sys.argv
    max_refs = None
    if "--max" in sys.argv:
        max_refs = int(sys.argv[sys.argv.index("--max") + 1])
    skip_hidden = "--skip-hidden" in sys.argv    # leave migration-only refs (shown nowhere) for a separate decision

    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    pending = stance.unscored_refs(conn, skip_hidden=skip_hidden)
    kinds = {}
    for r in pending:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print("{0} refs to score {1}".format(len(pending), kinds or ""))
    if dry or not pending:
        return

    cfg = stance.load_overrides(os.path.join(ROOT, "config", "stance_overrides.yaml"))
    stats = stance.score_pending(
        conn, os.path.join(ROOT, "data", "raw"),
        publish.load_secrets().get("anthropic_api_key"),
        datetime.date.today().isoformat(),
        max_refs=max_refs, overrides_cfg=cfg, skip_hidden=skip_hidden,
        log=lambda msg: print("  [gap] " + msg))

    print("scored {scored}; {failed_batches} batch(es) failed; "
          "{deferred} deferred; overrides on {overridden} vote refs".format(**stats))
    if stats["failed_batches"] or stats["deferred"]:
        print("re-run to fill the gaps (idempotent)")

    dist = {}
    for row in conn.execute("SELECT stance, COUNT(*) n FROM stance GROUP BY stance"):
        dist[stance.stance_to_column(row["stance"])] = row["n"]
    print("ledger stance distribution: " +
          "  ".join("{0} x{1}".format(c, dist[c]) for c in stance.COLUMNS if c in dist))
    conn.close()


if __name__ == "__main__":
    main()
