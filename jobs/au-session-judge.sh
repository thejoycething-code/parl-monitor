#!/bin/bash
# Australia session judge on the Mac Mini (tools/mini_run.sh au-session-judge,
# Fridays 03:10 London, after the Australia weekly's 02:00 slot).
#
# THE DEFAULT, FREE JUDGE (Christopher, 9 October 2026: "Switch US, Ireland
# and Australia scoring to the free route"): Claude Code on the Mini, signed
# in to the work account, scores the Australian judge's pending items on the plan
# allowance, not the API (tools/session_judge.sh, tools/au_triage.py
# --queue-out / --queue-in). AU_JUDGE, the paid API judge inside the weekly,
# stays the alternative and stays off.
#
# MINI ONLY, NO GITHUB WORKFLOW: the CLI and the subscription live here. Its
# heartbeat is its own ("Australia session judge", tools/coverage.py ON_DEMAND),
# never the weekly's, and a failure DMs through mini_run.sh.
#
# Order: score (at most SESSION_JUDGE_MAX items, 100 by default, 25 to a
# session, newest first), then rewrite this week's edition so it carries the
# scores (no DM: the weekly sent it), then the raw archive and the store.
# When claude is missing or not signed in, a [gap] line and a clean exit:
# the store is not touched or published.
#
# THE CAP ("5x, keep jobs lean"). A sitting week brings about 30 new items
# on our ground (some 25 speeches on their own words, a few divisions and
# bills), so 100 covers the week, newest first; the debates backfill (about
# 690 speeches) drains at some 70 a week.
#
# mini_run: commit editions
set -o pipefail
cd "$(dirname "$0")/.."
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Australia session judge}"
export PYTHONUNBUFFERED=1

rc=0
bash tools/session_judge.sh tools/au_triage.py "${SESSION_JUDGE_MAX:-100}" 25
jrc=$?
if [ "$jrc" -eq 3 ]; then
  exit 0                      # a gap, already logged; nothing to publish
fi
[ "$jrc" -eq 0 ] || rc=1

# The latest edition, rewritten with the scores. Its date fixes its window,
# so it is the same edition, ordered and annotated by the judge. No DM.
# Only an edition of the last seven days: an old one is history.
LATEST=$(ls editions/au-monitor-*.md 2>/dev/null | sort | tail -1 | sed 's/.*au-monitor-\(.*\)\.md/\1/')
WEEK_AGO=$(python3 -c 'import datetime; print(datetime.date.today() - datetime.timedelta(days=7))')
if [ -n "$LATEST" ] && [[ ! "$LATEST" < "$WEEK_AGO" ]]; then
  python3 tools/au_monitor.py --edition --date "$LATEST" || rc=1
fi

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
