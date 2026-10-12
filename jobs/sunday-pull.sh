#!/bin/bash
# Sunday pull on the Mac Mini (tools/mini_run.sh sunday-pull, Sundays 02:00
# London): pull every feed for the coming week, triage it (TRIAGE=auto, the
# routine weekly spend), write the review file, then publish the raw archive
# and the store. GitHub's .github/workflows/sunday-pull.yml is the backup and
# skips itself when this has run (mini-check, cover-hours).
#
# THE SAME STEPS AS THE WORKFLOW, IN ITS ORDER (tests/test_mini_jobs.py holds
# the two together; folding them into one script is for after a few clean
# Sundays). As there, the follow-up steps run whatever the pull did, and
# whatever was gathered is published. run_weekly.py's pull_log makes a second
# pull for the same week a no-op.
#
# mini_run: commit reviews
set -o pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mac Mini there is no GITHUB_WORKFLOW, so name it.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Sunday pull}"
export PYTHONUNBUFFERED=1
python3 tools/raw_state.py --pull || exit 1

rc=0
WEEK=$(TZ=Europe/London python3 -c "import datetime; t=datetime.date.today(); print((t + datetime.timedelta(days=1) if t.weekday() == 6 else t - datetime.timedelta(days=t.weekday())).isoformat())")
echo "Pulling for week commencing $WEEK"
TRIAGE=auto python3 run_weekly.py --pull "$WEEK" || rc=1
python3 tools/backfill_pq_text.py --limit 400 || rc=1
python3 tools/pull_pbc_attendance.py || rc=1
python3 tools/load_appgs.py || rc=1
python3 tools/pull_interests.py || rc=1
python3 tools/pull_division_rolls.py || rc=1

# The archive before the store: a store citing payloads the archive lacks is
# the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
