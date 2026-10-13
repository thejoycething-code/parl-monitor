#!/bin/bash
# Slovakia: every member's position on the term's votes, BY HAND on the Mac
# Mini (P7, the puberty blocker vote audit, 13 October 2026). Not a feed and
# not scheduled (no plist, no workflow): the weekly (jobs/sk-weekly.sh) reads
# about 440 vote pages in its 20 minutes, our ground first, then newest first,
# so the 4,606 votes of the 9th term fill in about ten weeks that way. This
# reads only vote pages (no prints' documents, no interpellations) for as long
# as JOB_TIMEOUT leaves after the publish, then publishes. Every vote is
# committed as it is read (positions_at), so a run cut short loses nothing
# and the next resumes where it stopped; rerun until it says no vote is owed.
#
#   cd ~ && JOB_TIMEOUT=7200 nohup ~/runner/parl-monitor/tools/mini_run.sh \
#     sk-positions-backfill >> ~/runner/logs/sk-positions-backfill.log 2>&1 &
#
#     SK_RECLASSIFY=true  first re-derive every stored print's, vote's and
#                         interpellation's areas, offline, the prints' bill
#                         documents matched again from the raw archive
#                         (tools/sk_rollcalls.py --reclassify): after a
#                         taxonomy-sk or watchlist-sk change
#     BUDGET              collector seconds (default: what JOB_TIMEOUT leaves,
#                         tools/collector_budget.sh, at most 3 hours)
#
# www.nrsr.sk: the hlasklub page is the only source of positions (no
# per-vote endpoint in the open data, no robots.txt; docs/slovakia-scope.md),
# 2 to 3 seconds a vote on average on the Mini with the 1-second throttle,
# single pages up to 96 seconds. Never while the Slovak weekly runs (Tuesdays
# 02:00 London; mini_run.sh's lock keeps them apart anyway).
set -eo pipefail
cd "$(dirname "$0")/.."
# Its own heartbeat, never the weekly's (tools/coverage.py ON_DEMAND).
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Slovakia positions backfill}"
export PYTHONUNBUFFERED=1
if [ "${SK_RECLASSIFY:-}" = "true" ]; then
  python3 tools/sk_rollcalls.py --reclassify
fi
BUDGET="${BUDGET:-$(bash tools/collector_budget.sh 10800 "$SECONDS")}"
[[ "$BUDGET" =~ ^[0-9]+$ ]] || { echo "BUDGET must be a number of seconds, not '$BUDGET'"; exit 2; }
rc=0
python3 tools/sk_rollcalls.py --positions all --no-interpellations --no-documents \
  --budget-seconds "$BUDGET" || rc=$?
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "sk-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
