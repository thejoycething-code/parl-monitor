#!/bin/bash
# Dominican Republic weekly: the Camara de Diputados' iniciativas, plenary
# sessions, recorded votes with deputies' positions, and the legislator list,
# all from the Chamber's SIL Ciudadano (tools/do_rollcalls.py); then publish
# the raw archive and the store.
#
# Called by .github/workflows/do-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh do-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     DO_RECLASSIFY=true    re-derive every stored DO iniciativa's and vote's
#                           areas, offline, before the pull (after
#                           config/taxonomy-es.yaml or watchlist-do changes)
#
# The first run backfills the 2024-2028 period: about 650 iniciativa pages,
# 203 sessions and 2,600 votes (each with one request for its iniciativas),
# at one request a second to the SIL. The budget (45 minutes) stops it
# cleanly and the next run resumes from the store, so the backfill is spread
# over two or three weeks rather than hammering the SIL in one. Later weeks
# re-read the iniciativa list (about 11 minutes) and only the new sessions.
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
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Dominican Republic weekly}"
if [ "${DO_RECLASSIFY:-}" = "true" ]; then
  python3 tools/do_rollcalls.py --reclassify
fi
rc=0
python3 tools/do_rollcalls.py --budget-seconds 2700 || rc=$?
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "do-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "do-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
