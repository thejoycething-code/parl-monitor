#!/bin/bash
# Mexico weekly, the work: deputies, iniciativas, votes and positions of the
# Chamber of Deputies (tools/mx_rollcalls.py).
#
# Called by .github/workflows/mx-weekly.yml only. Unlike the other country
# jobs it has no Mac Mini caller: diputados.gob.mx refuses UK addresses, so
# the Mini's jobs/mx-weekly.sh dispatches the workflow instead. The workflow
# fetches the store first, then publishes the raw archive and the store in
# its own steps (under the commit step's condition, as every store workflow
# does) and commits the sidecars.
#
#     MX_RECLASSIFY=true    re-derive every stored iniciativa's and vote's
#                           areas, offline, before the pull (after
#                           config/taxonomy-es.yaml or watchlist-mx changes)
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps (in the gaps table and as [gap] lines in the log): this script exits 0
# for that, so the run is green and its gaps are read from the summary. Any
# other failure exits non-zero and fails the step.
#
# THE EDITION (10 October 2026): after the collector, the Mexican FORTNIGHTLY
# edition (tools/mx_monitor.py, src/editions/mx.py on
# src/country_edition.py) is rendered to editions/mx-monitor-<date>.md and
# DMed to Chris alone. It runs here, at the end of the GitHub job, because
# the work does (X9: odd ISO weeks), and its window is a fortnight
# (Country.cadence_days in src/editions/mx.py). Once a day: an edition already committed
# for today is rewritten, not resent. Its failure is a [gap] line and never
# costs the store. The workflow commits editions/ with data/.
set -eo pipefail
cd "$(dirname "$0")/.."
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Mexico weekly}"
if [ "${MX_RECLASSIFY:-}" = "true" ]; then
  python3 tools/mx_rollcalls.py --reclassify
fi
rc=0
# The first run reads every vote of the LXVI (285 to 2 October 2026, about
# nine pages each at one a second); the budget stops it cleanly and the rest
# drains on later runs.
python3 tools/mx_rollcalls.py --budget-seconds 2400 || rc=$?
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "mx-rollcalls failed (exit $rc)"
  exit "$rc"
fi
# The edition, from the store just collected (not when the collector failed
# outright: a half-read week is not worth a DM).
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  TODAY=$(date +%Y-%m-%d)
  if git ls-files --error-unmatch "editions/mx-monitor-$TODAY.md" >/dev/null 2>&1; then
    echo "edition for $TODAY already committed: rewriting it, not resending the DM"
    python3 tools/mx_monitor.py --edition || echo "  [gap] the edition failed to render"
  else
    python3 tools/mx_monitor.py --edition --dm || echo "  [gap] the edition or its DM failed"
  fi
fi
# Same-day vote briefs (tools/country_vote_briefs.py, src/country_vote_brief.py):
# this country's watched and tier-1 votes not briefed yet, written to
# data/briefs/ and sent in one DM to Chris alone, de-duplicated in
# data/vote-briefs/mx.json (committed with data/). Never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_vote_briefs.py --country mx --send \
    || echo "  [gap] vote briefs failed for mx; the next run retries"
fi
[ "$rc" -eq 3 ] && echo "mx-rollcalls recorded gaps; keeping what it stored"
exit 0
