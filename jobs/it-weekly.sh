#!/bin/bash
# Italy weekly: bills of both chambers, Senate and Camera votes, and every
# member's position on the votes on our ground (tools/it_rollcalls.py), then
# publish the raw archive and the store.
#
# Called by .github/workflows/it-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh it-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     IT_RECLASSIFY=true    re-derive every stored IT bill's and division's
#                           areas, offline, before the pull (after the Italian
#                           taxonomy lands or watchlist-it changes)
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps (in the gaps table and as [gap] lines in the log): that run is still
# published, and this script exits 0 so the caller commits the sidecars with
# it. Any other failure publishes NOTHING and exits non-zero: a half-written
# store is not worth the divergence of a published store whose sidecar never
# got committed, and the next run re-reads whatever this one missed.
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped by db_state.py --push) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Italy weekly}"
if [ "${IT_RECLASSIFY:-}" = "true" ]; then
  python3 tools/it_rollcalls.py --reclassify
fi
rc=0
python3 tools/it_rollcalls.py --budget-seconds 2700 || rc=$?
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "it-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "it-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
