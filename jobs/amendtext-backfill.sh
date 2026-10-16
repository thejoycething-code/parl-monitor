#!/bin/bash
# Amendment text backlog (16 October 2026, tools/amendment_text.py), BY HAND on
# the Mac Mini. Not a feed and not scheduled (no plist, no workflow): each
# country's weekly reads the amendment, motion or order-of-the-day texts of NEW
# votes within its budget, but the stored backlog would take weeks that way
# (measured on the laptop, 16 October 2026: Netherlands about 24,500 zaken at
# 0.6 s each, four hours; France about 7,400 scrutins, an hour or two by HTTP
# Range; Italy about 11,000 Camera votes, 20 minutes; Germany 635 polls, 5
# minutes). Each run reads for what the hour leaves and stops; a vote is read
# once, so rerun it until every country says nothing is left for later, never
# while a country weekly runs (mini_run.sh's lock keeps them apart anyway).
#
#   cd ~ && AMENDTEXT_CC="nl fr" nohup ~/runner/parl-monitor/tools/mini_run.sh amendtext-backfill \
#     >> ~/runner/logs/amendtext-backfill.log 2>&1 &
#
#     AMENDTEXT_CC="..."   the countries, in order (default: nl fr it de pt es)
#
# Then the raw archive and the store are published, with every gated match
# applied to its vote (the weekly's step does the same each week).
set -o pipefail
cd "$(dirname "$0")/.."
# Its own heartbeat, never the weeklies' (tools/coverage.py ON_DEMAND).
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Amendment text backfill}"
export PYTHONUNBUFFERED=1
python3 tools/raw_state.py --pull || exit 1
rc=0
for cc in ${AMENDTEXT_CC:-nl fr it de pt es}; do
  r=0
  python3 tools/amendment_text.py --cc "$cc" \
    --budget-seconds "$(bash tools/collector_budget.sh 3300 "$SECONDS")" || r=$?
  if [ "$r" -ne 0 ] && [ "$r" -ne 3 ]; then
    echo "  [gap] amendment text for $cc failed (exit $r)"
    rc=1
  fi
done
# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
