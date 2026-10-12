#!/bin/bash
# Senedd weekly on the Mac Mini (tools/mini_run.sh sd-weekly, Thursdays 07:00 London).
# .github/workflows/sd-weekly.yml is the backup and skips itself when this has run
# (mini-check).
#
# THE SAME STEPS AS THE WORKFLOW'S SCHEDULED RUN, IN ITS ORDER
# (tests/test_mini_jobs.py holds the two together). As there, every step runs whatever the one before did.
# Whatever was gathered is published, as the workflow's guarded publish
# steps do.
# The MS votes page, rebuilt with each member's record on our ground,
# goes out with the commit (the workflow's `git add` names the same files).
# mini_run: commit partner_site/ms-votes.html docs/ms-votes.html
set -o pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mac Mini there is no GITHUB_WORKFLOW, so name it.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Senedd weekly}"
export PYTHONUNBUFFERED=1
python3 tools/raw_state.py --pull || exit 1

rc=0
python3 tools/sd_members.py || rc=1
python3 tools/sd_pull.py || rc=1
python3 tools/sd_divisions.py --parl 908 || rc=1
python3 tools/sd_bills.py || rc=1
python3 tools/sd_committees.py || rc=1
python3 tools/dg_consultations.py --nation wales || rc=1
python3 tools/dv_petitions.py --nation wales || rc=1
python3 tools/devolved_score.py --nation wales --apply || rc=1
python3 tools/devolved_5ca.py --nation wales || rc=1
python3 tools/make_devolved_votes.py --nation wales || rc=1

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
