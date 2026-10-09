#!/bin/bash
# Canada backfill on the Mac Mini, BY HAND (9 October 2026): the one-off and
# repair parts of ca-weekly.yml's dispatch form, which cost 296 GitHub minutes
# in one week. Same options, same steps, same order; then the raw archive and
# the store. The weekly's own collection and its petition judge are NOT run
# here: the Tuesday weekly does those.
#
#   cd ~ && CA_OLDER_SESSIONS="43-2 43-1" CA_OLDER_PETITIONS=true JOB_TIMEOUT=14400 \
#     nohup ~/runner/parl-monitor/tools/mini_run.sh ca-backfill \
#     >> ~/runner/logs/ca-backfill.log 2>&1 &
#
#     CA_BACKFILL=true          the one-off backfill (44-1 divisions, 45-1 Hansard
#                               and petitions below the highest held, the Gazette)
#     CA_ROLLCALL_SESSIONS="…"  re-tag and fetch roll-calls (no Hansard)
#     CA_OLDER_SESSIONS="…"     earlier sessions: divisions, bills, Senate, Hansard
#     CA_OLDER_PETITIONS=true   ...and their presented petitions (~105 min for three)
#     CA_GAZETTE_SINCE=YYYY-MM-DD   Gazette back to this date
#     CA_GAZETTE_FORGET="p1-2011-*" Gazette issues to drop and re-read (globs)
#     CA_FEDERAL_BACKFILL="senate committees courts"  (one part a run, as on GitHub)
#     CA_REFRESH_MEMBERS=true   repair names/parties/ridings from the rosters
#     CA_RETAG=true             retag stored rows under the current taxonomy
set -o pipefail
cd "$(dirname "$0")/.."
# Its own heartbeat, never the weekly's (tools/coverage.py ON_DEMAND).
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Canada backfill}"
export PYTHONUNBUFFERED=1
on() { [ "${1:-}" = "true" ] || [ "${1:-}" = "1" ]; }
if ! on "${CA_BACKFILL:-}" && [ -z "${CA_ROLLCALL_SESSIONS:-}${CA_OLDER_SESSIONS:-}${CA_GAZETTE_SINCE:-}${CA_FEDERAL_BACKFILL:-}" ] \
   && ! on "${CA_REFRESH_MEMBERS:-}" && ! on "${CA_RETAG:-}"; then
  echo "nothing asked for: set CA_BACKFILL, CA_OLDER_SESSIONS, CA_ROLLCALL_SESSIONS, CA_GAZETTE_SINCE,"
  echo "CA_FEDERAL_BACKFILL, CA_REFRESH_MEMBERS or CA_RETAG (see the head of this script)"
  exit 2
fi
python3 tools/raw_state.py --pull || exit 1

rc=0
if on "${CA_BACKFILL:-}"; then
  python3 tools/ca_rollcalls.py --session 44-1 || rc=1
  python3 tools/ca_hansard.py --session 45-1 --backfill --limit 200 --budget-seconds 2700 || rc=1
  python3 tools/ca_petitions.py --backfill --limit 1400 --budget-seconds 2700 || rc=1
  python3 tools/ca_gazette.py --since 2025-05-26 --budget-seconds 2400 || rc=1
fi
for s in ${CA_ROLLCALL_SESSIONS:-}; do
  python3 tools/ca_rollcalls.py --session "$s" --no-bills || rc=1
  python3 tools/ca_senate.py --session "$s" || rc=1
done
for s in ${CA_OLDER_SESSIONS:-}; do
  python3 tools/ca_rollcalls.py --session "$s" || rc=1
  python3 tools/ca_senate.py --session "$s" || rc=1
done
for s in ${CA_OLDER_SESSIONS:-}; do
  python3 tools/ca_hansard.py --session "$s" --limit 400 --budget-seconds 1800 || rc=1
done
if on "${CA_OLDER_PETITIONS:-}"; then
  for s in ${CA_OLDER_SESSIONS:-}; do
    python3 tools/ca_petitions.py --session "$s" --limit 6000 --budget-seconds 4500 || rc=1
  done
fi
if [ -n "${CA_GAZETTE_SINCE:-}" ]; then
  set -f   # the globs are for SQLite, not the shell
  python3 tools/ca_gazette.py --since "$CA_GAZETTE_SINCE" --budget-seconds 3000 \
    ${CA_GAZETTE_FORGET:+--forget $CA_GAZETTE_FORGET} || rc=1
  set +f
fi
case " ${CA_FEDERAL_BACKFILL:-} " in *" senate "*)
  python3 tools/ca_senate_debates.py --backfill --limit 400 --budget-seconds 2700 || rc=1 ;; esac
case " ${CA_FEDERAL_BACKFILL:-} " in *" committees "*)
  # One clock across the sessions, newest first, as on GitHub.
  end=$((SECONDS + 2700))
  for s in 44-1 43-2 43-1 42-1 41-2 41-1 40-3; do
    left=$((end - SECONDS)); [ "$left" -lt 180 ] && { echo "  clock spent before $s; the next run carries on"; break; }
    python3 tools/ca_committees.py --session "$s" --limit 400 --budget-seconds "$left" || rc=1
  done ;; esac
case " ${CA_FEDERAL_BACKFILL:-} " in *" courts "*)
  python3 tools/ca_courts.py --backfill --since 2010 --limit 200 --budget-seconds 2700 || rc=1 ;; esac
if on "${CA_REFRESH_MEMBERS:-}"; then python3 tools/ca_hansard.py --refresh-members || rc=1; fi
if on "${CA_RETAG:-}"; then python3 tools/ca_retag.py || rc=1; fi

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
