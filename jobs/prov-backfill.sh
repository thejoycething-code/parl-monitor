#!/bin/bash
# Provinces backfill on the Mac Mini, BY HAND (9 October 2026). Backfills used
# to be dispatched to prov-weekly.yml on GitHub: 2,308 minutes in one week,
# against the 60-a-day bar for making the repo private. Same options as that
# dispatch form, same steps, same order; then the raw archive and the store.
#
#   cd ~ && PROVINCES="nb on" SINCE=2010-01-01 MINUTES=280 JOB_TIMEOUT=18000 \
#     nohup ~/runner/parl-monitor/tools/mini_run.sh prov-backfill \
#     >> ~/runner/logs/prov-backfill.log 2>&1 &
#
#     PROVINCES       space-separated: ab sk bc mb on nb nl qc ns (required)
#     SINCE           votes backfill from this date (default 2010-01-01)
#     SPEECHES_SINCE  Hansard SPEECHES from this date instead of votes
#     MINUTES         one clock shared by the provinces (default 280; no cap
#                     here, but give mini_run.sh a JOB_TIMEOUT above it)
#
# A day or session read badly stays owed and is read again by the next run.
# Runs under the Mini's lock, so it queues behind (and holds up) the
# scheduled jobs: start long ones when the calendar is quiet.
set -o pipefail
cd "$(dirname "$0")/.."
# Its own heartbeat, never the weekly's: a backfill must not make a dead
# Provinces weekly look alive (tools/coverage.py ON_DEMAND).
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Provinces backfill}"
export PYTHONUNBUFFERED=1
[ -n "${PROVINCES:-}" ] || { echo "PROVINCES is required (e.g. PROVINCES=\"nb on\")"; exit 2; }
MINUTES="${MINUTES:-280}"
[[ "$MINUTES" =~ ^[0-9]+$ ]] || { echo "MINUTES must be a number, not '$MINUTES'"; exit 2; }
if [ -n "${JOB_TIMEOUT:-}" ] && [ "$JOB_TIMEOUT" -lt $(( MINUTES * 60 + 600 )) ]; then
  echo "warning: JOB_TIMEOUT ${JOB_TIMEOUT}s is under the ${MINUTES}-minute clock plus publishing"
fi
python3 tools/raw_state.py --pull || exit 1

set -- $PROVINCES
PER=$(( MINUTES * 60 / $# ))
rc=0
if [ -n "${SPEECHES_SINCE:-}" ]; then
  [[ "$SPEECHES_SINCE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || { echo "SPEECHES_SINCE must be YYYY-MM-DD"; exit 2; }
  echo "speeches backfill: $# province(s) from $SPEECHES_SINCE, ${PER}s of clock each"
  for p in "$@"; do
    case "$p" in ab|sk|bc|mb|on|nb|nl|qc) ;; *) echo "$p has no Hansard reader (ab sk bc mb on nb nl qc)"; rc=1; continue ;; esac
    python3 tools/prov_speeches.py --prov "$p" --all-sessions --since "$SPEECHES_SINCE" --budget-seconds "$PER" || rc=1
  done
else
  SINCE="${SINCE:-2010-01-01}"
  [[ "$SINCE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || { echo "SINCE must be YYYY-MM-DD"; exit 2; }
  echo "backfill: $# province(s) from $SINCE, ${PER}s of clock each"
  for p in "$@"; do
    case "$p" in ab|sk|bc|mb|on|nb|nl|qc|ns) ;; *) echo "$p is not a built province (ab sk bc mb on nb nl qc ns)"; rc=1; continue ;; esac
    python3 tools/prov_collect.py --prov "$p" --all-sessions --since "$SINCE" --budget-seconds "$PER" || rc=1
  done
fi
# The 5CA sheets of the backfilled provinces, as the workflow does.
for p in "$@"; do
  case "$p" in ab|sk|bc|mb|on|nb|nl|qc|ns) ;; *) continue ;; esac
  python3 tools/prov_5ca.py --prov "$p" --all || rc=1
done

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
