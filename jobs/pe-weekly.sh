#!/bin/bash
# Peru weekly: members of both chambers, proyectos de ley and plenary votes
# of the Congress (tools/pe_rollcalls.py), then publish the raw archive and
# the store.
#
# Called by .github/workflows/pe-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh pe-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards. (The pattern of
# jobs/au-weekly.sh, 9 October 2026.)
#
#     PE_RECLASSIFY=true    re-derive every stored PE proyecto's and vote's
#                           areas, offline, before the pull (after a taxonomy
#                           or watchlist-pe change, or the day taxonomy-es lands)
#     PE_PUBLISH=false      collect only. The GitHub workflow sets it and
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
# PE_PUBLISH=false the collector's exit code is passed straight through, so a
# gap turns the GitHub step red and the failure alert hears of it.
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped by db_state.py --push) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Peru weekly}"
if [ "${PE_RECLASSIFY:-}" = "true" ]; then
  python3 tools/pe_rollcalls.py --reclassify
fi
rc=0
python3 tools/pe_rollcalls.py --budget-seconds 2700 || rc=$?
# Same-day vote briefs (tools/country_vote_briefs.py, src/country_vote_brief.py):
# this country's watched and tier-1 votes not briefed yet, written to
# data/briefs/ and sent in one DM to Chris alone, de-duplicated in
# data/vote-briefs/pe.json (committed with data/). Before the alerts:
# a vote briefed here is not alerted again. Never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_vote_briefs.py --country pe --send \
    || echo "  [gap] vote briefs failed for pe; the next run retries"
fi
# Instant Latam alerts (tools/latam_alerts.py): this country's watched and
# tier-1 items, a short DM each to Chris alone, de-duplicated in
# data/latam-alerts/pe.json (committed with data/). Never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/latam_alerts.py --country pe --send \
    || echo "  [gap] latam-alerts failed for pe; the next run retries"
fi
if [ "${PE_PUBLISH:-true}" = "false" ]; then
  exit "$rc"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "pe-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "pe-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
