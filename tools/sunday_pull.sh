#!/bin/zsh
# Unattended Sunday pull (handoff section 8: Sunday 21:00 pull + triage queue).
#
# Fetches all feeds, archives raw responses, filters, stores, and triages.
# TRIAGE=auto: live Claude scoring when config/secrets.yaml carries an
# anthropic_api_key, deterministic stub otherwise. The review file is ready
# by ~21:30 for optional human edits before Monday's unattended publish.
#
# Scheduled via launchd: ~/Library/LaunchAgents/net.citizengo.parlmonitor.pull.plist
# (launchd runs a missed slot on wake, unlike cron).

set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

# Week commencing = the Monday after the run (run happens Sunday evening).
WEEK=$(python3 - <<'PY'
import datetime
today = datetime.date.today()
days_ahead = (0 - today.weekday()) % 7  # Monday=0
if days_ahead == 0:
    days_ahead = 7  # if run on a Monday, target next week
print((today + datetime.timedelta(days=days_ahead)).isoformat())
PY
)

LOG="$REPO/data/pull-logs"
mkdir -p "$LOG"

echo "[$(date -Iseconds)] pull for week commencing $WEEK" >> "$LOG/$WEEK.log"
TRIAGE=auto python3 run_weekly.py --pull "$WEEK" >> "$LOG/$WEEK.log" 2>&1
echo "[$(date -Iseconds)] done (exit $?)" >> "$LOG/$WEEK.log"
