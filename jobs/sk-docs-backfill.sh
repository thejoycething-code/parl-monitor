#!/bin/bash
# Slovakia, SK6: the bill documents of the term's backlog of prints, BY HAND on
# the Mac Mini. Not a feed and not scheduled (no plist, no workflow): the
# weekly (jobs/sk-weekly.sh) reads new prints' documents in its first ten
# minutes, but the 9th term's backlog (about 836 prints on 10 October 2026,
# about 11 seconds a print at nrsr.sk's measured speed: two and a half hours)
# would take fifteen weeks that way. Each run reads for 55 minutes (under
# mini_run.sh's hour) and stops; a print is read once, so rerun it until it
# says no prints are left (three runs), never while the Slovak weekly runs
# (Tuesdays 02:00 London; mini_run.sh's lock keeps them apart anyway).
#
#   cd ~ && nohup ~/runner/parl-monitor/tools/mini_run.sh sk-docs-backfill \
#     >> ~/runner/logs/sk-docs-backfill.log 2>&1 &
#
# Reads only the prints' pages and their two documents (bill text and
# explanatory memorandum) on www.nrsr.sk, one request a second at most; no
# vote pages, no interpellations. Then the raw archive and the store are
# published.
set -eo pipefail
cd "$(dirname "$0")/.."
# Its own heartbeat, never the weekly's (tools/coverage.py ON_DEMAND).
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Slovakia documents backfill}"
export PYTHONUNBUFFERED=1
rc=0
python3 tools/sk_rollcalls.py --positions none --no-interpellations \
  --doc-budget-seconds 3300 || rc=$?
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "sk-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
