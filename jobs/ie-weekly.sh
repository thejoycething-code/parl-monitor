#!/bin/bash
# Ireland weekly: Oireachtas members, bills and divisions (with the amendment
# behind each amendment vote) into the ie_* tables; the week ahead,
# parliamentary questions and debate speeches (phase 2); the judge when
# IE_JUDGE is on; then the edition and its DM to Christopher.
#
# Called by .github/workflows/ie-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh ie-weekly. One script, two callers (docs/mac-mini.md).
# Both callers fetch the store first and commit data/ and editions/ after.
#
#     IE_RECLASSIFY=true   re-derive stored areas offline first (after a
#                          taxonomy or watchlist-ie change)
#     IE_JUDGE=on          score new items (Christopher's yes; read from the
#                          repo variable when unset and gh is available). ON
#                          since 9 October 2026.
#     IE_QUESTIONS_BUDGET / IE_DEBATES_BUDGET
#                          seconds for the questions and debates steps (else
#                          what the job has left, capped; see below)
#     IE_PUBLISH=false     leave publishing to the caller (the workflow, whose
#                          own guarded steps publish the archive and the
#                          store, as in us-weekly.yml); exit with the
#                          collector's status, so gaps turn the step red
#
# By default (the Mini) this script publishes too: the raw archive, then the
# store. GAPS DO NOT FAIL IT THEN. A published store whose sidecar is never
# committed is refused by every later pull (SHA MISMATCH), and mini_run.sh
# commits only after a clean exit. So a run that finished publishes and
# exits 0, its gaps in the gaps table and as "[gap]" lines in the log; a run
# that crashed publishes nothing and fails.
#
# SPEAKS ONCE A DAY, as jobs/us-weekly.sh does. An edition already committed
# for today means another run (the Mini, or a GitHub backup) has sent the DM:
# it is rewritten, not resent. The edition is written even in a week with
# gaps; it says what it holds.
#
# mini_run: commit editions
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat names the pipeline, not "local", when the Mini runs this
# (tools/db_state.py stamps GITHUB_WORKFLOW into source_runs).
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Ireland weekly}"
# The DM goes to Christopher alone (9 October 2026). On the Mini the Slack
# token comes from ~/runner/env, as for Division watch and the US weekly.
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
LOG="${IE_LOG:-$(mktemp -t ie-weekly.XXXXXX)}"
LOG_DIR="$(dirname "$LOG")"
if [ "${IE_RECLASSIFY:-}" = "true" ]; then
  python3 tools/ie_rollcalls.py --reclassify
fi
rc=0
python3 tools/ie_rollcalls.py --budget-seconds 1500 2>&1 | tee "$LOG" || rc=$?
if ! grep -q "  store: " "$LOG"; then
  echo "ie-weekly: the collector did not finish (exit $rc); no edition, nothing published"
  [ "$rc" -eq 0 ] && rc=1
  exit "$rc"
fi
[ "$rc" -ne 0 ] && echo "ie-weekly: finished with gaps (exit $rc); going on with what it stored"

# Phase 2 (9 October 2026): the week ahead, parliamentary questions and debate
# speeches, before the judge (which scores questions and speeches) and the
# edition (its Coming up, Questions and Debate sections). Their gaps are
# logged, never fatal: the edition says what the store holds, as in
# jobs/us-weekly.sh.
#
# The schedule is one page (about 1.7 MB) and seconds. Questions and debates
# read a week at a time, newest first, and their backfill to the Dáil's first
# sitting (about 95 weeks: 30 s a week of questions, 25 s a week of debates,
# measured) DRAINS OVER RUNS. Each gets WHAT THE JOB HAS LEFT, capped: at most
# 5 minutes each on GitHub (the backup; keep it inside the workflow's 45) and
# 15 and 20 on the Mini, always keeping 20 minutes for the judge and 5 for
# the edition and the store transfers.
python3 tools/ie_schedule.py | tee "$LOG_DIR/ie-schedule.log" \
  || echo "  [gap] the week-ahead step ended with gaps; the edition says what it has"
if [ -n "${GITHUB_ACTIONS:-}" ]; then JOB_LIMIT=2700; Q_MAX=300; D_MAX=300
else JOB_LIMIT="${JOB_TIMEOUT:-10800}"; Q_MAX=900; D_MAX=1200; fi
budget_left() {  # $1: the step's cap
  local left=$(( JOB_LIMIT - SECONDS - 1200 - 300 ))
  echo $(( left < $1 ? left : $1 ))
}
Q_BUDGET="${IE_QUESTIONS_BUDGET:-$(budget_left "$Q_MAX")}"
if [ "$Q_BUDGET" -ge 60 ]; then
  python3 tools/ie_questions.py --budget-seconds "$Q_BUDGET" | tee "$LOG_DIR/ie-questions.log" \
    || echo "  [gap] the questions step ended with gaps; the edition shows what the store holds"
else
  echo "  [gap] questions skipped: ${Q_BUDGET}s left in the job's budget" | tee "$LOG_DIR/ie-questions.log"
fi
D_BUDGET="${IE_DEBATES_BUDGET:-$(budget_left "$D_MAX")}"
if [ "$D_BUDGET" -ge 60 ]; then
  python3 tools/ie_debates.py --budget-seconds "$D_BUDGET" | tee "$LOG_DIR/ie-debates.log" \
    || echo "  [gap] the debates step ended with gaps; the edition shows what the store holds"
else
  echo "  [gap] debates skipped: ${D_BUDGET}s left in the job's budget" | tee "$LOG_DIR/ie-debates.log"
fi

JUDGE="${IE_JUDGE:-}"
if [ -z "$JUDGE" ] && [ -z "${GITHUB_ACTIONS:-}" ] && command -v gh >/dev/null 2>&1; then
  JUDGE=$(gh variable get IE_JUDGE -R thejoycething-code/parl-monitor 2>/dev/null || true)
fi
if [ "$JUDGE" = "on" ]; then
  python3 tools/ie_triage.py --budget-seconds 1200 | tee "$LOG_DIR/ie-triage.log" || rc=$?
fi

TODAY=$(date +%Y-%m-%d)
if git ls-files --error-unmatch "editions/ie-monitor-$TODAY.md" >/dev/null 2>&1; then
  echo "edition for $TODAY already committed: rewriting it, not resending the DM"
  python3 tools/ie_monitor.py --edition | tee "$LOG_DIR/ie-monitor.log"
else
  python3 tools/ie_monitor.py --edition --dm | tee "$LOG_DIR/ie-monitor.log"
fi

if [ "${IE_PUBLISH:-true}" != "true" ]; then
  exit "$rc"
fi
# The archive before the store: a store citing payloads the archive lacks is
# the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
