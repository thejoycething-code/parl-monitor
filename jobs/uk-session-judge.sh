#!/bin/bash
# UK session judge on the Mac Mini (tools/mini_run.sh uk-session-judge,
# Sundays 12:30 London): between the Sunday pull (02:00, about 40 minutes)
# and the Monday publish (04:00), clear of Sunday's country weeklies (Uruguay
# 08:00, Dominican Republic 09:00, El Salvador 10:00, Bolivia 11:00, Honduras
# 14:00) and the editions session judge (16:45); behind any of them on the
# runner lock if one overruns.
#
# PAID AI OFF FOR THE UK WEEKLY (round 3, Chris, 16 October 2026). The
# Sunday pull's triage, its stance pass and the Monday devolved judge used the
# paid API whenever a key was set. Now they leave their work to this job:
# Claude Code on the Mini, signed in to the work account, on the plan
# allowance (tools/session_judge.sh: ANTHROPIC_API_KEY is removed from
# claude's environment, so a key in ~/runner/env can never turn this into
# API spend). The paid path survives only behind UK_PAID_JUDGE=1.
#
# THREE QUEUES, ONE WEEKLY BUDGET (SESSION_JUDGE_MAX, 200 items by default,
# 25 to a session), in this order so the edition's own scores come first:
#   1. the Sunday pull's items (tools/uk_pull_judge.py: watchlist, tier 1,
#      tier 2, newest first), at most UK_PULL_MAX (120);
#   2. the devolved rows (tools/devolved_triage.py: Holyrood, Senedd, NI,
#      divisions first), with what is left, at most UK_DEVOLVED_MAX (60);
#   3. the 5CA stances (tools/uk_stance_judge.py, displayable ground, newest
#      first), with what is left.
# A backlog spreads over weeks: what is not reached waits, disclosed, and the
# Monday render shows a pending tier-1 or watched item on rules alone.
# Measured steady state (api_spend, Sept to Oct 2026): 10 to 80 pull items,
# 10 to 70 devolved rows and up to 400 stance refs a week, nearly all of them
# migration-only refs that render nowhere and are skipped here; the
# displayable stance backlog was 25 refs on 16 October 2026.
#
# MINI ONLY, NO GITHUB WORKFLOW: the CLI and the subscription live here. Its
# heartbeat is its own ("UK session judge", tools/coverage.py ON_DEMAND),
# and a failure DMs through mini_run.sh. When claude is missing or not
# signed in, a [gap] line: nothing is scored and nothing is published.
#
# mini_run: commit reviews
set -o pipefail
cd "$(dirname "$0")/.."
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-UK session judge}"
export PYTHONUNBUFFERED=1

MAX="${SESSION_JUDGE_MAX:-200}"
PULL_MAX="${UK_PULL_MAX:-120}"
DEVOLVED_MAX="${UK_DEVOLVED_MAX:-60}"
rc=0
offered() { sed -n 's/.*; \([0-9][0-9]*\) offered, cap.*/\1/p' "$1" | tail -1; }
LOG=$(mktemp "${TMPDIR:-/tmp}/uk-judge.XXXXXX")
trap 'rm -f "$LOG"' EXIT

[ "$PULL_MAX" -gt "$MAX" ] && PULL_MAX=$MAX
bash tools/session_judge.sh tools/uk_pull_judge.py "$PULL_MAX" 25 > "$LOG" 2>&1
jrc=$?
cat "$LOG"
if [ "$jrc" -eq 3 ]; then
  exit 0                      # a gap, already logged: nothing scored, nothing to publish
fi
[ "$jrc" -eq 0 ] || rc=1
n=$(offered "$LOG"); left=$((MAX - ${n:-0}))

if [ "$left" -gt 0 ]; then
  want=$DEVOLVED_MAX; [ "$left" -lt "$want" ] && want=$left
  bash tools/session_judge.sh tools/devolved_triage.py "$want" 20 > "$LOG" 2>&1 || rc=1
  cat "$LOG"
  n=$(offered "$LOG"); left=$((left - ${n:-0}))
fi

if [ "$left" -gt 0 ]; then
  SESSION_JUDGE_PROMPT="$(python3 -c 'import sys; sys.path.insert(0, "tools"); import uk_stance_judge as s; print(s.STANCE_PROMPT)')" \
    bash tools/session_judge.sh tools/uk_stance_judge.py "$left" 25 || rc=1
else
  echo "stances: the scores used the week's $MAX session items; the stances wait a week"
fi

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
