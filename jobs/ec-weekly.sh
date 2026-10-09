#!/bin/bash
# Ecuador weekly: plenary votes with every member's position, the member
# register and the sitting roster of the Asamblea Nacional
# (tools/ec_rollcalls.py), then publish the raw archive and the store.
#
# Called by .github/workflows/ec-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh ec-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     EC_RECLASSIFY=true    re-derive every stored EC division's areas,
#                           offline, before the pull (after
#                           config/taxonomy-ec.yaml or watchlist-ec changes)
#
# The first run backfills period 8 (14 May 2025 onwards): about 520 vote
# details at one request a second plus the service's own second, roughly
# 20 minutes. The budget (45 minutes) stops a longer run cleanly and the
# next run resumes from the store. Earlier periods are a deliberate
# one-off (--period 7, --period 6), not this job's business.
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps (in the gaps table and as [gap] lines in the log): that run is still
# published, and this script exits 0 so the caller commits the sidecars with
# it. Any other failure publishes NOTHING and exits non-zero.
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on
# the workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here
# or the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Ecuador weekly}"
if [ "${EC_RECLASSIFY:-}" = "true" ]; then
  python3 tools/ec_rollcalls.py --reclassify
fi
rc=0
python3 tools/ec_rollcalls.py --budget-seconds 2700 || rc=$?
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "ec-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "ec-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
