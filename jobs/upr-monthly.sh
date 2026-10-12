#!/bin/bash
# UPR monthly on the Mac Mini (tools/mini_run.sh upr-monthly, the 3rd of each month, 07:00 London).
# .github/workflows/upr-monthly.yml is the backup and skips itself when this has run
# (mini-check).
#
# THE SAME STEPS AS THE WORKFLOW'S SCHEDULED RUN, IN ITS ORDER
# (tests/test_mini_jobs.py holds the two together). As there, the steps stop at the first failure.
# Whatever was gathered is published, as the workflow's guarded publish
# steps do.
#
# mini_run: commit docs/upr-tracker.md docs/upr-tracker.csv
set -o pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mac Mini there is no GITHUB_WORKFLOW, so name it.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-UPR monthly}"
export PYTHONUNBUFFERED=1
python3 tools/raw_state.py --pull || exit 1

rc=0
(
  set -e
  python3 tools/pull_upr.py
  python3 tools/make_upr_tracker.py --csv
) || rc=1

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
