#!/bin/bash
# Puberty blocker vote audit backfills on the Mac Mini, BY HAND, one at a time
# (13 October 2026; Chris approved them from the audit, PR #192). Each reads
# an earlier stretch of one country's votes with the country's own collector,
# then publishes the raw archive and the store, as the weeklies do.
#
#   cd ~ && ONE_OFF=nl-2021 JOB_TIMEOUT=7200 \
#     nohup ~/runner/parl-monitor/tools/mini_run.sh pb-backfill \
#     >> ~/runner/logs/pb-backfill.log 2>&1 &
#
#     ONE_OFF   which backfill (required):
#                 us-118    US 118th Congress: bills and HOUSE roll calls
#                           (senate.gov refuses the Mini, and us-weekly.yml's
#                           Senate half reads only the current Congress, so
#                           the 118th's Senate votes stay pending here; since
#                           14 October 2026 GitHub reads them: us-weekly.yml
#                           dispatched by hand with congress=118)
#                 au-46     Australian Senate, 46th Parliament (2019-2022)
#                 au-47     Australian Senate, 47th Parliament (2022-2025)
#                 nl-2021   Tweede Kamer votes since 1 January 2021
#                 fr-senat  French Senat scrutins from the 2023-24 session
#                           (October 2023 on: the dump is downloaded now)
#                 at-xxvii  Austrian Nationalrat and Bundesrat, XXVII. GP
#                           (2019-2024)
#                 cl-2024   Chilean Camara votes since 1 July 2024 (the
#                           PAIG votes are watched by division key in
#                           config/watchlist-cl.yaml)
#     BUDGET    collector seconds (default per backfill below; keep
#               JOB_TIMEOUT above it plus about ten minutes to publish)
#
# Every collector resumes from the store, so a run cut short by its budget is
# simply run again. Runs under the Mini's lock: start long ones when the
# calendar is quiet, never into the 08:30 UN weekday slot.
set -o pipefail
cd "$(dirname "$0")/.."
# Its own heartbeat, never a weekly's (tools/coverage.py ON_DEMAND).
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Puberty blocker backfill}"
export PYTHONUNBUFFERED=1
case "${ONE_OFF:-}" in
  us-118)   DEFAULT=5400 ;;
  au-46|au-47) DEFAULT=3600 ;;
  nl-2021)  DEFAULT=5400 ;;
  fr-senat) DEFAULT=1800 ;;
  at-xxvii) DEFAULT=3600 ;;
  cl-2024)  DEFAULT=5400 ;;
  *) echo "ONE_OFF must be one of us-118 au-46 au-47 nl-2021 fr-senat at-xxvii cl-2024, not '${ONE_OFF:-}'"; exit 2 ;;
esac
BUDGET="${BUDGET:-$DEFAULT}"
[[ "$BUDGET" =~ ^[0-9]+$ ]] || { echo "BUDGET must be a number of seconds, not '$BUDGET'"; exit 2; }
if [ -n "${JOB_TIMEOUT:-}" ] && [ "$JOB_TIMEOUT" -lt $(( BUDGET + 600 )) ]; then
  echo "warning: JOB_TIMEOUT ${JOB_TIMEOUT}s is under the ${BUDGET}s budget plus publishing"
fi
python3 tools/raw_state.py --pull || exit 1

rc=0
echo "pb-backfill: ${ONE_OFF}, ${BUDGET}s of collector clock"
case "$ONE_OFF" in
  us-118)
    python3 tools/us_rollcalls.py --congress 118 --no-senate --budget-seconds "$BUDGET" || rc=$? ;;
  au-46)
    python3 tools/au_rollcalls.py --parliament 46 --chamber senate --budget-seconds "$BUDGET" || rc=$? ;;
  au-47)
    python3 tools/au_rollcalls.py --parliament 47 --chamber senate --budget-seconds "$BUDGET" || rc=$? ;;
  nl-2021)
    python3 tools/nl_rollcalls.py --since 2021-01-01 --budget-seconds "$BUDGET" || rc=$? ;;
  fr-senat)
    python3 tools/fr_senat.py --force --first-session 2023 || rc=$? ;;
  at-xxvii)
    python3 tools/at_rollcalls.py --gp XXVII --budget-seconds "$BUDGET" || rc=$? ;;
  cl-2024)
    python3 tools/cl_rollcalls.py --since 2024-07-01 --no-senate --budget-seconds "$BUDGET" || rc=$? ;;
esac
# Exit 3 is "stored what it could, recorded gaps": still published.
[ "$rc" -eq 3 ] && { echo "pb-backfill: ${ONE_OFF} ended with gaps (recorded in the store)"; rc=0; }

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
