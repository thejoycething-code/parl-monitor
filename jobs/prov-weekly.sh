#!/bin/bash
# Provinces weekly on the Mac Mini (tools/mini_run.sh prov-weekly, Wednesdays 11:00 London).
# .github/workflows/prov-weekly.yml is the backup and skips itself when this has run
# (mini-check).
#
# THE SAME STEPS AS THE WORKFLOW'S SCHEDULED RUN, IN ITS ORDER
# (tests/test_mini_jobs.py holds the two together). As there, every step runs whatever the one before did.
# Whatever was gathered is published, as the workflow's guarded publish
# steps do.
# The dispatch-only backfills stay on GitHub, or run here by hand.
# Nothing here spends or posts.
set -o pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mac Mini there is no GITHUB_WORKFLOW, so name it.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Provinces weekly}"
export PYTHONUNBUFFERED=1
python3 tools/raw_state.py --pull || exit 1

rc=0
python3 tools/prov_collect.py --prov ab --resume --budget-seconds 900 || rc=1
python3 tools/prov_collect.py --prov sk --resume --budget-seconds 600 || rc=1
python3 tools/prov_collect.py --prov bc --resume --budget-seconds 600 || rc=1
python3 tools/prov_collect.py --prov mb --resume --budget-seconds 900 || rc=1
python3 tools/prov_collect.py --prov on --resume --budget-seconds 900 || rc=1
python3 tools/prov_collect.py --prov nb --resume --budget-seconds 1200 || rc=1
python3 tools/prov_collect.py --prov nl --resume --budget-seconds 600 || rc=1
python3 tools/prov_collect.py --prov ns --resume --budget-seconds 900 || rc=1
python3 tools/prov_collect.py --prov qc --roster-only --budget-seconds 600 || rc=1
python3 tools/prov_collect.py --prov qc --resume --budget-seconds 900 || rc=1
python3 tools/prov_speeches.py --prov ab --resume --budget-seconds 600 || rc=1
python3 tools/prov_speeches.py --prov sk --resume --budget-seconds 600 || rc=1
python3 tools/prov_speeches.py --prov bc --resume --budget-seconds 480 || rc=1
python3 tools/prov_speeches.py --prov mb --resume --budget-seconds 600 || rc=1
python3 tools/prov_speeches.py --prov on --resume --budget-seconds 600 || rc=1
python3 tools/prov_speeches.py --prov nb --resume --budget-seconds 900 || rc=1
python3 tools/prov_speeches.py --prov nl --resume --budget-seconds 480 || rc=1
python3 tools/prov_speeches.py --prov qc --resume --budget-seconds 600 || rc=1
python3 tools/prov_5ca.py --prov ab --all || rc=1
python3 tools/prov_5ca.py --prov sk --all || rc=1
python3 tools/prov_5ca.py --prov bc --all || rc=1
python3 tools/prov_5ca.py --prov mb --all || rc=1
python3 tools/prov_5ca.py --prov on --all || rc=1
python3 tools/prov_5ca.py --prov nb --all || rc=1
python3 tools/prov_5ca.py --prov nl --all || rc=1
python3 tools/prov_5ca.py --prov ns --all || rc=1
python3 tools/prov_5ca.py --prov qc --all || rc=1

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
