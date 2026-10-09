#!/bin/bash
# Portugal weekly: deputies, initiatives and plenary votes of the Assembleia
# da Republica (tools/pt_rollcalls.py), then publish the raw archive and the
# store.
#
# Called by .github/workflows/pt-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh pt-weekly. One script, two callers (the jobs/au-weekly.sh
# pattern). Both callers fetch the store first and commit data/ afterwards.
#
#     PT_RECLASSIFY=true    re-derive every stored PT initiative's and vote's
#                           areas, offline, before the pull (after a taxonomy
#                           or watchlist-pt change, and the day
#                           config/taxonomy-pt.yaml first lands)
#     PT_PUBLISH=false      collect only. The GitHub workflow sets it and
#                           publishes in its own steps, under the same
#                           condition as its commit step. On the Mini,
#                           publishing is this script's last step, as
#                           mini_run.sh requires.
#
# Exit codes on the Mini. The collector exits 3 when it stored what it could
# and recorded gaps (the deputies file failed but the initiatives were read):
# that run is still published, and this script exits 0 so mini_run.sh
# commits the sidecars with it. Exit 1 (no initiatives read) or anything else
# publishes NOTHING and exits non-zero; next week re-reads the whole
# legislature anyway. With PT_PUBLISH=false the collector's exit code is
# passed straight through, so a gap turns the GitHub step red and the
# failure alert hears of it.
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped by db_state.py --push) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Portugal weekly}"
if [ "${PT_RECLASSIFY:-}" = "true" ]; then
  python3 tools/pt_rollcalls.py --reclassify
fi
rc=0
# PT6 (10 October 2026): PT_LEGISLATURE=XV or XVI reads that legislature's
# files instead of the current one (the backfill, dispatched from CI).
leg=()
case "${PT_LEGISLATURE:-}" in
  "") ;;
  XV|XVI|XVII) leg=(--legislature "$PT_LEGISLATURE") ;;
  *) echo "pt-weekly: unknown legislature '${PT_LEGISLATURE}'"; exit 2 ;;
esac
python3 tools/pt_rollcalls.py --budget-seconds 2700 "${leg[@]}" || rc=$?
if [ "${PT_PUBLISH:-true}" = "false" ]; then
  exit "$rc"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "pt-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "pt-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
