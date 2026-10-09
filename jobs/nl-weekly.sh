#!/bin/bash
# Netherlands weekly: the Tweede Kamer's fracties, members and every vote
# with every position (tools/nl_rollcalls.py), then publish the raw archive
# and the store.
#
# Called by .github/workflows/nl-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh nl-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     NL_RECLASSIFY=true    re-derive every stored NL zaak's and vote's areas,
#                           offline, before the pull (after Chris approves
#                           config/taxonomy-nl.yaml, or a watchlist-nl change)
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps (in the gaps table and as [gap] lines in the log): that run is still
# published, and this script exits 0 so the caller commits the sidecars with
# it. Any other failure publishes NOTHING and exits non-zero: a half-written
# store is not worth the divergence of a published store whose sidecar never
# got committed, and the next run re-reads whatever this one missed (the
# collector re-reads a six-week window every week).
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Netherlands weekly}"
if [ "${NL_RECLASSIFY:-}" = "true" ]; then
  python3 tools/nl_rollcalls.py --reclassify
fi
rc=0
python3 tools/nl_rollcalls.py --budget-seconds 2700 || rc=$?
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "nl-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "nl-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
