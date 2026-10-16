#!/bin/bash
# Provinces session judge on the Mac Mini (tools/mini_run.sh prov-session-judge,
# Wednesdays 16:15 London, after the Provinces weekly's 11:00 slot).
#
# THE DEFAULT, FREE JUDGE (Christopher, 9 October 2026, "option 3"): Claude
# Code on the Mini, signed in to the work account, scores the provinces'
# pending items on the plan allowance, not the API (tools/session_judge.sh,
# tools/prov_triage.py --queue-out / --queue-in). PROV_JUDGE, the paid API
# judge inside the weekly, stays the alternative and stays off.
#
# MINI ONLY, NO GITHUB WORKFLOW: the CLI and the subscription live here. Its
# heartbeat is its own ("Provinces session judge", tools/coverage.py
# ON_DEMAND), never the weekly's, and a failure DMs through mini_run.sh.
#
# Order: score (at most SESSION_JUDGE_MAX items, 100 by default, 25 to a
# session), then rewrite this week's edition so it carries the scores (no
# DM: the weekly sent it), then the raw archive and the store. When claude
# is missing or not signed in, a [gap] line and a clean exit: the store is
# not touched or published.
#
# CANADA FEDERAL TOO (16 October 2026, Chris: "ALL model scoring moves off
# the paid Claude API"). The federal judge (tools/ca_triage.py: petitions and
# Supreme Court judgments) spent on the API inside the Canada weekly
# (Tuesdays 11:00) whenever a key was set; it now runs only with
# CA_TRIAGE_PAID=1 (src/paid_ai.py), and this job scores the federal rows
# after the provinces' with a cap of its own, CA_SESSION_MAX (60), 25 to a
# session, then rewrites the latest federal edition too. Steady state
# (api_spend, Oct 2026, the 2020 backfill week excluded): 30 to 50 rows a week.
#
# mini_run: commit editions
set -o pipefail
cd "$(dirname "$0")/.."
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Provinces session judge}"
export PYTHONUNBUFFERED=1

rc=0
bash tools/session_judge.sh tools/prov_triage.py "${SESSION_JUDGE_MAX:-100}" 25
jrc=$?
if [ "$jrc" -eq 3 ]; then
  exit 0                      # a gap, already logged; nothing to publish
fi
[ "$jrc" -eq 0 ] || rc=1

# Canada federal, with its own cap (claude is signed in: the provinces ran).
bash tools/session_judge.sh tools/ca_triage.py "${CA_SESSION_MAX:-60}" 25 || rc=1

# The latest edition, rewritten with the scores. Its date fixes its window,
# so it is the same edition, ordered and annotated by the judge. No DM.
# Only an edition of the last seven days: an old one is history.
LATEST=$(ls editions/prov-monitor-*.md 2>/dev/null | sort | tail -1 | sed 's/.*prov-monitor-\(.*\)\.md/\1/')
WEEK_AGO=$(python3 -c 'import datetime; print(datetime.date.today() - datetime.timedelta(days=7))')
if [ -n "$LATEST" ] && [[ ! "$LATEST" < "$WEEK_AGO" ]]; then
  python3 tools/prov_monitor.py --edition --date "$LATEST" || rc=1
fi
LATEST=$(ls editions/ca-monitor-*.md 2>/dev/null | sort | tail -1 | sed 's/.*ca-monitor-\(.*\)\.md/\1/')
if [ -n "$LATEST" ] && [[ ! "$LATEST" < "$WEEK_AGO" ]]; then
  python3 tools/ca_monitor.py --edition --date "$LATEST" || rc=1
fi

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
