#!/bin/bash
# Slovakia weekly: members, prints, votes and interpellations of the
# Národná rada SR, and every member's position on the votes on our ground
# (tools/sk_rollcalls.py), then publish the raw archive and the store.
#
# Called by .github/workflows/sk-weekly.yml and, on the Mac Mini, by
# tools/mini_run.sh sk-weekly. One script, two callers. Both callers fetch
# the store first and commit data/ afterwards. (Same pattern as
# jobs/au-weekly.sh on the australia branch.)
#
#     SK_RECLASSIFY=true    re-derive every stored SK print's, vote's and
#                           interpellation's areas, offline, before the pull
#                           (after a taxonomy-sk or watchlist-sk change)
#     SK_PUBLISH=false      collect only. The GitHub workflow sets it and
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
# SK_PUBLISH=false the collector's exit code is passed straight through, so a
# gap turns the GitHub step red and the failure alert hears of it.
#
# The vote pages are slow (1.7 to 96 seconds each, measured 9 October 2026),
# so the collector stops reading them at 35 minutes (and the bill documents,
# SK6, at 10) and the next run resumes;
# everything else it reads in under a minute.
# mini_run: commit editions profiles briefs
set -eo pipefail
cd "$(dirname "$0")/.."
# The heartbeat (source_runs, stamped by db_state.py --push) is keyed on the
# workflow's name; on the Mini there is no GITHUB_WORKFLOW, so name it here or
# the coverage watch would never see the Mini's runs.
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Slovakia weekly}"
if [ "${SK_RECLASSIFY:-}" = "true" ]; then
  python3 tools/sk_rollcalls.py --reclassify
fi
rc=0
# SK6 (10 October 2026): the bill documents take the first 10 minutes of the
# old 45-minute positions budget, so the job's length is unchanged (the
# Mini's JOB_TIMEOUT and the workflow's are both an hour).
python3 tools/sk_rollcalls.py --doc-budget-seconds 600 --budget-seconds 2100 || rc=$?
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  # The weekly edition (src/country_edition.py, tools/sk_monitor.py), to Chris
  # alone by DM, archived to editions/. Once a day: an edition already
  # committed for today is rewritten, not resent. A failed render never stops
  # the publish below.
  export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
  TODAY=$(date +%Y-%m-%d)
  if git ls-files --error-unmatch "editions/sk-monitor-$TODAY.md" >/dev/null 2>&1; then
    echo "edition for $TODAY already committed: rewriting it, not resending the DM"
    python3 tools/sk_monitor.py --edition \
      || echo "  [gap] sk-monitor: the edition failed to render; the store is still published"
  else
    python3 tools/sk_monitor.py --edition --dm \
      || echo "  [gap] sk-monitor: the edition or its DM failed; the store is still published"
  fi
fi
# Member profiles (tools/member_profiles.py, src/member_profiles.py): profiles/sk/
# rewritten from the store just collected and committed with it; never posted
# or DMed. A failure is a [gap] line and never costs the store.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/member_profiles.py sk \
    || echo "  [gap] member-profiles: the profiles failed to render; the store is still published"
fi
if [ "${SK_PUBLISH:-true}" = "false" ]; then
  exit "$rc"
fi
# Same-day vote briefs (tools/country_vote_briefs.py, src/country_vote_brief.py):
# this country's watched and tier-1 votes not briefed yet, written to
# data/briefs/ and sent in one DM to Chris alone, de-duplicated in
# data/vote-briefs/sk.json (committed with data/). Never stops the run.
if [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; then
  python3 tools/country_vote_briefs.py --country sk --send \
    || echo "  [gap] vote briefs failed for sk; the next run retries"
fi
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "sk-rollcalls failed (exit $rc); nothing published"
  exit "$rc"
fi
[ "$rc" -eq 3 ] && echo "sk-rollcalls recorded gaps; publishing what it stored"
# Campaign brief drafts (tools/country_briefs.py, src/country_briefs.py): a
# draft RF4 brief in briefs/ for each new watched or tier-1 bill, NOT READY
# until its stances are confirmed in config/sk_stance.yaml; unedited briefs
# are refreshed. Offline, from the store as it stands; sends nothing. A
# failure is a [gap] line and never costs the store.
python3 tools/country_briefs.py --cc sk \
  || echo "  [gap] country-briefs failed for sk; last week's briefs stand"
# The archive before the store: a store that cites payloads the archive
# lacks is the worse of the two failures. Both merge, never clobber.
python3 tools/raw_state.py --push
python3 tools/db_state.py --push
