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
# mini_run: commit profiles briefs
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
# X8/CO4 (10 October 2026): the Corte Constitucional's exhortations to
# Congress (tools/co_courts.py, one request).
# Gaps go to the store; a failure never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/co_courts.py \
    || echo "  [gap] co-courts recorded gaps or failed; the next run retries"
fi
# Instant Latam alerts (tools/latam_alerts.py): this country's watched and
# tier-1 items, a short DM each to Chris alone, de-duplicated in
# data/latam-alerts/co.json (committed with data/). Never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/latam_alerts.py --country co --send \
    || echo "  [gap] latam-alerts failed for co; the next run retries"
fi
# Member profiles (tools/member_profiles.py, src/member_profiles.py): profiles/co/
# rewritten from the store just collected and committed with it; never posted
# or DMed. A failure is a [gap] line and never costs the store.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_profiles.py co \
    || echo "  [gap] member-profiles: the profiles failed to render; the store is still published"
fi
if [ "${CO_PUBLISH:-true}" = "false" ]; then
  exit "$rc"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "co-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "co-rollcalls recorded gaps; publishing what it stored"
# Campaign brief drafts (tools/country_briefs.py, src/country_briefs.py): a
# draft RF4 brief in briefs/ for each new watched or tier-1 bill, NOT READY
# until its stances are confirmed in config/co_stance.yaml; unedited briefs
# are refreshed. Offline, from the store as it stands; sends nothing. A
# failure is a [gap] line and never costs the store.
python3 tools/country_briefs.py --cc co \
  || echo "  [gap] country-briefs failed for co; last week's briefs stand"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
