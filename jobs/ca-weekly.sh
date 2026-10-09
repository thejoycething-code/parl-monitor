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
# judge spends (the routine weekly), on the workflow's default clock. Then
# the edition and its DM (tools/ca_monitor.py), committed with the state.
#
# mini_run: commit editions
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

# The edition (tools/ca_monitor.py, 9 October 2026): editions/ca-monitor-<date>.md
# from the store just collected and judged, and a DM to Christopher alone.
# SPEAKS ONCE A DAY, as jobs/us-weekly.sh does: an edition already committed
# for today means another run (the Mini, or GitHub's backup) has sent the DM,
# so it is rewritten, not resent. On the Mini the Slack token comes from
# ~/runner/env.
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
TODAY=$(date +%Y-%m-%d)
if git ls-files --error-unmatch "editions/ca-monitor-$TODAY.md" >/dev/null 2>&1; then
  echo "edition for $TODAY already committed: rewriting it, not resending the DM"
  python3 tools/ca_monitor.py --edition || { echo "  [gap] the edition failed to render"; rc=1; }
else
  python3 tools/ca_monitor.py --edition --dm || { echo "  [gap] the edition or its DM failed"; rc=1; }
fi

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
