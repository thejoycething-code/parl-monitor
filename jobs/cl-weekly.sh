#!/bin/bash
# Chile weekly: deputies, senators, bills and Cámara and Senate votes of the
# National Congress (tools/cl_rollcalls.py), then publish the raw archive and
# the store.
#
# Called by .github/workflows/cl-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh cl-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     CL_RECLASSIFY=true    re-derive every stored Chile bill's and vote's
#                           areas, offline, before the pull (after the
#                           Spanish taxonomy or watchlist-cl changes)
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps (in the gaps table and as [gap] lines in the log): that run is still
# published, and this script exits 0 so the caller commits the sidecars with
# it. Any other failure publishes NOTHING and exits non-zero: the next run
# re-reads whatever this one missed (the Cámara pull resumes from the store).
# mini_run: commit briefs
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Chile weekly}"
if [ "${CL_RECLASSIFY:-}" = "true" ]; then
  python3 tools/cl_rollcalls.py --reclassify
fi
rc=0
python3 tools/cl_rollcalls.py --budget-seconds 2700 || rc=$?
# Instant Latam alerts (tools/latam_alerts.py): this country's watched and
# tier-1 items, a short DM each to Chris alone, de-duplicated in
# data/latam-alerts/cl.json (committed with data/). Never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/latam_alerts.py --country cl --send \
    || echo "  [gap] latam-alerts failed for cl; the next run retries"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "cl-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "cl-rollcalls recorded gaps; publishing what it stored"
# Campaign brief drafts (tools/country_briefs.py, src/country_briefs.py): a
# draft RF4 brief in briefs/ for each new watched or tier-1 bill, NOT READY
# until its stances are confirmed in config/cl_stance.yaml; unedited briefs
# are refreshed. Offline, from the store as it stands; sends nothing. A
# failure is a [gap] line and never costs the store.
python3 tools/country_briefs.py --cc cl \
  || echo "  [gap] country-briefs failed for cl; last week's briefs stand"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
