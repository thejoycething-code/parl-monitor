#!/bin/bash
# Croatia weekly: members, session agendas and recorded votes of the
# Hrvatski sabor (tools/hr_rollcalls.py), then publish the raw archive and
# the store.
#
# Called by .github/workflows/hr-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh hr-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     HR_RECLASSIFY=true    re-derive every stored HR item's and vote's
#                           areas, offline, before the pull (after
#                           config/taxonomy-hr.yaml or watchlist-hr changes)
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps (in the gaps table and as [gap] lines in the log): that run is still
# published, and this script exits 0 so the caller commits the sidecars with
# it. Any other failure publishes NOTHING and exits non-zero.
#
# THE FIRST RUN DOES NOT FINISH IN ONE GO, by design: the 11th Sabor has
# about 1,050 recorded votes and sabor.hr answers one every few seconds, so
# the 45-minute budget stores the newest few hundred and discloses the rest,
# which drain on the following runs (newest first). A normal week is the
# two latest sessions' agendas and the handful of votes held since.
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped by db_state.py --push) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Croatia weekly}"
if [ "${HR_RECLASSIFY:-}" = "true" ]; then
  python3 tools/hr_rollcalls.py --reclassify
fi
rc=0
python3 tools/hr_rollcalls.py --budget-seconds 2700 || rc=$?
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "hr-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "hr-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
