#!/bin/bash
# Export the session judge's queues for scoring OFF the Mini (Chris,
# 11 October 2026: "do 400 of them now on this Claude account rather than the
# mini"). One-off or occasional, never scheduled.
#
#     JUDGE_QUEUE_MAX=400 tools/mini_run.sh judge-queue-out
#
# Writes, under ~/runner/judge-queues/<date>/out/ (outside the clone, so
# nothing is committed): editions.md, the editions' pending items in the
# weekly job's priority order, then meanings.md, the vote meanings with what
# is left of JUDGE_QUEUE_MAX. Reads the store only: it changes no table, so
# there is nothing to publish. The filled-in files go back in
# ~/runner/judge-queues/<date>/in/ and jobs/judge-queue-in.sh applies them,
# under the same lock as every other store writer.
set -eo pipefail
cd "$(dirname "$0")/.."
MAX="${JUDGE_QUEUE_MAX:-400}"
DAY="${JUDGE_QUEUE_DATE:-$(date +%F)}"
OUT="${RUNNER_HOME:-$HOME/runner}/judge-queues/$DAY/out"
mkdir -p "$OUT" "${OUT%/out}/in"
LOG=$(python3 tools/edition_judge.py --date "$DAY" --queue-out "$OUT/editions.md" --limit "$MAX")
echo "$LOG"
n=$(sed -n 's/.*session queue: \([0-9][0-9]*\) item(s) written.*/\1/p' <<<"$LOG" | tail -1)
left=$((MAX - ${n:-0}))
if [ "$left" -gt 0 ]; then
  python3 tools/vote_meanings.py --date "$DAY" --queue-out "$OUT/meanings.md" --limit "$left"
fi
echo "judge queues for $DAY in $OUT"
