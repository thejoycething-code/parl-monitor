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
#
# THE JUDGE AND THE EDITION (9 October 2026). After the collectors:
# tools/prov_triage.py when the repository variable PROV_JUDGE is 'on'
# (Christopher's yes; read with gh when PROV_JUDGE is unset here; OFF), then
# the 5CA sheets, then the edition (tools/prov_monitor.py) and its DM to
# Christopher alone. SPEAKS ONCE A DAY, as jobs/us-weekly.sh does: an edition
# already committed for today means another run sent the DM, so it is
# rewritten, not resent. Nothing else here spends or posts.
#
# mini_run: commit editions
set -o pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mac Mini there is no GITHUB_WORKFLOW, so name it.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Provinces weekly}"
export PYTHONUNBUFFERED=1
# The DM goes to Christopher alone (9 October 2026). On the Mini the Slack
# token comes from ~/runner/env, as for the US and Irish weeklies.
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
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

# The judge, only on Christopher's yes (repository variable PROV_JUDGE = on).
# Its backlog on 9 October 2026 was 426 items, about $1.01 (--dry-run).
JUDGE="${PROV_JUDGE:-}"
if [ -z "$JUDGE" ] && [ -z "${GITHUB_ACTIONS:-}" ] && command -v gh >/dev/null 2>&1; then
  JUDGE=$(gh variable get PROV_JUDGE -R thejoycething-code/parl-monitor 2>/dev/null || true)
fi
if [ "$JUDGE" = "on" ]; then
  python3 tools/prov_triage.py --budget-seconds 1200 || rc=1
fi

python3 tools/prov_5ca.py --prov ab --all || rc=1
python3 tools/prov_5ca.py --prov sk --all || rc=1
python3 tools/prov_5ca.py --prov bc --all || rc=1
python3 tools/prov_5ca.py --prov mb --all || rc=1
python3 tools/prov_5ca.py --prov on --all || rc=1
python3 tools/prov_5ca.py --prov nb --all || rc=1
python3 tools/prov_5ca.py --prov nl --all || rc=1
python3 tools/prov_5ca.py --prov ns --all || rc=1
python3 tools/prov_5ca.py --prov qc --all || rc=1

# The edition, after the sheets it quotes. Once a day.
TODAY=$(date +%Y-%m-%d)
if git ls-files --error-unmatch "editions/prov-monitor-$TODAY.md" >/dev/null 2>&1; then
  echo "edition for $TODAY already committed: rewriting it, not resending the DM"
  python3 tools/prov_monitor.py --edition || rc=1
else
  python3 tools/prov_monitor.py --edition --dm || rc=1
fi

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
