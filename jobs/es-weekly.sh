#!/bin/bash
# Spain weekly: legislative initiatives, plenary votes with every deputy's
# position, and deputies of the Congreso de los Diputados
# (tools/es_rollcalls.py), then publish the raw archive and the store.
#
# Called by .github/workflows/es-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh es-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     ES_RECLASSIFY=true    re-derive every stored ES initiative's and
#                           division's areas, offline, before the pull (after
#                           config/taxonomy-es.yaml or watchlist-es changes)
#
# The first run backfills the XV legislature: 146 voting days and about
# 3,000 vote files at one request a second. The budget (45 minutes) stops it
# cleanly and the next run resumes from the store, so the backfill is spread
# over two or three runs rather than hammering congreso.es in one.
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps (in the gaps table and as [gap] lines in the log): that run is still
# published, and this script exits 0 so the caller commits the sidecars with
# it. Any other failure publishes NOTHING and exits non-zero.
# mini_run: commit editions
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Spain weekly}"
if [ "${ES_RECLASSIFY:-}" = "true" ]; then
  python3 tools/es_rollcalls.py --reclassify
fi
rc=0
python3 tools/es_rollcalls.py --budget-seconds 2700 || rc=$?
# The week ahead (src/agenda.py, tools/country_agenda.py): the agenda read
# into the store after the collector, so its bills match this week's store
# and the edition below shows it. Its failure is a [gap] line, never the run's.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_agenda.py es || echo "  [gap] the week-ahead agenda step failed"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "es-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "es-rollcalls recorded gaps; publishing what it stored"
# The weekly edition (src/country_edition.py, tools/es_monitor.py), to Chris
# alone by DM, archived to editions/. Once a day: an edition already
# committed for today is rewritten, not resent. A failed render never stops
# the publish below.
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
TODAY=$(date +%Y-%m-%d)
if git ls-files --error-unmatch "editions/es-monitor-$TODAY.md" >/dev/null 2>&1; then
  echo "edition for $TODAY already committed: rewriting it, not resending the DM"
  python3 tools/es_monitor.py --edition \
    || echo "  [gap] es-monitor: the edition failed to render; the store is still published"
else
  python3 tools/es_monitor.py --edition --dm \
    || echo "  [gap] es-monitor: the edition or its DM failed; the store is still published"
fi
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
