#!/bin/bash
# Brief narratives on the Mac Mini (tools/mini_run.sh brief-narratives,
# Sundays 18:15 London). Chris, 16 October 2026: "move brief narratives to the
# session judge". The Campaigns Brief builders (tools/make_briefs.py,
# tools/de_briefs.py) drafted their prose fields with the paid API, off since
# PR #209 (BRIEF_NARRATIVE_PAID); now Claude Code on this machine, signed in to
# the work account, drafts them on the plan allowance (tools/session_judge.sh:
# ANTHROPIC_API_KEY is removed from claude's environment, so a key in
# ~/runner/env can never turn this into API spend).
#
# WHEN: after the UK session judge (12:30) has scored the week's items, so the
# score-3 subjects exist, and after the editions session judge (16:45, about
# 15 minutes); before the German weekly (20:00, tools/de_briefs.py) and the
# Monday publish (04:00, tools/make_briefs.py), which build the briefs and so
# find the narratives already drafted. A longer run queues the next job on the
# runner lock, never the other way round.
#
# WHAT: tools/brief_narratives.py offers new Westminster subjects, then new
# German ones, then live briefs that shipped with placeholders (re-rendered in
# place; a UK sheet already on Drive is refilled by Monday's publisher while no
# person has edited it). ONE BRIEF TO A SESSION (each is twelve long fields
# and a fresh context drafts best), at most BRIEF_NARRATIVE_MAX (6) a week.
# What is not reached waits, its placeholders standing.
#
# MINI ONLY, NO GITHUB WORKFLOW: the CLI and the subscription live here. Its
# heartbeat is its own ("Brief narratives", tools/coverage.py ON_DEMAND), and a
# failure DMs through mini_run.sh. When claude is missing or signed out, a
# [gap] line: nothing is drafted and nothing is published.
#
# mini_run: commit briefs
set -o pipefail
cd "$(dirname "$0")/.."
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Brief narratives}"
export PYTHONUNBUFFERED=1

MAX="${BRIEF_NARRATIVE_MAX:-6}"
export CLAUDE_ROUND_TIMEOUT="${CLAUDE_ROUND_TIMEOUT:-780}"
rc=0

python3 tools/brief_narratives.py || rc=1          # the count before: pending, placeholders

SESSION_JUDGE_PROMPT="$(python3 -c 'import sys; sys.path.insert(0, "."); from src import brief_narratives as b; print(b.NARRATIVE_PROMPT)')" \
  bash tools/session_judge.sh tools/brief_narratives.py "$MAX" 1
jrc=$?
if [ "$jrc" -eq 3 ]; then
  exit 0                      # a gap, already logged: nothing drafted, nothing to publish
fi
[ "$jrc" -eq 0 ] || rc=1

python3 tools/brief_narratives.py || rc=1          # and after

python3 tools/db_state.py --push || rc=1
exit $rc
