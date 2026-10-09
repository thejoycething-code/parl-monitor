#!/bin/bash
# Honduras weekly: the Congreso Nacional's deputies, sessions and their
# agendas, the most recent legislative files (expedientes), press releases,
# and the issues of La Gaceta (tools/hn_rollcalls.py), then publish the raw
# archive and the store.
#
# There are no recorded votes to collect: the Congreso publishes none
# (docs/honduras-scope.md). Phase 1 is the record of what was tabled,
# scheduled and approved.
#
# Called by .github/workflows/hn-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh hn-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     HN_RECLASSIFY=true    re-derive every stored HN row's areas, offline,
#                           before the pull (after config/taxonomy-es.yaml or
#                           config/watchlist-hn.yaml changes)
#
# The first run backfills: about 360 session agendas (two requests each),
# press releases back to 25 January 2026 (about 13 pages) and La Gaceta
# since January (about 30 pages), at one request every 1.2 seconds. The
# budget (40 minutes) stops it cleanly and the next run resumes from the
# store. Later weeks are a few dozen requests.
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps (in the gaps table and as [gap] lines in the log): that run is still
# published, and this script exits 0 so the caller commits the sidecars with
# it. Any other failure publishes NOTHING and exits non-zero.
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Honduras weekly}"
if [ "${HN_RECLASSIFY:-}" = "true" ]; then
  python3 tools/hn_rollcalls.py --reclassify
fi
rc=0
python3 tools/hn_rollcalls.py --budget-seconds 2400 || rc=$?
# Instant Latam alerts (tools/latam_alerts.py): this country's watched and
# tier-1 items, a short DM each to Chris alone, de-duplicated in
# data/latam-alerts/hn.json (committed with data/). Never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/latam_alerts.py --country hn --send \
    || echo "  [gap] latam-alerts failed for hn; the next run retries"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "hn-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "hn-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
