#!/bin/bash
# NI Assembly weekly on the Mac Mini (tools/mini_run.sh ni-weekly, Saturdays 07:00 London).
# .github/workflows/ni-weekly.yml is the backup and skips itself when this has run
# (mini-check).
#
# THE SAME STEPS AS THE WORKFLOW'S SCHEDULED RUN, IN ITS ORDER
# (tests/test_mini_jobs.py holds the two together). As there, the first three steps stop at the first failure and the rest run whatever happened.
# Whatever was gathered is published, as the workflow's guarded publish
# steps do.
# The MLA votes page, rebuilt with each member's record on our ground,
# goes out with the commit (the workflow's `git add` names the same files).
# mini_run: commit partner_site/mla-votes.html docs/mla-votes.html
set -o pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mac Mini there is no GITHUB_WORKFLOW, so name it.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-NI Assembly weekly}"
export PYTHONUNBUFFERED=1
python3 tools/raw_state.py --pull || exit 1

rc=0
(
  set -e
  python3 tools/ni_pull.py
  python3 tools/ni_divisions.py
  python3 tools/ni_classify.py --apply
) || rc=1
python3 tools/ni_committees.py || rc=1
python3 tools/dg_consultations.py --nation ni || rc=1
python3 tools/devolved_score.py --nation ni --apply || rc=1
python3 tools/devolved_5ca.py --nation ni || rc=1
python3 tools/make_devolved_votes.py --nation ni || rc=1

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
