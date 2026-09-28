#!/bin/zsh
# Laptop clock for the Monday publish (28 Sept 2026).
#
# Since ~11 Sept GitHub has been CREATING this repo's scheduled runs 2-6 hours
# after their cron, so the 04:00 London edition landed at 09:35-10:35. A
# workflow_dispatch starts at once, so launchd runs this at 04:00 and 05:00
# London (local time, so DST is free) and it dispatches Monday publish with
# the Slack post on. The Actions crons stay as backup.
#
# If the laptop is asleep, launchd runs the missed slot once on wake. Any run
# created since Monday 00:00 London that is queued, running or succeeded
# counts as covered; a failed or cancelled one does not, so 05:00 retries it.
# Duplicates are harmless: the publish is idempotent per week (publish_log).
#
# Uses the thejoycething-code gh login on this Mac. Never a second token.

set -u
GH=/Users/chrisjoyce/.local/bin/gh
REPO=thejoycething-code/parl-monitor
WF=monday-publish.yml
stamp() { TZ=Europe/London date '+%Y-%m-%d %H:%M:%S %Z'; }
notify() { /usr/bin/osascript -e "display notification \"$1\" with title \"Parl monitor clock\"" 2>/dev/null; }

echo "[$(stamp)] clock fired"

runs=$("$GH" run list --repo "$REPO" --workflow "$WF" --limit 20 \
  --json databaseId,createdAt,status,conclusion,event,url 2>&1) || {
  echo "FAILED: gh run list: $runs"; notify "FAILED to list runs - see launchd-dispatch.out"; exit 1; }

covered=$(print -r -- "$runs" | /usr/bin/python3 -c '
import json, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
ldn = ZoneInfo("Europe/London")
now = datetime.now(ldn)
monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
for r in json.load(sys.stdin):
    made = datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00")).astimezone(ldn)
    if made >= monday and (r["status"] != "completed" or r["conclusion"] == "success"):
        print("{} ({}, {}/{}) {}".format(r["databaseId"], r["event"], r["status"], r["conclusion"], r["url"]))
        break
')

if [[ -n "$covered" ]]; then
  echo "SKIPPED: already covered this week by run $covered"
  exit 0
fi

out=$("$GH" workflow run "$WF" --repo "$REPO" --ref main -f dry_run=false 2>&1) || {
  echo "FAILED: gh workflow run: $out"; notify "FAILED to dispatch Monday publish - see launchd-dispatch.out"; exit 1; }
sleep 10
new=$("$GH" run list --repo "$REPO" --workflow "$WF" --limit 1 --json url,status --jq '.[0] | "\(.status) \(.url)"' 2>&1)
echo "DISPATCHED: $new"
