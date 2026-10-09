#!/bin/bash
# Panama weekly: deputies, every anteproyecto and proyecto de ley of the
# current term with stage histories where a stage moved, and the plenary's
# orden del dia (tools/pa_rollcalls.py), then publish the raw archive and the
# store. There are no recorded votes to collect: the Asamblea publishes none
# (docs/panama-scope.md).
#
# Called by .github/workflows/pa-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh pa-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     PA_RECLASSIFY=true    re-derive every stored PA bill's areas, offline,
#                           before the pull (after a Spanish taxonomy or
#                           watchlist-pa change)
#
# Each run walks all of segLegis (47 pages on 9 October 2026, about five
# minutes; the site's paging postbacks are slow and sometimes drop a TLS
# handshake, which the collector retries). The budget (45 minutes) is far
# above that and stops the run cleanly if the site crawls.
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps (in the gaps table and as [gap] lines in the log): that run is still
# published, and this script exits 0 so the caller commits the sidecars with
# it. Any other failure publishes NOTHING and exits non-zero.
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Panama weekly}"
if [ "${PA_RECLASSIFY:-}" = "true" ]; then
  python3 tools/pa_rollcalls.py --reclassify
fi
rc=0
python3 tools/pa_rollcalls.py --budget-seconds 2700 || rc=$?
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "pa-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "pa-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
