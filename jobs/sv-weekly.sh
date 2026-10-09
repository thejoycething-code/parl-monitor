#!/bin/bash
# El Salvador weekly: recorded plenary votes with every deputy's position,
# the dictámenes and piezas they decide, and the deputies of the Asamblea
# Legislativa (tools/sv_rollcalls.py), then publish the raw archive and the
# store.
#
# Called by .github/workflows/sv-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh sv-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     SV_RECLASSIFY=true    re-derive every stored SV dictamen's, pieza's and
#                           vote's areas, offline, before the pull (after
#                           config/taxonomy-es.yaml or watchlist-sv changes)
#
# The first run backfills the 2024-2027 legislature: 784 votes (one PDF
# each, about 400 KB, not archived) and every one of its 890 days from the
# session archive (about 37 s a sitting day, 1 s a day without one). About
# four hours in all: the budget (45 minutes, half of it at most for the
# archive) stops each run cleanly and the next resumes from the store, so
# at this budget the backfill takes about six Sundays
# (docs/el-salvador-scope.md).
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
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-El Salvador weekly}"
if [ "${SV_RECLASSIFY:-}" = "true" ]; then
  python3 tools/sv_rollcalls.py --reclassify
fi
rc=0
python3 tools/sv_rollcalls.py --budget-seconds 2700 || rc=$?
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "sv-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "sv-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
