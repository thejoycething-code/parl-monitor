#!/bin/bash
# Holyrood weekly on the Mac Mini (tools/mini_run.sh sp-weekly, Fridays 07:00
# London): roster, questions and motions, divisions and member votes,
# committee scrutiny, Scottish Government consultations, petitions, the scored
# divisions and the Holyrood 5CA sheets; then the raw archive and the store.
# .github/workflows/sp-weekly.yml is the backup and skips itself when this
# has run (mini-check).
#
# THE SAME STEPS AS THE WORKFLOW, IN ITS ORDER (tests/test_mini_jobs.py holds
# the two together). As there, every step runs whatever the one before did,
# and whatever was gathered is published. Nothing here spends or posts.
# The MSP votes page, rebuilt with each member's record on our ground,
# goes out with the commit (the workflow's `git add` names the same files).
# mini_run: commit partner_site/msp-votes.html docs/msp-votes.html
set -o pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mac Mini there is no GITHUB_WORKFLOW, so name it.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Holyrood weekly}"
export PYTHONUNBUFFERED=1
python3 tools/raw_state.py --pull || exit 1

rc=0
python3 tools/sp_pull.py || rc=1
python3 tools/sp_divisions.py || rc=1
python3 tools/sp_committees.py || rc=1
python3 tools/dg_consultations.py --nation scotland || rc=1
python3 tools/dv_petitions.py --nation scotland || rc=1
python3 tools/sp_score.py --apply || rc=1
python3 tools/devolved_5ca.py --nation scotland || rc=1
python3 tools/make_msp_votes.py || rc=1

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
