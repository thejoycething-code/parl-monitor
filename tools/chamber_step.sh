#!/bin/bash
# The chamber step of a country weekly (parity layer 5, 10 October 2026):
# what was said and asked in the chamber, tools/<cc>_chamber.py, run after the
# collector and before the edition so the edition carries it.
#
#     bash tools/chamber_step.sh <cc> "$SECONDS"
#
# TIME. The weeklies run under the Mini's JOB_TIMEOUT (an hour unless the
# plist says otherwise), so this step gets what is left of it after the
# publish and the later steps (tools/collector_budget.sh), at most ten
# minutes (the second argument is the job's own $SECONDS). A minute or less
# left: it says so and skips; the next run's three-week lookback reads what
# this one did not.
#
# NOT ON GITHUB. The GitHub workflows are the backup for a Mini that did not
# run, with their own 30 to 60 minute timeouts and the Actions minutes to
# save; the step is skipped there and the Mini's next run catches up.
#
# NEVER FATAL. A failure is a [gap] line (and a row in the gaps table) and
# never costs the store, the edition or the publish.
cc="${1:?usage: chamber_step.sh <cc> <job seconds so far>}"
spent="${2:-0}"
if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
  echo "chamber step: skipped on GitHub (the Mini's next run catches up)"
  exit 0
fi
budget=$(bash tools/collector_budget.sh 600 "$spent")
if [ "$budget" -le 60 ]; then
  echo "  [gap] ${cc}-chamber: no time left this run (${spent}s spent); the next run reads it"
  exit 0
fi
python3 "tools/${cc}_chamber.py" --budget-seconds "$budget" \
  || echo "  [gap] ${cc}-chamber exited $? (see the gaps table); the store and edition go on"
exit 0
