#!/bin/bash
# US weekly: members, bills, House roll calls and Senate votes of the current
# Congress, the week ahead (floor lists and committee meetings, both
# chambers), the judge when US_JUDGE is on, then the edition and its DM.
#
# Called by .github/workflows/us-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh us-weekly. One script, two callers (docs/mac-mini.md).
# Both callers fetch the store first; this script publishes the raw archive
# and the store itself, and the caller commits data/ and editions/.
#
# SENATE.GOV REFUSES SOME NETWORKS. It answered 403 to every page from the
# laptop on Christopher's home connection (9 October 2026) and answers
# GitHub's runners. So the Senate half goes one of two ways:
#   * senate.gov answers this machine: everything runs here.
#   * it refuses (the Mini, if it shares that connection): the script asks
#     GitHub for a Senate-only run (us-weekly.yml, input senate_only), waits
#     for it to publish, fetches the store again and does the rest here with
#     --no-senate. If GitHub cannot be reached, the week goes ahead without
#     the new Senate votes and says so in a [gap] line.
#
# SPEAKS ONCE A DAY. An edition already committed for today means another
# run (the Mini, or a GitHub backup) has sent the DM: it is rewritten, not
# resent.
#
#     US_RECLASSIFY=true    re-derive stored areas first (taxonomy change)
#     US_SENATE_ONLY=true   the Senate-only half GitHub runs for the Mini
#     US_JUDGE=on           score new items (Christopher's yes; read from the
#                           repo variable when unset and gh is available)
#
# mini_run: commit editions
set -eo pipefail
cd "$(dirname "$0")/.."
LOG="${US_LOG_DIR:-/tmp}"
mkdir -p "$LOG"
SENATE_MENU="https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_119_2.xml"
# The DM goes to Christopher alone (9 October 2026). On the Mini the Slack
# token comes from ~/runner/env, as for Division watch.
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
UA="parl-monitor (CitizenGO parliamentary monitor; thejoycething-code/parl-monitor)"

if [ "${US_RECLASSIFY:-}" = "true" ]; then
  python3 tools/us_rollcalls.py --reclassify | tee "$LOG/us-reclassify.log"
fi

if [ "${US_SENATE_ONLY:-}" = "true" ]; then
  python3 tools/us_rollcalls.py --congress 119 --no-bills --no-rolls --no-members \
    --budget-seconds 1500 | tee "$LOG/us-rollcalls.log"
  python3 tools/us_schedule.py --senate-only | tee "$LOG/us-schedule.log" \
    || echo "  [gap] the Senate week ahead stopped early; its gaps are in the store"
  python3 tools/raw_state.py --push
  python3 tools/db_state.py --push
  exit 0
fi

SENATE_ARGS=()
if ! curl -fsS -o /dev/null -m 30 -A "$UA" "$SENATE_MENU" 2>/dev/null; then
  echo "senate.gov refuses this machine; asking GitHub for the Senate half"
  SENATE_ARGS=(--no-senate)
  if [ -z "${GITHUB_ACTIONS:-}" ] && [ -n "${GH_TOKEN:-}" ] && command -v gh >/dev/null 2>&1; then
    REPO=thejoycething-code/parl-monitor
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    if gh workflow run us-weekly.yml -R "$REPO" --ref "$BRANCH" -f senate_only=true; then
      run_id=
      for _ in $(seq 1 20); do
        sleep 6
        run_id=$(gh run list -R "$REPO" --workflow us-weekly.yml --event workflow_dispatch \
                 --branch "$BRANCH" -L 5 --json databaseId,createdAt \
                 --jq "[.[] | select(.createdAt >= \"$since\")][0].databaseId // empty")
        [ -n "$run_id" ] && break
      done
      if [ -n "$run_id" ] && gh run watch "$run_id" -R "$REPO" --exit-status >/dev/null; then
        echo "GitHub run $run_id published the Senate votes; fetching the store again"
        git pull -q --rebase --autostash origin "$BRANCH"
        python3 tools/db_state.py --pull
      else
        echo "  [gap] Senate half on GitHub failed or never started (run ${run_id:-none}); this week has no new Senate votes"
      fi
    else
      echo "  [gap] could not dispatch the Senate half to GitHub; this week has no new Senate votes"
    fi
  else
    echo "  [gap] senate.gov refused and gh is unavailable; this week has no new Senate votes"
  fi
fi

python3 tools/us_rollcalls.py --congress 119 --budget-seconds 2700 "${SENATE_ARGS[@]}" \
  | tee "$LOG/us-rollcalls.log"

# The week ahead, after the bills (its rows join us_bills for areas) and
# before the edition that prints it. Non-zero means a gap, recorded in the
# store and said in the edition; it never stops the week's edition.
python3 tools/us_schedule.py "${SENATE_ARGS[@]}" | tee "$LOG/us-schedule.log" \
  || echo "  [gap] the week ahead stopped early; the edition says what it has"

JUDGE="${US_JUDGE:-}"
if [ -z "$JUDGE" ] && [ -z "${GITHUB_ACTIONS:-}" ] && command -v gh >/dev/null 2>&1; then
  JUDGE=$(gh variable get US_JUDGE -R thejoycething-code/parl-monitor 2>/dev/null || true)
fi
if [ "$JUDGE" = "on" ]; then
  python3 tools/us_triage.py --limit 800 --budget-seconds 1800 | tee "$LOG/us-triage.log"
fi

TODAY=$(date +%Y-%m-%d)
if git ls-files --error-unmatch "editions/us-monitor-$TODAY.md" >/dev/null 2>&1; then
  echo "edition for $TODAY already committed: rewriting it, not resending the DM"
  python3 tools/us_monitor.py --edition | tee "$LOG/us-monitor.log"
else
  python3 tools/us_monitor.py --edition --dm | tee "$LOG/us-monitor.log"
fi

# The raw archive before the store: a store citing payloads the archive
# lacks is the worse failure. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
