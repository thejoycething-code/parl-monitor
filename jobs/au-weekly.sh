#!/bin/bash
# Australia weekly: members, bills and House and Senate divisions of the
# Federal Parliament (tools/au_rollcalls.py), the judge when AU_JUDGE is on,
# the edition and its DM to Christopher (tools/au_monitor.py), then (on the
# Mini) publish the raw archive and the store.
#
# Called by .github/workflows/au-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh au-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards.
#
#     AU_RECLASSIFY=true    re-derive every stored AU bill's and division's
#                           areas, offline, before the pull (after a taxonomy
#                           or watchlist-au change)
#     AU_JUDGE=on           score new items (SPEND NEEDS A YES; read from the
#                           repo variable when unset and gh is available). Off.
#     AU_PUBLISH=false      collect and write the edition only. The GitHub workflow sets it and
#                           publishes in its own steps, under the same
#                           condition as its commit step, as every store
#                           workflow there does (tests/test_vote_tracker_display.py
#                           StorePublishGuardTests). On the Mini, publishing is
#                           this script's last step, as mini_run.sh requires.
#
# Exit codes on the Mini. The collector exits 3 when it stored what it could
# and recorded gaps (in the gaps table and as [gap] lines in the log): that
# run is still published, and this script exits 0 so mini_run.sh commits the
# sidecars with it. Any other failure publishes NOTHING and exits non-zero: a
# half-written store is not worth a published store whose sidecar never got
# committed, and the next run re-reads whatever this one missed. With
# AU_PUBLISH=false the collector's exit code is passed straight through, so a
# gap turns the GitHub step red and the failure alert hears of it.
#
# SPEAKS ONCE A DAY. An edition already committed for today means another
# run (the Mini, or a GitHub backup) has sent the DM: it is rewritten, not
# resent, as jobs/us-weekly.sh does.
#
# mini_run: commit editions
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped by db_state.py --push) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Australia weekly}"
# The DM goes to Christopher alone (decided 9 October 2026). On the Mini the
# Slack token comes from ~/runner/env, as for Division watch.
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
if [ "${AU_RECLASSIFY:-}" = "true" ]; then
  python3 tools/au_rollcalls.py --reclassify
fi
rc=0
python3 tools/au_rollcalls.py --budget-seconds 2700 || rc=$?
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "au-rollcalls failed (exit $rc); no edition, nothing published"
  exit "$rc"
fi

JUDGE="${AU_JUDGE:-}"
if [ -z "$JUDGE" ] && [ -z "${GITHUB_ACTIONS:-}" ] && command -v gh >/dev/null 2>&1; then
  JUDGE=$(gh variable get AU_JUDGE -R thejoycething-code/parl-monitor 2>/dev/null || true)
fi
if [ "$JUDGE" = "on" ]; then
  python3 tools/au_triage.py --limit 800 --budget-seconds 1800 || echo "  [gap] au-triage exited non-zero; unscored items wait for next week"
else
  python3 tools/au_triage.py --dry-run
fi

TODAY=$(date +%Y-%m-%d)
if git ls-files --error-unmatch "editions/au-monitor-$TODAY.md" >/dev/null 2>&1; then
  echo "edition for $TODAY already committed: rewriting it, not resending the DM"
  python3 tools/au_monitor.py --edition
else
  python3 tools/au_monitor.py --edition --dm
fi

if [ "${AU_PUBLISH:-true}" = "false" ]; then
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "au-rollcalls recorded gaps; publishing what it stored"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
