#!/bin/bash
# A collector's time budget, from what the job has left (11 October 2026).
#
#     python3 tools/xx_rollcalls.py --budget-seconds "$(bash tools/collector_budget.sh 2700 "$SECONDS")"
#     bash tools/collector_budget.sh <cap> <job seconds so far> [later steps' budgets]
#
# Prints the smaller of <cap> and the job's limit less what it has spent,
# less the seconds its own later budgeted steps may take (the third
# argument), less 25 minutes for the unbudgeted steps and the publish.
#
# WHY. The country weeklies gave their collectors a fixed 45 minutes under
# the Mini's JOB_TIMEOUT of an hour. On the Mini the publish alone now takes
# 13 to 16 minutes (from the raw archive's publish to the store's, in the
# sidecars of the Mini's runs on 10 and 11 October 2026: a 1.64 to 1.76 GB
# store uploaded from the Mini's line, against about 40 seconds on GitHub),
# and the vote briefs, alerts, profiles, briefs, agenda and edition run
# after the collector in the same hour. The Dominican Republic's first
# backfill (10 October) spent its 45 minutes and was killed at 3600 s before
# it published. PUBLISH_S keeps 20 minutes for the publish (room for the
# store to grow) and STEPS_S 5 for the steps between collector and publish,
# including a collector's overrun past its last budget check.
#
# ON GITHUB (GITHUB_ACTIONS=true, the backup) the cap is printed unchanged:
# the publish takes under a minute there and each workflow's timeout was set
# around these caps.
#
# The limit is JOB_TIMEOUT, which tools/mini_run.sh exports (an hour unless a
# plist sets it). Never less than 60 s, so a collector still reads its
# cheapest parts and records the gap for the next run (tools/chamber_step.sh
# skips its step at 60).
cap="${1:?usage: collector_budget.sh <cap> <job seconds so far> [later]}"
spent="${2:-0}"
later="${3:-0}"
PUBLISH_S=1200
STEPS_S=300
if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
  echo "$cap"
  exit 0
fi
limit="${JOB_TIMEOUT:-3600}"
left=$(( limit - spent - later - PUBLISH_S - STEPS_S ))
[ "$left" -lt 60 ] && left=60
echo $(( left < cap ? left : cap ))
