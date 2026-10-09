#!/bin/bash
# Ireland weekly: Oireachtas members, bills and divisions into the ie_* tables,
# then publish the raw archive and the store.
#
# Called by .github/workflows/ie-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh ie-weekly. One script, two callers (docs/mac-mini.md).
# Both callers fetch the store first and commit data/ after.
#
#     IE_RECLASSIFY=true   re-derive stored areas offline first (after a
#                          taxonomy or watchlist-ie change)
#
# GAPS DO NOT FAIL THIS SCRIPT ONCE THE STORE IS PUBLISHED. A published store
# whose sidecar is never committed is refused by every later pull (SHA
# MISMATCH), and the Mini commits data/ only after a clean exit. So: a run
# that finished publishes and exits 0, with its gaps in the gaps table and
# as "[gap]" lines in the log (the GitHub workflow turns those red after its
# commit step). A run that crashed publishes nothing and fails.
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat names the pipeline, not "local", when the Mini runs this
# (tools/db_state.py stamps GITHUB_WORKFLOW into source_runs).
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Ireland weekly}"
LOG="${IE_LOG:-$(mktemp -t ie-weekly.XXXXXX)}"
if [ "${IE_RECLASSIFY:-}" = "true" ]; then
  python3 tools/ie_rollcalls.py --reclassify
fi
rc=0
python3 tools/ie_rollcalls.py --budget-seconds 1500 2>&1 | tee "$LOG" || rc=$?
if ! grep -q "  store: " "$LOG"; then
  echo "ie-weekly: the collector did not finish (exit $rc); nothing published"
  [ "$rc" -eq 0 ] && rc=1
  exit "$rc"
fi
[ "$rc" -ne 0 ] && echo "ie-weekly: finished with gaps (exit $rc); publishing what it stored"
# The archive before the store: a store citing payloads the archive lacks is
# the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
