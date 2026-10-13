#!/bin/bash
# UN calls weekday check on the Mac Mini (tools/mini_run.sh un-weekday, Monday to
# Friday, 08:30 London). Chris signed off on 13 October 2026: unpaused, every
# weekday, DM to him alone (tools/post_un_calls.py forces U05LJP0BT61, never a
# channel). .github/workflows/un-calls-weekly.yml is the backup and skips itself
# when this has run (mini-check).
#
# THE SAME TOOL AS THE WORKFLOW'S SCHEDULED RUN (tests/test_mini_jobs.py holds
# the two together), but with the store: --db says what is NEW since the last
# run and lets the docs.un.org draft walks resume. The backup runs stateless
# (a first sign there is one dated in the last seven days), so it needs no
# store and never queues behind the other store writers on GitHub.
#
# post_un_calls exits 3 when the DM went out but a source could not be read
# (the DM's check log says which). That is delivered, not failed: a nonzero
# exit here would leave MINI_LAST unset and GitHub's backup would send the
# same DM again, every weekday OHCHR stays challenged.
set -o pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mac Mini there is no GITHUB_WORKFLOW, so name it.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-UN calls weekday}"
export PYTHONUNBUFFERED=1
python3 tools/raw_state.py --pull || exit 1

rc=0
python3 tools/post_un_calls.py --db data/parl-monitor.db
sent=$?
if [ "$sent" -eq 3 ]; then
  echo "un-weekday: DM sent; some sources could not be read (named in the DM's check log)"
elif [ "$sent" -ne 0 ]; then
  rc=1
fi

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
