#!/bin/bash
# Colombia weekly: both chambers' bill registers, Cámara plenary attendance
# and the Senate's published roll calls (tools/co_rollcalls.py), then publish
# the raw archive and the store.
#
# Called by .github/workflows/co-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh co-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards.
#
#     CO_RECLASSIFY=true    re-derive every stored CO bill's and division's
#                           areas, offline, before the pull (after a
#                           taxonomy-es or watchlist-co change)
#     CO_PUBLISH=false      collect only. The GitHub workflow sets it and
#                           publishes in its own steps, under the same
#                           condition as its commit step, as every store
#                           workflow there does. On the Mini, publishing is
#                           this script's last step, as mini_run.sh requires.
#
# Exit codes on the Mini. The collector exits 3 when it stored what it could
# and recorded gaps (in the gaps table and as [gap] lines in the log): that
# run is still published, and this script exits 0 so mini_run.sh commits the
# sidecars with it. Any other failure publishes NOTHING and exits non-zero: a
# half-written store is not worth a published store whose sidecar never got
# committed, and the next run re-reads whatever this one missed. With
# CO_PUBLISH=false the collector's exit code is passed straight through, so a
# gap turns the GitHub step red and the failure alert hears of it.
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped by db_state.py --push) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Colombia weekly}"
if [ "${CO_RECLASSIFY:-}" = "true" ]; then
  python3 tools/co_rollcalls.py --reclassify
fi
rc=0
python3 tools/co_rollcalls.py --budget-seconds 1800 || rc=$?
if [ "${CO_PUBLISH:-true}" = "false" ]; then
  exit "$rc"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "co-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "co-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
