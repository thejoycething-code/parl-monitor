#!/bin/bash
# The forward regional-agenda step of a country weekly (16 October 2026):
# the regional parliaments' upcoming plenary and committee business,
# tools/regional_agenda.py <cc>, run after the country's regional collector
# and before its edition, into regional_agenda (src/regional_agenda.py).
#
#     bash tools/regional_agenda_step.sh <cc> "$SECONDS" [cap seconds]
#
# TIME. What is left of the job's hour after the publish and the later steps
# (tools/collector_budget.sh), at most the cap (default 300 s). A minute or
# less left: it says so and skips; the stored forward rows stand (they carry
# their own last_seen) and the next run re-reads the whole horizon.
#
# ON GITHUB (the backup run) the step runs with the cap unchanged, like the
# regional collectors: a forward agenda not read in a week is a week the
# countdown shows stale dates.
#
# NEVER FATAL. Every region not read is a [gap] line and a gaps row
# ('<cc>-regional-agenda'); a failure never costs the store, the edition or
# the publish.
cc="${1:?usage: regional_agenda_step.sh <cc> <job seconds so far> [cap]}"
spent="${2:-0}"
cap="${3:-300}"
budget=$(bash tools/collector_budget.sh "$cap" "$spent")
if [ "$budget" -le 60 ]; then
  echo "  [gap] ${cc}-regional-agenda: no time left this run (${spent}s spent); the stored forward agenda stands"
  exit 0
fi
python3 tools/regional_agenda.py "$cc" --budget-seconds "$budget" \
  || echo "  [gap] ${cc}-regional-agenda exited $? (regions not read are in the gaps table); the store and edition go on"
exit 0
