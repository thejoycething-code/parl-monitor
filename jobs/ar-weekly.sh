#!/bin/bash
# Argentina weekly: members of both chambers, the Diputados register of
# expedientes, and Senate roll calls with every senator's position
# (tools/ar_rollcalls.py), then publish the raw archive and the store.
#
# Called by .github/workflows/ar-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh ar-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards.
#
#     AR_RECLASSIFY=true    re-derive every stored AR expediente's and
#                           division's areas, offline, before the pull (after
#                           config/taxonomy-es.yaml or watchlist-ar changes)
#     AR_PUBLISH=false      collect only. The GitHub workflow sets it and
#                           publishes in its own steps, under the same
#                           condition as its commit step, as every store
#                           workflow there does. On the Mini, publishing is
#                           this script's last step, as mini_run.sh requires.
#
# Exit codes on the Mini. The collector exits 3 when it stored what it could
# and recorded gaps (in the gaps table and as [gap] lines in the log): that
# run is still published, and this script exits 0 so mini_run.sh commits the
# sidecars with it. Any other failure publishes NOTHING and exits non-zero.
# With AR_PUBLISH=false the collector's exit code is passed straight through,
# so a gap turns the GitHub step red and the failure alert hears of it.
#
# Diputados roll calls are NOT collected (votaciones.hcdn.gob.ar refuses every
# client we have tried; docs/argentina-scope.md). The collector says so in one
# line each run and does not count it as a gap.
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped by db_state.py --push) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Argentina weekly}"
if [ "${AR_RECLASSIFY:-}" = "true" ]; then
  python3 tools/ar_rollcalls.py --reclassify
fi
rc=0
# AR6 (10 October 2026): AR_SENATE_BACKFILL=true also reads the 2024 and 2025
# Senate actas (a one-off; the weekly reads the current year only).
years=()
if [ "${AR_SENATE_BACKFILL:-}" = "true" ]; then
  years=(--years 2024 2025 "$(date -u +%Y)")
fi
python3 tools/ar_rollcalls.py --budget-seconds 2700 "${years[@]}" || rc=$?
if [ "${AR_PUBLISH:-true}" = "false" ]; then
  exit "$rc"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "ar-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "ar-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
