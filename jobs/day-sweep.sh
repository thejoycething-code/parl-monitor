#!/bin/bash
# Day sweep: sweep Hansard for the sitting days not yet swept, DM the day's
# debates on our issues, then publish the raw archive and the store.
#
# Called by .github/workflows/day-sweep.yml and, on the Mac Mini, by
# tools/mini_run.sh day-sweep. One script, two callers
# (docs/mac-mini-runner.md). Both fetch the store first; the caller commits
# the sidecars.
#
#     DAY_SWEEP_SINCE=YYYY-MM-DD  first day to consider (default 3 days ago)
#     DAY_SWEEP_RADAR_ONLY=true   find the debates, write no ledger rows
#     DAY_SWEEP_SLOT=morning      also drip the Supreme Court backfill. Unset,
#                                 a run before noon London counts as morning
#                                 (the Mini runs only at its slots); the
#                                 workflow sets it from the cron that fired.
#     DAY_SWEEP_LOGS=<dir>        where sweep.log and ca-courts.log go (/tmp)
#
# Whatever the sweep completed IS published, even if it failed part-way:
# every write is an upsert, so a re-run completes the job.
set -o pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped by db_state.py --push) is keyed on the
# workflow's name; on the Mac Mini there is no GITHUB_WORKFLOW, so name it, or
# tools/coverage.py would see this pipeline stop the day GitHub's backup skips.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Day sweep}"
LOGS="${DAY_SWEEP_LOGS:-/tmp}"
SLOT="${DAY_SWEEP_SLOT:-$( [ "$(TZ=Europe/London date +%H)" -lt 12 ] && echo morning || echo evening )}"

python3 tools/raw_state.py --pull || exit 1

ARGS=()
[ -n "${DAY_SWEEP_SINCE:-}" ] && ARGS+=(--since "$DAY_SWEEP_SINCE")
python3 tools/day_sweep.py "${ARGS[@]}" --dry-run | tee "$LOGS/pending.log"
[ "${DAY_SWEEP_RADAR_ONLY:-}" = "true" ] && ARGS+=(--radar-only)
python3 tools/day_sweep.py --dm "${ARGS[@]}" 2>&1 | tee "$LOGS/sweep.log"
rc=$?

# Supreme Court backfill, a daily drip on the morning slot until it is done.
if [ "$SLOT" = morning ] && [ ! -f data/ca-courts-backfill.done ]; then
  python3 tools/ca_courts.py --backfill --since 2010 --limit 150 --budget-seconds 900 2>&1 \
    | tee "$LOGS/ca-courts.log" || true
  if grep -q "^ca-courts: 0 judgment(s) read" "$LOGS/ca-courts.log" && ! grep -q "Norma\|\[gap\]" "$LOGS/ca-courts.log"; then
    date -u +%Y-%m-%dT%H:%MZ > data/ca-courts-backfill.done
    echo "Supreme Court backfill complete; the drip stops here."
  fi
fi

python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
