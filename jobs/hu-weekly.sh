#!/bin/bash
# Hungary weekly, phase 0: the Magyar Közlöny (official gazette), every new
# issue's contents (tools/hu_gazette.py), then the Hungarian edition, then
# publish the raw archive and the store.
#
# Called by .github/workflows/hu-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh hu-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards; publishing is this script's
# own last step, as mini_run.sh requires.
#
#     HU_RECLASSIFY=true    re-derive every stored entry's areas, offline,
#                           before the pull (after config/taxonomy-hu.yaml or
#                           config/watchlist-hu.yaml changes)
#
# The first run backfills the 43rd term from 9 May 2026: about 150 issues,
# one PDF each at one request every 2 s (about 60 MB, ten minutes). The
# budget (30 minutes) stops it cleanly, oldest first, and the next run
# resumes from the store. Later weeks read the RSS feed and the week's five
# or so new issues.
#
# Exit codes. The collector exits 3 when it stored what it could and recorded
# gaps (in the gaps table and as [gap] lines in the log): that run is still
# published, and this script exits 0 so the caller commits the sidecars with
# it. Any other failure publishes NOTHING and exits non-zero.
#
# THE EDITION: after the collector, the Hungarian edition
# (tools/hu_monitor.py, src/country_edition.py) is rendered to
# editions/hu-monitor-<date>.md and DMed to Chris alone. Once a day: an
# edition already committed for today is rewritten, not resent. Its failure
# is a [gap] line and never costs the store.
#
# mini_run: commit editions
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped when the store is published) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Hungary weekly}"
if [ "${HU_RECLASSIFY:-}" = "true" ]; then
  python3 tools/hu_gazette.py --reclassify
fi
rc=0
python3 tools/hu_gazette.py --budget-seconds 1800 || rc=$?
# The edition, from the store just collected (not when the collector failed
# outright: a half-read week is not worth a DM).
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  TODAY=$(date +%Y-%m-%d)
  if git ls-files --error-unmatch "editions/hu-monitor-$TODAY.md" >/dev/null 2>&1; then
    echo "edition for $TODAY already committed: rewriting it, not resending the DM"
    python3 tools/hu_monitor.py --edition || echo "  [gap] the edition failed to render"
  else
    python3 tools/hu_monitor.py --edition --dm || echo "  [gap] the edition or its DM failed"
  fi
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "hu-gazette failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "hu-gazette recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
