#!/bin/bash
# Mexico weekly, the work: deputies, iniciativas, votes and positions of the
# Chamber of Deputies (tools/mx_rollcalls.py).
#
# Called by .github/workflows/mx-weekly.yml only. Unlike the other country
# jobs it has no Mac Mini caller: diputados.gob.mx refuses UK addresses, so
# the Mini's jobs/mx-weekly.sh dispatches the workflow instead. The workflow
# fetches the store first, then publishes the raw archive and the store in
# its own steps (under the commit step's condition, as every store workflow
# does) and commits the sidecars.
#
#     MX_RECLASSIFY=true    re-derive every stored iniciativa's and vote's
#                           areas, offline, before the pull (after
#                           config/taxonomy-es.yaml or watchlist-mx changes)
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps (in the gaps table and as [gap] lines in the log): this script exits 0
# for that, so the run is green and its gaps are read from the summary. Any
# other failure exits non-zero and fails the step.
set -eo pipefail
cd "$(dirname "$0")/.."
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Mexico weekly}"
if [ "${MX_RECLASSIFY:-}" = "true" ]; then
  python3 tools/mx_rollcalls.py --reclassify
fi
rc=0
# The first run reads every vote of the LXVI (285 to 2 October 2026, about
# nine pages each at one a second); the budget stops it cleanly and the rest
# drains on later runs.
python3 tools/mx_rollcalls.py --budget-seconds 2400 || rc=$?
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "mx-rollcalls failed (exit $rc)"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "mx-rollcalls recorded gaps; keeping what it stored"
exit 0
