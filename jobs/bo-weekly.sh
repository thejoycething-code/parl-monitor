#!/bin/bash
# Bolivia weekly: members and proyectos de ley of both chambers of the
# Asamblea Legislativa Plurinacional (tools/bo_rollcalls.py), then publish
# the raw archive and the store. There are no roll calls to collect: neither
# chamber publishes per-member votes (docs/bolivia-scope.md).
#
# Called by .github/workflows/bo-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh bo-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards. (The pattern of
# jobs/au-weekly.sh, 9 October 2026.)
#
#     BO_RECLASSIFY=true    re-derive every stored BO bill's areas, offline,
#                           before the pull (after a taxonomy or watchlist-bo
#                           change, or the day taxonomy-es lands)
#     BO_BACKFILL=true      read every Diputados bill record since 2020 (55
#                           pages, about four minutes), not only the current
#                           legislative year and the last three weeks' moves.
#                           Once, on the first run; the store keeps them.
#     BO_PUBLISH=false      collect only. The GitHub workflow sets it and
#                           publishes in its own steps, under the same
#                           condition as its commit step, as every store
#                           workflow there does (tests/test_vote_tracker_display.py
#                           StorePublishGuardTests). On the Mini, publishing is
#                           this script's last step, as mini_run.sh requires.
#
# Exit codes on the Mini. The collector exits 3 when it stored what it could
# and recorded gaps (in the gaps table and as [gap] lines in the log): that
# run is still published, and this script exits 0 so mini_run.sh commits the
# sidecars with it. Any other failure publishes NOTHING and exits non-zero: a
# half-written store is not worth a published store whose sidecar never got
# committed, and the next run re-reads whatever this one missed. With
# BO_PUBLISH=false the collector's exit code is passed straight through, so a
# gap turns the GitHub step red and the failure alert hears of it.
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on
# the workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here
# or the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Bolivia weekly}"
if [ "${BO_RECLASSIFY:-}" = "true" ]; then
  python3 tools/bo_rollcalls.py --reclassify
fi
args=(--budget-seconds 1800)
[ "${BO_BACKFILL:-}" = "true" ] && args+=(--backfill)
rc=0
python3 tools/bo_rollcalls.py "${args[@]}" || rc=$?
if [ "${BO_PUBLISH:-true}" = "false" ]; then
  exit "$rc"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "bo-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "bo-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
