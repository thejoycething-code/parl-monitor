#!/bin/bash
# Portugal weekly: deputies, initiatives and plenary votes of the Assembleia
# da Republica (tools/pt_rollcalls.py), then publish the raw archive and the
# store.
#
# Called by .github/workflows/pt-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh pt-weekly. One script, two callers (the jobs/au-weekly.sh
# pattern). Both callers fetch the store first and commit data/ afterwards.
#
#     PT_RECLASSIFY=true    re-derive every stored PT initiative's and vote's
#                           areas, offline, before the pull (after a taxonomy
#                           or watchlist-pt change, and the day
#                           config/taxonomy-pt.yaml first lands)
#     PT_PUBLISH=false      collect only. The GitHub workflow sets it and
#                           publishes in its own steps, under the same
#                           condition as its commit step. On the Mini,
#                           publishing is this script's last step, as
#                           mini_run.sh requires.
#
# Exit codes on the Mini. The collector exits 3 when it stored what it could
# and recorded gaps (the deputies file failed but the initiatives were read):
# that run is still published, and this script exits 0 so mini_run.sh
# commits the sidecars with it. Exit 1 (no initiatives read) or anything else
# publishes NOTHING and exits non-zero; next week re-reads the whole
# legislature anyway. With PT_PUBLISH=false the collector's exit code is
# passed straight through, so a gap turns the GitHub step red and the
# failure alert hears of it.
#
# THE EDITION (10 October 2026): after the collector, the Portuguese weekly
# edition (tools/pt_monitor.py, src/country_edition.py) is rendered to
# editions/pt-monitor-<date>.md and DMed to Chris alone. Once a day: an
# edition already committed for today is rewritten, not resent. Its failure
# is a [gap] line and never costs the store.
#
# mini_run: commit editions profiles briefs
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped by db_state.py --push) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Portugal weekly}"
if [ "${PT_RECLASSIFY:-}" = "true" ]; then
  python3 tools/pt_rollcalls.py --reclassify
  python3 tools/pt_chamber.py --reclassify
fi
rc=0
# PT6 (10 October 2026): PT_LEGISLATURE=XV or XVI reads that legislature's
# files instead of the current one (the backfill, dispatched from CI).
leg=()
case "${PT_LEGISLATURE:-}" in
  "") ;;
  XV|XVI|XVII) leg=(--legislature "$PT_LEGISLATURE") ;;
  *) echo "pt-weekly: unknown legislature '${PT_LEGISLATURE}'"; exit 2 ;;
esac
python3 tools/pt_rollcalls.py --budget-seconds 2700 "${leg[@]}" || rc=$?
# X8 (10 October 2026): the Tribunal Constitucional's acórdãos
# (tools/pt_courts.py): 30 s between requests, at most ten rulings read, so
# about six minutes; a 429 ends it with one gap. Not on a backfill run.
# Gaps go to the store; a failure never stops the run.
if { [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; } && [ -z "${PT_LEGISLATURE:-}" ]; then
  python3 tools/pt_courts.py \
    || echo "  [gap] pt-courts recorded gaps or failed; the next run retries"
fi
# What was said and asked in the chamber (tools/pt_chamber.py, parity layer 5):
# time-boxed to what is left of the hour, never fatal, skipped on GitHub and
# on a backfill run (PT_LEGISLATURE set).
if [ -z "${PT_LEGISLATURE:-}" ]; then
  bash tools/chamber_step.sh pt "$SECONDS"
fi
# The edition, from the store just collected (not when the collector failed
# outright: a half-read week is not worth a DM; nor on a backfill run,
# PT_LEGISLATURE set).
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
if { [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; } && [ -z "${PT_LEGISLATURE:-}" ]; then
  TODAY=$(date +%Y-%m-%d)
  if git ls-files --error-unmatch "editions/pt-monitor-$TODAY.md" >/dev/null 2>&1; then
    echo "edition for $TODAY already committed: rewriting it, not resending the DM"
    python3 tools/pt_monitor.py --edition || echo "  [gap] the edition failed to render"
  else
    python3 tools/pt_monitor.py --edition --dm || echo "  [gap] the edition or its DM failed"
  fi
fi
# Member profiles (tools/member_profiles.py, src/member_profiles.py): profiles/pt/
# rewritten from the store just collected and committed with it; never posted
# or DMed. A failure is a [gap] line and never costs the store.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_profiles.py pt \
    || echo "  [gap] member-profiles: the profiles failed to render; the store is still published"
fi
if [ "${PT_PUBLISH:-true}" = "false" ]; then
  exit "$rc"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "pt-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "pt-rollcalls recorded gaps; publishing what it stored"
# Campaign brief drafts (tools/country_briefs.py, src/country_briefs.py): a
# draft RF4 brief in briefs/ for each new watched or tier-1 bill, NOT READY
# until its stances are confirmed in config/pt_stance.yaml; unedited briefs
# are refreshed. Offline, from the store as it stands; sends nothing. A
# failure is a [gap] line and never costs the store.
python3 tools/country_briefs.py --cc pt \
  || echo "  [gap] country-briefs failed for pt; last week's briefs stand"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
