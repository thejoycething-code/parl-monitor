#!/bin/bash
# EU day sweep: European Parliament roll calls and speeches for the days not
# yet swept, DM what lands on our ground, then publish the raw archive and the
# store.
#
# Called by .github/workflows/eu-day-sweep.yml and, on the Mac Mini, by
# tools/mini_run.sh eu-day-sweep. One script, two callers
# (docs/mac-mini-runner.md). Both fetch the store first; the caller commits
# the sidecars.
#
#     EU_SWEEP_SINCE=YYYY-MM-DD   first day to consider (default 7 days ago)
#     EU_SWEEP_LOGS=<dir>         where eu-pending.log and eu-sweep.log go (/tmp)
#
# Whatever the sweep completed IS published, even if it failed part-way:
# every write is an upsert, so a re-run completes the job.
set -o pipefail
cd "$(dirname "$0")/.."
LOGS="${EU_SWEEP_LOGS:-/tmp}"

python3 tools/raw_state.py --pull || exit 1

ARGS=()
[ -n "${EU_SWEEP_SINCE:-}" ] && ARGS+=(--since "$EU_SWEEP_SINCE")
python3 tools/eu_day_sweep.py "${ARGS[@]}" --dry-run | tee "$LOGS/eu-pending.log"
python3 tools/eu_day_sweep.py --dm "${ARGS[@]}" 2>&1 | tee "$LOGS/eu-sweep.log"
rc=$?

python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
