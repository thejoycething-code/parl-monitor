#!/bin/bash
# Canada weekly on the Mac Mini (tools/mini_run.sh ca-weekly, Tuesdays 11:00 London).
# .github/workflows/ca-weekly.yml is the backup and skips itself when this has run
# (mini-check).
#
# THE SAME STEPS AS THE WORKFLOW'S SCHEDULED RUN, IN ITS ORDER
# (tests/test_mini_jobs.py holds the two together). As there, every step runs whatever the one before did.
# Whatever was gathered is published, as the workflow's guarded publish
# steps do.
# The dispatch-only backfills and repairs stay on GitHub. The petition
# judge spends (the routine weekly), on the workflow's default clock.
set -o pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mac Mini there is no GITHUB_WORKFLOW, so name it.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Canada weekly}"
export PYTHONUNBUFFERED=1
python3 tools/raw_state.py --pull || exit 1

rc=0
python3 tools/ca_rollcalls.py --session 45-1 || rc=1
python3 tools/ca_senate.py --session 45-1 || rc=1
python3 tools/ca_hansard.py --session 45-1 || rc=1
python3 tools/ca_senate_debates.py --session 45-1 --budget-seconds 900 || rc=1
python3 tools/ca_committees.py --session 45-1 --budget-seconds 1200 || rc=1
python3 tools/ca_courts.py || rc=1
python3 tools/ca_petitions.py --limit 300 || rc=1
python3 tools/ca_gazette.py || rc=1
python3 tools/ca_triage.py --limit 2000 --budget-seconds 1200 || rc=1

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
