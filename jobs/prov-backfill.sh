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
#     ONE_OFF         a named one-off instead of PROVINCES (13 October 2026):
#                       nb-56-4  New Brunswick 56-4 with the Legislative
#                                Library's members page (config/prov-nb-56-4/):
#                                the session's Journals from its first sitting
#                                (17 November 2009), so its 11 recorded votes
#                                are stored and resolved; the Hansard of 28 May
#                                2026 re-read in full; and the two days the
#                                legislatures corrected (NL 3 October 2022,
#                                complete; MB 10 May 2024, no sitting) re-read.
#                       cd ~ && ONE_OFF=nb-56-4 MINUTES=60 JOB_TIMEOUT=4800 \
#                         nohup ~/runner/parl-monitor/tools/mini_run.sh prov-backfill \
#                         >> ~/runner/logs/prov-backfill.log 2>&1 &
#                       on-closure  Ontario's closure days re-read (16 October
#                                2026, PR #226): every sitting day whose stored
#                                division question has "Motion for closure on"
#                                is collected again with --refresh, so each
#                                closure sits on the bill it names (stage
#                                Closure); then Ontario's 5CA sheets.
#                       cd ~ && ONE_OFF=on-closure MINUTES=90 JOB_TIMEOUT=6600 \
#                         nohup ~/runner/parl-monitor/tools/mini_run.sh prov-backfill \
#                         >> ~/runner/logs/prov-backfill.log 2>&1 &
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
case "${ONE_OFF:-}" in
  ""|nb-56-4|on-closure) ;;
  *) echo "ONE_OFF must be nb-56-4 or on-closure, not '${ONE_OFF}'"; exit 2 ;;
esac
[ -n "${PROVINCES:-}" ] || [ -n "${ONE_OFF:-}" ] || { echo "PROVINCES is required (e.g. PROVINCES=\"nb on\")"; exit 2; }
MINUTES="${MINUTES:-280}"
[[ "$MINUTES" =~ ^[0-9]+$ ]] || { echo "MINUTES must be a number, not '$MINUTES'"; exit 2; }
if [ -n "${JOB_TIMEOUT:-}" ] && [ "$JOB_TIMEOUT" -lt $(( MINUTES * 60 + 600 )) ]; then
  echo "warning: JOB_TIMEOUT ${JOB_TIMEOUT}s is under the ${MINUTES}-minute clock plus publishing"
fi
python3 tools/raw_state.py --pull || exit 1

rc=0
if [ "${ONE_OFF:-}" = "nb-56-4" ]; then
  # New Brunswick 56-4 (docs/mac-mini.md, "New Brunswick 56-4"). Sittings
  # already read cleanly are skipped; the roster comes from
  # config/prov-nb-56-4/members.csv and the Library's index of recorded votes
  # is checked against the store (all 11 must be there).
  [ "$MINUTES" -ge 30 ] || { echo "ONE_OFF=nb-56-4 needs MINUTES of at least 30"; exit 2; }
  echo "one-off nb-56-4: ${MINUTES} minutes of clock"
  python3 tools/prov_collect.py --prov nb --session 56-4 --since 2009-11-17 --until 2010-04-16 \
    --budget-seconds $(( MINUTES * 60 - 900 )) || rc=1
  python3 tools/prov_speeches.py --prov nb --session 61-2 --since 2026-05-28 --until 2026-05-28 \
    --budget-seconds 300 || rc=1
  python3 tools/prov_collect.py --prov nl --session 50-1 --since 2022-10-03 --until 2022-10-03 \
    --no-bills --budget-seconds 300 || rc=1
  python3 tools/prov_speeches.py --prov nl --session 50-1 --since 2022-10-03 --until 2022-10-03 \
    --budget-seconds 300 || rc=1
  python3 tools/prov_speeches.py --prov mb --session 43-1 --since 2024-05-10 --until 2024-05-10 \
    --budget-seconds 300 || rc=1
  set -- nb nl mb
elif [ "${ONE_OFF:-}" = "on-closure" ]; then
  # The days come from the store BEFORE the re-read, when a closure's question
  # still carries its "Motion for closure on" line. A day not reached within
  # the clock stays as it was; running this again reads every day again.
  DAYS=$(python3 - <<'PY'
import sqlite3
db = sqlite3.connect("data/parl-monitor.db")
for s, d in db.execute("select distinct legislature || '-' || session, date from prov_divisions "
                       "where prov = 'on' and kind = 'recorded' and question like '%Motion for closure on%' "
                       "order by date"):
    print(s, d)
PY
) || { echo "could not list the closure days"; exit 1; }
  n=$(printf "%s\n" "$DAYS" | grep -c .)
  echo "one-off on-closure: $n day(s), ${MINUTES} minutes of clock"
  [ "$n" -gt 0 ] || { echo "no closure days in the store"; exit 1; }
  done_n=0
  while read -r sess day; do
    [ -n "$day" ] || continue
    if [ "$SECONDS" -ge $(( MINUTES * 60 - 600 )) ]; then
      echo "clock spent: $done_n of $n day(s) re-read; run again for the rest"; rc=1; break
    fi
    python3 tools/prov_collect.py --prov on --session "$sess" --since "$day" --until "$day" \
      --refresh --no-bills --budget-seconds 300 || rc=1
    done_n=$(( done_n + 1 ))
  done <<< "$DAYS"
  echo "on-closure: $done_n of $n day(s) re-read"
  set -- on
else
set -- $PROVINCES
PER=$(( MINUTES * 60 / $# ))
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
