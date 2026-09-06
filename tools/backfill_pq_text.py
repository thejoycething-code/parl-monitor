"""Fetch the FULL text of every written question the ledger holds.

    python3 tools/backfill_pq_text.py            # everything not yet archived
    python3 tools/backfill_pq_text.py --limit 50

Christopher, 2026-09-06: "Build it." The search endpoint the sweep uses
returns each question cut at ~255 characters and no answer, so every
reader of a PQ row -- 5CA quotes, the member roll, the stance judge, a
retag -- has been reading a stub. The detail endpoint has the whole
question and the minister's answer, and nothing had ever fetched it.

ARCHIVE ONLY. Writes data/raw/<today>/pq_detail-<id>.json.gz through
HttpClient and touches no table, so it is safe to run beside any
workflow: ONE WRITER AT A TIME is about the store, and this never opens
it for writing. Resumable: an id with a detail file anywhere under
data/raw is skipped. Throttled by the client (0.2s per call), so ~4,000
questions is about fifteen minutes. Free API.
"""

from __future__ import annotations

import glob
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db
from src.http import FetchError, HttpClient
from src.ingest import pqs

RAW = os.path.join(ROOT, "data", "raw")


def archived_ids(raw_dir=RAW):
    """Question ids that already have a detail file, wherever dated."""
    out = set()
    for path in glob.glob(os.path.join(raw_dir, "*", "pq_detail-*.json.gz")):
        base = os.path.basename(path)
        out.add(base[len("pq_detail-"):-len(".json.gz")])
    return out


def ledger_ids(conn):
    ids = set()
    for (ref,) in conn.execute("SELECT DISTINCT ref FROM mp_events WHERE kind = 'pq'"):
        if ref and ref.startswith("pq:"):
            ids.add(ref.split(":", 1)[1])
    for (iid,) in conn.execute("SELECT id FROM items WHERE source_feed = 'pq'"):
        if iid and iid.startswith("pq:"):
            ids.add(iid.split(":", 1)[1])
    return ids


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    want = sorted(ledger_ids(conn), key=int)
    conn.close()
    have = archived_ids()
    todo = [q for q in want if q not in have]
    if limit is not None:
        todo = todo[:limit]
    print("pq detail backfill: {0} question(s) in the ledger, {1} archived, "
          "{2} to fetch".format(len(want), len(have), len(todo)))
    client = HttpClient(raw_dir=RAW)
    done = gaps = 0
    started = time.time()
    for n, qid in enumerate(todo, 1):
        try:
            pqs.fetch_question(client, qid)
            done += 1
        except FetchError as exc:
            gaps += 1
            print("  [gap] pq {0}: {1}".format(qid, exc.cause))
        except Exception as exc:                     # noqa: BLE001
            gaps += 1
            print("  [gap] pq {0}: {1}".format(qid, exc))
        if n % 500 == 0:
            print("  {0}/{1} after {2}s".format(n, len(todo), int(time.time() - started)))
    print("pq detail backfill: {0} fetched, {1} gap(s), {2}s. Re-run to retry "
          "the gaps; archived ids are skipped.".format(done, gaps, int(time.time() - started)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
