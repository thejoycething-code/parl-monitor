#!/bin/bash
# Apply session-judge queues scored OFF the Mini (jobs/judge-queue-out.sh),
# then do what the Sunday judge job does after its scores: rewrite the
# scored editions (one DM to Chris only if a lead changed), the vote pages,
# the Latam alert pass, then the archive and the store.
#
#     JUDGE_QUEUE_DATE=2026-10-11 tools/mini_run.sh judge-queue-in
#
# Reads every *.md in ~/runner/judge-queues/<date>/in/: an editions queue
# goes to tools/edition_judge.py --queue-in, a meanings queue to
# tools/vote_meanings.py --queue-in (each refuses the other's file, and every
# item strictly). Applied files move to done/, so a rerun adds nothing twice.
# The date is the export's, so the editions' windows match what was offered.
#
# mini_run: commit editions config docs partner_site reviews
set -o pipefail
cd "$(dirname "$0")/.."
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Editions session judge}"
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
DAY="${JUDGE_QUEUE_DATE:?set JUDGE_QUEUE_DATE to the export date}"
BASE="${RUNNER_HOME:-$HOME/runner}/judge-queues/$DAY"
mkdir -p "$BASE/done"
rc=0; applied=0
for f in "$BASE"/in/*.md; do
  [ -f "$f" ] || continue
  if grep -q 'edition-session-queue v1' "$f"; then
    python3 tools/edition_judge.py --date "$DAY" --queue-in "$f" || rc=1
  elif grep -q 'vote-meaning-queue v1' "$f"; then
    python3 tools/vote_meanings.py --date "$DAY" --queue-in "$f" || rc=1
  else
    echo "  [gap] $f is neither judge queue; left in place"; continue
  fi
  mv "$f" "$BASE/done/" && applied=$((applied + 1))
done
echo "judge-queue-in: $applied file(s) applied for $DAY"
if [ "$applied" -gt 0 ]; then
  python3 tools/edition_judge.py --date "$DAY" --rerender --dm || { echo "  [gap] the rewrite failed"; rc=1; }
  python3 tools/make_country_votes.py || echo "  [gap] the new-country vote pages failed; last week's stand"
  python3 tools/latam_alerts.py --send || echo "  [gap] latam-alerts failed; the next country run retries"
  python3 tools/raw_state.py --push || rc=1
  python3 tools/db_state.py --push || rc=1
fi
exit $rc
