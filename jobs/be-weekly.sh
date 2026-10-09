#!/bin/bash
# Belgium weekly: members, dossiers, plenary sittings and recorded votes of
# the federal Chamber (tools/be_rollcalls.py), then publish the raw archive
# and the store.
#
# Called by .github/workflows/be-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh be-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     BE_RECLASSIFY=true    re-apply config/watchlist-be.yaml to every stored
#                           dossier and division, offline, before the pull
#
#     BE_PUBLISH=false      collect only (GitHub, whose own steps publish)
#
# Exit codes on the Mini. The collector exits 3 when it stored what it could
# and recorded gaps (in the gaps table and as [gap] lines in the log): that
# run is still published, and this script exits 0 so mini_run.sh commits the
# sidecars with it. Any other failure publishes NOTHING and exits non-zero: a
# half-written store is not worth a published store whose sidecar never got
# committed, and the next run re-reads whatever this one missed. With
# BE_PUBLISH=false the collector's exit code is passed straight through, so a
# gap turns the GitHub step red and the failure alert hears of it.
#
# THE EDITION (10 October 2026): after the collector, the Belgian weekly
# edition (tools/be_monitor.py, src/country_edition.py) is rendered to
# editions/be-monitor-<date>.md and DMed to Chris alone. Once a day: an
# edition already committed for today is rewritten, not resent. Its failure
# is a [gap] line and never costs the store.
#
# mini_run: commit editions
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped by db_state.py --push) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Belgium weekly}"
if [ "${BE_RECLASSIFY:-}" = "true" ]; then
  python3 tools/be_rollcalls.py --reclassify
fi
rc=0
python3 tools/be_rollcalls.py --budget-seconds 2700 || rc=$?
# The edition, from the store just collected (not when the collector failed
# outright: a half-read week is not worth a DM).
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  TODAY=$(date +%Y-%m-%d)
  if git ls-files --error-unmatch "editions/be-monitor-$TODAY.md" >/dev/null 2>&1; then
    echo "edition for $TODAY already committed: rewriting it, not resending the DM"
    python3 tools/be_monitor.py --edition || echo "  [gap] the edition failed to render"
  else
    python3 tools/be_monitor.py --edition --dm || echo "  [gap] the edition or its DM failed"
  fi
fi
if [ "${BE_PUBLISH:-true}" = "false" ]; then
  exit "$rc"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "be-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "be-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
