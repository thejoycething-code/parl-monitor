#!/bin/bash
# US session judge on the Mac Mini (tools/mini_run.sh us-session-judge,
# Fridays 19:30 London, after the US weekly's 10:00 slot).
#
# THE DEFAULT, FREE JUDGE (Christopher, 9 October 2026: "Switch US, Ireland
# and Australia scoring to the free route"): Claude Code on the Mini, signed
# in to the work account, scores the US judge's pending items on the plan
# allowance, not the API (tools/session_judge.sh, tools/us_triage.py
# --queue-out / --queue-in). US_JUDGE, the paid API judge inside the weekly,
# stays the alternative and stays off.
#
# MINI ONLY, NO GITHUB WORKFLOW: the CLI and the subscription live here. Its
# heartbeat is its own ("US session judge", tools/coverage.py ON_DEMAND),
# never the weekly's, and a failure DMs through mini_run.sh.
#
# Order: score (at most SESSION_JUDGE_MAX items, 150 by default, 25 to a
# session, newest first), then rewrite this week's edition so it carries the
# scores (no DM: the weekly sent it), then the raw archive and the store.
# When claude is missing or not signed in, a [gap] line and a clean exit:
# the store is not touched or published.
#
# THE CAP ("5x, keep jobs lean"). A sitting week brings some 50 to 65 new
# items on our ground (federal bills about 5, Federal Register 1 to 2, the
# Court's few, Record speeches on their own words 12 to 25, state bills that
# moved some 25 out of session); the Record's backfill (1,083 speeches)
# lands over its first ten weeks at about 100 a week, and state bills in
# session are far more. 150 covers the week with room for the backfill,
# newest first; the rest wait, disclosed.
#
# mini_run: commit editions
set -o pipefail
cd "$(dirname "$0")/.."
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-US session judge}"
export PYTHONUNBUFFERED=1

rc=0
bash tools/session_judge.sh tools/us_triage.py "${SESSION_JUDGE_MAX:-150}" 25
jrc=$?
if [ "$jrc" -eq 3 ]; then
  exit 0                      # a gap, already logged; nothing to publish
fi
[ "$jrc" -eq 0 ] || rc=1

# The latest edition, rewritten with the scores. Its date fixes its window,
# so it is the same edition, ordered and annotated by the judge. No DM.
# Only an edition of the last seven days: an old one is history.
LATEST=$(ls editions/us-monitor-*.md 2>/dev/null | sort | tail -1 | sed 's/.*us-monitor-\(.*\)\.md/\1/')
WEEK_AGO=$(python3 -c 'import datetime; print(datetime.date.today() - datetime.timedelta(days=7))')
if [ -n "$LATEST" ] && [[ ! "$LATEST" < "$WEEK_AGO" ]]; then
  python3 tools/us_monitor.py --edition --date "$LATEST" || rc=1
fi

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
