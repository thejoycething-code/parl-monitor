#!/bin/bash
# Member profiles on the Mac Mini (tools/mini_run.sh member-profiles, the 10th
# of each month, 09:00 London): Commons service and party history, published
# profile detail and the devolved members' profiles; then the raw archive and
# the store. .github/workflows/member-profiles.yml is the backup and skips
# itself when this has run (mini-check).
#
# THE SAME STEPS AS THE WORKFLOW, IN ITS ORDER (tests/test_mini_jobs.py holds
# the two together). As there, every step runs whatever the one before did,
# and whatever was gathered is published. Nothing here spends or posts.
set -o pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mac Mini there is no GITHUB_WORKFLOW, so name it.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Member profiles}"
export PYTHONUNBUFFERED=1
python3 tools/raw_state.py --pull || exit 1

rc=0
python3 tools/pull_service.py || rc=1
python3 tools/pull_profiles.py || rc=1
python3 tools/pull_devolved_profiles.py || rc=1

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
