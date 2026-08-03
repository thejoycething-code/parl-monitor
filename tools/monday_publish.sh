#!/bin/zsh
# Unattended Monday publish (handoff section 8: Monday 06:30 render after
# review edits) extended with publishing: render the edition, post summary +
# canvas to Slack, create the Asana reading task. Review decisions saved into
# reviews/review-<week>.md before this runs are applied; if nobody reviewed,
# the edition ships WATCH/NOTE-only (ACT requires a human-set owner).
#
# Scheduled via launchd: ~/Library/LaunchAgents/net.citizengo.parlmonitor.monday.plist

set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

WEEK=$(python3 -c "import datetime; t=datetime.date.today(); print((t - datetime.timedelta(days=t.weekday())).isoformat())")
LOG="$REPO/data/pull-logs"
mkdir -p "$LOG"

echo "[$(date -Iseconds)] monday publish for $WEEK" >> "$LOG/$WEEK.log"
python3 run_monday.py "$WEEK" >> "$LOG/$WEEK.log" 2>&1
echo "[$(date -Iseconds)] publish done (exit $?)" >> "$LOG/$WEEK.log"
